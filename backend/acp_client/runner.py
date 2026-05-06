"""
ACP (Agent Communication Protocol) runner -- executes prompts against AI coding agents.

This module provides the core function `run_acp_prompt` which:
  1. Looks up the agent in the registry
  2. Validates that required environment variables are set
  3. Spawns the agent CLI process via the ACP SDK
  4. Sends a prompt (system + user text) and waits for the response
  5. Returns a structured ACPResult with the response text and timing metrics

If the ACP SDK is not installed, the runner returns a mock response instead of
failing. This allows development and testing without needing actual agent CLIs.

Error hierarchy:
  - ACPError: base exception for all ACP-related errors
  - ACPTimeoutError: agent took longer than the configured timeout
  - ACPAgentNotFoundError: agent_id not found in the registry
  - ACPEnvMissingError: required environment variables are not set

The pipeline stages use this runner to invoke their assigned agents. Each stage
constructs a system prompt (role/instructions) and user prompt (data/schema),
then calls run_acp_prompt and parses the JSON response.
"""

import asyncio
import logging
import os
import pathlib
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from .registry import ACP_AGENTS

logger = logging.getLogger(__name__)


class ACPError(Exception):
    """Base exception for all ACP-related errors."""

    pass


class ACPTimeoutError(ACPError):
    """Raised when an ACP agent exceeds its timeout limit."""

    pass


class ACPAgentNotFoundError(ACPError):
    """Raised when the requested agent_id is not in the ACP registry."""

    pass


class ACPEnvMissingError(ACPError):
    """Raised when required environment variables for an agent are not set."""

    pass


@dataclass
class ACPResult:
    """
    Structured result from an ACP agent invocation.

    Attributes:
        text: The agent's response text (may contain JSON in markdown fences).
        tool_calls: Any tool calls the agent made during execution.
        stop_reason: Why the agent stopped (e.g., "end_turn", "mock").
        raw_updates: Raw streaming updates received during execution.
        latency_ms: Wall-clock time in milliseconds for the entire call.
        token_usage: Token consumption breakdown (prompt, completion, total).
    """

    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    stop_reason: str = ""
    raw_updates: list[dict[str, Any]] = field(default_factory=list)
    latency_ms: int = 0
    token_usage: dict[str, Any] = field(default_factory=dict)


async def run_acp_prompt(
    agent_id: str,
    *,
    cwd: pathlib.Path,
    system_text: str,
    user_text: str,
    timeout_s: int = 600,
    on_update: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> ACPResult:
    """
    Send a prompt to an ACP agent and return the structured result.

    Args:
        agent_id: Identifier of the agent to invoke (must exist in ACP_AGENTS registry).
        cwd: Working directory for the agent process (typically the project's code_path).
        system_text: System-level instructions that define the agent's role.
        user_text: User-level prompt containing data and expected output schema.
        timeout_s: Maximum seconds to wait for the agent's response (default: 600s / 10min).
        on_update: Optional async callback invoked for each streaming update from the agent.

    Returns:
        ACPResult with the agent's response text, latency, and token usage.

    Raises:
        ACPAgentNotFoundError: If agent_id is not in the registry.
        ACPEnvMissingError: If required environment variables are missing.
        ACPTimeoutError: If the agent exceeds the timeout.
        ACPError: For any other agent failure.
    """
    if agent_id not in ACP_AGENTS:
        raise ACPAgentNotFoundError(f"Agent '{agent_id}' not found in registry")

    spec = ACP_AGENTS[agent_id]

    # Check that all required API keys / env vars are set before spawning the process
    missing_env = [k for k in spec.env_required if not os.environ.get(k)]
    if missing_env:
        raise ACPEnvMissingError(f"Missing environment variables for {agent_id}: {missing_env}")

    start = time.monotonic()

    try:
        # The ACP SDK provides spawn_agent_process which starts the agent CLI,
        # establishes a bidirectional connection, and returns a context manager.
        from acp import spawn_agent_process  # type: ignore[import-untyped]

        logger.info("Spawning ACP agent %s with command: %s %s", agent_id, spec.command, spec.args)

        async with spawn_agent_process(spec.command, *spec.args, cwd=str(cwd)) as (conn, process):
            # Initialize the ACP protocol handshake
            await conn.initialize(protocol_version=1)
            # Create a new agent session scoped to the project directory
            session = await conn.new_session(cwd=str(cwd), mcp_servers=[])

            # Combine system and user prompts into a single message
            # (ACP's prompt API takes a list of content blocks)
            full_prompt = f"{system_text}\n\n{user_text}"
            response = await asyncio.wait_for(
                conn.prompt(session.id, [{"type": "text", "text": full_prompt}]),
                timeout=timeout_s,
            )

            elapsed = int((time.monotonic() - start) * 1000)
            return ACPResult(
                text=response.text if hasattr(response, "text") else str(response),
                latency_ms=elapsed,
            )

    except ImportError:
        # ACP SDK not installed -- return a mock response so development can
        # proceed without real agent CLIs. The pipeline stages handle this
        # gracefully by falling back to empty outputs.
        logger.warning("ACP SDK not installed; returning mock result for agent %s", agent_id)
        elapsed = int((time.monotonic() - start) * 1000)
        return ACPResult(
            text=f"[Mock ACP response from {agent_id}] No ACP SDK available.",
            latency_ms=elapsed,
            stop_reason="mock",
        )
    except asyncio.TimeoutError:
        raise ACPTimeoutError(f"Agent {agent_id} timed out after {timeout_s}s")
    except Exception as e:
        logger.exception("ACP agent %s failed: %s", agent_id, e)
        raise ACPError(f"Agent {agent_id} failed: {e}") from e
