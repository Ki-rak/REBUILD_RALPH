"""Actual user-JWT negative and changed-input checks, using isolated QA inputs.

The supplied project demo remains in demo_browser_verify.py. This verifies
non-demo failure cases without changing original INPUT or real user accounts.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from copy import deepcopy
from hashlib import sha256
import os,secrets,json
from uuid import uuid4
from datetime import datetime,timezone
import httpx
from backend.config import Settings,load_environment
from ops.demo import ProductAPI,DemoError,write_report
from ops.demo_live_verify import OwnedServer,require,check,cleanup_created_users
from ops.runtime.supabase_live_verify import _create_test_user,verify_live


def run_negative_flow(api,other,report):
    pid=api.json('POST','/api/projects',json={'name':'Isolated changed-input QA '+uuid4().hex,'kind':'current'})['id']
    marker=uuid4().hex
    original=f'Notice: 13 calendar days.\nQA run {marker}'.encode()
    def upload(name,data):
        return api.json('POST',f'/api/projects/{pid}/upload',files={'files':(name,data,'application/octet-stream')})['documents'][0]
    first=upload('original.txt',original)
    require(api.request('GET',f"/api/documents/{first['id']}/original").content==original,'QA_ORIGINAL_CHANGED')
    analysis=api.json('POST',f'/api/projects/{pid}/analyze',json={'mode':'rules'})
    notice=next(x for x in analysis['rows'] if x['id']=='notice')
    require('13 calendar days' in notice['current'] and not notice['historical_refs'] and notice['decision']=='REVIEW_REQUIRED','NO_HISTORY_MUST_REQUIRE_REVIEW')
    duplicate=upload('alias.txt',original)
    require(duplicate.get('duplicate') is True and duplicate['id']==first['id'],'QA_DUPLICATE_CREATED_NEW_DOCUMENT')
    docs=api.json('GET',f'/api/projects/{pid}/documents')
    require(len(docs)==1 and {'original.txt','alias.txt'}.issubset(docs[0]['aliases']),'QA_DUPLICATE_ALIASES_MISSING')
    check(report,'no_history_review_required_original_bytes_and_dedup')
    draft=api.json('POST',f'/api/projects/{pid}/drafts',json={'kind':'itb','mode':'rules'})
    api.request('POST',f"/api/drafts/{draft['id']}/export",expected=(409,))
    api.json('POST',f"/api/drafts/{draft['id']}/approve",json={'confirmed':True,'revision':draft['revision']})
    rows=deepcopy(draft['rows']);rows[0]['rationale']='Isolated automated QA reviewer edit'
    edited=api.json('PATCH',f"/api/drafts/{draft['id']}",json={'rows':rows,'revision':draft['revision']})
    require(edited['status']=='draft' and edited['revision']==draft['revision']+1,'EDIT_DID_NOT_INVALIDATE_APPROVAL')
    api.request('POST',f"/api/drafts/{draft['id']}/export",expected=(409,))
    api.request('POST',f"/api/drafts/{draft['id']}/approve",json={'confirmed':True,'revision':draft['revision']},expected=(409,))
    api.json('POST',f"/api/drafts/{draft['id']}/approve",json={'confirmed':True,'revision':edited['revision']})
    changed=upload('changed.txt',f'Notice: 9 calendar days.\nQA run {marker}'.encode())
    require(changed['sha256']!=first['sha256'],'CHANGED_BYTES_HASH_UNCHANGED')
    api.request('POST',f"/api/drafts/{draft['id']}/export",expected=(409,))
    after=api.json('POST',f'/api/projects/{pid}/analyze',json={'mode':'rules'})
    require(any('9 calendar days' in row['current'] for row in after['rows']) and after['rows']!=analysis['rows'],'CHANGED_INPUT_NOT_REFLECTED')
    check(report,'edit_stale_revision_and_new_input_invalidate_approval')
    broken=b'not-a-docx-'+marker.encode();corrupt=upload('corrupt.docx',broken)
    require(corrupt['extraction_status']=='ERROR' and corrupt['sha256']==sha256(broken).hexdigest(),'CORRUPT_INPUT_MISREPORTED')
    require(api.request('GET',f"/api/documents/{corrupt['id']}/original").content==broken,'CORRUPT_ORIGINAL_NOT_PRESERVED')
    retried=api.json('POST',f"/api/documents/{corrupt['id']}/retry")
    require(retried['extraction_status']=='ERROR' and retried['sha256']==corrupt['sha256'],'CORRUPT_RETRY_MISREPORTED')
    require(api.request('GET',f"/api/documents/{first['id']}/original").content==original,'VALID_ORIGINAL_LOST_AFTER_FAILURE')
    check(report,'corrupt_original_preserved_retry_honest_valid_document_survives')
    require(other.json('GET','/api/projects')==[],'CROSS_USER_PROJECT_LEAK')
    other.request('GET',f'/api/projects/{pid}',expected=(404,))
    other.request('GET',f"/api/documents/{first['id']}/original",expected=(404,))
    other.request('POST',f"/api/drafts/{draft['id']}/export",expected=(404,))
    check(report,'actual_product_cross_user_reads_and_exports_denied')


def main():
    load_environment();s=Settings.from_environment();key=os.environ.get('SUPABASE_SECRET_KEY','');run=uuid4().hex;users=[];server=None;stage='preflight'
    report={'product':'RE:Build Agent','boundary':'REAL_SUPABASE_USER_JWT_QA_INPUTS','run_id':run,'at':datetime.now(timezone.utc).isoformat(),'checks':[],'product_complete':False,'reviewer':'AUTOMATED_DISPOSABLE_TEST_ACCOUNT_ONLY','status':'PENDING','cleanup_complete':True}
    with httpx.Client(timeout=20,trust_env=False) as admin:
        try:
            s.validate();report['preflight']=verify_live(s.supabase_url,s.publishable_key,key);require(report['preflight']['status']=='PASSED','PREFLIGHT_FAILED')
            credentials=[]
            for index in range(2):
                email=f'rebuild-negative-{run}-{index}@example.com';password=secrets.token_urlsafe(30)
                users.append(_create_test_user(admin,s.supabase_url,key,email,password,run,20));credentials.append((email,password))
            server=OwnedServer(run,8794);stage='owned_server';server.start()
            with httpx.Client(base_url=server.url,timeout=180,trust_env=False) as client:
                api=ProductAPI(client);other=ProductAPI(client);api.login(*credentials[0]);other.login(*credentials[1])
                stage='negative_cases';run_negative_flow(api,other,report);api.logout();other.logout()
            report['status']='PASSED'
        except (Exception,KeyboardInterrupt) as error:report.update(status='FAILED',stage=stage,error_code=str(error) if isinstance(error,DemoError) else 'SAFE_DIAGNOSTIC_WITHHELD')
        finally:
            if server:server.stop()
            if users:
                report['cleanup_complete']=cleanup_created_users(admin,s.supabase_url,key,users,run)
                if not report['cleanup_complete']:report.update(status='CLEANUP_REQUIRED',cleanup_owner_ids=users)
    path=write_report(report,'negative-live-verification');print(json.dumps({'status':report['status'],'stage':report.get('stage'),'cleanup_complete':report['cleanup_complete'],'report':str(path.relative_to(ROOT))}))
    return 0 if report['status']=='PASSED' and report['cleanup_complete'] else 1

if __name__=='__main__':raise SystemExit(main())
