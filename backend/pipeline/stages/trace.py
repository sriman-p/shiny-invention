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
    name = "trace"

    async def run(
        self,
        ctx: StageContext,
        previous_output: BaseModel | None,
        on_event: Callable[[StageEvent], Awaitable[None]],
    ) -> TraceOutput:
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

        requirements_text = "\n".join(
            f"- {r.id}: {r.title}"
            for r in critique_output.generate.map.analyze.parse.requirements
        )
        tests_text = "\n".join(
            f"- {t.file_path}: {t.requirement_id}"
            for t in critique_output.generate.tests
        )

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
        )

        try:
            data = self.extract_json(result.text)
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
