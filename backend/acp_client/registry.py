"""
Registry of available AI agents that can be invoked via the Agent Communication Protocol (ACP).

ACP is a protocol that allows ReqLens to communicate with various AI coding agents
(Claude Code, OpenAI Codex, Gemini CLI, etc.) through a uniform interface. Each agent
is a CLI tool that speaks ACP -- the runner module spawns the agent process, sends
prompts, and receives structured responses.

This registry defines the known agents with their:
  - id: unique identifier used throughout the system to reference this agent
  - display_name: human-readable name shown in the UI
  - command: CLI command to invoke (must be on the system PATH)
  - args: command-line arguments to enable ACP mode
  - env_required: environment variables that must be set (typically API keys)
  - notes: optional description for the UI

The agents_list API endpoint reads this registry to tell the frontend which
agents are available and whether they are properly configured (command on PATH
and all env vars set).
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AgentSpec:
    """
    Specification for a single agent runner.

    Attributes:
        id: Unique string identifier (e.g., "claude-code", "codex").
        display_name: Human-readable name for UI display.
        command: CLI executable name that must be on the system PATH.
        args: Additional CLI arguments to pass when invoking the agent.
        runner: How ReqLens should invoke this agent ("acp" or "cursor-sdk").
        model: Optional model id for SDK-backed runners.
        model_options: Known model IDs that the UI can offer up front.
        env_required: List of environment variable names that must be set
            for this agent to function (typically API keys).
        notes: Optional descriptive text shown in the agent list UI.
    """

    id: str
    display_name: str
    command: str
    args: list[str] = field(default_factory=list)
    runner: str = "acp"
    model: str | None = None
    model_options: list[str] = field(default_factory=list)
    env_required: list[str] = field(default_factory=list)
    notes: str = ""


CURSOR_SDK_BRIDGE = Path(__file__).resolve().parent / "cursor_sdk" / "runner.mjs"


# Master registry of all supported ACP agents, keyed by agent ID.
# To add a new agent, add an entry here with its CLI command and requirements.
ACP_AGENTS: dict[str, AgentSpec] = {
    "claude-code": AgentSpec(
        id="claude-code",
        display_name="Claude Code",
        command="npx",
        args=["--yes", "@agentclientprotocol/claude-agent-acp@0.32.0"],
        model="agent-default",
        model_options=[
            "agent-default",
            "claude-sonnet-4.5",
            "claude-opus-4.1",
            "claude-haiku-4.5",
            "claude-3-7-sonnet-latest",
        ],
        notes="Claude Agent SDK adapter over ACP. Uses your Claude Code auth or ANTHROPIC_API_KEY.",
    ),
    "codex": AgentSpec(
        id="codex",
        display_name="OpenAI Codex CLI",
        command="npx",
        args=["--yes", "@zed-industries/codex-acp@0.13.0"],
        model="gpt-5.5/low",
        model_options=[
            "gpt-5.5/low",
            "gpt-5.5/medium",
            "gpt-5.5/high",
            "gpt-5.5/xhigh",
            "gpt-5.4/low",
            "gpt-5.4/medium",
            "gpt-5.4/high",
            "gpt-5.4/xhigh",
            "gpt-5.4-mini/low",
            "gpt-5.4-mini/medium",
            "gpt-5.4-mini/high",
            "gpt-5.4-mini/xhigh",
            "gpt-5.3-codex/low",
            "gpt-5.3-codex/medium",
            "gpt-5.3-codex/high",
            "gpt-5.3-codex/xhigh",
            "gpt-5.2/low",
            "gpt-5.2/medium",
            "gpt-5.2/high",
            "gpt-5.2/xhigh",
        ],
        notes="Codex ACP adapter. Default ReqLens configuration uses GPT-5.5 with low reasoning effort.",
    ),
    "cursor": AgentSpec(
        id="cursor",
        display_name="Cursor Agent",
        command="cursor",
        args=["agent", "acp"],
        model="agent-default",
        model_options=[
            "agent-default",
            "composer-2",
            "claude-4-sonnet",
            "claude-4-opus",
            "gemini-2.5-pro",
            "gpt-4.1",
            "o3",
        ],
        notes="Cursor Agent's native ACP server. Uses your Cursor login or CURSOR_API_KEY.",
    ),
    "cursor-sdk-composer-2": AgentSpec(
        id="cursor-sdk-composer-2",
        display_name="Cursor SDK (Composer 2)",
        command="node",
        args=[str(CURSOR_SDK_BRIDGE)],
        runner="cursor-sdk",
        model="composer-2",
        model_options=[
            "composer-2",
            "claude-4-sonnet",
            "claude-4-opus",
            "gemini-2.5-pro",
            "gpt-4.1",
            "o3",
        ],
        env_required=["CURSOR_API_KEY"],
        notes="TypeScript SDK bridge using Composer 2. Cursor account billing and eligible discounts apply.",
    ),
    "gemini": AgentSpec(
        id="gemini",
        display_name="Gemini CLI",
        command="gemini",
        args=["--acp"],
        model="agent-default",
        model_options=[
            "agent-default",
            "gemini-3-pro-preview",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
        ],
        env_required=[],
        notes="Gemini CLI over ACP. Uses `gemini auth login` (Google OAuth) or GEMINI_API_KEY.",
    ),
    "opencode": AgentSpec(
        id="opencode",
        display_name="OpenCode",
        command="opencode",
        args=["acp"],
        model="agent-default",
        model_options=["agent-default", "qwen3-coder", "gpt-5.5", "claude-sonnet-4.5", "gemini-2.5-pro"],
        env_required=[],
    ),
    "kiro": AgentSpec(
        id="kiro",
        display_name="Kiro CLI",
        command="kiro-cli",
        args=["acp"],
        model="agent-default",
        model_options=["agent-default"],
        env_required=[],
    ),
    "blackbox": AgentSpec(
        id="blackbox",
        display_name="Blackbox CLI",
        command="blackbox",
        args=["--experimental-acp"],
        model="agent-default",
        model_options=["agent-default"],
        env_required=["BLACKBOX_API_KEY"],
    ),
    "qwen-coder": AgentSpec(
        id="qwen-coder",
        display_name="Qwen Coder",
        command="qwen-coder",
        args=["acp"],
        model="agent-default",
        model_options=["agent-default", "qwen3-coder", "qwen2.5-coder"],
        env_required=[],
    ),
}
