"""
Django management command to seed the database with benchmark projects.

Usage: python manage.py seed_benchmark

This command populates the database with a predefined set of small benchmark
projects that live in the repository under benchmark/projects/. Each project
gets a full set of agent configurations (one per pipeline stage), all using
claude-code with zero_shot prompting and full context by default.

These benchmark projects are used for:
  - Development and manual testing (quick end-to-end pipeline runs)
  - Automated sweep benchmarking (comparing prompt strategies and agents)
  - CI/CD smoke tests (verifying the pipeline works on known inputs)

The command is idempotent: running it multiple times will update existing
projects rather than creating duplicates (uses update_or_create).
"""

from pathlib import Path

from django.core.management.base import BaseCommand

from core.models import AgentConfig, Project

# Resolve the benchmark/projects/ directory relative to this file's location.
# The path traverses: commands/ -> management/ -> core/ -> backend/ -> repo root -> benchmark/projects/
BENCHMARK_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "benchmark" / "projects"


class Command(BaseCommand):
    """Django management command that seeds benchmark projects into the database."""

    help = "Seed benchmark projects into the database"

    def handle(self, *args, **options):
        """
        Create or update benchmark projects and their agent configurations.

        Each project entry specifies a name, the path to its source code, and the
        path to its requirements document. After creating the project, all six
        pipeline stages are configured with default agent settings.
        """
        projects = [
            {
                "name": "calculator",
                "code_path": str(BENCHMARK_DIR / "calculator"),
                "requirements_path": str(BENCHMARK_DIR / "calculator" / "requirements.md"),
            },
            {
                "name": "url-shortener",
                "code_path": str(BENCHMARK_DIR / "url-shortener"),
                "requirements_path": str(BENCHMARK_DIR / "url-shortener" / "requirements.md"),
            },
            {
                "name": "todo-api",
                "code_path": str(BENCHMARK_DIR / "todo-api"),
                "requirements_path": str(BENCHMARK_DIR / "todo-api" / "requirements.md"),
            },
        ]

        # All six pipeline stages that need an agent config
        stages = ["parse", "analyze", "map", "generate", "critique", "trace"]

        for proj_data in projects:
            # update_or_create keyed on name ensures idempotency
            project, created = Project.objects.update_or_create(
                name=proj_data["name"],
                defaults=proj_data,
            )
            action = "Created" if created else "Updated"
            self.stdout.write(f"{action} project: {project.name}")

            # Create default agent configs for every stage
            for stage in stages:
                AgentConfig.objects.update_or_create(
                    project=project,
                    stage=stage,
                    defaults={
                        "agent_id": "claude-code",
                        "prompt_strategy": "zero_shot",
                        "context_mode": "full",
                        "enabled": True,
                    },
                )

        self.stdout.write(self.style.SUCCESS(f"Seeded {len(projects)} benchmark projects"))
