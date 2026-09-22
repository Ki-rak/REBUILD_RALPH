"""Server-only configuration; process secrets override local values."""
from dataclasses import dataclass, field
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = ROOT / "data/REBUILD_INPUT_v1/REBUILD_INPUT_v1"
TEMPLATE_ROOT = INPUT_ROOT / "03_OUTPUT_TEMPLATES"

def load_environment(path=ROOT / ".env"):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if value[:1] in ("'", '"') and value[-1:] == value[:1]:
            value = value[1:-1]
        if key.replace("_", "").isalnum():
            os.environ.setdefault(key, value)

@dataclass(frozen=True)
class Settings:
    supabase_url: str
    publishable_key: str
    environment: str
    approval_signing_key: str = field(default="", repr=False)
    upload_limit: int = 20 * 1024 * 1024

    @classmethod
    def from_environment(cls):
        load_environment()
        return cls(os.environ.get("SUPABASE_URL", "").rstrip("/"),
                   os.environ.get("SUPABASE_PUBLISHABLE_KEY", ""),
                   os.environ.get("REBUILD_ENV", "local"), os.environ.get("REBUILD_APPROVAL_SIGNING_KEY", ""),
                   3_800_000 if os.environ.get("REBUILD_ENV") == "deployed" else 20 * 1024 * 1024)

    def validate(self):
        if self.supabase_url != "https://wsziosnttnxefgfbgpeq.supabase.co":
            raise ValueError("SUPABASE_PROJECT_NOT_CONFIGURED")
        if len(self.approval_signing_key) < 32:
            raise ValueError("INTEGRITY_KEY_REQUIRED")
        if not self.publishable_key:
            raise ValueError("SUPABASE_KEY_NOT_CONFIGURED")
        if self.environment not in {"local", "demo", "deployed"}:
            raise ValueError("INVALID_ENVIRONMENT")
