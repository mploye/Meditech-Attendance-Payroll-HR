# Project Analysis — ESSL Attendance · Payroll · HR

> Generated from a full codebase review (backend, frontend, security, code quality).
> This is a snapshot of the project as-is; findings are organized by severity.

---

## 1. Project Overview

**Genetics Meditech** is an HR + Attendance + Payroll SaaS with official **eSSL eTimeTrackLite** and **AI-FACE-ORCUS** device integration.

| Layer | Stack | Location |
|---|---|---|
| Backend API | FastAPI (Python 3.13), SQLAlchemy 2.0, Alembic, APScheduler | `backend/` |
| Frontend UI | Next.js 16, React 19, Tailwind CSS 4, TypeScript | `frontend/` |
| Database | SQLAlchemy models; SQLite (dev) / Postgres via Supabase (prod) | `backend/app/models/` |
| Device sync | Standalone Python connector (TCP/ZKTeco protocol + HTTP) | `backend/connector/` |
| Deployment | Render (API), Vercel (UI), optional Docker Compose / Kubernetes | `deploy/`, `docker-compose.yml` |

---

## 2. Architecture Summary

### Backend (FastAPI — layered)

```
backend/
├── app/
│   ├── main.py                  # FastAPI entrypoint; mounts /api/v1 router, static files
│   ├── api/
│   │   ├── v1/router.py         # Aggregates 20 endpoint modules under /api/v1
│   │   ├── v1/endpoints/*.py    # 20 route modules (auth, employees, payroll, …)
│   │   └── deps.py              # ensure_perm, resolve_company_id, orm_to_dict, user_dict
│   ├── core/                    # config, database, security, deps, errors, rbac, audit, migrations
│   ├── models/                  # 30 SQLAlchemy models + enums (base, user, company, employee, payroll, …)
│   ├── services/                # 18 business-logic files (employee, payroll, attendance, …)
│   ├── payroll/                 # Calculator (563 lines), statutory, LOP
│   ├── integrations/essl/       # HTTP client, TCP protocol, mock, pulldevice, config, service
│   ├── tasks/                   # APScheduler jobs (sync, attendance processing)
│   └── static/                  # company_logo.png
├── connector/                   # Standalone device-sync worker (separate process)
├── tests/                       # 40 pytest tests (integration via TestClient)
├── scripts/                     # smoke_api.py, init_db.py, debug_db.py, smoke_attendance.py
└── alembic/ + alembic.ini       # Migrations (schema bootstraps via create_all fallback)
```

**Route pattern:** each endpoint file defines `router = APIRouter()`, exported, and mounted by `api/v1/router.py` under prefix `/api/v1`. All endpoints enforce RBAC via `ensure_perm(user, "module.action")` and tenant scope via `resolve_company_id`.

### Frontend (Next.js App Router)

```
frontend/
├── app/                         # App Router pages (routes MUST live here)
│   ├── layout.tsx, page.tsx     # Root: redirects to /dashboard or /login
│   ├── login/page.tsx           # Login with 3D scene
│   └── (app)/                   # Authenticated section; (app)/layout.tsx wraps in <Shell>
│       └── {16 pages}/page.tsx  # dashboard, employees, payroll, …, settings, audit
├── components/
│   ├── ui/index.tsx             # UI primitives (Button, Card, Input, …)
│   ├── Shell.tsx                # Sidebar + app shell (nav, role display)
│   ├── CrudPage.tsx             # Generic CRUD page (used by departments, designations)
│   └── LoginScene.tsx           # 3D animated login card
├── lib/api.ts                   # Typed API client, auth storage, file download, retries
├── public/                      # assets (genetics-logo.png)
├── tests/e2e/                   # Playwright E2E specs + helpers
└── <config files>               # next.config.ts, tsconfig.json, postcss.config.mjs, eslint.config.mjs, playwright.config.ts
```

**Pages cannot move out of `app/`** — this is required by Next.js App Router. The sidebar nav in `Shell.tsx` lists all 16 sections; every page is reachable.

---

## 3. Backend Deep Dive

### Models (30 tables)

All models inherit `PKMixin` (UUID primary key) + `TimestampMixin` (created_at, updated_at) + `Base`. Exceptions: `AttendanceLog`, `AuditLog`, `DeviceSyncLog`, `PayrollComponent`, `Payslip` do not inherit `TimestampMixin` (some define their own `created_at`/`generated_at`).

Key models: `User` (role, company_id, employee_id), `Company`, `Employee`, `PayrollPeriod`, `PayrollRecord`, `Payslip`, `AttendanceLog`, `AttendanceDaily`, `Device`, `ESSLConfig`, `LeaveType`, `LeaveRequest`, `SalaryStructure`, `EmployeeLoan`, `SalaryAdvance`, `OvertimeRecord`, `StatutoryRule`.

**Inconsistency:** `LoanInstallment.status` uses raw `String(20)` instead of the `LoanStatus` enum used by every other status field.

### Services (18 files)

Pattern: mostly free functions taking `db: Session` as first arg, company-scoped queries, raise `core.errors` exceptions. Inconsistencies: `SyncService` is a class, most others are functions; some functions commit inside, others expect callers to commit; some use `db.get()`, others `db.scalar(select(...))`.

**Largest/most complex:** `employee_service.py` (502 lines, 5+ responsibilities), `calculator.py` (563 lines, payroll engine).

**Missing:** `department_service.py` — the `organization.py` endpoint uses departments/designations sub-routers but there's no corresponding service file (logic may be inline in the endpoint).

### Critical Architectural Issues

1. **Circular dependency:** `payroll/calculator.py` imports from `services` via late imports; `services/employee_service.py` imports `payroll.calculator`. The `services/__init__.py` is **empty**, making `from services import X` fragile and dependent on `sys.path` manipulation.

2. **IN/OUT event-type bug:** `pulldevice.py` `_event_type()` maps `punch==1` → `EventType.OUT` and `punch==0` → `EventType.IN`, while `client.py` `_parse_event_type()` maps `"1"` → `EventType.IN` and `"2"` → `EventType.OUT`. **These two code paths produce opposite results for the same logical operation** — IN/OUT will be confused between the HTTP-client path and the TCP-pull path.

3. **`eval()` in salary formula** (`calculator.py:66`): `_eval_formula()` uses `eval(expr, {"__builtins__": {}}, {"basic": basic, "gross": gross})`. While `__builtins__` is disabled, this is still a code-injection risk if formulas come from user input through the API.

4. **`User.default_company_id` missing:** `core/deps.py:39` sets `user.default_company_id = str(default)` on the User object, but the `User` model has **no such column**. This will raise `AttributeError` at runtime for SUPER_ADMIN users with no company bound.

5. **`shift_work_datetime()` is a no-op** (`core/timezone.py:36`): returns `(start_time, end_time)` unchanged — dead placeholder code.

6. **`MockESSLClient.last_called` is class-level mutable state** (`integrations/essl/mock.py`) — persists across instances and leaks test data.

7. **`sync_employee_to_essl` in `employee_service.py`** calls `asyncio.run()` inside a sync function — a blocking anti-pattern that can deadlock in async contexts.

### Services Duplication

- `_round2()` defined identically in `calculator.py`, `lop.py`, `statutory.py`, `dashboard_service.py`, `report_service.py` — should be a utility.
- `_to_date()` duplicated in `leave_service.py` and `holiday_service.py`.
- `active_salary()` query duplicated in `employee_service.py` and `calculator.py`.
- Pagination + company-filter pattern copy-pasted across ~6 service files.

### Routing

20 endpoint modules mounted under `/api/v1`. Each uses `ensure_perm(user, "module.action")` at the top of every handler. The `device_sync.py` endpoint (`/api/v1/device-sync`) serves the standalone connector (authenticated via `DEVICE_CONNECTOR_API_KEY` header, not JWT).

**Note:** `device_sync.py` takes `company_id` directly from the URL path without validating it against the connector API key's authorized companies.

---

## 4. Frontend Deep Dive

### Pages (16 + login + root redirect)

Every authenticated page follows the same inline pattern (~130–232 lines each):
- `useState` for items, error, notice, busy
- `load()` async function with try/catch
- `useEffect` to auto-load on mount
- `<PageHeader>`, `<Alert>`, `<Card>` layout
- Table with `data-label` mobile-stacking attributes
- Inline `submit` handler with try/catch/finally

**This pattern is copy-pasted across 8+ pages.** Only `departments/page.tsx` and `designations/page.tsx` actually use `CrudPage.tsx` as an abstraction — the abstraction is not widely adopted.

### Components

- `Shell.tsx` (192 lines): sidebar nav, user/role display, responsive drawer. Reads role from stored user for display only (no nav filtering — all routes visible to any logged-in user).
- `ui/index.tsx` (178 lines): UI primitives kit (Button, Card, Input, PageHeader, Alert, Badge, Select, Empty, statusTone). All exported from a single barrel file.
- `CrudPage.tsx` (147 lines): generic list+form page. Under-used.
- `LoginScene.tsx` (79 lines): 3D animated card.

### API Client (`lib/api.ts`, 131 lines)

Typed HTTP client with: JWT storage (`hrms.token`), user storage (`hrms.user`), retry with exponential backoff (3 retries, 3s delay), `api.get/post/patch/put/del/download/login`, `downloadFile()` helper. Base URL from `NEXT_PUBLIC_API_URL`.

### Type Safety

The frontend relies heavily on `Record<string, unknown>` and `Record<string, string>` rather than proper TypeScript interfaces for API responses. There are **no shared type/interfaces modules**. Types are inferred inline per page. This defeats compile-time type safety for API data.

### Frontend Duplication

The `submit` handler, `load()` pattern, error/notice state, and table column markup are copy-pasted across 8+ pages. Moving these to shared hooks/components would substantially reduce file sizes and improve maintainability.

### CSS/Styling

Mostly Tailwind classes, but CSS animations (3D login, page transitions) use **inline `style` attributes** (`animationDuration`, `animationDelay`) rather than Tailwind classes or a CSS file. Inconsistent with the otherwise Tailwind-heavy codebase.

---

## 5. Security Assessment

### CRITICAL — On-Disk Secrets (NOT in git)

The `.env` files exist on disk but are **gitignored** (`.env` excluded; only `.env.example` tracked). However, `backend/.env` contains real production credentials that are exposed to anyone with filesystem access:

- `JWT_SECRET` (real value)
- `SUPABASE_PROJECT_ID`, `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY` (full database admin access)
- `RENDER_API_KEY`
- Database URL with project identifier

**Action:** Rotate all these secrets immediately. Remove `backend/.env` from the machine. Never commit `.env` (already correct in .gitignore). Consider adding a pre-commit hook to prevent accidental `.env` commits.

### HIGH Severity Findings

| # | Issue | File |
|---|---|---|
| 1 | **Hardcoded default admin password `"changeme"`** for new company creation | `auth.py:113` |
| 2 | **Hardcoded default user password `"Welcome@123"`** when creating users via API | `users.py:30` |
| 3 | **`verify=False`** disables SSL certificate validation on all eSSL API calls | `integrations/essl/client.py:69`, `connector/essl_client.py:29` |
| 4 | **No CORS origin validation** — `allow_origin_regex` allows `http://localhost:\d+` with `allow_credentials=True`, permitting any localhost port to make credentialed requests | `main.py:34` |
| 5 | **No rate limiting** on any endpoint, especially login/auth | `auth.py` |
| 6 | **No security headers** (X-Content-Type-Options, HSTS, CSP, X-Frame-Options, X-XSS-Protection) | `main.py` |
| 7 | **No CSRF protection** | — |
| 8 | **OpenAPI/Swagger docs accessible without authentication** — leaks API structure | `main.py:26` |
| 9 | **Access token expiry 1440 min (24h)** — excessively long; no refresh token mechanism exists despite `REFRESH_TOKEN_EXPIRE_DAYS` config | `config.py:21` |

### MEDIUM Severity Findings

| # | Issue | File |
|---|---|---|
| 10 | **`eval()` in `calculator.py:66`** for salary formulas — code injection if formulas are user-supplied | `payroll/calculator.py` |
| 11 | **XOR "encryption"** for ESSL secrets using `JWT_SECRET` as key — trivially reversible | `integrations/essl/config.py`, `core/supabase_sync.py` |
| 12 | **`ESSL_MOCK_MODE` defaults to `True`** — production eSSL operations silently use mocks unless explicitly disabled | `config.py:35` |
| 13 | **No password strength validation** on registration or password change | `auth.py` |
| 14 | **No account lockout** after failed login attempts | `auth.py` |
| 15 | **`users.py` `create_user` accepts `body: dict`** — no Pydantic model validation | `users.py:22` |
| 16 | **`device_sync.py` `company_id` from URL not validated** against API key scope | `device_sync.py:18` |
| 17 | **K8s `secret.yaml` has placeholder secrets** that are not replaced | `deploy/k8s/backend/secret.yaml` |
| 18 | **`imagePullPolicy: IfNotPresent`** in all K8s deployments — fails silently if image not pre-pulled | `deploy/k8s/**/*.yaml` |
| 19 | **Frontend `playwright.config.ts` hardcodes production base URL** | `frontend/playwright.config.ts:5` |
| 20 | **Frontend `Dockerfile` hardcodes `NEXT_PUBLIC_API_URL` to `hrms-api-4trx.onrender.com`** | `frontend/Dockerfile:16` |

### Observations

- **SQL injection:** None found — all queries use SQLAlchemy `select()` builder (parameterized).
- **JWT:** HS256 symmetric signing, explicit algorithm list (prevents alg confusion). Token includes `role` and `company_id` claims, but authorization decisions use `user.role` **from the database** (not the JWT claim) — so role escalation via JWT tampering is not possible.
- **Password hashing:** bcrypt — strong.
- **XSS:** No `dangerouslySetInnerHTML` or inline HTML rendering found in frontend or backend.
- **CORS:** `allow_methods=["*"]` + `allow_credentials=True` is technically invalid per the CORS spec (browsers will reject), so the app may fail CORS preflight in some browsers despite the config being permissive.

---

## 6. Code Quality & Technical Debt

### Largest Files (Backend)

| File | Lines | Concern |
|---|---|---|
| `payroll/calculator.py` | 563 | Entire payroll engine; `eval()`, late imports, circular deps |
| `services/employee_service.py` | 502 | 5+ responsibilities (CRUD, salary, devices, user, ESSL sync) |
| `services/attendance_service.py` | 463 | Raw log insertion, daily processing, idempotency |
| `services/payslip_service.py` | 381 | PDF generation (reportlab), lifecycle |
| `integrations/essl/pulldevice.py` | 374 | TCP device protocol |
| `services/report_service.py` | 373 | CSV/XLSX/PDF export |
| `services/leave_service.py` | 344 | Leave types, requests, approvals, balances |
| `api/v1/endpoints/attendance.py` | 246 | Endpoint mixing routing + business logic + raw SQL |

### Largest Files (Frontend)

| File | Lines | Concern |
|---|---|---|
| `app/(app)/employees/page.tsx` | 232 | Copy-pasted load/submit/table pattern |
| `app/(app)/payroll/page.tsx` | 221 | Copy-pasted load/submit/table pattern |
| `app/(app)/settings/page.tsx` | 220 | Copy-pasted load/submit/table pattern |
| `components/Shell.tsx` | 192 | Sidebar nav + role display |
| `app/(app)/leaves/page.tsx` | 204 | Copy-pasted load/submit/table pattern |

### Duplication Summary

- **8+ frontend pages** share identical load/submit/error/notice/table patterns — should be abstracted into a shared hook or base component.
- **`_round2()`** defined 5× in backend services.
- **Pagination + company-filter query pattern** copy-pasted across ~6 service files.
- **`orm_dict` wrapper** in `auth.py` (dead code — just calls `orm_to_dict`).
- **`Synchronization: pass`** class in `models/attendance.py` — dead code ("Tag object").

### Inconsistencies

- **Mixed sync/async:** `sync_service.py` uses `asyncio.run()` to bridge sync→async (blocking). `ESSLService` methods are async but called from sync services.
- **Mixed commit patterns:** Some functions commit inside, others expect callers to commit. `payslip_service.py` uses `with db.begin_nested():`; others don't use nested transactions at all.
- **Inconsistent serialization:** Endpoints use `orm_to_dict()`; `employee_service.py` has `_employee_summary()`; `company_service.py` has `_summary()`.
- **`shift_work_datetime()`** is a no-op placeholder in `core/timezone.py`.
- **`services/__init__.py`** is empty — services imported via `from services import X` (fragile, relies on `sys.path` manipulation).

### Empty / Dead Code

- `models/attendance.py`: `class Synchronization: pass` (dead).
- `auth.py`: local `orm_dict()` wrapper (dead).
- `core/timezone.py`: `shift_work_datetime()` no-op.
- `backend/app/api/v1/` dead layer **already deleted** (commit f74fd77).
- `backend/app/schemas/` dead layer **already deleted** (commit f74fd77).

---

## 7. Dependencies

### Frontend (`package.json`)

| Package | Version | Concern |
|---|---|---|
| `next` | 16.3.5 | Very new (Oct 2025); limited ecosystem support |
| `react` / `react-dom` | 19.2.8 | React 19 still in early adoption |
| `tailwindcss` / `@tailwindcss/postcss` | ^4 | Tailwind CSS 4 — major version, new API |
| `eslint` | ^9 | Major version |
| `@playwright/test` | ^1.63.0 | Stable |
| `typescript` | ^5 | OK |
| `dotenv` | ^18.0.3 | Used only by `playwright.config.ts` |

**No backend lock file** (`requirements.txt` has no `requirements.lock`, `Pipfile.lock`, or `poetry.lock`). Transitive dependency versions are not pinned — builds are not reproducible. Known vulnerability scanning (e.g., `pip-audit`, `safety`) is not configured.

### Backend (`requirements.txt`) — No lock file

| Package | Version | Concern |
|---|---|---|
| `fastapi` | 0.115.6 | Stable, slightly behind latest |
| `sqlalchemy` | 2.0.36 | Behind 2.0.37+ (includes fixes) |
| `pydantic` | 2.10.4 | Behind 2.10.6 (security fixes) |
| `pydantic-settings` | 2.7.0 | Matches pydantic |
| `psycopg2-binary` | 2.9.10 | Stable |
| `PyJWT` | 2.10.1 | Stable |
| `bcrypt` | 4.2.1 | Stable |
| `APScheduler` | 3.11.0 | Stable |
| `loguru` | 0.7.3 | Stable |
| `reportlab`, `openpyxl`, `python-multipart`, `httpx`, `tenacity`, `email-validator` | — | Stable |
| `pytest`, `pytest-asyncio`, `aiosqlite`, `greenlet`, `alembic` | — | Test / migration stack |

### Stack Risk

The combination **Next.js 16 + React 19 + Tailwind CSS 4** is an extremely new stack (all released late 2025). Limited community plugins, potential edge cases, and rapid upstream changes. Not inherently broken, but higher maintenance risk than a mature stack.

---

## 8. Testing

### Backend (40 integration tests, 0 unit tests)

- `tests/conftest.py` (212 lines): Creates a fresh SQLite DB (`test_hrms.db`) per test, defines fixtures (`superadmin`, `company`, `make_user`, etc.).
- **40 tests** via `pytest` (verified: `40 passed`). Test files: `test_api_auth.py`, `test_attendance_service.py`, `test_payroll_loan_service.py`, `test_leave_service.py`, `test_essl_protocol.py`, `test_essl_pull.py`, `test_api_company_flow.py`, `fake_zk_device.py`.
- **~90% of endpoints and services have ZERO test coverage** — employees, payroll, companies, shifts, leaves, loans, payslips, overtime, holidays, reports, audit, devices, integrations_essl, users, dashboard, tasks, calculator, services have no tests.
- No unit tests (all are integration tests using the real database). No mocking of external services (eSSl mock is in-memory).
- `conftest.py` sets `ESSL_MOCK_MODE=true` for tests.

### Frontend E2E (Playwright)

- 4 spec files: `login.spec.ts` (4 tests), `dashboard.spec.ts`, `navigation.spec.ts`, `responsive.spec.ts`.
- `tests/e2e/helpers.ts`: `loginAs` helper, credential-gated via `E2E_PASSWORD` env var.
- Baseline: 56/56 passing (as of 2026-09-23).
- **No React component unit tests** — no `@testing-library/react` or `jest`.

---

## 9. Configuration & Deployment

### Deploy Paths

1. **Render (current):** Vercel frontend + Render backend + Render Postgres. Both auto-deploy on `main`.
2. **Docker Compose:** `docker-compose.yml` — Postgres 16 + backend + frontend + Caddy. Local/VM deployment (`docs/DEPLOY.md`).
3. **Kubernetes:** `deploy/k8s/` — namespace, backend (1 replica), frontend (2 replicas), postgres statefulset, ingress, secrets/configmaps. All `imagePullPolicy: IfNotPresent`; all secrets are `CHANGE_ME_*` placeholders.

### Notable Config Issues

- **No health check for backend** in `docker-compose.yml` (Postgres has one).
- **`runAsNonRoot: true`** in K8s deployments but **no non-root user in Dockerfiles** — Docker containers still run as root.
- **`CORS_ORIGINS` default includes `localhost`** in `config.py` — should be restricted in production.
- **`@app.on_event("startup")` / `@app.on_event("shutdown")`** is deprecated FastAPI API — should use lifespan handlers.
- **`redoc_url=None`** — Redoc disabled (only Swagger UI available, and it's unauthenticated).
- **Frontend `next-env.d.ts`** and `app/` route manifest are gitignored (correct).
- **`backend/` root has `.env` with real secrets on disk** but gitignored — not in git history.

### Local Dev Setup (from README)

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                    # edit backend/.env (SQLite fine for dev)
$env:PYTHONPATH = "$PWD\app"            # macOS/Linux: export PYTHONPATH="$PWD/app"
python -m uvicorn main:app --reload --port 8000
```

Verified: this command boots the API and serves `/api/v1/health` → 200 with `mock_mode: true`.

---

## 10. Recommendations (Prioritized)

### Immediate (Critical)

1. **Rotate all secrets** in `backend/.env`: JWT_SECRET, Supabase service role key, Supabase anon key, Render API key, database credentials. Delete `backend/.env` from the working machine.
2. **Remove hardcoded passwords** (`"changeme"` in `auth.py:113`, `"Welcome@123"` in `users.py:30`) — generate random passwords or require user-set-on-first-login.
3. **Enable SSL verification** (`verify=True`) in `integrations/essl/client.py` and `connector/essl_client.py`.
4. **Fix the IN/OUT event-type inconsistency** between `pulldevice.py` and `client.py` — one path is inverted and will corrupt attendance data.
5. **Fix `User.default_company_id`** — add the column to the model or remove the assignment in `core/deps.py`.
6. **Add rate limiting** to auth endpoints (login, register) — use `slowapi` or reverse-proxy rate limiting.
7. **Restrict CORS** — remove `allow_origin_regex` for `http://localhost:\d+`, set explicit origins, remove `allow_methods=["*"]` and `allow_credentials=True` together.
8. **Add authentication to `/api/docs`** (Swagger UI) or remove it from production.

### High Priority

9. **Add security headers** middleware (X-Content-Type-Options, HSTS, CSP, X-Frame-Options).
10. **Add CSRF protection** for state-changing operations.
11. **Reduce access token expiry** to 15–60 min; implement a refresh token mechanism (config already has `REFRESH_TOKEN_EXPIRE_DAYS` but no implementation).
12. **Replace `eval()`** in `payroll/calculator.py` with a safe formula parser (e.g., `ast.literal_eval` + whitelist, or a small expression parser).
13. **Replace XOR "encryption"** in `integrations/essl/config.py` with `cryptography.fernet`.
14. **Set `ESSL_MOCK_MODE=false` explicitly** for production deployments and validate at startup.
15. **Add input validation** via Pydantic models instead of `body: dict` in `users.py` and `auth.py`.
16. **Add password strength validation** on registration and password change.
17. **Fix `imagePullPolicy`** to `Always` in all K8s deployments.
18. **Remove hardcoded production URLs** from `frontend/Dockerfile` and `frontend/playwright.config.ts`.

### Medium Priority (Architecture & Quality)

19. **Resolve the `calculator.py ↔ services` circular dependency** — extract a pure-math `payroll/calculator.py` that takes values as arguments (no service imports); move service calls to the endpoint layer.
20. **Fix `services/__init__.py`** — either export key services properly or remove the empty file; replace fragile `from services import X` with proper package imports.
21. **Split `employee_service.py`** (502 lines) into `employee_crud.py`, `employee_salary.py`, `employee_device.py`, `employee_essl.py`.
22. **Split `calculator.py`** (563 lines) into `calculator.py` (core math), `statutory.py` (PF/ESI/PT/TDS), `lop.py` (LOP).
23. **Extract shared frontend patterns** — the load/submit/table pattern duplicated across 8+ pages into a shared hook or base component; create a `lib/types.ts` for API response types; move inline CSS animations to Tailwind or a CSS file.
24. **Abstract `CrudPage.tsx` usage** — apply it to the 6+ pages that still copy-paste the CRUD pattern, or unify them all under one shared component.
25. **Extract `_round2()`**, `_to_date()`, pagination pattern into `backend/app/core/utils.py`.
26. **Remove dead code** — `Synchronization` class, `orm_dict` wrapper, `shift_work_datetime()` no-op, `models/attendance.py` `Synchronization`.
27. **Add non-root user** to Dockerfiles.
28. **Replace `@app.on_event`** with FastAPI lifespan handlers.
29. **Add `SECURE` cookie / token storage** consideration and document auth transport assumptions.
30. **Add `requirements.lock`** (e.g., `pip-compile` or `poetry.lock`) for reproducible builds; run `pip-audit`/`safety`.

### Low Priority (Maintainability)

31. **Add backend unit tests** for services, calculator, core modules (target 80% coverage).
32. **Add React component unit tests** with `@testing-library/react`.
33. **Replace `models/__init__.py`** bare `from models.*` with explicit relative imports.
34. **Add `LoanInstallment.status` as `LoanStatus` enum** instead of `String(20)`.
35. **Add `TimestampMixin`** to `AttendanceLog`, `AuditLog`, `DeviceSyncLog`, `PayrollComponent`, `Payslip` (or document the intentional omission).
36. **Create `department_service.py`** for the `organization.py` endpoint.
37. **Add K8s NetworkPolicy** and resource quotas.
38. **Add liveness/readiness probes** for the backend in `docker-compose.yml`.
39. **Add `playwright.config.ts` env var override** for baseURL (already supported, but the default is a hardcoded prod URL).
40. **Document `frontend/AGENTS.md` and `frontend/CLAUDE.md`** — currently empty/boilerplate.

---

## 11. Overall Assessment

**Strengths:**
- Clean FastAPI + Next.js stack with proper layered architecture.
- Strong RBAC with 7 roles and per-resource permission strings.
- Functional payroll engine with statutory calculations.
- eSSL device integration with dual HTTP + TCP protocol support.
- 40 passing backend integration tests + 56/56 passing E2E suite.
- Deployed and live on Render + Vercel with auto-deploy from `main`.
- Well-documented deployment runbooks (`docs/DEPLOY.md`).

**Weaknesses:**
- The project is architecturally immature with tight coupling (calculator ↔ services circular deps, fragile `sys.path` manipulation).
- Significant code duplication (8+ frontend pages, 5× `_round2()`, copy-pasted pagination).
- Several security gaps (hardcoded passwords, no rate limiting, no security headers, `verify=False`, `eval()`).
- ~90% of endpoints/services have zero test coverage.
- On-disk production secrets (gitignored, but still a local exposure risk).
- The React 19 + Next.js 16 + Tailwind 4 stack is very new and carries maintenance risk.
- `IN/OUT` event-type bug would silently corrupt attendance data if the TCP path is used in production with mock mode off.

**Bottom line:** The project is functional and deployed, but needs immediate security remediation (secrets rotation, hardcoded passwords, SSL verification, rate limiting) and architectural cleanup (circular deps, service splitting, dead code removal) before it can be considered production-hardened.
