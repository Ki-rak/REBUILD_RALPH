
'use strict';
const {chromium,request}=require('../../tools/web/node_modules/playwright');
const {expect}=require('../../tools/web/node_modules/playwright/test');
const fs=require('fs'),crypto=require('crypto');
const {base,verifyFixture}=require('./fixture_target.cjs');
const report={boundary:'TEST_STORAGE_INJECTED',scenario:'390px mobile fresh upload source review approval and download',started:new Date().toISOString(),checks:[],errors:[]};
const check=(name,detail)=>report.checks.push({name,status:'PASS',detail});
(async()=>{
 const api=await request.newContext({baseURL:base,extraHTTPHeaders:{Authorization:'Bearer browser-alice'}});
 await verifyFixture(api,report);
 const browser=await chromium.launch({headless:true}),context=await browser.newContext({viewport:{width:390,height:844}}),page=await context.newPage();
 page.on('pageerror',e=>report.errors.push(e.message));
 async function fit(stage){const size=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth,overflow:[...document.querySelectorAll('#main *')].filter(el=>{const r=el.getBoundingClientRect();return (r.right>innerWidth+1||el.scrollWidth>el.clientWidth+1)&&!el.closest('.table-wrap')}).slice(0,12).map(el=>({tag:el.tagName,class:el.className,text:el.textContent.slice(0,150),right:el.getBoundingClientRect().right,width:el.getBoundingClientRect().width,scroll:el.scrollWidth}))}));report.lastLayout={stage,...size};expect(size.document).toBeLessThanOrEqual(size.viewport+1);check(stage+' fits mobile document width',size)}
 try{
  const marker=crypto.randomUUID(),name='Mobile '+marker,text='Notice period: 23 calendar days. Employer: Mobile fresh upload '+marker;
  await page.goto(base);await page.getByLabel('이메일',{exact:true}).fill('browser-alice@example.invalid');await page.getByLabel('비밀번호',{exact:true}).fill('synthetic-test-only');await page.getByRole('button',{name:'로그인',exact:true}).click();
  await page.getByRole('button',{name:'새 프로젝트',exact:true}).click();await page.getByLabel('프로젝트 이름',{exact:true}).fill(name);await page.locator('#modal-files').setInputFiles({name:'mobile-fresh.txt',mimeType:'text/plain',buffer:Buffer.from(text)});await fit('Project upload dialog');await page.getByRole('button',{name:'프로젝트 생성',exact:true}).click();await expect(page.getByRole('heading',{name,exact:true})).toBeVisible();await expect(page.getByRole('cell',{name:'mobile-fresh.txt',exact:true})).toBeVisible();await fit('Uploaded project');
  await page.locator('[data-action=new-draft][data-kind=itb]').click();await page.getByRole('button',{name:'초안 생성',exact:true}).click();await expect(page.locator('#draft-form')).toBeVisible();await expect(page.locator('#draft-form textarea[name=current]').first()).toHaveValue(/23 calendar days/);await fit('Draft review');
  const sourceOpened=context.waitForEvent('page');await page.locator('#draft-form [data-action=source-original]').first().click();const source=await sourceOpened;await expect(source.locator('body')).toContainText('23 calendar days');await source.close();check('Original source opens from draft evidence on mobile');
  await page.getByLabel('1번 판단 근거',{exact:true}).fill('Mobile reviewer checked source '+marker);await expect(page.locator('[data-action=approve-draft]')).toBeDisabled();await expect(page.locator('[data-action=export-draft]')).toBeDisabled();await page.locator('[data-action=save-draft]').click();await expect(page.getByRole('heading',{name:'ITB 분석표 · Rev 2',exact:true})).toBeVisible();check('Mobile edit saves a real revision and prevents unsaved approval');
  await page.locator('[data-action=approve-draft]').click();await fit('Approval dialog');await page.locator('#approval-check').check();await page.getByRole('button',{name:'최종 승인',exact:true}).click();await expect(page.locator('[data-action=export-draft]')).toBeEnabled();
  const downloading=page.waitForEvent('download');await page.locator('[data-action=export-draft]').click();const downloaded=await downloading,file='ops/runtime/browser-mobile-result-'+marker+'.xlsx';await downloaded.saveAs(file);const bytes=fs.readFileSync(file);expect(bytes.length).toBeGreaterThan(1000);expect(bytes.subarray(0,2).toString()).toBe('PK');check('Mobile approved XLSX download',file);
  await page.screenshot({path:'ops/runtime/browser-mobile-core-'+marker+'.png',fullPage:true});await fit('Approved result');expect(report.errors).toEqual([]);check('No browser JavaScript errors');
 }catch(e){report.failure=e.stack;process.exitCode=1;}
 finally{report.finished=new Date().toISOString();const file='ops/runtime/browser-mobile-core-'+report.started.replace(/[:.]/g,'-')+'.json';fs.writeFileSync(file,JSON.stringify(report,null,2));console.log(JSON.stringify({...report,evidence:file},null,2));await browser.close();await api.dispose();}
})().catch(e=>{report.failure=e.stack;report.finished=new Date().toISOString();fs.writeFileSync('ops/runtime/browser-mobile-core-startup-'+report.started.replace(/[:.]/g,'-')+'.json',JSON.stringify(report,null,2));console.error(e);process.exitCode=1});

