"""
Pipeline orchestrator -- coordinates the sequential execution of all pipeline stages.

This is the "conductor" of the ReqLens pipeline. When a run is triggered, the
orchestrator:
  1. Loads the Run and Project from the database
  2. Sets the run status to "running"
  3. Iterates through stages in order: parse -> analyze -> map -> generate -> critique -> trace
  4. For each stage:
     a. Looks up the agent config (which agent, prompt strategy, context mode)
     b. Creates a StageExecution record snapshotting the input payload
     c. Builds a StageContext with all needed configuration
     d. Spawns the stage in an asyncio Task with a parallel cancel watcher so
        cancellations interrupt long-running tool calls instead of waiting for
        the next agent_update event
     e. Saves the stage result, rolling up token usage from acp_result events
        and emitting SSE events for both raw_updates and normalized reasoning
  5. If any stage fails, marks the run as failed and stops
  6. If all stages succeed, marks the run as succeeded

The orchestrator also writes BackgroundTask heartbeats so the AppConfig.ready()
recovery path can reap stale runs after a process restart.

Events are emitted via the on_event callback, which the views module wires up
to the SSE broadcast system. Event types include:
  - run_started, run_succeeded, run_failed, run_cancelled
  - stage_started, stage_completed, stage_failed, stage_cancelled, stage_progress
  - stage_agent_update (raw ACP/SDK payloads)
  - stage_reasoning (normalized ReasoningChunk dicts)
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from asgiref.sync import sync_to_async
from pydantic import BaseModel

from .contracts import AnalyzeOutput, CritiqueOutput, GenerateOutput, MapOutput, ParseOutput, TraceOutput
from .stages import STAGE_CLASSES, STAGE_ORDER
from .stages.base import StageContext, StageEvent

logger = logging.getLogger(__name__)
MAX_STAGE_ATTEMPTS = 3


class RunCancelledError(Exception):
    """Raised when a run is cancelled mid-execution."""


class StageOutputValidationError(ValueError):
    """Raised when a stage returned schema-valid but semantically empty output."""


EXPECTED_STAGE_OUTPUTS: dict[str, type[BaseModel]] = {
    "parse": ParseOutput,
    "analyze": AnalyzeOutput,
    "map": MapOutput,
    "generate": GenerateOutput,
    "critique": CritiqueOutput,
    "trace": TraceOutput,
}


def _now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string for event timestamps."""
    return datetime.now(timezone.utc).isoformat()


def _sum_token_usage(usage: dict[str, Any] | None) -> int:
    """Sum every numeric value in a token-usage dict, ignoring nested structures.

    ACP and Cursor SDK report different shapes (`input`/`output`, `prompt_tokens`/
    `completion_tokens`, `total`). We sum any numeric leaf so the rollup is
    robust against either schema.
    """
    if not isinstance(usage, dict):
        return 0
    total = 0
    for value in usage.values():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            total += int(value)
    return total


def _merge_token_usage(into: dict[str, Any], extra: dict[str, Any] | None) -> dict[str, Any]:
    """Merge two token-usage dicts by summing numeric leaves under the same key."""
    if not isinstance(extra, dict):
        return into
    result = dict(into)
    for key, value in extra.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            result[key] = int(result.get(key, 0)) + int(value)
        elif key not in result:
            result[key] = value
    return result


def _parsed_requirement_ids(output: BaseModel) -> set[str]:
    """Extract canonical parse-stage requirement IDs from any pipeline output."""
    if isinstance(output, ParseOutput):
        return {req.id for req in output.requirements}
    if isinstance(output, AnalyzeOutput):
        return _parsed_requirement_ids(output.parse)
    if isinstance(output, MapOutput):
        return _parsed_requirement_ids(output.analyze)
    if isinstance(output, GenerateOutput):
        return _parsed_requirement_ids(output.map)
    if isinstance(output, CritiqueOutput):
        return _parsed_requirement_ids(output.generate)
    if isinstance(output, TraceOutput):
        return _parsed_requirement_ids(output.critique)
    return set()


def _validate_stage_output(stage_name: str, output: BaseModel) -> None:
    """Reject shortcut outputs that satisfy JSON shape but not pipeline semantics."""
    expected_type = EXPECTED_STAGE_OUTPUTS.get(stage_name)
    if expected_type and not isinstance(output, expected_type):
        raise StageOutputValidationError(
            f"{stage_name} returned {type(output).__name__}, expected {expected_type.__name__}"
        )

    if isinstance(output, ParseOutput):
        if not output.requirements:
            raise StageOutputValidationError("parse produced no requirements")
        return

    if isinstance(output, AnalyzeOutput):
        if output.parse.requirements and not output.symbols:
            raise StageOutputValidationError("analyze produced no code symbols for parsed requirements")
        return

    if isinstance(output, MapOutput):
        requirement_ids = _parsed_requirement_ids(output)
        mapping_ids = {mapping.requirement_id for mapping in output.mappings}
        if requirement_ids and mapping_ids != requirement_ids:
            missing = sorted(requirement_ids - mapping_ids)
            extra = sorted(mapping_ids - requirement_ids)
            raise StageOutputValidationError(
                f"map must include one mapping per requirement; missing={missing} extra={extra}"
            )
        return

    if isinstance(output, GenerateOutput):
        mapped_ids = {mapping.requirement_id for mapping in output.map.mappings if mapping.symbol is not None}
        generated_ids = {test.requirement_id for test in output.tests}
        if mapped_ids and not mapped_ids.issubset(generated_ids):
            missing = sorted(mapped_ids - generated_ids)
            raise StageOutputValidationError(f"generate produced no tests for mapped requirements: {missing}")
        return

    if isinstance(output, CritiqueOutput):
        test_files = {test.file_path for test in output.generate.tests}
        score_files = {score.test_file for score in output.scores}
        if test_files and score_files != test_files:
            missing = sorted(test_files - score_files)
            extra = sorted(score_files - test_files)
            raise StageOutputValidationError(
                f"critique must score every generated test; missing={missing} extra={extra}"
            )
        return

    if isinstance(output, TraceOutput):
        requirement_ids = _parsed_requirement_ids(output)
        seen: set[str] = set()
        row_ids: set[str] = set()
        for row in output.matrix:
            if row.requirement_id in seen:
                raise StageOutputValidationError(f"trace duplicated requirement row: {row.requirement_id}")
            seen.add(row.requirement_id)
            row_ids.add(row.requirement_id)
            if row.coverage_status in {"covered", "partial"} and not row.test_files:
                raise StageOutputValidationError(f"trace marked {row.requirement_id} covered without test files")
        if requirement_ids and row_ids != requirement_ids:
            missing = sorted(requirement_ids - row_ids)
            extra = sorted(row_ids - requirement_ids)
            raise StageOutputValidationError(
                f"trace must include one row per requirement; missing={missing} extra={extra}"
            )


async def run_pipeline(
    run_id: str,
    on_event: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> None:
    """
    Execute the full pipeline for a given run ID.

    This is the main entry point called from background threads. It handles
    Django setup (since it runs outside the request lifecycle), then sequentially
    executes each pipeline stage.

    Args:
        run_id: UUID string of the Run to execute.
        on_event: Optional callback for emitting real-time events. The callback
            may be sync or async -- the emit() helper handles both cases.
    """
    # Ensure Django is fully initialized since this runs in a background thread
    # outside the normal WSGI request lifecycle.
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "reqlens.settings")

    import django

    django.setup()

    from core.background import (
        finish_background_task,
        heartbeat_background_task,
        register_background_task,
    )
    from core.models import AgentConfig, Run, StageExecution

    @sync_to_async
    def load_run() -> Run:
        """Load the run and related project outside the async event loop."""
        return Run.objects.select_related("project").get(id=run_id)

    @sync_to_async
    def save_run(run_obj: Run) -> None:
        run_obj.save()

    @sync_to_async
    def load_run_status() -> str:
        return str(Run.objects.only("status").get(id=run_id).status)

    def agent_configs_from_snapshot(snapshot: dict[str, Any]) -> dict[str, dict[str, str]]:
        agents = snapshot.get("agents", [])
        if not isinstance(agents, list):
            return {}
        return {
            str(ac["stage"]): {
                "agent_id": str(ac.get("agent_id") or "codex"),
                "model_id": str(ac.get("model_id") or ""),
                "prompt_strategy": str(ac.get("prompt_strategy") or "zero_shot"),
                "context_mode": str(ac.get("context_mode") or "full"),
            }
            for ac in agents
            if isinstance(ac, dict) and ac.get("stage")
        }

    @sync_to_async
    def load_agent_configs(project_id: str) -> dict[str, dict[str, str]]:
        return {
            ac.stage: {
                "agent_id": ac.agent_id,
                "model_id": ac.model_id,
                "prompt_strategy": ac.prompt_strategy,
                "context_mode": ac.context_mode,
            }
            for ac in AgentConfig.objects.filter(project_id=project_id, enabled=True)
        }

    @sync_to_async
    def create_stage_execution(
        stage_name: str,
        agent_id: str,
        model_id: str,
        input_payload: dict[str, Any],
    ) -> StageExecution:
        return StageExecution.objects.create(
            run_id=run_id,
            stage=stage_name,
            agent_id=agent_id,
            model_id=model_id,
            status="running",
            started_at=datetime.now(timezone.utc),
            input_payload=input_payload,
        )

    @sync_to_async
    def save_stage_execution(stage_execution: StageExecution) -> None:
        stage_execution.save()

    @sync_to_async
    def append_stage_update(stage_execution: StageExecution, update: dict[str, Any]) -> None:
        stage_execution.raw_updates = [*list(stage_execution.raw_updates or []), update]
        stage_execution.save(update_fields=["raw_updates", "updated_at"])

    @sync_to_async
    def append_stage_reasoning(stage_execution: StageExecution, chunk: dict[str, Any]) -> None:
        stage_execution.reasoning = [*list(stage_execution.reasoning or []), chunk]
        stage_execution.save(update_fields=["reasoning", "updated_at"])

    @sync_to_async
    def merge_stage_token_usage(stage_execution: StageExecution, usage: dict[str, Any]) -> None:
        stage_execution.token_usage = _merge_token_usage(dict(stage_execution.token_usage or {}), usage)
        stage_execution.save(update_fields=["token_usage", "updated_at"])

    run = await load_run()
    project = run.project

    # Register the background task so the AppConfig.ready() recovery path
    # can mark this run as failed if the process dies mid-execution.
    await register_background_task(kind="run", related_id=run_id)
    last_heartbeat = asyncio.get_event_loop().time()

    async def emit(event: dict[str, Any]) -> None:
        """
        Safely emit an event via the callback.

        Handles both sync and async callbacks (the views module passes a sync
        lambda that calls _broadcast). Swallows exceptions to prevent event
        emission errors from crashing the pipeline.
        """
        if on_event:
            try:
                if callable(on_event):
                    result = on_event(event)
                    # If the callback returns a coroutine, await it
                    if hasattr(result, "__await__"):
                        await result
            except Exception as e:
                logger.warning("Event emit failed: %s", e)

    try:
        # Mark the run as running and record the start time
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        await save_run(run)

        await emit({"type": "run_started", "run_id": run_id, "ts": _now_iso()})

        # Each stage's output is passed as input to the next stage.
        # The first stage (parse) receives None.
        previous_output: BaseModel | None = None

        # Prefer the immutable run snapshot; fall back to live configs for legacy
        # sweep runs that predate per-stage snapshots.
        agent_configs = agent_configs_from_snapshot(run.config_snapshot)
        if not agent_configs:
            agent_configs = await load_agent_configs(str(project.id))

        # Cache a single Retriever instance per run so the map stage doesn't pay
        # the FAISS/BM25 build cost more than once. Built lazily on first use.
        retriever_cache: dict[str, Any] = {}

        # Permission mode controls whether agent file/exec requests auto-approve
        # ("auto", default) or wait for a human via the REST endpoint.
        permission_mode = "auto"
        if isinstance(run.config_snapshot, dict):
            snap_perms = run.config_snapshot.get("permissions")
            if isinstance(snap_perms, str) and snap_perms:
                permission_mode = snap_perms
    except Exception as exc:
        logger.exception("Run setup failed: %s", exc)
        run.status = "failed"
        run.finished_at = datetime.now(timezone.utc)
        await save_run(run)
        await emit({"type": "run_failed", "run_id": run_id, "ts": _now_iso(), "payload": {"error": str(exc)}})
        try:
            await finish_background_task(run_id, "failed")
        except Exception as finish_exc:  # pragma: no cover - best effort
            logger.debug("finish_background_task failed: %s", finish_exc)
        return

    async def on_permission_request(payload: dict[str, Any]) -> None:
        """Broadcast a permission_required SSE so the UI can prompt the user."""
        await emit(
            {
                "type": "permission_required",
                "run_id": run_id,
                "ts": _now_iso(),
                "payload": payload,
            }
        )

    final_status = "succeeded"

    try:
        for stage_name in STAGE_ORDER:
            # Respect cancellation between stages.
            if await load_run_status() == "cancelled":
                final_status = "cancelled"
                await emit({"type": "run_cancelled", "run_id": run_id, "ts": _now_iso()})
                return

            stage_cls = STAGE_CLASSES.get(stage_name)
            if not stage_cls:
                continue

            # Look up the agent config for this stage, falling back to defaults
            ac = agent_configs.get(stage_name)
            agent_id = ac["agent_id"] if ac else "codex"
            model_id = ac["model_id"] if ac else "gpt-5.5/low"
            prompt_strategy = ac["prompt_strategy"] if ac else "zero_shot"
            context_mode = ac["context_mode"] if ac else "full"

            # Snapshot the input payload before creating the row so it survives
            # even if the stage crashes immediately.
            input_snapshot = previous_output.model_dump() if previous_output else {}
            se = await create_stage_execution(stage_name, agent_id, model_id, input_snapshot)

            await emit(
                {
                    "type": "stage_started",
                    "run_id": run_id,
                    "stage": stage_name,
                    "ts": _now_iso(),
                    "payload": {"agent_id": agent_id, "model_id": model_id},
                }
            )

            # Build the context object that carries all configuration to the stage
            ctx = StageContext(
                project_id=str(project.id),
                project_name=project.name,
                run_id=run_id,
                agent_id=agent_id,
                model_id=model_id,
                prompt_strategy=prompt_strategy,
                context_mode=context_mode,
                code_path=project.code_path,
                requirements_path=project.requirements_path,
                artifacts_dir=run.artifacts_path,
                retrieval_index=retriever_cache,
                permission_mode=permission_mode,
                on_permission_request=on_permission_request,
            )

            try:
                async def stage_event_handler(evt: StageEvent, _se=se, _stage_name=stage_name) -> None:
                    """Forward stage-level progress events to the SSE stream.

                    Splits the unified StageEvent stream into three SSE shapes:
                      - acp_result   -> roll usage into StageExecution.token_usage
                      - reasoning    -> persist on StageExecution.reasoning + emit stage_reasoning
                      - agent_update -> persist on StageExecution.raw_updates + emit stage_agent_update
                      - everything else -> emit as stage_progress
                    """
                    if evt.type == "acp_result":
                        usage = evt.payload.get("token_usage") if isinstance(evt.payload, dict) else None
                        await merge_stage_token_usage(_se, usage or {})
                        return
                    if evt.type == "reasoning":
                        chunk = evt.payload if isinstance(evt.payload, dict) else {}
                        await append_stage_reasoning(_se, chunk)
                        await emit(
                            {
                                "type": "stage_reasoning",
                                "run_id": run_id,
                                "stage": _stage_name,
                                "ts": _now_iso(),
                                "payload": chunk,
                            }
                        )
                        return
                    if evt.type == "agent_update":
                        await append_stage_update(_se, evt.payload)
                        await emit(
                            {
                                "type": "stage_agent_update",
                                "run_id": run_id,
                                "stage": _stage_name,
                                "ts": _now_iso(),
                                "payload": evt.payload,
                            }
                        )
                        return
                    await emit(
                        {
                            "type": "stage_progress",
                            "run_id": run_id,
                            "stage": _stage_name,
                            "ts": _now_iso(),
                            "payload": evt.payload,
                        }
                    )

                last_attempt_error: Exception | None = None
                for attempt in range(1, MAX_STAGE_ATTEMPTS + 1):
                    if await load_run_status() == "cancelled":
                        raise RunCancelledError("Run cancelled")

                    await emit(
                        {
                            "type": "stage_attempt_started",
                            "run_id": run_id,
                            "stage": stage_name,
                            "ts": _now_iso(),
                            "payload": {"attempt": attempt, "max_attempts": MAX_STAGE_ATTEMPTS},
                        }
                    )

                    stage = stage_cls()
                    stage_task = asyncio.create_task(
                        stage.run(ctx, previous_output, stage_event_handler),
                        name=f"stage:{stage_name}:{run_id}:attempt:{attempt}",
                    )
                    watcher_stop = asyncio.Event()

                    async def _cancel_watcher(_task=stage_task, _stop=watcher_stop) -> None:
                        nonlocal last_heartbeat
                        while not _stop.is_set():
                            try:
                                await asyncio.wait_for(_stop.wait(), timeout=1.0)
                                return
                            except asyncio.TimeoutError:
                                pass
                            # Heartbeat the background task every ~5s.
                            now = asyncio.get_event_loop().time()
                            if now - last_heartbeat >= 5.0:
                                last_heartbeat = now
                                try:
                                    await heartbeat_background_task(run_id)
                                except Exception as exc:  # pragma: no cover - best effort
                                    logger.debug("heartbeat failed: %s", exc)
                            if await load_run_status() == "cancelled" and not _task.done():
                                _task.cancel()
                                return

                    watcher = asyncio.create_task(_cancel_watcher(), name=f"cancel-watcher:{run_id}:{attempt}")

                    attempt_error: Exception | None = None
                    candidate_output: BaseModel | None = None
                    try:
                        candidate_output = await stage_task
                    except asyncio.CancelledError:
                        raise RunCancelledError("Run cancelled") from None
                    except Exception as exc:
                        attempt_error = exc
                    finally:
                        watcher_stop.set()
                        if not watcher.done():
                            watcher.cancel()
                            try:
                                await watcher
                            except (asyncio.CancelledError, Exception):
                                pass

                    # If the stage returned but the run was cancelled in the meantime, stop.
                    if await load_run_status() == "cancelled":
                        raise RunCancelledError("Run cancelled")

                    if attempt_error is None:
                        try:
                            if candidate_output is None:
                                raise StageOutputValidationError(f"{stage_name} returned no output")
                            _validate_stage_output(stage_name, candidate_output)
                        except StageOutputValidationError as exc:
                            attempt_error = exc
                        else:
                            previous_output = candidate_output
                            break

                    last_attempt_error = attempt_error

                    se.error = f"attempt {attempt}/{MAX_STAGE_ATTEMPTS}: {last_attempt_error}"
                    await save_stage_execution(se)
                    if attempt >= MAX_STAGE_ATTEMPTS:
                        raise last_attempt_error

                    await emit(
                        {
                            "type": "stage_attempt_failed",
                            "run_id": run_id,
                            "stage": stage_name,
                            "ts": _now_iso(),
                            "payload": {
                                "attempt": attempt,
                                "max_attempts": MAX_STAGE_ATTEMPTS,
                                "error": str(last_attempt_error),
                                "will_retry": True,
                            },
                        }
                    )
                    await asyncio.sleep(min(attempt, 3))

                # Record successful completion
                se.status = "succeeded"
                se.finished_at = datetime.now(timezone.utc)
                se.output_payload = previous_output.model_dump() if previous_output else {}
                se.latency_ms = int((se.finished_at - se.started_at).total_seconds() * 1000) if se.started_at else 0
                await save_stage_execution(se)

                await emit(
                    {
                        "type": "stage_completed",
                        "run_id": run_id,
                        "stage": stage_name,
                        "ts": _now_iso(),
                        "payload": {
                            "tokens_total": _sum_token_usage(se.token_usage),
                            "latency_ms": se.latency_ms,
                        },
                    }
                )

            except RunCancelledError:
                se.status = "cancelled"
                se.finished_at = datetime.now(timezone.utc)
                se.error = "cancelled"
                await save_stage_execution(se)

                run.status = "cancelled"
                run.finished_at = datetime.now(timezone.utc)
                await save_run(run)

                await emit(
                    {
                        "type": "stage_cancelled",
                        "run_id": run_id,
                        "stage": stage_name,
                        "ts": _now_iso(),
                    }
                )
                await emit({"type": "run_cancelled", "run_id": run_id, "ts": _now_iso()})
                final_status = "cancelled"
                return
            except Exception as e:
                # If any stage fails, record the error, mark the run as failed, and stop
                logger.exception("Stage %s failed: %s", stage_name, e)
                se.status = "failed"
                se.finished_at = datetime.now(timezone.utc)
                se.error = str(e)
                await save_stage_execution(se)

                run.status = "failed"
                run.finished_at = datetime.now(timezone.utc)
                await save_run(run)

                await emit(
                    {
                        "type": "stage_failed",
                        "run_id": run_id,
                        "stage": stage_name,
                        "ts": _now_iso(),
                        "payload": {"error": str(e)},
                    }
                )
                await emit({"type": "run_failed", "run_id": run_id, "ts": _now_iso()})
                final_status = "failed"
                return

        # All stages completed successfully
        # Double-check cancellation before marking success.
        if await load_run_status() == "cancelled":
            run.status = "cancelled"
            run.finished_at = datetime.now(timezone.utc)
            await save_run(run)
            await emit({"type": "run_cancelled", "run_id": run_id, "ts": _now_iso()})
            final_status = "cancelled"
            return

        run.status = "succeeded"
        run.finished_at = datetime.now(timezone.utc)
        await save_run(run)

        await emit({"type": "run_succeeded", "run_id": run_id, "ts": _now_iso()})
    finally:
        try:
            await finish_background_task(run_id, final_status)
        except Exception as exc:  # pragma: no cover - best effort
            logger.debug("finish_background_task failed: %s", exc)
