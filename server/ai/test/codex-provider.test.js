import test from "node:test";
import assert from "node:assert/strict";
import os from "node:os";
import path from "node:path";

import { createCodexProvider } from "../src/codex-provider.js";

const request = {
  question: "What is supported?",
  evidence: [{ id: "SRC-1", text: "Item A is supported.", location: "page 2" }],
};

test("Codex provider uses an empty temp cwd and disables tools, web, network, and approvals", async () => {
  let clientOptions;
  let threadOptions;
  class FakeCodex {
    constructor(options) { clientOptions = options; }
    startThread(options) {
      threadOptions = options;
      return {
        runStreamed: async () => ({ events: (async function* () {
          yield {
            type: "item.completed",
            item: {
              id: "m1",
              type: "agent_message",
              text: JSON.stringify({
                status: "ANSWERED",
                answer: "Item A is supported.",
                claims: [{ text: "Item A is supported.", source_ids: ["SRC-1"] }],
              }),
            },
          };
          yield { type: "turn.completed", usage: null };
        })() }),
      };
    }
  }

  const provider = createCodexProvider({
    CodexClass: FakeCodex,
    codexHome: path.join(os.tmpdir(), "rebuild-codex-home-test"),
    parentEnv: { PATH: "safe", OPENAI_API_KEY: "must-not-leak" },
    model: "gpt-oauth-test",
    statusChecker: async () => "LOGGED_IN",
  });
  const answer = await provider.analyze(request);

  assert.equal(answer.status, "ANSWERED");
  assert.equal(clientOptions.env.OPENAI_API_KEY, undefined);
  assert.equal(clientOptions.config.forced_login_method, "chatgpt");
  assert.equal(clientOptions.config.features.shell_tool, false);
  assert.equal(clientOptions.config.features.unified_exec, false);
  assert.equal(clientOptions.config.features.apps, false);
  assert.equal(clientOptions.config.features.multi_agent, false);
  assert.equal(clientOptions.config.features.hooks, false);
  assert.equal(clientOptions.config.features.goals, false);
  assert.equal(clientOptions.config.features.memories, false);
  assert.equal(clientOptions.config.features.code_mode.enabled, false);
  assert.equal(clientOptions.config.tools.view_image, false);
  assert.deepEqual(clientOptions.config.mcp_servers, {});
  assert.equal(clientOptions.configOverrides, undefined);
  assert.equal(threadOptions.sandboxMode, "read-only");
  assert.equal(threadOptions.approvalPolicy, "never");
  assert.equal(threadOptions.networkAccessEnabled, false);
  assert.equal(threadOptions.webSearchMode, "disabled");
  assert.equal(threadOptions.webSearchEnabled, false);
  assert.equal(threadOptions.skipGitRepoCheck, true);
  assert.equal(threadOptions.model, "gpt-oauth-test");
  assert.ok(path.resolve(threadOptions.workingDirectory).startsWith(path.resolve(os.tmpdir())));
  assert.ok(!path.resolve(threadOptions.workingDirectory).startsWith(path.resolve(process.cwd(), "..", "..")));
});

test("Codex provider rejects any tool or action event", async () => {
  let aborted = false;
  class ToolCallingCodex {
    startThread() {
      return {
        runStreamed: async (_prompt, { signal }) => ({ events: (async function* () {
          signal.addEventListener("abort", () => { aborted = true; }, { once: true });
          yield {
            type: "item.started",
            item: { id: "cmd1", type: "command_execution", command: "dir", aggregated_output: "", status: "in_progress" },
          };
        })() }),
      };
    }
  }
  const provider = createCodexProvider({
    CodexClass: ToolCallingCodex,
    codexHome: path.join(os.tmpdir(), "rebuild-codex-home-test"),
    parentEnv: { PATH: "safe" },
    statusChecker: async () => "LOGGED_IN",
  });

  await assert.rejects(() => provider.analyze(request), (error) => error.code === "TOOL_EVENT_REJECTED");
  assert.equal(aborted, true);
});

test("Codex provider refuses inference when official login is not ready", async () => {
  class MustNotRunCodex {
    startThread() { throw new Error("must not run"); }
  }
  const provider = createCodexProvider({
    CodexClass: MustNotRunCodex,
    codexHome: path.join(os.tmpdir(), "rebuild-codex-home-test"),
    parentEnv: { PATH: "safe" },
    statusChecker: async () => "NOT_LOGGED_IN",
  });

  await assert.rejects(() => provider.analyze(request), (error) => error.code === "CODEX_LOGIN_REQUIRED");
});
