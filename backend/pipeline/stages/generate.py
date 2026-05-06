"""
Generate stage -- creates test code for each requirement-to-code mapping.

This is the fourth stage of the pipeline. For each mapping produced by the
map stage, it asks an AI agent to generate pytest test files that verify the
requirement is correctly implemented by the mapped code symbol.

Input: MapOutput from the map stage (requirement-to-code mappings)
Output: GenerateOutput containing generated test files

The generated tests are not written to disk at this point -- they are stored
as structured data in the output. The critique stage will evaluate them first,
and only after critique would they potentially be written to the project.
"""

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
    """
    Pipeline stage that generates test code for requirement-to-code mappings.

    Takes the mappings from the map stage and asks the AI agent to produce
    pytest test files for each one. The prompt includes the mapping details
    and any available style reference examples from the project.
    """

    name = "generate"

    async def run(
        self,
        ctx: StageContext,
        previous_output: BaseModel | None,
        on_event: Callable[[StageEvent], Awaitable[None]],
    ) -> GenerateOutput:
        """
        Execute the generate stage.

        Args:
            ctx: Stage context with project paths, agent config, etc.
            previous_output: Expected to be a MapOutput from the map stage.
            on_event: Callback for emitting progress events.

        Returns:
            GenerateOutput with generated test files.
        """
        # Accept the map output from the previous stage, or create an empty fallback
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

        # Format the mappings as a readable list showing requirement -> symbol
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
            model_id=ctx.model_id,
        )

        try:
            data = self.extract_json(result.text)
            # Inject the map output if the agent didn't include it
            if "map" not in data:
                data["map"] = map_output.model_dump()
            output = GenerateOutput.model_validate(data)
        except Exception as e:
            logger.warning("Generate stage: parse failed: %s", e)
            output = GenerateOutput(map=map_output, tests=[])

        self.save_output(ctx, output)
        return output
