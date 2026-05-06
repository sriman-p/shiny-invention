"""
Pipeline orchestrator -- coordinates the sequential execution of all pipeline stages.

This is the "conductor" of the ReqLens pipeline. When a run is triggered, the
orchestrator:
  1. Loads the Run and Project from the database
  2. Sets the run status to "running"
  3. Iterates through stages in order: parse -> analyze -> map -> generate -> critique -> trace
  4. For each stage:
     a. Looks up the agent config (which agent, prompt strategy, context mode)
     b. Creates a StageExecution record
     c. Builds a StageContext with all needed configuration
     d. Executes the stage, passing the previous stage's output
     e. Saves the stage result and emits SSE events
  5. If any stage fails, marks the run as failed and stops
  6. If all stages succeed, marks the run as succeeded

The orchestrator uses an async/await pattern because ACP agent calls are async.
It runs inside a background thread spawned by the views module, with a fresh
asyncio event loop.

Events are emitted via the on_event callback, which the views module wires up
to the SSE broadcast system. Event types include:
  - run_started, run_succeeded, run_failed
  - stage_started, stage_completed, stage_failed, stage_progress
"""

import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from asgiref.sync import sync_to_async
from pydantic import BaseModel

from .stages import STAGE_CLASSES, STAGE_ORDER
from .stages.base import StageContext, StageEvent

logger = logging.getLogger(__name__)


class RunCancelledError(Exception):
    """Raised when a run is cancelled mid-execution."""


def _now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string for event timestamps."""
    return datetime.now(timezone.utc).isoformat()


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
    def create_stage_execution(stage_name: str, agent_id: str, model_id: str) -> StageExecution:
        return StageExecution.objects.create(
            run_id=run_id,
            stage=stage_name,
            agent_id=agent_id,
            model_id=model_id,
            status="running",
            started_at=datetime.now(timezone.utc),
        )

    @sync_to_async
    def save_stage_execution(stage_execution: StageExecution) -> None:
        stage_execution.save()

    @sync_to_async
    def append_stage_update(stage_execution: StageExecution, update: dict[str, Any]) -> None:
        stage_execution.raw_updates = [*list(stage_execution.raw_updates or []), update]
        stage_execution.save(update_fields=["raw_updates", "updated_at"])

    run = await load_run()
    project = run.project

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

    for stage_name in STAGE_ORDER:
        # Respect cancellation between stages.
        if await load_run_status() == "cancelled":
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

        # Create a database record to track this stage's execution
        se = await create_stage_execution(stage_name, agent_id, model_id)

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
        )

        try:
            stage = stage_cls()

            async def stage_event_handler(evt: StageEvent) -> None:
                """Forward stage-level progress events to the SSE stream."""
                # Best-effort cancellation check during long-running stages.
                if await load_run_status() == "cancelled":
                    raise RunCancelledError("Run cancelled")
                if evt.type == "agent_update":
                    await append_stage_update(se, evt.payload)
                await emit(
                    {
                        "type": "stage_agent_update" if evt.type == "agent_update" else "stage_progress",
                        "run_id": run_id,
                        "stage": stage_name,
                        "ts": _now_iso(),
                        "payload": evt.payload,
                    }
                )

            # Execute the stage, passing the previous stage's output
            previous_output = await stage.run(ctx, previous_output, stage_event_handler)

            # If the stage returned but the run was cancelled in the meantime, stop.
            if await load_run_status() == "cancelled":
                raise RunCancelledError("Run cancelled")

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
            return

    # All stages completed successfully
    # Double-check cancellation before marking success.
    if await load_run_status() == "cancelled":
        run.status = "cancelled"
        run.finished_at = datetime.now(timezone.utc)
        await save_run(run)
        await emit({"type": "run_cancelled", "run_id": run_id, "ts": _now_iso()})
        return

    run.status = "succeeded"
    run.finished_at = datetime.now(timezone.utc)
    await save_run(run)

    await emit({"type": "run_succeeded", "run_id": run_id, "ts": _now_iso()})
