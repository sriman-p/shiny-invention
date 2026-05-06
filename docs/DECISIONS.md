# Decisions

## D-001: SQLite for MVP
SQLite used as default database. Production-Postgres-ready via Django settings but not required for MVP.

## D-002: No Celery
Background pipeline execution uses daemon threads with asyncio.run(). Celery is out of scope for MVP.

## D-003: ACP Mock Fallback
When the ACP SDK is not installed, the runner returns mock responses. This enables UI development without external agent dependencies.

## D-004: Auto-approve permissions
Default permission mode is "auto" (always allow). Interactive permission mode is stubbed but not fully implemented for MVP.
