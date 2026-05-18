"""
Abstract base class and shared data structures for pipeline stages.

All pipeline stages inherit from the Stage ABC defined here. This module
provides the common interface and utility methods that every stage uses:
  - StageContext: carries all configuration needed to execute a stage
  - StageEvent: structure for emitting progress events during execution
    (types: agent_update, reasoning, acp_result, progress, ...)
  - Stage (ABC): defines the run() method that each stage must implement,
    plus helper methods for JSON extraction, output persistence, and the
    `emit_acp_events` helper that translates an ACPResult into the events
    the orchestrator listens for (token rollup + reasoning chunks).

The extract_json() method is particularly important because AI agents
return their responses in various formats (pure JSON, JSON in markdown
fences, JSON embedded in prose). This method tries multiple strategies
to reliably extract valid JSON from the response text.
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from pydantic import BaseModel

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_reasoning_chunks(raw_updates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Translate ACP/Cursor SDK raw update payloads into normalized ReasoningChunks.

    The orchestrator consumes ReasoningChunk dicts of the form:
        {"kind": <str>, "content": <str>, "metadata": <dict>, "ts": <iso str>}

    Where `kind` is one of:
      - thought          (agent_thought_chunk / Cursor "step" reasoning)
      - text             (agent_message_chunk / Cursor assistant text deltas)
      - tool_call        (tool_call / Cursor tool_use blocks)
      - tool_result      (tool_call_update with status=completed)
      - model_message    (cursor_sdk_result / final assistant)
      - status           (anything else worth a single line)

    Empty / unrecognized payloads return [].
    """
    chunks: list[dict[str, Any]] = []
    for update in raw_updates or []:
        if not isinstance(update, dict):
            continue
        ts = _now_iso()

        update_type = update.get("session_update") or update.get("type") or ""

        if update_type == "agent_message_chunk":
            content = update.get("content") or {}
            text = content.get("text") if isinstance(content, dict) else None
            if text:
                chunks.append({"kind": "text", "content": str(text), "metadata": {}, "ts": ts})
            continue

        if update_type == "agent_thought_chunk":
            content = update.get("content") or {}
            text = content.get("text") if isinstance(content, dict) else None
            if text:
                chunks.append({"kind": "thought", "content": str(text), "metadata": {}, "ts": ts})
            continue

        if update_type in {"tool_call", "tool_call_update"}:
            tool_name = update.get("tool_call_id") or update.get("name") or update.get("title") or "tool"
            status = update.get("status") or "started"
            is_completed_update = update_type == "tool_call_update" and status in {"completed", "failed"}
            kind = "tool_result" if is_completed_update else "tool_call"
            chunks.append(
                {
                    "kind": kind,
                    "content": str(tool_name),
                    "metadata": {k: v for k, v in update.items() if k not in {"session_id"}},
                    "ts": ts,
                }
            )
            continue

        if update_type == "delta":
            inner = update.get("update") or {}
            text = inner.get("text") if isinstance(inner, dict) else None
            if text:
                chunks.append({"kind": "text", "content": str(text), "metadata": {}, "ts": ts})
            continue

        if update_type == "step":
            step = update.get("step") or {}
            label = step.get("title") if isinstance(step, dict) else None
            kind = "thought" if (label and "think" in str(label).lower()) else "tool_call"
            chunks.append(
                {
                    "kind": kind,
                    "content": str(label or "step"),
                    "metadata": step if isinstance(step, dict) else {},
                    "ts": ts,
                }
            )
            continue

        if update_type == "assistant":
            blocks = update.get("message", {})
            content = blocks.get("content") if isinstance(blocks, dict) else None
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "text" and block.get("text"):
                        chunks.append({"kind": "text", "content": str(block["text"]), "metadata": {}, "ts": ts})
                    elif block.get("type") == "tool_use":
                        chunks.append(
                            {
                                "kind": "tool_call",
                                "content": str(block.get("name") or "tool"),
                                "metadata": block,
                                "ts": ts,
                            }
                        )
            else:
                text = update.get("text")
                if text:
                    chunks.append({"kind": "text", "content": str(text), "metadata": {}, "ts": ts})
            continue

        if update_type == "cursor_sdk_result":
            chunks.append(
                {
                    "kind": "model_message",
                    "content": "Cursor SDK run finished",
                    "metadata": {k: v for k, v in update.items() if k != "type"},
                    "ts": ts,
                }
            )
            continue

    return chunks


@dataclass
class StageContext:
    """
    Configuration and context passed to each pipeline stage.

    Carries everything a stage needs to execute: project identifiers,
    agent configuration, file paths, and the artifacts directory where
    stage outputs are saved.

    Attributes:
        project_id: UUID string of the project being analyzed.
        project_name: Human-readable project name (for logging/display).
        run_id: UUID string of the current pipeline run.
        agent_id: Which AI agent to invoke for this stage.
        model_id: Optional model override for agents that support model choice.
        prompt_strategy: How to structure the prompt (e.g., "zero_shot").
        context_mode: How much code context to include (e.g., "full").
        code_path: Filesystem path to the project's source code.
        requirements_path: Filesystem path to the requirements document.
        artifacts_dir: Directory where stage output JSON files are saved.
        retrieval_index: Optional pre-built retrieval index for code search.
        permission_mode: "auto" (default) auto-approves agent permission
            requests; any other value triggers the human-in-the-loop flow.
        on_permission_request: Optional async callback the orchestrator wires
            to broadcast `permission_required` SSE events to the UI.
    """

    project_id: str
    project_name: str
    run_id: str
    agent_id: str
    prompt_strategy: str
    context_mode: str
    code_path: str
    requirements_path: str
    artifacts_dir: str
    model_id: str = ""
    retrieval_index: Any = None
    permission_mode: str = "auto"
    on_permission_request: Any = None  # Callable[[dict], Awaitable[None]] | None


@dataclass
class StageEvent:
    """
    Progress event emitted during stage execution.

    Stages can emit events to provide real-time feedback (e.g., "processing
    requirement 3 of 10"). These events are forwarded through the orchestrator
    to the SSE stream.

    Attributes:
        type: Event type string (e.g., "progress", "warning").
        run_id: UUID string of the current pipeline run.
        stage: Name of the emitting stage.
        payload: Arbitrary data associated with the event.
        timestamp: ISO 8601 timestamp string.
    """

    type: str
    run_id: str
    stage: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""


class Stage(ABC):
    """
    Abstract base class for all pipeline stages.

    Each concrete stage (ParseStage, AnalyzeStage, etc.) must implement the
    run() method. The base class provides:
      - extract_json(): robust JSON extraction from agent response text
      - save_output(): persist stage output to the artifacts directory
    """

    name: str = ""

    @abstractmethod
    async def run(
        self,
        ctx: StageContext,
        previous_output: BaseModel | None,
        on_event: Callable[[StageEvent], Awaitable[None]],
    ) -> BaseModel: ...

    def extract_json(self, text: str) -> dict[str, Any]:
        """
        Extract a JSON object from agent response text.

        AI agents may return JSON in various formats. This method tries
        three strategies in order:
          1. Look for JSON inside markdown code fences (```json ... ```)
          2. Try parsing the entire text as JSON
          3. Find the outermost { ... } braces and parse that substring

        Args:
            text: The raw response text from the AI agent.

        Returns:
            The parsed JSON as a Python dict.

        Raises:
            json.JSONDecodeError: If no valid JSON can be extracted.
        """
        # Strategy 1: Extract JSON from markdown code fences
        pattern = r"```(?:json)?\s*\n(.*?)\n```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        # Strategy 2: Try parsing the entire response as JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Strategy 3: Find the outermost curly braces and parse that substring
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            raise

    def select_output_fields(self, data: dict[str, Any], *fields: str) -> dict[str, Any]:
        """Keep only contract fields from an agent response.

        Agents sometimes echo JSON Schema metadata such as ``$defs`` or
        ``properties`` beside the actual stage output. The contracts are strict
        about extra fields, so strip non-contract keys before validation.
        """
        return {field: data[field] for field in fields if field in data}

    def save_output(self, ctx: StageContext, output: BaseModel) -> None:
        """
        Persist the stage's structured output to a JSON file in the artifacts directory.

        The file is named after the stage (e.g., parse.json, analyze.json) and
        contains the pretty-printed JSON representation of the output model.

        Args:
            ctx: The stage context containing the artifacts directory path.
            output: The Pydantic model to serialize and save.
        """
        output_dir = Path(ctx.artifacts_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{self.name}.json"
        output_path.write_text(output.model_dump_json(indent=2))

    async def emit_acp_events(
        self,
        ctx: StageContext,
        on_event: Callable[["StageEvent"], Awaitable[None]],
        result: Any,
    ) -> None:
        """
        Forward ACPResult-derived events to the orchestrator.

        Emits two kinds of events:
          1. `acp_result` — carries `token_usage` so the orchestrator can roll
             it up into `StageExecution.token_usage`.
          2. `reasoning` — one event per normalized ReasoningChunk extracted
             from the result's raw_updates. The orchestrator persists these
             on `StageExecution.reasoning` and broadcasts them as SSE so the
             UI can render a Cursor/opencode-grade thought timeline.

        Stages call this helper once after every `run_acp_prompt` invocation.
        """
        token_usage = getattr(result, "token_usage", None) or {}
        await on_event(
            StageEvent(
                type="acp_result",
                run_id=ctx.run_id,
                stage=self.name,
                payload={"token_usage": token_usage, "latency_ms": getattr(result, "latency_ms", 0)},
            )
        )

        raw_updates = getattr(result, "raw_updates", []) or []
        for chunk in _extract_reasoning_chunks(raw_updates):
            await on_event(
                StageEvent(
                    type="reasoning",
                    run_id=ctx.run_id,
                    stage=self.name,
                    payload=chunk,
                )
            )
