# PRD: SmartKal (סמארט-כל)

## Introduction

SmartKal is a smart grocery shopping list PWA for the Israeli market. Unlike traditional shopping lists, SmartKal learns your purchase patterns and automatically refreshes items when you're likely to need them again. Upload a supermarket receipt PDF, and the app parses it with AI, matches products, compares prices across chains, and tells you where you could have saved money.

The app is built RTL Hebrew-first, styled like Apple Reminders, and runs as an installable PWA on mobile with a phone-frame layout on desktop.

## Goals

- One persistent list per user — items cycle between "active" and "completed", never deleted
- Auto-refresh engine that learns purchase frequency and re-activates items
- AI-powered receipt parsing (Claude Sonnet) with Hebrew fuzzy product matching
- Price comparison across Israeli supermarket chains via SuperGET API
- Apple Reminders-style UI, fully RTL Hebrew, installable PWA
- Production deployment on Render.com

## Tech Stack

- **Backend:** FastAPI + SQLAlchemy 2.0 async + PostgreSQL (asyncpg) + Alembic + Pydantic v2 + structlog
- **Frontend:** React 18 + TypeScript + Vite + Tailwind CSS + Zustand + Axios + React Router v6
- **AI:** Anthropic Claude API (Sonnet) for receipt parsing + auto-categorization
- **Prices:** SuperGET API for Israeli supermarket price comparison
- **PWA:** Workbox for offline support
- **Auth:** Google OAuth + JWT (access 15min + refresh 30d)
- **Deploy:** Render.com (static frontend + web backend + PostgreSQL)

## User Stories

---

### US-001: Project scaffolding
**Description:** As a developer, I want a monorepo with backend and frontend directories so that the project structure is ready for development.

**Acceptance Criteria:**
- [x] Create `backend/` and `frontend/` directories
- [x] `backend/pyproject.toml` and `requirements.txt` with: fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, alembic, pydantic, pydantic-settings, python-jose[cryptography], httpx, python-multipart, anthropic, pymupdf, rapidfuzz, structlog
- [x] `backend/requirements-dev.txt` with: pytest, pytest-asyncio, pytest-cov, ruff, mypy
- [x] `frontend/package.json` with: react, typescript, vite, tailwind, zustand, axios, react-router-dom, react-dropzone, recharts, lucide-react, workbox-window
- [x] Root: `.gitignore`, `.env.example`, `docker-compose.yml`, `Makefile` with install/dev/test targets
- [x] `cd backend && pip install -r requirements.txt` runs without errors
- [x] `cd frontend && npm install` runs without errors
- [x] Typecheck passes

---

### US-002: Backend skeleton with health endpoint
**Description:** As a developer, I want a FastAPI app with health check, CORS, and structured logging so that the backend foundation is ready.

**Acceptance Criteria:**
- [x] `backend/app/main.py` with FastAPI app, CORS middleware, lifespan hook
- [x] `backend/app/config.py` with Pydantic Settings (DATABASE_URL, JWT_SECRET, etc.)
- [x] `backend/app/core/logging.py` with structlog JSON setup
- [x] `GET /health` returns `{"status": "ok"}`
- [x] `uvicorn app.main:app` starts without errors
- [x] `curl localhost:8000/health` returns 200
- [x] Typecheck passes

---

### US-003: Frontend skeleton with RTL and phone frame
**Description:** As a user, I want an RTL Hebrew app shell with bottom navigation so that I can navigate between tabs.

**Acceptance Criteria:**
- [x] `frontend/src/main.tsx` and `App.tsx` with React Router
- [x] Tailwind configured with RTL support
- [x] `AppShell.tsx` with phone frame (430px max-width on desktop, full screen on mobile)
- [x] `BottomNav.tsx` with 3 tabs: רשימה, קבלות, עוד
- [x] Placeholder pages: `ListPage`, `ReceiptsPage`, `MorePage`
- [x] `index.html` has `dir="rtl"` and `lang="he"`
- [x] `npm run dev` loads app in browser with RTL layout and bottom nav
- [x] Typecheck passes
- [x] Verify changes work in browser

---

### US-004: Database models with UUID primary keys
**Description:** As a developer, I want all SQLAlchemy 2.0 async models defined so that the data layer is ready.

**Acceptance Criteria:**
- [x] `backend/app/db/session.py` with async engine and session factory (asyncpg)
- [x] `backend/app/models/base.py` with UUID mixin and timestamp mixin
- [x] Models created: User, Category, Product, ListItem, Receipt, Purchase, PriceHistory, UserProductPreference
- [x] ListItem has: status (active/completed), last_completed_at, last_activated_at, auto_refresh_days, system_refresh_days, next_refresh_at, source, confidence, display_order
- [x] All relationships and foreign keys defined correctly
- [x] `python -c "from app.models import *"` runs without import errors
- [x] Typecheck passes

---

### US-005: Alembic setup and initial migration with seed categories
**Description:** As a developer, I want Alembic migrations and default Hebrew categories seeded so that the database is ready.

**Acceptance Criteria:**
- [x] Alembic initialized with async support
- [x] Initial migration generated from models
- [x] Seed script with 15 Hebrew categories: ירקות, פירות, מוצרי חלב, בשר עופות ודגים, לחמים, קפואים, שימורים ויבשים, חטיפים ומתוקים, משקאות, ניקיון, טיפוח, תינוקות, חד-פעמי, תבלינים ורטבים, אחר
- [x] `alembic upgrade head` creates tables in PostgreSQL
- [x] Seed script inserts 15 categories
- [x] `alembic downgrade base` tears down cleanly
- [x] Typecheck passes

---

### US-006: Error handling system
**Description:** As a developer, I want a structured error hierarchy with Hebrew messages and request tracing so that all errors are consistent and debuggable.

**Acceptance Criteria:**
- [x] `backend/app/core/errors.py` with SmartKalError base class and subclasses: ValidationError, AuthenticationError, NotFoundError, RateLimitError, ExternalServiceError, ReceiptParsingError, ClaudeAPIError, SuperGETError, DatabaseError
- [x] Every error has: error_code, message_he, message_en, status_code, details dict, auto-captured source_location
- [x] Request ID middleware adds X-Request-ID to every response
- [x] Global exception handlers for SmartKalError and unhandled Exception
- [x] Error response format: `{error: {code, message, message_en, details, debug: {timestamp, request_id, source}}}`
- [x] Tests: each exception type returns correct status code and Hebrew message
- [x] Typecheck passes

---

### US-007: Google OAuth + JWT authentication backend
**Description:** As a user, I want to log in with Google and receive JWT tokens so that my data is secure and personal.

**Acceptance Criteria:**
- [x] FIRST: Search web for current Google OAuth token verification docs and confirm endpoint/library
- [x] `backend/app/core/security.py` — verify Google token, create/decode JWT pair
- [x] `backend/app/dependencies.py` — get_current_user dependency
- [x] `POST /api/v1/auth/google` — receives id_token, verifies with Google, creates user, returns JWT pair
- [x] `POST /api/v1/auth/refresh` — refresh token → new access token
- [x] `GET /api/v1/auth/me` — returns current user (protected)
- [x] Tests: mock Google verification, JWT lifecycle, protected endpoint returns 401 without token
- [x] Typecheck passes

---

### US-008: Frontend auth with Google Sign-In and Axios interceptor
**Description:** As a user, I want a Google login button and automatic token management so that I stay authenticated.

**Acceptance Criteria:**
- [x] `frontend/src/store/authStore.ts` — Zustand store with tokens in memory (NOT localStorage)
- [x] `frontend/src/pages/OnboardingPage.tsx` with Google Sign-In button
- [x] `frontend/src/api/client.ts` — Axios instance with JWT interceptor and auto-refresh on 401
- [x] Error interceptor maps error codes to Hebrew toast messages
- [x] Unauthenticated users redirected to OnboardingPage
- [x] App loads, shows login page, Google button visible
- [x] Typecheck passes
- [ ] Verify changes work in browser

---

### US-009: Shopping list CRUD backend
**Description:** As a user, I want to add, view, update, and delete items in my shopping list so that I can manage what I need to buy.

**Acceptance Criteria:**
- [x] `backend/app/api/v1/list.py` with routes
- [x] `GET /api/v1/list` — returns all items grouped by category (active and completed)
- [x] `POST /api/v1/list/items` — add item with name, optional quantity, optional category
- [x] `PUT /api/v1/list/items/{id}` — update name, quantity, note, category
- [x] `DELETE /api/v1/list/items/{id}` — permanent remove
- [x] Auto-categorization: if category not specified, use Claude API to categorize Hebrew product name
- [x] All endpoints are user-scoped (user_id from JWT)
- [x] Tests: CRUD operations, user isolation, auto-categorization (mocked)
- [x] Typecheck passes

---

### US-010: Complete/activate items + auto-refresh engine
**Description:** As a user, I want completed items to automatically return to my list when I'm likely to need them again.

**Acceptance Criteria:**
- [x] `PATCH /api/v1/list/items/{id}/complete` — set status=completed, record last_completed_at, calculate and set next_refresh_at
- [x] `PATCH /api/v1/list/items/{id}/activate` — set status=active, record last_activated_at, clear next_refresh_at
- [x] `POST /api/v1/list/refresh` — check all completed items, activate any past next_refresh_at
- [x] `backend/app/services/refresh_engine.py` — frequency calculation using median of intervals from completion history and receipt purchases
- [x] Confidence scoring: 1 interval=0.2, 2=0.3, 3-4=0.4, 5-9=0.6, 10+=0.8, low variance bonus +0.15, user override=0.95
- [x] `PATCH /api/v1/list/items/{id}/preferences` — set auto_refresh_days (user override)
- [x] Tests: complete sets next_refresh, refresh activates overdue items, frequency calculation with known dates, user override takes priority
- [x] Typecheck passes

---

### US-011: Category management backend
**Description:** As a user, I want to create, rename, reorder, and delete categories so that my list is organized my way.

**Acceptance Criteria:**
- [x] `GET /api/v1/categories` — all categories for current user
- [x] `POST /api/v1/categories` — create new category
- [x] `PUT /api/v1/categories/{id}` — rename, change icon
- [x] `DELETE /api/v1/categories/{id}` — delete (moves items to אחר)
- [x] `POST /api/v1/categories/reorder` — bulk reorder by passing array of IDs
- [x] On new user creation, seed 15 default categories
- [x] Tests: CRUD, reorder, delete moves items, new user gets defaults
- [x] Typecheck passes

---

### US-012: Shopping list UI — basic rendering with categories
**Description:** As a user, I want to see my shopping list grouped by category with collapsible sections so that items are organized.

**Acceptance Criteria:**
- [x] `ShoppingList.tsx` — renders items grouped by category
- [x] `CategorySection.tsx` — collapsible section with bold header and chevron icon
- [x] `ListItem.tsx` — circle indicator (○ active, ● completed), product name, optional quantity
- [x] Items fetched from `GET /api/v1/list` on mount
- [x] Typecheck passes
- [ ] Verify changes work in browser

---

### US-013: Shopping list UI — check/uncheck animations and completed section
**Description:** As a user, I want smooth animations when checking off items and a collapsible completed section.

**Acceptance Criteria:**
- [x] Tap ○ → animates to ● green, item text becomes gray with line-through, slides to completed section
- [x] Tap ● → animates back to ○, item returns to active section
- [x] `CompletedSection.tsx` — collapsible "X הושלמו · ניקוי" with show/hide toggle
- [x] Calls `PATCH /api/v1/list/items/{id}/complete` and `/activate` endpoints
- [x] Typecheck passes
- [ ] Verify changes work in browser

---

### US-014: Shopping list UI — add item input with autocomplete
**Description:** As a user, I want to quickly add items with a FAB button and get Hebrew autocomplete suggestions from my product history.

**Acceptance Criteria:**
- [x] `AddItemInput.tsx` — tap ⊕ FAB opens inline text input
- [x] Hebrew autocomplete from product history
- [x] Calls `POST /api/v1/list/items` on submit
- [x] Auto-refreshed items show a small green dot badge
- [x] Calls `POST /api/v1/list/refresh` on app open
- [x] Typecheck passes
- [ ] Verify changes work in browser

---

### US-015: Shopping list UI — swipe to delete and item details
**Description:** As a user, I want to swipe left to delete items and long-press for details so that I can manage items quickly.

**Acceptance Criteria:**
- [x] Swipe left on item → reveal red "הסר" button
- [x] Swipe delete calls `DELETE /api/v1/list/items/{id}`
- [x] Long press → bottom sheet with quantity, note, frequency override fields
- [x] Bottom sheet saves via `PUT /api/v1/list/items/{id}` and `PATCH /api/v1/list/items/{id}/preferences`
- [x] Typecheck passes
- [ ] Verify changes work in browser

---

### US-016: Price comparison card on list page
**Description:** As a user, I want to see a price comparison card at the top of my list showing where I can save money.

**Acceptance Criteria:**
- [x] `PriceComparisonCard.tsx` — shows recommended store and savings amount
- [x] Only visible when price data exists for the user
- [x] Tap → expands to show per-store breakdown
- [x] Design: subtle green background, store name + total + savings amount
- [x] Card hidden when no price data, visible when data exists
- [x] Typecheck passes
- [ ] Verify changes work in browser

---

### US-017: PDF text extraction utility
**Description:** As a developer, I want a utility that extracts and cleans Hebrew text from receipt PDFs so that it's ready for AI parsing.

**Acceptance Criteria:**
- [x] FIRST: Search web for current PyMuPDF API docs and confirm usage
- [x] `backend/app/utils/pdf.py` — PyMuPDF text extraction with Hebrew text cleaning
- [x] Handles RTL text correctly
- [x] Tests: extraction from sample PDF, Hebrew character handling
- [x] Typecheck passes

---

### US-018: Claude AI receipt parser service
**Description:** As a developer, I want a service that sends receipt text to Claude Sonnet and returns structured product data.

**Acceptance Criteria:**
- [x] FIRST: Search web for current Anthropic Claude API messages endpoint docs and confirm model name + request format
- [x] `backend/app/services/receipt_parser.py` — Claude Sonnet parsing with structured prompt
- [x] JSON validation of Claude response
- [x] Retry on failure (max 2 retries)
- [x] Tests: mocked Claude responses — valid JSON, invalid JSON, empty receipt
- [x] Typecheck passes

---

### US-019: Receipt API endpoints
**Description:** As a user, I want to upload receipt PDFs and view my receipt history so that my purchases are tracked.

**Acceptance Criteria:**
- [x] `POST /api/v1/receipts/upload` — accept PDF, validate (magic bytes, max 10MB), extract text, parse with Claude, return parsed result
- [x] `GET /api/v1/receipts/{id}` — full receipt with parsed items
- [x] `GET /api/v1/receipts` — paginated list of all receipts
- [x] Save Receipt + Purchase records to DB, update PriceHistory
- [x] All endpoints user-scoped
- [x] Tests: file validation, upload flow (mocked Claude), user isolation
- [x] Typecheck passes

---

### US-020: Product matching from receipts
**Description:** As a user, I want receipt items automatically matched to my existing products so that my list stays accurate.

**Acceptance Criteria:**
- [x] `backend/app/services/product_matcher.py` — rapidfuzz Hebrew fuzzy matching
- [x] Match priority: barcode exact → normalized name exact → fuzzy match (threshold 0.85) → create new product
- [x] When matched: offer to upgrade generic name (חלב) to precise name (חלב תנובה 3% 1 ליטר)
- [x] `POST /api/v1/list/items/{id}/upgrade` — upgrade item name to precise receipt name
- [x] Matched list items marked as completed (just bought), completion timestamp recorded
- [x] Recalculate refresh frequencies for affected products
- [x] Tests: exact match, fuzzy Hebrew match, barcode match, no match creates new, upgrade flow
- [x] Typecheck passes

---

### US-021: Receipt upload UI with parsed results
**Description:** As a user, I want to upload a receipt and see parsed items with price comparison — the wow moment.

**Acceptance Criteria:**
- [x] `ReceiptsPage.tsx` — upload zone + receipt history list by month
- [x] `ReceiptUpload.tsx` — drag-drop or tap to select PDF
- [x] `ReceiptResults.tsx` — price comparison card (savings in big green), category breakdown, parsed items list with edit/delete per item, warning for unmatched items
- [x] "אישור ושמירה" button: saves to inventory, merges with list, navigates to list tab
- [x] Loading state with skeleton while parsing
- [x] Upload PDF → see parsed items + price comparison + category breakdown
- [x] Typecheck passes
- [ ] Verify changes work in browser

---

### US-022: SuperGET API client and product matching
**Description:** As a developer, I want a client that queries SuperGET for Israeli supermarket prices and matches products.

**Acceptance Criteria:**
- [x] FIRST: Search web for SuperGET API documentation, confirm base URL, auth method, endpoints
- [x] `backend/app/services/price_comparator.py` — match products to SuperGET by barcode first, then fuzzy name match via Claude
- [x] Save SuperGET prices to PriceHistory with source='superget'
- [x] Tests: matching logic with mocked SuperGET responses
- [x] Typecheck passes

---

### US-023: Price comparison endpoints
**Description:** As a user, I want to compare my receipt or shopping list across supermarket chains to find the cheapest option.

**Acceptance Criteria:**
- [x] Calculate basket total per chain, return ranked comparison with coverage indicator
- [x] `GET /api/v1/prices/compare-receipt/{id}` — compare receipt basket across chains
- [x] `GET /api/v1/prices/compare-list` — compare current active list across chains
- [x] Handle partial matches gracefully: "השוואה על 18 מתוך 23 מוצרים (78%)"
- [x] Tests: basket calculation, partial coverage scenarios
- [x] Typecheck passes

---

### US-024: Dashboard backend API
**Description:** As a developer, I want spending analytics endpoints so that the frontend can display charts.

**Acceptance Criteria:**
- [x] `GET /api/v1/dashboard/spending?period=month` — spending by category
- [x] `GET /api/v1/dashboard/stores` — spending per store chain
- [x] `GET /api/v1/dashboard/trends` — monthly spending trend
- [x] All endpoints user-scoped
- [x] Tests: correct aggregation from receipt/purchase data
- [x] Typecheck passes

---

### US-025: Dashboard frontend UI with charts
**Description:** As a user, I want a spending dashboard with charts so that I can understand my grocery spending.

**Acceptance Criteria:**
- [x] `DashboardPage.tsx` — spending total, category donut chart (recharts), store breakdown, monthly trend line chart
- [x] Accessible from עוד tab → "דשבורד הוצאות"
- [x] Dashboard shows real data from uploaded receipts
- [x] Typecheck passes
- [ ] Verify changes work in browser

---

### US-026: More page, settings, and category management UI
**Description:** As a user, I want a settings page and category management so that I can customize my experience.

**Acceptance Criteria:**
- [x] `MorePage.tsx` — iOS Settings style grouped list: דשבורד הוצאות, ניהול קטגוריות, הגדרות, עזרה ומשוב, התנתק
- [x] `SettingsPage.tsx` — basic settings
- [x] `CategoryManagementPage.tsx` — list categories, rename, reorder (drag), add, delete
- [x] More tab shows all menu items, category management works
- [x] Typecheck passes
- [ ] Verify changes work in browser

---

### US-027: Onboarding flow
**Description:** As a new user, I want a welcoming onboarding experience that explains the app's value and gets me started.

**Acceptance Criteria:**
- [x] Step 1: logo + "סמארט-כל — רשימת הקניות שמכירה אותך" + Google Sign-In
- [x] Step 2: three swipeable value cards with dot indicators — "רשימה שמרעננת את עצמה", "העלה קבלה תראה איפה זול", "ככל שתשתמש ככה חכמה יותר"
- [x] Step 3: "מה תרצה לעשות?" with two big cards — "העלאת קבלה" / "יצירת רשימה"
- [x] After onboarding: redirect to ListPage or ReceiptsPage based on choice
- [x] Full onboarding flow works from login to first action
- [x] Typecheck passes
- [ ] Verify changes work in browser

---

### US-028: PWA setup with offline support
**Description:** As a user, I want the app installable on my phone and working offline so that I can use my list in the supermarket.

**Acceptance Criteria:**
- [x] `frontend/public/manifest.json` — RTL, Hebrew, SmartKal name, green theme, icons
- [x] `vite-plugin-pwa` configured with Workbox — precache app shell, runtime cache API responses
- [x] Shopping list works offline (cached list data)
- [x] Install prompt shown on mobile
- [x] Lighthouse PWA score > 90
- [x] App installable on Android Chrome
- [x] Typecheck passes
- [ ] Verify changes work in browser

---

### US-029: Production deployment on Render.com
**Description:** As a developer, I want the app deployed to production so that users can access it.

**Acceptance Criteria:**
- [x] Backend Dockerfile (multi-stage, slim Python)
- [x] `render.yaml` with: frontend static site, backend web service, PostgreSQL database
- [ ] Frontend: build command, static publish path, SPA rewrite rule
- [ ] Backend: start command with uvicorn, health check path, env vars from Render
- [ ] CORS configured for production domain
- [ ] Security headers middleware
- [ ] Rate limiting middleware (10 uploads/hour, 100 calls/minute)
- [ ] Deploy succeeds, health endpoint responds, frontend loads
- [ ] Typecheck passes

---

## Non-Goals

- Multi-language support (Hebrew only for now)
- Multiple lists per user (one persistent list only)
- Manual barcode scanning (barcode matching is from receipt data only)
- Real-time collaboration / shared lists
- Native mobile app (PWA only)
- Payment processing
- Store-specific promotions or coupons
- Nutritional information

## Technical Notes

- **PostgreSQL from the start** — no SQLite, use asyncpg
- **ListItem is the core entity** — items cycle between active/completed, no separate ShoppingList objects
- **RTL Hebrew first** — all UI text in Hebrew, `dir="rtl"`, Tailwind logical properties (`ps`/`pe` not `pl`/`pr`)
- **Apple Reminders design** — bold category headers, collapsible chevrons, circles for check/uncheck, completed items gray with line-through
- **Phone frame on desktop** — max-width 430px, centered, rounded corners, shadow; full screen on mobile
- **API verification rule** — before writing code that calls an external API, search the web for current docs and verify endpoints
- **Error handling** — every error includes error_code, message_he, message_en, details, debug info (request_id, source, timestamp)
