# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SmartKal (סמארט-כל) — a Hebrew-first RTL progressive web app for smart grocery shopping in Israel. Parses supermarket receipts via Claude AI, learns purchase frequency to auto-refresh items, and compares prices across Israeli chains via SuperGET API.

## Commands

### Development
```bash
make install            # Install all dependencies (backend pip + frontend npm)
make db-up              # Start PostgreSQL 16 via docker-compose
make dev-backend        # uvicorn with --reload on port 8000
make dev-frontend       # Vite dev server on port 5173
make dev                # Both servers in parallel
```

### Quality
```bash
make lint               # ruff check + ruff format --check (backend only)
make typecheck          # mypy app/ (strict) + tsc --noEmit (strict)
make test               # pytest --cov=app tests/ (backend only)
```

### Single test
```bash
cd backend && python -m pytest tests/test_auth.py -k "test_name" -v
```

### Database migrations
```bash
cd backend && alembic revision --autogenerate -m "description"
cd backend && alembic upgrade head
```

## Architecture

**Backend:** FastAPI (async) + SQLAlchemy 2.0 (asyncpg) + PostgreSQL 16. All API routes under `/api/v1/`. Entry point: `backend/app/main.py`.

**Frontend:** React 18 + TypeScript + Vite 6. State via Zustand (single auth store with in-memory tokens). Styling with Tailwind CSS. PWA with Workbox service worker.

**Auth flow:** Google OAuth id_token → server verifies → JWT access (15 min) + refresh (30 days) tokens. Guest login available. Axios interceptors handle auto-refresh on 401.

### Backend layers
- `api/v1/` — Route handlers (thin, delegate to services)
- `services/` — Business logic: `receipt_parser` (Claude API), `price_comparator` (SuperGET API), `product_matcher` (rapidfuzz Hebrew fuzzy matching), `refresh_engine` (purchase frequency learning)
- `models/` — SQLAlchemy 2.0 models with UUID PKs, `UUIDMixin` + `TimestampMixin` from `base.py`
- `core/` — Cross-cutting: error hierarchy with Hebrew messages (`errors.py`), middleware stack (request ID → rate limiting → security headers), structured logging via structlog
- `dependencies.py` — FastAPI deps: `get_db`, `get_current_user`

### Frontend structure
- `pages/` — Route-level components (7 pages)
- `components/` — Reusable UI (12 components), `AppShell` provides phone-frame layout
- `store/authStore.ts` — Zustand auth state, never persists tokens to localStorage
- `api/client.ts` — Axios instance with auth interceptor + token refresh coalescing

## Key Conventions

- **Hebrew RTL:** `index.html` has `dir="rtl" lang="he"`. Error messages include Hebrew text. All UI text is Hebrew.
- **Async everywhere:** Backend uses `async def` handlers, `AsyncSession`, asyncpg driver.
- **Error hierarchy:** `SmartKalError` base in `core/errors.py` with typed subclasses mapped to HTTP status codes.
- **Ruff rules:** `E, F, I, N, W, UP, B, A, SIM, TCH` — line length 100.
- **mypy strict** with pydantic plugin. Python ≥ 3.11.
- **TypeScript strict** mode enabled.
- **Alembic auto-runs** `upgrade head` on container startup (Dockerfile CMD).

## Deployment

Production on Render.com (`render.yaml`): managed PostgreSQL, backend as Docker container, frontend as static site with SPA rewrites. Environment config via Pydantic Settings reading from env vars.
