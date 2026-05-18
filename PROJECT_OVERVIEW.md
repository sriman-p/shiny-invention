# ReqLens — Project Overview

> A **requirement‑traced test generation tool** that runs a 6‑stage AI pipeline, delegates every stage to an external coding agent over the **Agent Client Protocol (ACP)** (with a Cursor SDK Composer 2 bridge), and ships a typed traceability matrix + gap report back to the user.

This document is a single‑page tour of the project: the **why**, the **what**, and the **how**, with every meaningful flow drawn as a Mermaid diagram. It is intentionally exhaustive — read top‑to‑bottom for a guided tour, or jump to a flow.

---

## 1. The 30‑Second Pitch

### Why does this exist?

Modern AI test generators (Copilot, single‑shot LLM prompts, EvoSuite, Pynguin) all share the same blind spot: **they produce tests, but they cannot tell you *which requirement* each test verifies**. In regulated or large codebases that is fatal — you cannot prove coverage, you cannot answer "which tests verify REQ‑247?", and gap reports do not exist.

ReqLens treats requirement‑to‑test traceability as a **first‑class deliverable**, not a side‑effect.

### What is it?

- A **Django 5.x backend** + **Next.js 16 / React 19 frontend** monorepo.
- A **6‑stage typed pipeline**: `parse → analyze → map → generate → critique → trace`.
- Every stage's I/O is a **Pydantic v2 model** with `extra="forbid"` and `strict=True`, so a malformed agent reply is caught at the boundary instead of silently corrupting downstream stages.
- All LLM work is delegated to **external coding agents** over **ACP**, plus a **Cursor SDK Composer 2** bridge. Currently 9 agents are registered (Claude Code, OpenAI Codex, Cursor Agent, Cursor SDK, Gemini, OpenCode, Kiro, Blackbox, Qwen Coder).
- A **hybrid retrieval engine** (FAISS dense + BM25 sparse, α=0.6) shortlists candidate code symbols before mapping.
- A **sweep evaluator** runs the same project across an N‑axis matrix `(agent, model, prompt_strategy, context_mode)` and produces ANOVA + Bonferroni‑corrected pairwise t‑tests + a "lift vs. worst configuration" delta table.

### How does it work, in one diagram?

```mermaid
flowchart LR
    User([User])
    UI["Next.js 16 / React 19<br/>localhost:3000"]
    API["Django 5.x REST + SSE<br/>localhost:8000/api/v1"]
    Orch["pipeline/orchestrator.py<br/>asyncio in daemon thread"]
    Stages["pipeline/stages/*<br/>parse → analyze → map →<br/>generate → critique → trace"]
    ACP["acp_client/runner.py<br/>ACP + Cursor SDK bridge"]
    Agents([External coding agents<br/>Claude / Codex / Gemini / Cursor / ...])
    Eval["eval/{metrics,stats,runner}<br/>ANOVA + baseline diff"]
    DB[(SQLite<br/>backend/data/reqlens.db)]
    Bg["BackgroundTask supervisor<br/>core/background.py"]

    User -- "browse / configure / start run" --> UI
    UI -- "REST + EventSource (SSE)" --> API
    API -- "spawn run" --> Orch
    API -- "spawn sweep" --> Eval
    Orch --> Stages
    Stages -- "run_acp_prompt" --> ACP
    ACP -- "spawn subprocess / SDK call" --> Agents
    Agents -- "session/update + onStep" --> ACP
    ACP --> Stages
    Orch -- "stage events / token usage" --> DB
    Orch -- "ring-buffered SSE" --> API
    API -- "EventSource frames" --> UI
    Eval -- "metrics + stats" --> DB
    Orch <-- "heartbeat" --> Bg
    Eval <-- "heartbeat" --> Bg
    API -- "GET /background-tasks" --> Bg
```

---

## 2. The Six Pipeline Stages (the "what")

Each stage has a focused responsibility, a typed input contract, a typed output contract, and a snapshot of `input_payload` / `output_payload` / `raw_updates` / normalized `reasoning` / `token_usage` / `latency_ms` stored on a `StageExecution` row.

```mermaid
flowchart LR
    Doc[/"requirements.md"/] --> P[Parse]
    Code[/"codebase/"/] --> A[Analyze]
    P -->|ParseOutput<br/>Requirement[]| M[Map]
    A -->|AnalyzeOutput<br/>CodeSymbol[]| M
    Retr["Hybrid retrieval<br/>FAISS + BM25 (α=0.6)<br/>local / module / full only"] -.shortlist hints.-> M
    M -->|MapOutput<br/>Mapping[] + confidence| G[Generate]
    G -->|GenerateOutput<br/>GeneratedTest[] + rationale| C[Critique]
    C -->|CritiqueOutput<br/>CritiqueScore[] 1-5 + revisions| T[Trace]
    T -->|TraceOutput<br/>matrix + gap report| Out[/"Final deliverable"/]

    classDef stage fill:#1e293b,stroke:#38bdf8,color:#f8fafc;
    class P,A,M,G,C,T stage;
```

**Why six and not one?**

| Stage | Responsibility | Why it's separate |
|---|---|---|
| **Parse** | Normalize unstructured requirements doc → `Requirement[]` with id / title / description / type / priority / acceptance criteria / source location | Single‑pass generation skips this and silently produces tests for ambiguous targets. |
| **Analyze** | Walk the codebase, build `CodeSymbol[]` (qualified name, kind, file path, line range, signature, docstring) | Gives the mapper a clean inventory instead of asking the model to re‑read the repo every call. |
| **Map** | Link each `Requirement` → implementing `CodeSymbol` with a confidence score | Hybrid retrieval shortlists candidates first; the agent confirms / rejects. Single‑pass guesses. |
| **Generate** | Produce a `pytest` test per mapping with explicit rationale | Tests are now anchored to a specific requirement id, not "everything in this file". |
| **Critique** | Score each test 1‑5 on relevance / completeness / correctness; revise or reject | Self‑correction quality gate — empirically rejects ~40% of the first‑draft tests. |
| **Trace** | Build the traceability matrix + explicit gap report | The headline deliverable: which requirements are covered, which are not, and why. |

Data flow is **chained nesting** — `TraceOutput` literally contains `CritiqueOutput`, which contains `GenerateOutput`, …, all the way down to `ParseOutput` and `AnalyzeOutput`. Any stage can read any prior result without joins.

---

## 3. End‑to‑End Run Flow (the "how", happy path)

```mermaid
sequenceDiagram
    autonumber
    actor U as User (browser)
    participant FE as Next.js UI
    participant API as Django REST + SSE
    participant DB as SQLite
    participant TH as Daemon thread<br/>(asyncio loop)
    participant ORCH as orchestrator.run_pipeline
    participant ST as Stage (parse, analyze, …)
    participant ACPR as acp_client.runner
    participant AG as External agent<br/>(Claude / Codex / …)
    participant BG as BackgroundTask heartbeat

    U->>FE: Click "Start Run" on Project page
    FE->>API: POST /api/v1/projects/<id>/runs
    API->>DB: INSERT Run (status=pending, config_snapshot=…)
    API->>TH: spawn daemon thread → asyncio.run(run_pipeline)
    API-->>FE: 202 + run_id
    FE->>API: GET /api/v1/runs/<id>/events  (EventSource)
    API-->>FE: stream open (replay from Last-Event-ID seq)

    TH->>BG: register BackgroundTask(kind=run, status=running)
    TH->>ORCH: run_pipeline(run_id, on_event)
    ORCH->>DB: UPDATE Run.status=running, started_at=now
    ORCH-->>API: emit run_started → SSE ring buffer
    API-->>FE: event: run_started

    loop for each of 6 stages in STAGE_ORDER
        ORCH->>DB: INSERT StageExecution(input_payload, status=running)
        ORCH-->>FE: event: stage_started
        ORCH->>ST: stage.execute(StageContext)
        ST->>ACPR: run_acp_prompt(agent, model, strategy, context_mode, prompt)
        ACPR->>AG: spawn subprocess / SDK call
        loop streamed tokens & tool calls
            AG-->>ACPR: session/update / onStep payloads
            ACPR-->>ST: ReasoningChunk(kind=thought|text|tool_call|tool_result|model_message|status)
            ST-->>ORCH: stage_agent_update + stage_reasoning
            ORCH-->>FE: SSE frames (id: seq)
        end
        AG-->>ACPR: terminal message + token_usage
        ACPR-->>ST: acp_result event
        ST->>ST: Pydantic validate output_payload
        ST-->>ORCH: structured output
        ORCH->>DB: UPDATE StageExecution(output_payload, latency_ms, token_usage, status=succeeded)
        ORCH-->>FE: event: stage_completed
    end

    ORCH->>DB: UPDATE Run.status=succeeded, finished_at=now
    ORCH-->>FE: event: run_succeeded
    TH->>BG: mark BackgroundTask succeeded
    FE-->>U: render trace matrix + gap report + per-stage reasoning
```

Key invariants enforced by the orchestrator:

1. Every stage is wrapped in `asyncio.create_task(...)` running **alongside** a `_cancel_watcher` that polls `Run.status` every 1s — so cancellations interrupt the agent subprocess instead of waiting for the next streamed token.
2. After each stage the orchestrator **rolls up** `token_usage` from `acp_result` events using `_merge_token_usage` (sums numeric leaves regardless of whether the agent reports `prompt_tokens`/`completion_tokens` or `input`/`output`/`total`).
3. `BackgroundTask.last_heartbeat` is refreshed roughly every 5s — see §8.

---

## 4. Cancellation Flow

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant FE as Frontend
    participant API as Django view
    participant DB as SQLite (Run row)
    participant ORCH as orchestrator
    participant CW as _cancel_watcher<br/>(parallel asyncio.task)
    participant ST as current stage
    participant ACPR as acp_client.runner
    participant AG as agent subprocess

    U->>FE: Click "Cancel"
    FE->>API: POST /api/v1/runs/<id>/cancel
    API->>DB: UPDATE Run.status = cancelled
    API-->>FE: 200

    Note over ORCH,CW: Both run inside the same event loop
    loop every 1s
        CW->>DB: SELECT Run.status
        DB-->>CW: status
    end
    CW->>CW: detect status == cancelled
    CW->>ST: task.cancel()
    ST->>ACPR: cancellation propagates
    ACPR->>AG: terminate()
    Note over ACPR,AG: 2-second grace period
    ACPR->>AG: kill() if still alive
    ORCH-->>FE: event: run_cancelled (SSE)
    FE-->>U: status flips to "Cancelled"
```

---

## 5. Permission Round‑Trip (interactive mode)

When `Run.config_snapshot["permissions"]` is anything other than `auto`, every tool call the agent wants to make is paused on a future until the user resolves it from the UI.

```mermaid
sequenceDiagram
    autonumber
    participant AG as agent
    participant ACPR as acp_client.permissions
    participant ORCH as orchestrator
    participant FE as Frontend<br/>&lt;PermissionPromptCard&gt;
    actor U as User
    participant API as Django view

    AG->>ACPR: request_permission(tool_call payload)
    ACPR->>ACPR: register asyncio.Future<br/>key = "{run_id}:{prompt_id}"
    ACPR-->>ORCH: emit permission_required<br/>(tool_call payload + prompt_id)
    ORCH-->>FE: SSE event: permission_required
    FE-->>U: render PermissionPromptCard

    Note over FE,API: user clicks Allow / Cancel
    U->>FE: choose outcome
    FE->>API: POST /runs/<id>/permissions/<prompt_id><br/>{outcome: "allowed_once" | "cancelled"}
    API->>ACPR: resolve_permission(future, outcome)
    ACPR-->>AG: response delivered
    AG->>AG: continue (or abort) tool call

    Note over ACPR: timeout = 5 minutes; future rejected if exceeded
```

`auto` mode short‑circuits this and auto‑approves `allow_once` so headless runs never block.

---

## 6. SSE Replay & Reconnect

The frontend never wants to miss a stage event because of a flaky connection.

```mermaid
sequenceDiagram
    participant FE as EventSource (lib/sse.ts)
    participant API as core/views._broadcast
    participant Buf as per-key deque(maxlen=200)<br/>annotated with monotonic seq

    Note over API,Buf: Every emit appends to deque + assigns seq
    FE->>API: GET /runs/<id>/events
    API-->>FE: id: 1<br/>data: {…}
    API-->>FE: id: 2<br/>data: {…}
    Note over FE: connection drops
    FE->>API: reconnect<br/>Last-Event-ID: 2
    API->>Buf: filter seq > 2
    Buf-->>API: [event#3, event#4, …]
    API-->>FE: id: 3, id: 4, …
    Note over FE: lib/sse.ts handles<br/>exp-backoff 1s→16s, 5 attempts<br/>caps in-memory buffer at 500
```

---

## 7. Sweep / Evaluation Flow

A sweep is "run the same project N times, vary the configuration, do statistics on it".

```mermaid
flowchart TB
    User([User on /projects/&lt;id&gt;/sweep]) --> Builder["AgentModelMatrixBuilder<br/>(multi-row picker)"]
    Builder -->|axes payload| Preview["POST /projects/&lt;id&gt;/sweeps/preview"]
    Preview --> Cells["flat matrix:<br/>(agent_id, model_id,<br/>prompt_strategy, context_mode)"]
    Cells -->|user confirms| Create["POST /projects/&lt;id&gt;/sweeps"]
    Create --> SweepRow[("Sweep row<br/>matrix=[…]<br/>status=running")]
    Create --> SweepThread["daemon thread<br/>eval/runner.run_sweep"]

    SweepThread --> Loop{for each cell}
    Loop -->|spawn child Run| ChildRun["new Run<br/>config_snapshot=cell"]
    ChildRun --> RunPipeline["orchestrator.run_pipeline<br/>(see §3)"]
    RunPipeline --> Metrics["eval/metrics.compute_metrics<br/>quality / traceability /<br/>latency / tokens"]
    Metrics --> Loop
    Loop -->|all cells done| Stats["eval/stats.run_statistical_analysis<br/>ANOVA on 3 axes:<br/>strategy / context / (agent,model)<br/>+ Bonferroni pairwise t-tests"]
    Stats --> Diff["eval/stats.compute_baseline_diff<br/>'lift vs worst configuration'<br/>(sign-corrected)"]
    Diff --> Persist[("Sweep:<br/>metrics_summary,<br/>baseline_summary,<br/>stats_report.markdown")]
    Persist --> SweepUI["frontend renders:<br/>- ranked metrics table<br/>- Lift vs Worst card<br/>- ANOVA markdown"]
```

> The legacy 4×4 = 16‑cell `prompt_strategy × context_mode` grid still works; the multi‑provider expansion adds the `axes` payload and turns the matrix into N‑D.

---

## 8. Background Task Supervision (the "no Celery" story)

Daemon threads have no external supervisor, so the app has to reap its own corpses.

```mermaid
stateDiagram-v2
    [*] --> Pending : Run / Sweep created
    Pending --> Running : daemon thread starts<br/>BackgroundTask row inserted

    state "Running" as Running {
        [*] --> Heartbeating
        Heartbeating --> Heartbeating : every ~5s<br/>refresh last_heartbeat
    }

    Running --> Succeeded : pipeline finishes
    Running --> Failed : exception
    Running --> Cancelled : user POST /cancel<br/>watcher detects flip

    Running --> Stale : process restart<br/>heartbeat &gt; 5 min old
    Stale --> Failed : core.apps.CoreConfig.ready()<br/>reap_stale_background_tasks()<br/>flips Run/Sweep to failed

    note right of Stale
      Reaper deliberately skips:
      - migrate / makemigrations / collectstatic
      - pytest harness
      Only fires for runserver and other
      long-running processes.
    end note
```

A live `GET /api/v1/background-tasks` is polled every 5s by the sidebar so users always see what is in flight.

---

## 9. Frontend Architecture & Page Map

```mermaid
flowchart TB
    Layout["app/layout.tsx<br/>+ providers.tsx (TanStack Query)"]
    Layout --> Side["AppSidebar<br/>+ Background Tasks badge"]
    Layout --> Pages

    subgraph Pages["app/* routes"]
      Home["/<br/>page.tsx<br/>Dashboard:<br/>recent runs + project list"]
      ProjNew["/projects/new<br/>create project<br/>(code_path + requirements_path)"]
      ProjDetail["/projects/[id]<br/>tabs:<br/>Overview / Agents / Runs / Sweep"]
      RunPage["/projects/[id]/runs/[runId]<br/>vertical accordion of 6 stages<br/>+ &lt;ReasoningStream&gt; per stage"]
      SweepPage["/projects/[id]/sweep<br/>&lt;AgentModelMatrixBuilder&gt;<br/>+ live mirrored reasoning<br/>+ Lift vs Worst card"]
      AgentsSettings["/settings/agents<br/>Agent Registry: PATH +<br/>env vars status per agent"]
    end

    Side -.-> Home
    Side -.-> ProjDetail
    Side -.-> AgentsSettings

    subgraph Hooks["src/hooks + src/lib"]
      Api["lib/api.ts<br/>(REST client)"]
      Sse["lib/sse.ts<br/>(EventSource w/ replay,<br/>exp-backoff 1→16s,<br/>buffer cap 500)"]
    end

    Pages -->|TanStack Query| Api
    RunPage --> Sse
    SweepPage --> Sse
```

Notable React building blocks:

| Component | Role |
|---|---|
| `<ReasoningStream>` | Auto‑scrolling, copy‑per‑chunk, typing‑cursor renderer for the normalized reasoning timeline. |
| `<AgentModelPicker>` | Combobox driven by `AgentSpec.model_groups` so users can pick a model per stage. |
| `<AgentModelMatrixBuilder>` | Multi‑row matrix UI for sweeps; rows turn into the `axes` payload sent to `/sweeps/preview`. |
| `<PermissionPromptCard>` | Renders a `permission_required` SSE payload and POSTs the user's outcome. |
| `<StatusBadge>` | Single source of truth for `pending / running / succeeded / failed / cancelled` styling. |
| `motion.tsx` | Shared Framer Motion presets (`fadeInUp`, `springSmooth`, `StaggerList`) so animations stay consistent. |

---

## 10. ACP / Cursor SDK Bridge — How Stages Talk to Agents

```mermaid
flowchart LR
    Stage["pipeline/stages/&lt;name&gt;.py"] --> Build["build_prompt(strategy, context_mode)<br/>→ pipeline/prompts.py<br/>→ pipeline/context_modes.py"]
    Build --> Runner["acp_client/runner.run_acp_prompt"]
    Runner --> Pick{AgentSpec.runner}

    Pick -->|"acp"| Spawn["subprocess.spawn(<br/>command + args from registry)"]
    Pick -->|"cursor-sdk"| SDK["Node bridge:<br/>backend/acp_client/cursor_sdk<br/>(npm-installed, talks to Composer 2)"]

    Spawn --> JSONRPC["ACP JSON-RPC over stdio<br/>session/update events"]
    SDK --> CursorAPI["Cursor SDK Composer 2 API<br/>onStep callback"]

    JSONRPC --> Norm["acp_client/runner._normalize<br/>→ ReasoningChunk"]
    CursorAPI --> Norm
    Norm --> StageOut["yield to stage:<br/>thought / text / tool_call /<br/>tool_result / model_message / status"]

    Runner -.->|on tool perm request| Perm["acp_client/permissions.handle_permission_request<br/>(see §5)"]

    Note["AgentSpec lives in acp_client/registry.py.<br/>Agents currently registered:<br/>claude-code, codex, cursor, cursor-sdk-composer-2,<br/>gemini, opencode, kiro, blackbox, qwen-coder."]
    Pick -.-> Note
```

Each stage gets a uniform contract:

```python
async for chunk in run_acp_prompt(agent_id, model_id, prompt, ...):
    # chunk: ReasoningChunk(kind, content, metadata, ts)
    ...
# trailing acp_result event carries final token_usage
```

When the ACP SDK is missing entirely the runner returns **mock responses** so the UI still works — see Decision D‑003.

---

## 11. Hybrid Retrieval (Map stage helper)

```mermaid
flowchart LR
    Req["Requirement.description<br/>(query string)"] --> Tok["tokenize"]
    Tok --> FAISS["FAISS dense search<br/>sentence-transformers<br/>all-MiniLM-L6-v2 (23 MB, CPU)"]
    Tok --> BM25["BM25 sparse search<br/>(rank_bm25)"]
    FAISS --> Score["score_dense (0..1)"]
    BM25 --> ScoreS["score_sparse (0..1)"]
    Score --> Mix
    ScoreS --> Mix
    Mix["α · dense + (1-α) · sparse<br/>α = 0.6"] --> TopK["top-K candidates"]
    TopK --> Inject["inject as 'retrieval hints'<br/>into Map prompt<br/>(only for context_mode ∈ {local, module, full})"]

    classDef ret fill:#0f172a,stroke:#22d3ee,color:#e0f2fe;
    class FAISS,BM25,Mix,TopK ret;
```

Verified by tests (14 retrieval tests, 100% pass): 100% precision@3 across all 3 benchmark projects (calculator, url‑shortener, todo‑api).

---

## 12. Database Schema

```mermaid
erDiagram
    Project ||--o{ AgentConfig : has
    Project ||--o{ Run : has
    Project ||--o{ Sweep : has
    Run ||--o{ StageExecution : has
    Sweep }o--o{ Run : "spawns / contains"
    BackgroundTask ||..|| Run : "kind=run, related_id"
    BackgroundTask ||..|| Sweep : "kind=sweep, related_id"

    Project {
        uuid id PK
        string name
        string code_path
        string requirements_path
        string test_framework
        string language
    }
    AgentConfig {
        uuid id PK
        uuid project_id FK
        string stage "parse|analyze|map|generate|critique|trace"
        string agent_id
        string model_id
        string prompt_strategy "zero_shot|chain_of_thought|few_shot_static|few_shot_dynamic"
        string context_mode "minimal|local|module|full"
        bool enabled
    }
    Run {
        uuid id PK
        uuid project_id FK
        string status "pending|running|succeeded|failed|cancelled"
        json config_snapshot
        datetime started_at
        datetime finished_at
        string artifacts_path
    }
    StageExecution {
        uuid id PK
        uuid run_id FK
        string stage
        string agent_id
        string model_id
        string status
        json input_payload
        json output_payload
        json raw_updates "faithful ACP/SDK audit trail"
        json reasoning "normalized ReasoningChunk[]"
        json token_usage
        int latency_ms
        text error
    }
    Sweep {
        uuid id PK
        uuid project_id FK
        json matrix "list of cells"
        string status
        json metrics_summary
        json stats_report "ANOVA + pairwise t-tests"
        json baseline_summary "lift vs worst configuration"
    }
    BackgroundTask {
        uuid id PK
        string kind "run|sweep"
        string related_id
        string status
        datetime last_heartbeat
        int pid
    }
```

> Every `BaseModel` carries `id` (UUID4), `created_at`, `updated_at`. UUIDs everywhere so multiple instances can merge data without sequential‑id collisions.

---

## 13. Public REST + SSE Surface

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/agents` | List all agents (with PATH + env‑var status) |
| `GET` | `/api/v1/agents/<agent_id>/models` | List the model catalog for one agent |
| `GET` / `POST` | `/api/v1/projects` | List / create projects |
| `GET` | `/api/v1/projects/<id>` | Project detail |
| `PUT` | `/api/v1/projects/<id>/agents` | Bulk update per‑stage `AgentConfig` |
| `POST` | `/api/v1/projects/<id>/runs` | Start a new pipeline run |
| `POST` | `/api/v1/projects/<id>/sweeps/preview` | Preview the flattened matrix |
| `POST` | `/api/v1/projects/<id>/sweeps` | Start a sweep |
| `GET` | `/api/v1/runs` | Recent runs across all projects |
| `GET` | `/api/v1/runs/<id>` | Run detail incl. all stage executions |
| `GET` | `/api/v1/runs/<id>/events` | **SSE** stream (replay via `Last-Event-ID`) |
| `GET` | `/api/v1/runs/<id>/artifacts/<name>` | Serve a stage output artifact file |
| `POST` | `/api/v1/runs/<id>/cancel` | Cancel a running pipeline |
| `POST` | `/api/v1/runs/<id>/permissions/<prompt_id>` | Resolve a permission prompt |
| `GET` | `/api/v1/sweeps/<id>` | Sweep detail (runs + stats) |
| `POST` | `/api/v1/sweeps/<id>/cancel` | Cancel a sweep |
| `GET` | `/api/v1/sweeps/<id>/events` | **SSE** stream for sweep progress |
| `GET` | `/api/v1/fs/validate` | Check filesystem path exists |
| `GET` | `/api/v1/background-tasks` | Heartbeat snapshot for the sidebar |

---

## 14. Configuration Matrix (the 16‑cell sweep)

```mermaid
flowchart LR
    subgraph Strategies["4 prompt strategies"]
      S1[zero_shot]
      S2[chain_of_thought]
      S3[few_shot_static]
      S4[few_shot_dynamic]
    end
    subgraph Modes["4 context modes"]
      M1["minimal<br/>req + target only"]
      M2["local<br/>+ same-file siblings"]
      M3["module<br/>+ full module source"]
      M4["full<br/>+ project summary"]
    end
    Strategies --> Cross{Cartesian product}
    Modes --> Cross
    Cross -->|"4 × 4 = 16 cells"| Eval[per-project sweep]
    Eval --> Best["Best (per published results):<br/>few_shot_dynamic + full<br/>≈ 87% traceability,<br/>84% accept rate"]
    Eval --> Worst["Worst:<br/>zero_shot + minimal<br/>≈ 52% traceability"]
```

Multi‑provider expansion adds two more axes (`agent_id`, `model_id`) so the actual sweep matrix is `agents × models × strategies × modes`.

---

## 15. Repository Layout (where to look for what)

```text
shiny-invention-main/
├── README.md                     # install + run instructions
├── AGENTS.md                     # cloud / agent-friendly notes
├── Makefile                      # install / dev-* / migrate / seed / sweep / test / lint
├── docker-compose.yml
├── .env.example                  # CURSOR_API_KEY / ANTHROPIC_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY / CODEX_API_KEY
│
├── backend/                      # Django 5.x, managed by `uv`
│   ├── manage.py
│   ├── pick_free_port.py         # auto-bumps from 8000 → 8009 if busy
│   ├── pyproject.toml
│   │
│   ├── reqlens/                  # Django project (settings, root urls, asgi, wsgi)
│   ├── core/                     # Models, REST views, SSE, admin, BackgroundTask supervisor
│   │   ├── models.py             # Project / AgentConfig / Run / StageExecution / Sweep / BackgroundTask
│   │   ├── views.py              # REST + SSE + ring buffer (deque maxlen=200) + Last-Event-ID replay
│   │   ├── apps.py               # CoreConfig.ready() → reap_stale_background_tasks
│   │   ├── background.py         # heartbeat helpers
│   │   ├── serializers.py
│   │   ├── urls.py               # routes listed in §13
│   │   └── management/commands/  # seed_benchmark, run_sweep
│   │
│   ├── pipeline/
│   │   ├── orchestrator.py       # run_pipeline: cancel watcher, token rollup, SSE emit
│   │   ├── contracts.py          # Pydantic v2 strict + extra="forbid" models
│   │   ├── prompts.py            # 4 strategies × 6 stages = 24 templates
│   │   ├── context_modes.py      # minimal / local / module / full builders
│   │   ├── retrieval.py          # FAISS + BM25 hybrid (α=0.6)
│   │   └── stages/
│   │       ├── base.py           # StageContext, StageEvent, common runner
│   │       ├── parse.py
│   │       ├── analyze.py
│   │       ├── map_stage.py
│   │       ├── generate.py
│   │       ├── critique.py
│   │       └── trace.py
│   │
│   ├── acp_client/
│   │   ├── registry.py           # AgentSpec catalog (9 agents)
│   │   ├── runner.py             # run_acp_prompt + ReasoningChunk normalization
│   │   ├── permissions.py        # asyncio.Future-based round trip
│   │   └── cursor_sdk/           # Node bridge → Cursor SDK Composer 2 (npm install)
│   │
│   ├── eval/
│   │   ├── metrics.py            # compute_metrics, rank_metrics
│   │   ├── stats.py              # ANOVA, Bonferroni pairwise t-tests, compute_baseline_diff, generate_markdown_report
│   │   └── runner.py             # run_sweep
│   │
│   └── tests/                    # 85 tests, 100% pass
│
├── frontend/                     # Next.js 16 (App Router) + React 19 + Tailwind v4 + shadcn/ui v4
│   ├── package.json              # pnpm 9 via Corepack
│   └── src/
│       ├── app/                  # routes — see §9 page map
│       ├── components/           # ReasoningStream, AgentModelPicker, StatusBadge, motion, …
│       ├── components/ui/        # shadcn primitives
│       ├── hooks/
│       └── lib/                  # api.ts (REST), sse.ts (EventSource w/ replay)
│
├── docs/
│   ├── ARCHITECTURE.md           # canonical architecture write-up
│   ├── DECISIONS.md              # D-001..D-004
│   ├── slides.md                 # IS 698 presentation deck
│   ├── generate_charts.py
│   └── figures/                  # rendered PNGs (architecture, pipeline_flow, eval matrices, …)
│
└── benchmark/                    # seed projects: calculator, url-shortener, todo-api
```

---

## 16. Key Decisions (from `docs/DECISIONS.md`)

| ID | Decision | Why |
|---|---|---|
| **D‑001** | SQLite for MVP | Postgres‑ready via Django settings, but SQLite is enough for MVP and zero‑setup. |
| **D‑002** | No Celery | Daemon threads + `asyncio.run()` keep the surface tiny; `BackgroundTask` heartbeat covers the supervisor gap. |
| **D‑003** | ACP mock fallback | When the ACP SDK or an agent CLI is missing, the runner returns mock responses so the UI is fully functional for config / development without API keys. |
| **D‑004** | Default permissions = `auto` | Interactive permission round‑trip is fully wired (see §5) but defaults to auto‑approve for headless dev runs. |

---

## 17. Why Each Big Choice Pays Off

- **Pydantic strict contracts** — a malformed agent reply fails *at the boundary* with a precise error, not three stages later as a `KeyError` on a missing field. Empirically caught dozens of agent regressions.
- **Per‑stage `StageExecution` row + `raw_updates` audit log** — every run is fully reconstructible. Useful for debugging, retro evals, and showing reviewers exactly what the agent said.
- **ACP as the only LLM seam** — swapping Claude → Codex → Gemini is a config change, not a code change. The Cursor SDK Composer 2 bridge plugs in the same way.
- **SSE ring buffer + `Last-Event-ID`** — flaky networks no longer mean lost stage events; the run page just resumes.
- **Heartbeat reaper** — process restarts no longer leave runs spinning forever.
- **Sweep with sign‑corrected lift** — positive numbers always mean "better than baseline" (lower latency reads as positive lift), so the UI is unambiguous.
- **Hybrid retrieval (FAISS + BM25)** — dense embeddings find paraphrased intent, sparse BM25 catches exact identifiers. The α=0.6 mix gets 100% precision@3 on the benchmark suite.

---

## 18. TL;DR

- **What:** a 6‑stage typed pipeline (`parse → analyze → map → generate → critique → trace`) that turns a requirements doc + a codebase into a traceability matrix and gap report.
- **Why:** existing AI test generators do not link tests to requirements; ReqLens makes that link the headline deliverable and proves it with statistics.
- **How:** Django backend orchestrates the pipeline in a daemon thread; each stage delegates to an external coding agent over ACP (or the Cursor SDK Composer 2 bridge); Next.js frontend streams every thought, tool call, and reasoning chunk live over SSE with replay; sweeps benchmark configurations with ANOVA + Bonferroni pairwise t‑tests + lift‑vs‑worst deltas.
