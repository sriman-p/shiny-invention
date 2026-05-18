"""
Tests for the phase-hardening work that closed the orchestrator/sweep gaps.

Covers:
  - Token usage rollup via the new `acp_result` StageEvent
  - Reasoning chunk extraction + persistence
  - Map stage retrieval wiring
  - Cooperative stage cancellation interrupting a long-running stage
  - Permission flow round-trip through the REST endpoint
  - Sweep baseline-diff sign convention (HIGHER vs LOWER is better)
  - BackgroundTask reaper marking stale tasks failed on startup
  - Sweep axes preview endpoint expanding cells correctly
  - Agent registry exposing a non-trivial model catalog with grouped IDs
"""

import asyncio
import time
from datetime import timedelta

import pytest
from pydantic import BaseModel, ValidationError

from acp_client.permissions import handle_permission_request, resolve_permission
from acp_client.registry import ACP_AGENTS
from acp_client.runner import ACPError
from core.background import (
    finish_background_task,
    heartbeat_background_task,
    reap_stale_background_tasks,
    register_background_task,
)
from core.models import BackgroundTask, Project, Run, StageExecution, Sweep
from core.serializers import SweepDetailSerializer
from eval.metrics import compute_metrics, rank_metrics
from eval.stats import compute_baseline_diff, run_statistical_analysis
from pipeline.contracts import (
    AnalyzeOutput,
    CodeSymbol,
    CritiqueScore,
    GeneratedTest,
    GenerateOutput,
    MapOutput,
    Mapping,
    ParseOutput,
    Requirement,
)
from pipeline.few_shot_examples import STAGES, get_static_examples
from pipeline.orchestrator import run_pipeline
from pipeline.stages import map_stage as map_stage_module
from pipeline.stages.base import StageContext, StageEvent, _extract_reasoning_chunks

# ---------------------------------------------------------------------------
# Fakes for stage execution
# ---------------------------------------------------------------------------


class _FakeOutput(BaseModel):
    pass


class _StageEmittingTokens:
    """Stage that emits an `acp_result` event so the orchestrator rolls up usage."""

    name = "parse"

    async def run(self, ctx: StageContext, previous_output, on_event):
        await on_event(
            StageEvent(
                type="acp_result",
                run_id=ctx.run_id,
                stage=self.name,
                payload={"token_usage": {"input_tokens": 7, "output_tokens": 3}},
            )
        )
        await on_event(
            StageEvent(
                type="reasoning",
                run_id=ctx.run_id,
                stage=self.name,
                payload={"kind": "thought", "content": "thinking…", "metadata": {}, "ts": "now"},
            )
        )
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


class _StageThatBlocks:
    """Stage that sleeps forever so we can test cooperative cancellation."""

    name = "parse"

    async def run(self, ctx: StageContext, previous_output, on_event):
        await asyncio.sleep(60)
        return _FakeOutput()


class _StageReturningShortcut:
    """Stage that returns the kind of shallow output a lazy model might produce."""

    name = "parse"

    async def run(self, ctx: StageContext, previous_output, on_event):  # noqa: ARG002
        return _FakeOutput()


class _StageFailsTwiceThenSucceeds:
    """Stage that proves retry attempts re-run the model request path."""

    name = "parse"
    attempts = 0

    async def run(self, ctx: StageContext, previous_output, on_event):  # noqa: ARG002
        type(self).attempts += 1
        if type(self).attempts < 3:
            return _FakeOutput()
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


class _StageAlwaysFailsValidation:
    name = "parse"
    attempts = 0

    async def run(self, ctx: StageContext, previous_output, on_event):  # noqa: ARG002
        type(self).attempts += 1
        return _FakeOutput()


class _StageRaisesAcpTwiceThenSucceeds(_StageFailsTwiceThenSucceeds):
    attempts = 0

    async def run(self, ctx: StageContext, previous_output, on_event):  # noqa: ARG002
        type(self).attempts += 1
        if type(self).attempts < 3:
            raise ACPError("temporary agent failure")
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


# ---------------------------------------------------------------------------
# Token rollup + reasoning persistence
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_orchestrator_rolls_up_token_usage_and_reasoning(monkeypatch, tmp_path):
    project = Project.objects.create(
        name="token-rollup",
        code_path=str(tmp_path),
        requirements_path=str(tmp_path / "requirements.md"),
    )
    run = Run.objects.create(project=project, artifacts_path=str(tmp_path / "artifacts"))

    monkeypatch.setattr("pipeline.orchestrator.STAGE_ORDER", ["parse"])
    monkeypatch.setattr(
        "pipeline.orchestrator.STAGE_CLASSES",
        {"parse": _StageEmittingTokens},
    )

    asyncio.run(run_pipeline(str(run.id)))

    run.refresh_from_db()
    assert run.status == "succeeded"
    stage = StageExecution.objects.get(run=run)
    assert stage.token_usage == {"input_tokens": 7, "output_tokens": 3}
    assert len(stage.reasoning) == 1
    assert stage.reasoning[0]["kind"] == "thought"


@pytest.mark.django_db(transaction=True)
def test_orchestrator_rejects_shortcut_stage_output(monkeypatch, tmp_path):
    project = Project.objects.create(
        name="shortcut-output",
        code_path=str(tmp_path),
        requirements_path=str(tmp_path / "requirements.md"),
    )
    run = Run.objects.create(project=project, artifacts_path=str(tmp_path / "artifacts"))

    monkeypatch.setattr("pipeline.orchestrator.STAGE_ORDER", ["parse"])
    monkeypatch.setattr("pipeline.orchestrator.STAGE_CLASSES", {"parse": _StageReturningShortcut})

    asyncio.run(run_pipeline(str(run.id)))

    run.refresh_from_db()
    stage = StageExecution.objects.get(run=run)
    assert run.status == "failed"
    assert stage.status == "failed"
    assert "expected ParseOutput" in stage.error


@pytest.mark.django_db(transaction=True)
def test_orchestrator_retries_validation_failures_three_times(monkeypatch, tmp_path):
    project = Project.objects.create(
        name="retry-then-success",
        code_path=str(tmp_path),
        requirements_path=str(tmp_path / "requirements.md"),
    )
    run = Run.objects.create(project=project, artifacts_path=str(tmp_path / "artifacts"))
    events: list[dict] = []
    _StageFailsTwiceThenSucceeds.attempts = 0

    monkeypatch.setattr("pipeline.orchestrator.STAGE_ORDER", ["parse"])
    monkeypatch.setattr("pipeline.orchestrator.STAGE_CLASSES", {"parse": _StageFailsTwiceThenSucceeds})

    asyncio.run(run_pipeline(str(run.id), on_event=events.append))

    run.refresh_from_db()
    stage = StageExecution.objects.get(run=run)
    assert _StageFailsTwiceThenSucceeds.attempts == 3
    assert run.status == "succeeded"
    assert stage.status == "succeeded"
    assert [event["payload"]["attempt"] for event in events if event["type"] == "stage_attempt_failed"] == [1, 2]


@pytest.mark.django_db(transaction=True)
def test_orchestrator_retries_acp_failures_three_times(monkeypatch, tmp_path):
    project = Project.objects.create(
        name="retry-acp-then-success",
        code_path=str(tmp_path),
        requirements_path=str(tmp_path / "requirements.md"),
    )
    run = Run.objects.create(project=project, artifacts_path=str(tmp_path / "artifacts"))
    _StageRaisesAcpTwiceThenSucceeds.attempts = 0

    monkeypatch.setattr("pipeline.orchestrator.STAGE_ORDER", ["parse"])
    monkeypatch.setattr("pipeline.orchestrator.STAGE_CLASSES", {"parse": _StageRaisesAcpTwiceThenSucceeds})

    asyncio.run(run_pipeline(str(run.id)))

    run.refresh_from_db()
    assert _StageRaisesAcpTwiceThenSucceeds.attempts == 3
    assert run.status == "succeeded"


@pytest.mark.django_db(transaction=True)
def test_orchestrator_fails_after_three_invalid_attempts(monkeypatch, tmp_path):
    project = Project.objects.create(
        name="retry-then-fail",
        code_path=str(tmp_path),
        requirements_path=str(tmp_path / "requirements.md"),
    )
    run = Run.objects.create(project=project, artifacts_path=str(tmp_path / "artifacts"))
    _StageAlwaysFailsValidation.attempts = 0

    monkeypatch.setattr("pipeline.orchestrator.STAGE_ORDER", ["parse"])
    monkeypatch.setattr("pipeline.orchestrator.STAGE_CLASSES", {"parse": _StageAlwaysFailsValidation})

    asyncio.run(run_pipeline(str(run.id)))

    run.refresh_from_db()
    stage = StageExecution.objects.get(run=run)
    assert _StageAlwaysFailsValidation.attempts == 3
    assert run.status == "failed"
    assert stage.status == "failed"
    assert "expected ParseOutput" in stage.error


@pytest.mark.django_db(transaction=True)
def test_orchestrator_marks_setup_failure_terminal(tmp_path):
    project = Project.objects.create(
        name="setup-failure",
        code_path=str(tmp_path),
        requirements_path=str(tmp_path / "requirements.md"),
    )
    run = Run.objects.create(project=project, artifacts_path=str(tmp_path / "artifacts"), config_snapshot=[])

    asyncio.run(run_pipeline(str(run.id)))

    run.refresh_from_db()
    task = BackgroundTask.objects.get(kind="run", related_id=str(run.id))
    assert run.status == "failed"
    assert task.status == "failed"


# ---------------------------------------------------------------------------
# Cancellation interrupts a blocking stage
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_cancellation_interrupts_blocking_stage(monkeypatch, tmp_path):
    project = Project.objects.create(
        name="cancel-fast",
        code_path=str(tmp_path),
        requirements_path=str(tmp_path / "requirements.md"),
    )
    run = Run.objects.create(project=project, artifacts_path=str(tmp_path / "artifacts"))

    monkeypatch.setattr("pipeline.orchestrator.STAGE_ORDER", ["parse"])
    monkeypatch.setattr("pipeline.orchestrator.STAGE_CLASSES", {"parse": _StageThatBlocks})

    async def _run_and_cancel():
        pipeline_task = asyncio.create_task(run_pipeline(str(run.id)))
        # Wait until the row flips to "running" before cancelling.
        from asgiref.sync import sync_to_async

        @sync_to_async
        def _read_status():
            return Run.objects.only("status").get(id=run.id).status

        @sync_to_async
        def _cancel():
            Run.objects.filter(id=run.id).update(status="cancelled")

        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if (await _read_status()) == "running":
                break
            await asyncio.sleep(0.05)
        await _cancel()
        # Cancel watcher polls every ~1s; allow up to 4s for the stage task to be cancelled.
        await asyncio.wait_for(pipeline_task, timeout=4)

    asyncio.run(_run_and_cancel())

    run.refresh_from_db()
    assert run.status == "cancelled"


# ---------------------------------------------------------------------------
# Reasoning chunk extraction
# ---------------------------------------------------------------------------


def test_extract_reasoning_chunks_handles_acp_payloads():
    chunks = _extract_reasoning_chunks(
        [
            {"session_update": "agent_message_chunk", "content": {"text": "hello"}},
            {"session_update": "agent_thought_chunk", "content": {"text": "i am thinking"}},
            {"session_update": "tool_call", "tool_call_id": "read_file", "status": "started"},
            {"session_update": "tool_call_update", "tool_call_id": "read_file", "status": "completed"},
        ]
    )
    kinds = [c["kind"] for c in chunks]
    assert kinds == ["text", "thought", "tool_call", "tool_result"]


def test_extract_reasoning_chunks_handles_cursor_payloads():
    chunks = _extract_reasoning_chunks(
        [
            {"type": "delta", "update": {"text": "streamed"}},
            {"type": "step", "step": {"title": "Thinking about it"}},
            {"type": "step", "step": {"title": "calling tool"}},
            {"type": "cursor_sdk_result", "agent_id": "agent-1", "duration_ms": 12},
        ]
    )
    kinds = [c["kind"] for c in chunks]
    # First step is recognized as a thought because the title contains "think".
    assert kinds == ["text", "thought", "tool_call", "model_message"]


def test_contracts_reject_shortcut_scores_and_empty_content():
    with pytest.raises(ValidationError):
        CritiqueScore(
            test_file="tests/test_req.py",
            relevance=100,
            completeness=5,
            correctness=5,
            decision="accept",
            notes="inflated score",
        )

    with pytest.raises(ValidationError):
        Mapping(requirement_id="REQ-1", confidence=2.0, rationale="too confident")

    with pytest.raises(ValidationError):
        GeneratedTest(requirement_id="REQ-1", file_path="tests/test_req.py", code="", rationale="empty code")

    with pytest.raises(ValidationError):
        Requirement(
            id="REQ-1",
            title="Shortcut",
            description="done",
            type="functional",
            priority="high",
            acceptance_criteria=[],
            source_location="requirements.md:1",
        )


def test_stage_output_field_selection_strips_schema_metadata():
    from pipeline.stages.trace import TraceStage

    data = {
        "$defs": {"TraceabilityRow": {}},
        "properties": {},
        "matrix": [
            {
                "requirement_id": "REQ-1",
                "symbol": "TodoStore.create",
                "test_files": ["tests/test_req.py"],
                "coverage_status": "covered",
            }
        ],
        "gap_report_md": "All covered.",
    }

    assert TraceStage().select_output_fields(data, "matrix", "gap_report_md") == {
        "matrix": data["matrix"],
        "gap_report_md": "All covered.",
    }


def test_critique_score_paths_are_reconciled_to_generated_files():
    from pipeline.stages.critique import _reconcile_score_test_files

    parse = ParseOutput(
        requirements=[
            Requirement(
                id="REQ-001",
                title="Create Todo",
                description="Users can create todos.",
                type="functional",
                priority="high",
                acceptance_criteria=["Todo is created."],
                source_location="requirements.md:1",
            )
        ]
    )
    symbol = CodeSymbol(
        qualified_name="TodoStore.create",
        kind="method",
        file_path="src/todo.py",
        line_start=1,
        line_end=3,
        signature="def create(self, title: str) -> Todo",
        docstring="Create a todo.",
    )
    generate = GenerateOutput(
        map=MapOutput(
            analyze=AnalyzeOutput(parse=parse, symbols=[symbol], project_summary="Todo store."),
            mappings=[Mapping(requirement_id="REQ-001", symbol=symbol, confidence=1.0, rationale="Direct method.")],
        ),
        tests=[
            GeneratedTest(
                requirement_id="REQ-001",
                file_path="tests/test_req001_todo_store_create.py",
                code="def test_create():\n    assert True\n",
                target_symbol="TodoStore.create",
                rationale="Covers create.",
            )
        ],
    )
    data = {
        "scores": [
            {
                "test_file": "tests/test_req_001_todo_store_create.py",
                "relevance": 5,
                "completeness": 5,
                "correctness": 5,
                "decision": "accept",
                "notes": "Matches requirement.",
            }
        ],
        "revised_tests": [],
    }

    _reconcile_score_test_files(data, generate)

    assert data["scores"][0]["test_file"] == "tests/test_req001_todo_store_create.py"


# ---------------------------------------------------------------------------
# Map stage retrieval wiring
# ---------------------------------------------------------------------------


class _FakeRetriever:
    documents = ["fake"]

    def __init__(self):
        self.queries = []

    def search(self, query, k, filter):  # noqa: A002 - mirror real signature
        self.queries.append(query)
        return []


def test_map_stage_calls_retriever_for_full_context(monkeypatch):
    fake = _FakeRetriever()
    monkeypatch.setattr(
        map_stage_module,
        "_get_or_build_retriever",
        lambda ctx: fake,
    )

    class _Req:
        id = "REQ-1"
        title = "User can log in"
        description = "Login flow accepts username/password."

    text = map_stage_module._format_retrieval_hints(fake, [_Req()])
    assert fake.queries, "Retriever.search must be invoked for retrieval hints"
    assert "no relevant snippets" in text  # search returned []


# ---------------------------------------------------------------------------
# Permission flow
# ---------------------------------------------------------------------------


def test_permissions_round_trip_unblocks_handler():
    async def _flow():
        task = asyncio.create_task(handle_permission_request("run-x", "prompt-1", mode="manual"))
        # Give the future a chance to register.
        await asyncio.sleep(0)
        ok = resolve_permission("run-x", "prompt-1", {"outcome": "allowed_once"})
        result = await asyncio.wait_for(task, timeout=2)
        return ok, result

    ok, result = asyncio.run(_flow())
    assert ok is True
    assert result == {"outcome": "allowed_once"}


# ---------------------------------------------------------------------------
# Baseline diff sign convention
# ---------------------------------------------------------------------------


def test_baseline_diff_higher_and_lower_is_better():
    ranked = rank_metrics(
        [
            {
                "run_id": "best",
                "quality_score": 0.9,
                "traceability_score": 0.9,
                "critique_accept_rate": 0.85,
                "latency_total_ms": 200,
                "tokens_total": 100,
            },
            {
                "run_id": "worst",
                "quality_score": 0.4,
                "traceability_score": 0.4,
                "critique_accept_rate": 0.3,
                "latency_total_ms": 1000,
                "tokens_total": 500,
            },
        ]
    )
    diff = compute_baseline_diff(ranked)
    assert diff["baseline"]["run_id"] == "worst"
    winner_lift = diff["lifts"][0]["lift"]
    assert winner_lift["quality_score"] > 0  # higher is better
    assert winner_lift["latency_total_ms"] > 0  # lower latency = positive lift
    assert winner_lift["tokens_total"] > 0


def test_baseline_diff_uses_last_ranked_configuration():
    ranked = [
        {"run_id": "winner", "rank": 1, "quality_score": 0.8, "traceability_score": 0.9},
        {"run_id": "last-ranked", "rank": 2, "quality_score": 0.8, "traceability_score": 0.4},
    ]

    diff = compute_baseline_diff(ranked)

    assert diff["baseline"]["run_id"] == "last-ranked"


def test_baseline_diff_prefers_explicit_comparison_baseline():
    ranked = [
        {"run_id": "winner", "rank": 1, "quality_score": 0.9, "traceability_score": 1.0},
        {"run_id": "direct", "rank": 2, "quality_score": 0.1, "traceability_score": 0.0, "comparison_baseline": True},
        {"run_id": "unmarked-worst", "rank": 3, "quality_score": 0.0, "traceability_score": 0.0},
    ]

    diff = compute_baseline_diff(ranked)

    assert diff["baseline"]["run_id"] == "direct"


def test_anova_groups_by_agent_when_axis_varies():
    metrics = [
        {
            "agent_id": "codex",
            "model_id": "gpt-5.5/low",
            "prompt_strategy": "zero_shot",
            "context_mode": "full",
            "quality_score": 0.8,
            "traceability_score": 0.8,
            "test_pass_rate": 0.7,
            "critique_accept_rate": 0.7,
        },
        {
            "agent_id": "codex",
            "model_id": "gpt-5.5/low",
            "prompt_strategy": "zero_shot",
            "context_mode": "full",
            "quality_score": 0.82,
            "traceability_score": 0.81,
            "test_pass_rate": 0.71,
            "critique_accept_rate": 0.72,
        },
        {
            "agent_id": "claude-code",
            "model_id": "claude-sonnet-4.5",
            "prompt_strategy": "zero_shot",
            "context_mode": "full",
            "quality_score": 0.55,
            "traceability_score": 0.5,
            "test_pass_rate": 0.4,
            "critique_accept_rate": 0.45,
        },
        {
            "agent_id": "claude-code",
            "model_id": "claude-sonnet-4.5",
            "prompt_strategy": "zero_shot",
            "context_mode": "full",
            "quality_score": 0.58,
            "traceability_score": 0.52,
            "test_pass_rate": 0.42,
            "critique_accept_rate": 0.46,
        },
    ]
    report = run_statistical_analysis(metrics)
    assert any(key.startswith("agent_") for key in report["anova"].keys())


def test_metrics_include_map_retrieval_and_faiss_evidence():
    metrics = compute_metrics(
        {
            "stages": [
                {
                    "stage": "parse",
                    "status": "succeeded",
                    "latency_ms": 1,
                    "token_usage": {},
                    "output_payload": {
                        "requirements": [
                            {"id": "REQ-1"},
                            {"id": "REQ-2"},
                        ]
                    },
                },
                {
                    "stage": "map",
                    "status": "succeeded",
                    "latency_ms": 10,
                    "token_usage": {},
                    "output_payload": {
                        "mappings": [
                            {
                                "requirement_id": "REQ-1",
                                "symbol": {"qualified_name": "app.foo"},
                                "confidence": 0.8,
                                "evidence_snippets": ["def foo(): ...", "return foo"],
                            },
                            {
                                "requirement_id": "REQ-2",
                                "symbol": None,
                                "confidence": 0.4,
                                "evidence_snippets": [],
                            },
                        ]
                    },
                }
            ]
        }
    )

    assert metrics["mapped_requirements_rate"] == 0.5
    assert metrics["mapping_confidence_avg"] == pytest.approx(0.6)
    assert metrics["faiss_evidence_count"] == 2
    assert metrics["faiss_evidence_per_mapping"] == 1.0


def test_quality_score_penalizes_broken_pipeline_provenance():
    metrics = compute_metrics(
        {
            "stages": [
                {
                    "stage": "parse",
                    "status": "succeeded",
                    "latency_ms": 1,
                    "token_usage": {},
                    "output_payload": {
                        "requirements": [
                            {"id": "REQ-1"},
                            {"id": "REQ-2"},
                        ]
                    },
                },
                {
                    "stage": "map",
                    "status": "succeeded",
                    "latency_ms": 1,
                    "token_usage": {},
                    "output_payload": {"mappings": []},
                },
                {
                    "stage": "generate",
                    "status": "succeeded",
                    "latency_ms": 1,
                    "token_usage": {},
                    "output_payload": {"tests": []},
                },
                {
                    "stage": "critique",
                    "status": "succeeded",
                    "latency_ms": 1,
                    "token_usage": {},
                    "output_payload": {
                        "scores": [
                            {
                                "test_file": "tests/test_req_1.py",
                                "relevance": 5,
                                "completeness": 5,
                                "correctness": 5,
                                "decision": "accept",
                            }
                        ]
                    },
                },
                {
                    "stage": "trace",
                    "status": "succeeded",
                    "latency_ms": 1,
                    "token_usage": {},
                    "output_payload": {
                        "matrix": [
                            {
                                "requirement_id": "REQ-1",
                                "test_files": ["tests/test_req_1.py"],
                                "coverage_status": "covered",
                            }
                        ]
                    },
                },
            ]
        }
    )

    assert metrics["total_requirements"] == 2
    assert metrics["traceability_score"] == 0.5
    assert metrics["trace_matrix_completion_rate"] == 0.5
    assert metrics["mapped_requirements_rate"] == 0.0
    assert metrics["generation_coverage_rate"] == 0.0
    assert metrics["critique_coverage_rate"] == 0.0
    assert metrics["quality_score"] < 0.5


def test_anova_exposes_significance_and_effect_magnitudes():
    metrics = [
        {
            "prompt_strategy": "zero_shot",
            "context_mode": "minimal",
            "quality_score": 0.1,
            "traceability_score": 0.1,
            "critique_accept_rate": 0.1,
            "mapping_confidence_avg": 0.1,
            "mapped_requirements_rate": 0.1,
            "faiss_evidence_per_mapping": 0.0,
        },
        {
            "prompt_strategy": "zero_shot",
            "context_mode": "minimal",
            "quality_score": 0.12,
            "traceability_score": 0.12,
            "critique_accept_rate": 0.12,
            "mapping_confidence_avg": 0.1,
            "mapped_requirements_rate": 0.1,
            "faiss_evidence_per_mapping": 0.0,
        },
        {
            "prompt_strategy": "few_shot_dynamic",
            "context_mode": "full",
            "quality_score": 0.9,
            "traceability_score": 0.9,
            "critique_accept_rate": 0.9,
            "mapping_confidence_avg": 0.9,
            "mapped_requirements_rate": 1.0,
            "faiss_evidence_per_mapping": 3.0,
        },
        {
            "prompt_strategy": "few_shot_dynamic",
            "context_mode": "full",
            "quality_score": 0.92,
            "traceability_score": 0.92,
            "critique_accept_rate": 0.92,
            "mapping_confidence_avg": 0.92,
            "mapped_requirements_rate": 1.0,
            "faiss_evidence_per_mapping": 4.0,
        },
    ]

    report = run_statistical_analysis(metrics)
    quality = report["anova"]["strategy_quality_score"]
    assert quality["significant"] is True
    assert quality["effect_magnitude"] == "large"
    pairwise = report["pairwise"]["strategy_quality_score"][0]
    assert pairwise["cohens_d_magnitude"] == "large"


def test_static_few_shot_examples_cover_seed_projects_and_stages():
    for project_name in ("todo-api", "url-shortener", "calculator"):
        for stage in STAGES:
            example = get_static_examples(project_name, stage, "few_shot_static")
            assert "```json" in example, f"{project_name}/{stage} missing JSON example"


def test_static_few_shot_examples_only_apply_to_static_strategy():
    assert get_static_examples("todo-api", "parse", "zero_shot") == ""
    assert get_static_examples("todo-api", "parse", "chain_of_thought") == ""
    assert get_static_examples("todo-api", "parse", "few_shot_dynamic") == ""


# ---------------------------------------------------------------------------
# BackgroundTask reaper
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_reaper_marks_stale_run_failed(tmp_path):
    project = Project.objects.create(
        name="reaper",
        code_path=str(tmp_path),
        requirements_path=str(tmp_path / "requirements.md"),
    )
    run = Run.objects.create(project=project, status="running", artifacts_path=str(tmp_path))
    asyncio.run(register_background_task(kind="run", related_id=str(run.id)))

    # Backdate the heartbeat so the reaper considers it stale.
    BackgroundTask.objects.filter(related_id=str(run.id)).update(
        last_heartbeat=BackgroundTask.objects.get(related_id=str(run.id)).last_heartbeat - timedelta(hours=1)
    )

    counts = reap_stale_background_tasks()
    assert counts["runs"] == 1
    run.refresh_from_db()
    assert run.status == "failed"


@pytest.mark.django_db(transaction=True)
def test_reaper_marks_stale_sweep_children_failed(tmp_path):
    project = Project.objects.create(
        name="stale-sweep",
        code_path=str(tmp_path),
        requirements_path=str(tmp_path / "requirements.md"),
    )
    sweep = Sweep.objects.create(project=project, status="running", matrix=[])
    run = Run.objects.create(project=project, status="running", artifacts_path=str(tmp_path))
    sweep.runs.add(run)
    asyncio.run(register_background_task(kind="sweep", related_id=str(sweep.id)))

    BackgroundTask.objects.filter(related_id=str(sweep.id)).update(
        last_heartbeat=BackgroundTask.objects.get(related_id=str(sweep.id)).last_heartbeat - timedelta(hours=1)
    )

    counts = reap_stale_background_tasks()
    assert counts["sweeps"] == 1
    assert counts["runs"] == 1
    sweep.refresh_from_db()
    run.refresh_from_db()
    assert sweep.status == "failed"
    assert run.status == "failed"


@pytest.mark.django_db(transaction=True)
def test_heartbeat_keeps_task_alive(tmp_path):
    project = Project.objects.create(
        name="heartbeat",
        code_path=str(tmp_path),
        requirements_path=str(tmp_path / "requirements.md"),
    )
    run = Run.objects.create(project=project, status="running", artifacts_path=str(tmp_path))
    asyncio.run(register_background_task(kind="run", related_id=str(run.id)))
    asyncio.run(heartbeat_background_task(str(run.id)))
    counts = reap_stale_background_tasks()
    # No stale tasks because the heartbeat is fresh.
    assert counts["tasks"] == 0
    asyncio.run(finish_background_task(str(run.id), "succeeded"))
    assert BackgroundTask.objects.get(related_id=str(run.id)).status == "succeeded"


# ---------------------------------------------------------------------------
# Sweep axes expansion endpoint
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_sweep_preview_expands_axes(client, tmp_path):
    project = Project.objects.create(
        name="preview",
        code_path=str(tmp_path),
        requirements_path=str(tmp_path / "requirements.md"),
    )
    response = client.post(
        f"/api/v1/projects/{project.id}/sweeps/preview",
        data={
            "axes": {
                "agents": [
                    {"agent_id": "codex", "model_id": "gpt-5.5/low"},
                    {"agent_id": "claude-code", "model_id": "claude-sonnet-4.5"},
                ],
                "strategies": ["zero_shot", "chain_of_thought"],
                "contexts": ["minimal", "full"],
            }
        },
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["total_cells"] == 2 * 2 * 2 == 8
    assert len(data["matrix"]) == 8
    assert {(c["agent_id"], c["model_id"]) for c in data["matrix"]} == {
        ("codex", "gpt-5.5/low"),
        ("claude-code", "claude-sonnet-4.5"),
    }


@pytest.mark.django_db(transaction=True)
def test_sweep_preview_pairs_does_not_cartesian_product(client, tmp_path):
    """Regression: when the UI sends individually toggled strategy/context
    cells via `pairs`, the backend must NOT cross them again. Previously we
    sent the same enabled list as both `strategies` and `contexts`, which
    turned 15 chosen cells into 15x15=225 runs (and 16 into 256)."""
    project = Project.objects.create(
        name="pairs",
        code_path=str(tmp_path),
        requirements_path=str(tmp_path / "requirements.md"),
    )
    pairs = [
        {"prompt_strategy": "zero_shot", "context_mode": "minimal"},
        {"prompt_strategy": "zero_shot", "context_mode": "local"},
        {"prompt_strategy": "zero_shot", "context_mode": "module"},
        {"prompt_strategy": "zero_shot", "context_mode": "full"},
        {"prompt_strategy": "chain_of_thought", "context_mode": "minimal"},
        {"prompt_strategy": "chain_of_thought", "context_mode": "full"},
        {"prompt_strategy": "few_shot_static", "context_mode": "full"},
        {"prompt_strategy": "few_shot_dynamic", "context_mode": "full"},
        {"prompt_strategy": "few_shot_static", "context_mode": "local"},
        {"prompt_strategy": "few_shot_static", "context_mode": "minimal"},
        {"prompt_strategy": "few_shot_static", "context_mode": "module"},
        {"prompt_strategy": "few_shot_dynamic", "context_mode": "minimal"},
        {"prompt_strategy": "few_shot_dynamic", "context_mode": "local"},
        {"prompt_strategy": "few_shot_dynamic", "context_mode": "module"},
        {"prompt_strategy": "chain_of_thought", "context_mode": "local"},
    ]
    response = client.post(
        f"/api/v1/projects/{project.id}/sweeps/preview",
        data={
            "axes": {
                "agents": [{"agent_id": "claude-code", "model_id": "default"}],
                "pairs": pairs,
            }
        },
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    # Exactly 15 enabled cells x 1 agent = 15 runs (NOT 15 x 15 = 225).
    assert data["summary"]["pair_count"] == 15
    assert data["summary"]["total_cells"] == 15
    assert len(data["matrix"]) == 15
    # Spot-check that each pair appears exactly once for the agent.
    rendered_pairs = {(c["prompt_strategy"], c["context_mode"]) for c in data["matrix"]}
    expected_pairs = {(p["prompt_strategy"], p["context_mode"]) for p in pairs}
    assert rendered_pairs == expected_pairs


@pytest.mark.django_db(transaction=True)
def test_sweep_preview_can_include_direct_acp_baseline(client, tmp_path):
    project = Project.objects.create(
        name="pairs-direct-baseline",
        code_path=str(tmp_path),
        requirements_path=str(tmp_path / "requirements.md"),
    )
    response = client.post(
        f"/api/v1/projects/{project.id}/sweeps/preview",
        data={
            "axes": {
                "agents": [{"agent_id": "codex", "model_id": "gpt-5.5/low"}],
                "include_direct_baseline": True,
                "pairs": [{"prompt_strategy": "zero_shot", "context_mode": "full"}],
            }
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["pair_count"] == 2
    assert data["summary"]["total_cells"] == 2
    baseline = data["matrix"][0]
    assert baseline["prompt_strategy"] == "direct_acp_baseline"
    assert baseline["context_mode"] == "direct"
    assert baseline["run_mode"] == "direct_acp_baseline"
    assert baseline["comparison_baseline"] is True


@pytest.mark.django_db(transaction=True)
def test_sweep_preview_pairs_multiplies_by_agents(client, tmp_path):
    """The pairs form should still multiply by the number of agent rows --
    that's the desired axis -- but never re-multiply pairs against itself."""
    project = Project.objects.create(
        name="pairs-multi",
        code_path=str(tmp_path),
        requirements_path=str(tmp_path / "requirements.md"),
    )
    response = client.post(
        f"/api/v1/projects/{project.id}/sweeps/preview",
        data={
            "axes": {
                "agents": [
                    {"agent_id": "codex", "model_id": "gpt-5.5/low"},
                    {"agent_id": "codex", "model_id": "gpt-5.5/medium"},
                    {"agent_id": "claude-code", "model_id": "default"},
                ],
                "pairs": [
                    {"prompt_strategy": "zero_shot", "context_mode": "full"},
                    {"prompt_strategy": "chain_of_thought", "context_mode": "minimal"},
                ],
            }
        },
        content_type="application/json",
    )
    data = response.json()
    # 3 agents x 2 pairs = 6 runs total.
    assert data["summary"]["total_cells"] == 6
    assert data["summary"]["pair_count"] == 2
    assert data["summary"]["agent_count"] == 3


@pytest.mark.django_db(transaction=True)
def test_sweep_detail_serializes_runs_in_matrix_order(tmp_path):
    project = Project.objects.create(
        name="sweep-order",
        code_path=str(tmp_path),
        requirements_path=str(tmp_path / "requirements.md"),
    )
    first_run = Run.objects.create(project=project, config_snapshot={"prompt_strategy": "zero_shot"})
    second_run = Run.objects.create(project=project, config_snapshot={"prompt_strategy": "few_shot_static"})
    sweep = Sweep.objects.create(
        project=project,
        matrix=[
            {"prompt_strategy": "zero_shot", "context_mode": "minimal"},
            {"prompt_strategy": "few_shot_static", "context_mode": "minimal"},
        ],
    )
    sweep.runs.add(first_run, second_run)

    data = SweepDetailSerializer(sweep).data

    assert [row["id"] for row in data["runs"]] == [str(first_run.id), str(second_run.id)]


@pytest.mark.django_db(transaction=True)
def test_sweep_create_accepts_axes(client, monkeypatch, tmp_path):
    project = Project.objects.create(
        name="axes-create",
        code_path=str(tmp_path),
        requirements_path=str(tmp_path / "requirements.md"),
    )

    started: list[str] = []

    class _FakeThread:
        def __init__(self, target, daemon=False):
            self._target = target

        def start(self):
            started.append("started")

    monkeypatch.setattr("core.views.threading.Thread", _FakeThread)

    response = client.post(
        f"/api/v1/projects/{project.id}/sweeps",
        data={
            "axes": {
                "agents": [{"agent_id": "codex", "model_id": "gpt-5.5/low"}],
                "strategies": ["zero_shot"],
                "contexts": ["minimal", "full"],
            }
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    sweep = Sweep.objects.get(project=project)
    assert len(sweep.matrix) == 2  # 1 agent x 1 strategy x 2 contexts
    assert started == ["started"]


# ---------------------------------------------------------------------------
# Agent registry catalog richness
# ---------------------------------------------------------------------------


def test_each_agent_exposes_grouped_models():
    for agent_id, spec in ACP_AGENTS.items():
        assert spec.model_options, f"{agent_id} has no model_options"
        # Every agent should publish at least one named group so the picker
        # can render a tidy combobox; exhaustive catalog is asserted below.
        assert spec.model_groups, f"{agent_id} has no model_groups"


def test_codex_has_full_effort_grid():
    spec = ACP_AGENTS["codex"]
    base_models = {"gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.3-codex", "gpt-5.2"}
    efforts = {"low", "medium", "high", "xhigh"}
    for base in base_models:
        for effort in efforts:
            assert f"{base}/{effort}" in spec.model_options, f"codex missing {base}/{effort}"


def test_claude_catalog_includes_adapter_shortcuts_and_bedrock_profiles():
    """The claude-code catalog combines the adapter's shortcut ids
    (default/sonnet[1m]/opus[1m]/haiku) with concrete Bedrock inference
    profile ids the user can select for direct provider routing."""
    spec = ACP_AGENTS["claude-code"]
    assert spec.model == "default"
    # Adapter shortcuts MUST be present so set_session_model can take that
    # ACP-native path when the user picks them.
    for shortcut in {"default", "sonnet[1m]", "opus[1m]", "haiku"}:
        assert shortcut in spec.model_options, f"missing adapter shortcut: {shortcut}"
    # At least one Bedrock-style id is offered so users on Bedrock have a
    # one-click escape hatch for the adapter's stale internal mapping.
    assert any(model.startswith("us.anthropic.") for model in spec.model_options), (
        "claude-code catalog must include at least one Bedrock inference profile id"
    )


def test_extract_suggested_model_matches_runner_passthrough_path():
    """The new env-var passthrough in run_acp_prompt should accept any model
    id the user types in the picker, including fully-qualified Bedrock
    inference profile ids that the adapter doesn't advertise via ACP."""
    # The runner imports inside the spawn block; we just verify the helper
    # imports cleanly so refactors don't break the public surface.
    from acp_client.runner import run_acp_prompt as _run_acp_prompt

    assert callable(_run_acp_prompt)


def test_cursor_model_alias_resolves_to_advertised_option_suffix():
    """Cursor Agent advertises Composer 2 with ACP option metadata."""
    from acp_client.runner import _resolve_advertised_model_id

    assert (
        _resolve_advertised_model_id(
            "composer-2",
            ["default[]", "composer-2[fast=true]", "gpt-5.5[context=272k,reasoning=medium,fast=false]"],
        )
        == "composer-2[fast=true]"
    )


def test_model_alias_resolution_keeps_ambiguous_ids_on_default_path():
    from acp_client.runner import _resolve_advertised_model_id

    assert _resolve_advertised_model_id("composer-2", ["composer-2[fast=true]", "composer-2[fast=false]"]) == ""


# ---------------------------------------------------------------------------
# Live model discovery endpoint
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_agent_models_endpoint_returns_static_when_discovery_unavailable(client, monkeypatch):
    """When ACP discovery returns an empty list (e.g. SDK not installed), the
    endpoint falls back to the agent's static catalog so the UI still works."""
    from acp_client import runner as runner_module

    async def _empty_discover(agent_id, *, cwd=None, timeout_s=60):
        return []

    monkeypatch.setattr(runner_module, "discover_agent_models", _empty_discover)
    response = client.get("/api/v1/agents/claude-code/models")
    assert response.status_code == 200
    data = response.json()
    assert data["agent_id"] == "claude-code"
    assert data["discovered"] is False
    assert "default" in data["models"]
    assert data["models"] == data["static"]


@pytest.mark.django_db(transaction=True)
def test_agent_models_endpoint_uses_discovery_when_present(client, monkeypatch):
    """When discovery returns a real list, the endpoint surfaces it as the
    `models` field so the frontend `<ModelSelect>` prefers it over the
    static catalog."""
    import core.views as views
    from acp_client import runner as runner_module

    async def _live_discover(agent_id, *, cwd=None, timeout_s=60):
        return ["live-sonnet", "live-opus"]

    monkeypatch.setattr(runner_module, "discover_agent_models", _live_discover)
    # Clear the per-process TTL cache so the test gets a fresh discovery.
    views._AGENT_MODEL_CACHE.clear()
    response = client.get("/api/v1/agents/claude-code/models")
    assert response.status_code == 200
    data = response.json()
    assert data["discovered"] is True
    assert data["models"] == ["live-sonnet", "live-opus"]
    # The static fallback list still ships in the response for reference.
    assert "default" in data["static"]


@pytest.mark.django_db(transaction=True)
def test_agent_models_endpoint_unknown_agent_returns_404(client):
    response = client.get("/api/v1/agents/does-not-exist/models")
    assert response.status_code == 404
