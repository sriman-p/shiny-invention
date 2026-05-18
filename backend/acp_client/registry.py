"""
Registry of available AI agents that can be invoked via the Agent Communication Protocol (ACP).

ACP is a protocol that allows ReqLens to communicate with various AI coding agents
(Claude Code, OpenAI Codex, Gemini CLI, etc.) through a uniform interface. Each agent
is a CLI tool that speaks ACP -- the runner module spawns the agent process, sends
prompts, and receives structured responses.

Each `AgentSpec` carries:
  - id: unique identifier used throughout the system to reference this agent
  - display_name: human-readable name shown in the UI
  - command: CLI command to invoke (must be on the system PATH)
  - args: command-line arguments to enable ACP mode
  - model: the agent's default model id
  - model_options: full flat catalog of model ids the agent supports (used for
    backwards-compatible flat dropdowns)
  - model_groups: optional grouped catalog (used by `<AgentModelPicker>` to
    render a tidy combobox); each group has a `label` and a list of model ids
  - env_required: environment variables that must be set (typically API keys)
  - notes: optional description for the UI

The agents_list API endpoint reads this registry to tell the frontend which
agents are available, whether they are properly configured, and the full set
of models the user can pick from for any run.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ModelGroup:
    """A labelled group of models within an agent's catalog."""

    label: str
    model_ids: list[str] = field(default_factory=list)


@dataclass
class AuthMode:
    """
    One way an agent can be authenticated.

    Agents like Claude Code accept multiple alternative auth backends
    (Anthropic API key, AWS Bedrock, GCP Vertex). Each mode lists the env
    vars required for that path; the agent is considered "authenticated"
    if AT LEAST ONE mode is fully satisfied.
    """

    id: str
    label: str
    env_required: list[str] = field(default_factory=list)
    notes: str = ""


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
        model_options: Flat list of known model IDs that the UI can offer.
        model_groups: Optional grouped list of models for richer UI rendering.
        env_required: Env vars that are ALWAYS required (in addition to any
            auth_mode). Most agents leave this empty and use auth_modes.
        auth_modes: Alternative auth modes -- ANY ONE being fully satisfied
            marks the agent authenticated. When `auth_modes` is empty the
            agent is authenticated as long as `env_required` is satisfied
            (or trivially when both are empty, e.g. the agent uses a local
            CLI login session).
        notes: Optional descriptive text shown in the agent list UI.
    """

    id: str
    display_name: str
    command: str
    args: list[str] = field(default_factory=list)
    runner: str = "acp"
    model: str | None = None
    model_options: list[str] = field(default_factory=list)
    model_groups: list[ModelGroup] = field(default_factory=list)
    env_required: list[str] = field(default_factory=list)
    auth_modes: list[AuthMode] = field(default_factory=list)
    notes: str = ""

    def serialize(self) -> dict:
        """Return a JSON-serializable view used by the agents_list endpoint."""
        return {
            "id": self.id,
            "display_name": self.display_name,
            "command": self.command,
            "args": list(self.args),
            "runner": self.runner,
            "model": self.model,
            "model_options": list(self.model_options),
            "model_groups": [{"label": group.label, "model_ids": list(group.model_ids)} for group in self.model_groups],
            "env_required": list(self.env_required),
            "auth_modes": [
                {
                    "id": mode.id,
                    "label": mode.label,
                    "env_required": list(mode.env_required),
                    "notes": mode.notes,
                }
                for mode in self.auth_modes
            ],
            "notes": self.notes,
        }


CURSOR_SDK_BRIDGE = Path(__file__).resolve().parent / "cursor_sdk" / "runner.mjs"


# ---------------------------------------------------------------------------
# Model catalogs
# ---------------------------------------------------------------------------
# These are intentionally exhaustive. Picking an agent in the UI surfaces the
# full per-agent catalog so users can compare e.g. every reasoning effort tier
# of Codex against every Claude Sonnet revision in a single sweep.


# Codex CLI: GPT-5.x family, each base model with low/medium/high/xhigh
# reasoning effort. Includes the "codex" reasoning model and 5.4-mini variants.
def _codex_groups() -> list[ModelGroup]:
    bases = ["gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.3-codex", "gpt-5.2"]
    efforts = ["low", "medium", "high", "xhigh"]
    return [ModelGroup(label=base.upper(), model_ids=[f"{base}/{effort}" for effort in efforts]) for base in bases]


CODEX_MODEL_GROUPS = _codex_groups()
CODEX_MODELS = [model for group in CODEX_MODEL_GROUPS for model in group.model_ids]


# Claude Code: the `@agentclientprotocol/claude-agent-acp` adapter exposes a
# small fixed set of model ids over ACP (visible via `session.models`). These
# are the slot names the adapter advertises -- internally they map to a
# concrete provider model (Anthropic API / Bedrock / Vertex).
#
# When running on Bedrock the adapter's internal mapping can drift behind
# Bedrock's actual catalog (so `sonnet` may resolve to a profile id that no
# longer exists in your account). The "Bedrock inference profiles" group
# lists currently-valid `us.anthropic.*` profile ids that ReqLens will pass
# verbatim via the ANTHROPIC_MODEL env var on the agent subprocess, side-
# stepping the adapter's mapping entirely. Update these as Bedrock evolves.
CLAUDE_MODEL_GROUPS = [
    ModelGroup(label="Adapter default", model_ids=["default"]),
    ModelGroup(label="Adapter shortcuts", model_ids=["sonnet[1m]", "opus[1m]", "haiku"]),
    ModelGroup(
        label="Bedrock inference profiles",
        model_ids=[
            "us.anthropic.claude-opus-4-1-20250805-v1:0",
            "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            "us.anthropic.claude-3-5-haiku-20241022-v1:0",
            "eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
            "apac.anthropic.claude-sonnet-4-5-20250929-v1:0",
        ],
    ),
]
CLAUDE_MODELS = [m for group in CLAUDE_MODEL_GROUPS for m in group.model_ids]


# Cursor router (Cursor Agent + Cursor SDK). Composer-2 plus every cross-provider
# model the router accepts.
CURSOR_MODEL_GROUPS = [
    ModelGroup(label="Cursor", model_ids=["composer-2", "agent-default"]),
    ModelGroup(
        label="Anthropic",
        model_ids=["claude-4-sonnet", "claude-4-opus", "claude-4-haiku", "claude-3-7-sonnet"],
    ),
    ModelGroup(
        label="Google",
        model_ids=["gemini-2.5-pro", "gemini-2.5-flash", "gemini-3-pro-preview"],
    ),
    ModelGroup(
        label="OpenAI",
        model_ids=["gpt-4.1", "gpt-4.1-mini", "o3", "o4-mini"],
    ),
]
CURSOR_MODELS = [m for group in CURSOR_MODEL_GROUPS for m in group.model_ids]


# Gemini CLI catalog.
GEMINI_MODEL_GROUPS = [
    ModelGroup(label="Default", model_ids=["agent-default"]),
    ModelGroup(label="Gemini 3", model_ids=["gemini-3-pro-preview"]),
    ModelGroup(
        label="Gemini 2.5",
        model_ids=["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"],
    ),
    ModelGroup(label="Gemini 2.0", model_ids=["gemini-2.0-flash"]),
    ModelGroup(label="Gemini 1.5", model_ids=["gemini-1.5-pro", "gemini-1.5-flash"]),
]
GEMINI_MODELS = [m for group in GEMINI_MODEL_GROUPS for m in group.model_ids]


# OpenCode multi-provider router presets.
OPENCODE_MODEL_GROUPS = [
    ModelGroup(label="Default", model_ids=["agent-default"]),
    ModelGroup(label="Qwen", model_ids=["qwen3-coder", "qwen2.5-coder"]),
    ModelGroup(label="Anthropic", model_ids=["claude-sonnet-4.5", "claude-opus-4.5"]),
    ModelGroup(label="OpenAI", model_ids=["gpt-5.5", "gpt-5.4", "o4-mini"]),
    ModelGroup(label="Google", model_ids=["gemini-2.5-pro", "gemini-2.5-flash"]),
    ModelGroup(label="Local", model_ids=["llama-3.3-70b", "qwen2.5-32b"]),
]
OPENCODE_MODELS = [m for group in OPENCODE_MODEL_GROUPS for m in group.model_ids]


# Kiro CLI catalog.
KIRO_MODEL_GROUPS = [
    ModelGroup(label="Default", model_ids=["agent-default"]),
    ModelGroup(label="Anthropic", model_ids=["claude-sonnet-4.5", "claude-haiku-4.5"]),
    ModelGroup(label="OpenAI", model_ids=["gpt-5.5", "gpt-4.1"]),
]
KIRO_MODELS = [m for group in KIRO_MODEL_GROUPS for m in group.model_ids]


# Blackbox CLI catalog.
BLACKBOX_MODEL_GROUPS = [
    ModelGroup(label="Default", model_ids=["agent-default"]),
    ModelGroup(label="Blackbox", model_ids=["blackbox-coder", "blackbox-reasoning"]),
    ModelGroup(label="Routed", model_ids=["claude-sonnet-4.5", "gpt-5.5", "gemini-2.5-pro"]),
]
BLACKBOX_MODELS = [m for group in BLACKBOX_MODEL_GROUPS for m in group.model_ids]


# Qwen Coder CLI catalog.
QWEN_MODEL_GROUPS = [
    ModelGroup(label="Default", model_ids=["agent-default"]),
    ModelGroup(label="Qwen 3", model_ids=["qwen3-coder", "qwen3-coder-plus"]),
    ModelGroup(label="Qwen 2.5", model_ids=["qwen2.5-coder", "qwen2.5-coder-32b", "qwen2.5-coder-7b"]),
]
QWEN_MODELS = [m for group in QWEN_MODEL_GROUPS for m in group.model_ids]


# Master registry of all supported ACP agents, keyed by agent ID.
# To add a new agent, add an entry here with its CLI command, requirements,
# and (ideally) a populated `model_groups` so the UI can render a grouped picker.
ACP_AGENTS: dict[str, AgentSpec] = {
    "claude-code": AgentSpec(
        id="claude-code",
        display_name="Claude Code",
        command="npx",
        args=["--yes", "@agentclientprotocol/claude-agent-acp@0.32.0"],
        model="default",
        model_options=CLAUDE_MODELS,
        model_groups=CLAUDE_MODEL_GROUPS,
        # Multiple auth modes -- any ONE being satisfied is enough.
        auth_modes=[
            AuthMode(
                id="local",
                label="Claude Code login session",
                env_required=[],
                notes=(
                    "Use the local `claude login` session that the Claude Code CLI "
                    "creates. No env vars needed, but the CLI must have been logged "
                    "in at least once on this machine."
                ),
            ),
            AuthMode(
                id="anthropic_api",
                label="Anthropic API key",
                env_required=["ANTHROPIC_API_KEY"],
                notes="Direct Anthropic API. Get a key at https://console.anthropic.com/.",
            ),
            AuthMode(
                id="bedrock",
                label="AWS Bedrock",
                env_required=[
                    "CLAUDE_CODE_USE_BEDROCK",
                    "AWS_REGION",
                ],
                notes=(
                    "Set CLAUDE_CODE_USE_BEDROCK=1 and AWS_REGION (e.g. us-east-1). "
                    "AWS credentials come from the standard chain: AWS_ACCESS_KEY_ID/"
                    "AWS_SECRET_ACCESS_KEY env vars, AWS_PROFILE, or the EC2/ECS/EKS "
                    "instance role. Optionally set ANTHROPIC_MODEL to a Bedrock "
                    "inference profile id like "
                    "us.anthropic.claude-sonnet-4-5-20250929-v1:0."
                ),
            ),
            AuthMode(
                id="vertex",
                label="GCP Vertex AI",
                env_required=[
                    "CLAUDE_CODE_USE_VERTEX",
                    "CLOUD_ML_REGION",
                    "ANTHROPIC_VERTEX_PROJECT_ID",
                ],
                notes=(
                    "Set CLAUDE_CODE_USE_VERTEX=1, CLOUD_ML_REGION, and "
                    "ANTHROPIC_VERTEX_PROJECT_ID. Application Default Credentials "
                    "(`gcloud auth application-default login`) provide the access "
                    "token."
                ),
            ),
        ],
        notes=(
            "Claude Agent SDK adapter over ACP. Model ids come from the adapter's "
            "session.models list (default / sonnet[1m] / opus[1m] / haiku). Supports "
            "Anthropic API, AWS Bedrock, and GCP Vertex backends -- pick whichever "
            "matches your environment."
        ),
    ),
    "codex": AgentSpec(
        id="codex",
        display_name="OpenAI Codex CLI",
        command="npx",
        args=["--yes", "@zed-industries/codex-acp@0.13.0"],
        model="gpt-5.5/low",
        model_options=CODEX_MODELS,
        model_groups=CODEX_MODEL_GROUPS,
        notes="Codex ACP adapter. Default ReqLens configuration uses GPT-5.5 with low reasoning effort.",
    ),
    "cursor": AgentSpec(
        id="cursor",
        display_name="Cursor Agent",
        command="cursor",
        args=["agent", "acp"],
        model="agent-default",
        model_options=CURSOR_MODELS,
        model_groups=CURSOR_MODEL_GROUPS,
        notes="Cursor Agent's native ACP server. Uses your Cursor login or CURSOR_API_KEY.",
    ),
    "cursor-sdk-composer-2": AgentSpec(
        id="cursor-sdk-composer-2",
        display_name="Cursor SDK (Composer 2)",
        command="node",
        args=[str(CURSOR_SDK_BRIDGE)],
        runner="cursor-sdk",
        model="composer-2",
        model_options=CURSOR_MODELS,
        model_groups=CURSOR_MODEL_GROUPS,
        env_required=["CURSOR_API_KEY"],
        notes="TypeScript SDK bridge using Composer 2. Cursor account billing and eligible discounts apply.",
    ),
    "gemini": AgentSpec(
        id="gemini",
        display_name="Gemini CLI",
        command="gemini",
        args=["--acp"],
        model="agent-default",
        model_options=GEMINI_MODELS,
        model_groups=GEMINI_MODEL_GROUPS,
        env_required=[],
        notes="Gemini CLI over ACP. Uses `gemini auth login` (Google OAuth) or GEMINI_API_KEY.",
    ),
    "opencode": AgentSpec(
        id="opencode",
        display_name="OpenCode",
        command="opencode",
        args=["acp"],
        model="agent-default",
        model_options=OPENCODE_MODELS,
        model_groups=OPENCODE_MODEL_GROUPS,
        env_required=[],
        notes="OpenCode CLI's multi-provider router. Picks the right backend for the chosen model.",
    ),
    "kiro": AgentSpec(
        id="kiro",
        display_name="Kiro CLI",
        command="kiro-cli",
        args=["acp"],
        model="agent-default",
        model_options=KIRO_MODELS,
        model_groups=KIRO_MODEL_GROUPS,
        env_required=[],
    ),
    "blackbox": AgentSpec(
        id="blackbox",
        display_name="Blackbox CLI",
        command="blackbox",
        args=["--experimental-acp"],
        model="agent-default",
        model_options=BLACKBOX_MODELS,
        model_groups=BLACKBOX_MODEL_GROUPS,
        env_required=["BLACKBOX_API_KEY"],
    ),
    "qwen-coder": AgentSpec(
        id="qwen-coder",
        display_name="Qwen Coder",
        command="qwen-coder",
        args=["acp"],
        model="agent-default",
        model_options=QWEN_MODELS,
        model_groups=QWEN_MODEL_GROUPS,
        env_required=[],
    ),
}
