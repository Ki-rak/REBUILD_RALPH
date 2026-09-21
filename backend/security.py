"""Integrity seals for server-created evidence and approvals; never authentication tokens."""
import hashlib
import hmac
import json

DOCUMENT_FIELDS = ("id", "project_id", "filename", "sha256", "storage_path", "revision",
                   "approval_status", "extraction_status", "blocks", "markdown", "metadata", "parser_version", "intake", "intake_signature")
APPROVAL_FIELDS = ("id", "project_id", "output_kind", "type", "revision", "rows", "input_fingerprint",
                   "template_id", "template_sha256", "approved_at", "reviewer", "approval_id", "mode", "ai_used", "ai_insight", "approved_entity_version")

class IntegrityError(ValueError):
    pass

def _seal(domain, owner, payload, fields, key):
    if not isinstance(key, str) or len(key) < 32:
        raise IntegrityError("INTEGRITY_KEY_REQUIRED")
    value = {"domain": domain, "owner": owner, "payload": {field: payload.get(field) for field in fields}}
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hmac.new(key.encode(), encoded, hashlib.sha256).hexdigest()

def sign_document(document, owner, key):
    return _seal("rebuild-document-v1", owner, document, DOCUMENT_FIELDS, key)

def verify_document(document, owner, key):
    expected = sign_document(document, owner, key)
    signature = document.get("extraction_signature")
    if not isinstance(signature, str) or not hmac.compare_digest(expected, signature):
        raise IntegrityError("EVIDENCE_INTEGRITY_FAILED")

def sign_approval(draft, owner, key):
    return _seal("rebuild-approval-v1", owner, draft, APPROVAL_FIELDS, key)

def verify_approval(draft, snapshot, owner, key):
    if draft.get("version") != draft.get("approved_entity_version") or draft.get("version") is None:
        raise IntegrityError("APPROVAL_VERSION_MISMATCH")
    signature = draft.get("approval_signature")
    expected = sign_approval(draft, owner, key)
    if not isinstance(signature, str) or not hmac.compare_digest(expected, signature):
        raise IntegrityError("APPROVAL_INTEGRITY_FAILED")
    if not snapshot or snapshot.get("id") != draft.get("approval_id") or snapshot.get("draft_id") != draft["id"]:
        raise IntegrityError("APPROVAL_SNAPSHOT_MISSING")
    if snapshot.get("approval_signature") != signature or snapshot.get("signed_draft") != {field: draft.get(field) for field in APPROVAL_FIELDS}:
        raise IntegrityError("APPROVAL_SNAPSHOT_MISMATCH")

INTAKE_FIELDS = ("document_id", "project_id", "filename", "sha256", "storage_path", "source_path")

def seal_intake(document, owner, key):
    intake = {field: document.get(field) for field in INTAKE_FIELDS}
    intake["document_id"] = document["id"]
    intake["source_path"] = document.get("metadata", {}).get("source_path", document["filename"])
    document["intake"] = intake
    document["intake_signature"] = _seal("rebuild-intake-v1", owner, intake, INTAKE_FIELDS, key)

def restore_intake(document, owner, key):
    intake, signature = document.get("intake"), document.get("intake_signature")
    if not isinstance(intake, dict) or not isinstance(signature, str):
        raise IntegrityError("INTAKE_INTEGRITY_FAILED")
    expected = _seal("rebuild-intake-v1", owner, intake, INTAKE_FIELDS, key)
    if not hmac.compare_digest(expected, signature) or intake.get("document_id") != document.get("id") or intake.get("project_id") != document.get("project_id"):
        raise IntegrityError("INTAKE_INTEGRITY_FAILED")
    restored = {**document}
    for field in ("filename", "sha256", "storage_path"):
        restored[field] = intake[field]
    restored["metadata"] = {"source_path": intake["source_path"]}
    return restored
