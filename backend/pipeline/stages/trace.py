"""
Trace stage -- builds the final traceability matrix and coverage gap report.

This is the sixth and final stage of the pipeline. It takes all the data
accumulated from previous stages (requirements, code symbols, tests, critique
scores) and produces:
  1. A traceability matrix: maps each requirement to its test files and
     indicates whether it is "covered", "partial", or "uncovered"
  2. A Markdown gap report: human-readable summary of coverage gaps that
     need attention

Input: CritiqueOutput from the critique stage (tests + quality scores)
Output: TraceOutput containing the traceability matrix and gap report

This is the primary deliverable of the entire pipeline. The traceability matrix
is what stakeholders use to verify that every requirement has adequate test
coverage, and the gap report highlights areas that need more testing.
"""

import logging
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
    TraceOutput,
)
from pipeline.prompts import get_prompt_template

from .base import Stage, StageContext, StageEvent

logger = logging.getLogger(__name__)


class TraceStage(Stage):
    """
    Pipeline stage that builds the traceability matrix and gap report.

    Takes the full chain of previous outputs (accessed through CritiqueOutput's
    nested structure) and asks the AI agent to map requirements to test coverage.
    """

    name = "trace"

    async def run(
        self,
        ctx: StageContext,
        previous_output: BaseModel | None,
        on_event: Callable[[StageEvent], Awaitable[None]],
    ) -> TraceOutput:
        """
        Execute the trace stage.

        Args:
            ctx: Stage context with project paths, agent config, etc.
            previous_output: Expected to be a CritiqueOutput from the critique stage.
            on_event: Callback for emitting progress events.

        Returns:
            TraceOutput with the traceability matrix and Markdown gap report.
        """
        # Accept the critique output, or create an empty fallback with the full
        # nested chain of all previous stage outputs
        critique_output = (
            previous_output
            if isinstance(previous_output, CritiqueOutput)
            else CritiqueOutput(
                generate=GenerateOutput(
                    map=MapOutput(
                        analyze=AnalyzeOutput(
                            parse=ParseOutput(requirements=[]),
                            symbols=[],
                            project_summary="",
                        ),
                        mappings=[],
                    ),
                    tests=[],
                ),
                scores=[],
                revised_tests=[],
            )
        )

        schema = TraceOutput.model_json_schema()
        template = get_prompt_template(ctx.prompt_strategy, self.name)

        # Navigate through the nested output chain to access requirements and tests.
        # The chain is: critique -> generate -> map -> analyze -> parse -> requirements
        requirements_text = "\n".join(
            f"- {r.id}: {r.title}" for r in critique_output.generate.map.analyze.parse.requirements
        )
        tests_text = "\n".join(f"- {t.file_path}: {t.requirement_id}" for t in critique_output.generate.tests)

        user_text = template.format(
            schema=schema,
            requirements=requirements_text,
            tests=tests_text,
            examples="",
            dynamic_examples="",
        )

        system_text = (
            "You are a traceability agent. Build a matrix mapping requirements to tests. "
            "Reply with JSON inside ```json fences."
        )

        result: ACPResult = await run_acp_prompt(
            ctx.agent_id,
            cwd=Path(ctx.code_path),
            system_text=system_text,
            user_text=user_text,
            model_id=ctx.model_id,
        )

        try:
            data = self.extract_json(result.text)
            # Inject the critique output if the agent didn't include it
            if "critique" not in data:
                data["critique"] = critique_output.model_dump()
            output = TraceOutput.model_validate(data)
        except Exception as e:
            logger.warning("Trace stage: parse failed: %s", e)
            output = TraceOutput(
                critique=critique_output,
                matrix=[],
                gap_report_md="Trace stage failed to produce a gap report.",
            )

        self.save_output(ctx, output)
        return output
