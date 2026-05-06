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
    type: str
    run_id: str
    stage: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""


class Stage(ABC):
    name: str = ""

    @abstractmethod
    async def run(
        self,
        ctx: StageContext,
        previous_output: BaseModel | None,
        on_event: Callable[[StageEvent], Awaitable[None]],
    ) -> BaseModel: ...

    def extract_json(self, text: str) -> dict[str, Any]:
        pattern = r"```(?:json)?\s*\n(.*?)\n```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            raise

    def save_output(self, ctx: StageContext, output: BaseModel) -> None:
        output_dir = Path(ctx.artifacts_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{self.name}.json"
        output_path.write_text(output.model_dump_json(indent=2))
