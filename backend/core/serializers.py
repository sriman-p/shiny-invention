"""
Django REST Framework serializers for the ReqLens core models.

Serializers handle conversion between Django model instances and JSON representations
for the REST API. Different serializers exist for the same model to control which
fields are exposed in list views (lightweight) vs. detail views (full data with
nested relationships).

Serializer hierarchy:
  - AgentConfigSerializer: used both standalone and nested inside ProjectDetailSerializer
  - ProjectListSerializer / ProjectDetailSerializer / ProjectCreateSerializer:
      list shows summary fields, detail includes nested agent configs, create accepts
      only writable fields
  - StageExecutionSerializer: nested inside RunDetailSerializer to show per-stage results
  - RunListSerializer / RunDetailSerializer: list shows summary, detail shows all
      stages and config snapshot
  - SweepListSerializer / SweepDetailSerializer: detail nests all associated runs
"""

from rest_framework import serializers

from .models import AgentConfig, Project, Run, StageExecution, Sweep


class AgentConfigSerializer(serializers.ModelSerializer):
    """
    Serializes an AgentConfig for a single pipeline stage.

    Used when displaying which agent handles each stage, both as a standalone
    response (e.g., after updating agent configs) and as a nested serializer
    inside ProjectDetailSerializer.
    """

    class Meta:
        model = AgentConfig
        fields = ["id", "stage", "agent_id", "model_id", "prompt_strategy", "context_mode", "enabled"]


class ProjectListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for project list views.

    Excludes nested agent configs and updated_at to keep list responses fast
    and compact when displaying many projects.
    """

    class Meta:
        model = Project
        fields = ["id", "name", "code_path", "requirements_path", "test_framework", "language", "created_at"]


class ProjectDetailSerializer(serializers.ModelSerializer):
    """
    Full serializer for a single project detail view.

    Includes the nested list of agent configurations so the frontend can
    display which agent is assigned to each pipeline stage without making
    a separate API call.
    """

    agents = AgentConfigSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "code_path",
            "requirements_path",
            "test_framework",
            "language",
            "created_at",
            "updated_at",
            "agents",
        ]


class ProjectCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new project.

    Only exposes the writable fields needed to create a project. Fields like
    id, created_at, updated_at, and agents are auto-generated or managed
    separately through the agent config endpoint.
    """

    class Meta:
        model = Project
        fields = ["name", "code_path", "requirements_path", "test_framework", "language"]


class StageExecutionSerializer(serializers.ModelSerializer):
    """
    Serializes a single stage execution record.

    Exposes all observability data for a pipeline stage: what agent ran it,
    its status, input/output payloads, any errors, token usage, and latency.
    Nested inside RunDetailSerializer to show the complete execution trace.
    """

    class Meta:
        model = StageExecution
        fields = [
            "id",
            "stage",
            "agent_id",
            "model_id",
            "status",
            "started_at",
            "finished_at",
            "input_payload",
            "output_payload",
            "raw_updates",
            "reasoning",
            "error",
            "token_usage",
            "latency_ms",
        ]


class RunListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing runs.

    Includes the denormalized project_name (via source="project.name") so the
    frontend can display the project name without a separate lookup. Excludes
    heavy fields like config_snapshot and nested stages.
    """

    # Denormalized field to avoid extra queries on the frontend.
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = Run
        fields = [
            "id",
            "project",
            "project_name",
            "status",
            "config_snapshot",
            "started_at",
            "finished_at",
            "created_at",
        ]


class RunDetailSerializer(serializers.ModelSerializer):
    """
    Full serializer for a single run detail view.

    Nests all StageExecution records and includes the config_snapshot and
    artifacts_path so the frontend can display the complete execution trace
    and link to output artifacts.
    """

    stages = StageExecutionSerializer(many=True, read_only=True)
    # Denormalized project name for convenience.
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = Run
        fields = [
            "id",
            "project",
            "project_name",
            "status",
            "config_snapshot",
            "started_at",
            "finished_at",
            "artifacts_path",
            "created_at",
            "stages",
        ]


class SweepRunStageSerializer(serializers.ModelSerializer):
    """
    Minimal stage serializer for sweep run entries.

    Only includes stage name and status — just enough for the frontend
    to render mini stage progress dots without the heavy payloads.
    """

    class Meta:
        model = StageExecution
        fields = ["stage", "status", "latency_ms"]


class SweepRunSerializer(serializers.ModelSerializer):
    """
    Serializer for runs within a sweep detail view.

    Includes config_snapshot for displaying which strategy/context each run used,
    and a lightweight stages list for mini stage progress indicators.
    """

    project_name = serializers.CharField(source="project.name", read_only=True)
    stages = SweepRunStageSerializer(many=True, read_only=True)

    class Meta:
        model = Run
        fields = [
            "id",
            "project",
            "project_name",
            "status",
            "config_snapshot",
            "started_at",
            "finished_at",
            "created_at",
            "stages",
        ]


class SweepListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing sweeps.

    Includes metrics_summary and stats_report inline because sweeps are
    primarily viewed for their aggregated results.
    """

    class Meta:
        model = Sweep
        fields = [
            "id",
            "project",
            "matrix",
            "status",
            "metrics_summary",
            "stats_report",
            "baseline_summary",
            "created_at",
        ]


class SweepDetailSerializer(serializers.ModelSerializer):
    """
    Full serializer for a single sweep detail view.

    Nests all associated runs (using SweepRunSerializer) so the frontend
    can display individual run results with stage progress alongside the
    aggregated statistics.
    """

    runs = serializers.SerializerMethodField()

    def get_runs(self, obj: Sweep) -> list[dict]:
        """Return runs in creation order so indexes align with sweep.matrix."""
        runs = obj.runs.all().order_by("created_at")
        return SweepRunSerializer(runs, many=True).data

    class Meta:
        model = Sweep
        fields = [
            "id",
            "project",
            "matrix",
            "status",
            "runs",
            "metrics_summary",
            "stats_report",
            "baseline_summary",
            "created_at",
        ]
