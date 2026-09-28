# Frontend — Attendance · Payroll · HR UI

Next.js 16 (App Router) + React 19 + Tailwind v4 + TypeScript. The complete project
guide (backend, env vars, deployment) lives in the root [`README.md`](../README.md).

## Quick start

```bash
npm install
npm run dev          # http://localhost:3000
```

The API base URL comes from `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).

## Routes

Pages live under `app/` (App Router). Authenticated pages are grouped in `app/(app)/`
and wrapped by `components/Shell.tsx`. `app/page.tsx` redirects to `/dashboard` or
`/login` based on the stored token.

## Structure

- `app/` — App Router pages (login + dashboard, employees, attendance, payroll, …)
- `components/ui/index.tsx` — UI primitives kit
- `components/Shell.tsx` — sidebar/app shell
- `components/CrudPage.tsx` — reusable list+form page
- `components/LoginScene.tsx` — 3D login animation
- `lib/api.ts` — typed HTTP client, auth storage, file download helpers
- `public/` — static assets
- `tests/e2e/` — Playwright E2E specs

## Scripts

| Command | Description |
| --- | --- |
| `npm run dev` | Dev server (port 3000) |
| `npm run build` | Production build |
| `npm run start` | Serve production build |
| `npm run lint` | ESLint |
| `npm run test:e2e` | Playwright end-to-end tests |

E2E setup, credentials gating and reporting: see [`docs/E2E_TESTING.md`](docs/E2E_TESTING.md).