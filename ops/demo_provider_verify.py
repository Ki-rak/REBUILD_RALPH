"""Explicit provider-mode product check with real Supabase and real model calls.

This is a private in-process API verification, not a deployment or a local
credential fallback. Select --environment explicitly. Supplied INPUT remains
unchanged and only this run's disposable Auth user is removed.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import argparse,json,os,secrets
from datetime import datetime,timezone
from uuid import uuid4
import httpx
from fastapi.testclient import TestClient
from backend.config import Settings,load_environment
from backend.ai import call_bridge
from backend.server import create_app
from backend.storage import SupabaseStore
from ops.demo import ProductAPI,DemoError,catalog,select_projects,seed_past,upload_new,write_report
from ops.demo_live_verify import require,check,cleanup_created_users,office_signature,capture_output_objects
from ops.runtime.supabase_live_verify import _create_test_user,verify_live


def verify_execution(insight,environment):
    expected='CHATGPT_OAUTH' if environment=='local' else 'OPENAI_API_KEY'
    execution=insight.get('execution',{});usage=insight.get('usage',{})
    require(execution.get('source')=='MODEL_CALL' and execution.get('state')=='SUCCEEDED' and execution.get('auth_mode')==expected,'EXPECTED_REAL_MODEL_EXECUTION_REQUIRED')
    require(isinstance(usage,dict) and all(type(usage.get(key)) is int and usage[key]>=0 for key in ['input_tokens','output_tokens']),'ACTUAL_TOKEN_USAGE_REQUIRED')
    return execution,usage


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--environment',required=True,choices=['local','deployed'])
    args=parser.parse_args();previous=os.environ.get('REBUILD_ENV');os.environ['REBUILD_ENV']=args.environment
    load_environment();s=Settings.from_environment();key=os.environ.get('SUPABASE_SECRET_KEY','');run=uuid4().hex;users=[];stage='provider_readiness'
    report={'product':'RE:Build Agent','boundary':'REAL_SUPABASE_REAL_MODEL_IN_PROCESS_PRODUCT_API','environment':args.environment,'run_id':run,'at':datetime.now(timezone.utc).isoformat(),'checks':[],'product_complete':False,'deployment':False,'reviewer':'AUTOMATED_DISPOSABLE_TEST_ACCOUNT_ONLY','status':'PENDING','cleanup_complete':True}
    with httpx.Client(timeout=20,trust_env=False) as admin:
        try:
            s.validate();require(bool(key),'SUPABASE_SECRET_KEY_REQUIRED')
            readiness=call_bridge('status')
            if args.environment=='local':require(readiness.get('authentication')=='LOGGED_IN','OFFICIAL_LOCAL_OAUTH_LOGIN_REQUIRED')
            stage='supabase_preflight';report['preflight']=verify_live(s.supabase_url,s.publishable_key,key)
            require(report['preflight']['status']=='PASSED','SUPABASE_PREFLIGHT_REQUIRED')
            email=f'rebuild-provider-{run}@example.com';password=secrets.token_urlsafe(30)
            users.append(_create_test_user(admin,s.supabase_url,key,email,password,run,20))
            entries=catalog();past=select_projects(entries,['P01'],'historical');new=select_projects(entries,['N01'],'current')[0]
            past[0]['files']=[x for x in past[0]['files'] if x['name'] in {'01_Project_Brief_and_Lessons.docx','02_ITB_and_Contract_Rev00.pdf'}]
            new['files']=[x for x in new['files'] if x['name'] in {'02_ITB_and_Contract_Rev00.pdf','11_Addendum_Rev01.pdf'}]
            with TestClient(create_app(s),raise_server_exceptions=False) as client:
                api=ProductAPI(client);api.login(email,password);stage='actual_source_intake'
                report['historical']=seed_past(api,past,approved=True);incoming=upload_new(api,new);pid=incoming['project_id']
                stage='actual_product_model_call'
                draft=api.json('POST',f'/api/projects/{pid}/drafts',json={'kind':'itb','mode':'ai','question':'승인된 통지 기한을 과거 사례와 비교하여 원문 근거로 설명하고, 부족하거나 충돌하는 사항은 검토 필요로 남기세요.'})
                insight=draft.get('ai_insight',{});execution,usage=verify_execution(insight,args.environment)
                claims=[row for row in draft['rows'] if row.get('method')=='AI_INFERENCE']
                require(bool(claims) and all(row.get('source_refs') for row in claims),'ACTUAL_CITED_CLAIMS_REQUIRED')
                report.update(execution=execution,usage=usage,cited_claims=len(claims),draft_id=draft['id'])
                check(report,'actual_product_provider_call_with_source_refs',auth_mode=execution['auth_mode'])
                stage='actual_approval_output'
                api.json('POST',f"/api/drafts/{draft['id']}/approve",json={'confirmed':True,'revision':draft['revision']})
                data=api.request('POST',f"/api/drafts/{draft['id']}/export").content;signature=office_signature(data,'itb')
                from hashlib import sha256
                snapshot={'drafts':[{'id':draft['id'],'file_sha256':sha256(data).hexdigest()}]}
                store=SupabaseStore(s.supabase_url,s.publishable_key,api.token)
                try:
                    require(any(row['payload'].get('usage')==usage for row in store.list('event',pid)),'ACTUAL_USAGE_EVENT_MISSING')
                    capture_output_objects(store,snapshot)
                finally:store.close()
                report['stored_outputs']=snapshot['stored_outputs'];report['office']=signature
                target=ROOT/'ops/runtime/demo'/run;target.mkdir(parents=True,exist_ok=True);(target/'AI-ITB.xlsx').write_bytes(data)
                check(report,'actual_db_usage_and_storage_approved_office')
                api.logout()
            stage='fresh_application_instance'
            with TestClient(create_app(s),raise_server_exceptions=False) as client:
                api=ProductAPI(client);api.login(email,password);saved=api.json('GET',f"/api/drafts/{draft['id']}")
                require(saved['ai_insight']['usage']==usage and saved['ai_insight']['execution']==execution and saved['status']=='approved','ACTUAL_AI_RECORD_NOT_PERSISTED')
                api.logout()
            check(report,'new_app_and_login_preserve_actual_ai_usage_and_approval',process_restart=False)
            report['status']='PASSED'
        except (Exception,KeyboardInterrupt) as error:
            report.update(status='BLOCKED' if stage=='provider_readiness' else 'FAILED',stage=stage,error_code=str(error) if isinstance(error,DemoError) else 'SAFE_DIAGNOSTIC_WITHHELD')
        finally:
            if users:
                report['cleanup_complete']=cleanup_created_users(admin,s.supabase_url,key,users,run)
                if not report['cleanup_complete']:report.update(status='CLEANUP_REQUIRED',cleanup_owner_ids=users)
            if previous is None:os.environ.pop('REBUILD_ENV',None)
            else:os.environ['REBUILD_ENV']=previous
    path=write_report(report,'provider-live-verification');print(json.dumps({'status':report['status'],'environment':args.environment,'stage':report.get('stage'),'cleanup_complete':report['cleanup_complete'],'report':str(path.relative_to(ROOT))}))
    return 0 if report['status']=='PASSED' and report['cleanup_complete'] else 1

if __name__=='__main__':raise SystemExit(main())
