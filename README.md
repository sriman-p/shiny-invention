# ReqLens

ReqLens is a local web application for requirement-traced test generation.

In simple terms: you give ReqLens a requirements document and a code folder. ReqLens walks through a six-stage AI-assisted workflow, then shows which requirements are covered by generated tests, which are partially covered, and which still have gaps.

This README is written so that someone who does not normally code can still run the application locally and understand what they are seeing.

## What ReqLens Does

ReqLens is built around one main idea: generated tests are more useful when they are connected back to requirements.

The application:

- Reads a requirements document.
- Reads a source-code folder.
- Breaks the work into six stages: Parse, Analyze, Map, Generate, Critique, and Trace.
- Uses structured stage outputs so results can be inspected.
- Stores project, run, stage, and artifact information in a local SQLite database.
- Shows progress and results in a browser.
- Produces traceability evidence, not just raw test code.

## What Is Included

```text
backend/        Django backend, REST API, pipeline orchestration, database models
frontend/       Next.js frontend, browser UI, run monitoring, result views
benchmark/      Small demo projects: calculator, url-shortener, todo-api
README.md       This setup and usage guide
.env.example    Safe example environment file
Makefile        Easy commands such as make setup and make dev-backend
```

## Technology Used

You do not need to understand these tools to run the app, but this helps explain what is inside the project.

| Area | Tools |
| --- | --- |
| Backend | Django, Django REST Framework |
| Frontend | Next.js, React, TypeScript, shadcn/ui |
| Database | SQLite, stored locally in `backend/data/reqlens.db` |
| AI agent interface | ACP, Agent Client Protocol |
| Validation | Pydantic contracts |
| Retrieval | FAISS dense retrieval and BM25 keyword retrieval |
| Tests | pytest for backend, Vitest for frontend |
| Package managers | `uv` for Python, Corepack-managed `pnpm` for frontend |

## Quickest Way To Run It

These are the main steps:

1. Install the required tools.
2. Download or clone the repository.
3. Copy `.env.example` to `.env`.
4. Run `make setup`.
5. Start the backend.
6. Start the frontend.
7. Open the browser at `http://localhost:3000`.

The detailed instructions below explain each step.

## Step 1: Install Required Tools

ReqLens needs:

- Git
- `make`
- Python 3.11 or newer
- `uv`
- Node.js 20.9 or newer. Node.js 22 is recommended.
- Corepack, included with Node

### macOS

If Homebrew is installed, run:

```bash
brew install git uv node@22
```

Then check the versions:

```bash
git --version
make --version
python3 --version
uv --version
node --version
```

If `node --version` still shows an older Node version after installing `node@22`, run:

```bash
export PATH="/opt/homebrew/opt/node@22/bin:$PATH"
node --version
```

### Windows

The easiest Windows path is WSL with Ubuntu. Open Ubuntu/WSL, then install the same tools there. ReqLens uses `make` commands and Unix-style paths, so WSL is recommended over plain Command Prompt.

## Step 2: Download The Project

If you are viewing this project on GitHub:

1. Click the green `Code` button.
2. Copy the repository URL.
3. Run the command below, replacing `<repository-url>` with that URL.

```bash
git clone <repository-url>
cd reqlens
```

If your folder has a different name, move into that folder instead:

```bash
cd /path/to/the/project-folder
```

You are in the correct folder if this command lists `backend`, `frontend`, and `Makefile`:

```bash
ls
```

## Step 3: Create The Local Environment File

ReqLens includes a safe example file named `.env.example`. Copy it to `.env`:

```bash
test -f .env || cp .env.example .env
```

For basic local setup, seeded projects, and UI inspection, you can leave `.env` exactly as it is.

For full AI-backed pipeline runs, add at least one AI provider key or local agent login. See [AI Agent Setup](#ai-agent-setup).

## Step 4: Install Dependencies And Seed Demo Data

Run:

```bash
make setup
```

This command does three things:

```bash
make install
make migrate
make seed
```

What those mean:

- `make install` installs Python and frontend dependencies.
- `make migrate` creates the local SQLite database.
- `make seed` adds three example projects to the database.

The seeded example projects are:

| Project | What it demonstrates |
| --- | --- |
| `calculator` | arithmetic requirements and edge cases |
| `url-shortener` | URL creation, resolving, and validation |
| `todo-api` | create, list, complete, and delete behavior |

If `make setup` finishes without errors, the local application is installed.

## Step 5: Start The Backend

Open a terminal window in the project folder and run:

```bash
make dev-backend
```

The backend is the Django API. It normally starts at:

```text
http://localhost:8000
```

Leave this terminal running.

If port `8000` is busy, the backend automatically chooses another nearby port, such as `8001`. The terminal output will show the chosen port.

## Step 6: Start The Frontend

Open a second terminal window in the same project folder and run:

```bash
make dev-frontend
```

The frontend is the browser application. It normally starts at:

```text
http://localhost:3000
```

Leave this terminal running too.

If the backend used a port other than `8000`, start the frontend with the matching backend URL. For example, if the backend printed port `8001`, run:

```bash
cd frontend
corepack enable
NEXT_PUBLIC_API_BASE_URL=http://localhost:8001/api/v1 pnpm dev
```

## Step 7: Open The App

Open a web browser and go to:

```text
http://localhost:3000
```

You should see the ReqLens dashboard. After `make seed`, the dashboard should show the sample projects.

## First Demo Walkthrough

This is the easiest way to verify that the app is running.

1. Open `http://localhost:3000`.
2. Look for the seeded projects: `calculator`, `url-shortener`, and `todo-api`.
3. Click `calculator`.
4. Open the `Overview` tab and confirm it shows:
   - code directory
   - requirements document
   - language
   - test framework
5. Open the `Agents` tab.
6. Review the six stages:
   - Parse
   - Analyze
   - Map
   - Generate
   - Critique
   - Trace
7. Open the Agent Registry page from the sidebar/settings area to see which AI agents are available on the machine.

If no AI agents are configured, that is okay for basic UI review. The professor can still confirm that the app installs, opens, seeds projects, displays configuration, and shows the intended workflow.

## AI Agent Setup

ReqLens can display the UI and seeded projects without AI keys.

To run the full AI-backed pipeline, at least one supported AI agent must be installed or authenticated. The backend reads keys from the root `.env` file.

Open `.env` and fill in only the key or keys you want to use:

```bash
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
CURSOR_API_KEY=
GEMINI_API_KEY=
BLACKBOX_API_KEY=
```

What each key is for:

| Variable | Used for |
| --- | --- |
| `ANTHROPIC_API_KEY` | Claude Code style agent access |
| `OPENAI_API_KEY` | OpenAI/Codex-compatible agent access |
| `CURSOR_API_KEY` | Cursor SDK Composer 2 bridge and optional Cursor Agent auth |
| `GEMINI_API_KEY` | Gemini CLI agent access |
| `BLACKBOX_API_KEY` | Blackbox CLI agent access |

The app has an Agent Registry page that checks:

- whether the required command exists on the machine
- whether the required environment variables are set
- which models are available or configured

If agents appear as `Missing`, the local UI can still be reviewed, but live AI pipeline stages may fail until agent credentials or CLI tools are configured.

## Running A Pipeline

After an AI agent is configured:

1. Open `http://localhost:3000`.
2. Click a project, such as `calculator`.
3. Open the `Agents` tab.
4. Choose an available agent and model for each stage.
5. Keep a simple first-run configuration, such as:
   - prompt strategy: `zero_shot`
   - context mode: `full`
6. Click `Save config`.
7. Click `Run pipeline`.
8. Watch the run page as stages complete.
9. Review the final traceability matrix and gap report.

The generated tests are stored as run artifacts for inspection. ReqLens does not silently rewrite the source project.

## What The Six Stages Mean

| Stage | What it does | Why it matters |
| --- | --- | --- |
| Parse | Reads the requirements document and extracts structured requirements | Creates stable requirement IDs and acceptance criteria |
| Analyze | Reads the code folder and inventories symbols | Finds functions, classes, files, and signatures |
| Map | Links requirements to implementation symbols | Connects natural-language requirements to code |
| Generate | Creates pytest-style tests for mapped requirements | Produces tests tied to requirement IDs |
| Critique | Scores generated tests for relevance, completeness, and correctness | Prevents weak tests from being counted blindly |
| Trace | Builds the final traceability matrix and gap report | Shows covered, partial, and uncovered requirements |

## Creating A New Project In The UI

ReqLens needs two paths:

- Code directory: the folder containing the project code.
- Requirements document: a Markdown file, usually named `requirements.md`.

Example project layout:

```text
my-project/
  requirements.md
  src/
    calculator.py
  tests/
    test_calculator.py
```

Example `requirements.md`:

```md
# Requirements

## REQ-001 Add two numbers

The calculator must return the sum of two numeric inputs.

Acceptance criteria:
- Given 2 and 3, the result is 5.
- Given -1 and 1, the result is 0.

## REQ-002 Reject division by zero

The calculator must raise an error when division is attempted with a zero divisor.

Acceptance criteria:
- Dividing any number by 0 raises ZeroDivisionError.
```

To create the project:

1. Click `New Project`.
2. Enter a project name.
3. Paste the absolute path to the code directory.
4. Paste the absolute path to the requirements file.
5. Click `Create project`.

To find an absolute path:

```bash
cd /path/to/my-project
pwd
```

For a seeded calculator example inside this repository, the paths look like this:

```text
/path/to/reqlens/benchmark/projects/calculator
/path/to/reqlens/benchmark/projects/calculator/requirements.md
```

Replace `/path/to/reqlens` with the actual folder path on your computer.

## Optional API Examples

Most users should use the browser UI. These command-line examples are included only for verification.

List projects:

```bash
curl http://localhost:8000/api/v1/projects
```

Create a project:

```bash
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "calculator-from-api",
    "code_path": "/path/to/reqlens/benchmark/projects/calculator",
    "requirements_path": "/path/to/reqlens/benchmark/projects/calculator/requirements.md",
    "language": "python",
    "test_framework": "pytest"
  }'
```

Start a run after replacing `<PROJECT_ID>`:

```bash
curl -X POST http://localhost:8000/api/v1/projects/<PROJECT_ID>/runs \
  -H "Content-Type: application/json" \
  -d '{}'
```

View a run after replacing `<RUN_ID>`:

```bash
curl http://localhost:8000/api/v1/runs/<RUN_ID>
```

Cancel a run:

```bash
curl -X POST http://localhost:8000/api/v1/runs/<RUN_ID>/cancel \
  -H "Content-Type: application/json" \
  -d '{}'
```

## Common Commands

Run these from the project root.

```bash
make help          # Show available commands
make setup         # Install dependencies, migrate database, seed demo projects
make install       # Install backend and frontend dependencies only
make migrate       # Create/update the SQLite database
make seed          # Add/update demo projects
make dev-backend   # Start Django API server
make dev-frontend  # Start Next.js frontend server
make run           # Start backend and frontend together
make test          # Run backend pytest and frontend tests
make lint          # Run backend and frontend linters
make build         # Build the frontend for production
```

For non-coders, the most important commands are:

```bash
make setup
make dev-backend
make dev-frontend
```

## Troubleshooting

### `uv: command not found`

Install `uv`:

```bash
brew install uv
```

Then rerun:

```bash
make setup
```

### `node` is too old

Install Node 22:

```bash
brew install node@22
export PATH="/opt/homebrew/opt/node@22/bin:$PATH"
node --version
```

Then rerun:

```bash
make setup
```

### The frontend cannot connect to the backend

Make sure the backend terminal is still running:

```bash
make dev-backend
```

If the backend is not on port `8000`, start the frontend with the printed backend port:

```bash
cd frontend
corepack enable
NEXT_PUBLIC_API_BASE_URL=http://localhost:8001/api/v1 pnpm dev
```

Replace `8001` with the actual backend port.

### The database looks empty

Run:

```bash
make migrate
make seed
```

Refresh the browser after seeding.

### Agents show as missing

This usually means the external AI agent CLI or API key is not configured. The app can still be reviewed for setup, UI, project creation, seeded examples, and configuration. Full AI pipeline execution needs at least one configured agent.

### `pnpm` does not work

Use Corepack from inside the frontend folder:

```bash
cd frontend
corepack enable
pnpm install
```

### Stop the app

In each terminal running a server, press:

```text
Control + C
```

## What Files Are Created Locally

These files/folders are created during setup and are not meant to be committed:

```text
backend/.venv/              Python virtual environment
frontend/node_modules/      Frontend dependencies
backend/data/reqlens.db     Local SQLite database
backend/data/reqlens.log    Local backend log file
backend/data/runs/          Saved run artifacts
```

## Validate The Installation

After setup, run:

```bash
make test
make lint
```

Build the frontend:

```bash
make build
```

These commands are useful for grading or final verification, but the basic app can be reviewed by running the backend and frontend and opening `http://localhost:3000`.

## Grading Checklist

Use this checklist to verify the local app:

- [ ] `make setup` completes.
- [ ] `make dev-backend` starts the backend.
- [ ] `make dev-frontend` starts the frontend.
- [ ] `http://localhost:3000` opens.
- [ ] Seeded projects appear on the dashboard.
- [ ] A project page opens.
- [ ] The `Agents` tab shows six pipeline stages.
- [ ] The Agent Registry page shows agent availability.
- [ ] If an AI agent is configured, a pipeline run can be started.
- [ ] Run artifacts, traceability output, and gap information can be inspected after a run.
