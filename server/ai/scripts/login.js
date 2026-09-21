// Run interactively in your own terminal. The official CLI handles the browser callback.
import { spawn } from 'node:child_process';
import { loadSettings, cliContext, CLI, AUTH_ARGS, safeCode } from './runtime.js';
import { resolveRuntime } from '../src/runtime-config.js';
try {
  const env = loadSettings();
  if (resolveRuntime(env).provider !== 'codex-oauth') throw new Error('HOSTED_OAUTH_FORBIDDEN');
  const child = spawn(process.execPath, [CLI, ...AUTH_ARGS, 'login'], { ...await cliContext(env), stdio: 'inherit' });
  child.on('error', () => { console.error('OFFICIAL_LOGIN_UNAVAILABLE'); process.exitCode = 1; });
  child.on('close', (code) => { process.exitCode = code ?? 1; });
} catch (error) { console.error(safeCode(error)); process.exitCode = 1; }
