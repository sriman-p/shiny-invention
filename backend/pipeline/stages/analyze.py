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
    name = "analyze"

    async def run(
        self,
        ctx: StageContext,
        previous_output: BaseModel | None,
        on_event: Callable[[StageEvent], Awaitable[None]],
    ) -> AnalyzeOutput:
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
            if "parse" not in data:
                data["parse"] = parse_output.model_dump()
            output = AnalyzeOutput.model_validate(data)
        except Exception as e:
            logger.warning("Analyze stage: parse failed: %s", e)
            output = AnalyzeOutput(parse=parse_output, symbols=[], project_summary="Analysis failed.")

        self.save_output(ctx, output)
        return output
