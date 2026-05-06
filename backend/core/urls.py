"""
URL routing for the ReqLens core API (mounted under /api/v1/).

All endpoints are RESTful and follow this resource hierarchy:
  - /agents              -- list available AI agents
  - /projects            -- list/create projects
  - /projects/<id>       -- project detail
  - /projects/<id>/agents -- update agent configs for a project
  - /projects/<id>/runs  -- create a new pipeline run for a project
  - /projects/<id>/sweeps -- create a parameter sweep for a project
  - /runs                -- list recent runs across all projects
  - /runs/<id>           -- run detail with all stage executions
  - /runs/<id>/events    -- SSE stream for real-time run progress
  - /runs/<id>/artifacts/<name> -- serve a stage output artifact file
  - /runs/<id>/cancel    -- cancel a running pipeline execution
  - /runs/<id>/permissions/<prompt_id> -- resolve a permission prompt
  - /sweeps/<id>         -- sweep detail with associated runs and stats
  - /sweeps/<id>/events  -- SSE stream for real-time sweep progress
  - /fs/validate         -- check if a filesystem path exists

Note: SSE endpoints use <str:...> instead of <uuid:...> because they are plain
Django views (not DRF api_views) and receive the ID as a string directly.
"""

from django.urls import path

from . import views

urlpatterns = [
    # Agent discovery
    path("agents", views.agents_list, name="agents-list"),
    # Project management
    path("projects", views.projects_list_create, name="projects-list-create"),
    path("projects/<uuid:project_id>", views.project_detail, name="project-detail"),
    path("projects/<uuid:project_id>/agents", views.project_agents_update, name="project-agents-update"),
    path("projects/<uuid:project_id>/runs", views.project_runs_create, name="project-runs-create"),
    path("projects/<uuid:project_id>/sweeps", views.sweeps_create, name="sweeps-create"),
    # Run management
    path("runs", views.runs_list, name="runs-list"),
    path("runs/<uuid:run_id>", views.run_detail, name="run-detail"),
    path("runs/<str:run_id>/events", views.run_events_stream, name="run-events"),
    path("runs/<uuid:run_id>/artifacts/<str:name>", views.run_artifacts, name="run-artifacts"),
    path("runs/<uuid:run_id>/cancel", views.run_cancel, name="run-cancel"),
    path("runs/<uuid:run_id>/permissions/<str:prompt_id>", views.run_permission_resolve, name="run-permission"),
    # Sweep management
    path("sweeps/<uuid:sweep_id>", views.sweep_detail, name="sweep-detail"),
    path("sweeps/<str:sweep_id>/events", views.sweep_events_stream, name="sweep-events"),
    # Utility
    path("fs/validate", views.fs_validate, name="fs-validate"),
]
