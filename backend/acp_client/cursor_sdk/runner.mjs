#!/usr/bin/env node

import { Agent } from "@cursor/sdk";

const DEFAULT_MODEL = "composer-2";

function readStdin() {
  return new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => {
      data += chunk;
    });
    process.stdin.on("end", () => resolve(data));
    process.stdin.on("error", reject);
  });
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function parseJsonEnv(name, fallback) {
  const value = process.env[name];
  if (!value) {
    return fallback;
  }

  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

function parseSettingSources(input) {
  if (Array.isArray(input)) {
    return input;
  }

  const fromEnv = process.env.REQLENS_CURSOR_SDK_SETTING_SOURCES;
  if (!fromEnv) {
    return undefined;
  }

  const parsed = parseJsonEnv("REQLENS_CURSOR_SDK_SETTING_SOURCES", undefined);
  if (Array.isArray(parsed)) {
    return parsed;
  }

  return fromEnv
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
}

function parseSandboxOptions(input) {
  if (input && typeof input === "object") {
    return input;
  }

  if (typeof input === "boolean") {
    return { enabled: input };
  }

  const fromEnv = process.env.REQLENS_CURSOR_SDK_SANDBOX_ENABLED;
  if (fromEnv === "true" || fromEnv === "1") {
    return { enabled: true };
  }

  if (fromEnv === "false" || fromEnv === "0") {
    return { enabled: false };
  }

  return undefined;
}

function collectMessageText(message) {
  if (message?.type === "assistant") {
    return asArray(message.message?.content)
      .filter((block) => block?.type === "text" && typeof block.text === "string")
      .map((block) => block.text)
      .join("");
  }

  return "";
}

function collectToolCall(message) {
  if (message?.type === "tool_call") {
    return message;
  }

  if (message?.type !== "assistant") {
    return undefined;
  }

  const toolBlocks = asArray(message.message?.content).filter((block) => block?.type === "tool_use");
  if (toolBlocks.length === 0) {
    return undefined;
  }

  return { type: "assistant_tool_use", agent_id: message.agent_id, run_id: message.run_id, blocks: toolBlocks };
}

function toErrorPayload(error) {
  if (error instanceof Error) {
    return {
      error: error.message,
      name: error.name,
      stack: error.stack,
      cause: error.cause ? String(error.cause) : undefined,
    };
  }

  return { error: String(error) };
}

async function main() {
  const input = JSON.parse(await readStdin());
  const cwd = input.cwd || process.cwd();
  const model = input.model || process.env.REQLENS_CURSOR_SDK_MODEL || DEFAULT_MODEL;
  const prompt = [input.system_text, input.user_text].filter(Boolean).join("\n\n");
  const mcpServers = input.mcp_servers || input.mcpServers || parseJsonEnv("REQLENS_CURSOR_SDK_MCP_SERVERS", undefined);
  const agents = input.agents || parseJsonEnv("REQLENS_CURSOR_SDK_SUBAGENTS", undefined);
  const settingSources = parseSettingSources(input.setting_sources || input.settingSources);
  const sandboxOptions = parseSandboxOptions(input.sandbox_options ?? input.sandboxOptions ?? input.sandbox_enabled);

  if (!process.env.CURSOR_API_KEY) {
    throw new Error("CURSOR_API_KEY is required for the Cursor TypeScript SDK bridge.");
  }

  const local = { cwd };
  if (settingSources) {
    local.settingSources = settingSources;
  }
  if (sandboxOptions) {
    local.sandboxOptions = sandboxOptions;
  }

  const agent = await Agent.create({
    apiKey: process.env.CURSOR_API_KEY,
    model: { id: model },
    local,
    name: input.name || process.env.REQLENS_CURSOR_SDK_NAME || "ReqLens Cursor SDK",
    ...(input.agent_id || input.agentId || process.env.REQLENS_CURSOR_SDK_AGENT_ID
      ? { agentId: input.agent_id || input.agentId || process.env.REQLENS_CURSOR_SDK_AGENT_ID }
      : {}),
    ...(mcpServers ? { mcpServers } : {}),
    ...(agents ? { agents } : {}),
  });

  const rawUpdates = [];
  const toolCalls = [];
  const textChunks = [];

  try {
    const run = await agent.send(prompt, {
      model: { id: model },
      ...(mcpServers ? { mcpServers } : {}),
      local: { force: input.force ?? true },
      onDelta: ({ update }) => {
        rawUpdates.push({ type: "delta", update });
      },
      onStep: ({ step }) => {
        rawUpdates.push({ type: "step", step });
      },
    });

    if (run.supports("stream")) {
      for await (const message of run.stream()) {
        rawUpdates.push(message);

        const toolCall = collectToolCall(message);
        if (toolCall) {
          toolCalls.push(toolCall);
        }

        const text = collectMessageText(message);
        if (text) {
          textChunks.push(text);
        }
      }
    } else {
      rawUpdates.push({ type: "stream_unsupported", reason: run.unsupportedReason("stream") });
    }

    const result = run.supports("wait") ? await run.wait() : undefined;
    const text = result?.result || run.result || textChunks.join("") || "";

    process.stdout.write(
      JSON.stringify({
        text,
        tool_calls: toolCalls,
        raw_updates: rawUpdates,
        stop_reason: result?.status || run.status || "finished",
        run_id: result?.id || run.id,
        agent_id: run.agentId || agent.agentId,
        model: result?.model || run.model || agent.model || { id: model },
        duration_ms: result?.durationMs || run.durationMs,
        git: result?.git || run.git,
        token_usage: {},
      }),
    );
  } finally {
    agent.close();
  }
}

main().catch((error) => {
  console.error(JSON.stringify(toErrorPayload(error)));
  process.exit(1);
});
