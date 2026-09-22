import { responseMetadata } from "./response-metadata.js";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { Codex } from "@openai/codex-sdk";

import { buildCodexEnvironment } from "./runtime-config.js";
import {
  ContractError,
  buildEvidencePrompt,
  evidenceOutputSchema,
  parseAnalyzeRequest,
  validateProviderAnswer,
} from "./evidence-contract.js";
import { ProviderError } from "./deployed-provider.js";

const FORBIDDEN_ITEM_TYPES = new Set([
  "command_execution",
  "file_change",
  "mcp_tool_call",
  "web_search",
]);

function parseJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    throw new ProviderError("INVALID_PROVIDER_JSON");
  }
}

function linkAbortSignal(source, target) {
  if (!source) return () => {};
  if (source.aborted) target.abort();
  const abort = () => target.abort();
  source.addEventListener("abort", abort, { once: true });
  return () => source.removeEventListener("abort", abort);
}

export function createCodexProvider({
  CodexClass = Codex,
  codexHome,
  parentEnv = process.env,
  statusChecker,
  model,
  timeoutMs = 90_000,
}) {
  const client = new CodexClass({
    env: buildCodexEnvironment(parentEnv, codexHome),
    config: {
      forced_login_method: "chatgpt",
      web_search: "disabled",
      mcp_servers: {},
      tools: { view_image: false },
      features: {
        shell_tool: false,
        unified_exec: false,
        apps: false,
        multi_agent: false,
        hooks: false,
        goals: false,
        memories: false,
        code_mode: { enabled: false },
      },
    },
  });

  return {
    async status() {
      const authentication = statusChecker ? await statusChecker() : "UNKNOWN";
      return { provider: "codex-oauth", authentication, inference: "NOT_TESTED" };
    },

    async analyze(input, options = {}) {
      if (statusChecker && await statusChecker() !== "LOGGED_IN") {
        throw new ProviderError("CODEX_LOGIN_REQUIRED");
      }
      const request = parseAnalyzeRequest(input);
      const allowedIds = new Set(request.evidence.map(({ id }) => id));
      const workDir = await fs.mkdtemp(path.join(os.tmpdir(), "rebuild-agent-ai-"));
      const controller = new AbortController();
      const unlink = linkAbortSignal(options.signal, controller);
      let timedOut = false;
      const timeout = setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, timeoutMs);
      let finalResponse;
      let usage;
      let completed = false;
      try {
        const thread = client.startThread({
          model,
          workingDirectory: workDir,
          skipGitRepoCheck: true,
          sandboxMode: "read-only",
          approvalPolicy: "never",
          networkAccessEnabled: false,
          webSearchMode: "disabled",
          webSearchEnabled: false,
          additionalDirectories: [],
        });
        const { events } = await thread.runStreamed(buildEvidencePrompt(request), {
          outputSchema: evidenceOutputSchema(request),
          signal: controller.signal,
        });
        for await (const event of events) {
          const item = event.item;
          if (event.type === "turn.completed") {
            usage = event.usage;
            completed = true;
          }
          if (item && FORBIDDEN_ITEM_TYPES.has(item.type)) {
            controller.abort();
            throw new ProviderError("TOOL_EVENT_REJECTED");
          }
          if (event.type === "error" || event.type === "turn.failed" || item?.type === "error") {
            throw new ProviderError("CODEX_TURN_FAILED");
          }
          if (event.type === "item.completed" && item?.type === "agent_message") {
            finalResponse = item.text;
          }
        }
        if (!finalResponse) throw new ProviderError("EMPTY_CODEX_RESPONSE");
        if (!completed) throw new ProviderError("CODEX_TURN_INCOMPLETE");
        const answer = validateProviderAnswer(parseJson(finalResponse), allowedIds);
        return {
          ...answer,
          ...responseMetadata({
            provider: "codex-oauth",
            authMode: "CHATGPT_OAUTH",
            requestedModel: model,
            reportedModel: null,
            usage,
            cachedInputTokens: usage?.cached_input_tokens,
          }),
        };
      } catch (error) {
        if (timedOut) throw new ProviderError("CODEX_TIMEOUT");
        if (error instanceof ProviderError || error instanceof ContractError) throw error;
        throw new ProviderError("CODEX_TURN_FAILED");
      } finally {
        clearTimeout(timeout);
        unlink();
        const resolved = path.resolve(workDir);
        const tempRoot = `${path.resolve(os.tmpdir())}${path.sep}`;
        if (resolved.startsWith(tempRoot)) await fs.rm(resolved, { recursive: true, force: true });
      }
    },
  };
}
