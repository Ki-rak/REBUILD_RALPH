"""Owned actual-Supabase UI upload, approvals, downloads and process-restart proof.

Temporary users only; credentials cross the child boundary through stdin, and are
never written to the reports or command line. This does not claim AI completion.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import argparse,os,json,secrets,subprocess
from datetime import datetime,timezone
from uuid import uuid4
import httpx
from backend.config import Settings,load_environment
from backend.storage import SupabaseStore
from ops.demo import ProductAPI,catalog,select_projects,seed_past,write_report,DemoError,read_original
from ops.demo_live_verify import OwnedServer,require,check,office_signature,capture_output_objects,recheck_persistence,verify_sidecars,cleanup_created_users
from ops.runtime.supabase_live_verify import verify_live,_create_test_user


def stop_browser_process(process):
    if process.poll() is not None:return
    if os.name=='nt':
        result=subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=20,
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if result.returncode!=0:
            if process.poll() is None:process.kill()
            process.wait(timeout=10)
            raise DemoError('BROWSER_PROCESS_TREE_CLEANUP_UNCONFIRMED')
    else:
        import signal
        os.killpg(process.pid,signal.SIGKILL)
    process.wait(timeout=10)


def browser_phase(server,run_id,credentials,projects,output_dir,phase,snapshot=None):
    config={'base':server.url,'run_id':run_id,'email':credentials[0],'password':credentials[1],
            'projects':projects,'output_dir':str(output_dir),'phase':phase,'snapshot':snapshot}
    process=subprocess.Popen(['node',str(ROOT/'ops/demo_browser.cjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        text=True,encoding='utf-8',cwd=ROOT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),start_new_session=os.name!='nt')
    try:process.communicate(json.dumps(config),timeout=2460)
    except (subprocess.TimeoutExpired,KeyboardInterrupt):
        stop_browser_process(process)
        raise DemoError('BROWSER_INTERRUPTED_OR_TIMED_OUT') from None
    path=output_dir/f'browser-{phase}.json'
    require(path.is_file(),'BROWSER_REPORT_MISSING')
    report=json.loads(path.read_text(encoding='utf-8'))
    require(process.returncode==0 and report['status']=='PASSED','BROWSER_'+phase.upper()+'_FAILED')
    for draft in report['drafts']:
        draft['signature']=office_signature(Path(draft['path']).read_bytes(),draft['kind'])
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--port',type=int,default=8793);args=parser.parse_args()
    load_environment();settings=Settings.from_environment();secret_key=os.environ.get('SUPABASE_SECRET_KEY','')
    run_id=uuid4().hex;users=[];server=None;stage='configuration'
    report={'product':'RE:Build Agent','boundary':'REAL_SUPABASE_BROWSER','run_id':run_id,'at':datetime.now(timezone.utc).isoformat(),
            'status':'PENDING','checks':[],'reviewer':'AUTOMATED_DISPOSABLE_TEST_ACCOUNT_ONLY','ai_verified':False,'product_complete':False,'cleanup_complete':True}
    with httpx.Client(timeout=20,trust_env=False) as admin:
        try:
            settings.validate();require(bool(secret_key),'SUPABASE_SECRET_KEY_REQUIRED')
            stage='preflight';report['preflight']=verify_live(settings.supabase_url,settings.publishable_key,secret_key)
            require(report['preflight']['status']=='PASSED','SUPABASE_PREFLIGHT_NOT_PASSED')
            entries=catalog();past=select_projects(entries,['P01','P06'],'historical');current=select_projects(entries,['N01','N02'],'current')
            stage='isolated_user';email=f'rebuild-browser-{run_id}@example.com';password=secrets.token_urlsafe(30)
            owner=_create_test_user(admin,settings.supabase_url,secret_key,email,password,run_id,20);users.append(owner);credentials=(email,password)
            server=OwnedServer(run_id,args.port);stage='start_server';first_pid=server.start();output_dir=ROOT/'ops/runtime/demo'/run_id;output_dir.mkdir(parents=True,exist_ok=True)
            stage='approved_past_only'
            with httpx.Client(base_url=server.url,timeout=180,trust_env=False) as client:
                api=ProductAPI(client);api.login(*credentials);report['historical']=seed_past(api,past,approved=True);api.logout()
            stage='initial_browser_ui';snapshot=browser_phase(server,run_id,credentials,current,output_dir,'initial')
            report['initial_browser_report']=str(output_dir/'browser-initial.json');report['snapshot']=snapshot
            check(report,'actual_ui_upload_edit_approve_download',projects=len(snapshot['projects']),documents=len(snapshot['documents']),outputs=len(snapshot['drafts']))
            with httpx.Client(base_url=server.url,timeout=180,trust_env=False) as client:
                api=ProductAPI(client);api.login(*credentials);store=SupabaseStore(settings.supabase_url,settings.publishable_key,api.token)
                try:capture_output_objects(store,snapshot)
                finally:store.close()
                verify_sidecars(api,settings,owner,snapshot,report);api.logout()
            stage='actual_restart';server.stop();second_pid=server.start();require(second_pid!=first_pid,'PROCESS_NOT_RESTARTED')
            with httpx.Client(base_url=server.url,timeout=180,trust_env=False) as client:
                api=ProductAPI(client);api.login(*credentials);store=SupabaseStore(settings.supabase_url,settings.publishable_key,api.token)
                try:recheck_persistence(api,snapshot,report,store)
                finally:store.close()
                api.logout()
            stage='resume_browser_ui';resumed=browser_phase(server,run_id,credentials,current,output_dir,'resume',snapshot)
            for draft in resumed['drafts']:
                previous=next(item for item in snapshot['drafts'] if item['id']==draft['id'])
                require(draft['signature']==previous['signature'],'RESTART_UI_OUTPUT_CONTENT_CHANGED')
            report['resumed_browser_report']=str(output_dir/'browser-resume.json')
            check(report,'actual_process_restart_fresh_ui_login_approved_downloads',first_pid=first_pid,second_pid=second_pid,outputs=len(resumed['drafts']))
            for project in past+current:
                for item in project['files']:read_original(item)
            check(report,'original_input_hashes_unchanged')
            report['status']='PASSED_REAL_UI_RULES_AI_NOT_TESTED'
        except (Exception,KeyboardInterrupt) as error:
            report.update(status='FAILED',stage=stage,error_code=str(error) if isinstance(error,DemoError) else 'SAFE_DIAGNOSTIC_WITHHELD')
        finally:
            if server:server.stop()
            if users:
                report['cleanup_complete']=cleanup_created_users(admin,settings.supabase_url,secret_key,users,run_id)
                if not report['cleanup_complete']:report.update(status='CLEANUP_REQUIRED',cleanup_owner_ids=users)
    path=write_report(report,'browser-live-verification')
    print(json.dumps({'status':report['status'],'stage':report.get('stage'),'report':str(path.relative_to(ROOT)),'cleanup_complete':report['cleanup_complete']}))
    return 0 if report['status']=='PASSED_REAL_UI_RULES_AI_NOT_TESTED' and report['cleanup_complete'] else 1


if __name__=='__main__':raise SystemExit(main())
