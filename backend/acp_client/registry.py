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


@dataclass
class AgentSpec:
    """
    Specification for a single ACP-compatible AI agent.

    Attributes:
        id: Unique string identifier (e.g., "claude-code", "codex").
        display_name: Human-readable name for UI display.
        command: CLI executable name that must be on the system PATH.
        args: Additional CLI arguments to pass when invoking the agent.
        env_required: List of environment variable names that must be set
            for this agent to function (typically API keys).
        notes: Optional descriptive text shown in the agent list UI.
    """

    id: str
    display_name: str
    command: str
    args: list[str] = field(default_factory=list)
    env_required: list[str] = field(default_factory=list)
    notes: str = ""


# Master registry of all supported ACP agents, keyed by agent ID.
# To add a new agent, add an entry here with its CLI command and requirements.
ACP_AGENTS: dict[str, AgentSpec] = {
    "claude-code": AgentSpec(
        id="claude-code",
        display_name="Claude Code",
        command="claude",
        args=["acp"],
        env_required=["ANTHROPIC_API_KEY"],
        notes="Anthropic's coding agent over ACP.",
    ),
    "codex": AgentSpec(
        id="codex",
        display_name="OpenAI Codex CLI",
        command="codex",
        args=["acp"],
        env_required=["OPENAI_API_KEY"],
    ),
    "gemini": AgentSpec(
        id="gemini",
        display_name="Gemini CLI",
        command="gemini",
        args=["--experimental-acp"],
        env_required=["GEMINI_API_KEY"],
    ),
    "opencode": AgentSpec(
        id="opencode",
        display_name="OpenCode",
        command="opencode",
        args=["acp"],
        env_required=[],
    ),
    "kiro": AgentSpec(
        id="kiro",
        display_name="Kiro CLI",
        command="kiro-cli",
        args=["acp"],
        env_required=[],
    ),
    "blackbox": AgentSpec(
        id="blackbox",
        display_name="Blackbox CLI",
        command="blackbox",
        args=["--experimental-acp"],
        env_required=["BLACKBOX_API_KEY"],
    ),
    "qwen-coder": AgentSpec(
        id="qwen-coder",
        display_name="Qwen Coder",
        command="qwen-coder",
        args=["acp"],
        env_required=[],
    ),
}
