// Only adapter-owned, allowlisted telemetry is returned; model-generated JSON is validated separately.
function tokenCount(value) {
  return Number.isSafeInteger(value) && value >= 0 ? value : null;
}

function modelName(value) {
  return typeof value === "string" && /^(?:gpt|chatgpt|codex|o[1-9])[a-zA-Z0-9._:-]{0,120}$/.test(value)
    ? value : null;
}

export function responseMetadata({ provider, authMode, requestedModel, reportedModel, usage, cachedInputTokens }) {
  return {
    execution: {
      provider,
      auth_mode: authMode,
      state: "SUCCEEDED",
      source: "MODEL_CALL",
      cache_hit: false,
      model: modelName(reportedModel),
      requested_model: modelName(requestedModel),
    },
    usage: {
      input_tokens: tokenCount(usage?.input_tokens),
      output_tokens: tokenCount(usage?.output_tokens),
      total_tokens: tokenCount(usage?.total_tokens),
      cached_input_tokens: tokenCount(cachedInputTokens),
    },
  };
}