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

import asyncio
import json
import logging
import os
import queue
import threading
import time
from collections import deque
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
    SweepListSerializer,
)

logger = logging.getLogger(__name__)

# -- In-memory pub/sub for Server-Sent Events (SSE) --
# Maps a run_id (or "sweep-{sweep_id}") to a list of subscriber queues.
# Each connected SSE client gets its own queue. When a pipeline event fires,
# it is broadcast to all subscriber queues for that run/sweep AND appended to
# a bounded ring buffer so reconnecting clients can replay the recent history
# (using the EventSource Last-Event-ID header to skip already-seen events).
_event_queues: dict[str, list[queue.Queue]] = {}  # type: ignore[type-arg]
_event_history: dict[str, deque] = {}  # type: ignore[type-arg]
_event_seq: dict[str, int] = {}
_event_queues_lock = threading.Lock()

# Number of events to retain per key for SSE replay on reconnect.
_HISTORY_LIMIT = 200


def _broadcast(run_id: str, event: dict) -> None:  # type: ignore[type-arg]
    """
    Push an event dict to all SSE subscriber queues for the given run/sweep
    and append it to the per-key replay ring buffer.

    Thread-safe: acquires the global lock before accessing the queue registry.
    Each event is annotated with a monotonic `seq` field so SSE clients can
    skip already-delivered events on reconnect.
    """
    with _event_queues_lock:
        seq = _event_seq.get(run_id, 0) + 1
        _event_seq[run_id] = seq
        annotated = {**event, "seq": seq}
        history = _event_history.setdefault(run_id, deque(maxlen=_HISTORY_LIMIT))
        history.append(annotated)
        queues = _event_queues.get(run_id, [])
        for q in queues:
            q.put(annotated)


def _subscribe(run_id: str, last_seq: int = 0) -> tuple[queue.Queue, list[dict]]:  # type: ignore[type-arg]
    """
    Register a new SSE subscriber for a run/sweep and return its queue plus
    any backlog of events the caller hasn't seen yet.

    The caller should drain the backlog first and then read from the queue
    in a loop. `last_seq` is the highest `seq` field the client has already
    received; events with `seq <= last_seq` are filtered from the backlog.
    """
    q: queue.Queue = queue.Queue()  # type: ignore[type-arg]
    with _event_queues_lock:
        _event_queues.setdefault(run_id, []).append(q)
        history = _event_history.get(run_id, deque(maxlen=_HISTORY_LIMIT))
        backlog = [evt for evt in history if int(evt.get("seq") or 0) > int(last_seq or 0)]
    return q, backlog


def _unsubscribe(run_id: str, q: queue.Queue) -> None:  # type: ignore[type-arg]
    """
    Remove a subscriber queue when an SSE client disconnects.

    Prevents memory leaks from abandoned subscriber queues.
    """
    with _event_queues_lock:
        queues = _event_queues.get(run_id, [])
        if q in queues:
            queues.remove(q)


def _parse_last_seq(request: HttpRequest) -> int:
    """Extract the last seen SSE seq from the standard Last-Event-ID header."""
    header = request.headers.get("Last-Event-ID") or request.GET.get("last_event_id")
    try:
        return int(header) if header else 0
    except (ValueError, TypeError):
        return 0


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
    import shutil

    agents = []
    for agent_id, spec in ACP_AGENTS.items():
        command_available = shutil.which(spec.command) is not None
        hard_env_available = all(os.environ.get(k) for k in spec.env_required)

        # Auth mode evaluation: an agent with an `auth_modes` list is
        # authenticated when at least one mode has all of its env vars set.
        # Agents with no auth_modes fall back to the legacy "all env_required
        # set" check (covers agents like `cursor-sdk-composer-2` whose env
        # really is mandatory).
        if spec.auth_modes:
            mode_states = []
            for mode in spec.auth_modes:
                missing = [k for k in mode.env_required if not os.environ.get(k)]
                mode_states.append(
                    {
                        "id": mode.id,
                        "label": mode.label,
                        "satisfied": len(missing) == 0,
                        "missing": missing,
                    }
                )
            authenticated = any(state["satisfied"] for state in mode_states)
            active_mode = next((state["id"] for state in mode_states if state["satisfied"]), None)
        else:
            mode_states = []
            authenticated = hard_env_available
            active_mode = None

        env_available = hard_env_available and authenticated

        payload = spec.serialize()
        payload.update(
            {
                "available": command_available and env_available,
                "command_on_path": command_available,
                "env_vars_set": env_available,
                "active_auth_mode": active_mode,
                "auth_mode_states": mode_states,
            }
        )
        agents.append(payload)
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
                "agent_id": cfg.get("agent_id", "codex"),
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
    existing_configs = list(project.agents.filter(enabled=True))
    if not existing_configs:
        for stage_name in ["parse", "analyze", "map", "generate", "critique", "trace"]:
            AgentConfig.objects.update_or_create(
                project=project,
                stage=stage_name,
                defaults={
                    "agent_id": "codex",
                    "model_id": "gpt-5.5/low",
                    "prompt_strategy": "zero_shot",
                    "context_mode": "full",
                    "enabled": True,
                },
            )
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
            Run.objects.filter(id=run.id, status__in=["pending", "running"]).update(
                status="failed",
                finished_at=timezone.now(),
            )
            _broadcast(str(run.id), {"type": "run_failed", "run_id": str(run.id), "payload": {"error": str(e)}})

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
    Events are formatted as SSE (Server-Sent Events) with "data:" + "id:" prefix
    (id = the broadcast sequence number used by EventSource's Last-Event-ID
    auto-reconnect). On reconnect, the server replays buffered events strictly
    after the client's `Last-Event-ID` header so no events are lost.

    The stream ends when a terminal event (run_succeeded / run_failed /
    run_cancelled) is received. A keepalive comment is sent every 30 seconds
    to prevent proxy/load-balancer timeouts.
    """
    last_seq = _parse_last_seq(request)
    q, backlog = _subscribe(run_id, last_seq=last_seq)

    def event_stream():  # type: ignore[no-untyped-def]
        try:
            terminal_seen = False
            for event in backlog:
                seq = event.get("seq") or ""
                yield f"id: {seq}\ndata: {json.dumps(event)}\n\n"
                if event.get("type") in ("run_succeeded", "run_failed", "run_cancelled"):
                    terminal_seen = True
            if terminal_seen:
                return
            while True:
                try:
                    event = q.get(timeout=30)
                    seq = event.get("seq") or ""
                    yield f"id: {seq}\ndata: {json.dumps(event)}\n\n"
                    if event.get("type") in ("run_succeeded", "run_failed", "run_cancelled"):
                        break
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            _unsubscribe(run_id, q)

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
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
        # Notify SSE subscribers so the stream terminates immediately
        _broadcast(
            str(run_id),
            {
                "type": "run_cancelled",
                "run_id": str(run_id),
                "ts": timezone.now().isoformat(),
            },
        )
    return Response(RunDetailSerializer(run).data)


@api_view(["GET", "POST"])
def sweeps_create(request: HttpRequest, project_id: UUID) -> Response:
    """
    GET  /api/v1/projects/<project_id>/sweeps -- List sweeps for a project.
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

    if request.method == "GET":
        sweeps = project.sweeps.all().order_by("-created_at")
        return Response(SweepListSerializer(sweeps, many=True).data)

    payload = request.data if isinstance(request.data, dict) else {}
    # Accept either a pre-expanded matrix or axes that we expand server-side.
    matrix, _summary = _expand_sweep_axes(payload)
    if not matrix:
        return Response({"error": "Sweep matrix cannot be empty"}, status=status.HTTP_400_BAD_REQUEST)

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
            Sweep.objects.filter(id=sweep.id, status__in=["pending", "running"]).update(status="failed")
            sweep.runs.filter(status__in=["pending", "running"]).update(status="failed", finished_at=timezone.now())
            _broadcast(
                f"sweep-{sweep.id}",
                {"type": "sweep_failed", "sweep_id": str(sweep.id), "payload": {"error": str(e)}},
            )

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


@api_view(["POST"])
def sweep_cancel(request: HttpRequest, sweep_id: UUID) -> Response:
    """
    POST /api/v1/sweeps/<sweep_id>/cancel -- Cancel a running sweep.

    Cancels the sweep and all its associated runs that are still pending or
    running. The parallel sweep runner has already queued all run rows, so this
    marks every visible pending/running child run as cancelled.
    """
    try:
        sweep = Sweep.objects.get(id=sweep_id)
    except Sweep.DoesNotExist:
        return Response({"error": "Sweep not found"}, status=status.HTTP_404_NOT_FOUND)

    if sweep.status in {"pending", "running"}:
        sweep.status = "cancelled"
        sweep.save()

        # Cancel all pending/running runs associated with this sweep
        for run in sweep.runs.filter(status__in=["pending", "running"]):
            run.status = "cancelled"
            run.finished_at = timezone.now()
            run.save()
            # Notify run SSE subscribers
            _broadcast(
                str(run.id),
                {
                    "type": "run_cancelled",
                    "run_id": str(run.id),
                    "ts": timezone.now().isoformat(),
                },
            )

        # Notify sweep SSE subscribers so the stream terminates
        _broadcast(
            f"sweep-{sweep_id}",
            {
                "type": "sweep_cancelled",
                "sweep_id": str(sweep_id),
                "ts": timezone.now().isoformat(),
            },
        )

    return Response(SweepDetailSerializer(sweep).data)


def sweep_events_stream(request: HttpRequest, sweep_id: str) -> StreamingHttpResponse:
    """
    GET /api/v1/sweeps/<sweep_id>/events -- SSE endpoint for real-time sweep progress.

    Works the same as run_events_stream but subscribes to `sweep-{sweep_id}`.
    Honours `Last-Event-ID` for replay on reconnect. Terminates when
    sweep_succeeded, sweep_failed, or sweep_cancelled is received.
    """
    key = f"sweep-{sweep_id}"
    last_seq = _parse_last_seq(request)
    q, backlog = _subscribe(key, last_seq=last_seq)

    def event_stream():  # type: ignore[no-untyped-def]
        try:
            terminal_seen = False
            for event in backlog:
                seq = event.get("seq") or ""
                yield f"id: {seq}\ndata: {json.dumps(event)}\n\n"
                if event.get("type") in ("sweep_succeeded", "sweep_failed", "sweep_cancelled"):
                    terminal_seen = True
            if terminal_seen:
                return
            while True:
                try:
                    event = q.get(timeout=30)
                    seq = event.get("seq") or ""
                    yield f"id: {seq}\ndata: {json.dumps(event)}\n\n"
                    if event.get("type") in ("sweep_succeeded", "sweep_failed", "sweep_cancelled"):
                        break
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            _unsubscribe(key, q)

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@api_view(["POST"])
def run_permission_resolve(request: HttpRequest, run_id: UUID, prompt_id: str) -> Response:
    """
    POST /api/v1/runs/<run_id>/permissions/<prompt_id> -- Resolve a permission prompt.

    When the pipeline needs user approval for a potentially dangerous action
    (e.g., writing files), the orchestrator pauses on
    `acp_client.permissions.handle_permission_request`. This endpoint resolves
    that pending future with the user's decision.

    Request body (optional): `{"outcome": "allowed_once" | "cancelled"}`
    Defaults to `allowed_once` when no body is provided.
    """
    from acp_client.permissions import resolve_permission

    decision = request.data if isinstance(request.data, dict) else {}
    outcome = decision.get("outcome") or "allowed_once"
    resolved = resolve_permission(str(run_id), str(prompt_id), {"outcome": outcome})
    payload = {"resolved": resolved, "outcome": outcome}
    # Echo a `permission_resolved` event so the UI can clear the prompt card.
    _broadcast(
        str(run_id),
        {
            "type": "permission_resolved",
            "run_id": str(run_id),
            "payload": {"prompt_id": str(prompt_id), "outcome": outcome, "resolved": resolved},
        },
    )
    if not resolved:
        return Response(payload, status=status.HTTP_404_NOT_FOUND)
    return Response(payload)


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


def _expand_sweep_axes(payload: dict) -> tuple[list[dict], dict]:
    """
    Expand a sweep axes payload into a flat matrix of cells.

    Accepts either of three shapes:

      1. ``{"matrix": [...]}`` -- already-flat matrix passed straight through.

      2. ``{"axes": {"agents": [...], "strategies": [...], "contexts": [...]}}``
         Cartesian product across all three axes. Use this when you want the
         full "every strategy × every context" grid for each (agent, model)
         row.

      3. ``{"axes": {"agents": [...], "pairs": [{"prompt_strategy", "context_mode"}, ...]}}``
         Cartesian product of agents x pairs. Use this when the UI lets the
         user toggle individual strategy/context cells -- only the explicitly
         enabled cells become runs (no implicit cross-product between
         strategy and context).

    Returns (matrix, summary) where summary is
    ``{"agent_count", "strategy_count", "context_count", "pair_count", "total_cells"}``
    so the UI can show "N agents × M cells = L runs" before submitting.
    """
    if not isinstance(payload, dict):
        return [], {
            "agent_count": 0,
            "strategy_count": 0,
            "context_count": 0,
            "pair_count": 0,
            "total_cells": 0,
        }

    matrix = payload.get("matrix")
    if isinstance(matrix, list) and matrix:
        cells = [c for c in matrix if isinstance(c, dict)]
        return list(matrix), {
            "agent_count": len({(c.get("agent_id"), c.get("model_id")) for c in cells}),
            "strategy_count": len({c.get("prompt_strategy") for c in cells}),
            "context_count": len({c.get("context_mode") for c in cells}),
            "pair_count": len({(c.get("prompt_strategy"), c.get("context_mode")) for c in cells}),
            "total_cells": len(matrix),
        }

    axes = payload.get("axes") or {}
    if not isinstance(axes, dict):
        return [], {
            "agent_count": 0,
            "strategy_count": 0,
            "context_count": 0,
            "pair_count": 0,
            "total_cells": 0,
        }

    agents = axes.get("agents") or [{"agent_id": "codex", "model_id": "gpt-5.5/low"}]
    include_direct_baseline = bool(axes.get("include_direct_baseline"))

    # Prefer the explicit "pairs" form so toggling individual strategy/context
    # cells produces exactly N runs per agent (not N x N like the cartesian
    # product would). Falls back to the legacy strategies+contexts product
    # when no pairs are supplied.
    raw_pairs = axes.get("pairs")
    pairs: list[tuple[str, str]] = []
    if isinstance(raw_pairs, list) and raw_pairs:
        for entry in raw_pairs:
            if not isinstance(entry, dict):
                continue
            pairs.append(
                (
                    str(entry.get("prompt_strategy") or "zero_shot"),
                    str(entry.get("context_mode") or "full"),
                )
            )
    else:
        strategies = axes.get("strategies") or ["zero_shot"]
        contexts = axes.get("contexts") or ["full"]
        for strategy in strategies:
            for context in contexts:
                pairs.append((str(strategy), str(context)))

    expanded: list[dict] = []
    for ag in agents:
        if not isinstance(ag, dict):
            continue
        agent_id = str(ag.get("agent_id") or "codex")
        model_id = str(ag.get("model_id") or "")
        if include_direct_baseline:
            expanded.append(
                {
                    "agent_id": agent_id,
                    "model_id": model_id,
                    "prompt_strategy": "direct_acp_baseline",
                    "context_mode": "direct",
                    "run_mode": "direct_acp_baseline",
                    "comparison_baseline": True,
                }
            )
        for strategy, context in pairs:
            expanded.append(
                {
                    "agent_id": agent_id,
                    "model_id": model_id,
                    "prompt_strategy": strategy,
                    "context_mode": context,
                }
            )

    return expanded, {
        "agent_count": len(agents),
        "strategy_count": len({strategy for strategy, _ in pairs}) + (1 if include_direct_baseline else 0),
        "context_count": len({context for _, context in pairs}) + (1 if include_direct_baseline else 0),
        "pair_count": len(pairs) + (1 if include_direct_baseline else 0),
        "total_cells": len(expanded),
    }


@api_view(["POST"])
def sweep_preview(request: HttpRequest, project_id: UUID) -> Response:
    """
    POST /api/v1/projects/<project_id>/sweeps/preview -- Expand sweep axes
    into a flat cell matrix without persisting anything.

    Used by the multi-row Agent/Model matrix builder in the UI: the user adds
    (agent, model) rows + ticks strategy/context cells, the UI POSTs the axes,
    and the server returns the expanded matrix it would actually run, plus a
    short summary so the UI can show "N agents × M strategies × K contexts =
    L runs" before the user submits.
    """
    matrix, summary = _expand_sweep_axes(request.data if isinstance(request.data, dict) else {})
    return Response({"matrix": matrix, "summary": summary})


@api_view(["GET"])
def background_tasks_list(request: HttpRequest) -> Response:
    """
    GET /api/v1/background-tasks -- List currently active background tasks.

    Returns a row for each running orchestrator/sweep coroutine along with
    `last_heartbeat` and a `stale` flag (True when the heartbeat is older
    than the reaper threshold). The frontend polls this endpoint to render
    a "Background Tasks" badge in the sidebar so the user can always see
    what work the server is currently doing.
    """
    from .background import list_active_background_tasks

    return Response(list(list_active_background_tasks()))


# Process-local cache of {agent_id: (timestamp, [model_ids])}. The discovery
# call spawns the agent CLI which is expensive; results are stable for a
# session so a 5-minute TTL is more than enough.
_AGENT_MODEL_CACHE: dict[str, tuple[float, list[str]]] = {}
_AGENT_MODEL_CACHE_TTL = 300.0
_AGENT_MODEL_CACHE_LOCK = threading.Lock()


@api_view(["GET"])
def agent_models(request: HttpRequest, agent_id: str) -> Response:
    """
    GET /api/v1/agents/<agent_id>/models -- Discover the models an ACP agent
    actually advertises by spawning a short-lived ACP session.

    Returns `{"agent_id", "discovered", "models", "static": [...], "error"?}`.
    `discovered=True` means the list came from a live ACP `session.models`
    call; `discovered=False` means we returned the static catalog (either
    the agent doesn't speak ACP, or discovery failed). The frontend
    `<ModelSelect>` prefers the discovered list when present so the picker
    can never offer a model the adapter would reject.
    """
    from acp_client.registry import ACP_AGENTS
    from acp_client.runner import discover_agent_models

    spec = ACP_AGENTS.get(agent_id)
    if spec is None:
        return Response({"error": "Agent not found"}, status=status.HTTP_404_NOT_FOUND)

    static_models = list(spec.model_options or [])

    refresh = request.query_params.get("refresh") in {"1", "true", "yes"}
    now = time.monotonic()
    with _AGENT_MODEL_CACHE_LOCK:
        cached = _AGENT_MODEL_CACHE.get(agent_id)
    if cached is not None and not refresh:
        ts, models = cached
        if now - ts < _AGENT_MODEL_CACHE_TTL and models:
            return Response(
                {
                    "agent_id": agent_id,
                    "discovered": True,
                    "models": models,
                    "static": static_models,
                    "cached": True,
                }
            )

    try:
        loop = asyncio.new_event_loop()
        try:
            models = loop.run_until_complete(discover_agent_models(agent_id))
        finally:
            loop.close()
    except Exception as exc:
        logger.warning("agent_models discovery failed for %s: %s", agent_id, exc)
        return Response(
            {
                "agent_id": agent_id,
                "discovered": False,
                "models": static_models,
                "static": static_models,
                "error": str(exc),
            }
        )

    if not models:
        return Response(
            {
                "agent_id": agent_id,
                "discovered": False,
                "models": static_models,
                "static": static_models,
            }
        )

    with _AGENT_MODEL_CACHE_LOCK:
        _AGENT_MODEL_CACHE[agent_id] = (now, models)

    return Response(
        {
            "agent_id": agent_id,
            "discovered": True,
            "models": models,
            "static": static_models,
        }
    )
