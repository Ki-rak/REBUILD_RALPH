'use strict';
const {chromium,request}=require('../../tools/web/node_modules/playwright');
const {expect}=require('../../tools/web/node_modules/playwright/test');
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const base=process.env.SCOPE_TEST_URL||'http://127.0.0.1:8783';
const report={boundary:'TEST_STORAGE_INJECTED',scenario:'Search scope isolation and mode persistence',started:new Date().toISOString(),checks:[],errors:[]};
const check=name=>report.checks.push({name,status:'PASS'});
(async()=>{
 const api=await request.newContext({baseURL:base,extraHTTPHeaders:{Authorization:'Bearer browser-alice'}});
 await expect.poll(async()=>{try{return(await api.get('/api/config')).status()}catch{return 0}},{timeout:60000}).toBe(200);
 expect(await(await api.get('/api/projects')).json()).toEqual([]);
 const browser=await chromium.launch({headless:true}),page=await browser.newPage();
 page.on('pageerror',e=>report.errors.push(e.message));
 try{
  const marker=crypto.randomUUID(),current='CurrentScope '+marker,past='PastScope '+marker;
  await page.goto(base);await page.getByLabel('이메일',{exact:true}).fill('browser-alice@example.invalid');await page.getByLabel('비밀번호',{exact:true}).fill('synthetic-test-only');await page.getByRole('button',{name:'로그인',exact:true}).click();
  for(const item of [{kind:'historical',name:past,text:'Scopeproof historical contract 28 days.'},{kind:'current',name:current,text:'Scopeproof current contract 17 days.'}]){
   await page.getByRole('button',{name:'새 프로젝트',exact:true}).click();
   await page.getByLabel('프로젝트 이름',{exact:true}).fill(item.name);await page.getByLabel('프로젝트 용도',{exact:true}).selectOption(item.kind);
   await page.locator('#modal-files').setInputFiles({name:item.kind+'.txt',mimeType:'text/plain',buffer:Buffer.from(item.text+' '+marker)});
   await page.getByRole('button',{name:'프로젝트 생성',exact:true}).click();await expect(page.getByRole('heading',{name:item.name,exact:true})).toBeVisible();
   if(item.kind==='historical')await page.getByRole('button',{name:'프로젝트 변경',exact:true}).click();
  }
  check('Fresh historical and current uploads created via product UI');
  await page.getByRole('button',{name:'지식조회',exact:true}).click();
  const scope=page.getByLabel('검색 자료 범위',{exact:true}),results=page.locator('#query-results');
  await expect(scope).toHaveValue('all');await page.getByLabel('질문 또는 확인할 조건',{exact:true}).fill('Scopeproof');
  async function search(expectedScope){
   const response=page.waitForResponse(r=>r.url().includes('/api/search?'));
   await page.getByRole('button',{name:'자료 검색',exact:true}).click();
   const received=await response;expect(received.status()).toBe(200);expect(new URL(received.url()).searchParams.get('scope')).toBe(expectedScope);
  }
  await search('all');await expect(results).toContainText('historical contract 28 days');await expect(results).toContainText('current contract 17 days');check('All scope returns both actual source contents');
  await scope.selectOption('current');await expect(results).not.toContainText('historical contract 28 days');await expect(results).toContainText('검색 범위가 변경');
  await search('current');await expect(results).toContainText('current contract 17 days');await expect(results).not.toContainText('historical contract 28 days');check('Current scope clears old results and returns only current source');
  await scope.selectOption('historical');await search('historical');await expect(results).toContainText('historical contract 28 days');await expect(results).not.toContainText('current contract 17 days');check('Historical scope returns only past source');
  await page.getByRole('tab',{name:'AI Insight Mode',exact:true}).click();await expect(page.getByLabel('질문 또는 확인할 조건',{exact:true})).toHaveValue('Scopeproof');await expect(page.locator('#query-form')).toContainText('검색 범위는 AI 적용 검토를 제한하지 않습니다');await expect(scope).toHaveCount(0);check('AI mode preserves question and explicitly discloses its comparison scope');
  await page.getByRole('tab',{name:'Search Mode',exact:true}).click();await expect(scope).toHaveValue('historical');await expect(page.getByLabel('질문 또는 확인할 조건',{exact:true})).toHaveValue('Scopeproof');await search('historical');await expect(results).not.toContainText('current contract 17 days');check('Returning to Search preserves selected scope and query');
  expect(report.errors).toEqual([]);check('No browser errors');
 }catch(e){report.failure=e.stack;process.exitCode=1;}
 finally{report.finished=new Date().toISOString();const file=path.join('ops/runtime','browser-search-scope-'+report.started.replace(/[:.]/g,'-')+'.json');fs.writeFileSync(file,JSON.stringify(report,null,2));console.log(JSON.stringify({...report,evidence:file},null,2));await browser.close();await api.dispose();}
})().catch(e=>{console.error(e);process.exitCode=1});
