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
async function run(config){
 const {chromium,request}=require('../tools/web/node_modules/playwright');
 const expect=require('../tools/web/node_modules/playwright/test').expect.configure({timeout:180000});
 const base=validateTarget(config),out=path.resolve(config.output_dir);
 assert(out.startsWith(path.join(ROOT,'ops/runtime/demo')+path.sep),'REPORT_DIRECTORY_REQUIRED');
 assert(['initial','resume'].includes(config.phase),'PHASE_REQUIRED');
 fs.mkdirSync(out,{recursive:true});
 const report={product:'RE:Build Agent',boundary:'REAL_SUPABASE_BROWSER',run_id:config.run_id,phase:config.phase,checks:[],projects:[],documents:[],historical_documents:[],drafts:[],status:'RUNNING',ai_verified:false,product_complete:false};
 let browser,page,stage='identity';
 const deadline=setTimeout(()=>{if(browser)browser.close().catch(()=>{})},900000);
 const check=(name,details={})=>report.checks.push({name,passed:true,...details});
 const probe=await request.newContext({baseURL:base,timeout:20000});
 try{
  const identity=await probe.get('/__rebuild_live_verify_identity',{maxRedirects:0});assert.equal(identity.status(),200);assert.equal(new URL(identity.url()).origin,base);verifyIdentity(await identity.json(),config.run_id);
  // Separate, owned browser; no user's saved profile, cookies or OAuth access.
  browser=await chromium.launch({headless:false});page=await browser.newPage({viewport:{width:1440,height:1000}});page.setDefaultTimeout(180000);
  let pageErrors=0;page.on('pageerror',()=>pageErrors++);
  stage='ui_login';await page.goto(base);assert.equal(new URL(page.url()).origin,base,'LOGIN_ORIGIN_CHANGED');await page.getByLabel('이메일',{exact:true}).fill(config.email);await page.getByLabel('비밀번호',{exact:true}).fill(config.password);
  await page.getByRole('button',{name:'로그인',exact:true}).click();await expect(page.getByRole('button',{name:'새 프로젝트',exact:true})).toBeVisible();check('real_ui_login');
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
   for(const kind of ['itb','risk','slides']){
    stage=selected.code+'_'+kind+'_'+config.phase;
    let saved;
    if(config.phase==='initial'){
     await page.locator(`[data-action=new-draft][data-kind=${kind}]`).click();await page.getByRole('button',{name:'초안 생성',exact:true}).click();await expect(page.locator('#draft-form')).toBeVisible();await expect(page.locator('[data-action=export-draft]')).toBeDisabled();
     const label=kind==='slides'?'1번 슬라이드 제목':kind==='risk'?'1번 대응':'1번 판단 근거';const value=kind==='slides'?'프로젝트 개요 검토':'격리 시험 계정: 제공된 원문 근거를 확인했습니다.';
     await page.getByLabel(label,{exact:true}).fill(value);await expect(page.locator('[data-action=approve-draft]')).toBeDisabled();await page.locator('[data-action=save-draft]').click();await expect(page.getByRole('heading',{name:/ · Rev 2$/})).toBeVisible();await expect(page.getByLabel(label,{exact:true})).toHaveValue(value);
     await page.locator('[data-action=approve-draft]').click();await page.locator('#approval-check').check();await page.getByRole('button',{name:'최종 승인',exact:true}).click();await expect(page.locator('[data-action=export-draft]')).toBeEnabled();
     saved=(await api(`/api/projects/${pid}/drafts`)).find(x=>x.kind===kind&&x.status==='approved');assert(saved);
    }else{
     saved=config.snapshot.drafts.find(x=>x.project_id===pid&&x.kind===kind);assert(saved);
     await page.locator(`[data-action=open-draft][data-id="${saved.id}"]`).click();await expect(page.getByRole('heading',{name:/ · Rev 2$/})).toBeVisible();await expect(page.locator('[data-action=export-draft]')).toBeEnabled();
     const current=await api(`/api/drafts/${saved.id}`);for(const key of ['revision','approval_id','input_fingerprint'])assert.equal(current[key],saved[key]);
    }
    const download=page.waitForEvent('download');await page.locator('[data-action=export-draft]').click();const target=path.join(out,`${selected.code}-${kind}-${config.phase}.${kind==='slides'?'pptx':'xlsx'}`);await(await download).saveAs(target);
    report.drafts.push({id:saved.id,project_id:pid,kind,revision:saved.revision,approval_id:saved.approval_id,input_fingerprint:saved.input_fingerprint,path:target,file_sha256:hash(fs.readFileSync(target))});check('ui_review_approval_download',{project:selected.code,kind,phase:config.phase});
   }
  }
  stage='management_templates_mobile';await page.getByRole('button',{name:'데이터 관리',exact:true}).click();await expect(page.locator('.stats')).toContainText('과거 보유 문서');
  await page.getByRole('button',{name:'표준 양식',exact:true}).click();await expect(page.locator('[data-action=template-original]')).toHaveCount(7);
  await page.setViewportSize({width:390,height:844});const widths=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));assert(widths.scroll<=widths.width+1,'MOBILE_OVERFLOW');await page.screenshot({path:path.join(out,'mobile-'+config.phase+'.png'),fullPage:true});check('real_account_management_templates_mobile');
  stage='logout';await page.getByRole('button',{name:'로그아웃',exact:true}).click();await expect(page.getByRole('heading',{name:'워크스페이스 로그인',exact:true})).toBeVisible();assert.equal(pageErrors,0);check('ui_logout_no_page_errors');report.status='PASSED';
 }catch(error){report.status='FAILED';report.stage=stage;report.error_type=error.name||'Error';report.assertion=error.matcherResult?.name||null;report.timeout_ms=Number(error.message?.match(/(?:Timeout|timeout) (\d+)ms/)?.[1])||null;if(page&&stage!=='ui_login')await page.screenshot({path:path.join(out,'failure-'+config.phase+'.png'),fullPage:true}).catch(()=>{});}
 finally{clearTimeout(deadline);if(browser)await browser.close();await probe.dispose();fs.writeFileSync(path.join(out,'browser-'+config.phase+'.json'),JSON.stringify(report,null,2));}
 console.log(JSON.stringify({status:report.status,phase:report.phase,stage:report.stage,checks:report.checks.length}));return report.status==='PASSED'?0:1;
}
module.exports={validateTarget,verifyIdentity,verifyDocumentCoverage};
if(require.main===module){run(JSON.parse(fs.readFileSync(0,'utf8'))).then(code=>{process.exitCode=code}).catch(()=>{console.error('LIVE_BROWSER_RUN_FAILED_SAFE');process.exitCode=1})}
