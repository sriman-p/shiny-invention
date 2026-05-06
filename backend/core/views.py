"""
REST API views for the ReqLens core application.

This module defines all HTTP endpoints for the ReqLens API. The views handle:
  - Agent discovery: listing available AI agents and their readiness status
  - Project CRUD: creating and retrieving projects and their agent configurations
  - Run lifecycle: creating pipeline runs, streaming real-time events, fetching
    artifacts, and cancelling runs
  - Sweep management: creating parameter sweeps and streaming sweep events
  - Utility endpoints: filesystem path validation, permission resolution

Real-time updates use Server-Sent Events (SSE). When a run or sweep starts,
it executes in a background thread. Clients connect to the SSE endpoint and
receive stage_started, stage_completed, run_succeeded, etc. events as they
happen. The pub/sub mechanism uses in-memory queues protected by a threading
lock, which works for single-process deployments.
"""

import json
import logging
import os
import queue
import threading
from pathlib import Path
from uuid import UUID

from django.http import HttpRequest, HttpResponse, JsonResponse, StreamingHttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from acp_client.registry import ACP_AGENTS
from pipeline.orchestrator import run_pipeline

from .models import AgentConfig, Project, Run, Sweep
from .serializers import (
    AgentConfigSerializer,
    ProjectCreateSerializer,
    ProjectDetailSerializer,
    ProjectListSerializer,
    RunDetailSerializer,
    RunListSerializer,
    SweepDetailSerializer,
)

logger = logging.getLogger(__name__)

# -- In-memory pub/sub for Server-Sent Events (SSE) --
# Maps a run_id (or "sweep-{sweep_id}") to a list of subscriber queues.
# Each connected SSE client gets its own queue. When a pipeline event fires,
# it is broadcast to all subscriber queues for that run/sweep.
_event_queues: dict[str, list[queue.Queue]] = {}  # type: ignore[type-arg]
_event_queues_lock = threading.Lock()


def _broadcast(run_id: str, event: dict) -> None:  # type: ignore[type-arg]
    """
    Push an event dict to all SSE subscriber queues for the given run/sweep.

    Thread-safe: acquires the global lock before accessing the queue registry.
    """
    with _event_queues_lock:
        queues = _event_queues.get(run_id, [])
        for q in queues:
            q.put(event)


def _subscribe(run_id: str) -> queue.Queue:  # type: ignore[type-arg]
    """
    Register a new SSE subscriber for a run/sweep and return its queue.

    The caller should read from this queue in a loop to receive events.
    """
    q: queue.Queue = queue.Queue()  # type: ignore[type-arg]
    with _event_queues_lock:
        _event_queues.setdefault(run_id, []).append(q)
    return q


def _unsubscribe(run_id: str, q: queue.Queue) -> None:  # type: ignore[type-arg]
    """
    Remove a subscriber queue when an SSE client disconnects.

    Prevents memory leaks from abandoned subscriber queues.
    """
    with _event_queues_lock:
        queues = _event_queues.get(run_id, [])
        if q in queues:
            queues.remove(q)


@api_view(["GET"])
def agents_list(request: HttpRequest) -> Response:
    """
    GET /api/v1/agents -- List all registered AI agents and their availability.

    For each agent in the ACP registry, checks:
      1. Whether the agent's CLI command is on the system PATH
      2. Whether all required environment variables are set
    Returns both individual checks and an overall "available" boolean so the
    frontend can show which agents are ready to use.
    """
    agents = []
    for agent_id, spec in ACP_AGENTS.items():
        import shutil

        command_available = shutil.which(spec.command) is not None
        env_available = all(os.environ.get(k) for k in spec.env_required)
        agents.append(
            {
                "id": spec.id,
                "display_name": spec.display_name,
                "command": spec.command,
                "args": spec.args,
                "runner": spec.runner,
                "model": spec.model,
                "model_options": spec.model_options,
                "available": command_available and env_available,
                "command_on_path": command_available,
                "env_vars_set": env_available,
                "env_required": spec.env_required,
                "notes": spec.notes,
            }
        )
    return Response(agents)


@api_view(["GET", "POST"])
def projects_list_create(request: HttpRequest) -> Response:
    """
    GET  /api/v1/projects -- List all projects (newest first).
    POST /api/v1/projects -- Create a new project.

    On POST, validates the request body with ProjectCreateSerializer and returns
    the full project detail (including empty agents list) with HTTP 201.
    """
    if request.method == "GET":
        projects = Project.objects.all().order_by("-created_at")
        return Response(ProjectListSerializer(projects, many=True).data)

    serializer = ProjectCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    project = serializer.save()
    return Response(ProjectDetailSerializer(project).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def project_detail(request: HttpRequest, project_id: UUID) -> Response:
    """
    GET /api/v1/projects/<project_id> -- Retrieve a single project with its agent configs.
    """
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(ProjectDetailSerializer(project).data)


@api_view(["PATCH"])
def project_agents_update(request: HttpRequest, project_id: UUID) -> Response:
    """
    PATCH /api/v1/projects/<project_id>/agents -- Upsert agent configs for a project.

    Accepts a JSON array of agent config objects. For each one, uses update_or_create
    keyed on (project, stage), so sending the same stage twice overwrites the previous
    config. This design lets the frontend submit all stage configs in a single request
    rather than making six individual calls.
    """
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

    configs = request.data if isinstance(request.data, list) else []
    results = []
    for cfg in configs:
        agent_config, _ = AgentConfig.objects.update_or_create(
            project=project,
            stage=cfg["stage"],
            defaults={
                "agent_id": cfg.get("agent_id", "claude-code"),
                "model_id": cfg.get("model_id") or "",
                "prompt_strategy": cfg.get("prompt_strategy", "zero_shot"),
                "context_mode": cfg.get("context_mode", "full"),
                "enabled": cfg.get("enabled", True),
            },
        )
        results.append(AgentConfigSerializer(agent_config).data)
    return Response(results)


@api_view(["POST"])
def project_runs_create(request: HttpRequest, project_id: UUID) -> Response:
    """
    POST /api/v1/projects/<project_id>/runs -- Start a new pipeline run.

    Steps:
      1. Snapshot the current enabled agent configs into the Run's config_snapshot
      2. Create the run record and its artifacts directory on disk
      3. Launch the pipeline in a background daemon thread (so the HTTP response
         returns immediately with the run's initial state)

    The background thread uses asyncio.run() because the pipeline is async but
    Django views are synchronous. The daemon=True flag ensures the thread won't
    prevent process shutdown.

    Clients can poll the run detail endpoint or connect to the SSE stream to
    track progress.
    """
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

    permissions = request.data.get("permissions", "auto") if request.data else "auto"
    agent_configs = AgentConfigSerializer(project.agents.filter(enabled=True), many=True).data
    config_snapshot = {
        "permissions": permissions,
        "agents": agent_configs,
    }

    # Store artifacts under backend/data/runs/<run_id>/
    artifacts_dir = Path(__file__).resolve().parent.parent / "data" / "runs"
    run = Run.objects.create(
        project=project,
        config_snapshot=config_snapshot,
    )
    run.artifacts_path = str(artifacts_dir / str(run.id))
    run.save()

    os.makedirs(run.artifacts_path, exist_ok=True)

    import asyncio

    def _run_in_thread() -> None:
        """Execute the async pipeline in a new event loop within this thread."""
        try:
            asyncio.run(
                run_pipeline(
                    str(run.id),
                    on_event=lambda evt: _broadcast(str(run.id), evt),
                )
            )
        except Exception as e:
            logger.exception("Pipeline run %s failed: %s", run.id, e)

    t = threading.Thread(target=_run_in_thread, daemon=True)
    t.start()

    return Response(RunDetailSerializer(run).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def run_detail(request: HttpRequest, run_id: UUID) -> Response:
    """
    GET /api/v1/runs/<run_id> -- Retrieve full details of a single run,
    including all stage executions.
    """
    try:
        run = Run.objects.get(id=run_id)
    except Run.DoesNotExist:
        return Response({"error": "Run not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(RunDetailSerializer(run).data)


@api_view(["GET"])
def runs_list(request: HttpRequest) -> Response:
    """
    GET /api/v1/runs -- List the 10 most recent runs across all projects.

    Uses select_related("project") to avoid N+1 queries when serializing
    the project_name field.
    """
    runs = Run.objects.select_related("project").all()[:10]
    return Response(RunListSerializer(runs, many=True).data)


def run_events_stream(request: HttpRequest, run_id: str) -> StreamingHttpResponse:
    """
    GET /api/v1/runs/<run_id>/events -- SSE endpoint for real-time run progress.

    Opens a long-lived HTTP connection that streams pipeline events as they occur.
    Events are formatted as SSE (Server-Sent Events) with "data:" prefix.

    The stream ends when a terminal event (run_succeeded or run_failed) is received.
    A keepalive comment is sent every 30 seconds to prevent proxy/load-balancer timeouts.

    Note: This is a plain Django view (not @api_view) because StreamingHttpResponse
    requires direct control over the response lifecycle.
    """
    q = _subscribe(run_id)

    def event_stream():  # type: ignore[no-untyped-def]
        try:
            while True:
                try:
                    event = q.get(timeout=30)
                    yield f"data: {json.dumps(event)}\n\n"
                    # Stop streaming after a terminal event
                    if event.get("type") in ("run_succeeded", "run_failed"):
                        break
                except queue.Empty:
                    # Send SSE comment as keepalive to prevent connection timeout
                    yield ": keepalive\n\n"
        finally:
            _unsubscribe(run_id, q)

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    # Disable nginx buffering so events are pushed immediately
    response["X-Accel-Buffering"] = "no"
    return response


@api_view(["GET"])
def run_artifacts(request: HttpRequest, run_id: UUID, name: str) -> HttpResponse:
    """
    GET /api/v1/runs/<run_id>/artifacts/<name> -- Serve a run artifact file.

    Each pipeline stage saves its output as a JSON file in the run's artifacts
    directory (e.g., parse.json, analyze.json). This endpoint lets the frontend
    fetch those files by name.
    """
    try:
        run = Run.objects.get(id=run_id)
    except Run.DoesNotExist:
        return JsonResponse({"error": "Run not found"}, status=404)

    file_path = Path(run.artifacts_path) / name
    if not file_path.exists() or not file_path.is_file():
        return JsonResponse({"error": "Artifact not found"}, status=404)

    with open(file_path) as f:
        content = f.read()
    return HttpResponse(content, content_type="application/json")


@api_view(["POST"])
def run_cancel(request: HttpRequest, run_id: UUID) -> Response:
    """
    POST /api/v1/runs/<run_id>/cancel -- Cancel a running pipeline execution.

    Cancels runs that are currently in "pending" or "running" status. Sets the
    status to "cancelled" and records the finish time. Note that this does not
    forcefully terminate the background thread -- the pipeline stages check
    run status and should exit gracefully.
    """
    try:
        run = Run.objects.get(id=run_id)
    except Run.DoesNotExist:
        return Response({"error": "Run not found"}, status=status.HTTP_404_NOT_FOUND)

    if run.status in {"pending", "running"}:
        run.status = "cancelled"
        run.finished_at = timezone.now()
        run.save()
    return Response(RunDetailSerializer(run).data)


@api_view(["POST"])
def sweeps_create(request: HttpRequest, project_id: UUID) -> Response:
    """
    POST /api/v1/projects/<project_id>/sweeps -- Start a parameter sweep.

    Accepts a "matrix" array where each entry specifies a configuration
    (prompt_strategy, context_mode, agent_id). The sweep runner will execute
    a full pipeline run for each configuration, then aggregate metrics and
    perform statistical analysis to compare configurations.

    Like runs, the sweep executes in a background daemon thread.
    """
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

    matrix = request.data.get("matrix", []) if request.data else []
    sweep = Sweep.objects.create(project=project, matrix=matrix)

    import asyncio

    from eval.runner import run_sweep

    def _run_sweep_thread() -> None:
        """Execute the async sweep in a new event loop within this thread."""
        try:
            asyncio.run(
                run_sweep(
                    str(sweep.id),
                    on_event=lambda evt: _broadcast(f"sweep-{sweep.id}", evt),
                )
            )
        except Exception as e:
            logger.exception("Sweep %s failed: %s", sweep.id, e)

    t = threading.Thread(target=_run_sweep_thread, daemon=True)
    t.start()

    return Response(SweepDetailSerializer(sweep).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def sweep_detail(request: HttpRequest, sweep_id: UUID) -> Response:
    """
    GET /api/v1/sweeps/<sweep_id> -- Retrieve full details of a sweep,
    including all associated runs and statistical analysis.
    """
    try:
        sweep = Sweep.objects.get(id=sweep_id)
    except Sweep.DoesNotExist:
        return Response({"error": "Sweep not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(SweepDetailSerializer(sweep).data)


def sweep_events_stream(request: HttpRequest, sweep_id: str) -> StreamingHttpResponse:
    """
    GET /api/v1/sweeps/<sweep_id>/events -- SSE endpoint for real-time sweep progress.

    Works the same as run_events_stream but subscribes to "sweep-{sweep_id}" events.
    Terminates when sweep_succeeded or sweep_failed is received.
    """
    q = _subscribe(f"sweep-{sweep_id}")

    def event_stream():  # type: ignore[no-untyped-def]
        try:
            while True:
                try:
                    event = q.get(timeout=30)
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("type") in ("sweep_succeeded", "sweep_failed"):
                        break
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            _unsubscribe(f"sweep-{sweep_id}", q)

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@api_view(["POST"])
def run_permission_resolve(request: HttpRequest, run_id: UUID, prompt_id: str) -> Response:
    """
    POST /api/v1/runs/<run_id>/permissions/<prompt_id> -- Resolve a permission prompt.

    When the pipeline needs user approval for a potentially dangerous action
    (e.g., writing files), it pauses and waits for this endpoint to be called.
    Currently returns a simple OK response; the full interactive permission
    flow is handled by the acp_client.permissions module.
    """
    return Response({"status": "ok"})


@api_view(["GET"])
def fs_validate(request: HttpRequest) -> Response:
    """
    GET /api/v1/fs/validate?path=<path> -- Check if a filesystem path exists.

    Used by the frontend to validate user-entered code_path and requirements_path
    values before creating a project. Returns {"path": "...", "exists": true/false}.
    """
    path = request.query_params.get("path", "")
    exists = Path(path).exists() if path else False
    return Response({"path": path, "exists": exists})
