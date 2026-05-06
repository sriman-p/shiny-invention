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
    pass


class ACPTimeoutError(ACPError):
    pass


class ACPAgentNotFoundError(ACPError):
    pass


class ACPEnvMissingError(ACPError):
    pass


@dataclass
class ACPResult:
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
    if agent_id not in ACP_AGENTS:
        raise ACPAgentNotFoundError(f"Agent '{agent_id}' not found in registry")

    spec = ACP_AGENTS[agent_id]

    missing_env = [k for k in spec.env_required if not os.environ.get(k)]
    if missing_env:
        raise ACPEnvMissingError(f"Missing environment variables for {agent_id}: {missing_env}")

    start = time.monotonic()

    try:
        from acp import spawn_agent_process  # type: ignore[import-untyped]

        logger.info("Spawning ACP agent %s with command: %s %s", agent_id, spec.command, spec.args)

        async with spawn_agent_process(spec.command, *spec.args, cwd=str(cwd)) as (conn, process):
            await conn.initialize(protocol_version=1)
            session = await conn.new_session(cwd=str(cwd), mcp_servers=[])

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
