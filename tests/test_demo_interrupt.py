import importlib
from pathlib import Path
from types import SimpleNamespace
import pytest

@pytest.mark.parametrize('name',['ops.demo_negative_verify','ops.demo_provider_verify'])
def test_interrupted_verifier_records_failed_cleanup_and_owned_ids(monkeypatch,name):
    module=importlib.import_module(name);captured={};creates=[]
    monkeypatch.setattr(module,'load_environment',lambda:None)
    monkeypatch.setattr(module.Settings,'from_environment',lambda:SimpleNamespace(supabase_url='https://example.invalid',publishable_key='test',validate=lambda:None))
    monkeypatch.setenv('SUPABASE_SECRET_KEY','synthetic-test-only')
    monkeypatch.setattr(module.secrets,'token_urlsafe',lambda *args:'synthetic-password-not-a-real-account')
    monkeypatch.setenv('REBUILD_ENV','local')
    monkeypatch.setattr(module,'verify_live',lambda *args:{'status':'PASSED'})
    if name.endswith('provider_verify'):
        monkeypatch.setattr(module,'call_bridge',lambda *args:{'authentication':'LOGGED_IN'})
        monkeypatch.setattr(module.sys,'argv',['test','--environment','deployed'])
    def create(*args):
        creates.append(1)
        if name.endswith('provider_verify') or len(creates)>1:raise KeyboardInterrupt()
        return 'only-created-test-owner'
    if name.endswith('provider_verify'):
        monkeypatch.setattr(module,'catalog',lambda: (_ for _ in ()).throw(KeyboardInterrupt()))
        def create(*args):return 'only-created-test-owner'
    monkeypatch.setattr(module,'_create_test_user',create)
    def cleanup(http,url,key,users,run):
        captured['owners']=users.copy();return False
    monkeypatch.setattr(module,'cleanup_created_users',cleanup)
    def write(report,prefix):captured['report']=report.copy();return module.ROOT/'ops/runtime/demo/not-written.json'
    monkeypatch.setattr(module,'write_report',write)
    try:exit_code=module.main()
    except KeyboardInterrupt:pytest.fail('interruption escaped before durable recovery report')
    assert exit_code==1
    assert captured['report']['status']=='CLEANUP_REQUIRED'
    assert captured['report']['cleanup_owner_ids']==captured['owners']==['only-created-test-owner']
    assert captured['report']['product_complete'] is False
    assert module.os.environ['REBUILD_ENV']=='local'
