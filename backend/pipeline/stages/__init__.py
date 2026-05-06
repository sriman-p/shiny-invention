from .analyze import AnalyzeStage
from .base import Stage
from .base import StageContext as StageContext
from .base import StageEvent as StageEvent
from .critique import CritiqueStage
from .generate import GenerateStage
from .map_stage import MapStage
from .parse import ParseStage
from .trace import TraceStage

STAGE_ORDER = ["parse", "analyze", "map", "generate", "critique", "trace"]

STAGE_CLASSES: dict[str, type[Stage]] = {
    "parse": ParseStage,
    "analyze": AnalyzeStage,
    "map": MapStage,
    "generate": GenerateStage,
    "critique": CritiqueStage,
    "trace": TraceStage,
}
