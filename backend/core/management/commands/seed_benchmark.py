from pathlib import Path

from django.core.management.base import BaseCommand

from core.models import AgentConfig, Project

BENCHMARK_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "benchmark" / "projects"


class Command(BaseCommand):
    help = "Seed benchmark projects into the database"

    def handle(self, *args, **options):
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

        stages = ["parse", "analyze", "map", "generate", "critique", "trace"]

        for proj_data in projects:
            project, created = Project.objects.update_or_create(
                name=proj_data["name"],
                defaults=proj_data,
            )
            action = "Created" if created else "Updated"
            self.stdout.write(f"{action} project: {project.name}")

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
