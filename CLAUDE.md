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
make test-e2e           # Playwright E2E tests (21 tests, needs DB + servers)
make test-all           # backend unit + E2E combined
```

### Single test
```bash
cd backend && python -m pytest tests/test_auth.py -k "test_name" -v
npx playwright test e2e/auth.spec.ts              # single E2E file
npx playwright test --ui                           # interactive E2E debugger
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
- `api/v1/` — Route handlers (thin, delegate to services). List has bulk endpoints (`bulk/activate`, `bulk/complete`, `bulk/delete`, `recategorize`). Receipt has `reprocess` endpoint.
- `services/` — Business logic: `receipt_parser` (Claude API with self-correction retries), `price_comparator` (SuperGET API), `product_matcher` (rapidfuzz Hebrew fuzzy matching, 85% threshold), `refresh_engine` (median-of-intervals + confidence scoring), `categorizer`, `basket_comparator`
- `models/` — SQLAlchemy 2.0 models with UUID PKs, `UUIDMixin` + `TimestampMixin` from `base.py`
- `core/` — Cross-cutting: error hierarchy with Hebrew messages (`errors.py`), middleware stack (request ID → rate limiting → security headers), structured logging via structlog
- `dependencies.py` — FastAPI deps: `get_db`, `get_current_user`
- `db/seed.py` — 15 Hebrew categories with emojis auto-seeded for new users during auth signup

### Frontend structure
- `pages/` — Route-level components (7 pages)
- `components/` — Reusable UI (13 components), `AppShell` provides phone-frame layout (430px max-width), `BulkActionBar` for multi-select operations
- `store/authStore.ts` — Zustand auth state, never persists tokens to localStorage
- `api/client.ts` — Axios instance with auth interceptor + token refresh coalescing (single inflight refresh via promise lock)
- Path alias: `@/` resolves to `src/` (configured in vite.config.ts + tsconfig)
- PWA: Workbox service worker with `NetworkFirst` for API data, `StaleWhileRevalidate` for categories, `NetworkOnly` for OAuth

### E2E tests (`e2e/`)
- Playwright with Chromium, 430×932 mobile viewport, Hebrew locale, 1 worker (serial)
- `fixtures/auth.fixture.ts` — `authenticatedPage` fixture: guest login → skip onboarding → `/list`
- 3 spec files: `auth.spec.ts`, `shopping-list.spec.ts`, `receipts.spec.ts`
- Receipt tests mock `/api/v1/receipts/upload` via `page.route()` to avoid calling Claude API
- Config starts both backend (8000) and frontend (5173) web servers automatically

## Key Conventions

- **Hebrew RTL:** `index.html` has `dir="rtl" lang="he"`. Error messages include Hebrew text. All UI text is Hebrew.
- **Hebrew normalization:** Product matching removes nikud (vowel marks U+0591–U+05C7), lowercases, strips punctuation, collapses whitespace.
- **Async everywhere:** Backend uses `async def` handlers, `AsyncSession`, asyncpg driver. Logging uses `await logger.ainfo()` / `await logger.aerror()`.
- **Error hierarchy:** `SmartKalError` base in `core/errors.py` with typed subclasses mapped to HTTP status codes. Errors include bilingual messages (`message_he` + `message_en`), error codes (e.g. `RECEIPT_004`), and source file:line via `inspect.currentframe()`.
- **Pydantic v2:** Response schemas use `model_config = {"from_attributes": True}` for ORM conversion.
- **`db.refresh(item)` after `db.flush()`** when returning Pydantic-validated responses — required to avoid `MissingGreenlet` errors on lazy-loaded `updated_at`.
- **Auth tokens:** Access token in memory (frontend), refresh token in httpOnly cookie scoped to `/api/v1/auth`. Cookie is `secure=True` + `samesite="lax"` in production.
- **Rate limiting:** 100 req/min general + 10 uploads/hour in production; relaxed to 1000 req/min in development (for E2E tests). Sliding window algorithm, in-memory per-IP.
- **Ruff rules:** `E, F, I, N, W, UP, B, A, SIM, TCH` — line length 100.
- **mypy strict** with pydantic plugin. Python ≥ 3.11.
- **TypeScript strict** mode enabled.
- **Alembic auto-runs** `upgrade head` on container startup (Dockerfile CMD).
- **API docs:** Swagger UI at `/docs` only in dev mode (disabled in production). Health check at `/health`.

## Deployment

Production on Railway: managed PostgreSQL, backend as Docker container (uses `backend/Dockerfile`), frontend as a separate Railway service. Configured via the Railway dashboard (no `railway.toml`/`nixpacks.toml` in the repo) — env vars are set per-service in the dashboard and read by the backend through Pydantic Settings. Frontend and backend are deployed on separate `up.railway.app` subdomains, which is why `cookie_samesite="none"` is required in production (cross-site cookies due to PSL).
