"""
Analyze stage -- inventories code symbols in the project's codebase.

This is the second stage of the pipeline. It directs an AI agent to walk the
project's source code directory and produce a structured inventory of all
functions, classes, and methods, along with a one-paragraph project summary.

Input: ParseOutput from the parse stage (requirements list)
Output: AnalyzeOutput containing the parse output, discovered code symbols,
    and a project summary

The analyze output combines the requirements from the parse stage with the
code symbols discovered here, forming the complete "two sides" that the
map stage will link together.
"""

import logging
from pathlib import Path
from typing import Awaitable, Callable

from pydantic import BaseModel

from acp_client.runner import ACPResult, run_acp_prompt
from pipeline.contracts import AnalyzeOutput, ParseOutput
from pipeline.prompts import get_prompt_template

from .base import Stage, StageContext, StageEvent

logger = logging.getLogger(__name__)


class AnalyzeStage(Stage):
    """
    Pipeline stage that discovers code symbols in the project's source tree.

    Sends the AI agent to walk the codebase directory, identify all functions,
    classes, and methods, and return them as structured CodeSymbol objects.
    """

    name = "analyze"

    async def run(
        self,
        ctx: StageContext,
        previous_output: BaseModel | None,
        on_event: Callable[[StageEvent], Awaitable[None]],
    ) -> AnalyzeOutput:
        """
        Execute the analyze stage.

        Args:
            ctx: Stage context with project paths, agent config, etc.
            previous_output: Expected to be a ParseOutput from the parse stage.
            on_event: Callback for emitting progress events.

        Returns:
            AnalyzeOutput with the symbol inventory and project summary.
        """
        # Accept the parse output from the previous stage, or create an empty fallback
        parse_output = previous_output if isinstance(previous_output, ParseOutput) else ParseOutput(requirements=[])

        schema = AnalyzeOutput.model_json_schema()
        template = get_prompt_template(ctx.prompt_strategy, self.name)

        user_text = template.format(
            schema=schema,
            code_path=ctx.code_path,
            examples="",
            dynamic_examples="",
        )

        system_text = (
            "You are a code analysis agent. Walk the codebase directory and identify all "
            "functions, classes, and methods. Return a symbol inventory and project summary. "
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
            # The agent may not include the parse output in its response,
            # so we inject it if missing to maintain the output chain
            if "parse" not in data:
                data["parse"] = parse_output.model_dump()
            output = AnalyzeOutput.model_validate(data)
        except Exception as e:
            logger.warning("Analyze stage: parse failed: %s", e)
            output = AnalyzeOutput(parse=parse_output, symbols=[], project_summary="Analysis failed.")

        self.save_output(ctx, output)
        return output
