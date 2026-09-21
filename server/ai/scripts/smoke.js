import { loadSettings, configuredProvider, safeCode } from './runtime.js';
const started = Date.now();
try {
  const env = loadSettings();
  const provider = await configuredProvider(env);
  const answer = await provider.analyze({ question: 'What is the notice period in the supplied clause? Answer briefly using this evidence only.', evidence: [{ id: 'SMOKE-CLAUSE-1', text: 'Approved contract clause: notice must be delivered within 14 calendar days.', location: 'component test fixture, clause 1' }] });
  const passed = answer.status === 'ANSWERED' && answer.claims.some(c => c.source_ids.includes('SMOKE-CLAUSE-1'));
  console.log(JSON.stringify({ component: 'RE:Build Agent AI provider', environment: env.REBUILD_ENV, actual_call: true, passed, cited_claims: answer.claims.length, elapsed_ms: Date.now()-started, product_e2e: false, execution: answer.execution, usage: answer.usage }));
  if (!passed) process.exitCode = 1;
} catch (error) { console.log(JSON.stringify({ actual_call_verified: false, error: safeCode(error), elapsed_ms: Date.now()-started })); process.exitCode = 1; }
