
'use strict';
const {chromium,request}=require('../../tools/web/node_modules/playwright');
const {expect}=require('../../tools/web/node_modules/playwright/test');
const fs=require('fs'),crypto=require('crypto');
const {base,verifyFixture}=require('./fixture_target.cjs');
const report={boundary:'TEST_STORAGE_INJECTED',scenario:'Editable deferred profiles and project provider selection',started:new Date().toISOString(),checks:[],errors:[]};
const check=name=>report.checks.push({name,status:'PASS'});
(async()=>{
 const api=await request.newContext({baseURL:base,extraHTTPHeaders:{Authorization:'Bearer browser-alice'}});
 await verifyFixture(api,report);
 const browser=await chromium.launch({headless:true}),page=await browser.newPage();
 page.on('pageerror',e=>report.errors.push(e.message));
 let corporateRequests=0;
 page.on('request',r=>{if(r.url().includes('company.example'))corporateRequests++});
 try{
  const marker=crypto.randomUUID(),name='Provider '+marker;
  await page.goto(base);await page.getByLabel('이메일',{exact:true}).fill('browser-alice@example.invalid');await page.getByLabel('비밀번호',{exact:true}).fill('synthetic-test-only');await page.getByRole('button',{name:'로그인',exact:true}).click();
  await page.getByRole('button',{name:'새 프로젝트',exact:true}).click();await page.getByLabel('프로젝트 이름',{exact:true}).fill(name);await page.locator('#modal-files').setInputFiles({name:'provider.txt',mimeType:'text/plain',buffer:Buffer.from('Notice period: 17 days. '+marker)});await page.getByRole('button',{name:'프로젝트 생성',exact:true}).click();await expect(page.getByRole('heading',{name,exact:true})).toBeVisible();
  const projects=await(await api.get('/api/projects')).json(),pid=projects.find(p=>p.name===name).id;
  await page.getByRole('button',{name:'설정',exact:true}).click();await expect(page.getByLabel('설정 대상 프로젝트')).toHaveValue(pid);
  const form=page.locator('.settings-profile-form').filter({has:page.getByRole('heading',{name:'사내 LLM 구성',exact:true})});
  await form.getByLabel('표시 이름',{exact:true}).fill('Deferred LLM '+marker);await form.getByLabel('HTTPS Endpoint',{exact:true}).fill('https://llm.company.example/v1');await form.getByLabel('모델',{exact:true}).fill('first-model');await form.getByRole('button',{name:'비밀값 없이 저장',exact:true}).click();
  const entry=page.locator('.source-ref').filter({hasText:'Deferred LLM '+marker});await expect(entry).toBeVisible();
  const initial=(await(await api.get('/api/settings/profiles')).json()).find(p=>p.name==='Deferred LLM '+marker);expect(initial.status).toBe('NOT_CONFIGURED');check('New metadata-only LLM profile saved');
  await entry.getByRole('button',{name:'프로필 수정'}).click();const dialog=page.getByRole('dialog');await dialog.getByLabel('표시 이름',{exact:true}).fill('Edited LLM '+marker);await dialog.getByLabel('모델',{exact:true}).fill('second-model');await dialog.getByRole('button',{name:'수정 저장',exact:true}).click();await expect(dialog).toHaveCount(0);
  const edited=(await(await api.get('/api/settings/profiles')).json()).find(p=>p.id===initial.id);expect(edited.name).toBe('Edited LLM '+marker);expect(edited.model).toBe('second-model');expect(edited.version).toBeGreaterThan(initial.version);check('Edit updates the same profile ID and advances version');
  await page.getByLabel('사용할 AI 구성').selectOption(initial.id);await page.getByRole('button',{name:'프로젝트 AI 구성 저장',exact:true}).click();await expect(page.locator('#project-provider-form')).toContainText('AI 호출은 차단');await page.reload();await expect(page.getByLabel('사용할 AI 구성')).toHaveValue(initial.id);check('Project selection persists after page reload');
  await page.route('**/api/provider/status',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({connected:true,inference:'SUCCEEDED',provider:'OpenAI',environment:'local'})}));
  await page.getByRole('button',{name:'지식조회',exact:true}).click();await page.getByRole('tab',{name:'AI Insight Mode',exact:true}).click();await expect(page.locator('#main')).toContainText('Edited LLM '+marker);await expect(page.locator('#main')).toContainText('자동 전환하지 않습니다');
  await page.getByLabel('질문 또는 확인할 조건',{exact:true}).fill('Notice period');
  const response=page.waitForResponse(r=>r.url().endsWith('/analyze'));await page.getByRole('button',{name:'적용 검토 실행',exact:true}).click();expect((await response).status()).toBe(503);await expect(page.locator('#query-results')).toContainText('PROFILE_NOT_CONNECTED');check('Selected unconnected profile overrides global connected status and fails honestly');
  await page.unroute('**/api/provider/status');await page.getByRole('button',{name:'설정',exact:true}).click();await page.getByLabel('사용할 AI 구성').selectOption('');await page.getByRole('button',{name:'프로젝트 AI 구성 저장',exact:true}).click();await expect(page.locator('#project-provider-form')).toContainText('기본 OpenAI를 사용하도록');await page.reload();await expect(page.getByLabel('사용할 AI 구성')).toHaveValue('');
  const selection=await(await api.get('/api/projects/'+pid+'/provider')).json();expect(selection.selected_profile).toBeNull();expect(selection.status).toBe('ENVIRONMENT_DEFAULT');check('Clearing saved selection restores explicit environment default and persists');
  expect(corporateRequests).toBe(0);expect(report.errors).toEqual([]);check('No corporate endpoint requests or browser errors');
 }catch(e){report.failure=e.stack;process.exitCode=1;}
 finally{report.finished=new Date().toISOString();const file='ops/runtime/browser-provider-profiles-'+report.started.replace(/[:.]/g,'-')+'.json';fs.writeFileSync(file,JSON.stringify(report,null,2));console.log(JSON.stringify({...report,evidence:file},null,2));await browser.close();await api.dispose();}
})().catch(e=>{report.failure=e.stack;report.finished=new Date().toISOString();fs.writeFileSync('ops/runtime/browser-provider-profiles-startup-'+report.started.replace(/[:.]/g,'-')+'.json',JSON.stringify(report,null,2));console.error(e);process.exitCode=1});

