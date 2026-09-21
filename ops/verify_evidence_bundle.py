"""Verify the pre-auth evidence inventory; never activate or complete a goal.

The optional ZIP contains only explicitly inventoried, non-secret evidence.
Raw session exports stay local and separate from this review bundle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "ops/verification/preauth-20260922/manifest.json"
PRODUCT_AC = {f"AC{i:02}" for i in (*range(1, 17), *range(23, 43))}
EVENT_AC = {f"AC{i:02}" for i in range(17, 23)}


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe_path(root: Path, name: str, *, raw: bool = False) -> Path:
    relative = PurePosixPath(name)
    if relative.is_absolute() or ".." in relative.parts or "\\" in name or ":" in name:
        raise ValueError("Evidence paths must be relative to the workspace")
    forbidden = {".env", "auth.json", ".git", "private", "REBUILD_EVALUATOR_v1"}
    if any(part in forbidden or part.startswith(".env.") for part in relative.parts):
        raise ValueError("Private or excluded evidence path")
    if "node_modules" in relative.parts and name != "tools/omx/node_modules/oh-my-codex/dist/ultragoal/artifacts.js":
        raise ValueError("Only the inspected OMX contract source may be bundled")
    if "sessions" in relative.parts and not raw:
        raise ValueError("Raw sessions cannot enter the review ZIP")
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError(f"Missing or external evidence: {name}")
    return target


def validate(manifest: dict, root: Path = ROOT) -> dict:
    if manifest.get("product") != "RE:Build Agent" or manifest.get("scope") != "PRE_AUTH_EVIDENCE_PREPARATION":
        raise ValueError("Unexpected product or evidence scope")
    if manifest.get("product_complete") is not False or manifest.get("native_goal_status") != "blocked":
        raise ValueError("Preparation cannot claim product/goal completion")
    criteria = manifest["criteria"]
    ids = [row["id"] for row in criteria]
    if len(ids) != 36 or set(ids) != PRODUCT_AC or set(manifest["deferred_event_criteria"]) != EVENT_AC:
        raise ValueError("Acceptance coverage must be exactly 36 product and 6 deferred event criteria")
    artifacts = manifest["artifacts"]
    artifact_ids = [item["id"] for item in artifacts]
    if len(artifact_ids) != len(set(artifact_ids)):
        raise ValueError("Duplicate artifact IDs")
    index = {item["id"]: item for item in artifacts}
    for item in artifacts:
        path = safe_path(root, item["path"])
        if digest(path) != item["sha256"]:
            raise ValueError(f"Evidence changed: {item['id']}")
        if not item.get("boundary"):
            raise ValueError("Every artifact needs an evidence boundary")
    for row in criteria:
        if row.get("final_acceptance") != "PENDING" or not row.get("remaining"):
            raise ValueError(f"Pre-auth criterion cannot be promoted: {row['id']}")
        if not row.get("evidence") or any(ref not in index for ref in row["evidence"]):
            raise ValueError(f"Missing evidence reference: {row['id']}")
        if not row.get("tests") or not row.get("implementation"):
            raise ValueError(f"Missing implementation/test mapping: {row['id']}")
        for name in row["implementation"] + row["tests"]:
            if name not in {item["path"] for item in artifacts}:
                raise ValueError(f"Unhashed code/test reference: {name}")
    gate = json.loads(safe_path(root, manifest["pending_gate"]).read_text(encoding="utf-8-sig"))
    if (gate["aiSlopCleaner"]["status"] != "pending"
            or gate["verification"]["status"] != "pending"
            or gate["codeReview"]["recommendation"] != "REQUEST_CHANGES"
            or gate["codeReview"]["architectStatus"] != "BLOCK"
            or gate["architectureInvariantGate"]["status"] != "pending"):
        raise ValueError("Pending OMX template must retain non-passing statuses")
    for invariant in gate["architectureInvariantGate"]["invariants"]:
        if invariant.get("status") != "pending" or not invariant.get("blockers"):
            raise ValueError("Unproved invariant cannot be submitted as proved")
    if not manifest.get("blockers"):
        raise ValueError("Required live/final blockers must remain visible")
    return {"status": "PASS", "scope": manifest["scope"], "product_criteria": 36,
            "deferred_event_criteria": 6, "hashed_artifacts": len(artifacts),
            "product_complete": False, "omx_strict_executed": False}


def verify_raw_snapshots(manifest: dict, root: Path = ROOT) -> int:
    for segment in manifest["raw_session_snapshots"]:
        path = safe_path(root, segment["path"], raw=True)
        if digest(path) != segment["sha256"]:
            raise ValueError("Raw snapshot hash changed")
        with path.open(encoding="utf-8") as stream:
            count = sum(1 for line in stream if line.strip() and json.loads(line))
        if count != segment["events"]:
            raise ValueError("Raw snapshot record count changed")
    return len(manifest["raw_session_snapshots"])


def write_bundle(manifest: dict, manifest_path: Path, target: Path, root: Path = ROOT) -> dict:
    destination = target.resolve()
    if not destination.is_relative_to((root / "ops/exports").resolve()):
        raise ValueError("Evidence ZIP must remain in ignored ops/exports")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Read and hash the exact bytes that will be archived, preventing a stale read.
    entries = {}
    for item in manifest["artifacts"]:
        data = safe_path(root, item["path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError(f"Evidence changed while bundling: {item['id']}")
        entries[item["path"]] = data
    entries[manifest_path.relative_to(root).as_posix()] = manifest_path.read_bytes()
    with zipfile.ZipFile(destination, "x", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(entries.items()):
            archive.writestr(name, data)
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(entries):
            raise ValueError("Evidence ZIP reopen failed")
        for name, data in entries.items():
            if archive.read(name) != data:
                raise ValueError("Evidence ZIP byte mismatch")
    return {"path": destination.relative_to(root).as_posix(), "sha256": digest(destination),
            "files": len(entries), "reopened": True, "raw_sessions_included": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--check-local-raw", action="store_true")
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--bundle", type=Path)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
        result = validate(manifest)
        if args.check_local_raw:
            result["raw_snapshots_verified"] = verify_raw_snapshots(manifest)
        if args.require_complete:
            result.update(status="BLOCKED", blockers=manifest["blockers"])
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 2
        if args.bundle:
            result["bundle"] = write_bundle(manifest, args.manifest.resolve(), args.bundle)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as error:
        print(json.dumps({"status": "FAIL", "reason": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
