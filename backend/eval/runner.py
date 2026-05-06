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

The sweep runner modifies the project's AgentConfig records during execution
to set the prompt_strategy and context_mode for each configuration. This means
sweeps should not run concurrently on the same project, as they would interfere
with each other's agent configurations.
"""

import logging
from typing import Any, Awaitable, Callable

from .metrics import compute_metrics
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

    from core.models import AgentConfig, Run, Sweep

    sweep = Sweep.objects.select_related("project").get(id=sweep_id)
    project = sweep.project

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
    sweep.save()

    await emit({"type": "sweep_started", "sweep_id": sweep_id})

    # Accumulate metrics from all runs for statistical analysis
    all_metrics = []

    for i, config in enumerate(sweep.matrix):
        # Extract configuration values, with safe defaults for malformed entries
        strategy = config.get("prompt_strategy", "zero_shot") if isinstance(config, dict) else "zero_shot"
        context_mode = config.get("context_mode", "full") if isinstance(config, dict) else "full"
        agent_id = config.get("agent_id", "claude-code") if isinstance(config, dict) else "claude-code"

        # Create a new Run for this configuration
        run = Run.objects.create(
            project=project,
            config_snapshot={
                "prompt_strategy": strategy,
                "context_mode": context_mode,
                "agent_id": agent_id,
                "permissions": "auto",
            },
            artifacts_path=str(project.code_path),
        )
        # Associate this run with the sweep
        sweep.runs.add(run)

        # Update the project's agent configs for ALL stages to use this
        # configuration. This is what makes each sweep run use a different
        # prompt strategy / context mode / agent.
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

            await run_pipeline(str(run.id))
        except Exception as e:
            logger.exception("Sweep run %s failed: %s", run.id, e)

        # Compute metrics from the completed run's stage data
        run.refresh_from_db()
        run_data = {"stages": list(run.stages.values("stage", "output_payload", "latency_ms", "token_usage"))}
        metrics = compute_metrics(run_data)
        # Tag the metrics with the configuration used for this run
        metrics["prompt_strategy"] = strategy
        metrics["context_mode"] = context_mode
        metrics["agent_id"] = agent_id
        metrics["run_id"] = str(run.id)
        all_metrics.append(metrics)

        await emit(
            {
                "type": "sweep_run_completed",
                "sweep_id": sweep_id,
                "run_id": str(run.id),
                "config_index": i,
                "metrics": metrics,
            }
        )

    # Perform statistical analysis comparing all configurations
    stats = run_statistical_analysis(all_metrics)
    markdown_report = generate_markdown_report(stats)

    # Store results on the sweep object
    sweep.metrics_summary = all_metrics
    sweep.stats_report = {**stats, "markdown": markdown_report}
    sweep.status = "succeeded"
    sweep.save()

    await emit(
        {
            "type": "sweep_succeeded",
            "sweep_id": sweep_id,
            "metrics_summary": all_metrics,
        }
    )
