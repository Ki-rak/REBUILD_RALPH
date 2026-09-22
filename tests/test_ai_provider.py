import json
from types import SimpleNamespace
import httpx
import pytest
from backend import ai
from backend.openai_provider import OpenAIProviderError, analyze, status

ENV = {"REBUILD_ENV": "deployed", "OPENAI_API_KEY": "server-secret", "OPENAI_MODEL": "gpt-test", "OPENAI_BASE_URL": "https://api.openai.com/v1"}
REQUEST = {"question": "What changed?", "evidence": [{"id": "SRC-1", "text": "The approved period is 14 days.", "location": "page 1"}]}

def payload(source_id="SRC-1"):
    return {"model": "gpt-test-2026-01-01", "usage": {"input_tokens": 12, "output_tokens": 7, "total_tokens": 19, "input_tokens_details": {"cached_tokens": 3}}, "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps({"status": "ANSWERED", "answer": "The approved period is 14 days.", "claims": [{"text": "The approved period is 14 days.", "source_ids": [source_id]}]})}]}]}

def test_deployed_direct_request_and_trusted_metadata():
    seen = {}
    def handler(request):
        seen["request"] = request
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=payload())
    result = analyze(REQUEST, environ=ENV, transport=httpx.MockTransport(handler))
    assert seen["request"].url == httpx.URL("https://api.openai.com/v1/responses")
    assert seen["request"].headers["authorization"] == "Bearer server-secret"
    assert seen["body"]["store"] is False and seen["body"]["tools"] == []
    assert seen["body"]["text"]["format"]["strict"] is True
    assert result["usage"] == {"input_tokens": 12, "output_tokens": 7, "total_tokens": 19, "cached_input_tokens": 3}
    assert result["execution"]["source"] == "MODEL_CALL"

def test_deployed_rejects_unknown_citation_and_base_url():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload("OTHER")))
    with pytest.raises(OpenAIProviderError, match="UNKNOWN_SOURCE_ID"):
        analyze(REQUEST, environ=ENV, transport=transport)
    with pytest.raises(OpenAIProviderError, match="OPENAI_BASE_URL_FORBIDDEN"):
        analyze(REQUEST, environ={**ENV, "OPENAI_BASE_URL": "https://evil.example/v1"}, transport=transport)

@pytest.mark.parametrize("status_code,code", [(400, "OPENAI_INVALID_REQUEST"), (401, "OPENAI_AUTH_FAILED"), (429, "OPENAI_RATE_LIMITED"), (503, "OPENAI_UNAVAILABLE")])
def test_deployed_redacts_http_errors(status_code, code):
    transport = httpx.MockTransport(lambda request: httpx.Response(status_code, text="server-secret upstream body"))
    with pytest.raises(OpenAIProviderError) as caught:
        analyze(REQUEST, environ=ENV, transport=transport)
    assert caught.value.code == code and str(caught.value) == code

def test_deployed_timeout_and_status_are_sanitized():
    def timeout(_request):
        raise httpx.ReadTimeout("server-secret detail")
    with pytest.raises(OpenAIProviderError, match="OPENAI_REQUEST_TIMEOUT"):
        analyze(REQUEST, environ=ENV, transport=httpx.MockTransport(timeout), timeout=.01)
    assert status(ENV) == {"provider": "openai-responses", "authentication": "CONFIGURED_UNTESTED", "inference": "NOT_TESTED"}

def test_call_bridge_deployed_never_spawns_node(monkeypatch):
    monkeypatch.setenv("REBUILD_ENV", "deployed")
    monkeypatch.setattr(ai.subprocess, "run", lambda *args, **kwargs: pytest.fail("Node must not run"))
    monkeypatch.setattr(ai, "deployed_analyze", lambda request, environ=None: {"answer": request["question"]})
    assert ai.call_bridge("analyze", {"question": "direct", "evidence": []}) == {"answer": "direct"}

def test_call_bridge_local_keeps_official_node_bridge(monkeypatch):
    monkeypatch.setenv("REBUILD_ENV", "local")
    seen = {}
    def run(command, **kwargs):
        seen.update(command=command, kwargs=kwargs)
        return SimpleNamespace(returncode=0, stdout=json.dumps({"ok": True, "result": {"provider": "codex-oauth"}}))
    monkeypatch.setattr(ai.subprocess, "run", run)
    assert ai.call_bridge("status") == {"provider": "codex-oauth"}
    assert seen["command"][0] == "node" and seen["kwargs"]["timeout"] == 105

@pytest.mark.parametrize(
    "code",
    [
        "INVALID_OPENAI_RESPONSE",
        "INVALID_PROVIDER_JSON",
        "UNCITED_ANSWER",
        "UNCITED_CLAIM",
    ],
)
def test_ai_error_preserves_safe_provider_contract_codes(code):
    assert ai.AIError(code).code == code


def test_deployed_schema_allows_only_this_requests_citation_ids():
    bodies=[]
    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200,json=payload())
    analyze(REQUEST,environ=ENV,transport=httpx.MockTransport(handler))
    ids=bodies[0]["text"]["format"]["schema"]["properties"]["claims"]["items"]["properties"]["source_ids"]["items"]
    assert ids == {"type":"string","enum":["SRC-1"]}
    from backend.openai_provider import OUTPUT_SCHEMA
    assert "enum" not in OUTPUT_SCHEMA["properties"]["claims"]["items"]["properties"]["source_ids"]["items"]
