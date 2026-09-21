"""Build a clearly labelled UI-only inventory from supplied INPUT originals."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import Counter
import hashlib, json, shutil, zipfile, xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
INPUT=ROOT/'data/REBUILD_INPUT_v1/REBUILD_INPUT_v1'
UI=ROOT/'docs/ui-review'
stamp=datetime.now(timezone(timedelta(hours=9))).strftime('%Y%m%dT%H%M%S')
backup=ROOT/'ops/checkpoints'/f'{stamp}-before-ui-v6'
backup.mkdir(parents=True)
for name in ['index.html','styles.css','app.js']:
    shutil.copy2(UI/name,backup/name)
for name in ['GOAL.md','ops/GOAL_INPUT.txt','.omx/ultragoal/goals.json']:
    p=ROOT/name
    (backup/(name.replace('/','__')+'.sha256')).write_text(hashlib.sha256(p.read_bytes()).hexdigest())

def title(folder):
    path=folder/'01_Project_Brief_and_Lessons.docx'
    if not path.exists(): return folder.name
    with zipfile.ZipFile(path) as z:
        tree=ET.fromstring(z.read('word/document.xml'))
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        first=tree.find('.//w:body/w:p',ns)
        text=''.join(first.itertext())
    return text.replace(' 준공 및 교훈 보고서','').replace(' 사업 개요 및 입찰 안내','').replace(' 입찰자 안내','')

projects=[]
for category,kind in [('01_PAST_PROJECTS','past'),('02_NEW_PROJECTS','new')]:
    for folder in sorted((INPUT/category).iterdir()):
        if not folder.is_dir(): continue
        files=[{'name':p.name,'type':p.suffix[1:].upper(),'size':p.stat().st_size} for p in sorted(folder.iterdir()) if p.is_file()]
        projects.append({'id':folder.name.split('_')[0],'name':title(folder),'kind':kind,'folder':str(folder.relative_to(ROOT)).replace('\\','/'),'files':files,'count':len(files)})
templates=[]
labels={'ITB_Analysis_Template.xlsx':('ITB 분석표','itb','주요정보 · 조건 비교 · 적용성 판단'), 'Risk_Register_Template.xlsx':('Risk Register','risk','위험 · 강도 · 대응 · 검토 상태'), 'Review_Deck_Template.pptx':('심의장표','slides','사업 개요부터 의사결정까지 5장'), 'Contract_Review_Template.docx':('계약 검토서','contract','계약 조건 · 검토 의견'), 'Custom_Committee_OnePager.docx':('심의 요약서','onepager','핵심 쟁점 · 의사결정 요약'), 'Lessons_Learned_Template.docx':('교훈 정리서','lessons','사건 · 대응 · 재사용 조건'), 'Project_Comparison_Template.xlsx':('프로젝트 비교표','comparison','과거와 신규 프로젝트의 조건 비교')}
(UI/'templates').mkdir(exist_ok=True)
for p in sorted((INPUT/'03_OUTPUT_TEMPLATES').iterdir()):
    if not p.is_file(): continue
    label,key,desc=labels[p.name]
    shutil.copy2(p,UI/'templates'/p.name)
    templates.append({'name':p.name,'label':label,'key':key,'description':desc,'size':p.stat().st_size,'url':'templates/'+p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
for kind,prefix,names in [('01_PAST_PROJECTS','P01',['01_Project_Brief_and_Lessons.docx','02_ITB_and_Contract_Rev00.pdf']),('02_NEW_PROJECTS','N01',['01_Project_Brief_and_Lessons.docx','02_ITB_and_Contract_Rev00.pdf','11_Addendum_Rev01.pdf','11_Addendum_Rev02.pdf'])]:
    folder=next((INPUT/kind).glob(prefix+'_*'))
    for name in names:
        shutil.copy2(folder/name,UI/'sources'/f'{prefix}_{name}')
assets=UI/'assets'
assets.mkdir(exist_ok=True)
shutil.copy2(ROOT/'tools/web/node_modules/pretendard/dist/web/variable/woff2/PretendardVariable.woff2',assets/'PretendardVariable.woff2')
shutil.copy2(ROOT/'tools/web/node_modules/pretendard/README.md',assets/'Pretendard-README.md')
shutil.copy2(ROOT/'tools/web/node_modules/pretendard/dist/LICENSE.txt',assets/'Pretendard-LICENSE.txt')
inventory={'scope':'UI_PREVIEW_INPUT_INVENTORY_NOT_SUPABASE_REGISTRATION','checkedAt':datetime.now(timezone(timedelta(hours=9))).isoformat(),'projects':projects,'pastCount':sum(p['count'] for p in projects if p['kind']=='past'),'newCount':sum(p['count'] for p in projects if p['kind']=='new'),'types':dict(Counter(f['type'] for p in projects if p['kind']=='past' for f in p['files'])),'templates':templates,'templateRoot':'data/REBUILD_INPUT_v1/REBUILD_INPUT_v1/03_OUTPUT_TEMPLATES'}
(UI/'inventory.js').write_text('window.UI_INVENTORY = '+json.dumps(inventory,ensure_ascii=False,indent=2)+';\n',encoding='utf-8')
(ROOT/'ops/preflight/ui-v6-preparation.json').write_text(json.dumps({'backup':str(backup.relative_to(ROOT)), 'inventory':{k:inventory[k] for k in ['pastCount','newCount','types','checkedAt']},'font':{'package':'pretendard','version':'1.3.9','license':'OFL-1.1','upstream':'https://github.com/orioncactus/pretendard'},'goal_modified':False},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'past_projects':sum(p['kind']=='past' for p in projects),'past_files':inventory['pastCount'],'new_files':inventory['newCount'],'templates':len(templates),'backup':str(backup)},ensure_ascii=False))
