'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {validateTarget,verifyIdentity}=require('../../ops/demo_browser.cjs');
test('live browser refuses arbitrary credential destination',()=>{
 for(const base of ['https://example.com','http://127.0.0.1.evil.test','http://u:p@localhost:8793','http://localhost:8793/redirect','http://localhost:8793/?next=evil'])
  assert.throws(()=>validateTarget({base,run_id:'1234567890123456'}));
 assert.equal(validateTarget({base:'http://127.0.0.1:8793',run_id:'1234567890123456'}),'http://127.0.0.1:8793');
 assert.throws(()=>validateTarget({base:'http://127.0.0.1:8793'}));
});
test('credentials wait for exact real-service owner identity',()=>{
 const expected={run_id:'1234567890123456',boundary:'REAL_SUPABASE_USER_JWT',product:'RE:Build Agent'};
 verifyIdentity(expected,expected.run_id);
 for(const actual of [{...expected,run_id:'different'},{...expected,boundary:'TEST_STORAGE_INJECTED'},{...expected,product:'Preview'},{}])
  assert.throws(()=>verifyIdentity(actual,expected.run_id));
});
test('all filenames survive SHA dedup and missing aliases fail',()=>{
 const {verifyDocumentCoverage}=require('../../ops/demo_browser.cjs');
 const selected={files:[{name:'a.pdf',sha256:'same'},{name:'copy.pdf',sha256:'same'},{name:'new.pdf',sha256:'other'}]};
 const docs=[{sha256:'same',aliases:['a.pdf','copy.pdf'],extraction_status:'EXTRACTED'},{sha256:'other',aliases:['new.pdf'],extraction_status:'EXTRACTED'}];
 verifyDocumentCoverage(selected,docs);
 assert.throws(()=>verifyDocumentCoverage(selected,docs.slice(0,1)));
 assert.throws(()=>verifyDocumentCoverage(selected,[{...docs[0],aliases:['a.pdf']},docs[1]]));
 assert.throws(()=>verifyDocumentCoverage(selected,[docs[0],{...docs[1],extraction_status:'FAILED'}]));
});
