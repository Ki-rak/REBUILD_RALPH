import test from "node:test";
import assert from "node:assert/strict";

import {
  ConfigurationError,
  buildCodexEnvironment,
  resolveRuntime,
} from "../src/runtime-config.js";

test("local stays on ChatGPT OAuth even when an API key exists", () => {
  const runtime = resolveRuntime({
    REBUILD_ENV: "local",
    OPENAI_API_KEY: "must-not-be-used",
  });

  assert.equal(runtime.provider, "codex-oauth");
  assert.equal(runtime.credentialMode, "chatgpt-oauth");
});

test("hosted execution refuses the local OAuth route", () => {
  assert.throws(
    () => resolveRuntime({ REBUILD_ENV: "local", VERCEL: "1" }),
    (error) => error instanceof ConfigurationError && error.code === "HOSTED_OAUTH_FORBIDDEN",
  );
});

test("missing REBUILD_ENV never guesses a credential route", () => {
  assert.throws(
    () => resolveRuntime({}),
    (error) => error instanceof ConfigurationError && error.code === "REBUILD_ENV_REQUIRED",
  );
});

test("deployed requires a key and model and rejects arbitrary base URLs", () => {
  assert.throws(
    () => resolveRuntime({ REBUILD_ENV: "deployed", OPENAI_MODEL: "gpt-test" }),
    (error) => error.code === "OPENAI_API_KEY_REQUIRED",
  );
  assert.throws(
    () => resolveRuntime({ REBUILD_ENV: "deployed", OPENAI_API_KEY: "secret" }),
    (error) => error.code === "OPENAI_MODEL_REQUIRED",
  );
  assert.throws(
    () => resolveRuntime({
      REBUILD_ENV: "deployed",
      OPENAI_API_KEY: "secret",
      OPENAI_MODEL: "gpt-test",
      OPENAI_BASE_URL: "https://internal.example/v1",
    }),
    (error) => error.code === "OPENAI_BASE_URL_FORBIDDEN",
  );
});

test("the explicit Codex child environment excludes provider secrets", () => {
  const child = buildCodexEnvironment({
    PATH: "safe-path",
    SystemRoot: "C:\\Windows",
    TEMP: "C:\\Temp",
    OPENAI_API_KEY: "openai-secret",
    ANTHROPIC_API_KEY: "anthropic-secret",
    AWS_SECRET_ACCESS_KEY: "aws-secret",
    AZURE_OPENAI_API_KEY: "azure-secret",
  }, "D:\\private-codex-home");

  assert.equal(child.CODEX_HOME, "D:\\private-codex-home");
  assert.equal(child.USERPROFILE, "D:\\private-codex-home");
  assert.equal(child.HOME, "D:\\private-codex-home");
  assert.equal(child.PATH, "safe-path");
  assert.equal(child.SystemRoot, "C:\\Windows");
  assert.equal(child.OPENAI_API_KEY, undefined);
  assert.equal(child.ANTHROPIC_API_KEY, undefined);
  assert.equal(child.AWS_SECRET_ACCESS_KEY, undefined);
  assert.equal(child.AZURE_OPENAI_API_KEY, undefined);
});
