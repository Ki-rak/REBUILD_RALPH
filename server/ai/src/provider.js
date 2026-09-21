import path from "node:path";
import { fileURLToPath } from "node:url";

import { createCodexProvider } from "./codex-provider.js";
import { createDeployedProvider } from "./deployed-provider.js";
import { resolveRuntime } from "./runtime-config.js";

const moduleDir = path.dirname(fileURLToPath(import.meta.url));
const defaultCodexHome = path.resolve(moduleDir, "../../../ops/private/codex-ai");

export function createProvider({
  env = process.env,
  factories = { codex: createCodexProvider, deployed: createDeployedProvider },
  codexHome = defaultCodexHome,
  statusChecker,
} = {}) {
  const runtime = resolveRuntime(env);
  if (runtime.provider === "codex-oauth") {
    return factories.codex({ codexHome, parentEnv: env, statusChecker, model: env.CODEX_MODEL });
  }
  return factories.deployed({
    apiKey: runtime.apiKey,
    model: runtime.model,
    baseUrl: runtime.baseUrl,
  });
}

export { defaultCodexHome as DEFAULT_CODEX_HOME };
