"""
Critique stage -- evaluates and optionally revises generated tests.

This is the fifth stage of the pipeline. It sends the generated tests to an
AI agent for quality review. Each test is scored on three dimensions
(relevance, completeness, correctness) on a 1-5 scale, and receives a
decision: accept, revise, or reject.

Input: GenerateOutput from the generate stage (generated test files)
Output: CritiqueOutput containing scores for each test and optionally
    revised versions of tests that the agent decided to improve

The critique stage acts as a quality gate -- it prevents low-quality tests
from being included in the final traceability matrix. Tests marked as
"reject" are dropped, "accept" tests pass through, and "revise" tests
get improved versions from the agent.
"""

import logging
import re
from pathlib import Path
from typing import Awaitable, Callable

from pydantic import BaseModel

from acp_client.runner import ACPResult, run_acp_prompt
from pipeline.contracts import (
    AnalyzeOutput,
    CritiqueOutput,
    GenerateOutput,
    MapOutput,
    ParseOutput,
)
from pipeline.few_shot_examples import get_static_examples
from pipeline.prompts import get_prompt_template

from .base import Stage, StageContext, StageEvent

logger = logging.getLogger(__name__)


def _canonical_test_path(path: str) -> str:
    """Return a loose path key for matching generated tests to critique scores."""
    return re.sub(r"[^a-z0-9]+", "", path.lower())


def _reconcile_score_test_files(data: dict, generate_output: GenerateOutput) -> None:
    """Rewrite score paths to the exact generated file paths when they clearly match."""
    generated_files = {test.file_path for test in generate_output.tests}
    generated_by_key = {_canonical_test_path(test.file_path): test.file_path for test in generate_output.tests}
    for score in data.get("scores") or []:
        if not isinstance(score, dict):
            continue
        test_file = score.get("test_file")
        if not isinstance(test_file, str) or test_file in generated_files:
            continue
        generated_file = generated_by_key.get(_canonical_test_path(test_file))
        if generated_file:
            score["test_file"] = generated_file


class CritiqueStage(Stage):
    """
    Pipeline stage that evaluates and scores generated test files.

    Sends all generated tests to the AI agent along with scoring criteria,
    and receives quality scores and optional revised test code.
    """

    name = "critique"

    async def run(
        self,
        ctx: StageContext,
        previous_output: BaseModel | None,
        on_event: Callable[[StageEvent], Awaitable[None]],
    ) -> CritiqueOutput:
        """
        Execute the critique stage.

        Args:
            ctx: Stage context with project paths, agent config, etc.
            previous_output: Expected to be a GenerateOutput from the generate stage.
            on_event: Callback for emitting progress events.

        Returns:
            CritiqueOutput with quality scores and optional revised tests.
        """
        # Accept the generate output, or create an empty fallback with the full
        # nested chain of previous outputs
        generate_output = (
            previous_output
            if isinstance(previous_output, GenerateOutput)
            else GenerateOutput(
                map=MapOutput(
                    analyze=AnalyzeOutput(
                        parse=ParseOutput(requirements=[]),
                        symbols=[],
                        project_summary="",
                    ),
                    mappings=[],
                ),
                tests=[],
            )
        )

        schema = CritiqueOutput.model_json_schema()
        template = get_prompt_template(ctx.prompt_strategy, self.name)
        examples = get_static_examples(ctx.project_name, self.name, ctx.prompt_strategy)

        # Summarize each test for the critique prompt (file path, requirement, code length)
        tests_text = "\n".join(
            f"- {t.file_path}: {t.requirement_id} ({len(t.code)} chars)" for t in generate_output.tests
        )

        user_text = template.format(
            schema=schema,
            tests=tests_text,
            examples=examples,
            dynamic_examples="",
        )

        system_text = (
            "You are a test critique agent. Score each test on relevance, completeness, "
            "and correctness (1-5). Reply with JSON inside ```json fences."
        )

        result: ACPResult = await run_acp_prompt(
            ctx.agent_id,
            cwd=Path(ctx.code_path),
            system_text=system_text,
            user_text=user_text,
            model_id=ctx.model_id,
            run_id=ctx.run_id,
            permission_mode=ctx.permission_mode,
            on_permission_request=ctx.on_permission_request,
            on_update=lambda update: on_event(
                StageEvent(type="agent_update", run_id=ctx.run_id, stage=self.name, payload=update)
            ),
        )

        await self.emit_acp_events(ctx, on_event, result)

        try:
            data = self.extract_json(result.text)
            data = self.select_output_fields(data, "scores", "revised_tests")
            _reconcile_score_test_files(data, generate_output)
            # Preserve real pipeline provenance even if the agent echoes or
            # invents nested generated tests/mappings in its response.
            data["generate"] = generate_output.model_dump()
            output = CritiqueOutput.model_validate(data)
        except Exception as e:
            logger.warning("Critique stage: parse failed: %s", e)
            output = CritiqueOutput(generate=generate_output, scores=[], revised_tests=[])

        self.save_output(ctx, output)
        return output
