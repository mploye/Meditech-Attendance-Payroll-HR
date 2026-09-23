# E2E Testing Guide

End-to-end tests for the ESSL Attendance & Payroll HR web application, covering login, dashboard, navigation, and responsive behavior on production.

## Test script

    npm run test:e2e

`test:e2e` runs `playwright test` with the project setup below.

## Configuration (playwright.config.ts)

- baseURL defaults to `https://meditech-attendance-payroll-hr.vercel.app`; override with `E2E_BASE_URL`.
- testDir `./tests/e2e`; timeout 30s; expect timeout 10s.
- Runs fully parallel; 6 workers locally, 2 in CI.
- Retries: 0 locally, 2 in CI.
- Reporters: HTML (auto-open never) + list.
- Projects: `desktop` (Desktop Chrome) and `mobile` (Pixel 7).
- Artifacts on failure: screenshot, trace (on first retry), video (retained on failure).
- No webServer — tests hit the deployed backend (`https://hrms-api-4trx.onrender.com`) and the deployed frontend.

## Environment variables

Create/edit `frontend/.env`:

    E2E_EMAIL=
    E2E_PASSWORD=

Playwright auto-loads `.env`. Credential-based tests auto-skip when either variable is empty.

## Test files

| File | Coverage |
| --- | --- |
| `tests/e2e/login.spec.ts` | Form render, empty submit, invalid credentials, valid login → dashboard |
| `tests/e2e/dashboard.spec.ts` | Dashboard rendering + data |
| `tests/e2e/navigation.spec.ts` | Navigation between pages |
| `tests/e2e/responsive.spec.ts` | Desktop + mobile viewports |

`tests/e2e/helpers.ts` exposes `E2E_EMAIL_AVAILABLE` / `E2E_PASSWORD_AVAILABLE`; `login.spec.ts` and `dashboard.spec.ts` gate credential cases with `test.skip`.

## Baseline (2026-09-23)

- PASSED 56/56 on production (`npm run test:e2e`, 6 workers).
- Skipped: credential + double-login subtests (no `E2E_PASSWORD` set).
- HTML report: `frontend/playwright-report/index.html`.
- See `frontend/E2E_TEST_REPORT.md`.

### Re-verification (2026-09-23)
- Same-day re-run of the baseline suite, unchanged config (`frontend/playwright.config.ts`) and unchanged specs (`tests/e2e/`).
- PASSED 56/56 again; no failures — `frontend/test-results/.last-run.json` reports `status: "passed"` with `failedTests: []`.
- Credential + double-login subtests auto-skipped again (no `E2E_PASSWORD` set).
- Evidence: `frontend/test-results/.last-run.json` and `frontend/playwright-report/index.html`.