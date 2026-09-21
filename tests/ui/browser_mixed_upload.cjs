'use strict';
const {chromium,request}=require('../../tools/web/node_modules/playwright');
const {expect}=require('../../tools/web/node_modules/playwright/test');
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const base='http://127.0.0.1:8782',out=path.resolve('ops/runtime');
const report={boundary:'TEST_STORAGE_INJECTED',scenario:'AR10 mixed valid and corrupt supported upload',started:new Date().toISOString(),checks:[],errors:[]};
const record=(name,detail)=>report.checks.push({name,status:'PASS',detail});
(async()=>{
 const api=await request.newContext({baseURL:base,extraHTTPHeaders:{Authorization:'Bearer browser-alice'}});
 await expect.poll(async()=>{try{return(await api.get('/api/config')).status()}catch{return 0}},{timeout:60000}).toBe(200);
 const browser=await chromium.launch({headless:true}),context=await browser.newContext(),page=await context.newPage();
 page.on('pageerror',e=>report.errors.push(e.message));
 try {
  const marker=crypto.randomUUID(),goodName='fresh-'+marker+'.txt',badName='corrupt-'+marker+'.docx';
  const goodBytes=Buffer.from('Notice period: 31 calendar days.\nFresh mixed-upload marker: '+marker),badBytes=Buffer.from('This is deliberately not an OOXML ZIP archive. '+marker);
  await page.goto(base);await page.getByLabel('이메일',{exact:true}).fill('browser-alice@example.invalid');await page.getByLabel('비밀번호',{exact:true}).fill('synthetic-test-only');await page.getByRole('button',{name:'로그인',exact:true}).click();
  await page.getByRole('button',{name:'새 프로젝트',exact:true}).click();await page.getByLabel('프로젝트 이름',{exact:true}).fill('Mixed upload '+marker);
  await page.locator('#modal-files').setInputFiles([{name:goodName,mimeType:'text/plain',buffer:goodBytes},{name:badName,mimeType:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',buffer:badBytes}]);
  const batch=page.waitForResponse(r=>r.url().includes('/upload')&&r.request().method()==='POST');await page.getByRole('button',{name:'프로젝트 생성',exact:true}).click();const uploaded=await batch;expect(uploaded.status()).toBe(200);const result=await uploaded.json();expect(result.documents).toHaveLength(2);
  const good=result.documents.find(d=>d.filename===goodName),bad=result.documents.find(d=>d.filename===badName);expect(good.id).toBeTruthy();expect(bad.id).toBeTruthy();record('Single mixed batch preserved both original records');
  const goodRow=page.getByRole('row').filter({has:page.getByRole('cell',{name:goodName,exact:true})}),badRow=page.getByRole('row').filter({has:page.getByRole('cell',{name:badName,exact:true})});
  await expect(goodRow).toBeVisible();await expect(badRow).toBeVisible();expect(JSON.stringify(good.blocks)).toContain('31 calendar days');expect(['EXTRACTED','SUCCESS','COMPLETE','COMPLETED','READY']).toContain(good.extraction_status.toUpperCase());record('Valid item extracted and visible despite neighboring corruption',good.extraction_status);
  expect(['ERROR','FAILED']).toContain(bad.extraction_status.toUpperCase());await expect(badRow).toContainText(bad.extraction_status);await expect(badRow.getByRole('button',{name:'재처리',exact:true})).toBeVisible();await expect(page.locator('#toast')).toContainText('재처리 필요');record('Corrupt supported DOCX has explicit per-document failed conversion state',bad.extraction_status);
  async function original(row,doc,bytes){
   const received=page.waitForResponse(r=>r.url().endsWith('/api/documents/'+doc.id+'/original')),opened=context.waitForEvent('page');
   await row.getByRole('button',{name:'원문 열기',exact:true}).click();const response=await received,source=await opened;expect(response.status()).toBe(200);
   // Chromium reports an empty CDP response body for the attachment fetch; verify
   // visible TXT source plus the authenticated original endpoint's actual bytes.
   if(doc.filename.endsWith('.txt'))await expect(source.locator('body')).toContainText('31 calendar days');
   const originalResponse=await api.get('/api/documents/'+doc.id+'/original');expect(originalResponse.status()).toBe(200);expect(Buffer.compare(await originalResponse.body(),bytes)).toBe(0);
  }
  await original(goodRow,good,goodBytes);await original(badRow,bad,badBytes);record('Original UI actions succeed and valid text source is visibly readable');record('Authenticated original download API preserves exact bytes for both files');
  const retry=page.waitForResponse(r=>r.url().endsWith('/api/documents/'+bad.id+'/retry'));await badRow.getByRole('button',{name:'재처리',exact:true}).click();const retried=await retry;expect(retried.status()).toBe(200);const after=await retried.json();expect(['ERROR','FAILED']).toContain(after.extraction_status.toUpperCase());await expect(badRow).toContainText(after.extraction_status);await expect(page.locator('#toast')).toContainText('재처리 결과: '+after.extraction_status);await expect(badRow.getByRole('button',{name:'재처리',exact:true})).toBeEnabled();record('Retry reports continued corruption honestly without fake READY',after.extraction_status);
  await original(badRow,bad,badBytes);await expect(goodRow).toBeVisible();const retained=await(await api.get('/api/projects/'+good.project_id+'/documents')).json();expect(retained).toHaveLength(2);expect(retained.find(d=>d.id===good.id).sha256).toBe(crypto.createHash('sha256').update(goodBytes).digest('hex'));record('Retry retains corrupt original and does not lose successful document');
  await page.locator('[data-action=new-draft][data-kind=itb]').click();await page.getByRole('button',{name:'초안 생성',exact:true}).click();await expect(page.locator('#draft-form textarea[name=current]').first()).toHaveValue(/31 calendar days/);record('Successful file remains usable in actual draft after failed conversion retry');
  await page.getByRole('button',{name:'데이터 관리',exact:true}).click();await expect(page.getByRole('heading',{name:'데이터 관리',exact:true})).toBeVisible();await expect(page.locator('.stats')).not.toContainText(/실패|처리중|처리 중/);record('No removed failure or processing KPI introduced');
  expect(report.errors).toEqual([]);record('No browser JavaScript errors');
 }catch(e){report.failure=e.stack;process.exitCode=1;await page.screenshot({path:path.join(out,'browser-mixed-upload-failure-'+report.started.replace(/[:.]/g,'-')+'.png'),fullPage:true});}
 finally{report.finished=new Date().toISOString();const file='browser-mixed-upload-'+report.started.replace(/[:.]/g,'-')+'.json';fs.writeFileSync(path.join(out,file),JSON.stringify(report,null,2));console.log(JSON.stringify({...report,evidence:file},null,2));await browser.close();await api.dispose();}
})().catch(e=>{console.error(e);process.exitCode=1});
