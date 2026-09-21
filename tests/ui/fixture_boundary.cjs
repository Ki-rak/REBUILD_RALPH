'use strict';
const assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');
const helper = require.resolve('./fixture_target.cjs');
(async()=>{
 const cleanEnv={...process.env};delete cleanEnv.BROWSER_TEST_URL;delete cleanEnv.BROWSER_TEST_RUN_ID;
 assert.notEqual(spawnSync(process.execPath,['-e',`require(${JSON.stringify(helper)})`],{env:cleanEnv}).status,0);
 process.env.BROWSER_TEST_URL='http://127.0.0.1:8799';process.env.BROWSER_TEST_RUN_ID='1234567890abcdef1234567890abcdef';
 const {verifyFixture}=require(helper);
 const response=(boundary,runId)=>({get:async()=>({status:()=>200,headers:()=>({'x-test-boundary':boundary,'x-test-run-id':runId})})});
 await assert.rejects(()=>verifyFixture(response(undefined,process.env.BROWSER_TEST_RUN_ID),{}),/not a test fixture/);
 await assert.rejects(()=>verifyFixture(response('TEST_STORAGE_INJECTED','other-run'),{}),/belong to this runner/);
 const report={};await verifyFixture(response('TEST_STORAGE_INJECTED',process.env.BROWSER_TEST_RUN_ID),report);assert.equal(report.fixture.boundary_verified,true);
 console.log('4 fixture target boundary checks PASS');
})().catch(e=>{console.error(e.message);process.exitCode=1});