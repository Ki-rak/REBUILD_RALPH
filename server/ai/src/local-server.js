import http from "node:http";

import { ContractError } from "./evidence-contract.js";

class LocalServerError extends Error {
  constructor(code) {
    super(code);
    this.code = code;
  }
}

function isLoopbackHost(host) {
  const value = host.toLowerCase();
  return value === "localhost" || value === "127.0.0.1" || value === "::1";
}

function requestHostIsLoopback(hostHeader) {
  if (!hostHeader) return false;
  try {
    return isLoopbackHost(new URL(`http://${hostHeader}`).hostname.replace(/^\[|\]$/g, ""));
  } catch {
    return false;
  }
}

function originIsLoopback(origin) {
  if (!origin) return true;
  try {
    return isLoopbackHost(new URL(origin).hostname.replace(/^\[|\]$/g, ""));
  } catch {
    return false;
  }
}

function sendJson(response, status, body) {
  const encoded = JSON.stringify(body);
  response.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(encoded),
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
  });
  response.end(encoded);
}

async function readJson(request, maxBodyBytes) {
  const declared = Number(request.headers["content-length"] || 0);
  if (Number.isFinite(declared) && declared > maxBodyBytes) {
    throw new LocalServerError("BODY_TOO_LARGE");
  }
  let size = 0;
  const chunks = [];
  for await (const chunk of request) {
    size += chunk.length;
    if (size > maxBodyBytes) throw new LocalServerError("BODY_TOO_LARGE");
    chunks.push(chunk);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    throw new LocalServerError("INVALID_JSON");
  }
}

export function createLocalServer({
  provider,
  env,
  maxBodyBytes = 64 * 1024,
  maxConcurrent = 2,
  timeoutMs = 30_000,
}) {
  if (env !== "local" && env !== "demo") throw new LocalServerError("LOCAL_SERVER_ONLY");
  let active = 0;

  const server = http.createServer(async (request, response) => {
    if (!requestHostIsLoopback(request.headers.host) || !originIsLoopback(request.headers.origin)) {
      sendJson(response, 403, { error: "LOOPBACK_REQUEST_REQUIRED" });
      return;
    }

    if (request.method === "GET" && request.url === "/status") {
      try {
        const status = await provider.status();
        sendJson(response, 200, {
          component: "RE:Build Agent AI provider component test",
          environment: env,
          authentication: status.authentication || "UNKNOWN",
          inference: status.inference || "NOT_TESTED",
        });
      } catch {
        sendJson(response, 503, {
          component: "RE:Build Agent AI provider component test",
          environment: env,
          authentication: "UNKNOWN",
          inference: "NOT_TESTED",
        });
      }
      return;
    }

    if (request.method !== "POST" || request.url !== "/analyze") {
      sendJson(response, 404, { error: "NOT_FOUND" });
      return;
    }
    if (!String(request.headers["content-type"] || "").toLowerCase().startsWith("application/json")) {
      sendJson(response, 415, { error: "JSON_REQUIRED" });
      return;
    }
    if (active >= maxConcurrent) {
      sendJson(response, 429, { error: "ANALYSIS_BUSY" });
      return;
    }

    active += 1;
    const controller = new AbortController();
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);
    try {
      const timeoutPromise = new Promise((_, reject) => {
        controller.signal.addEventListener("abort", () => reject(new LocalServerError("ANALYSIS_TIMEOUT")), { once: true });
        if (controller.signal.aborted) reject(new LocalServerError("ANALYSIS_TIMEOUT"));
      });
      const operation = (async () => {
        const input = await readJson(request, maxBodyBytes);
        if (controller.signal.aborted) throw new LocalServerError("ANALYSIS_TIMEOUT");
        return provider.analyze(input, { signal: controller.signal });
      })();
      const answer = await Promise.race([operation, timeoutPromise]);
      sendJson(response, 200, answer);
    } catch (error) {
      if (timedOut || error?.code === "ANALYSIS_TIMEOUT") {
        sendJson(response, 504, { error: "ANALYSIS_TIMEOUT" });
        response.once("finish", () => request.destroy());
      } else if (error?.code === "BODY_TOO_LARGE") {
        sendJson(response, 413, { error: "BODY_TOO_LARGE" });
      } else if (error?.code === "INVALID_JSON" || error instanceof ContractError) {
        sendJson(response, 400, { error: error.code || "INVALID_REQUEST" });
      } else {
        sendJson(response, 502, { error: "ANALYSIS_FAILED" });
      }
    } finally {
      clearTimeout(timer);
      active -= 1;
    }
  });
  server.requestTimeout = timeoutMs + 2_000;
  server.headersTimeout = Math.min(10_000, timeoutMs + 1_000);

  return {
    server,
    async listen({ host = "127.0.0.1", port = 4319 } = {}) {
      if (!isLoopbackHost(host)) throw new LocalServerError("LOOPBACK_REQUIRED");
      await new Promise((resolve, reject) => {
        server.once("error", reject);
        server.listen(port, host, () => {
          server.off("error", reject);
          resolve();
        });
      });
    },
    close() {
      server.close();
    },
  };
}
