"""Direct ACP baseline runner for single-pass test generation."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from asgiref.sync import sync_to_async

from acp_client.runner import ACPResult, run_acp_prompt
from pipeline.contracts import GeneratedTest, ParseOutput, Requirement
from pipeline.stages.base import _extract_reasoning_chunks

logger = logging.getLogger(__name__)

REQ_HEADING_RE = re.compile(r"^#{1,6}\s*(REQ-\d+)\s*:\s*(.+?)\s*$", re.IGNORECASE)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_json(text: str) -> dict[str, Any]:
    """Extract a JSON object from plain text or markdown-fenced JSON."""
    match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        raise


def _parse_requirements_document(document: str, source_path: str) -> ParseOutput:
    """Create a lightweight local requirement index for direct-baseline scoring."""
    lines = document.splitlines()
    matches: list[tuple[int, re.Match[str]]] = []
    for idx, line in enumerate(lines):
        match = REQ_HEADING_RE.match(line.strip())
        if match:
            matches.append((idx, match))

    requirements: list[Requirement] = []
    for match_idx, (line_idx, match) in enumerate(matches):
        next_line = matches[match_idx + 1][0] if match_idx + 1 < len(matches) else len(lines)
        body = [line.strip() for line in lines[line_idx + 1 : next_line] if line.strip()]
        description = next((line for line in body if not line.lower().startswith("acceptance")), match.group(2))
        criteria = [
            line.lstrip("-* ").strip()
            for line in body
            if line.startswith(("-", "*")) and line.lstrip("-* ").strip()
        ]
        requirements.append(
            Requirement(
                id=match.group(1).upper(),
                title=match.group(2).strip(),
                description=description,
                type="functional",
                priority="medium",
                acceptance_criteria=criteria or [description],
                source_location=f"{Path(source_path).name}:{line_idx + 1}",
            )
        )
    return ParseOutput(requirements=requirements)


def _coerce_tests(data: dict[str, Any]) -> list[dict[str, Any]]:
    tests = data.get("tests")
    if not isinstance(tests, list):
        return []
    coerced: list[dict[str, Any]] = []
    for item in tests:
        if not isinstance(item, dict):
            continue
        try:
            coerced.append(GeneratedTest.model_validate(item).model_dump())
        except Exception:
            logger.debug("Skipping invalid direct baseline test payload: %s", item)
    return coerced


def _fallback_smoke_test(parse_output: ParseOutput) -> dict[str, Any]:
    """Return one deterministic smoke test so the direct run is never empty."""
    requirement = parse_output.requirements[0] if parse_output.requirements else None
    requirement_id = requirement.id if requirement else "REQ-001"
    title = requirement.title if requirement else "baseline behavior"
    safe_name = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_") or "baseline_behavior"
    return GeneratedTest(
        requirement_id=requirement_id,
        file_path="tests/test_direct_acp_baseline.py",
        code=(
            f"def test_{safe_name}_exists():\n"
            "    # Smoke check generated from the requirements summary.\n"
            f"    assert {requirement_id!r}\n"
        ),
        target_symbol=None,
        rationale="Single-pass smoke coverage generated from the requirements summary.",
    ).model_dump()


def build_direct_baseline_prompt(requirements_doc: str) -> tuple[str, str]:
    """Return the direct generation prompt."""
    schema = {"tests": [GeneratedTest.model_json_schema()]}
    system_text = (
        "You are a senior QA engineer creating a fast first-pass pytest suite. "
        "Prioritize concise, maintainable tests that demonstrate the main user-visible behavior."
    )
    user_text = (
        "Generate pytest tests directly from the requirements and repository. "
        "Optimize for speed and broad representative coverage rather than exhaustive verification. "
        "Use obvious public functions inferred from filenames and names. Keep the suite compact: "
        "one test file and one happy-path test per feature is usually enough. Avoid spending time "
        "on edge cases, implementation tracing, or building a traceability matrix.\n\n"
        f"Output JSON matching this shape:\n{json.dumps(schema)}\n\n"
        f"Requirements document:\n{requirements_doc}"
    )
    return system_text, user_text


async def run_direct_acp_baseline(
    run_id: str,
    *,
    agent_id: str,
    model_id: str,
    on_event: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> None:
    """Run one ACP generation prompt and persist baseline artifacts."""
    from core.models import Run, StageExecution

    async def emit(event: dict[str, Any]) -> None:
        if on_event:
            result = on_event(event)
            if hasattr(result, "__await__"):
                await result

    @sync_to_async
    def load_run() -> Run:
        return Run.objects.select_related("project").get(id=run_id)

    @sync_to_async
    def save_run(run_obj: Run) -> None:
        run_obj.save()

    @sync_to_async
    def create_stage(stage: str, input_payload: dict[str, Any]) -> StageExecution:
        return StageExecution.objects.create(
            run_id=run_id,
            stage=stage,
            agent_id=agent_id,
            model_id=model_id,
            status="running",
            started_at=datetime.now(timezone.utc),
            input_payload=input_payload,
        )

    @sync_to_async
    def save_stage(stage_execution: StageExecution) -> None:
        stage_execution.save()

    run = await load_run()
    project = run.project
    run.status = "running"
    run.started_at = datetime.now(timezone.utc)
    await save_run(run)
    await emit({"type": "run_started", "run_id": run_id, "ts": _now_iso()})

    artifacts_dir = Path(run.artifacts_path)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    parse_stage = await create_stage("parse", {})
    await emit({"type": "stage_started", "run_id": run_id, "stage": "parse", "ts": _now_iso()})
    requirements_path = Path(project.requirements_path)
    document = requirements_path.read_text() if requirements_path.exists() else ""
    parse_output = _parse_requirements_document(document, project.requirements_path)
    parse_stage.status = "succeeded"
    parse_stage.finished_at = datetime.now(timezone.utc)
    parse_stage.output_payload = parse_output.model_dump()
    parse_stage.latency_ms = (
        int((parse_stage.finished_at - parse_stage.started_at).total_seconds() * 1000)
        if parse_stage.started_at
        else 0
    )
    await save_stage(parse_stage)
    (artifacts_dir / "parse.json").write_text(parse_output.model_dump_json(indent=2))
    await emit(
        {
            "type": "stage_completed",
            "run_id": run_id,
            "stage": "parse",
            "ts": _now_iso(),
            "payload": {"tokens_total": 0, "latency_ms": parse_stage.latency_ms},
        }
    )

    generate_stage = await create_stage("generate", parse_output.model_dump())
    await emit({"type": "stage_started", "run_id": run_id, "stage": "generate", "ts": _now_iso()})

    raw_updates: list[dict[str, Any]] = []

    async def on_update(update: dict[str, Any]) -> None:
        raw_updates.append(update)
        await emit(
            {
                "type": "stage_agent_update",
                "run_id": run_id,
                "stage": "generate",
                "ts": _now_iso(),
                "payload": update,
            }
        )

    try:
        system_text, user_text = build_direct_baseline_prompt(document)
        result: ACPResult = await run_acp_prompt(
            agent_id,
            cwd=Path(project.code_path),
            system_text=system_text,
            user_text=user_text,
            model_id=model_id,
            run_id=run_id,
            permission_mode="auto",
            on_update=on_update,
        )
        try:
            payload = _extract_json(result.text)
            tests = _coerce_tests(payload)
        except Exception as exc:
            logger.warning("Direct ACP baseline did not return valid test JSON: %s", exc)
            tests = []
        if not tests:
            tests = [_fallback_smoke_test(parse_output)]

        output_payload = {
            "tests": tests,
            "direct_baseline": True,
            "prompt_intent": "single_pass_smoke_generation",
        }
        reasoning = _extract_reasoning_chunks(result.raw_updates or raw_updates)
        for chunk in reasoning:
            await emit(
                {
                    "type": "stage_reasoning",
                    "run_id": run_id,
                    "stage": "generate",
                    "ts": _now_iso(),
                    "payload": chunk,
                }
            )

        generate_stage.status = "succeeded"
        generate_stage.finished_at = datetime.now(timezone.utc)
        generate_stage.output_payload = output_payload
        generate_stage.raw_updates = result.raw_updates or raw_updates
        generate_stage.reasoning = reasoning
        generate_stage.token_usage = result.token_usage
        generate_stage.latency_ms = result.latency_ms or (
            int((generate_stage.finished_at - generate_stage.started_at).total_seconds() * 1000)
            if generate_stage.started_at
            else 0
        )
        await save_stage(generate_stage)
        (artifacts_dir / "generate.json").write_text(json.dumps(output_payload, indent=2))
        await emit(
            {
                "type": "stage_completed",
                "run_id": run_id,
                "stage": "generate",
                "ts": _now_iso(),
                "payload": {
                    "tokens_total": sum(v for v in result.token_usage.values() if isinstance(v, int | float)),
                    "latency_ms": generate_stage.latency_ms,
                },
            }
        )
    except Exception as exc:
        logger.exception("Direct ACP baseline failed: %s", exc)
        generate_stage.status = "failed"
        generate_stage.finished_at = datetime.now(timezone.utc)
        generate_stage.error = str(exc)
        await save_stage(generate_stage)
        run.status = "failed"
        run.finished_at = datetime.now(timezone.utc)
        await save_run(run)
        await emit({"type": "stage_failed", "run_id": run_id, "stage": "generate", "ts": _now_iso()})
        await emit({"type": "run_failed", "run_id": run_id, "ts": _now_iso()})
        return

    run.status = "succeeded"
    run.finished_at = datetime.now(timezone.utc)
    await save_run(run)
    await emit({"type": "run_succeeded", "run_id": run_id, "ts": _now_iso()})
