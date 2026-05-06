from django.urls import path

from . import views

urlpatterns = [
    path("agents", views.agents_list, name="agents-list"),
    path("projects", views.projects_list_create, name="projects-list-create"),
    path("projects/<uuid:project_id>", views.project_detail, name="project-detail"),
    path("projects/<uuid:project_id>/agents", views.project_agents_update, name="project-agents-update"),
    path("projects/<uuid:project_id>/runs", views.project_runs_create, name="project-runs-create"),
    path("projects/<uuid:project_id>/sweeps", views.sweeps_create, name="sweeps-create"),
    path("runs", views.runs_list, name="runs-list"),
    path("runs/<uuid:run_id>", views.run_detail, name="run-detail"),
    path("runs/<str:run_id>/events", views.run_events_stream, name="run-events"),
    path("runs/<uuid:run_id>/artifacts/<str:name>", views.run_artifacts, name="run-artifacts"),
    path("runs/<uuid:run_id>/cancel", views.run_cancel, name="run-cancel"),
    path("runs/<uuid:run_id>/permissions/<str:prompt_id>", views.run_permission_resolve, name="run-permission"),
    path("sweeps/<uuid:sweep_id>", views.sweep_detail, name="sweep-detail"),
    path("sweeps/<str:sweep_id>/events", views.sweep_events_stream, name="sweep-events"),
    path("fs/validate", views.fs_validate, name="fs-validate"),
]
