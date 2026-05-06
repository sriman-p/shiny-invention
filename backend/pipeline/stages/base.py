"""
Abstract base class and shared data structures for pipeline stages.

All pipeline stages inherit from the Stage ABC defined here. This module
provides the common interface and utility methods that every stage uses:
  - StageContext: carries all configuration needed to execute a stage
  - StageEvent: structure for emitting progress events during execution
  - Stage (ABC): defines the run() method that each stage must implement,
    plus helper methods for JSON extraction and output persistence

The extract_json() method is particularly important because AI agents
return their responses in various formats (pure JSON, JSON in markdown
fences, JSON embedded in prose). This method tries multiple strategies
to reliably extract valid JSON from the response text.
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from pydantic import BaseModel

logger = logging.getLogger(__name__)


@dataclass
class StageContext:
    """
    Configuration and context passed to each pipeline stage.

    Carries everything a stage needs to execute: project identifiers,
    agent configuration, file paths, and the artifacts directory where
    stage outputs are saved.

    Attributes:
        project_id: UUID string of the project being analyzed.
        project_name: Human-readable project name (for logging/display).
        run_id: UUID string of the current pipeline run.
        agent_id: Which AI agent to invoke for this stage.
        prompt_strategy: How to structure the prompt (e.g., "zero_shot").
        context_mode: How much code context to include (e.g., "full").
        code_path: Filesystem path to the project's source code.
        requirements_path: Filesystem path to the requirements document.
        artifacts_dir: Directory where stage output JSON files are saved.
        retrieval_index: Optional pre-built retrieval index for code search.
    """

    project_id: str
    project_name: str
    run_id: str
    agent_id: str
    prompt_strategy: str
    context_mode: str
    code_path: str
    requirements_path: str
    artifacts_dir: str
    retrieval_index: Any = None


@dataclass
class StageEvent:
    """
    Progress event emitted during stage execution.

    Stages can emit events to provide real-time feedback (e.g., "processing
    requirement 3 of 10"). These events are forwarded through the orchestrator
    to the SSE stream.

    Attributes:
        type: Event type string (e.g., "progress", "warning").
        run_id: UUID string of the current pipeline run.
        stage: Name of the emitting stage.
        payload: Arbitrary data associated with the event.
        timestamp: ISO 8601 timestamp string.
    """

    type: str
    run_id: str
    stage: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""


class Stage(ABC):
    """
    Abstract base class for all pipeline stages.

    Each concrete stage (ParseStage, AnalyzeStage, etc.) must implement the
    run() method. The base class provides:
      - extract_json(): robust JSON extraction from agent response text
      - save_output(): persist stage output to the artifacts directory
    """

    name: str = ""

    @abstractmethod
    async def run(
        self,
        ctx: StageContext,
        previous_output: BaseModel | None,
        on_event: Callable[[StageEvent], Awaitable[None]],
    ) -> BaseModel: ...

    def extract_json(self, text: str) -> dict[str, Any]:
        """
        Extract a JSON object from agent response text.

        AI agents may return JSON in various formats. This method tries
        three strategies in order:
          1. Look for JSON inside markdown code fences (```json ... ```)
          2. Try parsing the entire text as JSON
          3. Find the outermost { ... } braces and parse that substring

        Args:
            text: The raw response text from the AI agent.

        Returns:
            The parsed JSON as a Python dict.

        Raises:
            json.JSONDecodeError: If no valid JSON can be extracted.
        """
        # Strategy 1: Extract JSON from markdown code fences
        pattern = r"```(?:json)?\s*\n(.*?)\n```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        # Strategy 2: Try parsing the entire response as JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Strategy 3: Find the outermost curly braces and parse that substring
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            raise

    def save_output(self, ctx: StageContext, output: BaseModel) -> None:
        """
        Persist the stage's structured output to a JSON file in the artifacts directory.

        The file is named after the stage (e.g., parse.json, analyze.json) and
        contains the pretty-printed JSON representation of the output model.

        Args:
            ctx: The stage context containing the artifacts directory path.
            output: The Pydantic model to serialize and save.
        """
        output_dir = Path(ctx.artifacts_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{self.name}.json"
        output_path.write_text(output.model_dump_json(indent=2))
