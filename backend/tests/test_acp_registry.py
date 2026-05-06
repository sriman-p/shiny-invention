"""
Tests for the ACP agent registry and runner module.
"""
import pytest
from acp_client.registry import ACP_AGENTS, AgentSpec
from acp_client.runner import ACPAgentNotFoundError, ACPEnvMissingError, run_acp_prompt
import pathlib


class TestAgentRegistry:
    def test_seven_agents_registered(self):
        assert len(ACP_AGENTS) == 7

    def test_claude_code_spec(self):
        spec = ACP_AGENTS["claude-code"]
        assert spec.display_name == "Claude Code"
        assert spec.command == "claude"
        assert "ANTHROPIC_API_KEY" in spec.env_required

    def test_codex_spec(self):
        spec = ACP_AGENTS["codex"]
        assert spec.command == "codex"
        assert "OPENAI_API_KEY" in spec.env_required

    def test_gemini_spec(self):
        spec = ACP_AGENTS["gemini"]
        assert spec.command == "gemini"
        assert "--experimental-acp" in spec.args

    def test_agents_without_env_requirements(self):
        no_env = [a for a in ACP_AGENTS.values() if len(a.env_required) == 0]
        assert len(no_env) >= 3  # opencode, kiro, qwen-coder

    def test_all_agents_have_ids(self):
        for agent_id, spec in ACP_AGENTS.items():
            assert spec.id == agent_id

    def test_all_agents_have_commands(self):
        for spec in ACP_AGENTS.values():
            assert spec.command
            assert len(spec.command) > 0

    def test_agent_spec_dataclass(self):
        spec = AgentSpec(id="test", display_name="Test Agent", command="test-cmd",
                         args=["--acp"], env_required=["TEST_KEY"], notes="A test agent")
        assert spec.id == "test"
        assert spec.notes == "A test agent"


class TestACPRunner:
    @pytest.mark.asyncio
    async def test_unknown_agent_raises(self):
        with pytest.raises(ACPAgentNotFoundError):
            await run_acp_prompt("nonexistent-agent", cwd=pathlib.Path("/tmp"),
                                 system_text="test", user_text="test")

    @pytest.mark.asyncio
    async def test_missing_env_raises(self):
        """Claude-code requires ANTHROPIC_API_KEY which is not set in test env."""
        import os
        old = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            with pytest.raises(ACPEnvMissingError):
                await run_acp_prompt("claude-code", cwd=pathlib.Path("/tmp"),
                                     system_text="test", user_text="test")
        finally:
            if old:
                os.environ["ANTHROPIC_API_KEY"] = old
