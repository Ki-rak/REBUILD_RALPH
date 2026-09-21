import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { createProvider, DEFAULT_CODEX_HOME } from '../src/provider.js';
import { buildCodexEnvironment, resolveRuntime } from '../src/runtime-config.js';
const exec = promisify(execFile);
export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
export const CLI = path.join(ROOT, 'server/ai/node_modules/@openai/codex/bin/codex.js');
export const AUTH_ARGS = ['-c', 'forced_login_method="chatgpt"'];
export function loadSettings() {
  try { process.loadEnvFile(path.join(ROOT, '.env')); }
  catch (error) { if (error.code !== 'ENOENT') throw new Error('ENV_LOAD_FAILED'); }
  return { ...process.env };
}
export async function cliContext(env) {
  await fs.mkdir(DEFAULT_CODEX_HOME, { recursive: true });
  return { cwd: os.tmpdir(), env: buildCodexEnvironment(env, DEFAULT_CODEX_HOME), windowsHide: true };
}
export async function loginStatus(env) {
  const options = { ...await cliContext(env), timeout: 20000, maxBuffer: 65536 };
  try {
    const r = await exec(process.execPath, [CLI, ...AUTH_ARGS, 'login', 'status'], options);
    return /logged in using chatgpt/i.test(r.stdout + r.stderr) ? 'LOGGED_IN' : 'AUTH_STATUS_UNAVAILABLE';
  } catch (error) {
    return /not logged in/i.test(String(error.stdout || '') + String(error.stderr || '')) ? 'NOT_LOGGED_IN' : 'AUTH_STATUS_UNAVAILABLE';
  }
}
export async function configuredProvider(env = loadSettings()) {
  const route = resolveRuntime(env);
  if (route.provider === 'codex-oauth') await cliContext(env);
  return createProvider({ env, statusChecker: () => loginStatus(env) });
}
const SAFE_CODES = new Set(['REBUILD_ENV_REQUIRED','REBUILD_ENV_INVALID','HOSTED_OAUTH_FORBIDDEN','OPENAI_API_KEY_REQUIRED','OPENAI_MODEL_REQUIRED','OPENAI_BASE_URL_FORBIDDEN','OPENAI_REQUEST_FAILED','OPENAI_REQUEST_TIMEOUT','OPENAI_AUTH_FAILED','OPENAI_RATE_LIMITED','OPENAI_INVALID_REQUEST','OPENAI_UNAVAILABLE','INVALID_OPENAI_RESPONSE','INVALID_PROVIDER_JSON','INVALID_PROVIDER_OUTPUT','UNKNOWN_SOURCE_ID','CODEX_LOGIN_REQUIRED','CODEX_TURN_FAILED','CODEX_TURN_INCOMPLETE','CODEX_REQUEST_TIMEOUT','CODEX_TIMEOUT','EMPTY_CODEX_RESPONSE','TOOL_EVENT_REJECTED','UNCITED_ANSWER','UNCITED_CLAIM','ENV_LOAD_FAILED']);
export function safeCode(error) { return SAFE_CODES.has(error?.code) ? error.code : SAFE_CODES.has(error?.message) ? error.message : 'AI_COMPONENT_FAILED'; }
