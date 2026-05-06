"""Regression tests for async pipeline and sweep runtime behavior."""

import asyncio
from pathlib import Path

import pytest
from pydantic import BaseModel

from core.models import Project, Run, Sweep
from pipeline.orchestrator import run_pipeline
from pipeline.stages.base import StageContext, StageEvent


class EmptyOutput(BaseModel):
    """Minimal stage output used by the fake stage."""


class FakeStage:
    name = "parse"

    async def run(self, ctx: StageContext, previous_output: BaseModel | None, on_event) -> BaseModel:
        await on_event(StageEvent(type="progress", run_id=ctx.run_id, stage=self.name))
        return EmptyOutput()


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

    async def fake_run_pipeline(run_id: str) -> None:
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
