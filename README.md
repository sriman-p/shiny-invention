# ReqLens

ReqLens helps you turn a requirements document into generated tests that are linked back to the exact requirements they check.

In plain English: you give ReqLens a folder of code and a `requirements.md` file. ReqLens reads both, asks an AI coding agent to work through six focused steps, and gives you a traceability matrix showing which requirements are covered, partially covered, or still missing tests.

ReqLens is a local web application:

- Backend: Django API on `http://localhost:8000`
- Frontend: Next.js web app on `http://localhost:3000`
- Database: local SQLite file at `backend/data/reqlens.db`
- AI agent calls: routed through ACP, the Agent Client Protocol

You do not need to understand Django, Next.js, or ACP to run the app. Most tasks use the `make` commands below.

## Quick Start

Open Terminal, go to the project folder, and run these commands.

```bash
git clone <repository-url>
cd reqlens
test -f .env || cp .env.example .env
make setup
```

Start the backend in one Terminal window:

```bash
make dev-backend
```

Start the frontend in a second Terminal window:

```bash
make dev-frontend
```

Open the app:

```text
http://localhost:3000
```

The seeded example projects are `calculator`, `url-shortener`, and `todo-api`.

## What You Need Installed

Check whether the required tools are already installed:

```bash
git --version
make --version
python3 --version
uv --version
node --version
```

Recommended versions:

- Python 3.11 or newer
- Node.js 20.9 or newer. Node.js 22 is recommended.
- `uv` for Python dependencies
- Corepack, included with Node, for the pinned frontend `pnpm`

On macOS with Homebrew, install the main tools with:

```bash
brew install git uv node@22
```

If `node --version` still shows an old version after installing `node@22`, run:

```bash
export PATH="/opt/homebrew/opt/node@22/bin:$PATH"
node --version
```

## Get The Code

If you do not already have this folder, clone it:

```bash
git clone <repository-url>
cd reqlens
```

If you already downloaded or unzipped the project, just move into that folder:

```bash
cd /path/to/reqlens
```

## Configure The App

Create your local environment file:

```bash
test -f .env || cp .env.example .env
```

For browsing the UI, creating projects, and viewing seeded data, the default `.env` values are enough.

To run real AI-backed pipeline stages, add the key or login method for the agent you want to use. Open `.env` and fill in only the keys you need:

```bash
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
CURSOR_API_KEY=
GEMINI_API_KEY=
BLACKBOX_API_KEY=
```

The Agent Registry page in the app shows which agents are ready.

## Install And Prepare Data

The easiest setup command is:

```bash
make setup
```

That command does three things:

```bash
make install
make migrate
make seed
```

What those mean:

- `make install` installs backend and frontend dependencies.
- `make migrate` creates or updates the local database.
- `make seed` adds the example projects.

You can safely run `make seed` more than once.

## Run The App

Use two Terminal windows so the logs are easier to read.

Terminal 1:

```bash
make dev-backend
```

Terminal 2:

```bash
make dev-frontend
```

Then open:

```text
http://localhost:3000
```

The backend normally uses port `8000`. If that port is busy, the backend picks the next free port and prints it, such as `8001`. If that happens, start the frontend with the matching backend URL:

```bash
cd frontend
corepack enable
NEXT_PUBLIC_API_BASE_URL=http://localhost:8001/api/v1 pnpm dev
```

Replace `8001` with the port printed by the backend.

## First Walkthrough In The Web App

1. Open `http://localhost:3000`.
2. Click one of the seeded projects, such as `calculator`.
3. Open the `Agents` tab.
4. Pick an available agent and model for each stage, or keep the defaults if your Codex setup is ready.
5. Click `Save config` if you changed anything.
6. Click `Run pipeline`.
7. Watch the run page as ReqLens moves through the six stages.
8. Review the final trace matrix and gap report.

ReqLens does not silently rewrite your source code. Generated tests and stage outputs are stored as run artifacts so you can inspect them first.

## Creating Your Own Project

ReqLens needs two paths:

- Code directory: the folder that contains your project code.
- Requirements document: a Markdown file, usually named `requirements.md`.

Example folder layout:

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

To create the project in the UI:

1. Click `New Project`.
2. Enter a project name.
3. Paste the absolute path to your code directory.
4. Paste the absolute path to your requirements file.
5. Click `Create project`.

To find an absolute path on macOS or Linux:

```bash
cd /path/to/my-project
pwd
```

If the project is inside this repository, a seeded calculator example uses paths like:

```text
/path/to/reqlens/benchmark/projects/calculator
/path/to/reqlens/benchmark/projects/calculator/requirements.md
```

## What The Six Stages Mean

| Stage | What it does | Output you should expect |
| --- | --- | --- |
| Parse | Reads the requirements document | Structured requirement IDs, descriptions, and acceptance criteria |
| Analyze | Reads the code directory | Functions, classes, files, and symbols found in the code |
| Map | Connects requirements to code | Requirement-to-symbol mappings with confidence and evidence |
| Generate | Writes candidate tests | Pytest-style test code tied to requirement IDs |
| Critique | Reviews generated tests | Scores, accept/revise/reject decisions, and possible revisions |
| Trace | Builds the final evidence view | Traceability matrix and gap report |

## Using The API With Code

You can also use ReqLens from the command line while the backend is running.

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

Start a run after replacing `<PROJECT_ID>` with a real project ID:

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

```bash
make help          # Show available commands
make setup         # Install dependencies, migrate database, seed examples
make install       # Install backend and frontend dependencies only
make migrate       # Apply database migrations
make seed          # Add or update benchmark projects
make dev-backend   # Start Django API server
make dev-frontend  # Start Next.js frontend server
make run           # Start backend and frontend together
make test          # Run backend pytest and frontend tests
make lint          # Run backend and frontend linters
make build         # Build the frontend for production
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

Then rerun frontend setup:

```bash
cd frontend
corepack enable
pnpm install
```

### The frontend cannot reach the backend

Make sure the backend is running:

```bash
make dev-backend
```

If the backend printed a port other than `8000`, start the frontend with that port:

```bash
cd frontend
NEXT_PUBLIC_API_BASE_URL=http://localhost:8001/api/v1 pnpm dev
```

### Agents show as missing

This is expected if the external agent CLI tools or API keys are not configured yet. The app can still be used for project setup and UI work. To run the full AI pipeline, configure at least one supported agent and check `Settings -> Agent Registry`.

### The database looks empty

Run migrations and seed data:

```bash
make migrate
make seed
```

## Project Structure

```text
backend/        Django API, pipeline orchestration, ACP agent runners
frontend/       Next.js web application
benchmark/      Example projects used for demos and evaluation
Makefile        Copy-paste commands for common tasks
.env.example    Template for local settings and agent API keys
docker-compose.yml Optional local service configuration
AGENTS.md       Development instructions for coding agents
```

## Validate The Install

Run tests and lint checks:

```bash
make test
make lint
```

Build the frontend:

```bash
make build
```
