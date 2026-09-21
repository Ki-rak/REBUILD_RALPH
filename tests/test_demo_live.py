"""Runner safety and real-input workflow tests; storage is explicitly injected."""
from copy import deepcopy
from pathlib import Path
from io import BytesIO
import pytest
from test_api import flow, FakeStorage
from ops.demo import ProductAPI,catalog,select_projects,DemoError
from ops.demo_live_verify import run_test_flow,recheck_persistence,office_signature,cleanup_created_users,capture_output_objects


def test_actual_dataset_to_three_outputs_and_resume_checkpoint(flow,tmp_path):
    c,records,files=flow;api=ProductAPI(c,token='alice')
    entries=catalog();past=select_projects(entries,['P01'],'historical')
    past[0]['files']=[x for x in past[0]['files'] if x['name'] in {'01_Project_Brief_and_Lessons.docx','02_ITB_and_Contract_Rev00.pdf','03_Commercial_Risk_Procurement.xlsx'}]
    current=select_projects(entries,['N01'],'current')
    current[0]['files']=[x for x in current[0]['files'] if x['name'] in {'01_Project_Brief_and_Lessons.docx','02_ITB_and_Contract_Rev00.pdf','03_Commercial_Risk_Procurement.xlsx','11_Addendum_Rev01.pdf','11_Addendum_Rev02.pdf'}]
    report={'boundary':'TEST_STORAGE_INJECTED','checks':[]}
    snapshot=run_test_flow(api,past,current,tmp_path,report)
    assert {x['kind'] for x in snapshot['drafts']}=={'itb','risk','slides'}
    assert len(snapshot['documents'])==5
    owner=next(owner for owner,eid in records)
    store=FakeStorage(owner,records,files)
    capture_output_objects(store,snapshot)
    recheck_persistence(api,snapshot,report,store)
    assert any(x['name']=='persisted_approved_outputs' and x['passed'] for x in report['checks'])
    document=snapshot['documents'][0]
    # A disappeared document must not silently become a passing restart proof.
    owner=next(owner for owner,eid in records if eid==document['id'])
    records.pop((owner,document['id']))
    with pytest.raises(DemoError):recheck_persistence(api,snapshot,report,store)


def test_reopen_rejects_corrupt_office():
    with pytest.raises(DemoError):office_signature(b'not an xlsx','itb')
    with pytest.raises(DemoError):office_signature(b'not a pptx','slides')


def test_cleanup_never_deletes_accounts_if_inventory_failed():
    class Broken:
        def __init__(self):self.requests=[]
        def request(self,method,url,**kwargs):
            self.requests.append(method)
            raise OSError('synthetic unavailability')
    http=Broken()
    assert cleanup_created_users(http,'https://wsziosnttnxefgfbgpeq.supabase.co','test-secret',['known-created-owner'],'test-run') is False
    assert 'DELETE' not in http.requests


def test_full_supplied_p01_p06_n01_n02_dataset(flow,tmp_path):
    c,records,files=flow;api=ProductAPI(c,token='alice');entries=catalog()
    report={'boundary':'TEST_STORAGE_INJECTED','checks':[]}
    snapshot=run_test_flow(api,select_projects(entries,['P01','P06'],'historical'),select_projects(entries,['N01','N02'],'current'),tmp_path,report)
    assert len(snapshot['projects'])==2 and len(snapshot['documents'])==18
    assert len(snapshot['drafts'])==6 and len(snapshot['historical_documents'])==21
    owner=next(owner for owner,eid in records)
    store=FakeStorage(owner,records,files)
    capture_output_objects(store,snapshot)
    recheck_persistence(api,snapshot,report,store)
    assert all(check['passed'] for check in report['checks'])


def test_cleanup_lists_real_storage_paths_including_orphans_before_deleting_user():
    import httpx
    owner='11111111-1111-4111-8111-111111111111';run='run123';objects={owner+'/'+owner+'/p/original.pdf',owner+'/orphan/knowledge.md'};deleted=[]
    def handler(request):
        url=request.url.path
        if request.method=='GET' and '/auth/v1/admin/users/' in url:return httpx.Response(200,json={'user_metadata':{'created_by':'rebuild-agent-live-probe','run_id':run}})
        if request.method=='GET' and url=='/rest/v1/rb_entities':return httpx.Response(200,json=[{'id':'row1','payload':{'storage_path':owner+'/p/original.pdf'}}])
        if request.method=='POST' and url.endswith('/object/list/rebuild-agent'):
            import json
            prefix=json.loads(request.content)['prefix'].rstrip('/')+'/'
            entries={}
            for path in objects:
                if path.startswith(prefix):
                    tail=path[len(prefix):];name=tail.split('/')[0]
                    entries[name]={'name':name,'id':None if '/' in tail else 'object-id','metadata':None if '/' in tail else {}}
            return httpx.Response(200,json=list(entries.values()))
        if request.method=='DELETE' and url.endswith('/object/rebuild-agent'):
            import json
            for path in json.loads(request.content)['prefixes']:
                assert path in objects;objects.remove(path);deleted.append(path)
            return httpx.Response(200,json=[])
        if request.method=='DELETE':
            assert not objects,'Never destroy row/user recovery metadata before Storage is empty'
            return httpx.Response(204)
        raise AssertionError((request.method,url))
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        assert cleanup_created_users(http,'https://wsziosnttnxefgfbgpeq.supabase.co','fake-secret',[owner],run)
    assert len(deleted)==2 and not objects


@pytest.mark.parametrize('failure',['traversal','second_page','objects_remain','owner_mismatch'])
def test_cleanup_failure_preserves_recovery_user_and_rows(failure):
    import httpx,json
    owner='11111111-1111-4111-8111-111111111111';run='run123';requests=[]
    def handler(request):
        requests.append((request.method,request.url.path))
        if request.method=='GET':
            return httpx.Response(200,json={'user_metadata':{'created_by':'rebuild-agent-live-probe','run_id':'different' if failure=='owner_mismatch' else run}})
        if request.method=='POST':
            offset=json.loads(request.content)['offset']
            if failure=='traversal':return httpx.Response(200,json=[{'name':'../another-owner','id':'file','metadata':{}}])
            if failure=='second_page':
                return httpx.Response(503) if offset else httpx.Response(200,json=[{'name':f'file-{i}','id':f'id-{i}','metadata':{}} for i in range(100)])
            return httpx.Response(200,json=[{'name':'still-present','id':'file','metadata':{}}])
        return httpx.Response(200,json=[])
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        assert not cleanup_created_users(http,'https://example.invalid','fake-secret',[owner],run)
    assert not any(method=='DELETE' and '/storage/' not in path for method,path in requests)
    if failure!='objects_remain':assert not any(method=='DELETE' for method,path in requests)


def test_missing_stored_output_fails_before_export_could_regenerate():
    class MissingStore:
        def download_bytes(self,path):raise FileNotFoundError('injected missing object')
    class NoAPI:
        def json(self,*args,**kwargs):raise AssertionError('No API regeneration allowed before exact object check')
    snapshot={'drafts':[{'id':'draft'}],'stored_outputs':[{'path':'owner/output.xlsx','sha256':'a'*64}]}
    with pytest.raises(DemoError,match='RESTART_STORED_OUTPUT_UNAVAILABLE'):
        recheck_persistence(NoAPI(),snapshot,{'checks':[]},MissingStore())

def test_real_server_identity_is_not_shadowed_by_frontend(monkeypatch):
    from fastapi.testclient import TestClient
    from ops.demo_live_server import app
    monkeypatch.setenv('REBUILD_LIVE_VERIFY_RUN_ID','owned-live-run')
    with TestClient(app) as client:
        response=client.get('/__rebuild_live_verify_identity')
        assert response.status_code==200
        assert response.json()=={'run_id':'owned-live-run','boundary':'REAL_SUPABASE_USER_JWT','product':'RE:Build Agent'}
        assert 'text/html' in client.get('/').headers['content-type']
        monkeypatch.delenv('REBUILD_LIVE_VERIFY_RUN_ID')
        assert client.get('/__rebuild_live_verify_identity').status_code==404
