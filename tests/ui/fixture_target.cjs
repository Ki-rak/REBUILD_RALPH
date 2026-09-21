'use strict';
const assert = require('node:assert/strict');
const base = process.env.BROWSER_TEST_URL;
const runId = process.env.BROWSER_TEST_RUN_ID;
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(base || '') || !/^[a-f0-9]{32}$/.test(runId || '')) {
  throw new Error('Run browser checks through tests/ui/run_browser.py with an owned fixture');
}
async function verifyFixture(api, report) {
  const response = await api.get('/api/config');
  assert.equal(response.status(), 200, 'Owned fixture must be ready');
  const headers = response.headers();
  assert.equal(headers['x-test-boundary'], 'TEST_STORAGE_INJECTED', 'Production server is not a test fixture');
  assert.equal(headers['x-test-run-id'], runId, 'Browser target must belong to this runner');
  report.fixture = {url: base, run_id: runId, boundary_verified: true};
}
module.exports = {base, verifyFixture};