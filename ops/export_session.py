"""Snapshot this task's actual Codex rollout segments without changing originals.

Operational evidence utility, not a product runtime or an autonomous runner.
Only files matching the selected root thread and date are read. No auth files are read.
"""
import argparse
import collections
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
KST = dt.timezone(dt.timedelta(hours=9))
UUID_PATTERN = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def discover_segments(codex_dir, session_date, session_id):
    if not session_id or not re.fullmatch(UUID_PATTERN, session_id):
        raise ValueError("A valid explicit root thread ID is required")
    if not re.fullmatch(r"\d{4}/\d{2}/\d{2}", session_date):
        raise ValueError("Session date must use YYYY/MM/DD")
    dt.datetime.strptime(session_date, "%Y/%m/%d")
    name_pattern = re.compile(
        rf"rollout-\d{{4}}-\d{{2}}-\d{{2}}T\d{{2}}-\d{{2}}-\d{{2}}-{session_id}"
        rf"(?:_({UUID_PATTERN}))?\.jsonl"
    )
    folder = Path(codex_dir) / "sessions" / session_date
    candidates = sorted(
        path for path in folder.glob(f"*{session_id}*.jsonl")
        if path.is_file() and not path.is_symlink() and name_pattern.fullmatch(path.name)
    )
    if not candidates:
        raise ValueError("No rollout segments found for the specified root thread and date")
    return candidates


def read_segment(source, session_id, workspace):
    data = source.read_bytes()
    # Do not include an incomplete final record while Codex is still writing.
    boundary = data.rfind(b"\n") + 1
    complete = data[:boundary]
    rows = [json.loads(line) for line in complete.splitlines() if line.strip()]
    metas = [row.get("payload") for row in rows if row.get("type") == "session_meta"]
    if len(metas) != 1 or not isinstance(metas[0], dict):
        raise ValueError("Expected exactly one session metadata record per segment")
    meta = metas[0]
    suffix = source.stem.split(session_id, 1)[1]
    filename_segment_id = suffix[1:] if suffix.startswith("_") else None
    allowed_ids = {session_id}
    if filename_segment_id:
        allowed_ids.add(filename_segment_id)
    if meta.get("id") not in allowed_ids:
        raise ValueError("Session metadata mismatch")
    if not meta.get("cwd") or Path(meta["cwd"]).resolve() != Path(workspace).resolve():
        raise ValueError("Session belongs to a different workspace")
    return data, complete, rows, meta, filename_segment_id


def sanitize_credentials(complete, environ):
    # Known token patterns + actual key-like environment values. Never print hits.
    patterns = [
        rb"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{24,}",
        rb"\bsb_secret_[A-Za-z0-9_-]{16,}",
        rb"\bgh[pousr]_[A-Za-z0-9]{30,}",
        rb"\bgithub_pat_[A-Za-z0-9_]{30,}",
        rb"\bAIza[A-Za-z0-9_-]{30,}",
        rb"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}",
    ]
    sanitized = complete
    replacements = 0
    for pattern in patterns:
        sanitized, count = re.subn(pattern, b"[REDACTED_CREDENTIAL]", sanitized)
        replacements += count
    for key, value in environ.items():
        if re.search(r"(?:API_KEY|TOKEN|SECRET|PASSWORD)$", key, re.I) and len(value) >= 12:
            raw = value.encode()
            count = sanitized.count(raw)
            if count:
                sanitized = sanitized.replace(raw, b"[REDACTED_ENV_CREDENTIAL]")
                replacements += count
    return sanitized, replacements


def goal_input_evidence(rows, goal_reference=None):
    """Role-aware textual evidence only; never infer native goal execution/completion."""
    evidence = {
        "reference_check_requested": bool(goal_reference),
        "user_goal_command_seen": False,
        "user_goal_reference_seen": False,
        "assistant_goal_command_seen": False,
        "assistant_goal_reference_seen": False,
        "user_input_evidence_seen": False,
    }
    reference = goal_reference.replace("\\", "/") if goal_reference else None
    for row in rows:
        payload = row.get("payload", {})
        if not isinstance(payload, dict):
            continue
        role = None
        texts = []
        if row.get("type") == "response_item" and payload.get("type") == "message":
            role = payload.get("role")
            content = payload.get("content", [])
            if isinstance(content, str):
                texts.append(content)
            elif isinstance(content, list):
                texts.extend(item["text"] for item in content
                             if isinstance(item, dict) and isinstance(item.get("text"), str))
        elif row.get("type") == "event_msg":
            role = {"user_message": "user", "agent_message": "assistant"}.get(payload.get("type"))
            if isinstance(payload.get("message"), str):
                texts.append(payload["message"])
        if role not in ("user", "assistant"):
            continue
        text = "\n".join(texts)
        if re.match(r"^\s*/goal(?:\s|$)", text):
            evidence[f"{role}_goal_command_seen"] = True
        if reference and reference in text.replace("\\", "/"):
            evidence[f"{role}_goal_reference_seen"] = True
    evidence["user_input_evidence_seen"] = (
        evidence["user_goal_command_seen"] or evidence["user_goal_reference_seen"]
    )
    return evidence


def export_sessions(codex_dir, session_id, session_date, *, workspace=ROOT,
                    session_order=1, phase="preparation", all_segments=False,
                    goal_reference=None, environ=None):
    candidates = discover_segments(codex_dir, session_date, session_id)
    selected = list(enumerate(candidates, 1))
    if not all_segments:
        selected = selected[-1:]
    # Validate every selected source before creating any export.
    snapshots = [(sequence, source, read_segment(source, session_id, workspace))
                 for sequence, source in selected]
    stamp = dt.datetime.now(KST)
    results = []
    for sequence, source, snapshot in snapshots:
        data, complete, rows, meta, filename_segment_id = snapshot
        sanitized, replacements = sanitize_credentials(
            complete, os.environ if environ is None else environ
        )
        parsed_export = [json.loads(line) for line in sanitized.splitlines() if line.strip()]
        if len(parsed_export) != len(rows):
            raise ValueError("Export event count differs from source")
        target = (Path(workspace) / "ops" / "sessions" / session_id
                  / f"{stamp.strftime('%Y%m%dT%H%M%S%f%z')}-segment-{sequence:03d}")
        target.mkdir(parents=True, exist_ok=False)
        name = "rollout.raw.jsonl" if replacements == 0 else "rollout.redacted.jsonl"
        exported = target / name
        exported.write_bytes(sanitized)
        result = {
            "product": "RE:Build Agent", "session_id": session_id,
            "root_thread_id": session_id, "native_metadata_session_id": meta["id"],
            "filename_segment_id": filename_segment_id,
            "segment_sequence": sequence, "segment_sequence_scope": session_date,
            "discovered_segment_count": len(candidates),
            "segment_is_latest_discovered": sequence == len(candidates),
            "segment_selection": "all" if all_segments else "latest",
            "session_order": session_order, "phase": phase,
            "exported_at_kst": stamp.isoformat(), "source": str(source),
            "source_preserved": True, "source_snapshot_bytes": len(data),
            "complete_record_bytes": len(complete), "deferred_tail_bytes": len(data) - len(complete),
            "source_snapshot_sha256": sha(data), "complete_record_sha256": sha(complete),
            "export_path": str(exported), "export_sha256": sha(exported.read_bytes()),
            "exact_complete_record_copy": replacements == 0 and exported.read_bytes() == complete,
            "redaction_count": replacements, "event_count": len(rows),
            "event_types": dict(collections.Counter(row.get("type") for row in rows)),
            "first_record_timestamp": rows[0].get("timestamp"),
            "last_record_timestamp": rows[-1].get("timestamp"),
            "originator": meta.get("originator"), "cli_version": meta.get("cli_version"),
            "jsonl_parse": "PASS", "session_still_active": True,
            "scope": "One native segment snapshot through last_record_timestamp; not a final-session export.",
            "segments_combined": False,
            "goal_input_evidence": goal_input_evidence(rows, goal_reference),
            "final_goal_result_assessed": False,
            "secret_scan_limit": "Pattern checks cannot guarantee absence of all credentials. Review before submission.",
            "official_submission_format_confirmed": True,
            "official_format_scope": "Main JSONL 1 required, additional JSONL ZIP 1 optional; schema and upload limits unverified.",
            "main_session_eligibility": "NOT_ASSESSED: user input evidence does not prove native goal execution or final result",
        }
        (target / "manifest.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        index = Path(workspace) / "ops" / "sessions" / "index.jsonl"
        with index.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(result, ensure_ascii=False) + "\n")
        results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", default=os.environ.get("CODEX_THREAD_ID"),
                        help="Root thread ID, including for rotated segments")
    parser.add_argument("--session-order", type=int, default=1)
    parser.add_argument("--phase", choices=["preparation", "development", "submission"], default="preparation")
    parser.add_argument("--session-date", default="2026/09/21")
    parser.add_argument("--all-segments", action="store_true",
                        help="Export each matching segment separately; default selects the latest")
    parser.add_argument("--goal-reference",
                        help="Exact attachment path/reference to check in user vs assistant messages; no file is opened")
    args = parser.parse_args()
    codex_dir = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    try:
        results = export_sessions(
            codex_dir, args.session_id, args.session_date,
            session_order=args.session_order, phase=args.phase,
            all_segments=args.all_segments, goal_reference=args.goal_reference,
        )
    except (ValueError, OSError) as error:
        raise SystemExit(str(error)) from None
    print(json.dumps({"root_thread_id": args.session_id, "segment_exports": results},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
