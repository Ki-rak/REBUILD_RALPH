from __future__ import annotations

import json
import os
import secrets
import sys
import uuid
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote

import httpx

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.auth import AuthError, SupabaseAuth
from backend.storage import ConflictError, StorageError, SupabaseStore
from ops.runtime.supabase_probe import _load_env


class LiveVerifyFailure(RuntimeError):
    def __init__(self, stage: str) -> None:
        super().__init__(stage)
        self.stage = stage


def verify_live(
    url: str,
    publishable_key: str,
    secret_key: str,
    *,
    client: httpx.Client | None = None,
    timeout: float = 20.0,
) -> dict[str, Any]:
    result = {
        "status": "FAILED",
        "stage": "configuration",
        "auth_login_verified": False,
        "db_rls_verified": False,
        "storage_rls_verified": False,
        "logout_verified": False,
        "cleanup_complete": True,
    }
    if not url or not publishable_key or not secret_key:
        result["status"] = "NOT_CONFIGURED"
        return result

    http = client or httpx.Client()
    # Anonymous users cannot read this table by design. Use the service key only
    # to check schema metadata; all isolation checks below use real user JWTs.
    auth_metadata = _safe_request(
        http, "GET", f"{url.rstrip('/')}/auth/v1/settings",
        headers={"apikey": publishable_key}, timeout=timeout,
    )
    table_metadata = _safe_request(
        http, "GET", f"{url.rstrip('/')}/rest/v1/rb_entities",
        headers=_service_headers(secret_key),
        params={"select": "id", "limit": "0"}, timeout=timeout,
    )
    if (
        auth_metadata is None or auth_metadata.status_code != 200
        or table_metadata is None or table_metadata.status_code != 200
    ):
        result.update(status="PENDING_SCHEMA", stage="schema_preflight")
        if client is None:
            http.close()
        return result
    bucket_metadata = _safe_request(
        http, "GET", f"{url.rstrip('/')}/storage/v1/bucket/rebuild-agent",
        headers=_service_headers(secret_key), timeout=timeout,
    )
    try:
        bucket = bucket_metadata.json() if bucket_metadata is not None else {}
    except ValueError:
        bucket = {}
    if (
        bucket_metadata is None or bucket_metadata.status_code != 200
        or not isinstance(bucket, dict) or bucket.get("public") is not False
    ):
        result.update(status="PENDING_SCHEMA", stage="schema_preflight")
        if client is None:
            http.close()
        return result

    run_id = uuid.uuid4().hex
    password_a = secrets.token_urlsafe(24)
    password_b = secrets.token_urlsafe(24)
    email_a = f"rebuild-agent-probe+{run_id}-a@example.com"
    email_b = f"rebuild-agent-probe+{run_id}-b@example.com"
    users: list[str] = []
    entity_ids: dict[str, list[str]] = {}
    object_paths: list[str] = []
    stage = "create_test_users"

    try:
        user_a_id = _create_test_user(
            http, url, secret_key, email_a, password_a, run_id, timeout
        )
        users.append(user_a_id)
        entity_ids[user_a_id] = []

        user_b_id = _create_test_user(
            http, url, secret_key, email_b, password_b, run_id, timeout
        )
        users.append(user_b_id)
        entity_ids[user_b_id] = []

        stage = "login"
        auth = SupabaseAuth(url, publishable_key, client=http, timeout=timeout)
        session_a = auth.login(email_a, password_a)
        session_b = auth.login(email_b, password_b)
        if session_a.user.id != user_a_id or session_b.user.id != user_b_id:
            raise LiveVerifyFailure(stage)
        result["auth_login_verified"] = True

        stage = "database_rls"
        store_a = SupabaseStore(
            url, publishable_key, session_a.access_token, client=http, timeout=timeout
        )
        store_b = SupabaseStore(
            url, publishable_key, session_b.access_token, client=http, timeout=timeout
        )
        project_a = f"rb-probe-{run_id}-project-a"
        project_b = f"rb-probe-{run_id}-project-b"
        document_a = f"rb-probe-{run_id}-document-a"
        document_b = f"rb-probe-{run_id}-document-b"
        entity_ids[user_a_id].extend((project_a, document_a))
        entity_ids[user_b_id].extend((project_b, document_b))

        store_a.save("project", project_a, None, {"name": "RLS probe A"})
        store_a.save(
            "document",
            document_a,
            project_a,
            {"filename": "a.txt", "sha256": _probe_hash(run_id, "a")},
        )
        store_b.save("project", project_b, None, {"name": "RLS probe B"})
        store_b.save(
            "document",
            document_b,
            project_b,
            {"filename": "b.txt", "sha256": _probe_hash(run_id, "b")},
        )

        isolated_lists = (
            store_b.list("document", project_a) == []
            and store_a.list("document", project_b) == []
        )
        isolated_gets = store_b.get(document_a) is None and store_a.get(document_b) is None
        blocked_cross_update = False
        try:
            store_b.save(
                "document",
                document_a,
                project_a,
                {"filename": "blocked.txt", "sha256": _probe_hash(run_id, "a")},
                expected_version=1,
            )
        except ConflictError:
            blocked_cross_update = True
        if not isolated_lists or not isolated_gets or not blocked_cross_update:
            raise LiveVerifyFailure(stage)
        result["db_rls_verified"] = True

        stage = "storage_rls"
        relative_path = f"probe/{run_id}/same-name.bin"
        data_a = f"owner-a:{run_id}".encode()
        data_b = f"owner-b:{run_id}".encode()
        object_a = f"{user_a_id}/{relative_path}"
        object_b = f"{user_b_id}/{relative_path}"
        store_a.upload_bytes(relative_path, data_a, "application/octet-stream")
        object_paths.append(object_a)
        store_b.upload_bytes(relative_path, data_b, "application/octet-stream")
        object_paths.append(object_b)
        if store_a.download_bytes(relative_path) != data_a:
            raise LiveVerifyFailure(stage)
        if store_b.download_bytes(relative_path) != data_b:
            raise LiveVerifyFailure(stage)
        cross_response = _request(
            http,
            "GET",
            f"{url.rstrip('/')}/storage/v1/object/rebuild-agent/{_encode_path(object_a)}",
            headers=_user_headers(publishable_key, session_b.access_token),
            timeout=timeout,
        )
        if cross_response.status_code not in (400, 401, 403, 404):
            raise LiveVerifyFailure(stage)
        result["storage_rls_verified"] = True

        stage = "logout"
        auth.logout(session_a.access_token)
        auth.logout(session_b.access_token)
        result["logout_verified"] = True
        result.update(status="PASSED", stage="complete")
    except (AuthError, StorageError, LiveVerifyFailure, httpx.RequestError, ValueError):
        result.update(status="FAILED", stage=stage)
    finally:
        result["cleanup_complete"] = _cleanup(
            http=http,
            url=url,
            secret_key=secret_key,
            users=users,
            entity_ids=entity_ids,
            object_paths=object_paths,
            timeout=timeout,
        )
        if not result["cleanup_complete"]:
            result.update(status="FAILED", stage="cleanup")

    if client is None:
        http.close()
    return result


def _create_test_user(
    client: httpx.Client,
    url: str,
    secret_key: str,
    email: str,
    password: str,
    run_id: str,
    timeout: float,
) -> str:
    response = _request(
        client,
        "POST",
        f"{url.rstrip('/')}/auth/v1/admin/users",
        headers=_service_headers(secret_key),
        json={
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"created_by": "rebuild-agent-live-probe", "run_id": run_id},
        },
        timeout=timeout,
    )
    if response.status_code not in (200, 201):
        raise LiveVerifyFailure("create_test_users")
    data = _object(response, "create_test_users")
    user_id = data.get("id")
    if not isinstance(user_id, str) or not user_id:
        raise LiveVerifyFailure("create_test_users")
    return user_id


def _cleanup(
    *,
    http: httpx.Client,
    url: str,
    secret_key: str,
    users: list[str],
    entity_ids: dict[str, list[str]],
    object_paths: list[str],
    timeout: float,
) -> bool:
    complete = True
    headers = _service_headers(secret_key)

    if object_paths:
        response = _safe_request(
            http,
            "DELETE",
            f"{url.rstrip('/')}/storage/v1/object/rebuild-agent",
            headers=headers,
            json={"prefixes": list(object_paths)},
            timeout=timeout,
        )
        complete = complete and response is not None and response.status_code in (200, 204)

    for owner_id, ids in entity_ids.items():
        if not ids:
            continue
        encoded_ids = ",".join(quote(entity_id, safe="") for entity_id in ids)
        response = _safe_request(
            http,
            "DELETE",
            f"{url.rstrip('/')}/rest/v1/rb_entities",
            headers=headers,
            params={
                "owner_id": f"eq.{owner_id}",
                "id": f"in.({encoded_ids})",
            },
            timeout=timeout,
        )
        complete = complete and response is not None and response.status_code in (200, 204)

    for user_id in reversed(users):
        response = _safe_request(
            http,
            "DELETE",
            f"{url.rstrip('/')}/auth/v1/admin/users/{quote(user_id, safe='')}",
            headers=headers,
            timeout=timeout,
        )
        complete = complete and response is not None and response.status_code in (200, 204)
    return complete


def _probe_hash(run_id: str, owner: str) -> str:
    import hashlib

    return hashlib.sha256(f"{run_id}:{owner}".encode()).hexdigest()


def _service_headers(secret_key: str) -> dict[str, str]:
    headers = {"apikey": secret_key}
    if secret_key.count(".") == 2:
        headers["Authorization"] = f"Bearer {secret_key}"
    return headers


def _user_headers(publishable_key: str, access_token: str) -> dict[str, str]:
    return {
        "apikey": publishable_key,
        "Authorization": f"Bearer {access_token}",
    }


def _request(client: httpx.Client, method: str, url: str, **kwargs: Any) -> httpx.Response:
    return client.request(method, url, **kwargs)


def _safe_request(
    client: httpx.Client, method: str, url: str, **kwargs: Any
) -> httpx.Response | None:
    try:
        return _request(client, method, url, **kwargs)
    except httpx.RequestError:
        return None


def _object(response: httpx.Response, stage: str) -> Mapping[str, Any]:
    try:
        data = response.json()
    except ValueError as exc:
        raise LiveVerifyFailure(stage) from exc
    if not isinstance(data, Mapping):
        raise LiveVerifyFailure(stage)
    return data


def _encode_path(path: str) -> str:
    return "/".join(quote(part, safe="") for part in path.split("/"))


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    file_values = _load_env(project_root / ".env")
    url = os.environ.get("SUPABASE_URL") or file_values.get("SUPABASE_URL", "")
    publishable_key = (
        os.environ.get("SUPABASE_PUBLISHABLE_KEY")
        or file_values.get("SUPABASE_PUBLISHABLE_KEY", "")
    )
    secret_key = (
        os.environ.get("SUPABASE_SECRET_KEY")
        or file_values.get("SUPABASE_SECRET_KEY", "")
    )
    result = verify_live(url, publishable_key, secret_key)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PASSED" else 3


if __name__ == "__main__":
    raise SystemExit(main())