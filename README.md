# Genetics Meditech — Attendance · Payroll · HR

HR + Attendance + Payroll management SaaS with official **eSSL eTimeTrackLite** and **AI-FACE-ORCUS** device integration.

- **Backend** — FastAPI (`backend/`), 31 tables, RBAC, audit trail, eSSL sync (mock mode), reports & payslips.
- **Frontend** — Next.js 16 + Tailwind v4 (`frontend/`), 19 routes covering employees, attendance, leaves, overtime, loans, payroll, payslips, reports, settings, users and audit.
- **Database** — SQLAlchemy 2.0 models with Alembic migrations; SQLite default, Postgres/Supabase supported.

## Repo layout

```
backend/
  app/
    api/v1/          # FastAPI routers (auth, companies, employees, attendance, payroll, …)
    core/            # config, database, rbac, errors, migrations
    models/          # 31 SQLAlchemy models
    services/        # business logic (attendance, leave, payroll, loan, eSSL…)
    tasks/           # background scheduler
  alembic/           # migration scripts (env.py binds to app metadata)
  scripts/smoke_api.py
  tests/             # pytest suite (API + service level)
frontend/
  app/               # Next.js App Router pages
  components/        # Shell, CRUD primitives, UI kit
  lib/api.ts         # typed HTTP client + download helper
docs/                # API contract and database design
```

## Prerequisites

- Python 3.13+ and Node 22+
- Windows PowerShell / Linux shell

## Backend

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# set PYTHONPATH so `services`, `core`, `models` importable (package root is backend/app)
$env:PYTHONPATH = "$PWD\app"      # macOS/Linux: export PYTHONPATH="$PWD/app"

python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

On startup the app applies schema via Alembic (`alembic upgrade head`); pre-existing
`create_all` databases and missing-alembic setups fall back to `metadata.create_all`.

Configuration lives in `backend/.env.example` (copy to `backend/.env`). Use
`ESSL_MOCK_MODE=true` for device mocks; real eSSL credentials are never committed.

### Seed / smoke test

```bash
cd backend
$env:PYTHONPATH = "$PWD\app"
python scripts/smoke_api.py      # 44 end-to-end checks (creates smoke demo data)
```

### Tests

```bash
cd backend
$env:PYTHONPATH = "$PWD\app"
python -m pytest                  # 23 tests (API flows + services), uses test_hrms.db
```

### Migrations

```bash
cd backend
$env:PYTHONPATH = "$PWD\app"
python -m alembic upgrade head          # apply
python -m alembic revision --autogenerate -m "describe change"   # new migration
```

## Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
# or production: npm run build && npm start -- -p 3000
```

`NEXT_PUBLIC_API_URL` (default `http://localhost:8000`) points the UI at the API.

Default UI login after seeding: `hr@smoke.com` / `Hr123456` (company admin).

## API

Interactive docs at `http://127.0.0.1:8000/api/docs`; concise contract in `docs/api.md`.

Responses use an envelope: success `{"success": true, "data": …}`, error
`{"error": {"code", "message"}}`.

## Key conventions

- Multi-tenant by `company_id`, enforced server-side via `core/rbac.py`
  (`ensure_perm`, `resolve_company_id`).
- eSSL integration is mock-driven (`ESSL_MOCK_MODE`) — only documented device
  endpoints are called; raw credentials are filtered from API responses.
- Payroll period lifecycle: `DRAFT → CALCULATING → REVIEW → APPROVED → LOCKED`.
- UI routes are static client components (Next 16 — see `frontend/AGENTS.md` for
  the breaking-changes notes used while building).