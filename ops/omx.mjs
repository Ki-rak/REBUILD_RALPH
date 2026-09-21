// Project-local entry point for upstream OMX; no custom execution loop.
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const result = spawnSync(process.execPath, [path.join(root, 'tools/omx/node_modules/oh-my-codex/dist/cli/omx.js'), ...process.argv.slice(2)], {
  cwd: process.cwd(),
  env: { ...process.env, OMX_NATIVE_CACHE_DIR: path.join(root, 'tools/omx/native-cache') },
  stdio: 'inherit',
  windowsHide: true,
});
if (result.error) { console.error(result.error.message); process.exit(1); }
process.exit(result.status ?? 1);
