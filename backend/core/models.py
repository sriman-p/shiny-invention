"""
Django ORM models for the ReqLens core application.

ReqLens is a requirements-to-code traceability platform that uses AI agents
(via the Agent Communication Protocol) to analyze codebases, extract requirements,
map them to code symbols, generate tests, critique those tests, and produce
traceability matrices.

This module defines the database schema for the entire workflow:
  - Project: a software project to be analyzed
  - AgentConfig: which AI agent handles each pipeline stage for a project
  - Run: a single end-to-end pipeline execution
  - StageExecution: the result of one pipeline stage within a run
  - Sweep: a batch of runs across different configurations for benchmarking

The pipeline stages flow in order: parse -> analyze -> map -> generate -> critique -> trace.
Each stage is executed by an AI agent whose behavior is controlled by a prompt strategy
(how the prompt is structured) and a context mode (how much surrounding code context
is provided to the agent).
"""

import uuid

from django.db import models


class BaseModel(models.Model):
    """
    Abstract base model providing common fields for all ReqLens models.

    Every model gets a UUID primary key (instead of auto-incrementing integers)
    for globally unique identification, plus automatic created/updated timestamps.
    Using UUIDs avoids exposing sequential IDs in the API and makes it safe to
    merge records across database instances.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# -- Choice constants for CharField-based enums --
# These are used across models to constrain field values at the database level
# and provide human-readable labels in Django admin.

# The six pipeline stages in execution order. Each stage produces structured
# output that feeds into the next stage.
STAGE_CHOICES = [
    ("parse", "Parse"),  # Extract requirements from a document
    ("analyze", "Analyze"),  # Inventory code symbols (functions, classes, methods)
    ("map", "Map"),  # Link requirements to implementing code symbols
    ("generate", "Generate"),  # Generate test code for each mapping
    ("critique", "Critique"),  # Score and optionally revise generated tests
    ("trace", "Trace"),  # Build final traceability matrix and gap report
]

# Lifecycle states for a Run or StageExecution.
RUN_STATUS_CHOICES = [
    ("pending", "Pending"),  # Created but not yet started
    ("running", "Running"),  # Currently executing
    ("succeeded", "Succeeded"),  # Completed without errors
    ("failed", "Failed"),  # Terminated due to an error
    ("cancelled", "Cancelled"),  # Manually cancelled by a user
]

# Prompt strategies control how the LLM prompt is structured for each stage.
# Different strategies can produce significantly different quality outputs,
# which is why sweeps exist -- to benchmark strategies against each other.
PROMPT_STRATEGY_CHOICES = [
    ("zero_shot", "Zero Shot"),  # Direct instruction, no examples
    ("chain_of_thought", "Chain of Thought"),  # Asks the agent to reason step-by-step
    ("few_shot_static", "Few Shot Static"),  # Includes hardcoded example outputs
    ("few_shot_dynamic", "Few Shot Dynamic"),  # Includes project-specific example outputs
]

# Context modes control how much surrounding code context is included in prompts.
# More context can improve accuracy but increases token cost and latency.
CONTEXT_MODE_CHOICES = [
    ("minimal", "Minimal"),  # Only the requirement and target symbol
    ("local", "Local"),  # Requirement, symbol, and same-file siblings
    ("module", "Module"),  # Requirement, symbol, and the full module
    ("full", "Full"),  # Everything above plus a project summary
]


class Project(BaseModel):
    """
    A software project that ReqLens will analyze.

    A project points to a codebase on disk (code_path) and a requirements document
    (requirements_path). The pipeline reads these paths to extract requirements and
    analyze code. Each project can have multiple agent configurations (one per stage)
    and multiple runs.
    """

    name = models.CharField(max_length=200, unique=True)
    code_path = models.CharField(max_length=500)
    requirements_path = models.CharField(max_length=500)
    test_framework = models.CharField(max_length=50, default="pytest")
    language = models.CharField(max_length=50, default="python")

    def __str__(self) -> str:
        return self.name


class AgentConfig(BaseModel):
    """
    Configuration binding a specific AI agent to a pipeline stage for a project.

    Each project has at most one agent config per stage (enforced by unique_together).
    This determines which AI agent (e.g., claude-code, codex) handles that stage,
    what prompt strategy to use, and how much code context to include.

    When a run starts, the orchestrator reads these configs to know which agent
    to invoke for each stage.
    """

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="agents")
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES)
    agent_id = models.CharField(max_length=100)
    model_id = models.CharField(max_length=100, blank=True, default="")
    prompt_strategy = models.CharField(max_length=30, choices=PROMPT_STRATEGY_CHOICES, default="zero_shot")
    context_mode = models.CharField(max_length=20, choices=CONTEXT_MODE_CHOICES, default="full")
    enabled = models.BooleanField(default=True)

    class Meta:
        # Only one agent config allowed per (project, stage) pair.
        unique_together = [("project", "stage")]

    def __str__(self) -> str:
        return f"{self.project.name}/{self.stage} -> {self.agent_id}"


class Run(BaseModel):
    """
    A single end-to-end execution of the pipeline for a project.

    When a user triggers a run, the system snapshots the current agent configs
    into config_snapshot (so the run's configuration is immutable even if configs
    change later). The pipeline then executes each stage sequentially, creating
    StageExecution records along the way.

    Artifacts (stage output JSON files) are stored on disk at artifacts_path.
    """

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
    """
    Record of a single pipeline stage's execution within a run.

    Stores the input payload sent to the agent, the structured output received,
    any errors, token usage metrics, and timing information. This provides full
    observability into what happened at each step of the pipeline.
    """

    run = models.ForeignKey(Run, on_delete=models.CASCADE, related_name="stages")
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES)
    agent_id = models.CharField(max_length=100)
    model_id = models.CharField(max_length=100, blank=True, default="")
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
    """
    A parameter sweep that benchmarks different pipeline configurations.

    A sweep takes a matrix of configurations (varying prompt_strategy, context_mode,
    and/or agent_id) and executes a full pipeline run for each combination. After
    all runs complete, it aggregates metrics and runs statistical analysis (ANOVA,
    pairwise t-tests) to determine which configuration performs best.

    The runs relationship tracks all individual runs spawned by this sweep.
    metrics_summary stores per-run metrics, and stats_report stores the
    statistical analysis including ANOVA results and effect sizes.
    """

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
