"""
Pydantic data contracts for the ReqLens pipeline stages.

These models define the exact shape of data flowing between pipeline stages.
Each stage produces a typed output that the next stage consumes. The contracts
enforce strict validation (no extra fields, correct types) so that any schema
mismatch is caught immediately rather than causing subtle downstream errors.

Data flow through the pipeline:
  ParseOutput -> AnalyzeOutput -> MapOutput -> GenerateOutput -> CritiqueOutput -> TraceOutput

Each output model nests the previous stage's output, creating a chain of provenance.
For example, TraceOutput contains CritiqueOutput, which contains GenerateOutput, etc.
This design means any stage can access all previous stages' data without separate lookups.

All models use Pydantic's strict mode and extra="forbid" to ensure the AI agents
produce exactly the expected JSON structure. If an agent returns unexpected fields,
validation will fail and the stage will fall back to a safe empty output.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Requirement(BaseModel):
    """
    A single requirement extracted from a requirements document.

    Represents a functional or non-functional requirement with metadata about
    its priority, acceptance criteria, and where it was found in the source document.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str = Field(min_length=1)  # Unique identifier (e.g., "REQ-001")
    title: str = Field(min_length=1)  # Short descriptive title
    description: str = Field(min_length=1)  # Full requirement text
    type: Literal["functional", "non_functional"]  # Whether it describes behavior or a quality attribute
    priority: Literal["high", "medium", "low"]  # Business priority
    acceptance_criteria: list[str] = Field(min_length=1)  # Concrete conditions that must be met
    source_location: str = Field(min_length=1)  # Where in the document this was found


class CodeSymbol(BaseModel):
    """
    A code symbol (function, class, or method) discovered during code analysis.

    Captures the symbol's fully qualified name, location in the source tree,
    its signature, and optional docstring. Used by the map stage to link
    requirements to implementing code.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    qualified_name: str = Field(min_length=1)  # Fully qualified path (e.g., "src.calc.Calculator.add")
    kind: Literal["function", "class", "method"]  # Type of symbol
    file_path: str = Field(min_length=1)  # Relative path to the source file
    line_start: int = Field(ge=1)  # Starting line number in the file
    line_end: int = Field(ge=1)  # Ending line number in the file
    signature: str = Field(min_length=1)  # Function/method signature string
    docstring: str | None = None  # Docstring if present, None otherwise


class ParseOutput(BaseModel):
    """
    Output of the Parse stage: a list of extracted requirements.

    This is the first stage's output and serves as the foundation for all
    subsequent stages. If parsing fails, an empty requirements list is used
    as a safe fallback.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    requirements: list[Requirement]  # All requirements extracted from the document
    raw_token_usage: dict = Field(default_factory=dict)  # Token usage from the agent call


class AnalyzeOutput(BaseModel):
    """
    Output of the Analyze stage: code symbol inventory plus project summary.

    Combines the previous parse output with a list of discovered code symbols
    and a high-level project summary. The symbols list is the "code side" that
    will be matched against requirements in the map stage.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    parse: ParseOutput  # Nested output from the previous stage
    symbols: list[CodeSymbol]  # All discovered functions, classes, and methods
    project_summary: str = Field(min_length=1)  # One-paragraph description of the project


class Mapping(BaseModel):
    """
    A single requirement-to-code mapping produced by the Map stage.

    Links a requirement to the code symbol that implements it, with a confidence
    score and rationale explaining why the agent believes this mapping is correct.
    Evidence snippets are optional code excerpts supporting the mapping.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    requirement_id: str = Field(min_length=1)  # ID of the requirement being mapped
    symbol: CodeSymbol | None = None  # The implementing code symbol (None if no match found)
    confidence: float = Field(ge=0.0, le=1.0)  # Agent's confidence in this mapping
    rationale: str = Field(min_length=1)  # Explanation of why this mapping was chosen
    evidence_snippets: list[str] = Field(default_factory=list)  # Supporting code excerpts


class MapOutput(BaseModel):
    """
    Output of the Map stage: requirement-to-code mappings.

    Contains the full analyze output (for provenance) plus a list of mappings
    linking each requirement to its implementing code symbol.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    analyze: AnalyzeOutput  # Nested output from the previous stage
    mappings: list[Mapping]  # One mapping per requirement


class GeneratedTest(BaseModel):
    """
    A single test file generated by the Generate stage.

    Contains the actual test code as a string, along with metadata about which
    requirement it tests and which code symbol it targets.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    requirement_id: str = Field(min_length=1)  # The requirement this test verifies
    file_path: str = Field(min_length=1)  # Suggested file path for the test file
    code: str = Field(min_length=1)  # The actual test source code
    target_symbol: str | None = None  # The code symbol being tested (if applicable)
    rationale: str = Field(min_length=1)  # Why this test was designed this way


class GenerateOutput(BaseModel):
    """
    Output of the Generate stage: generated test files.

    Contains the full map output (for provenance) plus a list of generated
    test files, one or more per requirement-to-code mapping.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    map: MapOutput  # Nested output from the previous stage
    tests: list[GeneratedTest]  # All generated test files


class CritiqueScore(BaseModel):
    """
    Quality score for a single generated test, produced by the Critique stage.

    Each test is scored on three dimensions (1-5 scale) and gets a decision:
      - accept: test is good enough to use as-is
      - revise: test needs improvements (a revised version may be provided)
      - reject: test is fundamentally flawed and should be discarded
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    test_file: str = Field(min_length=1)  # Path of the test being scored
    relevance: int = Field(ge=1, le=5)  # How relevant the test is to the requirement (1-5)
    completeness: int = Field(ge=1, le=5)  # How thoroughly the test covers the requirement (1-5)
    correctness: int = Field(ge=1, le=5)  # How likely the test is to pass and be valid (1-5)
    decision: Literal["accept", "revise", "reject"]  # Overall verdict
    notes: str = Field(min_length=1)  # Explanation of the scores and decision


class CritiqueOutput(BaseModel):
    """
    Output of the Critique stage: scores and optional revisions for generated tests.

    The critique agent evaluates each test and may provide revised versions
    for tests that received a "revise" decision.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    generate: GenerateOutput  # Nested output from the previous stage
    scores: list[CritiqueScore]  # One score per generated test
    revised_tests: list[GeneratedTest] = Field(default_factory=list)  # Improved versions of tests that needed revision


class TraceabilityRow(BaseModel):
    """
    A single row in the traceability matrix, produced by the Trace stage.

    Maps a requirement to its test files and indicates the coverage status.
    This is the core deliverable of the pipeline -- showing whether each
    requirement has adequate test coverage.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    requirement_id: str = Field(min_length=1)  # The requirement being traced
    symbol: str | None = None  # The implementing code symbol (if known)
    test_files: list[str]  # Test files that cover this requirement
    coverage_status: Literal["covered", "partial", "uncovered"]  # How well the requirement is tested


class TraceOutput(BaseModel):
    """
    Output of the Trace stage: the final traceability matrix and gap report.

    This is the last stage's output and the primary deliverable of the pipeline.
    The matrix shows requirement-to-test mappings, and the gap report is a
    Markdown document highlighting requirements with insufficient coverage.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    critique: CritiqueOutput  # Nested output from the previous stage
    matrix: list[TraceabilityRow]  # The traceability matrix
    gap_report_md: str = Field(min_length=1)  # Markdown-formatted coverage gap report
