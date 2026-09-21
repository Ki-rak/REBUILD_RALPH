const OPENAI_BASE_URL = "https://api.openai.com/v1";
const LOCAL_ENVS = new Set(["local", "demo"]);
const CHILD_ENV_KEYS = [
  "PATH",
  "Path",
  "PATHEXT",
  "SystemRoot",
  "WINDIR",
  "COMSPEC",
  "TEMP",
  "TMP",
  "LOCALAPPDATA",
  "APPDATA",
  "LANG",
  "LC_ALL",
  "TERM",
];

export class ConfigurationError extends Error {
  constructor(code) {
    super(code);
    this.name = "ConfigurationError";
    this.code = code;
  }
}

export function isHosted(env) {
  return env.NODE_ENV === "production" || Boolean(env.VERCEL);
}

export function resolveRuntime(env) {
  const mode = env.REBUILD_ENV;
  if (!mode) throw new ConfigurationError("REBUILD_ENV_REQUIRED");
  if (!["local", "demo", "deployed"].includes(mode)) {
    throw new ConfigurationError("REBUILD_ENV_INVALID");
  }

  if (LOCAL_ENVS.has(mode)) {
    if (isHosted(env)) throw new ConfigurationError("HOSTED_OAUTH_FORBIDDEN");
    return { mode, provider: "codex-oauth", credentialMode: "chatgpt-oauth" };
  }

  if (!env.OPENAI_API_KEY) throw new ConfigurationError("OPENAI_API_KEY_REQUIRED");
  if (!env.OPENAI_MODEL) throw new ConfigurationError("OPENAI_MODEL_REQUIRED");
  const baseUrl = env.OPENAI_BASE_URL || OPENAI_BASE_URL;
  if (baseUrl !== OPENAI_BASE_URL) throw new ConfigurationError("OPENAI_BASE_URL_FORBIDDEN");
  return {
    mode,
    provider: "openai-responses",
    credentialMode: "server-api-key",
    apiKey: env.OPENAI_API_KEY,
    model: env.OPENAI_MODEL,
    baseUrl,
  };
}

export function buildCodexEnvironment(parentEnv, codexHome) {
  const child = {};
  for (const key of CHILD_ENV_KEYS) {
    if (typeof parentEnv[key] === "string" && parentEnv[key]) child[key] = parentEnv[key];
  }
  child.CODEX_HOME = codexHome;
  child.HOME = codexHome;
  child.USERPROFILE = codexHome;
  return child;
}

export const DEFAULT_OPENAI_BASE_URL = OPENAI_BASE_URL;
