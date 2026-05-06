from rest_framework import serializers

from .models import AgentConfig, Project, Run, StageExecution, Sweep


class AgentConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentConfig
        fields = ["id", "stage", "agent_id", "prompt_strategy", "context_mode", "enabled"]


class ProjectListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["id", "name", "code_path", "requirements_path", "test_framework", "language", "created_at"]


class ProjectDetailSerializer(serializers.ModelSerializer):
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
    class Meta:
        model = Project
        fields = ["name", "code_path", "requirements_path", "test_framework", "language"]


class StageExecutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = StageExecution
        fields = [
            "id",
            "stage",
            "agent_id",
            "status",
            "started_at",
            "finished_at",
            "input_payload",
            "output_payload",
            "error",
            "token_usage",
            "latency_ms",
        ]


class RunListSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = Run
        fields = ["id", "project", "project_name", "status", "started_at", "finished_at", "created_at"]


class RunDetailSerializer(serializers.ModelSerializer):
    stages = StageExecutionSerializer(many=True, read_only=True)
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


class SweepListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sweep
        fields = ["id", "project", "matrix", "status", "metrics_summary", "stats_report", "created_at"]


class SweepDetailSerializer(serializers.ModelSerializer):
    runs = RunListSerializer(many=True, read_only=True)

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
            "created_at",
        ]
