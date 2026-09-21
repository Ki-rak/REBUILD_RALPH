"""Configuration profiles remain separate from supported environment-bound inference."""
from test_api import flow, auth, project, upload


def configuration():
    return {"type": "corporate_llm", "name": "Team research", "protocol": "OpenAI-compatible HTTPS",
            "endpoint": "https://llm.example.invalid/v1", "model": "future-model"}


def profile(client, **changes):
    response = client.post('/api/settings/profiles', json={**configuration(), **changes}, headers=auth())
    assert response.status_code == 200
    return response.json()


def test_profile_edit_preserves_identity_and_uses_optimistic_version(flow):
    client, _, _ = flow
    saved = profile(client)
    changed = {**configuration(), "name": "Revised configuration", "model": "model-two", "version": saved['version']}
    response = client.patch(f"/api/settings/profiles/{saved['id']}", json=changed, headers=auth())
    assert response.status_code == 200
    updated = response.json()
    assert updated['id'] == saved['id'] and updated['version'] == saved['version'] + 1
    assert updated['name'] == changed['name'] and updated['status'] == 'NOT_CONFIGURED'
    assert updated['active'] is False
    assert len(client.get('/api/settings/profiles', headers=auth()).json()) == 1
    assert client.patch(f"/api/settings/profiles/{saved['id']}", json=changed, headers=auth()).status_code == 409
    assert client.patch(f"/api/settings/profiles/{saved['id']}", json=changed, headers=auth('bob')).status_code == 404


def test_project_profile_selection_blocks_unconnected_ai_without_fallback(flow):
    client, _, _ = flow
    pid = project(client)
    upload(client, pid, 'Notice period: 19 calendar days.')
    saved = profile(client)
    current = client.get(f'/api/projects/{pid}', headers=auth()).json()
    selected = client.put(f'/api/projects/{pid}/provider-profile',
        json={'profile_id': saved['id'], 'version': current['version']}, headers=auth())
    assert selected.status_code == 200
    assert selected.json()['provider_profile_id'] == saved['id']
    state = client.get(f'/api/projects/{pid}/provider', headers=auth()).json()
    assert state['selected_profile']['id'] == saved['id']
    assert state['active'] is False and state['status'] == 'NOT_CONFIGURED'
    blocked = client.post(f'/api/projects/{pid}/analyze', json={'mode': 'ai'}, headers=auth())
    assert blocked.status_code == 503
    assert blocked.json()['detail']['code'] == 'PROFILE_NOT_CONNECTED'
    assert client.post(f'/api/projects/{pid}/analyze', json={'mode': 'rules'}, headers=auth()).status_code == 200
    assert client.put(f'/api/projects/{pid}/provider-profile',
        json={'profile_id': saved['id'], 'version': current['version']}, headers=auth()).status_code == 409
    cleared = client.put(f'/api/projects/{pid}/provider-profile',
        json={'profile_id': None, 'version': selected.json()['version']}, headers=auth())
    assert cleared.status_code == 200 and cleared.json()['provider_profile_id'] is None
    default = client.get(f'/api/projects/{pid}/provider', headers=auth()).json()
    assert default['selected_profile'] is None and default['runtime_policy'] == 'ENVIRONMENT_BOUND_OPENAI'


def test_profile_selection_and_updates_enforce_owner_type_and_safe_endpoint(flow):
    client, _, _ = flow
    pid = project(client)
    saved = profile(client)
    current = client.get(f'/api/projects/{pid}', headers=auth()).json()
    assert client.put(f'/api/projects/{pid}/provider-profile',
        json={'profile_id': saved['id'], 'version': current['version']}, headers=auth('bob')).status_code == 404
    sso = profile(client, type='sso', protocol='OIDC', model='')
    assert client.put(f'/api/projects/{pid}/provider-profile',
        json={'profile_id': sso['id'], 'version': current['version']}, headers=auth()).status_code == 422
    unsafe = {**configuration(), 'endpoint': 'https://user:secret@example.invalid', 'version': saved['version']}
    assert client.patch(f"/api/settings/profiles/{saved['id']}", json=unsafe, headers=auth()).status_code == 400
    profiles = client.get('/api/settings/profiles', headers=auth()).json()
    assert next(p for p in profiles if p['id'] == saved['id'])['endpoint'] == configuration()['endpoint']
    assert client.get('/api/settings/profiles', headers=auth('bob')).json() == []


def test_provider_change_before_model_call_discards_analysis_without_call(monkeypatch):
    _provider_race(monkeypatch, during_call=False)


def test_provider_change_during_model_call_discards_result_without_draft(monkeypatch):
    _provider_race(monkeypatch, during_call=True)


def _provider_race(monkeypatch, during_call):
    from uuid import uuid4
    from fastapi.testclient import TestClient
    from backend.config import Settings
    import backend.server as server
    from test_api import FakeStorage, FakeAuth
    records, files, calls = {}, {}, []
    owner = str(uuid4())
    holder = {}
    def context(token):
        return server.Context({'id': owner}, FakeStorage(owner, records, files), FakeAuth(), token)
    def switch():
        client, pid, selected = holder['client'], holder['pid'], holder['profile']
        current = client.get(f'/api/projects/{pid}', headers=auth()).json()
        response = client.put(f'/api/projects/{pid}/provider-profile',
            json={'profile_id': selected['id'], 'version': current['version']}, headers=auth())
        assert response.status_code == 200
    def bridge(operation, request=None):
        calls.append(operation)
        if during_call:
            switch()
        # Controlled routing stub: this is not an actual AI/provider connection.
        return {'answer': 'Controlled test response', 'claims': []}
    client = TestClient(server.create_app(Settings('https://example.supabase.co', 'test-key', 'local',
        'test-integrity-key-of-at-least-32-characters'), context_factory=context, ai_bridge=bridge),
        raise_server_exceptions=False)
    pid = project(client)
    upload(client, pid, 'Notice period: 19 calendar days.')
    holder.update(client=client, pid=pid, profile=profile(client))
    if not during_call:
        compare = server.compare
        def change_during_comparison(current, historical):
            result = compare(current, historical)
            switch()
            return result
        monkeypatch.setattr(server, 'compare', change_during_comparison)
    response = client.post(f'/api/projects/{pid}/drafts',
        json={'kind': 'itb', 'mode': 'ai'}, headers=auth())
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'PROVIDER_CONFIGURATION_CHANGED'
    assert calls == (['analyze'] if during_call else [])
    assert client.get(f'/api/projects/{pid}/drafts', headers=auth()).json() == []
