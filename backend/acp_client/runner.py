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
import json
import logging
import os
import pathlib
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable
from uuid import uuid4

from .registry import ACP_AGENTS

logger = logging.getLogger(__name__)

CODEX_MODEL_ALIASES = {
    "gpt-5.5": "gpt-5.5/low",
    "gpt-5.4": "gpt-5.4/low",
    "gpt-5.4-mini": "gpt-5.4-mini/low",
    "gpt-5.3-codex": "gpt-5.3-codex/low",
    "gpt-5.2": "gpt-5.2/low",
}


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


def _decode_process_output(data: bytes) -> str:
    return data.decode("utf-8", errors="replace").strip()


def _parse_bridge_error(stderr: bytes, stdout: bytes) -> str:
    stderr_text = _decode_process_output(stderr)
    stdout_text = _decode_process_output(stdout)

    for line in reversed(stderr_text.splitlines()):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue

        if isinstance(payload, dict):
            message = payload.get("error") or payload.get("message")
            error_name = payload.get("name")
            if message and error_name:
                return f"{error_name}: {message}"
            if message:
                return str(message)

    if stderr_text:
        return stderr_text[-2000:]
    if stdout_text:
        return stdout_text[-2000:]
    return "process exited without error output"


async def run_cursor_sdk_prompt(
    spec: Any,
    *,
    cwd: pathlib.Path,
    system_text: str,
    user_text: str,
    timeout_s: int,
    model_id: str = "",
    on_update: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> ACPResult:
    """Run a prompt through the local Cursor TypeScript SDK bridge."""
    start = time.monotonic()
    env = os.environ.copy()
    selected_model = model_id or spec.model
    if selected_model:
        env["REQLENS_CURSOR_SDK_MODEL"] = selected_model

    payload = {
        "cwd": str(cwd),
        "model": selected_model,
        "system_text": system_text,
        "user_text": user_text,
    }

    process = await asyncio.create_subprocess_exec(
        spec.command,
        *spec.args,
        cwd=str(cwd),
        env=env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(json.dumps(payload).encode("utf-8")),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise ACPTimeoutError(f"Agent {spec.id} timed out after {timeout_s}s")

    if process.returncode != 0:
        error_text = _parse_bridge_error(stderr, stdout)
        raise ACPError(f"Cursor SDK bridge failed: {error_text}")

    try:
        data = json.loads(_decode_process_output(stdout))
    except json.JSONDecodeError as e:
        raw_output = _decode_process_output(stdout)
        raise ACPError(f"Cursor SDK bridge returned invalid JSON: {raw_output}") from e

    raw_updates = data.get("raw_updates", [])
    metadata = {
        key: data[key]
        for key in ("agent_id", "run_id", "model", "duration_ms", "git")
        if key in data and data[key] is not None
    }
    if metadata:
        raw_updates.append({"type": "cursor_sdk_result", **metadata})

    if on_update:
        for update in raw_updates:
            await on_update(update)

    elapsed = int((time.monotonic() - start) * 1000)
    return ACPResult(
        text=data.get("text", ""),
        tool_calls=data.get("tool_calls", []),
        stop_reason=data.get("stop_reason", ""),
        raw_updates=raw_updates,
        latency_ms=elapsed,
        token_usage=data.get("token_usage", {}),
    )


class ReqLensACPClient:
    """
    Minimal ACP client implementation used when ReqLens drives external agents.

    ACP agents stream their actual answer through ``session/update`` messages;
    the final ``session/prompt`` response only reports why the turn stopped.
    This client accumulates text chunks and exposes safe read/write helpers for
    agents that ask the client to read files from the current project directory.
    """

    def __init__(
        self,
        *,
        cwd: pathlib.Path,
        on_update: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> None:
        self.cwd = cwd.resolve()
        self.on_update = on_update
        self.text_chunks: list[str] = []
        self.raw_updates: list[dict[str, Any]] = []
        self.tool_calls: list[dict[str, Any]] = []
        self.usage: dict[str, Any] = {}

    def _resolve_path(self, path: str) -> pathlib.Path:
        candidate = pathlib.Path(path)
        if not candidate.is_absolute():
            candidate = self.cwd / candidate
        resolved = candidate.resolve()
        if resolved != self.cwd and self.cwd not in resolved.parents:
            raise PermissionError(f"ACP file access outside workspace is not allowed: {path}")
        return resolved

    async def session_update(self, session_id: str, update: Any, **kwargs: Any) -> None:
        if hasattr(update, "model_dump"):
            raw_update = update.model_dump(by_alias=True, exclude_none=True)
        else:
            raw_update = {"update": update}
        self.raw_updates.append({"session_id": session_id, **raw_update})

        update_type = getattr(update, "session_update", None)
        if update_type == "agent_message_chunk":
            content = getattr(update, "content", None)
            text = getattr(content, "text", None)
            if text:
                self.text_chunks.append(text)
        elif update_type in {"tool_call", "tool_call_update"}:
            self.tool_calls.append(raw_update)
        elif update_type == "usage_update":
            self.usage = raw_update

        if self.on_update:
            await self.on_update(raw_update)

    async def request_permission(self, options: list[Any], session_id: str, tool_call: Any, **kwargs: Any) -> Any:
        from acp.schema import AllowedOutcome, DeniedOutcome, RequestPermissionResponse

        allow_option = next((option for option in options if getattr(option, "kind", None) == "allow_once"), None)
        if allow_option is None:
            return RequestPermissionResponse(outcome=DeniedOutcome(outcome="cancelled"))

        return RequestPermissionResponse(outcome=AllowedOutcome(outcome="selected", option_id=allow_option.option_id))

    async def read_text_file(
        self,
        path: str,
        session_id: str,
        limit: int | None = None,
        line: int | None = None,
        **kwargs: Any,
    ) -> Any:
        from acp.schema import ReadTextFileResponse

        resolved = self._resolve_path(path)
        text = resolved.read_text(encoding="utf-8", errors="replace")

        if line is not None or limit is not None:
            lines = text.splitlines(keepends=True)
            start = max((line or 1) - 1, 0)
            end = start + limit if limit is not None else None
            text = "".join(lines[start:end])

        return ReadTextFileResponse(content=text)

    async def write_text_file(self, content: str, path: str, session_id: str, **kwargs: Any) -> Any:
        from acp.schema import WriteTextFileResponse

        resolved = self._resolve_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return WriteTextFileResponse()

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        return {}

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        return None

    def on_connect(self, conn: Any) -> None:
        return None


async def run_acp_prompt(
    agent_id: str,
    *,
    cwd: pathlib.Path,
    system_text: str,
    user_text: str,
    model_id: str = "",
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
        model_id: Optional model override for agents that expose model selection.
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

    if spec.runner == "cursor-sdk":
        return await run_cursor_sdk_prompt(
            spec,
            cwd=cwd,
            system_text=system_text,
            user_text=user_text,
            model_id=model_id,
            timeout_s=timeout_s,
            on_update=on_update,
        )

    start = time.monotonic()
    if agent_id == "codex":
        selected_model = CODEX_MODEL_ALIASES.get(model_id, model_id) or spec.model or "gpt-5.5/low"
        model_id = selected_model
        system_text = (
            f"Use model {selected_model} for this ReqLens stage. "
            "Keep the final answer concise and machine-readable.\n\n"
            f"{system_text}"
        )

    try:
        # The ACP SDK provides spawn_agent_process which starts the agent CLI,
        # establishes a bidirectional connection, and returns a context manager.
        from acp import spawn_agent_process, text_block  # type: ignore[import-untyped]
        from acp.schema import AuthCapabilities, ClientCapabilities, FileSystemCapabilities, Implementation

        logger.info("Spawning ACP agent %s with command: %s %s", agent_id, spec.command, spec.args)

        client = ReqLensACPClient(cwd=cwd, on_update=on_update)
        async with spawn_agent_process(client, spec.command, *spec.args, cwd=str(cwd)) as (conn, process):
            # Initialize the ACP protocol handshake
            await conn.initialize(
                protocol_version=1,
                client_capabilities=ClientCapabilities(
                    auth=AuthCapabilities(terminal=False),
                    fs=FileSystemCapabilities(read_text_file=True, write_text_file=True),
                    terminal=False,
                    field_meta={"terminal_output": True},
                ),
                client_info=Implementation(name="reqlens", title="ReqLens", version="0.1.0"),
            )
            # Create a new agent session scoped to the project directory
            session = await conn.new_session(cwd=str(cwd), mcp_servers=[])
            if model_id:
                available_models = getattr(session.models, "available_models", None) if session.models else None
                available_model_ids = [model.model_id for model in available_models or []]
                if available_model_ids and model_id not in available_model_ids:
                    raise ACPError(
                        f"Model '{model_id}' is not available for {agent_id}. Available models: {available_model_ids}"
                    )
                if session.models is None:
                    raise ACPError(f"Agent {agent_id} does not expose ACP model selection")
                await conn.set_session_model(model_id=model_id, session_id=session.session_id)

            # Combine system and user prompts into a single message
            # (ACP's prompt API takes a list of content blocks)
            full_prompt = f"{system_text}\n\n{user_text}"
            response = await asyncio.wait_for(
                conn.prompt(
                    session_id=session.session_id,
                    prompt=[text_block(full_prompt)],
                    message_id=str(uuid4()),
                ),
                timeout=timeout_s,
            )

            elapsed = int((time.monotonic() - start) * 1000)
            usage = response.usage.model_dump(by_alias=True, exclude_none=True) if response.usage else client.usage
            return ACPResult(
                text="".join(client.text_chunks),
                tool_calls=client.tool_calls,
                stop_reason=response.stop_reason,
                raw_updates=client.raw_updates,
                latency_ms=elapsed,
                token_usage=usage,
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
