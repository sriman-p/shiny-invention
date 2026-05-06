from dataclasses import dataclass, field


@dataclass
class AgentSpec:
    id: str
    display_name: str
    command: str
    args: list[str] = field(default_factory=list)
    env_required: list[str] = field(default_factory=list)
    notes: str = ""


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
