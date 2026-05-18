"""
Sweep runner -- executes multiple pipeline runs across different configurations.

A sweep is a benchmarking tool that runs the full pipeline multiple times with
different combinations of prompt_strategy, context_mode, and agent_id. After
all runs complete, it computes metrics for each run and performs statistical
analysis to determine which configuration produces the best results.

Workflow:
  1. Load the Sweep and its configuration matrix from the database
  2. Create an isolated Run for each configuration in the matrix.
  3. Execute queued runs concurrently, bounded by SWEEP_MAX_CONCURRENCY
     (default: 4).
     a. Execute the full pipeline via the orchestrator
     b. Compute quality and cost metrics as each run finishes
     c. Persist partial rankings so the UI updates while the sweep is running
  4. After all runs finish, run ANOVA and pairwise statistical tests
  5. Store the metrics summary and statistical report on the Sweep object

Each spawned Run stores an immutable per-stage configuration snapshot, so a
sweep can continue in the background without mutating the project's saved
agent configuration.
"""

import asyncio
import contextlib
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable

from asgiref.sync import sync_to_async

from .direct_baseline import run_direct_acp_baseline
from .metrics import compute_metrics, rank_metrics
from .stats import compute_baseline_diff, generate_markdown_report, run_statistical_analysis

logger = logging.getLogger(__name__)

DEFAULT_SWEEP_CONCURRENCY = 4


def _coerce_concurrency(value: str | None, total: int) -> int:
    """Parse the optional env override while keeping a useful default."""
    try:
        parsed = int(value or DEFAULT_SWEEP_CONCURRENCY)
    except (TypeError, ValueError):
        parsed = DEFAULT_SWEEP_CONCURRENCY
    return max(1, min(parsed, max(total, 1)))


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
    def create_run_for_config(
        strategy: str,
        context_mode: str,
        agent_id: str,
        model_id: str,
        run_mode: str = "pipeline",
        comparison_baseline: bool = False,
    ) -> Run:
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
                "run_mode": run_mode,
                "comparison_baseline": comparison_baseline,
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
    def mark_run_cancelled(run_obj: Run) -> None:
        Run.objects.filter(id=run_obj.id, status__in=["pending", "running"]).update(
            status="cancelled",
            finished_at=timezone.now(),
        )

    @sync_to_async
    def mark_unfinished_runs_failed() -> int:
        return Sweep.objects.get(id=sweep_id).runs.filter(status__in=["pending", "running"]).update(
            status="failed",
            finished_at=timezone.now(),
        )

    @sync_to_async
    def persist_partial_metrics(metrics: list[dict[str, Any]]) -> None:
        ranked = rank_metrics(metrics)
        baseline = compute_baseline_diff(ranked)
        Sweep.objects.filter(id=sweep_id).update(
            metrics_summary=ranked,
            baseline_summary=baseline or None,
            stats_report={"partial": True, "completed_configs": len(ranked), "total_configs": len(sweep.matrix)},
        )

    @sync_to_async
    def check_cancelled() -> bool:
        """Reload the sweep from DB to check if it was cancelled via the API."""
        return Sweep.objects.filter(id=sweep_id, status="cancelled").exists()

    from core.background import (
        finish_background_task,
        heartbeat_background_task,
        register_background_task,
    )

    sweep = await load_sweep()
    await register_background_task(kind="sweep", related_id=sweep_id)
    heartbeat_stop = asyncio.Event()

    async def sweep_heartbeat_loop() -> None:
        while not heartbeat_stop.is_set():
            try:
                await asyncio.wait_for(heartbeat_stop.wait(), timeout=5.0)
                return
            except asyncio.TimeoutError:
                try:
                    await heartbeat_background_task(sweep_id)
                except Exception as exc:  # pragma: no cover - best effort
                    logger.debug("sweep heartbeat failed for %s: %s", sweep_id, exc)

    heartbeat_task = asyncio.create_task(sweep_heartbeat_loop(), name=f"sweep-heartbeat:{sweep_id}")

    async def stop_sweep_heartbeat() -> None:
        heartbeat_stop.set()
        heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat_task

    async def emit(event: dict[str, Any]) -> None:
        """Safely emit an event, handling both sync and async callbacks."""
        if on_event:
            try:
                result = on_event(event)
                if hasattr(result, "__await__"):
                    await result
            except Exception as exc:
                logger.debug("sweep event emit failed for %s: %s", sweep_id, exc)

    sweep.status = "running"
    await save_sweep(sweep)

    concurrency = _coerce_concurrency(os.environ.get("SWEEP_MAX_CONCURRENCY"), len(sweep.matrix))

    await emit(
        {
            "type": "sweep_started",
            "sweep_id": sweep_id,
            "concurrency": concurrency,
            "total_configs": len(sweep.matrix),
        }
    )

    # Accumulate metrics from all runs for statistical analysis
    all_metrics: list[dict[str, Any]] = []
    metrics_lock = asyncio.Lock()
    cancel_event = asyncio.Event()
    failure_event = asyncio.Event()
    run_specs: list[dict[str, Any]] = []

    # Create the full run queue up front so the UI can show all 16 cells
    # immediately and cancellation can mark every pending/running run.
    for index, config in enumerate(sweep.matrix):
        if await check_cancelled():
            cancel_event.set()
            logger.info("Sweep %s was cancelled while queueing config %d", sweep_id, index)
            break

        strategy = config.get("prompt_strategy", "zero_shot") if isinstance(config, dict) else "zero_shot"
        context_mode = config.get("context_mode", "full") if isinstance(config, dict) else "full"
        agent_id = config.get("agent_id", "codex") if isinstance(config, dict) else "codex"
        model_id = config.get("model_id", "gpt-5.5/low") if isinstance(config, dict) else "gpt-5.5/low"
        run_mode = config.get("run_mode", "pipeline") if isinstance(config, dict) else "pipeline"
        comparison_baseline = bool(config.get("comparison_baseline")) if isinstance(config, dict) else False
        run = await create_run_for_config(strategy, context_mode, agent_id, model_id, run_mode, comparison_baseline)
        run_specs.append(
            {
                "index": index,
                "run": run,
                "prompt_strategy": strategy,
                "context_mode": context_mode,
                "agent_id": agent_id,
                "model_id": model_id,
                "run_mode": run_mode,
                "comparison_baseline": comparison_baseline,
            }
        )

        await emit(
            {
                "type": "sweep_run_queued",
                "sweep_id": sweep_id,
                "run_id": str(run.id),
                "config_index": index,
            }
        )

    semaphore = asyncio.Semaphore(concurrency)

    async def run_one_config(spec: dict[str, Any]) -> None:
        async with semaphore:
            if cancel_event.is_set() or await check_cancelled():
                cancel_event.set()
                await mark_run_cancelled(spec["run"])
                return

            run = spec["run"]
            index = int(spec["index"])
            await emit(
                {
                    "type": "sweep_run_started",
                    "sweep_id": sweep_id,
                    "run_id": str(run.id),
                    "config_index": index,
                    "concurrency": concurrency,
                }
            )

            # Execute either the full six-stage pipeline or the explicit direct
            # ACP baseline used as the comparison floor in sweeps.
            try:
                if spec.get("run_mode") == "direct_acp_baseline":
                    await run_direct_acp_baseline(
                        str(run.id),
                        agent_id=str(spec["agent_id"]),
                        model_id=str(spec["model_id"]),
                        on_event=lambda evt, run_id=str(run.id), config_index=index: emit(
                            {
                                "type": "sweep_run_event",
                                "sweep_id": sweep_id,
                                "run_id": run_id,
                                "config_index": config_index,
                                "event": evt,
                            }
                        ),
                    )
                else:
                    from pipeline.orchestrator import run_pipeline

                    await run_pipeline(
                        str(run.id),
                        on_event=lambda evt, run_id=str(run.id), config_index=index: emit(
                            {
                                "type": "sweep_run_event",
                                "sweep_id": sweep_id,
                                "run_id": run_id,
                                "config_index": config_index,
                                "event": evt,
                            }
                        ),
                    )
            except asyncio.CancelledError:
                await mark_run_cancelled(run)
                raise
            except Exception as e:
                logger.exception("Sweep run %s failed: %s", run.id, e)
                await mark_run_failed(run)
                failure_event.set()

            run_data = await collect_run_data(run)
            if run_data.get("status") == "cancelled":
                cancel_event.set()
                return
            if run_data.get("status") != "succeeded":
                failure_event.set()
                await emit(
                    {
                        "type": "sweep_run_failed",
                        "sweep_id": sweep_id,
                        "run_id": str(run.id),
                        "config_index": index,
                    }
                )
                return

            metrics = compute_metrics(run_data)
            metrics["prompt_strategy"] = spec["prompt_strategy"]
            metrics["context_mode"] = spec["context_mode"]
            metrics["agent_id"] = spec["agent_id"]
            metrics["model_id"] = spec["model_id"]
            metrics["run_id"] = str(run.id)
            metrics["run_mode"] = spec.get("run_mode", "pipeline")
            metrics["comparison_baseline"] = bool(spec.get("comparison_baseline"))

            async with metrics_lock:
                all_metrics.append(metrics)
                await persist_partial_metrics(list(all_metrics))

            await emit(
                {
                    "type": "sweep_run_completed",
                    "sweep_id": sweep_id,
                    "run_id": str(run.id),
                    "config_index": index,
                    "metrics": metrics,
                }
            )

            if await check_cancelled():
                cancel_event.set()

    tasks = [asyncio.create_task(run_one_config(spec)) for spec in run_specs]
    if tasks:
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, asyncio.CancelledError):
                    cancel_event.set()
                elif isinstance(result, Exception):
                    failure_event.set()
                    logger.exception("Sweep worker failed unexpectedly: %s", result)
        except asyncio.CancelledError:
            cancel_event.set()
            for task in tasks:
                task.cancel()
            raise

    was_cancelled = cancel_event.is_set() or await check_cancelled()
    had_failures = failure_event.is_set()

    if was_cancelled:
        # Store partial results if any
        sweep = await load_sweep()
        sweep.status = "cancelled"
        if all_metrics:
            ranked = rank_metrics(all_metrics)
            sweep.metrics_summary = ranked
            sweep.baseline_summary = compute_baseline_diff(ranked) or None
            sweep.stats_report = {
                "partial": True,
                "completed_configs": len(ranked),
                "total_configs": len(sweep.matrix),
            }
        await save_sweep(sweep)
        try:
            await finish_background_task(sweep_id, "cancelled")
        except Exception as exc:  # pragma: no cover - best effort
            logger.debug("finish_background_task failed for sweep %s: %s", sweep_id, exc)
        await stop_sweep_heartbeat()
        await emit({"type": "sweep_cancelled", "sweep_id": sweep_id})
        return

    # Perform statistical analysis + baseline diff across all configurations.
    ranked_metrics = rank_metrics(all_metrics)
    baseline_summary = compute_baseline_diff(ranked_metrics)
    stats = run_statistical_analysis(ranked_metrics)
    stats["partial"] = had_failures or len(ranked_metrics) != len(sweep.matrix)
    stats["completed_configs"] = len(ranked_metrics)
    stats["total_configs"] = len(sweep.matrix)
    markdown_report = generate_markdown_report(stats, baseline_summary)

    # Store results on the sweep object
    sweep.metrics_summary = ranked_metrics
    sweep.baseline_summary = baseline_summary or None
    sweep.stats_report = {**stats, "markdown": markdown_report}
    sweep.status = "failed" if had_failures else "succeeded"
    await save_sweep(sweep)
    try:
        await finish_background_task(sweep_id, sweep.status)
    except Exception as exc:  # pragma: no cover - best effort
        logger.debug("finish_background_task failed for sweep %s: %s", sweep_id, exc)
    await stop_sweep_heartbeat()
    if had_failures:
        failed_count = await mark_unfinished_runs_failed()
        if failed_count:
            logger.warning("Sweep %s marked %d unfinished run(s) failed", sweep_id, failed_count)

    await emit(
        {
            "type": "sweep_failed" if had_failures else "sweep_succeeded",
            "sweep_id": sweep_id,
            "metrics_summary": ranked_metrics,
            "baseline_summary": baseline_summary or None,
        }
    )
