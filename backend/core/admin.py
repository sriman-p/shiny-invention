from django.contrib import admin

from .models import AgentConfig, Project, Run, StageExecution, Sweep

admin.site.register(Project)
admin.site.register(AgentConfig)
admin.site.register(Run)
admin.site.register(StageExecution)
admin.site.register(Sweep)
