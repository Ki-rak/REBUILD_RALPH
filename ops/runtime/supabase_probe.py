from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx


def probe(
    url: str,
    publishable_key: str,
    *,
    client: httpx.Client | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Probe public Supabase surfaces without exposing provider response bodies."""

    if not url or not publishable_key:
        return {
            "configured": False,
            "auth": {"status_code": None, "reachable": False},
            "rest": {
                "status_code": None,
                "reachable": False,
                "table_ready": False,
                "visible_row_count": None,
            },
            "storage": {
                "status_code": None,
                "reachable": False,
                "bucket_ready": False,
                "visible_object_count": None,
            },
        }

    http = client or httpx.Client()
    headers = {"apikey": publishable_key}
    auth_response = _safe_request(
        http,
        "GET",
        f"{url.rstrip('/')}/auth/v1/settings",
        headers=headers,
        timeout=timeout,
    )
    rest_response = _safe_request(
        http,
        "GET",
        f"{url.rstrip('/')}/rest/v1/rb_entities",
        headers=headers,
        params={"select": "id", "limit": "1"},
        timeout=timeout,
    )
    storage_response = _safe_request(
        http,
        "POST",
        f"{url.rstrip('/')}/storage/v1/object/list/rebuild-agent",
        headers=headers,
        json={"prefix": "", "limit": 1, "offset": 0},
        timeout=timeout,
    )

    rest_count = _list_count(rest_response)
    storage_count = _list_count(storage_response)
    return {
        "configured": True,
        "auth": _endpoint_status(auth_response),
        "rest": {
            **_endpoint_status(rest_response),
            "table_ready": _status_code(rest_response) == 200,
            "visible_row_count": rest_count,
        },
        "storage": {
            **_endpoint_status(storage_response),
            "bucket_ready": _status_code(storage_response) == 200,
            "visible_object_count": storage_count,
        },
    }


def _safe_request(client: httpx.Client, method: str, url: str, **kwargs: Any) -> httpx.Response | None:
    try:
        return client.request(method, url, **kwargs)
    except httpx.RequestError:
        return None


def _status_code(response: httpx.Response | None) -> int | None:
    return response.status_code if response is not None else None


def _endpoint_status(response: httpx.Response | None) -> dict[str, Any]:
    return {
        "status_code": _status_code(response),
        "reachable": response is not None,
    }


def _list_count(response: httpx.Response | None) -> int | None:
    if response is None or response.status_code != 200:
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    return len(data) if isinstance(data, list) else None


def _load_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        values[name.strip()] = value
    return values


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    file_values = _load_env(project_root / ".env")
    url = os.environ.get("SUPABASE_URL") or file_values.get("SUPABASE_URL", "")
    publishable_key = (
        os.environ.get("SUPABASE_PUBLISHABLE_KEY")
        or file_values.get("SUPABASE_PUBLISHABLE_KEY", "")
    )
    result = probe(url, publishable_key)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["configured"] else 2


if __name__ == "__main__":
    raise SystemExit(main())