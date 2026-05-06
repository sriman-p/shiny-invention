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
)
from pipeline.prompts import get_prompt_template

from .base import Stage, StageContext, StageEvent

logger = logging.getLogger(__name__)


class CritiqueStage(Stage):
    name = "critique"

    async def run(
        self,
        ctx: StageContext,
        previous_output: BaseModel | None,
        on_event: Callable[[StageEvent], Awaitable[None]],
    ) -> CritiqueOutput:
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

        tests_text = "\n".join(
            f"- {t.file_path}: {t.requirement_id} ({len(t.code)} chars)"
            for t in generate_output.tests
        )

        user_text = template.format(
            schema=schema,
            tests=tests_text,
            examples="",
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
        )

        try:
            data = self.extract_json(result.text)
            if "generate" not in data:
                data["generate"] = generate_output.model_dump()
            output = CritiqueOutput.model_validate(data)
        except Exception as e:
            logger.warning("Critique stage: parse failed: %s", e)
            output = CritiqueOutput(generate=generate_output, scores=[], revised_tests=[])

        self.save_output(ctx, output)
        return output
