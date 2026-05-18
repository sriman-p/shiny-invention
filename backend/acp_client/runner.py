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


MODEL_SELECTION_SENTINELS = {"", "default", "agent-default"}


def _resolve_advertised_model_id(model_id: str, available_model_ids: list[str]) -> str:
    """Resolve friendly model ids to ACP-advertised ids with option suffixes.

    Cursor Agent advertises ids like ``composer-2[fast=true]`` while the UI's
    static catalog may submit ``composer-2``. Prefer the exact id, then a single
    bracket-suffixed match, and otherwise let the caller decide how to proceed.
    """
    if model_id in MODEL_SELECTION_SENTINELS:
        return ""
    if model_id in available_model_ids:
        return model_id

    prefixed_matches = [candidate for candidate in available_model_ids if candidate.split("[", 1)[0] == model_id]
    if len(prefixed_matches) == 1:
        return prefixed_matches[0]
    return ""


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
    except asyncio.CancelledError:
        # Cooperative cancellation from the orchestrator's cancel watcher --
        # terminate the bridge subprocess so it doesn't keep streaming after
        # the run row has flipped to "cancelled".
        if process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        raise

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
        run_id: str | None = None,
        permission_mode: str = "auto",
        on_permission_request: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> None:
        self.cwd = cwd.resolve()
        self.on_update = on_update
        self.text_chunks: list[str] = []
        self.raw_updates: list[dict[str, Any]] = []
        self.tool_calls: list[dict[str, Any]] = []
        self.usage: dict[str, Any] = {}
        self.run_id = run_id or ""
        # "auto" (default) auto-approves all permission requests so non-interactive
        # runs Just Work. Any other value means the client will register the
        # permission request via `acp_client.permissions.handle_permission_request`
        # and wait for a human to resolve it via the REST endpoint.
        self.permission_mode = permission_mode
        self.on_permission_request = on_permission_request

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
        """
        Handle an ACP permission request.

        In `auto` mode we eagerly approve any `allow_once` option so headless
        runs proceed without human input. In any other mode we register a
        pending permission via `acp_client.permissions.handle_permission_request`,
        broadcast a `permission_required` SSE so the UI can prompt the user,
        and wait up to 5 minutes for the REST endpoint to resolve it.
        """
        from uuid import uuid4

        from acp.schema import AllowedOutcome, DeniedOutcome, RequestPermissionResponse

        from .permissions import handle_permission_request

        allow_option = next((option for option in options if getattr(option, "kind", None) == "allow_once"), None)
        deny_response = RequestPermissionResponse(outcome=DeniedOutcome(outcome="cancelled"))
        approve_response = (
            RequestPermissionResponse(outcome=AllowedOutcome(outcome="selected", option_id=allow_option.option_id))
            if allow_option is not None
            else deny_response
        )

        if self.permission_mode == "auto" or not self.run_id:
            return approve_response

        prompt_id = str(uuid4())
        if self.on_permission_request is not None:
            try:
                tool_summary: dict[str, Any]
                if hasattr(tool_call, "model_dump"):
                    tool_summary = tool_call.model_dump(by_alias=True, exclude_none=True)
                elif isinstance(tool_call, dict):
                    tool_summary = tool_call
                else:
                    tool_summary = {"repr": repr(tool_call)}
                option_summaries = [
                    {
                        "option_id": getattr(opt, "option_id", None),
                        "kind": getattr(opt, "kind", None),
                        "label": getattr(opt, "label", None),
                    }
                    for opt in options
                ]
                await self.on_permission_request(
                    {
                        "run_id": self.run_id,
                        "prompt_id": prompt_id,
                        "session_id": session_id,
                        "tool_call": tool_summary,
                        "options": option_summaries,
                    }
                )
            except Exception as exc:  # pragma: no cover - best effort broadcast
                logger.debug("permission_required broadcast failed: %s", exc)

        decision = await handle_permission_request(self.run_id, prompt_id, mode=self.permission_mode)
        outcome = decision.get("outcome") if isinstance(decision, dict) else None
        if outcome in {"allowed_once", "allow_once", "selected"} and allow_option is not None:
            return approve_response
        return deny_response

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


async def discover_agent_models(agent_id: str, *, cwd: pathlib.Path | None = None, timeout_s: int = 60) -> list[str]:
    """
    Spawn the agent's CLI just long enough to read `session.models.available_models`.

    Returns the actual model ids the adapter advertises so the UI never asks
    the user to pick a model the adapter would reject. Returns an empty list
    when the agent doesn't expose model selection over ACP, or when the SDK
    isn't installed (mock environment).

    Cached by `core.views.agent_models` with a short TTL so the cold-start
    cost of `npx --yes <package>` is amortised.
    """
    if agent_id not in ACP_AGENTS:
        raise ACPAgentNotFoundError(f"Agent '{agent_id}' not found in registry")

    spec = ACP_AGENTS[agent_id]
    missing_env = [k for k in spec.env_required if not os.environ.get(k)]
    if missing_env:
        raise ACPEnvMissingError(f"Missing environment variables for {agent_id}: {missing_env}")

    # The Cursor SDK bridge doesn't speak ACP; its catalog lives in the
    # registry. Returning an empty list signals "use the static catalog".
    if spec.runner != "acp":
        return []

    work_dir = cwd or pathlib.Path.cwd()

    try:
        from acp import spawn_agent_process
        from acp.schema import (
            AuthCapabilities,
            ClientCapabilities,
            FileSystemCapabilities,
            Implementation,
        )
    except ImportError:
        # ACP SDK not installed -- fall back to the static catalog.
        return []

    client = ReqLensACPClient(cwd=work_dir, on_update=None, run_id="discover")
    try:
        async with spawn_agent_process(
            client, spec.command, *spec.args, cwd=str(work_dir), env=os.environ.copy()
        ) as (conn, _process):
            await asyncio.wait_for(
                conn.initialize(
                    protocol_version=1,
                    client_capabilities=ClientCapabilities(
                        auth=AuthCapabilities(terminal=False),
                        fs=FileSystemCapabilities(read_text_file=True, write_text_file=False),
                        terminal=False,
                        field_meta={"terminal_output": True},
                    ),
                    client_info=Implementation(name="reqlens-discover", title="ReqLens", version="0.1.0"),
                ),
                timeout=timeout_s,
            )
            session = await asyncio.wait_for(conn.new_session(cwd=str(work_dir), mcp_servers=[]), timeout=timeout_s)
            models = getattr(session.models, "available_models", None) if session.models else None
            return [str(m.model_id) for m in models or [] if getattr(m, "model_id", None)]
    except asyncio.TimeoutError as exc:
        raise ACPTimeoutError(f"discover_agent_models({agent_id}) timed out after {timeout_s}s") from exc
    except Exception as exc:
        # Surface as ACPError so the view can return a sensible 5xx response.
        raise ACPError(f"discover_agent_models({agent_id}) failed: {exc}") from exc


async def run_acp_prompt(
    agent_id: str,
    *,
    cwd: pathlib.Path,
    system_text: str,
    user_text: str,
    model_id: str = "",
    timeout_s: int = 600,
    on_update: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    run_id: str = "",
    permission_mode: str = "auto",
    on_permission_request: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
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

        client = ReqLensACPClient(
            cwd=cwd,
            on_update=on_update,
            run_id=run_id,
            permission_mode=permission_mode,
            on_permission_request=on_permission_request,
        )
        # Explicitly forward the parent process env so Bedrock/Vertex/proxy
        # vars (CLAUDE_CODE_USE_BEDROCK, AWS_*, ANTHROPIC_VERTEX_*, HTTPS_PROXY, ...)
        # always reach the agent CLI, independent of how the SDK chose to default.
        # If the user passed a fully-qualified provider model id (e.g. a Bedrock
        # inference profile like `us.anthropic.claude-opus-4-1-20250805-v1:0`)
        # that the adapter doesn't advertise via session.models, we pass it as
        # ANTHROPIC_MODEL so the adapter's env-var fallback picks it up. We
        # decide AFTER spawn whether to call set_session_model or rely on this
        # env-var path -- but it's simpler to set the env var unconditionally
        # for every non-empty model_id and let set_session_model take precedence
        # when the id is in the advertised list.
        spawn_env = os.environ.copy()
        if agent_id == "claude-code" and model_id and model_id not in MODEL_SELECTION_SENTINELS:
            spawn_env["ANTHROPIC_MODEL"] = model_id
        async with spawn_agent_process(
            client, spec.command, *spec.args, cwd=str(cwd), env=spawn_env
        ) as (conn, process):
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
            should_select_model = model_id not in MODEL_SELECTION_SENTINELS
            if should_select_model:
                available_models = getattr(session.models, "available_models", None) if session.models else None
                available_model_ids = [model.model_id for model in available_models or []]
                resolved_model_id = _resolve_advertised_model_id(model_id, available_model_ids)
                if resolved_model_id:
                    # Model id matches one the adapter advertises -- use the
                    # ACP-native selection path.
                    if resolved_model_id != model_id:
                        logger.info(
                            "Resolved model '%s' to advertised %s model id '%s'",
                            model_id,
                            agent_id,
                            resolved_model_id,
                        )
                    await conn.set_session_model(model_id=resolved_model_id, session_id=session.session_id)
                elif session.models is None:
                    # Adapter doesn't expose ACP model selection at all and the
                    # caller asked for a specific model. Claude Code supports
                    # ANTHROPIC_MODEL passthrough for direct provider routing;
                    # other adapters should keep their own default.
                    if agent_id == "claude-code":
                        logger.info(
                            "Agent %s has no ACP model selection; relying on ANTHROPIC_MODEL=%s in subprocess env",
                            agent_id,
                            model_id,
                        )
                    else:
                        logger.info("Agent %s has no ACP model selection; using adapter default", agent_id)
                else:
                    # Model id is fully-qualified (e.g. a Bedrock inference
                    # profile like `us.anthropic.claude-opus-4-1-20250805-v1:0`)
                    # that the adapter's session.models list doesn't advertise.
                    # Claude Code can route those through ANTHROPIC_MODEL; for
                    # other adapters, avoid passing provider-specific env vars
                    # and let the adapter use its default model.
                    passthrough = agent_id == "claude-code"
                    logger.info(
                        "Model '%s' not in %s adapter's advertised list (%s); %s",
                        model_id,
                        agent_id,
                        available_model_ids,
                        "falling back to ANTHROPIC_MODEL env var"
                        if passthrough
                        else "using adapter default",
                    )
                    if on_update:
                        await on_update(
                            {
                                "type": "model_passthrough" if passthrough else "model_unavailable",
                                "model_id": model_id,
                                "agent_id": agent_id,
                                "message": (
                                    f"Model '{model_id}' is not in the adapter's advertised list. "
                                    + (
                                        "Passing it as ANTHROPIC_MODEL so the adapter routes it directly "
                                        "to the upstream provider (Anthropic / Bedrock / Vertex)."
                                        if passthrough
                                        else "Using the adapter default model instead."
                                    )
                                ),
                            }
                        )

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
