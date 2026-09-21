from __future__ import annotations

import json

import httpx
import pytest

from backend.auth import AuthError, AuthUnavailableError, SupabaseAuth
from backend.storage import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    StorageUnavailableError,
    StorageError,
    SupabaseStore,
)


BASE_URL = "https://project.supabase.co"
PUBLISHABLE_KEY = "publishable-test-key"
ACCESS_TOKEN = "user-access-token"
USER_ID = "11111111-1111-4111-8111-111111111111"


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _json_response(status: int, data, request: httpx.Request) -> httpx.Response:
    return httpx.Response(status, json=data, request=request)


def test_list_returns_application_entities_and_scopes_project() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/rb_entities"
        assert request.url.params["kind"] == "eq.document"
        assert request.url.params["project_id"] == "eq.project-1"
        assert request.url.params["order"] == "updated_at.desc,id.asc"
        assert request.headers["authorization"] == f"Bearer {ACCESS_TOKEN}"
        assert request.headers["range"] == "0-999"
        return httpx.Response(
            200,
            headers={"Content-Range": "0-0/1"},
            json=[{
                "id": "doc-1", "kind": "document", "project_id": "project-1",
                "payload": {"filename": "brief.pdf", "sha256": "abc"}, "version": 3,
                "created_at": "2026-09-21T00:00:00Z", "updated_at": "2026-09-21T01:00:00Z",
            }],
            request=request,
        )

    store = SupabaseStore(BASE_URL, PUBLISHABLE_KEY, ACCESS_TOKEN, client=_client(handler))

    assert store.list("document", "project-1") == [{
        "id": "doc-1", "kind": "document", "project_id": "project-1",
        "payload": {"filename": "brief.pdf", "sha256": "abc"}, "version": 3,
        "created_at": "2026-09-21T00:00:00Z", "updated_at": "2026-09-21T01:00:00Z",
    }]


def test_list_collects_server_capped_pages_using_actual_response_ranges() -> None:
    requested_ranges: list[str] = []
    timestamp = "2026-09-21T01:00:00Z"
    pages = {
        "0-999": (
            "0-1/*",
            [
                {"id": "doc-a", "kind": "document", "project_id": "project-1", "payload": {}, "version": 1, "created_at": timestamp, "updated_at": timestamp},
                {"id": "doc-b", "kind": "document", "project_id": "project-1", "payload": {}, "version": 1, "created_at": timestamp, "updated_at": timestamp},
            ],
        ),
        "2-1001": (
            "2-3/*",
            [
                {"id": "doc-c", "kind": "document", "project_id": "project-1", "payload": {}, "version": 1, "created_at": timestamp, "updated_at": timestamp},
                {"id": "doc-d", "kind": "document", "project_id": "project-1", "payload": {}, "version": 1, "created_at": timestamp, "updated_at": timestamp},
            ],
        ),
        "4-1003": ("*/ *".replace(" ", ""), []),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["order"] == "updated_at.desc,id.asc"
        requested_range = request.headers["range"]
        requested_ranges.append(requested_range)
        content_range, rows = pages[requested_range]
        return httpx.Response(
            200,
            headers={"Content-Range": content_range},
            json=rows,
            request=request,
        )

    store = SupabaseStore(BASE_URL, PUBLISHABLE_KEY, ACCESS_TOKEN, client=_client(handler))

    assert [row["id"] for row in store.list("document", "project-1")] == [
        "doc-a", "doc-b", "doc-c", "doc-d",
    ]
    assert requested_ranges == ["0-999", "2-1001", "4-1003"]


def test_list_rejects_nonadvancing_response_range() -> None:
    calls = 0
    row = {
        "id": "doc-a", "kind": "document", "project_id": "project-1",
        "payload": {}, "version": 1,
        "created_at": "2026-09-21T00:00:00Z",
        "updated_at": "2026-09-21T00:00:00Z",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            headers={"Content-Range": "0-0/*"},
            json=[row],
            request=request,
        )

    store = SupabaseStore(BASE_URL, PUBLISHABLE_KEY, ACCESS_TOKEN, client=_client(handler))

    with pytest.raises(StorageUnavailableError, match="pagination"):
        store.list("document")
    assert calls == 2


def test_approve_posts_one_atomic_rpc_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/rest/v1/rpc/rb_approve_draft"
        assert json.loads(request.content) == {
            "draft_id": "draft-1",
            "expected_version": 2,
            "draft_payload": {"status": "approved"},
            "approval_id": "approval-1",
            "approval_payload": {"approval_fingerprint": "fingerprint"},
        }
        return _json_response(200, [{
            "id": "draft-1", "kind": "draft", "project_id": "project-1",
            "payload": {"status": "approved"}, "version": 3,
            "created_at": "2026-09-21T00:00:00Z",
            "updated_at": "2026-09-21T01:00:00Z",
        }], request)

    store = SupabaseStore(BASE_URL, PUBLISHABLE_KEY, ACCESS_TOKEN, client=_client(handler))

    result = store.approve(
        "draft-1",
        2,
        {"status": "approved"},
        "approval-1",
        {"approval_fingerprint": "fingerprint"},
    )
    assert result["id"] == "draft-1"
    assert result["version"] == 3


def test_approve_maps_postgres_serialization_failure_to_conflict() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            400,
            {"code": "40001", "message": "provider detail must stay private"},
            request,
        )

    store = SupabaseStore(BASE_URL, PUBLISHABLE_KEY, ACCESS_TOKEN, client=_client(handler))

    with pytest.raises(ConflictError, match="approval version conflict") as exc:
        store.approve("draft-1", 2, {}, "approval-1", {})
    assert exc.value.code == "VERSION_CONFLICT"

def test_save_inserts_then_updates_with_expected_version() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = json.loads(request.content)
        if request.method == "POST":
            assert body == {
                "id": "doc-1", "kind": "document", "project_id": "project-1",
                "payload": {"sha256": "abc", "approval_status": "draft"},
            }
            return _json_response(201, [{**body, "version": 1}], request)
        assert request.method == "PATCH"
        assert request.url.params["id"] == "eq.doc-1"
        assert request.url.params["version"] == "eq.1"
        assert body == {
            "kind": "document", "project_id": "project-1",
            "payload": {"sha256": "abc", "approval_status": "approved"}, "version": 2,
        }
        return _json_response(200, [{"id": "doc-1", **body}], request)

    store = SupabaseStore(BASE_URL, PUBLISHABLE_KEY, ACCESS_TOKEN, client=_client(handler))
    created = store.save("document", "doc-1", "project-1", {"sha256": "abc", "approval_status": "draft"})
    updated = store.save(
        "document", "doc-1", "project-1",
        {"sha256": "abc", "approval_status": "approved"}, expected_version=1,
    )

    assert created["version"] == 1
    assert updated["payload"]["approval_status"] == "approved"
    assert updated["version"] == 2
    assert [request.method for request in requests] == ["POST", "PATCH"]


def test_save_rejects_stale_version_without_overwriting() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(200, [], request)

    store = SupabaseStore(BASE_URL, PUBLISHABLE_KEY, ACCESS_TOKEN, client=_client(handler))
    with pytest.raises(ConflictError, match="stale entity version") as exc:
        store.save("draft", "draft-1", "project-1", {"status": "approved"}, expected_version=4)
    assert exc.value.code == "VERSION_CONFLICT"


@pytest.mark.parametrize("version", [True, 0, -1, 1.5, "1"])
def test_save_rejects_invalid_expected_version_before_network(version) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("invalid versions must not reach Supabase")

    store = SupabaseStore(BASE_URL, PUBLISHABLE_KEY, ACCESS_TOKEN, client=_client(handler))
    with pytest.raises(ValueError, match="expected version"):
        store.save("draft", "draft-1", "project-1", {}, expected_version=version)

def test_get_missing_and_permission_errors_are_typed_and_sanitized() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _json_response(200, [], request)
        return _json_response(403, {"message": f"rejected {ACCESS_TOKEN}", "hint": PUBLISHABLE_KEY}, request)

    store = SupabaseStore(BASE_URL, PUBLISHABLE_KEY, ACCESS_TOKEN, client=_client(handler))
    assert store.get("missing") is None
    with pytest.raises(PermissionDeniedError) as exc:
        store.list("document")
    assert ACCESS_TOKEN not in str(exc.value)
    assert PUBLISHABLE_KEY not in str(exc.value)


def test_storage_uses_verified_user_prefix_and_downloads_bytes() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/auth/v1/user":
            return _json_response(200, {"id": USER_ID, "email": "owner@example.com"}, request)
        assert request.url.path == f"/storage/v1/object/rebuild-agent/{USER_ID}/project-1/source.pdf"
        if request.method == "POST":
            assert request.content == b"pdf-bytes"
            assert request.headers["content-type"] == "application/pdf"
            return _json_response(200, {"Key": f"{USER_ID}/project-1/source.pdf"}, request)
        return httpx.Response(200, content=b"pdf-bytes", request=request)

    store = SupabaseStore(BASE_URL, PUBLISHABLE_KEY, ACCESS_TOKEN, client=_client(handler))
    uploaded = store.upload_bytes("project-1/source.pdf", b"pdf-bytes", "application/pdf")
    downloaded = store.download_bytes("project-1/source.pdf")

    assert uploaded == {"path": "project-1/source.pdf", "size": 9, "content_type": "application/pdf"}
    assert downloaded == b"pdf-bytes"
    assert [request.url.path for request in requests].count("/auth/v1/user") == 1


@pytest.mark.parametrize("path", ["", "/absolute", "../secret", "project/../../secret"])
def test_storage_rejects_unsafe_paths_before_network(path: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("unsafe paths must not reach Supabase")

    store = SupabaseStore(BASE_URL, PUBLISHABLE_KEY, ACCESS_TOKEN, client=_client(handler))
    with pytest.raises(ValueError, match="storage path"):
        store.upload_bytes(path, b"x", "application/octet-stream")


def test_auth_login_get_user_and_logout_use_publishable_client() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/auth/v1/token":
            assert request.url.params["grant_type"] == "password"
            assert json.loads(request.content) == {"email": "owner@example.com", "password": "password"}
            return _json_response(200, {
                "access_token": ACCESS_TOKEN, "refresh_token": "refresh-token",
                "expires_in": 3600, "token_type": "bearer",
                "user": {"id": USER_ID, "email": "owner@example.com"},
            }, request)
        assert request.headers["authorization"] == f"Bearer {ACCESS_TOKEN}"
        if request.url.path == "/auth/v1/user":
            return _json_response(200, {"id": USER_ID, "email": "owner@example.com"}, request)
        assert request.url.path == "/auth/v1/logout"
        return httpx.Response(204, request=request)

    auth = SupabaseAuth(BASE_URL, PUBLISHABLE_KEY, client=_client(handler))
    session = auth.login("owner@example.com", "password")
    user = auth.get_user(session.access_token)
    auth.logout(session.access_token)

    assert session.access_token == ACCESS_TOKEN
    assert session.refresh_token == "refresh-token"
    assert user.id == USER_ID
    assert user.email == "owner@example.com"


def test_auth_refresh_returns_new_session_without_exposing_tokens() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/auth/v1/token"
        assert request.url.params["grant_type"] == "refresh_token"
        assert json.loads(request.content) == {"refresh_token": "old-refresh-token"}
        return _json_response(200, {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
            "token_type": "bearer",
            "user": {"id": USER_ID, "email": "owner@example.com"},
        }, request)

    auth = SupabaseAuth(BASE_URL, PUBLISHABLE_KEY, client=_client(handler))
    session = auth.refresh("old-refresh-token")

    assert session.access_token == "new-access-token"
    assert session.refresh_token == "new-refresh-token"
    assert session.user.id == USER_ID


def test_auth_and_store_close_their_http_clients() -> None:
    auth_client = _client(lambda request: _json_response(200, {}, request))
    store_client = _client(lambda request: _json_response(200, [], request))
    auth = SupabaseAuth(BASE_URL, PUBLISHABLE_KEY, client=auth_client)
    store = SupabaseStore(BASE_URL, PUBLISHABLE_KEY, ACCESS_TOKEN, client=store_client)

    auth.close()
    store.close()

    assert auth_client.is_closed
    assert store_client.is_closed

def test_auth_failure_does_not_expose_provider_body_or_credentials() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(400, {"message": "password bad-password rejected", "token": ACCESS_TOKEN}, request)

    auth = SupabaseAuth(BASE_URL, PUBLISHABLE_KEY, client=_client(handler))
    with pytest.raises(AuthError) as exc:
        auth.login("owner@example.com", "bad-password")
    assert str(exc.value) == "authentication failed"
    assert "bad-password" not in str(exc.value)
    assert ACCESS_TOKEN not in str(exc.value)


def test_auth_rejects_malformed_session_without_raw_value() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(200, {
            "access_token": ACCESS_TOKEN,
            "refresh_token": "refresh-token",
            "expires_in": "provider-secret-invalid",
            "user": {"id": USER_ID},
        }, request)

    auth = SupabaseAuth(BASE_URL, PUBLISHABLE_KEY, client=_client(handler))
    with pytest.raises(AuthUnavailableError) as exc:
        auth.login("owner@example.com", "password")
    assert str(exc.value) == "authentication service returned an invalid response"
    assert "provider-secret-invalid" not in str(exc.value)

def test_invalid_entity_kind_is_rejected_before_network() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("invalid kinds must not reach Supabase")

    store = SupabaseStore(BASE_URL, PUBLISHABLE_KEY, ACCESS_TOKEN, client=_client(handler))
    with pytest.raises(ValueError, match="entity kind"):
        store.list("../../secrets")


def test_download_missing_object_raises_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/v1/user":
            return _json_response(200, {"id": USER_ID}, request)
        return _json_response(404, {"message": "not found"}, request)

    store = SupabaseStore(BASE_URL, PUBLISHABLE_KEY, ACCESS_TOKEN, client=_client(handler))
    with pytest.raises(NotFoundError, match="storage object not found"):
        store.download_bytes("project/missing.pdf")

def test_live_probe_reports_only_sanitized_capabilities() -> None:
    from ops.runtime.supabase_probe import probe

    secret = "provider-error-containing-secret"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/v1/settings":
            return _json_response(200, {"external": {"email": True}}, request)
        if request.url.path == "/rest/v1/rb_entities":
            return _json_response(200, [], request)
        if request.url.path == "/storage/v1/object/list/rebuild-agent":
            return _json_response(403, {"message": secret}, request)
        raise AssertionError(f"unexpected probe request: {request.url.path}")

    result = probe(BASE_URL, PUBLISHABLE_KEY, client=_client(handler))

    assert result == {
        "configured": True,
        "auth": {"status_code": 200, "reachable": True},
        "rest": {
            "status_code": 200,
            "reachable": True,
            "table_ready": True,
            "visible_row_count": 0,
        },
        "storage": {
            "status_code": 403,
            "reachable": True,
            "bucket_ready": False,
            "visible_object_count": None,
        },
    }
    assert secret not in json.dumps(result)

def test_live_verify_stops_before_creating_users_when_schema_is_missing() -> None:
    from ops.runtime.supabase_live_verify import verify_live

    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/auth/v1/settings":
            return _json_response(200, {"external": {"email": True}}, request)
        if request.url.path == "/rest/v1/rb_entities":
            return _json_response(404, {"message": "missing and provider-secret"}, request)
        if request.url.path == "/storage/v1/object/list/rebuild-agent":
            return _json_response(200, [], request)
        raise AssertionError("schema preflight must stop before admin or user mutations")

    result = verify_live(
        BASE_URL,
        PUBLISHABLE_KEY,
        "secret-server-key",
        client=_client(handler),
    )

    assert result == {
        "status": "PENDING_SCHEMA",
        "stage": "schema_preflight",
        "auth_login_verified": False,
        "db_rls_verified": False,
        "storage_rls_verified": False,
        "logout_verified": False,
        "cleanup_complete": True,
    }
    serialized = json.dumps(result)
    assert "provider-secret" not in serialized
    assert "secret-server-key" not in serialized
    assert all("/auth/v1/admin/" not in path for path in calls)

def test_download_supabase_400_no_such_key_is_missing_object() -> None:
    # Observed from the actual user-JWT Storage API; HTTP status differs from
    # the enclosed 404. Only this documented object error means absent bytes.
    def handler(request):
        if request.url.path == "/auth/v1/user":
            return _json_response(200, {"id": USER_ID}, request)
        return _json_response(400, {"statusCode": "404", "error": "not_found",
            "message": "Object not found", "code": "NoSuchKey"}, request)
    store = SupabaseStore(BASE_URL, PUBLISHABLE_KEY, ACCESS_TOKEN, client=_client(handler))
    with pytest.raises(NotFoundError, match="storage object not found"):
        store.download_bytes("project/new-output.xlsx")


@pytest.mark.parametrize("status,code,method,path,expected", [
    (400, "NoSuchBucket", "GET", "/storage/v1/object/rebuild-agent/missing", StorageError),
    (400, "AccessDenied", "GET", "/storage/v1/object/rebuild-agent/missing", StorageError),
    (400, "NoSuchKey", "PATCH", "/rest/v1/rb_entities", StorageError),
    (400, "NoSuchKey", "POST", "/storage/v1/object/rebuild-agent/missing", StorageError),
    (403, "NoSuchKey", "GET", "/storage/v1/object/rebuild-agent/missing", PermissionDeniedError),
])
def test_only_storage_get_no_such_key_maps_to_missing(status,code,method,path,expected):
    store = SupabaseStore(BASE_URL, PUBLISHABLE_KEY, ACCESS_TOKEN,
        client=_client(lambda request: _json_response(status, {"code": code}, request)))
    with pytest.raises(expected) as error:
        store._request(method,path)
    assert type(error.value) is expected
