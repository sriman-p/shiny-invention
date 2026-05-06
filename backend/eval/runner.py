"""
Sweep runner -- executes multiple pipeline runs across different configurations.

A sweep is a benchmarking tool that runs the full pipeline multiple times with
different combinations of prompt_strategy, context_mode, and agent_id. After
all runs complete, it computes metrics for each run and performs statistical
analysis to determine which configuration produces the best results.

Workflow:
  1. Load the Sweep and its configuration matrix from the database
  2. For each configuration in the matrix:
     a. Create a new Run with the configuration snapshot
     b. Update the project's AgentConfig for all stages to match this config
     c. Execute the full pipeline via the orchestrator
     d. Compute quality and cost metrics for the completed run
  3. After all runs finish, run ANOVA and pairwise statistical tests
  4. Store the metrics summary and statistical report on the Sweep object

Each spawned Run stores an immutable per-stage configuration snapshot, so a
sweep can continue in the background without mutating the project's saved
agent configuration.
"""

import logging
from pathlib import Path
from typing import Any, Awaitable, Callable

from asgiref.sync import sync_to_async

from .metrics import compute_metrics, rank_metrics
from .stats import generate_markdown_report, run_statistical_analysis

logger = logging.getLogger(__name__)


async def run_sweep(
    sweep_id: str,
    on_event: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> None:
    """
    Execute a parameter sweep: run the pipeline once per configuration and compare results.

    This function runs in a background thread (spawned by the views module) with
    its own asyncio event loop. It handles Django setup internally since it runs
    outside the WSGI lifecycle.

    Args:
        sweep_id: UUID string of the Sweep to execute.
        on_event: Optional callback for emitting real-time SSE events. Events
            include sweep_started, sweep_run_started, sweep_run_completed,
            and sweep_succeeded.
    """
    # Ensure Django is initialized (running in background thread)
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "reqlens.settings")

    import django

    django.setup()

    from django.utils import timezone

    from core.models import Run, Sweep

    @sync_to_async
    def load_sweep() -> Sweep:
        return Sweep.objects.select_related("project").get(id=sweep_id)

    @sync_to_async
    def save_sweep(sweep_obj: Sweep) -> None:
        sweep_obj.save()

    @sync_to_async
    def create_run_for_config(strategy: str, context_mode: str, agent_id: str, model_id: str) -> Run:
        agents = [
            {
                "stage": stage_name,
                "agent_id": agent_id,
                "model_id": model_id,
                "prompt_strategy": strategy,
                "context_mode": context_mode,
                "enabled": True,
            }
            for stage_name in ["parse", "analyze", "map", "generate", "critique", "trace"]
        ]
        run_obj = Run.objects.create(
            project=sweep.project,
            config_snapshot={
                "prompt_strategy": strategy,
                "context_mode": context_mode,
                "agent_id": agent_id,
                "model_id": model_id,
                "agents": agents,
                "permissions": "auto",
            },
        )
        run_obj.artifacts_path = str(Path(__file__).resolve().parent.parent / "data" / "runs" / str(run_obj.id))
        run_obj.save()
        Path(run_obj.artifacts_path).mkdir(parents=True, exist_ok=True)
        sweep.runs.add(run_obj)
        return run_obj

    @sync_to_async
    def collect_run_data(run_obj: Run) -> dict[str, Any]:
        run_obj.refresh_from_db()
        return {
            "status": run_obj.status,
            "stages": list(
                run_obj.stages.values("stage", "status", "output_payload", "latency_ms", "token_usage", "error")
            ),
        }

    @sync_to_async
    def mark_run_failed(run_obj: Run) -> None:
        Run.objects.filter(id=run_obj.id, status__in=["pending", "running"]).update(
            status="failed",
            finished_at=timezone.now(),
        )

    @sync_to_async
    def persist_partial_metrics(metrics: list[dict[str, Any]]) -> None:
        Sweep.objects.filter(id=sweep_id).update(metrics_summary=rank_metrics(metrics))

    @sync_to_async
    def check_cancelled() -> bool:
        """Reload the sweep from DB to check if it was cancelled via the API."""
        return Sweep.objects.filter(id=sweep_id, status="cancelled").exists()

    sweep = await load_sweep()

    async def emit(event: dict[str, Any]) -> None:
        """Safely emit an event, handling both sync and async callbacks."""
        if on_event:
            try:
                result = on_event(event)
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                pass

    sweep.status = "running"
    await save_sweep(sweep)

    await emit({"type": "sweep_started", "sweep_id": sweep_id})

    # Accumulate metrics from all runs for statistical analysis
    all_metrics = []
    was_cancelled = False

    for i, config in enumerate(sweep.matrix):
        # Check if the sweep was cancelled between runs
        if await check_cancelled():
            was_cancelled = True
            logger.info("Sweep %s was cancelled, stopping at config %d", sweep_id, i)
            break

        # Extract configuration values, with safe defaults for malformed entries
        strategy = config.get("prompt_strategy", "zero_shot") if isinstance(config, dict) else "zero_shot"
        context_mode = config.get("context_mode", "full") if isinstance(config, dict) else "full"
        agent_id = config.get("agent_id", "codex") if isinstance(config, dict) else "codex"
        model_id = config.get("model_id", "gpt-5.5/low") if isinstance(config, dict) else "gpt-5.5/low"

        # Create an isolated run/artifact directory for this configuration.
        run = await create_run_for_config(strategy, context_mode, agent_id, model_id)

        await emit(
            {
                "type": "sweep_run_started",
                "sweep_id": sweep_id,
                "run_id": str(run.id),
                "config_index": i,
            }
        )

        # Execute the full pipeline for this configuration
        try:
            from pipeline.orchestrator import run_pipeline

            await run_pipeline(
                str(run.id),
                on_event=lambda evt, run_id=str(run.id), index=i: emit(
                    {
                        "type": "sweep_run_event",
                        "sweep_id": sweep_id,
                        "run_id": run_id,
                        "config_index": index,
                        "event": evt,
                    }
                ),
            )
        except Exception as e:
            logger.exception("Sweep run %s failed: %s", run.id, e)
            await mark_run_failed(run)

        # Check again after the run completes
        if await check_cancelled():
            was_cancelled = True
            logger.info("Sweep %s was cancelled after run %s", sweep_id, run.id)
            break

        # Compute metrics from the completed run's stage data
        run_data = await collect_run_data(run)
        metrics = compute_metrics(run_data)
        # Tag the metrics with the configuration used for this run
        metrics["prompt_strategy"] = strategy
        metrics["context_mode"] = context_mode
        metrics["agent_id"] = agent_id
        metrics["model_id"] = model_id
        metrics["run_id"] = str(run.id)
        all_metrics.append(metrics)
        await persist_partial_metrics(all_metrics)

        await emit(
            {
                "type": "sweep_run_completed",
                "sweep_id": sweep_id,
                "run_id": str(run.id),
                "config_index": i,
                "metrics": metrics,
            }
        )

    if was_cancelled:
        # Store partial results if any
        sweep = await load_sweep()
        sweep.status = "cancelled"
        if all_metrics:
            sweep.metrics_summary = rank_metrics(all_metrics)
        await save_sweep(sweep)
        await emit({"type": "sweep_cancelled", "sweep_id": sweep_id})
        return

    # Perform statistical analysis comparing all configurations
    ranked_metrics = rank_metrics(all_metrics)
    stats = run_statistical_analysis(ranked_metrics)
    markdown_report = generate_markdown_report(stats)

    # Store results on the sweep object
    sweep.metrics_summary = ranked_metrics
    sweep.stats_report = {**stats, "markdown": markdown_report}
    sweep.status = "succeeded"
    await save_sweep(sweep)

    await emit(
        {
            "type": "sweep_succeeded",
            "sweep_id": sweep_id,
            "metrics_summary": ranked_metrics,
        }
    )
