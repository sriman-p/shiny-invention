"""
Comprehensive tests for all Pydantic pipeline contracts.
Validates schema enforcement, nesting, serialization, and rejection of bad data.
"""
import json
import pytest
from pydantic import ValidationError
from pipeline.contracts import (
    Requirement, CodeSymbol, ParseOutput, AnalyzeOutput,
    Mapping, MapOutput, GeneratedTest, GenerateOutput,
    CritiqueScore, CritiqueOutput, TraceabilityRow, TraceOutput,
)


# ---------------------------------------------------------------------------
# Requirement
# ---------------------------------------------------------------------------

class TestRequirement:
    def test_valid_functional_requirement(self):
        r = Requirement(
            id="REQ-001", title="Add numbers", description="Calculator adds two numbers",
            type="functional", priority="high",
            acceptance_criteria=["2+3=5", "negative numbers work"],
            source_location="requirements.md:L1-10",
        )
        assert r.id == "REQ-001"
        assert r.type == "functional"
        assert len(r.acceptance_criteria) == 2

    def test_valid_non_functional_requirement(self):
        r = Requirement(
            id="REQ-005", title="Input validation",
            description="Validate inputs are numeric",
            type="non_functional", priority="medium",
            acceptance_criteria=["raise ValueError for strings"],
            source_location="requirements.md:L42-58",
        )
        assert r.type == "non_functional"
        assert r.priority == "medium"

    def test_rejects_invalid_type(self):
        with pytest.raises(ValidationError):
            Requirement(
                id="REQ-X", title="Bad", description="Invalid type",
                type="invalid_type", priority="high",
                acceptance_criteria=[], source_location="x",
            )

    def test_rejects_invalid_priority(self):
        with pytest.raises(ValidationError):
            Requirement(
                id="REQ-X", title="Bad", description="Invalid priority",
                type="functional", priority="critical",
                acceptance_criteria=[], source_location="x",
            )

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            Requirement(
                id="REQ-X", title="Bad", description="Extra field",
                type="functional", priority="high",
                acceptance_criteria=[], source_location="x",
                extra_field="should fail",
            )

    def test_serialization_roundtrip(self):
        r = Requirement(
            id="REQ-001", title="Add", description="Addition",
            type="functional", priority="high",
            acceptance_criteria=["works"], source_location="req.md:L1",
        )
        data = json.loads(r.model_dump_json())
        r2 = Requirement.model_validate(data)
        assert r == r2


# ---------------------------------------------------------------------------
# CodeSymbol
# ---------------------------------------------------------------------------

class TestCodeSymbol:
    def test_valid_method(self):
        s = CodeSymbol(
            qualified_name="src.calc.Calculator.add", kind="method",
            file_path="src/calc.py", line_start=5, line_end=10,
            signature="def add(self, a: float, b: float) -> float",
            docstring="Add two numbers.",
        )
        assert s.kind == "method"
        assert s.line_end > s.line_start

    def test_valid_function_no_docstring(self):
        s = CodeSymbol(
            qualified_name="utils.helper", kind="function",
            file_path="utils.py", line_start=1, line_end=5,
            signature="def helper(x: int) -> str",
        )
        assert s.docstring is None

    def test_valid_class(self):
        s = CodeSymbol(
            qualified_name="src.calc.Calculator", kind="class",
            file_path="src/calc.py", line_start=1, line_end=40,
            signature="class Calculator",
        )
        assert s.kind == "class"

    def test_rejects_invalid_kind(self):
        with pytest.raises(ValidationError):
            CodeSymbol(
                qualified_name="x", kind="module",
                file_path="x.py", line_start=1, line_end=2,
                signature="x",
            )


# ---------------------------------------------------------------------------
# Full pipeline chain — nesting tests
# ---------------------------------------------------------------------------

class TestPipelineChain:
    """Test the full stage output nesting: Parse -> Analyze -> Map -> Generate -> Critique -> Trace."""

    def _make_parse(self):
        return ParseOutput(requirements=[
            Requirement(id="REQ-001", title="Add", description="Addition",
                        type="functional", priority="high",
                        acceptance_criteria=["2+3=5"], source_location="req.md:L1"),
            Requirement(id="REQ-002", title="Subtract", description="Subtraction",
                        type="functional", priority="high",
                        acceptance_criteria=["5-3=2"], source_location="req.md:L10"),
        ], raw_token_usage={"input": 100, "output": 200})

    def _make_symbol(self):
        return CodeSymbol(
            qualified_name="calc.Calculator.add", kind="method",
            file_path="calc.py", line_start=5, line_end=10,
            signature="def add(self, a, b)", docstring="Add two numbers.",
        )

    def test_parse_output(self):
        p = self._make_parse()
        assert len(p.requirements) == 2
        assert p.raw_token_usage["input"] == 100

    def test_analyze_output_nests_parse(self):
        a = AnalyzeOutput(
            parse=self._make_parse(),
            symbols=[self._make_symbol()],
            project_summary="A simple calculator.",
        )
        assert len(a.parse.requirements) == 2
        assert len(a.symbols) == 1
        assert a.project_summary == "A simple calculator."

    def test_map_output_nests_analyze(self):
        analyze = AnalyzeOutput(
            parse=self._make_parse(), symbols=[self._make_symbol()],
            project_summary="Calculator",
        )
        m = MapOutput(analyze=analyze, mappings=[
            Mapping(requirement_id="REQ-001", symbol=self._make_symbol(),
                    confidence=0.95, rationale="Direct implementation"),
            Mapping(requirement_id="REQ-002", symbol=None,
                    confidence=0.0, rationale="No matching symbol found"),
        ])
        assert len(m.mappings) == 2
        assert m.mappings[0].confidence == 0.95
        assert m.mappings[1].symbol is None

    def test_generate_output_nests_map(self):
        analyze = AnalyzeOutput(parse=self._make_parse(), symbols=[self._make_symbol()], project_summary="Calc")
        map_out = MapOutput(analyze=analyze, mappings=[
            Mapping(requirement_id="REQ-001", symbol=self._make_symbol(), confidence=0.9, rationale="Match"),
        ])
        g = GenerateOutput(map=map_out, tests=[
            GeneratedTest(requirement_id="REQ-001", file_path="test_add.py",
                          code="def test_add(): assert Calculator().add(2,3) == 5",
                          target_symbol="calc.Calculator.add", rationale="Test basic addition"),
        ])
        assert len(g.tests) == 1
        assert "assert" in g.tests[0].code

    def test_critique_output_with_scores(self):
        analyze = AnalyzeOutput(parse=self._make_parse(), symbols=[], project_summary="C")
        map_out = MapOutput(analyze=analyze, mappings=[])
        gen = GenerateOutput(map=map_out, tests=[
            GeneratedTest(requirement_id="REQ-001", file_path="test_add.py",
                          code="def test_add(): pass", rationale="Basic test"),
        ])
        c = CritiqueOutput(generate=gen, scores=[
            CritiqueScore(test_file="test_add.py", relevance=4, completeness=3,
                          correctness=5, decision="accept", notes="Good test"),
        ], revised_tests=[])
        assert c.scores[0].decision == "accept"
        assert c.scores[0].relevance == 4

    def test_trace_output_full_chain(self):
        analyze = AnalyzeOutput(parse=self._make_parse(), symbols=[], project_summary="C")
        map_out = MapOutput(analyze=analyze, mappings=[])
        gen = GenerateOutput(map=map_out, tests=[])
        crit = CritiqueOutput(generate=gen, scores=[], revised_tests=[])
        t = TraceOutput(critique=crit, matrix=[
            TraceabilityRow(requirement_id="REQ-001", symbol="calc.add",
                            test_files=["test_add.py"], coverage_status="covered"),
            TraceabilityRow(requirement_id="REQ-002", symbol=None,
                            test_files=[], coverage_status="uncovered"),
        ], gap_report_md="## Gap Report\n- REQ-002 is uncovered")
        assert len(t.matrix) == 2
        assert t.matrix[0].coverage_status == "covered"
        assert t.matrix[1].coverage_status == "uncovered"
        assert "REQ-002" in t.gap_report_md

    def test_full_chain_serialization(self):
        """Verify the entire nested chain serializes to JSON and back."""
        analyze = AnalyzeOutput(parse=self._make_parse(), symbols=[self._make_symbol()], project_summary="Calc")
        map_out = MapOutput(analyze=analyze, mappings=[
            Mapping(requirement_id="REQ-001", symbol=self._make_symbol(), confidence=0.9, rationale="Match"),
        ])
        gen = GenerateOutput(map=map_out, tests=[
            GeneratedTest(requirement_id="REQ-001", file_path="t.py", code="pass", rationale="Test"),
        ])
        crit = CritiqueOutput(generate=gen, scores=[
            CritiqueScore(test_file="t.py", relevance=5, completeness=5, correctness=5, decision="accept", notes="Perfect"),
        ])
        trace = TraceOutput(critique=crit, matrix=[
            TraceabilityRow(requirement_id="REQ-001", symbol="calc.add", test_files=["t.py"], coverage_status="covered"),
        ], gap_report_md="All covered")

        json_str = trace.model_dump_json()
        restored = TraceOutput.model_validate_json(json_str)
        assert restored.critique.scores[0].decision == "accept"
        assert restored.matrix[0].coverage_status == "covered"
