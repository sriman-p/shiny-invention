"""
Migration: add reasoning stream + baseline summary + BackgroundTask supervision.

Adds:
  - StageExecution.reasoning (JSONField, default list) — normalized
    ReasoningChunk timeline used by the run/sweep UIs.
  - Sweep.baseline_summary (JSONField, nullable) — pre-computed deltas vs
    the worst-performing config so the "Lift vs worst" UI never recomputes.
  - BackgroundTask model — heartbeat row used by the AppConfig.ready()
    reaper to mark stale runs/sweeps as failed after a process restart.
"""

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0003_stageexecution_raw_updates"),
    ]

    operations = [
        migrations.AddField(
            model_name="stageexecution",
            name="reasoning",
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name="sweep",
            name="baseline_summary",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="BackgroundTask",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "kind",
                    models.CharField(
                        choices=[("run", "Run"), ("sweep", "Sweep")],
                        max_length=10,
                    ),
                ),
                ("related_id", models.CharField(db_index=True, max_length=64)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("running", "Running"),
                            ("succeeded", "Succeeded"),
                            ("failed", "Failed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="running",
                        max_length=20,
                    ),
                ),
                ("last_heartbeat", models.DateTimeField(auto_now_add=True)),
                ("pid", models.IntegerField(blank=True, null=True)),
            ],
            options={
                "ordering": ["-last_heartbeat"],
            },
        ),
        migrations.AddIndex(
            model_name="backgroundtask",
            index=models.Index(
                fields=["status", "last_heartbeat"],
                name="core_backgr_status_f1aef9_idx",
            ),
        ),
    ]
