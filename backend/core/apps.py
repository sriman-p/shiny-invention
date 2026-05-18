"""
Django AppConfig for the ReqLens core application.

`ready()` runs once per process at startup and is the right place to install
the BackgroundTask reaper: any `running` task whose heartbeat is older than
`STALE_AFTER` is assumed to belong to a previous process that crashed, and the
related Run / Sweep is marked as failed so the UI doesn't show a permanently
spinning row.

The reaper guards against a missing table (first run before migrations) and
against the `RUN_MAIN` reload loop in `manage.py runserver`, where `ready()`
fires twice -- once in the parent and once in the autoreloader child.
"""

from __future__ import annotations

import logging
import os

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    name = "core"

    def ready(self) -> None:
        # `runserver` spawns a reloader child; only run the reaper there to
        # avoid double-cleanup races. Outside of runserver, RUN_MAIN is unset
        # and the check is a no-op.
        if os.environ.get("RUN_MAIN") == "false":
            return
        # Skip during pytest-django setup -- the test harness manages its own
        # transactions and would emit "Accessing the database during app
        # initialization" warnings.
        if "pytest" in os.environ.get("_", "") or os.environ.get("PYTEST_CURRENT_TEST"):
            return
        # The reaper only makes sense for long-running server processes that
        # could leave orphaned BackgroundTask rows behind on crash. Restrict
        # it to a small allow-list of server entry points so management
        # commands like `migrate`, `seed_benchmark`, `shell`, etc. don't
        # touch the DB during AppConfig.ready() (which Django warns about).
        argv = list(getattr(__import__("sys"), "argv", []))
        server_commands = {"runserver", "runworker", "uvicorn", "gunicorn", "daphne"}
        is_server = any(cmd in argv for cmd in server_commands) or any(
            entry in (argv[0] if argv else "") for entry in server_commands
        )
        if not is_server:
            return

        try:
            from .background import reap_stale_background_tasks

            reap_stale_background_tasks()
        except Exception as exc:  # pragma: no cover - guard against startup failures
            logger.debug("Background task reaper failed at startup: %s", exc)
