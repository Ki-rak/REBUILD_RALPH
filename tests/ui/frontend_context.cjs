'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return {promise, resolve};
}

function jsonResponse(payload) {
  return {
    ok:true,
    status:200,
    headers:{get(name){return name.toLowerCase()==='content-type'?'application/json':''}},
    async json(){return payload},
    async text(){return JSON.stringify(payload)},
  };
}

function harness() {
  const listeners = {};
  const app = {className:'', innerHTML:'', setAttribute(){}};
  const modal = {innerHTML:'', querySelector(){return null}};
  const toast = {textContent:'', hidden:true};
  const resultRegion = {innerHTML:''};
  const nodes = {'#app':app,'#modal-root':modal,'#toast':toast,'#query-results':resultRegion};
  const document = {
    querySelector(selector){return nodes[selector] || null},
    addEventListener(type, handler){listeners[type]=handler},
    createElement(){return {click(){},remove(){}}},
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
    + '\nglobalThis.__test={state,runKnowledgeQuery:typeof runKnowledgeQuery==="function"?runKnowledgeQuery:null,setKnowledgeProject:typeof setKnowledgeProject==="function"?setKnowledgeProject:null,setKnowledgeMode:typeof setKnowledgeMode==="function"?setKnowledgeMode:null};';
  vm.createContext(context);
  vm.runInContext(source,context,{filename:'frontend/app.js'});
  return {context,listeners,resultRegion};
}

function assertContextApi(api) {
  assert.equal(typeof api.runKnowledgeQuery,'function','query execution must capture its context');
  assert.equal(typeof api.setKnowledgeProject,'function','project changes must invalidate result context');
  assert.equal(typeof api.setKnowledgeMode,'function','mode changes must invalidate result context');
}

async function testProjectSwitchRejectsStaleResponse() {
  const {context,resultRegion} = harness();
  const test = context.__test;
  assertContextApi(test);
  test.state.project={id:'p1',name:'One'};
  test.state.mode='search';
  const request=deferred();
  context.fetch=()=>request.promise;

  const pending=test.runKnowledgeQuery('notice period',resultRegion);
  test.setKnowledgeProject({id:'p2',name:'Two'});
  request.resolve(jsonResponse({results:[{title:'stale project one'}]}));
  await pending;

  assert.equal(test.state.project.id,'p2');
  assert.equal(test.state.query,'notice period','typed question must survive project change');
  assert.equal(test.state.result,null,'old project response must not enter shared state');
  assert.doesNotMatch(resultRegion.innerHTML,/stale project one/);
}

async function testModeSwitchPreservesQuestionAndRejectsStaleResponse() {
  const {context,resultRegion} = harness();
  const test = context.__test;
  assertContextApi(test);
  test.state.project={id:'p1',name:'One'};
  test.state.mode='search';
  const request=deferred();
  context.fetch=()=>request.promise;

  const pending=test.runKnowledgeQuery('groundwater risk',resultRegion);
  test.setKnowledgeMode('ai');
  request.resolve(jsonResponse({results:[{title:'stale search result'}]}));
  await pending;

  assert.equal(test.state.mode,'ai');
  assert.equal(test.state.query,'groundwater risk');
  assert.equal(test.state.result,null);
  assert.doesNotMatch(resultRegion.innerHTML,/stale search result/);
}

async function testNewerQueryWinsWhenOlderPromiseResolvesLast() {
  const {context,resultRegion} = harness();
  const test = context.__test;
  assertContextApi(test);
  test.state.project={id:'p1',name:'One'};
  test.state.mode='search';
  const first=deferred(),second=deferred(),requests=[first,second];
  context.fetch=()=>requests.shift().promise;

  const oldPending=test.runKnowledgeQuery('old question',resultRegion);
  const newPending=test.runKnowledgeQuery('new question',resultRegion);
  second.resolve(jsonResponse({results:[{title:'fresh answer'}]}));
  await newPending;
  first.resolve(jsonResponse({results:[{title:'stale answer'}]}));
  await oldPending;

  assert.equal(test.state.query,'new question');
  assert.equal(test.state.result.results[0].title,'fresh answer');
  assert.equal(test.state.resultContext.projectId,'p1');
  assert.equal(test.state.resultContext.mode,'search');
  assert.equal(test.state.resultContext.query,'new question');
  assert.match(resultRegion.innerHTML,/fresh answer/);
  assert.doesNotMatch(resultRegion.innerHTML,/stale answer/);
}

function testUnsubmittedQuestionSurvivesModeChange() {
  const {context,listeners} = harness();
  const test = context.__test;
  assertContextApi(test);
  listeners.input({target:{id:'query',value:'unfinished question'}});
  test.setKnowledgeMode('ai');
  assert.equal(test.state.query,'unfinished question');
}

(async()=>{
  await testProjectSwitchRejectsStaleResponse();
  await testModeSwitchPreservesQuestionAndRejectsStaleResponse();
  await testNewerQueryWinsWhenOlderPromiseResolvesLast();
  testUnsubmittedQuestionSurvivesModeChange();
  console.log('frontend context isolation: 4 passed');
})().catch(error=>{console.error(error);process.exitCode=1});
