import { configuredProvider, loadSettings, safeCode } from './runtime.js';
let raw = '';
try {
  for await (const chunk of process.stdin) {
    raw += chunk.toString('utf8');
    if (Buffer.byteLength(raw) > 65536) throw new Error('INVALID_REQUEST');
  }
  const input = JSON.parse(raw);
  const provider = await configuredProvider(loadSettings());
  let result;
  if (input.operation === 'status') result = await provider.status();
  else if (input.operation === 'analyze') result = await provider.analyze(input.request);
  else throw new Error('INVALID_REQUEST');
  process.stdout.write(JSON.stringify({ok:true,result}));
} catch(error) {
  process.stdout.write(JSON.stringify({ok:false,error:safeCode(error)}));
  process.exitCode = 1;
}
