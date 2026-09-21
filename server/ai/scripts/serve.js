import { loadSettings, configuredProvider, safeCode } from './runtime.js';
import { createLocalServer } from '../src/local-server.js';
try {
  const env = loadSettings();
  const provider = await configuredProvider(env);
  const app = createLocalServer({ provider, env: env.REBUILD_ENV });
  await app.listen({ host: '127.0.0.1', port: 4319 });
  console.log('RE:Build Agent AI component test: http://127.0.0.1:4319 (loopback only; not the product UI)');
  process.once('SIGINT', () => app.close());
  process.once('SIGTERM', () => app.close());
} catch (error) { console.error(safeCode(error)); process.exitCode = 1; }
