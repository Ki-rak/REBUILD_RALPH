import test from "node:test";
import assert from "node:assert/strict";

import { createProvider } from "../src/provider.js";

test("local routing cannot fall back to the deployed transport", async () => {
  let oauthCalls = 0;
  let deployedCalls = 0;
  const provider = createProvider({
    env: { REBUILD_ENV: "local", OPENAI_API_KEY: "present-but-ignored", CODEX_MODEL: "gpt-oauth-test" },
    factories: {
      codex: () => ({ analyze: async () => { oauthCalls += 1; return { status: "REVIEW_REQUIRED", answer: "No evidence.", claims: [] }; } }),
      deployed: () => ({ analyze: async () => { deployedCalls += 1; throw new Error("must not run"); } }),
    },
  });

  const answer = await provider.analyze({ question: "x", evidence: [] });
  assert.equal(answer.status, "REVIEW_REQUIRED");
  assert.equal(oauthCalls, 1);
  assert.equal(deployedCalls, 0);
});

test("deployed routing cannot fall back to local OAuth", async () => {
  let oauthCalls = 0;
  let deployedCalls = 0;
  const provider = createProvider({
    env: { REBUILD_ENV: "deployed", OPENAI_API_KEY: "secret", OPENAI_MODEL: "gpt-test" },
    factories: {
      codex: () => ({ analyze: async () => { oauthCalls += 1; throw new Error("must not run"); } }),
      deployed: () => ({ analyze: async () => { deployedCalls += 1; return { status: "REVIEW_REQUIRED", answer: "No evidence.", claims: [] }; } }),
    },
  });

  await provider.analyze({ question: "x", evidence: [] });
  assert.equal(deployedCalls, 1);
  assert.equal(oauthCalls, 0);
});
