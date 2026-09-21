"""Bounded process boundary to the official provider adapters; no secrets in diagnostics."""
import json
import hashlib
import hmac
import os
import subprocess
from .config import ROOT, load_environment

SAFE_ERRORS = {
    "CODEX_LOGIN_REQUIRED", "CODEX_TIMEOUT", "CODEX_TURN_FAILED", "OPENAI_AUTH_FAILED",
    "OPENAI_RATE_LIMITED", "OPENAI_REQUEST_TIMEOUT", "OPENAI_REQUEST_FAILED", "OPENAI_INVALID_REQUEST",
    "OPENAI_UNAVAILABLE", "OPENAI_API_KEY_REQUIRED", "OPENAI_MODEL_REQUIRED", "HOSTED_OAUTH_FORBIDDEN",
    "OPENAI_BASE_URL_FORBIDDEN", "INVALID_PROVIDER_OUTPUT", "UNKNOWN_SOURCE_ID", "TOOL_EVENT_REJECTED",
}

class AIError(Exception):
    def __init__(self, code):
        self.code = code if code in SAFE_ERRORS else "AI_UNAVAILABLE"
        super().__init__(self.code)

def provider_configuration():
    load_environment()
    env = os.environ.get("REBUILD_ENV", "local")
    return {"environment": env, "provider": "openai-responses" if env == "deployed" else "codex-oauth",
            "authentication_method": "API key" if env == "deployed" else "ChatGPT OAuth",
            "model": os.environ.get("OPENAI_MODEL" if env == "deployed" else "CODEX_MODEL") or "provider default",
            "key_configured": bool(os.environ.get("OPENAI_API_KEY")) if env == "deployed" else False,
            "authentication": "NOT_TESTED", "inference": "NOT_TESTED", "connected": False,
            "corporate_llm": "NOT_CONFIGURED", "sso": "NOT_CONFIGURED"}

def call_bridge(operation, request=None):
    payload = json.dumps({"operation": operation, "request": request}, ensure_ascii=False)
    try:
        result = subprocess.run(["node", str(ROOT / "server/ai/scripts/bridge.js")], input=payload,
            text=True, encoding="utf-8", capture_output=True, timeout=65, cwd=ROOT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        answer = json.loads(result.stdout)
    except (subprocess.TimeoutExpired, OSError, ValueError):
        raise AIError("AI_UNAVAILABLE") from None
    if result.returncode or not answer.get("ok"):
        raise AIError(answer.get("error"))
    return answer["result"]


def configuration_revision(signing_key):
    """Opaque server-side change detector; never returns actual credential values."""
    load_environment()
    env = os.environ.get("REBUILD_ENV", "local")
    fields = ("REBUILD_ENV", "OPENAI_MODEL", "OPENAI_BASE_URL", "OPENAI_API_KEY") if env == "deployed" else ("REBUILD_ENV", "CODEX_MODEL")
    content = {key: os.environ.get(key, "") for key in fields}
    if env != "deployed":
        auth_path = ROOT / "ops/private/codex-ai/auth.json"
        try:
            stat = auth_path.stat()
            content["oauth_file_revision"] = [stat.st_mtime_ns, stat.st_size]
        except OSError:
            content["oauth_file_revision"] = None
    return hmac.new(signing_key.encode(), json.dumps(content, sort_keys=True).encode(), hashlib.sha256).hexdigest()
