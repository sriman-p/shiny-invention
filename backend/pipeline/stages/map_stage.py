"""
Map stage -- links requirements to implementing code symbols.

This is the third stage of the pipeline. For each requirement extracted in the
parse stage, it asks an AI agent to identify which code symbol(s) from the
analyze stage's inventory implement that requirement.

Input: AnalyzeOutput from the analyze stage (requirements + code symbols)
Output: MapOutput containing requirement-to-code mappings with confidence scores

This is often the most critical stage because it determines the accuracy of
the entire traceability matrix. The prompt includes retrieval hints (when
available) to help the agent narrow down candidates from a potentially large
symbol inventory.

Note: The module is named map_stage.py (not map.py) to avoid shadowing
Python's built-in map() function.
"""

import logging
from pathlib import Path
from typing import Awaitable, Callable

from pydantic import BaseModel

from acp_client.runner import ACPResult, run_acp_prompt
from pipeline.contracts import AnalyzeOutput, MapOutput, ParseOutput
from pipeline.prompts import get_prompt_template

from .base import Stage, StageContext, StageEvent

logger = logging.getLogger(__name__)


class MapStage(Stage):
    """
    Pipeline stage that maps requirements to their implementing code symbols.

    Formats the requirements and symbols into a prompt, optionally includes
    retrieval hints from the FAISS+BM25 index, and asks the AI agent to
    produce a mapping with confidence scores and rationale.
    """

    name = "map"

    async def run(
        self,
        ctx: StageContext,
        previous_output: BaseModel | None,
        on_event: Callable[[StageEvent], Awaitable[None]],
    ) -> MapOutput:
        """
        Execute the map stage.

        Args:
            ctx: Stage context with project paths, agent config, etc.
            previous_output: Expected to be an AnalyzeOutput from the analyze stage.
            on_event: Callback for emitting progress events.

        Returns:
            MapOutput with requirement-to-symbol mappings.
        """
        # Accept the analyze output from the previous stage, or create an empty fallback
        analyze_output = (
            previous_output
            if isinstance(previous_output, AnalyzeOutput)
            else AnalyzeOutput(
                parse=ParseOutput(requirements=[]),
                symbols=[],
                project_summary="",
            )
        )

        schema = MapOutput.model_json_schema()
        template = get_prompt_template(ctx.prompt_strategy, self.name)

        # Format requirements and symbols as readable lists for the prompt
        requirements_text = "\n".join(f"- {r.id}: {r.title}" for r in analyze_output.parse.requirements)
        symbols_text = "\n".join(f"- {s.qualified_name} ({s.kind}) in {s.file_path}" for s in analyze_output.symbols)

        user_text = template.format(
            schema=schema,
            retrieval_hints="(no retrieval hints available)",
            requirements=requirements_text,
            symbols=symbols_text,
            examples="",
            dynamic_examples="",
        )

        system_text = (
            "You are a requirement-to-code mapping agent. For each requirement, "
            "identify implementing code symbols. Reply with JSON inside ```json fences."
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
            # Inject the analyze output if the agent didn't include it
            if "analyze" not in data:
                data["analyze"] = analyze_output.model_dump()
            output = MapOutput.model_validate(data)
        except Exception as e:
            logger.warning("Map stage: parse failed: %s", e)
            output = MapOutput(analyze=analyze_output, mappings=[])

        self.save_output(ctx, output)
        return output
