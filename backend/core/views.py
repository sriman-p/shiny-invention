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

_event_queues: dict[str, list[queue.Queue]] = {}  # type: ignore[type-arg]
_event_queues_lock = threading.Lock()


def _broadcast(run_id: str, event: dict) -> None:  # type: ignore[type-arg]
    with _event_queues_lock:
        queues = _event_queues.get(run_id, [])
        for q in queues:
            q.put(event)


def _subscribe(run_id: str) -> queue.Queue:  # type: ignore[type-arg]
    q: queue.Queue = queue.Queue()  # type: ignore[type-arg]
    with _event_queues_lock:
        _event_queues.setdefault(run_id, []).append(q)
    return q


def _unsubscribe(run_id: str, q: queue.Queue) -> None:  # type: ignore[type-arg]
    with _event_queues_lock:
        queues = _event_queues.get(run_id, [])
        if q in queues:
            queues.remove(q)


@api_view(["GET"])
def agents_list(request: HttpRequest) -> Response:
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
    if request.method == "GET":
        projects = Project.objects.all().order_by("-created_at")
        return Response(ProjectListSerializer(projects, many=True).data)

    serializer = ProjectCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    project = serializer.save()
    return Response(ProjectDetailSerializer(project).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def project_detail(request: HttpRequest, project_id: UUID) -> Response:
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(ProjectDetailSerializer(project).data)


@api_view(["PATCH"])
def project_agents_update(request: HttpRequest, project_id: UUID) -> Response:
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
                "prompt_strategy": cfg.get("prompt_strategy", "zero_shot"),
                "context_mode": cfg.get("context_mode", "full"),
                "enabled": cfg.get("enabled", True),
            },
        )
        results.append(AgentConfigSerializer(agent_config).data)
    return Response(results)


@api_view(["POST"])
def project_runs_create(request: HttpRequest, project_id: UUID) -> Response:
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

    permissions = request.data.get("permissions", "auto") if request.data else "auto"
    agent_configs = list(project.agents.filter(enabled=True).values())
    config_snapshot = {
        "permissions": permissions,
        "agents": agent_configs,
    }

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
    try:
        run = Run.objects.get(id=run_id)
    except Run.DoesNotExist:
        return Response({"error": "Run not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(RunDetailSerializer(run).data)


@api_view(["GET"])
def runs_list(request: HttpRequest) -> Response:
    runs = Run.objects.select_related("project").all()[:10]
    return Response(RunListSerializer(runs, many=True).data)


def run_events_stream(request: HttpRequest, run_id: str) -> StreamingHttpResponse:
    q = _subscribe(run_id)

    def event_stream():  # type: ignore[no-untyped-def]
        try:
            while True:
                try:
                    event = q.get(timeout=30)
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("type") in ("run_succeeded", "run_failed"):
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
    try:
        run = Run.objects.get(id=run_id)
    except Run.DoesNotExist:
        return Response({"error": "Run not found"}, status=status.HTTP_404_NOT_FOUND)

    if run.status == "running":
        run.status = "cancelled"
        run.finished_at = timezone.now()
        run.save()
    return Response(RunDetailSerializer(run).data)


@api_view(["POST"])
def sweeps_create(request: HttpRequest, project_id: UUID) -> Response:
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

    matrix = request.data.get("matrix", []) if request.data else []
    sweep = Sweep.objects.create(project=project, matrix=matrix)

    import asyncio

    from eval.runner import run_sweep

    def _run_sweep_thread() -> None:
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
    try:
        sweep = Sweep.objects.get(id=sweep_id)
    except Sweep.DoesNotExist:
        return Response({"error": "Sweep not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(SweepDetailSerializer(sweep).data)


def sweep_events_stream(request: HttpRequest, sweep_id: str) -> StreamingHttpResponse:
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
    return Response({"status": "ok"})


@api_view(["GET"])
def fs_validate(request: HttpRequest) -> Response:
    path = request.query_params.get("path", "")
    exists = Path(path).exists() if path else False
    return Response({"path": path, "exists": exists})
