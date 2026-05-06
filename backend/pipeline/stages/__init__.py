"""
Pipeline stage registry -- imports all concrete stages and defines execution order.

This package contains the six pipeline stages that make up the ReqLens analysis
pipeline. Each stage is a separate module with a class inheriting from Stage ABC.

STAGE_ORDER defines the sequence in which stages execute. The orchestrator
iterates through this list, passing each stage's output to the next.

STAGE_CLASSES maps stage names to their implementing classes, allowing the
orchestrator to instantiate stages by name from the database configuration.

Re-exports StageContext and StageEvent so other modules can import them
from this package without reaching into the base module directly.
"""

from .analyze import AnalyzeStage
from .base import Stage
from .base import StageContext as StageContext
from .base import StageEvent as StageEvent
from .critique import CritiqueStage
from .generate import GenerateStage
from .map_stage import MapStage
from .parse import ParseStage
from .trace import TraceStage

# The canonical execution order of pipeline stages.
# Changing this order would break the pipeline because each stage depends
# on the output of the previous one.
STAGE_ORDER = ["parse", "analyze", "map", "generate", "critique", "trace"]

# Maps stage name strings to their implementing classes. Used by the
# orchestrator to instantiate the correct stage class for each step.
STAGE_CLASSES: dict[str, type[Stage]] = {
    "parse": ParseStage,
    "analyze": AnalyzeStage,
    "map": MapStage,
    "generate": GenerateStage,
    "critique": CritiqueStage,
    "trace": TraceStage,
}
