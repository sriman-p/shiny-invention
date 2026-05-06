import logging
from typing import Any, Awaitable, Callable

from .metrics import compute_metrics
from .stats import generate_markdown_report, run_statistical_analysis

logger = logging.getLogger(__name__)


async def run_sweep(
    sweep_id: str,
    on_event: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> None:
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "reqlens.settings")

    import django

    django.setup()

    from core.models import AgentConfig, Run, Sweep

    sweep = Sweep.objects.select_related("project").get(id=sweep_id)
    project = sweep.project

    async def emit(event: dict[str, Any]) -> None:
        if on_event:
            try:
                result = on_event(event)
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                pass

    sweep.status = "running"
    sweep.save()

    await emit({"type": "sweep_started", "sweep_id": sweep_id})

    all_metrics = []

    for i, config in enumerate(sweep.matrix):
        strategy = config.get("prompt_strategy", "zero_shot") if isinstance(config, dict) else "zero_shot"
        context_mode = config.get("context_mode", "full") if isinstance(config, dict) else "full"
        agent_id = config.get("agent_id", "claude-code") if isinstance(config, dict) else "claude-code"

        run = Run.objects.create(
            project=project,
            config_snapshot={
                "prompt_strategy": strategy,
                "context_mode": context_mode,
                "agent_id": agent_id,
                "permissions": "auto",
            },
            artifacts_path=str(
                project.code_path
            ),
        )
        sweep.runs.add(run)

        for stage_name in ["parse", "analyze", "map", "generate", "critique", "trace"]:
            AgentConfig.objects.update_or_create(
                project=project,
                stage=stage_name,
                defaults={
                    "agent_id": agent_id,
                    "prompt_strategy": strategy,
                    "context_mode": context_mode,
                    "enabled": True,
                },
            )

        await emit({
            "type": "sweep_run_started",
            "sweep_id": sweep_id,
            "run_id": str(run.id),
            "config_index": i,
        })

        try:
            from pipeline.orchestrator import run_pipeline

            await run_pipeline(str(run.id))
        except Exception as e:
            logger.exception("Sweep run %s failed: %s", run.id, e)

        run.refresh_from_db()
        run_data = {
            "stages": list(
                run.stages.values(
                    "stage", "output_payload", "latency_ms", "token_usage"
                )
            )
        }
        metrics = compute_metrics(run_data)
        metrics["prompt_strategy"] = strategy
        metrics["context_mode"] = context_mode
        metrics["agent_id"] = agent_id
        metrics["run_id"] = str(run.id)
        all_metrics.append(metrics)

        await emit({
            "type": "sweep_run_completed",
            "sweep_id": sweep_id,
            "run_id": str(run.id),
            "config_index": i,
            "metrics": metrics,
        })

    stats = run_statistical_analysis(all_metrics)
    markdown_report = generate_markdown_report(stats)

    sweep.metrics_summary = all_metrics
    sweep.stats_report = {**stats, "markdown": markdown_report}
    sweep.status = "succeeded"
    sweep.save()

    await emit({
        "type": "sweep_succeeded",
        "sweep_id": sweep_id,
        "metrics_summary": all_metrics,
    })
