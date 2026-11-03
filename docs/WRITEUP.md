# BillBox — portfolio write-up

BillBox is a mobile-first PWA that keeps a household's bills searchable instead
of lost in a drawer. A member photographs a bill or uploads a PDF, the API
extracts the useful fields, and everyone in the household can find it later by
merchant, tag, amount, date or a natural phrase such as “electricity over 5000
last month”.

The product brief and architecture decisions are in
[`../BillBox-Blueprint.md`](../BillBox-Blueprint.md); the implementation plan and
E2E checkpoints are in [`../PLAN.md`](../PLAN.md).

## Why this project

Household paperwork fails in three predictable ways:

1. It is captured in the wrong place (a camera roll, a chat thread, a drawer).
2. It is readable by one person but not the rest of the household.
3. It is impossible to search six months later, especially across English,
   Hindi and Marathi labels.

BillBox is deliberately narrow: one household, one receipt shelf, fast capture
and a search box that accepts the way people actually describe bills.

## What it does

- **Capture** — camera or gallery upload, up to 10 images or one PDF, client-side
  compression, 25 MB total cap, page reorder and remove before upload.
- **Extraction** — one Gemini call per bill returns merchant, amount, date,
  bill type, line items and a confidence score; every field stays editable.
- **Privacy choice** — “Skip AI” stores the bill without sending it to Gemini,
  for Aadhaar, PAN, bank statements and other sensitive documents.
- **Tags** — deterministic rules run before the model, so common merchants and
  bill types are consistent; AI and user tags are kept with their source.
- **Search** — keyword search over titles, merchants, raw text and multilingual
  tag labels, plus tag chips, amount phrases, date phrases, sorting and
  pagination. URL state survives reload and back/forward.
- **Household** — invite-code join, owner-only rotation, eight-member cap and
  strict household scoping on every API route.
- **Offline capture** — a bill captured without a connection is stored in a
  user-scoped IndexedDB queue and uploaded automatically when the browser comes
  back online. A header banner shows the queue, retries and discard controls.
- **Export** — a ZIP containing `receipts.csv` and the original pages.
- **PWA** — installable shell, offline app shell, bottom navigation, safe-area
  insets and a “waking up the server” state for free-tier cold starts.

## Architecture

```
React 19 + Vite PWA  ──►  FastAPI (Cloud Run)  ──►  Supabase Postgres
        │                        │                   private Storage
        │                        └──► Gemini         Auth (JWT)
        └── Supabase anon key (SELECT under RLS)
```

The API is the only writer. The browser receives the anon key and can read rows
its household owns under RLS, but every create, join, upload, edit, tag and
delete goes through FastAPI with the service-role key and an explicit membership
check. Storage stays private; pages are served through short-lived signed URLs.

### Free-tier decisions that shaped the design

- **No background workers.** Gemini runs synchronously in a claimed receipt
  process, with a stale-claim timeout and an idempotent Retry path. This keeps
  the MVP on Cloud Run's request model and avoids a queue service.
- **Bounded uploads.** The client compresses images and enforces 10 pages /
  25 MB; the API re-validates magic bytes, page count and total size.
- **Cold starts are visible.** Requests that take longer than 1.5 s show a
  “Waking up the server” banner instead of looking frozen.
- **AI is optional per bill.** The skip-AI path is a first-class flow, not an
  error state, because the free Gemini tier may use submitted content to improve
  Google products.

## Hard parts

### Multilingual search that behaves predictably

A natural-language query is parsed into structured filters: amount comparisons,
month/year phrases, and tag labels in English, Hindi and Marathi. Tag chips are
AND filters. The subtle bug was combining the two: a query like
`q=electricity&tag=groceries` used to discard the parsed electricity tag when an
explicit chip was present. Parsed and explicit tag filters are now merged, so
text plus chip stays an AND filter.

### Offline capture without losing or duplicating bills

The queue lives in IndexedDB, scoped by user id, and stores the original files as
blobs. Reconnect sync uploads with the same multipart shape as the online path,
then starts processing. The receipt id is persisted **after** the API accepts the
upload and **before** cleanup, so a failed IndexedDB delete cannot cause a
duplicate bill on the next retry. Signing out leaves another user's queue
untouched.

### Testing an E2E suite that uses a real local Supabase

The Playwright suite runs three browser profiles against local Supabase with
mocked Gemini. A shared fixture fails a test on unexpected console errors,
page errors or 5xx responses. Expected 4xx responses (no household yet, deleted
receipt, full household) are filtered by their generic browser resource message,
while the 5xx listener stays strict. Navigation helpers scope links to the
primary nav so copy such as “Back to Home” and “Scan a bill” cannot collide with
a nav item.

The offline test drops the browser context's network, saves a synthetic bill,
asserts the queue banner, reconnects and waits for the receipt to appear. It runs
with service workers blocked so the queue is exercised rather than the cache.

## What is verified

- 63 backend unit/parser/search/API tests pass locally (8 integration tests skip
  without local Supabase).
- Frontend typecheck and production PWA build pass.
- GitHub Actions runs backend lint/tests, frontend typecheck/build, API-level
  E2E, and the Playwright suite on desktop Chromium, mobile Chrome and mobile
  Safari, nightly and on push/PR.
- Manual gates still pending: 30 real bills for extraction quality, a two-account
  household trial, live Gemini checks and deployed smoke tests.

## What I would do next

1. Run Gate 1 and Gate 2 on real, consented household bills and record the
   extraction metrics.
2. Deploy the API to Cloud Run and the PWA to Cloudflare Pages, then run the
   deployed smoke test.
3. Add Lighthouse CI to the frontend job for the installability and performance
   budget.
4. Add server-side idempotency keys for uploads so even a pathological retry
   cannot duplicate a receipt.
5. Add member removal and account deletion before a public launch.

## Links

- [README](../README.md) — setup, checks and deployment
- [PLAN.md](../PLAN.md) — build order, E2E checkpoints and runbook
- [DEMO.md](DEMO.md) — demo storyboard and capture instructions
