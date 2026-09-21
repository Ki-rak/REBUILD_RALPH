import test from "node:test";
import assert from "node:assert/strict";

import { createDeployedProvider } from "../src/deployed-provider.js";

const request = {
  question: "What is supported?",
  evidence: [{ id: "SRC-1", text: "Only item A is approved.", location: "section 1" }],
};

test("deployed provider sends a non-persistent constrained Responses request", async () => {
  let observed;
  const provider = createDeployedProvider({
    apiKey: "server-secret",
    model: "gpt-test",
    baseUrl: "https://api.openai.com/v1",
    fetchImpl: async (url, init) => {
      observed = { url, init, body: JSON.parse(init.body) };
      return new Response(JSON.stringify({
        output_text: JSON.stringify({
          status: "ANSWERED",
          answer: "Item A is approved.",
          claims: [{ text: "Item A is approved.", source_ids: ["SRC-1"] }],
        }),
      }), { status: 200, headers: { "content-type": "application/json" } });
    },
  });

  const answer = await provider.analyze(request);

  assert.equal(answer.status, "ANSWERED");
  assert.equal(observed.url, "https://api.openai.com/v1/responses");
  assert.equal(observed.init.headers.Authorization, "Bearer server-secret");
  assert.equal(observed.body.store, false);
  assert.equal(observed.body.model, "gpt-test");
  assert.equal(observed.body.text.format.type, "json_schema");
  assert.equal(observed.body.text.format.strict, true);
  assert.deepEqual(observed.body.tools, []);
});

test("deployed provider redacts remote errors and secrets", async () => {
  const provider = createDeployedProvider({
    apiKey: "server-secret",
    model: "gpt-test",
    baseUrl: "https://api.openai.com/v1",
    fetchImpl: async () => new Response("server-secret upstream diagnostic", { status: 401 }),
  });

  await assert.rejects(
    () => provider.analyze(request),
    (error) => error.code === "OPENAI_AUTH_FAILED"
      && !error.message.includes("server-secret")
      && !error.message.includes("diagnostic"),
  );
});

test("deployed provider reports safe actionable HTTP categories", async () => {
  const cases = [
    [400, "OPENAI_INVALID_REQUEST"],
    [403, "OPENAI_AUTH_FAILED"],
    [429, "OPENAI_RATE_LIMITED"],
    [503, "OPENAI_UNAVAILABLE"],
  ];
  for (const [status, code] of cases) {
    const provider = createDeployedProvider({
      apiKey: "server-secret",
      model: "gpt-test",
      baseUrl: "https://api.openai.com/v1",
      fetchImpl: async () => new Response("sensitive body", { status }),
    });
    await assert.rejects(() => provider.analyze(request), (error) => error.code === code && error.message === code);
  }
});

test("deployed factory rejects a non-OpenAI endpoint when called directly", () => {
  assert.throws(
    () => createDeployedProvider({ apiKey: "secret", model: "gpt-test", baseUrl: "https://evil.example/v1" }),
    (error) => error.code === "OPENAI_BASE_URL_FORBIDDEN",
  );
});

test("deployed provider maps unknown transport errors to a safe error", async () => {
  const provider = createDeployedProvider({
    apiKey: "server-secret",
    model: "gpt-test",
    baseUrl: "https://api.openai.com/v1",
    fetchImpl: async () => {
      const error = new Error("server-secret transport diagnostic");
      error.code = "SECRET_TRANSPORT_CODE";
      throw error;
    },
  });

  await assert.rejects(
    () => provider.analyze(request),
    (error) => error.code === "OPENAI_REQUEST_FAILED" && !error.message.includes("server-secret"),
  );
});

test("deployed provider rejects citations not present in the request", async () => {
  const provider = createDeployedProvider({
    apiKey: "server-secret",
    model: "gpt-test",
    baseUrl: "https://api.openai.com/v1",
    fetchImpl: async () => new Response(JSON.stringify({
      output_text: JSON.stringify({
        status: "ANSWERED",
        answer: "Unsupported.",
        claims: [{ text: "Unsupported.", source_ids: ["OTHER"] }],
      }),
    }), { status: 200 }),
  });

  await assert.rejects(() => provider.analyze(request), (error) => error.code === "UNKNOWN_SOURCE_ID");
});
