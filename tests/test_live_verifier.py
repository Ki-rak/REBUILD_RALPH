import httpx
import pytest
from ops.runtime import supabase_live_verify as live

URL="https://wsziosnttnxefgfbgpeq.supabase.co"


def test_live_preflight_uses_privileged_metadata_then_enters_user_rls_checks(monkeypatch):
    seen=[]
    def handler(request):
        seen.append((request.url.path,request.headers.get("apikey"),request.url.params.get("limit")))
        if request.url.path=="/auth/v1/settings":
            return httpx.Response(200,json={})
        if request.url.path=="/rest/v1/rb_entities":
            if request.headers.get("apikey")=="synthetic-admin":
                return httpx.Response(200,json=[])
            return httpx.Response(401,json={"code":"42501"})
        if request.url.path=="/storage/v1/bucket/rebuild-agent":
            return httpx.Response(200,json={"id":"rebuild-agent","public":False})
        return httpx.Response(403,json={})
    def reached_user_checks(*args,**kwargs):
        raise live.LiveVerifyFailure("create_test_users")
    monkeypatch.setattr(live,"_create_test_user",reached_user_checks)
    result=live.verify_live(URL,"synthetic-public","synthetic-admin",
                           client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert result["stage"]=="create_test_users"
    assert result["status"]=="FAILED" and not result["db_rls_verified"]
    assert ("/rest/v1/rb_entities","synthetic-admin","0") in seen


def test_missing_schema_preflight_never_creates_users(monkeypatch):
    def handler(request):
        return httpx.Response(404,json={}) if "/rest/" in request.url.path else httpx.Response(200,json={})
    def forbidden(*args,**kwargs):
        pytest.fail("Schema preflight must finish before creating isolated users")
    monkeypatch.setattr(live,"_create_test_user",forbidden)
    result=live.verify_live(URL,"synthetic-public","synthetic-admin",
                           client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert result["status"]=="PENDING_SCHEMA" and result["cleanup_complete"]