# Genetics Meditech — Attendance · Payroll · HR

HR + Attendance + Payroll management SaaS backed by official **eSSL eTimeTrackLite**
and **AI-FACE-ORCUS** device integrations.

- **Backend** — FastAPI (`backend/`), 31 tables, RBAC, audit trail, eSSL sync
  (mock-first), payroll engine, reports and PDF payslips.
- **Frontend** — Next.js 16 + Tailwind v4 + TypeScript (`frontend/`), 16 app pages
  (employees, attendance, shifts, devices, leaves, overtime, loans, payroll,
  payslips, reports, users, audit, settings, …) plus 3D animated login.
- **Database** — SQLAlchemy 2.0 + Alembic; SQLite for local dev, Postgres for
  production (Render/Supabase supported).
- **Deployment** — Render (API), Vercel (UI), optional Docker Compose / Kubernetes
  runbooks in `docs/DEPLOY.md`.

---

## 1. Repo layout

```
backend/
  app/
    main.py               # FastAPI entrypoint (app.main:app)
    api/
      v1/router.py        # registers all routes under /api/v1
      v1/endpoints/       # 20 route modules (auth, employees, payroll, …)
      deps.py             # shared dependencies (auth, tenant scope, RBAC)
    core/                 # config, database, security, rbac, errors, audit, timezone
    models/               # SQLAlchemy models
    services/             # business logic (attendance, leave, payroll, loan, eSSL…)
    payroll/              # payroll/statutory/LOP calculation domain layer
    integrations/essl/    # eSSL eTimeTrackLite client, protocol, mock, pull device
    tasks/                # APScheduler background jobs (attendance, device sync)
    static/               # static assets (company logo for payslips)
  connector/              # standalone device-sync worker (optional, runs separately)
  tests/                  # pytest suite (API + services)
  scripts/                # seed/smoke scripts (smoke_api.py, init_db.py, …)
  alembic/                # migrations (alembic.ini at backend root)

frontend/
  app/                    # Next.js App Router pages (routes live here)
    login/page.tsx        # login page (3D scene)
    (app)/                # authenticated section: layout + 16 pages
  components/
    ui/index.tsx          # UI primitives kit (Button, Card, Input, …)
    Shell.tsx             # app shell / sidebar navigation
    CrudPage.tsx          # reusable list+form page for simple entities
    LoginScene.tsx        # 3D login animation
  lib/api.ts              # typed API client, auth storage, file download
  public/                 # static assets (logo)
  tests/e2e/              # Playwright E2E specs
  docs/                   # E2E testing guide + report

docs/                     # API contract, DB design, deployment runbook
deploy/                   # Docker Compose, Kubernetes, bootstrap/backup scripts
```

---

## 2. Prerequisites

- Python **3.13+**
- Node.js **22+** and npm
- Windows PowerShell / macOS / Linux shell

---

## 3. Backend (FastAPI)

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# Configuration
cp .env.example .env              # then edit backend/.env (SQLite is fine for dev)

# Run the API (port 8000). PYTHONPATH must include backend/app so the
# package-relative imports (`core`, `services`, ...) resolve.
$env:PYTHONPATH = "$PWD\app"      # macOS/Linux: export PYTHONPATH="$PWD/app"
python -m uvicorn main:app --reload --port 8000
```

On startup the app creates/upgrades the schema (`core/migrations.run_migrations`)
and starts the APScheduler. Health check: `http://127.0.0.1:8000/api/v1/health`.

### Backend environment variables (`backend/.env`)

| Variable | Purpose | Default (dev) |
| --- | --- | --- |
| `DATABASE_URL` | SQLAlchemy URL | `sqlite:///./hrms.db` |
| `JWT_SECRET` | Token signing secret | `change-me-in-production` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime | `1440` |
| `CORS_ORIGINS` | Allowed UI origins | `http://localhost:3000,http://localhost:3001` |
| `ESSL_MOCK_MODE` | Mock eSSL instead of real portal | `true` |
| `DEVICE_CONNECTOR_API_KEY` | Auth key for connector | `change-me-connector-key` |
| `SUPABASE_URL/_ANON_KEY/_SERVICE_ROLE_KEY` | Optional Supabase sync | — |

### Seed / smoke check

```bash
cd backend
$env:PYTHONPATH = "$PWD\app"          # same as the server run above
python scripts/smoke_api.py           # runs end-to-end API checks + demo company data
```

### Tests

```bash
cd backend
$env:PYTHONPATH = "$PWD\app"      # macOS/Linux: export PYTHONPATH="$PWD/app"
python -m pytest                  # 40 tests (API flows + services)
```

### Migrations (Alembic)

```bash
cd backend
python -m alembic upgrade head                                                # apply
python -m alembic revision --autogenerate -m "describe change"                # new
```

> The app also auto-creates tables at startup via `create_all`, so a bare SQLite
> DB works without running Alembic first.

---

## 4. Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev            # http://localhost:3000
# Production preview:
npm run build && npm start -- -p 3000
```

`NEXT_PUBLIC_API_URL` (default `http://localhost:8000`) tells the UI where the API
lives. Put a value like `https://hrms-api.example.com` in `frontend/.env` for a
non-local API. CORS on the backend must allow the UI origin.

### Signing in locally

After running `scripts/smoke_api.py`, use the seeded company admin:

- **`hr@smoke.com` / `Hr123456`** (company admin)

In production the first user registers as Super Admin, then creates the company and
its admin.

### Lint / E2E tests

```bash
cd frontend
npm run lint
npm run test:e2e                  # Playwright — see frontend/docs/E2E_TESTING.md
```

---

## 5. API

- Interactive docs: `http://127.0.0.1:8000/api/docs` (OpenAPI).
- Contract reference: `docs/api.md`; database design: `docs/database.md`.
- Response envelope — success: `{"success": true, "data": …}`; error:
  `{"error": {"code": "…", "message": "…"}}`.

---

## 6. Deployment

- **Current hosting (reference):** Vercel (UI → `https://meditech-attendance-payroll-hr.vercel.app`),
  Render (API → `https://hrms-api-4trx.onrender.com`), Render Postgres (production DB).
  Both auto-deploy from the `main` branch.
- Self-hosted options (Docker Compose on a free VM, or Kubernetes): full runbook in
  `docs/DEPLOY.md`.

---

## 7. Key conventions

- **Multi-tenant**: every record is scoped to a `company_id`; enforced server-side in
  `core/rbac.py` (`ensure_perm`, `resolve_company_id`).
- **eSSL mock-first**: `ESSL_MOCK_MODE=true` by default; real device credentials are
  never committed. Direct device pulls need TCP/UDP 4370 access to device IPs.
- **Payroll lifecycle**: `DRAFT → CALCULATING → REVIEW → APPROVED → LOCKED`.
- **Frontend structure**: pages stay under `app/` (Next.js App Router requirement);
  shared code goes in `components/`, `lib/`. See `frontend/AGENTS.md` for the
  framework-specific notes.