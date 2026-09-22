import { responseMetadata } from "./response-metadata.js";
import {
  ContractError,
  evidenceOutputSchema,
  buildEvidencePrompt,
  parseAnalyzeRequest,
  validateProviderAnswer,
} from "./evidence-contract.js";
import { DEFAULT_OPENAI_BASE_URL } from "./runtime-config.js";

export class ProviderError extends Error {
  constructor(code) {
    super(code);
    this.name = "ProviderError";
    this.code = code;
  }
}

function responseText(payload) {
  if (typeof payload?.output_text === "string") return payload.output_text;
  if (!Array.isArray(payload?.output)) throw new ProviderError("INVALID_OPENAI_RESPONSE");
  for (const item of payload.output) {
    if (!Array.isArray(item?.content)) continue;
    for (const content of item.content) {
      if (content?.type === "output_text" && typeof content.text === "string") return content.text;
    }
  }
  throw new ProviderError("INVALID_OPENAI_RESPONSE");
}

function parseJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    throw new ProviderError("INVALID_PROVIDER_JSON");
  }
}

export function createDeployedProvider({
  apiKey,
  model,
  baseUrl,
  fetchImpl = fetch,
  timeoutMs = 90_000,
}) {
  if (baseUrl !== DEFAULT_OPENAI_BASE_URL) throw new ProviderError("OPENAI_BASE_URL_FORBIDDEN");
  return {
    async status() {
      return {
        provider: "openai-responses",
        authentication: apiKey ? "CONFIGURED_UNTESTED" : "NOT_CONFIGURED",
        inference: "NOT_TESTED",
      };
    },

    async analyze(input, options = {}) {
      const request = parseAnalyzeRequest(input);
      const allowedIds = new Set(request.evidence.map(({ id }) => id));
      const timeoutController = new AbortController();
      const timeout = setTimeout(() => timeoutController.abort(), timeoutMs);
      const signal = options.signal
        ? AbortSignal.any([options.signal, timeoutController.signal])
        : timeoutController.signal;
      try {
        const response = await fetchImpl(`${baseUrl}/responses`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${apiKey}`,
            "content-type": "application/json",
          },
          body: JSON.stringify({
            model,
            store: false,
            input: buildEvidencePrompt(request),
            tools: [],
            text: {
              format: {
                type: "json_schema",
                name: "rebuild_evidence_answer",
                strict: true,
                schema: evidenceOutputSchema(request),
              },
            },
          }),
          signal,
        });
        if (!response.ok) {
          const code = response.status === 401 || response.status === 403 ? "OPENAI_AUTH_FAILED"
            : response.status === 429 ? "OPENAI_RATE_LIMITED"
            : response.status === 400 || response.status === 404 ? "OPENAI_INVALID_REQUEST"
            : response.status >= 500 ? "OPENAI_UNAVAILABLE" : "OPENAI_REQUEST_FAILED";
          throw new ProviderError(code);
        }
        let payload;
        try {
          payload = await response.json();
        } catch {
          throw new ProviderError("INVALID_OPENAI_RESPONSE");
        }
        const answer = validateProviderAnswer(parseJson(responseText(payload)), allowedIds);
        return {
          ...answer,
          ...responseMetadata({
            provider: "openai-responses",
            authMode: "OPENAI_API_KEY",
            requestedModel: model,
            reportedModel: payload.model,
            usage: payload.usage,
            cachedInputTokens: payload.usage?.input_tokens_details?.cached_tokens,
          }),
        };
      } catch (error) {
        if (error instanceof ProviderError || error instanceof ContractError) throw error;
        if (signal.aborted) throw new ProviderError("OPENAI_REQUEST_TIMEOUT");
        throw new ProviderError("OPENAI_REQUEST_FAILED");
      } finally {
        clearTimeout(timeout);
      }
    },
  };
}
