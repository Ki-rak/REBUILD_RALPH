"""Synthetic rollout regression tests; never read real session messages."""
import importlib.util
import json
from pathlib import Path

import pytest


SPEC = importlib.util.spec_from_file_location(
    "session_export", Path(__file__).resolve().parents[1] / "ops" / "export_session.py"
)
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)
ROOT_ID = "11111111-1111-1111-1111-111111111111"
SEGMENT_ID = "22222222-2222-2222-2222-222222222222"
GOAL_REFERENCE = "attachment-id/goal-objective.md"


def rollout(tmp_path, *, rotated=False, native_id=None, cwd=None, events=None, tail=b""):
    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)
    base = tmp_path / "codex" / "sessions" / "2026" / "09" / "21"
    base.mkdir(parents=True, exist_ok=True)
    time = "18-48-20" if rotated else "15-07-58"
    suffix = f"_{SEGMENT_ID}" if rotated else ""
    source = base / f"rollout-2026-09-21T{time}-{ROOT_ID}{suffix}.jsonl"
    rows = [{"timestamp": f"2026-09-21T{time.replace('-', ':')}Z", "type": "session_meta",
             "payload": {"id": native_id or ROOT_ID, "cwd": str(cwd or workspace)}}]
    rows.extend(events or [])
    source.write_bytes(b"".join((json.dumps(row) + "\n").encode() for row in rows) + tail)
    return workspace, source


def export(tmp_path, workspace, **kwargs):
    return exporter.export_sessions(
        tmp_path / "codex", ROOT_ID, "2026/09/21", workspace=workspace,
        environ={}, goal_reference=GOAL_REFERENCE, **kwargs
    )


def test_default_selects_latest_rotated_segment_and_keeps_native_metadata(tmp_path):
    workspace, original = rollout(tmp_path)
    _, rotated = rollout(tmp_path, rotated=True)
    result = export(tmp_path, workspace)
    assert len(result) == 1
    manifest = result[0]
    assert Path(manifest["source"]) == rotated
    assert manifest["root_thread_id"] == ROOT_ID
    assert manifest["native_metadata_session_id"] == ROOT_ID
    assert manifest["filename_segment_id"] == SEGMENT_ID
    assert manifest["segment_sequence"] == 2
    assert manifest["discovered_segment_count"] == 2
    assert Path(manifest["export_path"]).read_bytes() == rotated.read_bytes()
    assert original.exists()
    assert manifest["session_still_active"] is True
    assert manifest["final_goal_result_assessed"] is False


def test_all_segments_preserves_separate_records_sources_and_previous_index(tmp_path):
    workspace, original = rollout(tmp_path)
    _, rotated = rollout(tmp_path, rotated=True, native_id=SEGMENT_ID)
    before = {source: source.read_bytes() for source in (original, rotated)}
    first = export(tmp_path, workspace)
    index = workspace / "ops" / "sessions" / "index.jsonl"
    previous_index = index.read_bytes()
    second = export(tmp_path, workspace, all_segments=True)
    assert [record["segment_sequence"] for record in second] == [1, 2]
    assert len({record["export_path"] for record in first + second}) == 3
    assert index.read_bytes().startswith(previous_index)
    for record in second:
        source = Path(record["source"])
        assert source.read_bytes() == before[source]
        assert Path(record["export_path"]).read_bytes() == before[source]
        assert record["export_sha256"] == exporter.sha(before[source])
        saved = json.loads(Path(record["export_path"]).with_name("manifest.json").read_text())
        assert saved == record


def test_partial_tail_is_deferred_without_rewriting_source(tmp_path):
    workspace, source = rollout(tmp_path, tail=b'{"unfinished":')
    before = source.read_bytes()
    record = export(tmp_path, workspace)[0]
    assert record["deferred_tail_bytes"] == len(b'{"unfinished":')
    assert record["event_count"] == 1
    assert source.read_bytes() == before
    assert record["source_snapshot_sha256"] == exporter.sha(before)
    assert Path(record["export_path"]).read_bytes() == before[:record["complete_record_bytes"]]


def test_redacts_supabase_openai_and_environment_credentials_in_copies_only(tmp_path):
    secrets = ["sb_secret_" + "S" * 32, "sk-proj-" + "O" * 32, "custom-env-value-123"]
    events = [{"type": "event_msg", "payload": {"type": "agent_message", "message": " ".join(secrets)}}]
    workspace, source = rollout(tmp_path, events=events)
    before = source.read_bytes()
    record = exporter.export_sessions(
        tmp_path / "codex", ROOT_ID, "2026/09/21", workspace=workspace,
        environ={"EXAMPLE_API_KEY": secrets[-1]}
    )[0]
    exported = Path(record["export_path"]).read_bytes()
    assert record["redaction_count"] == 3
    assert record["exact_complete_record_copy"] is False
    assert all(secret.encode() not in exported for secret in secrets)
    assert source.read_bytes() == before
    assert len([json.loads(line) for line in exported.splitlines()]) == 2


@pytest.mark.parametrize("event", [
    {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [
        {"type": "input_text", "text": r"Use attachment-id\goal-objective.md"}]}},
    {"type": "event_msg", "payload": {"type": "user_message", "message": "Use " + GOAL_REFERENCE}},
])
def test_goal_reference_evidence_requires_user_message_role(tmp_path, event):
    workspace, _ = rollout(tmp_path, events=[event])
    evidence = export(tmp_path, workspace)[0]["goal_input_evidence"]
    assert evidence["user_goal_reference_seen"] is True
    assert evidence["user_input_evidence_seen"] is True
    assert evidence["user_goal_command_seen"] is False
    assert all(isinstance(value, bool) for value in evidence.values())


def test_assistant_quotes_and_tool_outputs_are_not_user_goal_evidence(tmp_path):
    events = [
        {"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": [
            {"type": "output_text", "text": "/goal use " + GOAL_REFERENCE}]}},
        {"type": "response_item", "payload": {"type": "function_call_output", "output": "/goal " + GOAL_REFERENCE}},
    ]
    workspace, _ = rollout(tmp_path, events=events)
    evidence = export(tmp_path, workspace)[0]["goal_input_evidence"]
    assert evidence["user_input_evidence_seen"] is False
    assert evidence["assistant_goal_reference_seen"] is True
    assert evidence["assistant_goal_command_seen"] is True


@pytest.mark.parametrize("mismatch", ["metadata", "workspace"])
def test_rejects_metadata_or_workspace_mismatch_before_writing(tmp_path, mismatch):
    workspace, _ = rollout(tmp_path, native_id="33333333-3333-3333-3333-333333333333" if mismatch == "metadata" else None,
                           cwd=tmp_path / "other" if mismatch == "workspace" else None)
    with pytest.raises(ValueError):
        export(tmp_path, workspace)
    assert not (workspace / "ops" / "sessions").exists()


def test_discovery_ignores_near_matches_and_rejects_path_traversal(tmp_path):
    workspace, source = rollout(tmp_path)
    source.with_name(source.stem + "_invalid.jsonl").write_text("not json")
    assert len(export(tmp_path, workspace)) == 1
    with pytest.raises(ValueError):
        exporter.discover_segments(tmp_path / "codex", "../../other", ROOT_ID)
