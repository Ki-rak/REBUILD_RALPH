'use strict';
// Credentials arrive only over inherited stdin, never command arguments or reports.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const ROOT=path.resolve(__dirname,'..'),INPUT=path.join(ROOT,'data/REBUILD_INPUT_v1/REBUILD_INPUT_v1');
const hash=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
function validateTarget(config){
 const url=new URL(config.base);
 assert(url.protocol==='http:' && ['localhost','127.0.0.1','[::1]'].includes(url.hostname) && !url.username && !url.password && url.pathname==='/' && !url.search && !url.hash,'LOOPBACK_REQUIRED');
 assert(typeof config.run_id==='string' && /^[a-zA-Z0-9-]{16,64}$/.test(config.run_id),'RUN_ID_REQUIRED');
 return url.origin;
}
function verifyIdentity(actual,runId){assert.deepEqual(actual,{run_id:runId,boundary:'REAL_SUPABASE_USER_JWT',product:'RE:Build Agent'},'REAL_SERVER_IDENTITY_REQUIRED')}
function verifyDocumentCoverage(selected,docs){
 const hashes=[...new Set(selected.files.map(x=>x.sha256))].sort();
 assert.deepEqual(docs.map(x=>x.sha256).sort(),hashes,'UNIQUE_SOURCE_COVERAGE_MISMATCH');
 for(const item of selected.files){const doc=docs.find(x=>x.sha256===item.sha256);assert(doc?.aliases?.includes(item.name),'SOURCE_ALIAS_MISSING');assert.equal(doc.extraction_status,'EXTRACTED')}
}
const SAFE_PRODUCT_CODES=new Set(['SERVICE_UNAVAILABLE','VERSION_CONFLICT','DRAFT_STALE','APPROVAL_REQUIRED','ORIGINAL_HASH_MISMATCH','EVIDENCE_INTEGRITY_FAILED','APPROVAL_INTEGRITY_FAILED','SLIDE_CONTENT_TOO_LONG','SLIDE_TITLE_TOO_LONG','INVALID_REQUEST','NOT_FOUND','SESSION_INVALID','AUTH_REQUIRED','SOURCE_REF_INVALID','SOURCE_QUOTE_MISMATCH','EVIDENCE_REQUIRED','INPUT_INTEGRITY_FAILED']);
async function requireProductResponse(response,action,diagnostics){
 assert(['LOGIN','AUTH_ME','CONFIG','CREATE','SAVE','APPROVE','EXPORT'].includes(action),'DIAGNOSTIC_ACTION_REQUIRED');
 const status=response.status();assert(Number.isInteger(status)&&status>=100&&status<=599,'INVALID_HTTP_STATUS');
 let code=null;if(status<200||status>=300){try{const candidate=(await response.json())?.detail?.code;code=SAFE_PRODUCT_CODES.has(candidate)?candidate:'UNRECOGNIZED_PRODUCT_ERROR'}catch{code='UNRECOGNIZED_PRODUCT_ERROR'}}
 diagnostics.push({action,http_status:status,detail_code:code});
 if(status<200||status>=300)throw Object.assign(new Error('PRODUCT_REQUEST_FAILED'),{safeCode:`PRODUCT_${action}_HTTP_${status}`});
 return response;
}
async function run(config){
 const {chromium,request}=require('../tools/web/node_modules/playwright');
 const expect=require('../tools/web/node_modules/playwright/test').expect.configure({timeout:180000});
 const base=validateTarget(config),out=path.resolve(config.output_dir);
 assert(out.startsWith(path.join(ROOT,'ops/runtime/demo')+path.sep),'REPORT_DIRECTORY_REQUIRED');
 assert(['initial','resume'].includes(config.phase),'PHASE_REQUIRED');assert(!config.kinds||(Array.isArray(config.kinds)&&config.kinds.length&&config.kinds.every(kind=>['itb','risk','slides'].includes(kind))),'KINDS_REQUIRED');
 fs.mkdirSync(out,{recursive:true});
 const report={product:'RE:Build Agent',boundary:'REAL_SUPABASE_BROWSER',run_id:config.run_id,phase:config.phase,checks:[],responses:[],projects:[],documents:[],historical_documents:[],drafts:[],status:'RUNNING',ai_verified:false,product_complete:false};
 let browser,page,stage='identity',deadlineExpired=false;
 const deadline=setTimeout(()=>{deadlineExpired=true;if(browser)browser.close().catch(()=>{})},2400000);
 const check=(name,details={})=>report.checks.push({name,passed:true,...details});
 const probe=await request.newContext({baseURL:base,timeout:20000});
 try{
  const identity=await probe.get('/__rebuild_live_verify_identity',{maxRedirects:0});assert.equal(identity.status(),200);assert.equal(new URL(identity.url()).origin,base);verifyIdentity(await identity.json(),config.run_id);
  // Separate, owned browser; no user's saved profile, cookies or OAuth access.
  browser=await chromium.launch({headless:false});page=await browser.newPage({viewport:{width:1440,height:1000}});page.setDefaultTimeout(180000);
  let pageErrors=0;page.on('pageerror',()=>pageErrors++);
  stage='ui_login';await page.goto(base);assert.equal(new URL(page.url()).origin,base,'LOGIN_ORIGIN_CHANGED');await page.getByLabel('이메일',{exact:true}).fill(config.email);await page.getByLabel('비밀번호',{exact:true}).fill(config.password);
  const loginResponse=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/auth/login'&&r.request().method()==='POST');const bootstrapResponses=Promise.all(['/api/auth/me','/api/config'].map(route=>page.waitForResponse(r=>new URL(r.url()).pathname===route).then(r=>requireProductResponse(r,route.endsWith('/me')?'AUTH_ME':'CONFIG',report.responses)))).then(()=>({ok:true}),()=>({ok:false}));await page.getByRole('button',{name:'로그인',exact:true}).click();await requireProductResponse(await loginResponse,'LOGIN',report.responses);assert((await bootstrapResponses).ok,'BOOTSTRAP_API_FAILED');await expect(page.getByRole('button',{name:'새 프로젝트',exact:true})).toBeVisible();check('real_ui_login');
  const api=route=>page.evaluate(async route=>{
   const response=await fetch(route,{headers:{Authorization:'Bearer '+sessionStorage.getItem('rebuild_access_token')}});
   if(!response.ok)throw Error('READ_API_HTTP_'+response.status);return response.json();
  },route);
  for(const selected of config.projects){
   stage=selected.code+'_open';
   if(await page.locator('[data-action=switch-project]').count())await page.locator('[data-action=switch-project]').click();
   await page.getByRole('button',{name:'프로젝트',exact:true}).click();
   let pid;
   if(config.phase==='initial'){
    const existing=new Set();for(const prior of await api('/api/projects'))for(const doc of await api(`/api/projects/${prior.id}/documents`))existing.add(doc.sha256);
    const primary=selected.files.find(x=>x.name==='02_ITB_and_Contract_Rev00.pdf');assert(primary && !existing.has(primary.sha256),'NEW_CONTRACT_ALREADY_PRESENT');
    const files=selected.files.map(item=>{const absolute=path.resolve(INPUT,item.path);assert(item.path.startsWith('02_NEW_PROJECTS/')&&absolute.startsWith(INPUT+path.sep),'INPUT_PATH_REJECTED');assert.equal(hash(fs.readFileSync(absolute)),item.sha256,'SOURCE_CHANGED');return absolute});
    check('new_input_hash_absence',{project:selected.code,fresh_hashes:new Set(selected.files.filter(x=>!existing.has(x.sha256)).map(x=>x.sha256)).size});
    stage=selected.code+'_ui_upload';await page.getByRole('button',{name:'새 프로젝트',exact:true}).click();await page.getByLabel('프로젝트 이름',{exact:true}).fill(selected.name);await page.locator('#modal-files').setInputFiles(files);await page.getByRole('button',{name:'프로젝트 생성',exact:true}).click();
    await expect(page.getByRole('heading',{name:selected.name,exact:true})).toBeVisible();
    pid=(await api('/api/projects')).find(x=>x.name===selected.name).id;
    const docs=await api(`/api/projects/${pid}/documents`);verifyDocumentCoverage(selected,docs);
    for(const doc of docs){const knowledge=await api(`/api/documents/${doc.id}/knowledge`);assert(knowledge.markdown&&knowledge.blocks.length&&knowledge.sidecars);report.documents.push({id:doc.id,sha256:doc.sha256,sidecars:knowledge.sidecars})}
    check('ui_uploaded_originals_extracted',{project:selected.code,input_files:selected.files.length,unique_documents:docs.length});
   }else{
    pid=(await api('/api/projects')).find(x=>x.name===selected.name).id;
    await page.locator(`[data-action=open-project][data-id="${pid}"]`).click();await expect(page.getByRole('heading',{name:selected.name,exact:true})).toBeVisible();
   }
   report.projects.push(pid);
   if(config.phase==='initial'){
    stage=selected.code+'_evidence';const graph=await api(`/api/projects/${pid}/knowledge`);
    const linked=graph.comparisons.find(x=>x.current_refs?.length&&x.historical_refs?.length);assert(linked,'PAST_NEW_LINK_MISSING');
    if(selected.code==='N01'){const notice=graph.comparisons.find(x=>x.id==='notice');assert(notice.current.includes('14 calendar days')&&!notice.current.includes('7 calendar days'),'APPROVED_NOTICE_MISSING')}
    await page.getByRole('button',{name:'지식 자료실',exact:true}).click();await page.locator(`[data-action=select-comparison][data-row-id="${linked.id}"]`).click();await expect(page.locator('.comparison-side')).toHaveCount(2);
    const source=graph.nodes.find(x=>x.type==='document'&&report.documents.some(d=>d.id===x.document_id));assert(source);
    await page.locator(`[data-action=graph-document][data-id="${source.document_id}"]`).first().click();await expect(page.getByRole('dialog')).toContainText(report.documents.find(x=>x.id===source.document_id).sha256);
    await page.getByRole('button',{name:'닫기',exact:true}).last().click();
    await page.screenshot({path:path.join(out,selected.code+'-knowledge.png'),fullPage:true});check('real_graph_and_both_source_panels',{project:selected.code});
    await page.getByRole('button',{name:'프로젝트',exact:true}).click();
   }
   for(const kind of config.kinds||['itb','risk','slides']){
    stage=selected.code+'_'+kind+'_'+config.phase;
    let saved;
    if(config.phase==='initial'){
     const title={itb:'ITB 분석표',risk:'Risk Register',slides:'심의장표'}[kind];
     await page.locator(`[data-action=new-draft][data-kind=${kind}]`).click();
     const createdResponse=page.waitForResponse(r=>new URL(r.url()).pathname===`/api/projects/${pid}/drafts`&&r.request().method()==='POST');
     await page.getByRole('button',{name:'초안 생성',exact:true}).click();
     const created=await(await requireProductResponse(await createdResponse,'CREATE',report.responses)).json();
     assert.equal(created.kind,kind);assert.equal(created.revision,1);assert(/^[a-f0-9-]{36}$/.test(created.id),'DRAFT_ID_REQUIRED');
     await expect(page.getByRole('heading',{name:title+' · Rev 1',exact:true})).toBeVisible();await expect(page.locator('[data-action=export-draft]')).toBeDisabled();
     const label=kind==='slides'?'1번 슬라이드 제목':kind==='risk'?'1번 대응':'1번 판단 근거';const value=kind==='slides'?'프로젝트 개요 검토':'격리 시험 계정: 제공된 원문 근거를 확인했습니다.';
     await page.getByLabel(label,{exact:true}).fill(value);await expect(page.locator('[data-action=approve-draft]')).toBeDisabled();
     const savedResponse=page.waitForResponse(r=>new URL(r.url()).pathname===`/api/drafts/${created.id}`&&r.request().method()==='PATCH');
     await page.locator('[data-action=save-draft]').click();const edited=await(await requireProductResponse(await savedResponse,'SAVE',report.responses)).json();
     assert.equal(edited.id,created.id);assert.equal(edited.kind,kind);assert.equal(edited.revision,2);
     await expect(page.getByRole('heading',{name:title+' · Rev 2',exact:true})).toBeVisible();await expect(page.getByLabel(label,{exact:true})).toHaveValue(value);
     stage=selected.code+'_'+kind+'_'+config.phase+'_approve';
     await page.locator('[data-action=approve-draft]').click();await page.locator('#approval-check').check();
     const approvalResponse=page.waitForResponse(r=>new URL(r.url()).pathname===`/api/drafts/${created.id}/approve`&&r.request().method()==='POST');
     await page.getByRole('button',{name:'최종 승인',exact:true}).click();
     const approval=await approvalResponse;try{saved=await(await requireProductResponse(approval,'APPROVE',report.responses)).json()}catch(error){let stored=null;try{stored=await api(`/api/drafts/${created.id}`)}catch{}report.approval_failure_state={read_succeeded:Boolean(stored),status:['draft','approved'].includes(stored?.status)?stored.status:null,revision:Number.isInteger(stored?.revision)?stored.revision:null};throw error}
     assert.equal(saved.id,created.id);assert.equal(saved.kind,kind);assert.equal(saved.revision,2);assert.equal(saved.status,'approved');
     await expect(page.getByRole('heading',{name:title+' · Rev 2',exact:true})).toBeVisible();await expect(page.locator('[data-action=export-draft]')).toBeEnabled();
    }else{
     saved=config.snapshot.drafts.find(x=>x.project_id===pid&&x.kind===kind);assert(saved);
     await page.locator(`[data-action=open-draft][data-id="${saved.id}"]`).click();await expect(page.getByRole('heading',{name:({itb:'ITB 분석표',risk:'Risk Register',slides:'심의장표'}[kind])+' · Rev 2',exact:true})).toBeVisible();await expect(page.locator('[data-action=export-draft]')).toBeEnabled();
     const current=await api(`/api/drafts/${saved.id}`);for(const key of ['revision','approval_id','input_fingerprint'])assert.equal(current[key],saved[key]);
    }
    stage=selected.code+'_'+kind+'_'+config.phase+'_export';
    const download=page.waitForEvent('download').then(event=>({event}),error=>({error}));
    const exportResponse=page.waitForResponse(response=>new URL(response.url()).pathname===`/api/drafts/${saved.id}/export`&&response.request().method()==='POST');
    await page.locator('[data-action=export-draft]').click();const response=await exportResponse;
    await requireProductResponse(response,'EXPORT',report.responses);
    const result=await download;if(result.error)throw result.error;
    const target=path.join(out,`${selected.code}-${kind}-${config.phase}.${kind==='slides'?'pptx':'xlsx'}`);await result.event.saveAs(target);
    report.drafts.push({id:saved.id,project_id:pid,kind,revision:saved.revision,approval_id:saved.approval_id,input_fingerprint:saved.input_fingerprint,path:target,file_sha256:hash(fs.readFileSync(target))});check('ui_review_approval_download',{project:selected.code,kind,phase:config.phase});
   }
  }
  stage='management_templates_mobile';await page.getByRole('button',{name:'데이터 관리',exact:true}).click();await expect(page.locator('.stats')).toContainText('과거 보유 문서');
  await page.getByRole('button',{name:'표준 양식',exact:true}).click();await expect(page.locator('[data-action=template-original]')).toHaveCount(7);
  await page.setViewportSize({width:390,height:844});const widths=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));assert(widths.scroll<=widths.width+1,'MOBILE_OVERFLOW');await page.screenshot({path:path.join(out,'mobile-'+config.phase+'.png'),fullPage:true});check('real_account_management_templates_mobile');
  stage='logout';await page.getByRole('button',{name:'로그아웃',exact:true}).click();await expect(page.getByRole('heading',{name:'워크스페이스 로그인',exact:true})).toBeVisible();assert.equal(pageErrors,0);check('ui_logout_no_page_errors');report.status='PASSED';
 }catch(error){if(page&&stage==='ui_login')report.login_state={shell_visible:await page.locator('.app-shell').isVisible().catch(()=>false),login_visible:await page.locator('#login-form').isVisible().catch(()=>false),error_visible:await page.locator('.form-error').isVisible().catch(()=>false),new_project_buttons:await page.locator('[data-action=new-project]').count().catch(()=>0)};report.status='FAILED';report.stage=stage;report.error_type=error.name||'Error';report.error_code=deadlineExpired?'WORKFLOW_TIME_BUDGET_EXCEEDED':/^PRODUCT_(?:LOGIN|AUTH_ME|CONFIG|CREATE|SAVE|APPROVE|EXPORT)_HTTP_[0-9]{3}$/.test(error.safeCode||'')?error.safeCode:'UI_ASSERTION_FAILED';report.assertion=error.matcherResult?.name||null;report.timeout_ms=Number(error.message?.match(/(?:Timeout|timeout) (\d+)ms/)?.[1])||null;if(page&&stage!=='ui_login')await page.screenshot({path:path.join(out,'failure-'+config.phase+'.png'),fullPage:true}).catch(()=>{});}
 finally{clearTimeout(deadline);if(browser)await browser.close();await probe.dispose();fs.writeFileSync(path.join(out,'browser-'+config.phase+'.json'),JSON.stringify(report,null,2));}
 console.log(JSON.stringify({status:report.status,phase:report.phase,stage:report.stage,checks:report.checks.length}));return report.status==='PASSED'?0:1;
}
module.exports={validateTarget,verifyIdentity,verifyDocumentCoverage,requireProductResponse};
if(require.main===module){run(JSON.parse(fs.readFileSync(0,'utf8'))).then(code=>{process.exitCode=code}).catch(()=>{console.error('LIVE_BROWSER_RUN_FAILED_SAFE');process.exitCode=1})}
