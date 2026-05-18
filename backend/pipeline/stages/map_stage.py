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

import asyncio
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable

from pydantic import BaseModel

from acp_client.runner import ACPResult, run_acp_prompt
from pipeline.contracts import AnalyzeOutput, MapOutput, ParseOutput
from pipeline.few_shot_examples import get_static_examples
from pipeline.prompts import get_prompt_template
from pipeline.retrieval import Retriever

from .base import Stage, StageContext, StageEvent

logger = logging.getLogger(__name__)

# Number of retrieval hits to include per requirement.
DEFAULT_TOP_K = 5

# Context modes that should include retrieval hints. "minimal" intentionally
# skips retrieval to provide a true baseline that costs less.
RETRIEVAL_CONTEXT_MODES = {"local", "module", "full"}


def _get_or_build_retriever(ctx: StageContext) -> Retriever | None:
    """
    Lazily build a Retriever, caching it on `ctx.retrieval_index` so subsequent
    stages in the same run reuse the FAISS/BM25 index instead of rebuilding.
    """
    cache = ctx.retrieval_index if isinstance(ctx.retrieval_index, dict) else None
    if cache is not None and "retriever" in cache:
        return cache["retriever"]

    retriever = Retriever()
    try:
        retriever.build_index(ctx.code_path)
    except Exception as exc:
        logger.warning("Map stage: retriever build failed: %s", exc)
        return None
    if not retriever.documents:
        return None
    if cache is not None:
        cache["retriever"] = retriever
    return retriever


def _format_retrieval_hints(retriever: Retriever, requirements: list[Any]) -> str:
    """Render top-k snippets per requirement as a compact bulleted block."""
    lines: list[str] = []
    seen: set[str] = set()
    for req in requirements:
        try:
            query = f"{req.title}\n{req.description}"
        except AttributeError:
            continue
        for hit in retriever.search(query, k=DEFAULT_TOP_K, filter="code"):
            key = f"{req.id}:{hit.source}"
            if key in seen:
                continue
            seen.add(key)
            snippet = " ".join(hit.text.split())[:240]
            lines.append(f"- [{req.id}] {hit.source} (score={hit.score:.2f}): {snippet}")
    if not lines:
        return "(retrieval index built but no relevant snippets found)"
    return "\n".join(lines)


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
        examples = get_static_examples(ctx.project_name, self.name, ctx.prompt_strategy)

        # Format requirements and symbols as readable lists for the prompt
        requirements_text = "\n".join(f"- {r.id}: {r.title}" for r in analyze_output.parse.requirements)
        symbols_text = "\n".join(f"- {s.qualified_name} ({s.kind}) in {s.file_path}" for s in analyze_output.symbols)

        # Retrieval hints: built lazily, cached on ctx, gated by context_mode.
        retrieval_hints = "(no retrieval hints available)"
        if ctx.context_mode in RETRIEVAL_CONTEXT_MODES and analyze_output.parse.requirements:
            # Building the FAISS index can be expensive; do it in a worker thread
            # so we don't block the event loop.
            retriever = await asyncio.to_thread(_get_or_build_retriever, ctx)
            if retriever is not None:
                retrieval_hints = await asyncio.to_thread(
                    _format_retrieval_hints, retriever, analyze_output.parse.requirements
                )

        user_text = template.format(
            schema=schema,
            retrieval_hints=retrieval_hints,
            requirements=requirements_text,
            symbols=symbols_text,
            examples=examples,
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
            run_id=ctx.run_id,
            permission_mode=ctx.permission_mode,
            on_permission_request=ctx.on_permission_request,
            on_update=lambda update: on_event(
                StageEvent(type="agent_update", run_id=ctx.run_id, stage=self.name, payload=update)
            ),
        )

        await self.emit_acp_events(ctx, on_event, result)

        try:
            data = self.extract_json(result.text)
            data = self.select_output_fields(data, "mappings")
            # Preserve real pipeline provenance even if the agent echoes or
            # invents nested analyze/parse data in its response.
            data["analyze"] = analyze_output.model_dump()
            output = MapOutput.model_validate(data)
        except Exception as e:
            logger.warning("Map stage: parse failed: %s", e)
            output = MapOutput(analyze=analyze_output, mappings=[])

        self.save_output(ctx, output)
        return output
