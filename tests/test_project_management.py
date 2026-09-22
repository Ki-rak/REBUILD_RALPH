from test_api import flow, auth, project, upload, draft


def test_project_rename_and_soft_delete_preserve_originals_and_deny_access(flow):
    c, records, files = flow
    pid = project(c, 'Original')
    document = upload(c, pid, 'Notice period: 14 calendar days.')
    made = draft(c, pid)
    before = c.get(f'/api/projects/{pid}', headers=auth()).json()
    assert c.patch(f'/api/projects/{pid}', json={'name':'Renamed','version':before['version']}, headers=auth('bob')).status_code == 404
    assert c.request('DELETE',f'/api/projects/{pid}',json={'confirmed':True,'version':before['version']},headers=auth('bob')).status_code == 404
    renamed = c.patch(f'/api/projects/{pid}', json={'name':'Renamed','version':before['version']}, headers=auth())
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()['name'] == 'Renamed'
    assert c.patch(f'/api/projects/{pid}', json={'name':'Stale','version':before['version']}, headers=auth()).status_code == 409
    assert c.post(f'/api/drafts/{made["id"]}/approve',json={'confirmed':True,'revision':made['revision']},headers=auth()).status_code == 409
    version = renamed.json()['version']
    assert c.request('DELETE',f'/api/projects/{pid}',json={'confirmed':False,'version':version},headers=auth()).status_code == 400
    assert c.request('DELETE',f'/api/projects/{pid}',json={'confirmed':True,'version':before['version']},headers=auth()).status_code == 409
    removed=c.request('DELETE',f'/api/projects/{pid}',json={'confirmed':True,'version':version},headers=auth())
    assert removed.status_code == 200, removed.text
    assert removed.json()['originals_preserved'] is True
    assert files[document['storage_path']] == b'Notice period: 14 calendar days.'
    assert not c.get('/api/projects',headers=auth()).json()
    assert not c.get('/api/search?q=Notice',headers=auth()).json()['items']
    for path in [f'/api/projects/{pid}',f'/api/projects/{pid}/documents',f'/api/projects/{pid}/drafts',f'/api/documents/{document["id"]}/original',f'/api/documents/{document["id"]}/knowledge',f'/api/drafts/{made["id"]}']:
        assert c.get(path,headers=auth()).status_code == 404, path
    assert c.post(f'/api/projects/{pid}/analyze',json={'mode':'rules'},headers=auth()).status_code == 404
    assert c.post(f'/api/drafts/{made["id"]}/export',headers=auth()).status_code == 404


def test_historical_project_change_invalidates_related_approval(flow):
    c, records, files=flow
    past=project(c,'Historical','historical')
    upload(c,past,'Notice period: 28 calendar days.','past.txt')
    current=project(c)
    upload(c,current,'Notice period: 14 calendar days.')
    made=draft(c,current)
    assert c.post(f'/api/drafts/{made["id"]}/approve',json={'confirmed':True,'revision':made['revision']},headers=auth()).status_code==200
    old=c.get(f'/api/projects/{past}',headers=auth()).json()
    changed=c.patch(f'/api/projects/{past}',json={'name':'Historical revised','version':old['version']},headers=auth())
    assert changed.status_code==200,changed.text
    assert c.get(f'/api/drafts/{made["id"]}',headers=auth()).json()['status']=='draft'
    assert c.post(f'/api/drafts/{made["id"]}/export',headers=auth()).status_code==409
    fresh=draft(c,current)
    assert c.post(f'/api/drafts/{fresh["id"]}/approve',json={'confirmed':True,'revision':fresh['revision']},headers=auth()).status_code==200
    version=changed.json()['version']
    assert c.request('DELETE',f'/api/projects/{past}',json={'confirmed':True,'version':version},headers=auth()).status_code==200
    assert c.post(f'/api/drafts/{fresh["id"]}/export',headers=auth()).status_code==409
    analyzed=c.post(f'/api/projects/{current}/analyze',json={'mode':'rules'},headers=auth()).json()
    assert not any(row.get('historical_refs') for row in analyzed['rows'])


def test_legacy_draft_requires_new_snapshot_and_signed_snapshot_cannot_be_tampered(flow):
    c, records, files = flow
    pid=project(c)
    upload(c,pid,'Notice period: 14 calendar days.')
    made=draft(c,pid)
    assert c.post(f'/api/drafts/{made["id"]}/approve',json={'confirmed':True,'revision':made['revision']},headers=auth()).status_code==200
    stored=next(v for v in records.values() if v['id']==made['id'])
    saved_versions=stored['payload'].pop('project_versions')
    response=c.post(f'/api/drafts/{made["id"]}/export',headers=auth())
    assert response.status_code==409 and response.json()['detail']['code']=='DRAFT_PROJECT_SNAPSHOT_REQUIRED'
    stored['payload']['project_versions']=saved_versions
    stored['payload']['project_versions']['forged-project']=1
    assert c.post(f'/api/drafts/{made["id"]}/export',headers=auth()).status_code==409

    legacy=draft(c,pid)
    legacy_stored=next(v for v in records.values() if v['id']==legacy['id'])
    legacy_stored['payload'].pop('project_versions')
    response=c.post(f'/api/drafts/{legacy["id"]}/approve',json={'confirmed':True,'revision':legacy['revision']},headers=auth())
    assert response.status_code==409 and response.json()['detail']['code']=='DRAFT_PROJECT_SNAPSHOT_REQUIRED'
