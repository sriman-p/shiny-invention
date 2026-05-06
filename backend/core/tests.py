import pytest
from django.test import TestCase

from pipeline.contracts import (
    CodeSymbol,
    CritiqueOutput,
    CritiqueScore,
    GenerateOutput,
    GeneratedTest,
    MapOutput,
    Mapping,
    ParseOutput,
    Requirement,
    TraceOutput,
    TraceabilityRow,
)


class ContractsTest(TestCase):
    def test_requirement_model(self):
        req = Requirement(
            id="REQ-001",
            title="Test Requirement",
            description="A test requirement",
            type="functional",
            priority="high",
            acceptance_criteria=["It works"],
            source_location="requirements.md:L1-5",
        )
        assert req.id == "REQ-001"
        assert req.type == "functional"

    def test_code_symbol_model(self):
        sym = CodeSymbol(
            qualified_name="src.calc.Calculator.add",
            kind="method",
            file_path="src/calc.py",
            line_start=5,
            line_end=10,
            signature="def add(self, a: float, b: float) -> float",
            docstring="Add two numbers.",
        )
        assert sym.kind == "method"

    def test_parse_output(self):
        out = ParseOutput(requirements=[], raw_token_usage={})
        assert out.requirements == []

    def test_traceability_row(self):
        row = TraceabilityRow(
            requirement_id="REQ-001",
            symbol="Calculator.add",
            test_files=["test_calc.py"],
            coverage_status="covered",
        )
        assert row.coverage_status == "covered"


class APITest(TestCase):
    def test_agents_endpoint(self):
        response = self.client.get("/api/v1/agents")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "claude-code" in [a["id"] for a in data]

    def test_projects_list(self):
        response = self.client.get("/api/v1/projects")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_project(self):
        response = self.client.post(
            "/api/v1/projects",
            data={
                "name": "test-project",
                "code_path": "/tmp/test",
                "requirements_path": "/tmp/test/requirements.md",
            },
            content_type="application/json",
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-project"

    def test_fs_validate(self):
        response = self.client.get("/api/v1/fs/validate?path=/tmp")
        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is True
