# BillBox

BillBox is a household receipt shelf: capture a bill once, extract the useful
fields, and find it later by merchant, tag, amount or date. The product and
architecture decisions live in [`BillBox-Blueprint.md`](BillBox-Blueprint.md);
the build order and E2E checkpoints live in [`PLAN.md`](PLAN.md).

**Status:** Day 1 scaffold is in place — auth, households, RLS, PWA shell and the
Playwright harness. The Section 1 checkpoint still has to be run against a live
local Supabase and deployed to Cloud Run and Cloudflare Pages.

## Stack

| Layer | Choice |
| --- | --- |
| Frontend | React 19 + Vite + TypeScript, Tailwind CSS, PWA via `vite-plugin-pwa`, Cloudflare Pages |
| Backend | FastAPI (Python 3.12), Cloud Run `asia-south1`, max 2 instances |
| Data and auth | Supabase free tier: Postgres, private Storage, email/password auth |
| AI | Gemini `gemini-3.8-flash` (Section 2+) |
| Tests | pytest for the API, Playwright for the PWA, axe-core for accessibility |

The API is the only writer. Browsers receive the anon key and can `select` rows
their household owns; every create, join, upload and tag change goes through
FastAPI with the service-role key and an explicit membership check.

## Layout

```
frontend/            React PWA, Playwright config and e2e/
backend/             FastAPI app, unit tests and API-level e2e/
supabase/            migrations, RLS/storage, seed and local config
.github/workflows/   ci.yml, e2e.yml, keepalive.yml
.env.example         backend + frontend values in one place
.env.e2e.example     harness values (copy to .env.e2e)
```

## Local setup

Prerequisites: Node 22+, Python 3.12+, npm, and Docker (required by the Supabase
CLI). The Supabase CLI is used through `npx`; no global install is needed.

### 1. Start Supabase

```powershell
npx supabase start
npx supabase db reset
```

`db reset` applies every migration and then `supabase/seed.sql`, which seeds the
15 system bill-type tags and the `heartbeat` row.

### 2. Configure the apps

`npx supabase status -o env` prints the local keys. Map them as follows:

| Supabase status | Environment variable |
| --- | --- |
| `API_URL` | `SUPABASE_URL` / `VITE_SUPABASE_URL` |
| `ANON_KEY` | `SUPABASE_ANON_KEY` / `VITE_SUPABASE_ANON_KEY` |
| `SERVICE_ROLE_KEY` | `SUPABASE_SERVICE_ROLE_KEY` (backend only) |
| `JWT_SECRET` | `SUPABASE_JWT_SECRET` (legacy HS256 local tokens) |

Backend (`backend/.env` or exported variables):

```dotenv
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_ANON_KEY=<anon key>
SUPABASE_SERVICE_ROLE_KEY=<service-role key>
SUPABASE_JWT_SECRET=<jwt secret>
ENVIRONMENT=local
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Frontend (`frontend/.env.local`):

```dotenv
VITE_SUPABASE_URL=http://127.0.0.1:54321
VITE_SUPABASE_ANON_KEY=<anon key>
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Never put `SUPABASE_SERVICE_ROLE_KEY` in a `VITE_*` variable; Vite ships those to
the browser.

### 3. Run the API

```powershell
py -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -e "backend[dev]"
Set-Location backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Health check: <http://127.0.0.1:8000/health>. Local OpenAPI docs:
<http://127.0.0.1:8000/docs>.

### 4. Run the PWA

```powershell
Set-Location frontend
npm install
npm run dev
```

Open <http://127.0.0.1:5173>. Sign up, create a household, then use the invite
code from the Household screen to join from a second account.

## Checks

```powershell
# Backend
backend\.venv\Scripts\python.exe -m ruff check backend
backend\.venv\Scripts\python.exe -m pytest backend -q

# Frontend
Set-Location frontend
npm run typecheck
npm run build
```

Unit and fast API tests use an in-memory repository and need no database.

## E2E harness

The harness expects a local Supabase, uses the service role only in test
fixtures, and never writes to production.

```powershell
Copy-Item .env.e2e.example .env.e2e
# Fill SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY and
# SUPABASE_JWT_SECRET from `npx supabase status -o env`.

Set-Location frontend
node node_modules/@playwright/test/cli.js install chromium webkit
npm run e2e          # desktop-chromium, mobile-chrome, mobile-safari
npm run e2e:ui       # interactive runner
npm run e2e:list     # list tests without starting anything
```

The scripts call the local Playwright CLI directly because, on some Windows
machines, a Python `playwright.exe` on `PATH` shadows npm's shim.

API-level E2E loads `.env.e2e` on its own:

```powershell
$env:RUN_E2E = "1"
backend\.venv\Scripts\python.exe -m pytest backend -m e2e -q
```

E2E-1.7 is skipped until `E2E_DEPLOYED_APP_URL` and `E2E_DEPLOYED_API_URL` are
set in `.env.e2e`.

Artifacts on failure: trace, screenshot, video and an HTML report under
`frontend/test-results/` and `frontend/playwright-report/`. Both are gitignored.

## CI

- `ci.yml` runs backend lint/unit tests and the frontend typecheck/build on every
  push to `main` and every pull request.
- `e2e.yml` starts local Supabase with Docker, applies migrations, runs the
  pytest E2E suite and the Playwright suite, and uploads the report on failure.
  It runs on pull requests, pushes to `main` and nightly.
- `keepalive.yml` selects the `heartbeat` row every two days so the free
  Supabase project does not pause. Add `SUPABASE_URL` and `SUPABASE_ANON_KEY` as
  repository secrets.

## Deployment

### Supabase

Create a project, then:

```powershell
npx supabase link --project-ref <project-ref>
npx supabase db push
```

Keep email confirmation off for the MVP, keep the `receipts` bucket private, and
copy the URL, anon key and service-role key into the secret stores below.

### Backend — Cloud Run

```powershell
gcloud run deploy billbox-api --source backend `
  --region asia-south1 --allow-unauthenticated `
  --memory 512Mi --cpu 1 --concurrency 2 --max-instances 2 `
  --timeout 300 --port 8080 `
  --set-env-vars "ENVIRONMENT=production,CORS_ORIGINS=https://<pages-domain>" `
  --set-secrets "SUPABASE_URL=...,SUPABASE_SERVICE_ROLE_KEY=...,SUPABASE_JWT_SECRET=..."
```

Do not set `SUPABASE_JWT_SECRET` when the project uses asymmetric signing keys
and JWKS; the API then verifies signatures against
`<SUPABASE_URL>/auth/v1/.well-known/jwks.json`. See the runbook in `PLAN.md` for
the full GCP setup, billing alerts and Gemini secrets.

### Frontend — Cloudflare Pages

- Build command: `npm run build` (root directory `frontend`)
- Output directory: `dist`
- Environment: `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`,
  `VITE_API_BASE_URL`
- `frontend/public/_redirects` supplies the SPA fallback.

### Deployed smoke

Set the two deployed URLs in `.env.e2e` and rerun the harness:

```dotenv
E2E_DEPLOYED_APP_URL=https://<pages-domain>
E2E_DEPLOYED_API_URL=https://<cloud-run-url>
```

## Safety rules

- No real bills, names, addresses or account numbers in git. Use only synthetic
  fixtures. `evals/` is gitignored.
- The `receipts` Storage bucket is private; page images are served through
  short-lived signed URLs (Section 2).
- Direct browser access is SELECT-only under RLS. All writes are validated by
  FastAPI.
- The household cap is 8, enforced by the API and by a database trigger.
- Live Gemini runs are manual or nightly with a separate key, never on pull
  requests.
