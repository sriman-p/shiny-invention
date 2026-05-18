"""
Django admin site registration for ReqLens core models.

Registers all core models with the default Django admin so they can be
viewed and edited through the /admin/ interface. This is primarily useful
for development and debugging -- for example, inspecting run status,
viewing stage execution details, or manually editing agent configs.

No custom admin classes are defined here; the default ModelAdmin is used,
which provides basic list/detail/edit views for each model.
"""

from django.contrib import admin

from .models import AgentConfig, BackgroundTask, Project, Run, StageExecution, Sweep

admin.site.register(Project)
admin.site.register(AgentConfig)
admin.site.register(Run)
admin.site.register(StageExecution)
admin.site.register(Sweep)
admin.site.register(BackgroundTask)
