"""
Async helpers for the BackgroundTask supervision table.

The orchestrator and sweep runner both run inside daemon threads with no
external worker. To detect tasks that died with their host process, we keep a
heartbeat row per active task and reap stale rows on Django startup.

These helpers are async-friendly wrappers around the synchronous Django ORM.
The corresponding synchronous reaper lives in `core.apps.CoreConfig.ready()`.
"""

from __future__ import annotations

import logging
import os
from datetime import timedelta
from typing import Iterable

from asgiref.sync import sync_to_async
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

# How long without a heartbeat before a task is considered abandoned.
STALE_AFTER = timedelta(minutes=5)


@sync_to_async
def register_background_task(*, kind: str, related_id: str) -> str:
    """Create or refresh a BackgroundTask row and return its primary key."""
    from .models import BackgroundTask

    obj, _ = BackgroundTask.objects.update_or_create(
        kind=kind,
        related_id=str(related_id),
        defaults={
            "status": "running",
            "last_heartbeat": timezone.now(),
            "pid": os.getpid(),
        },
    )
    return str(obj.id)


@sync_to_async
def heartbeat_background_task(related_id: str) -> None:
    """Bump the last_heartbeat timestamp for the given related task."""
    from .models import BackgroundTask

    BackgroundTask.objects.filter(related_id=str(related_id), status="running").update(last_heartbeat=timezone.now())


@sync_to_async
def finish_background_task(related_id: str, status: str) -> None:
    """Mark the task complete with a terminal status."""
    from .models import BackgroundTask

    BackgroundTask.objects.filter(related_id=str(related_id)).update(
        status=status,
        last_heartbeat=timezone.now(),
    )


def reap_stale_background_tasks() -> dict[str, int]:
    """Synchronously reap any background tasks whose heartbeat is older than STALE_AFTER.

    Designed to be safe to call from `AppConfig.ready()`: it tolerates a missing
    table (during the first migration) and returns counts of what it cleaned up
    so the calling code can log them.
    """
    counts = {"runs": 0, "sweeps": 0, "tasks": 0}
    try:
        from .models import BackgroundTask, Run, Sweep
    except Exception as exc:  # pragma: no cover - import-time only
        logger.debug("BackgroundTask reaper could not import models: %s", exc)
        return counts

    cutoff = timezone.now() - STALE_AFTER
    try:
        stale = list(
            BackgroundTask.objects.filter(status="running", last_heartbeat__lt=cutoff).values("kind", "related_id")
        )
    except Exception as exc:
        # Table may not exist yet (first run before migrations).
        logger.debug("BackgroundTask reaper skipped (table missing?): %s", exc)
        return counts

    if not stale:
        return counts

    run_ids: list[str] = []
    sweep_ids: list[str] = []
    for row in stale:
        if row["kind"] == "run":
            run_ids.append(row["related_id"])
        elif row["kind"] == "sweep":
            sweep_ids.append(row["related_id"])

    with transaction.atomic():
        if run_ids:
            counts["runs"] = Run.objects.filter(id__in=run_ids, status__in=["pending", "running"]).update(
                status="failed",
                finished_at=timezone.now(),
            )
        if sweep_ids:
            counts["sweeps"] = Sweep.objects.filter(id__in=sweep_ids, status__in=["pending", "running"]).update(
                status="failed"
            )
            stale_sweeps = Sweep.objects.filter(id__in=sweep_ids).prefetch_related("runs")
            for sweep in stale_sweeps:
                counts["runs"] += sweep.runs.filter(status__in=["pending", "running"]).update(
                    status="failed",
                    finished_at=timezone.now(),
                )
        counts["tasks"] = BackgroundTask.objects.filter(status="running", last_heartbeat__lt=cutoff).update(
            status="failed", last_heartbeat=timezone.now()
        )

    if counts["tasks"]:
        logger.warning(
            "BackgroundTask reaper marked %d task(s) failed (runs=%d sweeps=%d)",
            counts["tasks"],
            counts["runs"],
            counts["sweeps"],
        )
    return counts


def list_active_background_tasks() -> Iterable[dict]:
    """Synchronous helper used by the REST endpoint that lists active tasks."""
    try:
        from .models import BackgroundTask
    except Exception:  # pragma: no cover
        return []

    cutoff = timezone.now() - STALE_AFTER
    return [
        {
            "id": str(task.id),
            "kind": task.kind,
            "related_id": task.related_id,
            "status": task.status,
            "last_heartbeat": task.last_heartbeat.isoformat() if task.last_heartbeat else None,
            "pid": task.pid,
            "stale": task.last_heartbeat is not None and task.last_heartbeat < cutoff,
        }
        for task in BackgroundTask.objects.filter(status="running").order_by("-last_heartbeat")
    ]
