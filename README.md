# ReqLens

ReqLens is a requirement-traced test generation tool with a Django backend and a Next.js frontend. It runs a six-stage pipeline and delegates LLM work to external coding agents through ACP (Agent Client Protocol), with an additional Cursor SDK Composer 2 bridge.

## Prerequisites

- Git
- `make`
- Python 3.11 or newer
- `uv`
- Node.js 20.9 or newer; Node.js 22 is recommended
- Corepack, included with Node, for the pinned frontend `pnpm`

Install the local toolchain on macOS with Homebrew:

```bash
brew install uv node@22
```

If `node` still points at an older version after installing `node@22`, add it to your shell path:

```bash
export PATH="/opt/homebrew/opt/node@22/bin:$PATH"
```

## Download

```bash
git clone https://github.com/sriman-p/shiny-invention.git
cd shiny-invention
```

## Configure

Create a local environment file:

```bash
cp .env.example .env
```

For basic UI and configuration work, the default development values are enough. To run real agent-backed pipeline stages, set the keys or local auth for the agents you plan to use:

- `CURSOR_API_KEY` for `Cursor SDK (Composer 2)`
- Cursor desktop/CLI auth or `CURSOR_API_KEY` for `Cursor Agent`
- Claude Code auth or `ANTHROPIC_API_KEY` for `Claude Code`
- ChatGPT/Codex auth, `CODEX_API_KEY`, or `OPENAI_API_KEY` for `OpenAI Codex CLI`
- `GEMINI_API_KEY` for `Gemini CLI`

## Install

```bash
make install
```

This installs backend dependencies with `uv`, the Cursor SDK bridge under `backend/acp_client/cursor_sdk`, and frontend dependencies with Corepack-managed `pnpm`.

## Database

```bash
make migrate
make seed
```

`make seed` creates benchmark projects for calculator, URL shortener, and todo API examples.

## Run Locally

Start the backend:

```bash
make dev-backend
```

In a second terminal, start the frontend:

```bash
make dev-frontend
```

Open http://localhost:3000.

The backend defaults to port 8000. If 8000 is busy, `make dev-backend` chooses the next free port and prints it. When that happens, start the frontend with the matching API URL:

```bash
cd frontend
corepack enable
NEXT_PUBLIC_API_BASE_URL=http://localhost:8001/api/v1 pnpm dev
```

Replace `8001` with the port printed by the backend.

## Check The Install

```bash
make test
make lint
```

For frontend production validation:

```bash
cd frontend
corepack enable
pnpm build
```

## Agent Registry

The Agent Registry page at http://localhost:3000/settings/agents shows whether each agent command is on `PATH` and whether required environment variables are set. Missing optional agents do not block local UI work.

On a project page, use the Agents tab to choose the agent and model for each pipeline stage. Leaving the model as `Agent default` uses that agent's configured default; choosing a known model or entering a custom model ID stores it in the run snapshot and passes it to agents that support model selection.
