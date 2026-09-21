import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";

import { createLocalServer } from "../src/local-server.js";

async function startServer(options = {}) {
  const provider = options.provider ?? {
    status: async () => ({ authentication: "NOT_LOGGED_IN", inference: "NOT_TESTED" }),
    analyze: async () => ({ status: "REVIEW_REQUIRED", answer: "Insufficient evidence.", claims: [] }),
  };
  const app = createLocalServer({ provider, env: "local", ...options });
  await app.listen({ host: "127.0.0.1", port: 0 });
  const address = app.server.address();
  return { app, url: `http://127.0.0.1:${address.port}` };
}

function rawStatus(url, headers) {
  return new Promise((resolve, reject) => {
    const request = http.get(`${url}/status`, { headers }, (response) => {
      response.resume();
      response.on("end", () => resolve(response.statusCode));
    });
    request.on("error", reject);
  });
}

test("component server refuses hosted/deployed mode and public binds", async () => {
  assert.throws(() => createLocalServer({ provider: {}, env: "deployed" }), (error) => error.code === "LOCAL_SERVER_ONLY");
  const app = createLocalServer({ provider: {}, env: "local" });
  await assert.rejects(() => app.listen({ host: "0.0.0.0", port: 0 }), (error) => error.code === "LOOPBACK_REQUIRED");
});

test("status is sanitized and invalid Host or Origin is rejected", async (t) => {
  const { app, url } = await startServer();
  t.after(() => app.close());

  const status = await fetch(`${url}/status`);
  assert.equal(status.status, 200);
  assert.deepEqual(await status.json(), {
    component: "RE:Build Agent AI provider component test",
    environment: "local",
    authentication: "NOT_LOGGED_IN",
    inference: "NOT_TESTED",
  });

  assert.equal(await rawStatus(url, { host: "evil.example" }), 403);
  const badOrigin = await fetch(`${url}/status`, { headers: { origin: "https://evil.example" } });
  assert.equal(badOrigin.status, 403);
});

test("analyze enforces body and concurrency limits", async (t) => {
  let release;
  const blocked = new Promise((resolve) => { release = resolve; });
  const provider = {
    status: async () => ({}),
    analyze: async () => { await blocked; return { status: "REVIEW_REQUIRED", answer: "done", claims: [] }; },
  };
  const { app, url } = await startServer({ provider, maxBodyBytes: 120, maxConcurrent: 1 });
  t.after(() => { release(); app.close(); });

  const oversized = await fetch(`${url}/analyze`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question: "x".repeat(200), evidence: [] }),
  });
  assert.equal(oversized.status, 413);

  const first = fetch(`${url}/analyze`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question: "x", evidence: [] }),
  });
  await new Promise((resolve) => setTimeout(resolve, 20));
  const second = await fetch(`${url}/analyze`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question: "x", evidence: [] }),
  });
  assert.equal(second.status, 429);
  release();
  assert.equal((await first).status, 200);
});

test("analyze times out without leaking internal errors", async (t) => {
  const provider = {
    status: async () => ({}),
    analyze: async (_request, { signal }) => new Promise((resolve, reject) => {
      signal.addEventListener("abort", () => reject(new Error("secret internal timeout detail")), { once: true });
    }),
  };
  const { app, url } = await startServer({ provider, timeoutMs: 20 });
  t.after(() => app.close());

  const response = await fetch(`${url}/analyze`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question: "x", evidence: [] }),
  });
  assert.equal(response.status, 504);
  assert.deepEqual(await response.json(), { error: "ANALYSIS_TIMEOUT" });
});

test("slow request bodies time out before any provider call", async (t) => {
  let calls = 0;
  const { app, url } = await startServer({ timeoutMs: 30, provider: {
    status: async () => ({}),
    analyze: async () => { calls++; return {}; },
  } });
  t.after(() => app.close());
  const result = await new Promise((resolve, reject) => {
    const req = http.request(url + "/analyze", {
      method:"POST", headers: {"content-type":"application/json", "content-length":"200"},
    }, (res) => {
      let body = ""; res.on("data", (data) => { body += data; });
      res.on("end", () => resolve({status:res.statusCode,body}));
    });
    req.on("error", reject);
    req.write('{"question":"');
  });
  assert.equal(result.status, 504);
  assert.equal(JSON.parse(result.body).error, "ANALYSIS_TIMEOUT");
  assert.equal(calls, 0);
});
