import { loadSettings, configuredProvider, safeCode } from './runtime.js';
try {
  const env = loadSettings();
  const provider = await configuredProvider(env);
  const status = await provider.status();
  console.log(JSON.stringify({ component: 'RE:Build Agent AI provider', environment: env.REBUILD_ENV, provider: status.provider, authentication: status.authentication, inference: status.inference }));
} catch (error) { console.log(JSON.stringify({ error: safeCode(error), inference: 'NOT_TESTED' })); process.exitCode = 1; }
