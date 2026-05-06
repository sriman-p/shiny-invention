import logging
from pathlib import Path
from typing import Awaitable, Callable

from pydantic import BaseModel

from acp_client.runner import ACPResult, run_acp_prompt
from pipeline.contracts import (
    AnalyzeOutput,
    GenerateOutput,
    MapOutput,
    ParseOutput,
)
from pipeline.prompts import get_prompt_template

from .base import Stage, StageContext, StageEvent

logger = logging.getLogger(__name__)


class GenerateStage(Stage):
    name = "generate"

    async def run(
        self,
        ctx: StageContext,
        previous_output: BaseModel | None,
        on_event: Callable[[StageEvent], Awaitable[None]],
    ) -> GenerateOutput:
        map_output = (
            previous_output
            if isinstance(previous_output, MapOutput)
            else MapOutput(
                analyze=AnalyzeOutput(
                    parse=ParseOutput(requirements=[]),
                    symbols=[],
                    project_summary="",
                ),
                mappings=[],
            )
        )

        schema = GenerateOutput.model_json_schema()
        template = get_prompt_template(ctx.prompt_strategy, self.name)

        mappings_text = "\n".join(
            f"- {m.requirement_id} -> {m.symbol.qualified_name if m.symbol else 'unmapped'} "
            f"(confidence: {m.confidence})"
            for m in map_output.mappings
        )

        user_text = template.format(
            schema=schema,
            few_shot_examples="(no examples available)",
            mappings=mappings_text,
            examples="",
            dynamic_examples="",
        )

        system_text = (
            "You are a test generation agent. For each requirement mapping, generate "
            "pytest test files. Reply with JSON inside ```json fences."
        )

        result: ACPResult = await run_acp_prompt(
            ctx.agent_id,
            cwd=Path(ctx.code_path),
            system_text=system_text,
            user_text=user_text,
        )

        try:
            data = self.extract_json(result.text)
            if "map" not in data:
                data["map"] = map_output.model_dump()
            output = GenerateOutput.model_validate(data)
        except Exception as e:
            logger.warning("Generate stage: parse failed: %s", e)
            output = GenerateOutput(map=map_output, tests=[])

        self.save_output(ctx, output)
        return output
