"""Acceptance boundary probes use isolated source copies, never evaluator or original mutations."""
from copy import deepcopy
from test_api import flow, auth, project, upload
import backend.server as server


def test_folder_approval_has_no_conversion_or_storage_side_effects_until_confirmation(flow, tmp_path, monkeypatch):
    client, records, files = flow
    root = tmp_path / 'INPUT'
    folder = root / '01_PAST_PROJECTS' / 'Past'
    folder.mkdir(parents=True)
    chosen = folder / 'approved.txt'
    chosen.write_text('Notice period: 28 calendar days.', encoding='utf-8')
    unchosen = folder / 'unselected.txt'
    unchosen.write_text('Employer: Other contract.', encoding='utf-8')
    monkeypatch.setattr(server, 'INPUT_ROOT', root)
    calls = []
    extract = server.extract_document
    def observe(data, *args, **kwargs):
        assert bytes(data) in files.values(), 'Original must exist before conversion starts'
        calls.append(args)
        return extract(data, *args, **kwargs)
    monkeypatch.setattr(server, 'extract_document', observe)
    pid = project(client, 'Approved archive', 'historical')
    before = deepcopy(records)
    listed = client.get('/api/import/candidates', headers=auth())
    assert listed.status_code == 200 and len(listed.json()['candidates']) == 2
    assert listed.json()['confirmation_required'] is True
    assert calls == [] and files == {} and records == before
    rel = '01_PAST_PROJECTS/Past/approved.txt'
    denied = client.post('/api/import/approve', headers=auth(),
        json={'project_id': pid, 'paths': [rel], 'confirmed': False})
    assert denied.status_code == 400
    assert calls == [] and files == {} and records == before
    accepted = client.post('/api/import/approve', headers=auth(),
        json={'project_id': pid, 'paths': [rel], 'confirmed': True})
    assert accepted.status_code == 200 and len(calls) == 1
    docs = client.get(f'/api/projects/{pid}/documents', headers=auth()).json()
    assert len(docs) == 1 and docs[0]['filename'] == 'approved.txt'
    assert docs[0]['extraction_status'] == 'EXTRACTED'
    assert files[docs[0]['storage_path']] == chosen.read_bytes()
    assert not any(record.get('payload', {}).get('filename') == 'unselected.txt' for record in records.values())


def test_management_latest_state_reacts_to_pending_modified_failed_and_lost_access(flow, tmp_path, monkeypatch):
    client, records, files = flow
    root = tmp_path / 'INPUT'
    folder = root / '01_PAST_PROJECTS' / 'Past'
    folder.mkdir(parents=True)
    chosen = folder / 'history.txt'
    chosen.write_text('Notice period: 28 calendar days.', encoding='utf-8')
    monkeypatch.setattr(server, 'INPUT_ROOT', root)
    pid = project(client, 'Archive', 'historical')
    status = lambda: client.get('/api/management', headers=auth()).json()
    assert status()['up_to_date'] is False and status()['unregistered_count'] == 1
    assert client.post('/api/import/approve', headers=auth(), json={
        'project_id': pid, 'paths': ['01_PAST_PROJECTS/Past/history.txt'], 'confirmed': True}).status_code == 200
    fresh = status()
    assert fresh['up_to_date'] is True and fresh['checked_at'] and fresh['historical_documents'] == 1
    document = client.get(f'/api/projects/{pid}/documents', headers=auth()).json()[0]
    original = files[document['storage_path']]
    chosen.write_text('Notice period: 21 calendar days.', encoding='utf-8')
    assert status()['up_to_date'] is False and status()['unregistered_count'] == 1
    assert files[document['storage_path']] == original
    chosen.write_bytes(original)
    assert status()['up_to_date'] is True
    response = client.post(f'/api/projects/{pid}/upload', headers=auth(),
        files={'files': ('broken.docx', b'not a document', 'application/octet-stream')})
    assert response.status_code == 200
    assert status()['up_to_date'] is False
    assert client.get('/api/management', headers=auth('revoked')).status_code == 401


def test_unrelated_history_does_not_create_false_notice_connection(flow):
    client, _, _ = flow
    past = project(client, 'Other topic', 'historical')
    upload(client, past, 'Garden planting species: oak and maple.', 'landscape.txt')
    current = project(client, 'New contract')
    upload(client, current, 'Notice period: 19 calendar days.', 'contract.txt')
    response = client.post(f'/api/projects/{current}/analyze', json={'mode': 'rules'}, headers=auth())
    assert response.status_code == 200
    row = next(row for row in response.json()['rows'] if row['id'] == 'notice')
    assert '19 calendar days' in row['current']
    assert row['historical_refs'] == [] and row['past'] == ''
    assert row['decision'] == 'REVIEW_REQUIRED'
    assert row['missing_information']
