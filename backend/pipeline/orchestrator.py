import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from pydantic import BaseModel

from .stages import STAGE_CLASSES, STAGE_ORDER
from .stages.base import StageContext, StageEvent

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def run_pipeline(
    run_id: str,
    on_event: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> None:
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "reqlens.settings")

    import django

    django.setup()

    from core.models import AgentConfig, Run, StageExecution

    run = Run.objects.select_related("project").get(id=run_id)
    project = run.project

    async def emit(event: dict[str, Any]) -> None:
        if on_event:
            try:
                if callable(on_event):
                    result = on_event(event)
                    if hasattr(result, "__await__"):
                        await result
            except Exception as e:
                logger.warning("Event emit failed: %s", e)

    run.status = "running"
    run.started_at = datetime.now(timezone.utc)
    run.save()

    await emit({"type": "run_started", "run_id": run_id, "ts": _now_iso()})

    previous_output: BaseModel | None = None

    agent_configs = {ac.stage: ac for ac in AgentConfig.objects.filter(project=project, enabled=True)}

    for stage_name in STAGE_ORDER:
        stage_cls = STAGE_CLASSES.get(stage_name)
        if not stage_cls:
            continue

        ac = agent_configs.get(stage_name)
        agent_id = ac.agent_id if ac else "claude-code"
        prompt_strategy = ac.prompt_strategy if ac else "zero_shot"
        context_mode = ac.context_mode if ac else "full"

        se = StageExecution.objects.create(
            run=run,
            stage=stage_name,
            agent_id=agent_id,
            status="running",
            started_at=datetime.now(timezone.utc),
        )

        await emit({
            "type": "stage_started",
            "run_id": run_id,
            "stage": stage_name,
            "ts": _now_iso(),
            "payload": {"agent_id": agent_id},
        })

        ctx = StageContext(
            project_id=str(project.id),
            project_name=project.name,
            run_id=run_id,
            agent_id=agent_id,
            prompt_strategy=prompt_strategy,
            context_mode=context_mode,
            code_path=project.code_path,
            requirements_path=project.requirements_path,
            artifacts_dir=run.artifacts_path,
        )

        try:
            stage = stage_cls()

            async def stage_event_handler(evt: StageEvent) -> None:
                await emit({
                    "type": "stage_progress",
                    "run_id": run_id,
                    "stage": stage_name,
                    "ts": _now_iso(),
                    "payload": evt.payload,
                })

            previous_output = await stage.run(ctx, previous_output, stage_event_handler)

            se.status = "succeeded"
            se.finished_at = datetime.now(timezone.utc)
            se.output_payload = previous_output.model_dump() if previous_output else {}
            se.latency_ms = int(
                (se.finished_at - se.started_at).total_seconds() * 1000
            ) if se.started_at else 0
            se.save()

            await emit({
                "type": "stage_completed",
                "run_id": run_id,
                "stage": stage_name,
                "ts": _now_iso(),
            })

        except Exception as e:
            logger.exception("Stage %s failed: %s", stage_name, e)
            se.status = "failed"
            se.finished_at = datetime.now(timezone.utc)
            se.error = str(e)
            se.save()

            run.status = "failed"
            run.finished_at = datetime.now(timezone.utc)
            run.save()

            await emit({
                "type": "stage_failed",
                "run_id": run_id,
                "stage": stage_name,
                "ts": _now_iso(),
                "payload": {"error": str(e)},
            })
            await emit({"type": "run_failed", "run_id": run_id, "ts": _now_iso()})
            return

    run.status = "succeeded"
    run.finished_at = datetime.now(timezone.utc)
    run.save()

    await emit({"type": "run_succeeded", "run_id": run_id, "ts": _now_iso()})
