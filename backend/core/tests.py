"""
Unit and integration tests for the ReqLens core application.

This module contains two test classes:

  ContractsTest: validates that the Pydantic data contracts in pipeline.contracts
  can be instantiated correctly and enforce the expected field types. These are
  pure unit tests with no database access.

  APITest: integration tests that exercise the REST API endpoints using Django's
  test client. These tests hit real views, go through URL routing, and use the
  test database. They verify that the API returns correct HTTP status codes and
  response structures.

Run with: cd backend && uv run pytest  (or: uv run python manage.py test)
"""

from unittest.mock import patch

from django.test import TestCase

from core.models import AgentConfig, Project, Run
from pipeline.contracts import (
    CodeSymbol,
    ParseOutput,
    Requirement,
    TraceabilityRow,
)


class ContractsTest(TestCase):
    """
    Unit tests for the Pydantic data models in pipeline.contracts.

    These tests verify that the contract models can be instantiated with
    valid data and that field values are stored correctly. Since the contracts
    use Pydantic's strict mode and extra="forbid", any schema violations would
    raise ValidationError, so successful instantiation proves the schema is met.
    """

    def test_requirement_model(self):
        """Verify a Requirement can be created with all required fields."""
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
        """Verify a CodeSymbol captures function/method metadata correctly."""
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
        """Verify ParseOutput can be created with an empty requirements list."""
        out = ParseOutput(requirements=[], raw_token_usage={})
        assert out.requirements == []

    def test_traceability_row(self):
        """Verify TraceabilityRow correctly stores coverage status."""
        row = TraceabilityRow(
            requirement_id="REQ-001",
            symbol="Calculator.add",
            test_files=["test_calc.py"],
            coverage_status="covered",
        )
        assert row.coverage_status == "covered"


class APITest(TestCase):
    """
    Integration tests for the REST API endpoints.

    Uses Django's test client which handles URL routing, middleware,
    serialization, and database transactions. Each test method exercises
    a different API endpoint and verifies the response.
    """

    def test_agents_endpoint(self):
        """Verify GET /api/v1/agents returns a non-empty list including claude-code."""
        response = self.client.get("/api/v1/agents")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "claude-code" in [a["id"] for a in data]
        cursor_sdk = next(a for a in data if a["id"] == "cursor-sdk-composer-2")
        assert cursor_sdk["runner"] == "cursor-sdk"
        assert cursor_sdk["model"] == "composer-2"
        assert "composer-2" in cursor_sdk["model_options"]
        assert cursor_sdk["args"]

    def test_projects_list(self):
        """Verify GET /api/v1/projects returns an empty list when no projects exist."""
        response = self.client.get("/api/v1/projects")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_project(self):
        """Verify POST /api/v1/projects creates a project and returns HTTP 201."""
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

    def test_create_run_snapshots_agent_configs_as_json(self):
        """Verify POST /api/v1/projects/<id>/runs stores JSON-serializable config."""
        project = Project.objects.create(
            name="test-project",
            code_path="/tmp/test",
            requirements_path="/tmp/test/requirements.md",
        )
        agent_config = AgentConfig.objects.create(
            project=project,
            stage="parse",
            agent_id="cursor-sdk-composer-2",
            model_id="composer-2",
        )

        async def noop_run_pipeline(*args, **kwargs):
            return None

        with patch("core.views.run_pipeline", noop_run_pipeline):
            response = self.client.post(
                f"/api/v1/projects/{project.id}/runs",
                data={"permissions": "auto"},
                content_type="application/json",
            )

        assert response.status_code == 201
        run = Run.objects.get(id=response.json()["id"])
        assert run.config_snapshot["agents"][0]["id"] == str(agent_config.id)
        assert run.config_snapshot["agents"][0]["agent_id"] == "cursor-sdk-composer-2"
        assert run.config_snapshot["agents"][0]["model_id"] == "composer-2"

    def test_fs_validate(self):
        """Verify GET /api/v1/fs/validate correctly reports that /tmp exists."""
        response = self.client.get("/api/v1/fs/validate?path=/tmp")
        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is True
