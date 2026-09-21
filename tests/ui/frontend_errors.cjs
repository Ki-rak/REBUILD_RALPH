'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function harness() {
  const listeners = {};
  const app = {className:'', innerHTML:'', setAttribute(){}};
  const modal = {innerHTML:'', querySelector(){return null}};
  const toast = {textContent:'', hidden:true};
  const nodes = {'#app':app,'#modal-root':modal,'#toast':toast};
  const document = {
    querySelector(selector){return nodes[selector] || null},
    addEventListener(type, handler){listeners[type]=handler},
    createElement(){return {click(){},remove(){},set href(v){this._href=v},set download(v){this._download=v}}},
    body:{append(){}},
  };
  const storage = new Map();
  const sessionStorage = {
    getItem(key){return storage.get(key) ?? null},
    setItem(key,value){storage.set(key,String(value))},
    removeItem(key){storage.delete(key)},
  };
  const context = {
    console, document, sessionStorage, location:{hash:''},
    window:{addEventListener(){},open(){return null}},
    Headers, FormData, Event,
    URL:{createObjectURL(){return 'blob:test'},revokeObjectURL(){}},
    setTimeout(){return 1}, clearTimeout(){},
    fetch: async()=>{throw new Error('unexpected fetch')},
  };
  context.globalThis = context;
  const source = fs.readFileSync(path.join(__dirname,'../../frontend/app.js'),'utf8')
    .replace(/initialize\(\);\s*$/,'')
    + '\nglobalThis.__test={state,downloadAuthorized,openAuthorized,ApiError};';
  vm.createContext(context);
  vm.runInContext(source,context,{filename:'frontend/app.js'});
  return {context,listeners,nodes};
}

function headers(contentType='', disposition='') {
  return {get(name){return name.toLowerCase()==='content-type'?contentType:name.toLowerCase()==='content-disposition'?disposition:''}};
}

async function testReadOnceTextError() {
  const {context} = harness();
  let jsonCalls=0, textCalls=0, consumed=false;
  context.__test.state.token='token';
  context.fetch=async()=>({
    ok:false,status:500,headers:headers('text/plain'),
    async json(){jsonCalls++;consumed=true;throw new SyntaxError('not json')},
    async text(){textCalls++;if(consumed)throw new TypeError('Body is unusable');consumed=true;return 'plain failure'},
  });
  await assert.rejects(()=>context.__test.downloadAuthorized('/file','x.bin'),error=>{
    assert.equal(error.message,'plain failure');
    assert.equal(error.status,500);
    return true;
  });
  assert.equal(jsonCalls,0,'non-JSON error must not call json()');
  assert.equal(textCalls,1,'error body must be read exactly once');
}

async function testDownloadRefreshesOnce() {
  const {context} = harness();
  const calls=[];
  context.__test.state.token='old';
  context.__test.state.refreshToken='refresh';
  context.fetch=async(url,options={})=>{
    calls.push([url,options.headers?.Authorization || options.headers?.get?.('Authorization')]);
    if(calls.length===1)return {ok:false,status:401,headers:headers('application/json'),async text(){return '{"detail":{"code":"EXPIRED","message":"expired"}}'}};
    if(url==='/api/auth/refresh')return {ok:true,status:200,async json(){return {access_token:'new',refresh_token:'next'}}};
    return {ok:true,status:200,headers:headers('application/octet-stream','attachment; filename=x.bin'),async blob(){return {}}};
  };
  await context.__test.downloadAuthorized('/file','x.bin');
  assert.deepEqual(calls.map(call=>call[0]),['/file','/api/auth/refresh','/file']);
  assert.equal(calls[2][1],'Bearer new');
}

function testDropAssignmentErrorIsVisible() {
  const {context,listeners,nodes}=harness();
  const errorNode={textContent:''};
  const input={
    set files(_value){throw new TypeError('read only')},
    dispatchEvent(){throw new Error('must stop after assignment failure')},
  };
  const originalQuery=context.document.querySelector;
  context.document.querySelector=selector=>selector==='#modal-files'?input:selector==='#file-error'?errorNode:originalQuery(selector);
  const zone={classList:{remove(){}}};
  listeners.drop({
    target:{closest(selector){return selector==='#dropzone'?zone:null}},
    preventDefault(){},
    dataTransfer:{files:[{name:'sample.pdf'}]},
  });
  assert.match(errorNode.textContent,/드롭|파일/);
}

(async()=>{
  await testReadOnceTextError();
  await testDownloadRefreshesOnce();
  testDropAssignmentErrorIsVisible();
  console.log('frontend error paths: 3 passed');
})().catch(error=>{console.error(error);process.exitCode=1});
