"""Demo preparation uses actual INPUT files, not evaluator/preflight knowledge."""
from hashlib import sha256
from pathlib import Path
import pytest
from test_api import flow, auth
from ops.demo import catalog, select_projects, ProductAPI, seed_past, upload_new, validate_url, DemoError

ROOT=Path(__file__).resolve().parents[1]

def test_real_catalog_maps_all_past_and_new_without_evaluator():
    entries=catalog()
    assert len([x for x in entries if x['kind']=='historical'])==15
    assert {x['code'] for x in entries if x['kind']=='current'}=={'N01','N02'}
    for project in entries:
        for file in project['files']:
            assert file['path'].startswith(('01_PAST_PROJECTS/','02_NEW_PROJECTS/'))
            assert 'EVALUATOR' not in file['path'] and 'preflight' not in file['path']
    n01=next(x for x in entries if x['code']=='N01')
    assert any(x['name']=='11_Addendum_Rev02.pdf' for x in n01['files'])

@pytest.mark.parametrize('url',['https://example.com','http://localhost.evil.test','http://u:p@127.0.0.1:8780','http://127.0.0.1:8780/redirect','http://127.0.0.1:8780/?target=evil'])
def test_credentials_only_reach_loopback_product(url):
    with pytest.raises(DemoError):validate_url(url)

def test_selector_rejects_new_files_in_past_seeding():
    with pytest.raises(DemoError):select_projects(catalog(),['N01'],'historical')

def test_unapproved_seed_has_no_side_effects(flow):
    c,records,files=flow
    api=ProductAPI(c,token='alice')
    with pytest.raises(DemoError):seed_past(api,select_projects(catalog(),['P01'],'historical'),approved=False)
    assert not records and not files

def test_seed_uses_import_approval_and_keeps_new_projects_absent_then_real_bytes_upload(flow):
    c,records,files=flow;api=ProductAPI(c,token='alice')
    selected=select_projects(catalog(),['P01'],'historical')
    # Use a bounded actual-source slice; the CLI selection itself retains all files.
    selected[0]['files']=[x for x in selected[0]['files'] if x['name'] in {'01_Project_Brief_and_Lessons.docx','02_ITB_and_Contract_Rev00.pdf','03_Commercial_Risk_Procurement.xlsx'}]
    first=seed_past(api,selected,approved=True)
    again=seed_past(api,selected,approved=True)
    assert first[0]['project_id']==again[0]['project_id']
    assert len(api.json('GET','/api/projects'))==1
    assert len(api.json('GET',f"/api/projects/{first[0]['project_id']}/documents"))==3
    assert any(r['payload'].get('action')=='folder_import_approved' for r in records.values())
    chosen=select_projects(catalog(),['N01'],'current')[0]
    chosen['files']=[x for x in chosen['files'] if x['name'] in {'02_ITB_and_Contract_Rev00.pdf','11_Addendum_Rev01.pdf','11_Addendum_Rev02.pdf'}]
    result=upload_new(api,chosen)
    assert result['fresh_hash_count']==3
    assert len(result['documents'])==3
    for doc in result['documents']:
        original=next(x for x in chosen['files'] if x['sha256']==doc['sha256'])
        assert sha256(files[doc['storage_path']]).hexdigest()==original['sha256']
    analysis=api.json('POST',f"/api/projects/{result['project_id']}/analyze",json={'mode':'rules'})
    notice=next(row for row in analysis['rows'] if row['id']=='notice')
    assert '14 calendar days' in notice['current'] and '7 calendar days' not in notice['current']
    assert notice['historical_refs'] and notice['current_refs']
    with pytest.raises(DemoError,match='NEW_INPUT_ALREADY_PRESENT'):upload_new(api,chosen)

def test_catalog_refuses_symlink_or_non_input_roots(tmp_path):
    with pytest.raises(DemoError):catalog(tmp_path/'REBUILD_EVALUATOR_v1')


@pytest.mark.parametrize('failure',['missing','failed'])
def test_incomplete_past_ingest_never_passes(flow,failure):
    c,records,files=flow
    class FaultyResponse(ProductAPI):
        def json(self,method,path,**kwargs):
            result=super().json(method,path,**kwargs)
            if path=='/api/import/approve':
                if failure=='missing':result['documents']=[]
                else:result['documents'][0]['extraction_status']='FAILED'
            return result
    selected=select_projects(catalog(),['P01'],'historical')
    selected[0]['files']=selected[0]['files'][:1]
    with pytest.raises(DemoError,match='COVERAGE_MISMATCH|EXTRACTION_NOT_COMPLETE'):
        seed_past(FaultyResponse(c,token='alice'),selected,approved=True)


def test_windows_start_pins_local_and_restores_inherited_environment(tmp_path):
    import os,shutil,subprocess,json
    if os.name!='nt':pytest.skip('Windows launcher contract')
    shell=shutil.which('powershell') or shutil.which('pwsh')
    assert shell
    ops=tmp_path/'ops';ops.mkdir()
    shutil.copyfile(ROOT/'ops/demo.ps1',ops/'demo.ps1')
    (ops/'python.ps1').write_text('Write-Output ("CHILD_ENV=" + $env:REBUILD_ENV)\nexit 0\n',encoding='utf-8')
    script=tmp_path/'probe.ps1'
    script.write_text("$env:REBUILD_ENV = 'deployed'\n& $PSScriptRoot/ops/demo.ps1 -Action Start\nWrite-Output (\"PARENT_ENV=\" + $env:REBUILD_ENV)\n",encoding='utf-8')
    result=subprocess.run([shell,'-NoProfile','-File',str(script)],capture_output=True,text=True,timeout=60)
    assert result.returncode==0
    assert 'CHILD_ENV=local' in result.stdout and 'PARENT_ENV=deployed' in result.stdout


def test_reports_never_overwrite_when_clock_ticks_match(monkeypatch,tmp_path):
    import ops.demo as module
    from datetime import datetime,timezone
    from types import SimpleNamespace
    import json
    monkeypatch.setattr(module,'ROOT',tmp_path)
    fixed=datetime(2026,9,22,tzinfo=timezone.utc)
    monkeypatch.setattr(module,'datetime',SimpleNamespace(now=lambda zone:fixed))
    first=module.write_report({'case':'local'},'provider')
    second=module.write_report({'case':'deployed'},'provider')
    assert first!=second
    assert json.loads(first.read_text())['case']=='local'
    assert json.loads(second.read_text())['case']=='deployed'
