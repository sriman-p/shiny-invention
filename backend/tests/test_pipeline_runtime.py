"""Regression tests for async pipeline and sweep runtime behavior."""

import asyncio
from pathlib import Path

import pytest

from core.models import Project, Run, Sweep
from pipeline.contracts import ParseOutput, Requirement
from pipeline.orchestrator import run_pipeline
from pipeline.stages.base import StageContext, StageEvent


class FakeStage:
    name = "parse"

    async def run(self, ctx: StageContext, previous_output, on_event) -> ParseOutput:
        await on_event(StageEvent(type="progress", run_id=ctx.run_id, stage=self.name))
        return ParseOutput(
            requirements=[
                Requirement(
                    id="REQ-1",
                    title="Do work",
                    description="The system does useful work.",
                    type="functional",
                    priority="high",
                    acceptance_criteria=["Useful work is completed."],
                    source_location="requirements.md:1",
                )
            ]
        )


@pytest.mark.django_db(transaction=True)
def test_run_pipeline_uses_async_safe_orm(monkeypatch, tmp_path):
    project = Project.objects.create(
        name="async-pipeline",
        code_path=str(tmp_path),
        requirements_path=str(tmp_path / "requirements.md"),
    )
    run = Run.objects.create(project=project, artifacts_path=str(tmp_path / "artifacts"))

    monkeypatch.setattr("pipeline.orchestrator.STAGE_ORDER", ["parse"])
    monkeypatch.setattr("pipeline.orchestrator.STAGE_CLASSES", {"parse": FakeStage})

    asyncio.run(run_pipeline(str(run.id)))

    run.refresh_from_db()
    assert run.status == "succeeded"
    assert run.stages.get(stage="parse").status == "succeeded"


@pytest.mark.django_db(transaction=True)
def test_sweep_runs_use_isolated_artifact_directories(monkeypatch, tmp_path):
    project = Project.objects.create(
        name="sweep-artifacts",
        code_path=str(tmp_path / "source"),
        requirements_path=str(tmp_path / "source" / "requirements.md"),
    )
    sweep = Sweep.objects.create(
        project=project,
        matrix=[{"prompt_strategy": "zero_shot", "context_mode": "full", "agent_id": "claude-code"}],
    )

    async def fake_run_pipeline(run_id: str, **_kwargs) -> None:
        run = await Run.objects.aget(id=run_id)
        run.status = "succeeded"
        await run.asave()

    monkeypatch.setattr("pipeline.orchestrator.run_pipeline", fake_run_pipeline)

    from eval.runner import run_sweep

    asyncio.run(run_sweep(str(sweep.id)))

    run = sweep.runs.get()
    assert run.artifacts_path != project.code_path
    assert run.artifacts_path.endswith(f"data/runs/{run.id}")
    assert Path(run.artifacts_path).is_dir()


@pytest.mark.django_db(transaction=True)
def test_sweep_runs_configs_in_four_run_batches(monkeypatch, tmp_path):
    project = Project.objects.create(
        name="sweep-parallel",
        code_path=str(tmp_path / "source"),
        requirements_path=str(tmp_path / "source" / "requirements.md"),
    )
    sweep = Sweep.objects.create(
        project=project,
        matrix=[
            {"prompt_strategy": f"strategy_{index}", "context_mode": "full", "agent_id": "codex"}
            for index in range(8)
        ],
    )

    active = 0
    max_active = 0

    async def fake_run_pipeline(run_id: str, **_kwargs) -> None:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.05)
        active -= 1
        run = await Run.objects.aget(id=run_id)
        run.status = "succeeded"
        await run.asave()

    monkeypatch.setattr("pipeline.orchestrator.run_pipeline", fake_run_pipeline)

    from eval.runner import run_sweep

    asyncio.run(run_sweep(str(sweep.id)))

    assert max_active == 4
    assert sweep.runs.count() == 8


@pytest.mark.django_db(transaction=True)
def test_sweep_metrics_exclude_failed_runs(monkeypatch, tmp_path):
    project = Project.objects.create(
        name="sweep-metrics",
        code_path=str(tmp_path / "source"),
        requirements_path=str(tmp_path / "source" / "requirements.md"),
    )
    sweep = Sweep.objects.create(
        project=project,
        matrix=[
            {"prompt_strategy": "zero_shot", "context_mode": "minimal", "agent_id": "codex"},
            {"prompt_strategy": "zero_shot", "context_mode": "full", "agent_id": "codex"},
        ],
    )

    async def fake_run_pipeline(run_id: str, **_kwargs) -> None:
        run = await Run.objects.aget(id=run_id)
        snapshot = run.config_snapshot or {}
        run.status = "failed" if snapshot.get("context_mode") == "minimal" else "succeeded"
        await run.asave()

    monkeypatch.setattr("pipeline.orchestrator.run_pipeline", fake_run_pipeline)

    from eval.runner import run_sweep

    asyncio.run(run_sweep(str(sweep.id)))

    sweep.refresh_from_db()
    assert sweep.status == "failed"
    assert len(sweep.metrics_summary) == 1
    assert sweep.metrics_summary[0]["context_mode"] == "full"
    assert set(sweep.runs.values_list("status", flat=True)) == {"failed", "succeeded"}
