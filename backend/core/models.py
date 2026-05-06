import uuid

from django.db import models


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


STAGE_CHOICES = [
    ("parse", "Parse"),
    ("analyze", "Analyze"),
    ("map", "Map"),
    ("generate", "Generate"),
    ("critique", "Critique"),
    ("trace", "Trace"),
]

RUN_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("running", "Running"),
    ("succeeded", "Succeeded"),
    ("failed", "Failed"),
    ("cancelled", "Cancelled"),
]

PROMPT_STRATEGY_CHOICES = [
    ("zero_shot", "Zero Shot"),
    ("chain_of_thought", "Chain of Thought"),
    ("few_shot_static", "Few Shot Static"),
    ("few_shot_dynamic", "Few Shot Dynamic"),
]

CONTEXT_MODE_CHOICES = [
    ("minimal", "Minimal"),
    ("local", "Local"),
    ("module", "Module"),
    ("full", "Full"),
]


class Project(BaseModel):
    name = models.CharField(max_length=200, unique=True)
    code_path = models.CharField(max_length=500)
    requirements_path = models.CharField(max_length=500)
    test_framework = models.CharField(max_length=50, default="pytest")
    language = models.CharField(max_length=50, default="python")

    def __str__(self) -> str:
        return self.name


class AgentConfig(BaseModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="agents")
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES)
    agent_id = models.CharField(max_length=100)
    prompt_strategy = models.CharField(max_length=30, choices=PROMPT_STRATEGY_CHOICES, default="zero_shot")
    context_mode = models.CharField(max_length=20, choices=CONTEXT_MODE_CHOICES, default="full")
    enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = [("project", "stage")]

    def __str__(self) -> str:
        return f"{self.project.name}/{self.stage} -> {self.agent_id}"


class Run(BaseModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="runs")
    status = models.CharField(max_length=20, choices=RUN_STATUS_CHOICES, default="pending")
    config_snapshot = models.JSONField(default=dict)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    artifacts_path = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Run {self.id} ({self.status})"


class StageExecution(BaseModel):
    run = models.ForeignKey(Run, on_delete=models.CASCADE, related_name="stages")
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES)
    agent_id = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=RUN_STATUS_CHOICES, default="pending")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    input_payload = models.JSONField(default=dict)
    output_payload = models.JSONField(null=True, blank=True)
    error = models.TextField(blank=True, default="")
    token_usage = models.JSONField(default=dict)
    latency_ms = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.run_id}/{self.stage} ({self.status})"


class Sweep(BaseModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="sweeps")
    matrix = models.JSONField(default=list)
    status = models.CharField(max_length=20, choices=RUN_STATUS_CHOICES, default="pending")
    runs = models.ManyToManyField(Run, related_name="sweeps", blank=True)
    metrics_summary = models.JSONField(null=True, blank=True)
    stats_report = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Sweep {self.id} ({self.status})"
