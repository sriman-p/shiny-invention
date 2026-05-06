"""
Tests for the ACP agent registry and runner module.
"""

import pathlib
import sys

import pytest

from acp_client.registry import ACP_AGENTS, AgentSpec
from acp_client.runner import (
    ACPAgentNotFoundError,
    ACPEnvMissingError,
    ACPError,
    ACPTimeoutError,
    run_acp_prompt,
    run_cursor_sdk_prompt,
)


class TestAgentRegistry:
    def test_nine_agents_registered(self):
        assert len(ACP_AGENTS) == 9

    def test_claude_code_spec(self):
        spec = ACP_AGENTS["claude-code"]
        assert spec.display_name == "Claude Code"
        assert spec.command == "npx"
        assert "@agentclientprotocol/claude-agent-acp@0.32.0" in spec.args

    def test_codex_spec(self):
        spec = ACP_AGENTS["codex"]
        assert spec.command == "npx"
        assert "@zed-industries/codex-acp@0.13.0" in spec.args

    def test_cursor_spec(self):
        spec = ACP_AGENTS["cursor"]
        assert spec.command == "cursor"
        assert spec.args == ["agent", "acp"]

    def test_cursor_sdk_composer_2_spec(self):
        spec = ACP_AGENTS["cursor-sdk-composer-2"]
        assert spec.command == "node"
        assert spec.runner == "cursor-sdk"
        assert spec.model == "composer-2"
        assert "composer-2" in spec.model_options
        assert "CURSOR_API_KEY" in spec.env_required

    def test_gemini_spec(self):
        spec = ACP_AGENTS["gemini"]
        assert spec.command == "gemini"
        assert "--experimental-acp" in spec.args

    def test_agents_without_env_requirements(self):
        no_env = [a for a in ACP_AGENTS.values() if len(a.env_required) == 0]
        assert len(no_env) >= 6  # ACP adapters can use local CLI auth sessions

    def test_all_agents_have_ids(self):
        for agent_id, spec in ACP_AGENTS.items():
            assert spec.id == agent_id

    def test_all_agents_have_commands(self):
        for spec in ACP_AGENTS.values():
            assert spec.command
            assert len(spec.command) > 0

    def test_agent_spec_dataclass(self):
        spec = AgentSpec(
            id="test",
            display_name="Test Agent",
            command="test-cmd",
            args=["--acp"],
            runner="acp",
            env_required=["TEST_KEY"],
            notes="A test agent",
        )
        assert spec.id == "test"
        assert spec.notes == "A test agent"


class TestACPRunner:
    @pytest.mark.asyncio
    async def test_unknown_agent_raises(self):
        with pytest.raises(ACPAgentNotFoundError):
            await run_acp_prompt("nonexistent-agent", cwd=pathlib.Path("/tmp"), system_text="test", user_text="test")

    @pytest.mark.asyncio
    async def test_missing_env_raises(self):
        """Gemini requires GEMINI_API_KEY which is not set in test env."""
        import os

        old = os.environ.pop("GEMINI_API_KEY", None)
        try:
            with pytest.raises(ACPEnvMissingError):
                await run_acp_prompt("gemini", cwd=pathlib.Path("/tmp"), system_text="test", user_text="test")
        finally:
            if old:
                os.environ["GEMINI_API_KEY"] = old

    @pytest.mark.asyncio
    async def test_cursor_sdk_missing_env_raises(self):
        """The Cursor SDK bridge requires CURSOR_API_KEY."""
        import os

        old = os.environ.pop("CURSOR_API_KEY", None)
        try:
            with pytest.raises(ACPEnvMissingError):
                await run_acp_prompt(
                    "cursor-sdk-composer-2",
                    cwd=pathlib.Path("/tmp"),
                    system_text="test",
                    user_text="test",
                )
        finally:
            if old:
                os.environ["CURSOR_API_KEY"] = old

    @pytest.mark.asyncio
    async def test_cursor_sdk_runner_success_with_fake_bridge(self, tmp_path):
        bridge = tmp_path / "fake_bridge.py"
        bridge.write_text(
            """
import json
import os
import sys

payload = json.load(sys.stdin)
json.dump(
    {
        "text": f"{payload['system_text']} / {payload['user_text']}",
        "tool_calls": [{"type": "tool_call", "name": "read_file"}],
        "raw_updates": [{"type": "assistant", "text": "hello"}],
        "stop_reason": "finished",
        "run_id": "run-123",
        "agent_id": "agent-456",
        "model": {"id": os.environ["REQLENS_CURSOR_SDK_MODEL"]},
        "duration_ms": 42,
        "token_usage": {"total": 3},
    },
    sys.stdout,
)
""",
            encoding="utf-8",
        )
        spec = AgentSpec(
            id="cursor-sdk-test",
            display_name="Cursor SDK Test",
            command=sys.executable,
            args=[str(bridge)],
            runner="cursor-sdk",
            model="composer-2",
        )
        updates = []

        async def on_update(update):
            updates.append(update)

        result = await run_cursor_sdk_prompt(
            spec,
            cwd=tmp_path,
            system_text="system",
            user_text="user",
            timeout_s=5,
            on_update=on_update,
        )

        assert result.text == "system / user"
        assert result.tool_calls == [{"type": "tool_call", "name": "read_file"}]
        assert result.stop_reason == "finished"
        assert result.token_usage == {"total": 3}
        assert result.raw_updates[-1]["type"] == "cursor_sdk_result"
        assert result.raw_updates[-1]["model"] == {"id": "composer-2"}
        assert updates == result.raw_updates

    @pytest.mark.asyncio
    async def test_cursor_sdk_runner_uses_model_override(self, tmp_path):
        bridge = tmp_path / "fake_bridge.py"
        bridge.write_text(
            """
import json
import sys

payload = json.load(sys.stdin)
json.dump(
    {
        "text": payload["model"],
        "tool_calls": [],
        "raw_updates": [],
        "stop_reason": "finished",
        "model": {"id": payload["model"]},
    },
    sys.stdout,
)
""",
            encoding="utf-8",
        )
        spec = AgentSpec(
            id="cursor-sdk-test",
            display_name="Cursor SDK Test",
            command=sys.executable,
            args=[str(bridge)],
            runner="cursor-sdk",
            model="composer-2",
        )

        result = await run_cursor_sdk_prompt(
            spec,
            cwd=tmp_path,
            system_text="system",
            user_text="user",
            timeout_s=5,
            model_id="claude-4-sonnet",
        )

        assert result.text == "claude-4-sonnet"
        assert result.raw_updates[-1]["model"] == {"id": "claude-4-sonnet"}

    @pytest.mark.asyncio
    async def test_cursor_sdk_runner_reports_bridge_errors(self, tmp_path):
        bridge = tmp_path / "failing_bridge.py"
        bridge.write_text(
            """
import json
import sys

json.dump({"name": "BridgeError", "error": "boom"}, sys.stderr)
sys.exit(7)
""",
            encoding="utf-8",
        )
        spec = AgentSpec(
            id="cursor-sdk-test",
            display_name="Cursor SDK Test",
            command=sys.executable,
            args=[str(bridge)],
            runner="cursor-sdk",
            model="composer-2",
        )

        with pytest.raises(ACPError, match="BridgeError: boom"):
            await run_cursor_sdk_prompt(
                spec,
                cwd=tmp_path,
                system_text="system",
                user_text="user",
                timeout_s=5,
            )

    @pytest.mark.asyncio
    async def test_cursor_sdk_runner_reports_invalid_json(self, tmp_path):
        bridge = tmp_path / "invalid_json_bridge.py"
        bridge.write_text("import sys\nsys.stdout.write('not json')\n", encoding="utf-8")
        spec = AgentSpec(
            id="cursor-sdk-test",
            display_name="Cursor SDK Test",
            command=sys.executable,
            args=[str(bridge)],
            runner="cursor-sdk",
            model="composer-2",
        )

        with pytest.raises(ACPError, match="invalid JSON"):
            await run_cursor_sdk_prompt(
                spec,
                cwd=tmp_path,
                system_text="system",
                user_text="user",
                timeout_s=5,
            )

    @pytest.mark.asyncio
    async def test_cursor_sdk_runner_times_out(self, tmp_path):
        bridge = tmp_path / "slow_bridge.py"
        bridge.write_text("import time\ntime.sleep(10)\n", encoding="utf-8")
        spec = AgentSpec(
            id="cursor-sdk-test",
            display_name="Cursor SDK Test",
            command=sys.executable,
            args=[str(bridge)],
            runner="cursor-sdk",
            model="composer-2",
        )

        with pytest.raises(ACPTimeoutError, match="timed out"):
            await run_cursor_sdk_prompt(
                spec,
                cwd=tmp_path,
                system_text="system",
                user_text="user",
                timeout_s=0.05,
            )
