import logging
from pathlib import Path
from typing import Awaitable, Callable

from pydantic import BaseModel

from acp_client.runner import ACPResult, run_acp_prompt
from pipeline.contracts import ParseOutput
from pipeline.prompts import get_prompt_template

from .base import Stage, StageContext, StageEvent

logger = logging.getLogger(__name__)


class ParseStage(Stage):
    name = "parse"

    async def run(
        self,
        ctx: StageContext,
        previous_output: BaseModel | None,
        on_event: Callable[[StageEvent], Awaitable[None]],
    ) -> ParseOutput:
        req_path = Path(ctx.requirements_path)
        document = req_path.read_text() if req_path.exists() else ""

        schema = ParseOutput.model_json_schema()
        template = get_prompt_template(ctx.prompt_strategy, self.name)

        user_text = template.format(
            schema=schema,
            document=document,
            examples="",
            dynamic_examples="",
        )

        system_text = (
            "You are a requirements extraction agent. "
            "Parse the document and output structured requirements. "
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
            output = ParseOutput.model_validate(data)
        except Exception as e:
            logger.warning("Parse stage: first parse attempt failed: %s", e)
            output = ParseOutput(requirements=[], raw_token_usage=result.token_usage)

        output.raw_token_usage = result.token_usage
        self.save_output(ctx, output)
        return output
