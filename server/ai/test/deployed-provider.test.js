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

test("deployed usage metadata preserves official counts without treating prompt caching as a result cache", async () => {
  const provider = createDeployedProvider({
    apiKey: "server-secret", model: "gpt-5-mini", baseUrl: "https://api.openai.com/v1",
    fetchImpl: async () => new Response(JSON.stringify({
      model: "gpt-5-mini-2025-08-07",
      usage: { input_tokens: 120, output_tokens: 30, total_tokens: 150, input_tokens_details: { cached_tokens: 64 }, secret: "must-not-leak" },
      output_text: JSON.stringify({ status: "ANSWERED", answer: "A.", claims: [{ text: "A.", source_ids: ["SRC-1"] }] }),
    }), { status: 200 }),
  });
  const result = await provider.analyze(request);
  assert.deepEqual(result.usage, { input_tokens: 120, output_tokens: 30, total_tokens: 150, cached_input_tokens: 64 });
  assert.deepEqual(result.execution, {
    provider: "openai-responses", auth_mode: "OPENAI_API_KEY", state: "SUCCEEDED",
    source: "MODEL_CALL", cache_hit: false, model: "gpt-5-mini-2025-08-07", requested_model: "gpt-5-mini",
  });
  assert.ok(!JSON.stringify(result).includes("must-not-leak"));
  assert.ok(!JSON.stringify(result).includes("server-secret"));
});

test("deployed absent or invalid usage remains null and never becomes a fabricated zero", async () => {
  for (const usage of [undefined, { input_tokens: -1, output_tokens: "12", total_tokens: 1.5, input_tokens_details: { cached_tokens: Number.MAX_SAFE_INTEGER + 1 } }]) {
    const provider = createDeployedProvider({
      apiKey: "server-secret", model: "gpt-5-mini", baseUrl: "https://api.openai.com/v1",
      fetchImpl: async () => new Response(JSON.stringify({
        usage,
        output_text: JSON.stringify({ status: "ANSWERED", answer: "A.", claims: [{ text: "A.", source_ids: ["SRC-1"] }] }),
      }), { status: 200 }),
    });
    const result = await provider.analyze(request);
    assert.deepEqual(result.usage, { input_tokens: null, output_tokens: null, total_tokens: null, cached_input_tokens: null });
    assert.equal(result.execution.model, null);
    assert.equal(result.execution.requested_model, "gpt-5-mini");
  }
});

test("deployed measured zero token counts are preserved", async () => {
  const provider = createDeployedProvider({
    apiKey: "server-secret", model: "gpt-5-mini", baseUrl: "https://api.openai.com/v1",
    fetchImpl: async () => new Response(JSON.stringify({
      usage: { input_tokens: 0, output_tokens: 0, total_tokens: 0, input_tokens_details: { cached_tokens: 0 } },
      output_text: JSON.stringify({ status: "REVIEW_REQUIRED", answer: "Insufficient evidence.", claims: [] }),
    }), { status: 200 }),
  });
  assert.deepEqual((await provider.analyze(request)).usage, { input_tokens: 0, output_tokens: 0, total_tokens: 0, cached_input_tokens: 0 });
});

test("model generated metadata cannot replace trusted adapter metadata", async () => {
  const provider = createDeployedProvider({
    apiKey: "server-secret", model: "gpt-5-mini", baseUrl: "https://api.openai.com/v1",
    fetchImpl: async () => new Response(JSON.stringify({
      output_text: JSON.stringify({ status: "ANSWERED", answer: "A.", claims: [{ text: "A.", source_ids: ["SRC-1"] }], usage: { input_tokens: 0 } }),
    }), { status: 200 }),
  });
  await assert.rejects(() => provider.analyze(request), (error) => error.code === "INVALID_PROVIDER_OUTPUT");
});

test("deployed provider keeps an explicit bounded timeout", async () => {
  const provider = createDeployedProvider({
    apiKey: "server-secret", model: "gpt-test", baseUrl: "https://api.openai.com/v1", timeoutMs: 10,
    fetchImpl: async (_url, { signal }) => new Promise((resolve, reject) => {
      signal.addEventListener("abort", () => reject(new Error("aborted")), { once: true });
    }),
  });
  await assert.rejects(() => provider.analyze(request), (error) => error.code === "OPENAI_REQUEST_TIMEOUT");
});
