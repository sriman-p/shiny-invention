from typing import Literal

from pydantic import BaseModel, ConfigDict


class Requirement(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    title: str
    description: str
    type: Literal["functional", "non_functional"]
    priority: Literal["high", "medium", "low"]
    acceptance_criteria: list[str]
    source_location: str


class CodeSymbol(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    qualified_name: str
    kind: Literal["function", "class", "method"]
    file_path: str
    line_start: int
    line_end: int
    signature: str
    docstring: str | None = None


class ParseOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirements: list[Requirement]
    raw_token_usage: dict = {}


class AnalyzeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parse: ParseOutput
    symbols: list[CodeSymbol]
    project_summary: str


class Mapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement_id: str
    symbol: CodeSymbol | None = None
    confidence: float
    rationale: str
    evidence_snippets: list[str] = []


class MapOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analyze: AnalyzeOutput
    mappings: list[Mapping]


class GeneratedTest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement_id: str
    file_path: str
    code: str
    target_symbol: str | None = None
    rationale: str


class GenerateOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    map: MapOutput
    tests: list[GeneratedTest]


class CritiqueScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_file: str
    relevance: int
    completeness: int
    correctness: int
    decision: Literal["accept", "revise", "reject"]
    notes: str


class CritiqueOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generate: GenerateOutput
    scores: list[CritiqueScore]
    revised_tests: list[GeneratedTest] = []


class TraceabilityRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement_id: str
    symbol: str | None = None
    test_files: list[str]
    coverage_status: Literal["covered", "partial", "uncovered"]


class TraceOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    critique: CritiqueOutput
    matrix: list[TraceabilityRow]
    gap_report_md: str
