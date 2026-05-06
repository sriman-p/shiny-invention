# ReqLens

Requirement-traced test generation tool. Supplies a requirements document and code directory, runs a 6-stage pipeline delegating LLM work to external coding agents over ACP (Agent Client Protocol).

## Quick Start

```bash
make install
cp .env.example .env  # fill in API keys
make migrate
make seed
make dev-backend &
make dev-frontend
```

Open http://localhost:3000.

## Architecture

- **Backend**: Django 5.x + DRF, SQLite, background pipeline execution
- **Frontend**: Next.js 15, React 19, shadcn/ui, Tailwind v4
- **Pipeline**: 6 stages (Parse, Analyze, Map, Generate, Critique, Trace)
- **ACP**: All LLM interactions via Agent Client Protocol SDK
- **Eval**: 16-configuration sweep (4 prompt strategies x 4 context modes)
