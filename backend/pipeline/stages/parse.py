"""
Parse stage -- extracts structured requirements from a requirements document.

This is the first stage of the pipeline. It reads the project's requirements
document (e.g., requirements.md), sends it to an AI agent along with the
expected output schema, and parses the agent's response into a list of
structured Requirement objects.

Input: None (this is the first stage; previous_output is ignored)
Output: ParseOutput containing a list of Requirement objects

If the AI agent's response cannot be parsed into valid JSON matching the
schema, the stage falls back to an empty requirements list rather than
failing the entire pipeline. This graceful degradation means subsequent
stages will simply have nothing to work with, but the run won't crash.
"""

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
    """
    Pipeline stage that extracts requirements from a requirements document.

    Reads the requirements file specified in the project configuration, formats
    a prompt using the configured strategy, sends it to the assigned AI agent,
    and parses the structured response.
    """

    name = "parse"

    async def run(
        self,
        ctx: StageContext,
        previous_output: BaseModel | None,
        on_event: Callable[[StageEvent], Awaitable[None]],
    ) -> ParseOutput:
        """
        Execute the parse stage.

        Args:
            ctx: Stage context with project paths, agent config, etc.
            previous_output: Ignored for the parse stage (always None).
            on_event: Callback for emitting progress events.

        Returns:
            ParseOutput with the extracted requirements list.
        """
        # Read the requirements document from disk
        req_path = Path(ctx.requirements_path)
        document = req_path.read_text() if req_path.exists() else ""

        # Get the JSON schema for the expected output (sent to the agent
        # so it knows the exact structure to produce)
        schema = ParseOutput.model_json_schema()
        template = get_prompt_template(ctx.prompt_strategy, self.name)

        # Format the user prompt with the schema and document content.
        # Empty strings are passed for example fields that may be used
        # by few-shot strategies but are not populated here.
        user_text = template.format(
            schema=schema,
            document=document,
            examples="",
            dynamic_examples="",
        )

        # System prompt defines the agent's role and expected response format
        system_text = (
            "You are a requirements extraction agent. "
            "Parse the document and output structured requirements. "
            "Reply with JSON inside ```json fences."
        )

        # Call the AI agent via ACP
        result: ACPResult = await run_acp_prompt(
            ctx.agent_id,
            cwd=Path(ctx.code_path),
            system_text=system_text,
            user_text=user_text,
            model_id=ctx.model_id,
            on_update=lambda update: on_event(
                StageEvent(type="agent_update", run_id=ctx.run_id, stage=self.name, payload=update)
            ),
        )

        # Attempt to parse the agent's response into our structured format
        try:
            data = self.extract_json(result.text)
            output = ParseOutput.model_validate(data)
        except Exception as e:
            # Graceful fallback: return empty requirements rather than crashing
            logger.warning("Parse stage: first parse attempt failed: %s", e)
            output = ParseOutput(requirements=[], raw_token_usage=result.token_usage)

        # Track token usage for cost monitoring, then save artifacts to disk
        output.raw_token_usage = result.token_usage
        self.save_output(ctx, output)
        return output
