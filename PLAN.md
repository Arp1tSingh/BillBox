# BillBox — MVP Implementation Plan

Derived from `BillBox-Blueprint.md` · 2 Nov 2026 · @Arpit Singh

This plan turns the blueprint into a buildable five-day MVP. It records the four
open questions as decisions and calls out where the original design has to
change to work on the chosen free tiers and the current Gemini API: background
processing, request-size limits and sampling parameters.

The build is split into six sections in §12. Each section ends with an E2E
checkpoint (E2E-1.x through E2E-6.x) plus a shared R1–R6 regression suite; a
section is not done until both are green.

---

## 1. Locked decisions

| Area | Decision |
| --- | --- |
| Name | **BillBox** — PWA name, icon label, page title, README, repo folder |
| Client | React + Vite + TypeScript PWA, mobile-first |
| Backend | FastAPI (Python 3.12), containerised |
| Data and auth | Supabase free tier: Postgres, private Storage, Auth (email + password) |
| AI | Gemini `gemini-3.8-flash`, one call per bill, free tier |
| Access | Individual accounts joined to one household by invite code; cap 8 members |
| Sensitive docs | Allowed, with a **skip-AI** switch and a first-upload warning |
| Backend host | **Google Cloud Run, `asia-south1` (Mumbai)**, scale-to-zero |
| Frontend host | Cloudflare Pages (fallback: Vercel Hobby) |
| Email intake | Deferred past MVP |

### Decisions that changed the blueprint

1. **No FastAPI `BackgroundTasks`.** Cloud Run's default request-based billing
   throttles CPU after the response, so post-response work is unreliable.
   Extraction runs in a normal HTTP request: the client calls
   `POST /receipts/{id}/process` immediately after upload. The endpoint is
   idempotent and is also the Retry button.
2. **Upload cap is 25 MB total, not 10 × 10 MB.** Cloud Run rejects HTTP
   requests above 32 MiB. Client-side compression keeps 10 phone pages around
   3–5 MB; a single PDF may be up to 10 MB. Validation enforces the total.
3. **Gemini 3 does not accept `temperature`.** Use `thinking_level="low"` and
   structured output instead. The blueprint's "low temperature" rule is
   replaced.
4. **Supabase keep-alive runs from GitHub Actions**, not from the API host, so
   it does not consume Cloud Run resources or depend on a warm service.
5. **Four extra receipt columns and two extra tag columns** are needed for a
   clean implementation: `receipts.ai_skipped`, `receipts.failure_reason`,
   `receipts.processing_started_at`, `receipts.processed_at`; `tags.kind`,
   `tags.keywords`. Details in §5. These are additive, not a schema redesign.

---

## 2. Architecture

```
Browser (React PWA)
  │  Supabase Auth (email + password)        ← sign-in / JWT refresh
  │  HTTPS + Bearer JWT
  ▼
FastAPI on Cloud Run (asia-south1)
  │  service-role key, Gemini key (Secret Manager)
  ├── Supabase Postgres   ← rows, tags, full-text search
  ├── Supabase Storage    ← private bucket, signed URLs for reads
  └── Gemini 3.8 Flash    ← one multimodal call per bill
```

- The browser never receives the service-role key or the Gemini key.
- Uploads are proxied through FastAPI (per the blueprint diagram), then written
  to Storage before any AI call.
- The browser reads page images only through short-lived signed URLs.
- FastAPI verifies the Supabase JWT and resolves household membership on every
  request. RLS is defence-in-depth for any direct Supabase access.

### Request flow for a scan

```
1. Client compresses pages to ~1600 px, JPEG q≈0.82
2. POST /receipts (multipart, ≤25 MB) → store pages → rows, status=processing
3. Client POST /receipts/{id}/process → Gemini call → rules → tags → status=ready
4. Client polls GET /receipts/{id} every 2 s
5. On failure: retry with backoff inside the same request; if exhausted,
   status=failed + reason; UI shows Retry (same /process endpoint)
```

---

## 3. Stack

### Backend

| Concern | Choice |
| --- | --- |
| Framework | FastAPI + Uvicorn |
| Validation | Pydantic v2, pydantic-settings |
| Supabase | `supabase-py` async client (PostgREST + Storage); RPC for search |
| Auth | `PyJWT` + Supabase JWKS, cached; legacy HS256 secret as fallback |
| AI | `google-genai` SDK, async client |
| Uploads | `python-multipart`, `filetype` for magic-byte checks, `pypdf` for PDF page count |
| Retries | `tenacity` (429/5xx, exponential backoff) |
| Tests | `pytest`, `pytest-asyncio`, `respx` (mock Gemini), local Supabase CLI |
| Quality | Ruff, mypy (non-blocking) |

### Frontend

| Concern | Choice |
| --- | --- |
| Framework | React 19 + TypeScript + Vite |
| Routing | React Router |
| Server state | TanStack Query (polling, caching) |
| Styling | Tailwind CSS v4, custom small component set |
| Auth | `@supabase/supabase-js` |
| PWA | `vite-plugin-pwa` (autoUpdate, shell precache only) |
| Icons | lucide-react |
| Dates/amounts | date-fns; `Intl.NumberFormat('en-IN')` |

---

## 4. Repository layout

```
BillBox/
├─ frontend/
│  ├─ public/                     # icons, maskable icon
│  ├─ src/
│  │  ├─ components/              # Layout, ReceiptCard, TagChip, ...
│  │  ├─ pages/                   # Home, Scan, ReceiptDetail, Household, SignIn
│  │  ├─ lib/                     # supabase.ts, api.ts, image.ts, format.ts
│  │  ├─ hooks/                   # useHousehold, useReceipt, useSearch
│  │  └─ main.tsx / App.tsx
│  ├─ e2e/                        # Playwright specs, fixtures, helpers
│  ├─ playwright.config.ts
│  ├─ vite.config.ts
│  └─ package.json
├─ backend/
│  ├─ app/
│  │  ├─ main.py                  # app factory, CORS, error handlers
│  │  ├─ config.py                # env settings
│  │  ├─ auth.py                  # JWT verification, membership dependency
│  │  ├─ routers/                 # households.py, receipts.py, tags.py, export.py
│  │  ├─ services/                # storage.py, extraction.py, tagging.py, search.py
│  │  ├─ prompts/extract.py       # system prompt + JSON schema
│  │  └─ rules/tags_seed.py       # fixed tag set and trigger words
│  ├─ scripts/eval_extraction.py  # 30-bill quality harness
│  ├─ tests/
│  │  └─ e2e/                     # API-level E2E: auth, RLS, limits, process
│  ├─ Dockerfile
│  └─ pyproject.toml
├─ supabase/
│  ├─ migrations/                 # schema, RLS, search function, triggers
│  └─ seed.sql                    # system tags + heartbeat row
├─ .github/workflows/
│  ├─ ci.yml                      # lint + unit + build
│  ├─ e2e.yml                     # Playwright + local Supabase + mock Gemini
│  └─ keepalive.yml               # Supabase ping every 2 days
├─ evals/                         # gitignored: real bills + results
├─ .env.example
└─ README.md
```

---

## 5. Data model

Six user-data tables, plus one operational `heartbeat` table, with the
additive columns called out above.

### `households`
`id uuid pk`, `name text`, `invite_code text unique`, `created_by uuid`,
`created_at`, `updated_at`.

- Invite code: 8 characters from an unambiguous alphabet
  (`ABCDEFGHJKLMNPQRSTUVWXYZ23456789`), rotatable by the owner.

### `household_members`
`household_id`, `user_id` (FK `auth.users`), `role` (`owner` | `member`),
`created_at`, PK `(household_id, user_id)`.

- `unique (user_id)` for MVP: one household per account. Private vaults later
  are a receipt-level container, not a second membership.
- Max 8 enforced in the join endpoint; add a DB trigger if time allows.

### `receipts`
`id`, `household_id`, `created_by`, `title`, `merchant`, `amount numeric(12,2)`,
`currency char(3) default 'INR'`, `bill_date date`, `bill_type text`,
`language text`, `status` (`processing` | `ready` | `failed`), `raw_text`,
`extracted jsonb`, `search_vector tsvector`, `vault_id uuid null`,
`created_at`, `updated_at`.

Additive:
- `ai_skipped boolean default false`
- `failure_reason text` (user-safe code/message, never raw bill text)
- `processing_started_at timestamptz` (stale-lock recovery)
- `processed_at timestamptz`

### `receipt_pages`
`id`, `receipt_id`, `page_no`, `storage_path`, `mime_type`, `size_bytes`,
`created_at`; unique `(receipt_id, page_no)`.

- Images: one row per page, `page_no` 1..10.
- PDF: one row for the whole file (`page_no=1`, `mime_type=application/pdf`);
  page count validated with `pypdf` (≤10). The viewer embeds the PDF.

### `tags`
`id`, `household_id` (null = system tag), `slug`, `label_en`, `label_hi`,
`label_mr`, `kind` (`bill_type` | `merchant` | `custom`), `keywords text[]`,
`created_at`.

- Partial unique indexes: `unique (slug) where household_id is null`;
  `unique (household_id, slug) where household_id is not null`.
- System tags are `kind=bill_type` and null household. Merchant tags and
  AI/user tags are household-scoped.

### `receipt_tags`
`receipt_id`, `tag_id`, `source` (`rule` | `ai` | `user`), `confidence numeric`,
`created_at`, `removed_at timestamptz`, `removed_by uuid`; PK
`(receipt_id, tag_id)`.

- **Soft delete** implements "removal is final": re-runs skip any row that
  exists, including rows with `removed_at` set.
- User edits are never overwritten: reprocessing only replaces `rule`/`ai`
  rows that are still active.

### `heartbeat`
`id int pk default 1`, `last_ping timestamptz`. RLS: anon/authenticated
`select` allowed; writes only via service role. Used by the keep-alive cron.

### RLS and storage

- Helper `is_household_member(p_household uuid)` — `security definer`,
  `search_path = ''`, stable.
- Every table: enable RLS; allow `select/insert/update/delete` only when the
  row's household is one of the caller's memberships.
- Bucket `receipts` is private. Paths:
  `{household_id}/{receipt_id}/{page_no}-{uuid}.{ext}`.
  Storage policy checks the first path segment against membership.
- Signed URLs: 60-minute expiry, generated server-side only.

### Search vector

`search_vector` is maintained by a trigger on `receipts` and `receipt_tags`:
`to_tsvector('simple', title || merchant || raw_text || all active tag labels
(en/hi/mr))`.

Indexes:
- `gin (search_vector)`
- `gin (merchant gin_trgm_ops)` with `pg_trgm`
- `btree (household_id, bill_date desc)`
- `btree (household_id, amount)`

### Fixed tag seed

`kind=bill_type`, `household_id=null`. Hindi/Marathi labels need a native
speaker's review before launch.

| slug | English | Hindi | Marathi | example triggers |
| --- | --- | --- | --- | --- |
| electricity | Electricity | बिजली | वीज | electricity, MSEDCL, Adani Electricity, बिजली, वीज |
| water | Water | पानी | पाणी | water, पानी, पाणी |
| gas | Gas | गैस | गॅस | LPG, PNG, gas cylinder, गैस, गॅस |
| internet-phone | Internet and Phone | इंटरनेट और फ़ोन | इंटरनेट आणि फोन | broadband, recharge, postpaid, wifi |
| maintenance | Maintenance | मेंटेनेंस | देखभाल | society maintenance, मेंटेनेंस, देखभाल |
| property-tax | Property Tax | संपत्ति कर | मालमत्ता कर | property tax, मालमत्ता कर |
| electronics | Electronics and Appliances | इलेक्ट्रॉनिक्स और उपकरण | इलेक्ट्रॉनिक्स आणि उपकरणे | router, laptop, mixer, warranty card |
| medical | Medical | चिकित्सा | वैद्यकीय | pharmacy, clinic, दवाई, औषध |
| groceries | Groceries | किराना | किराणा | grocery, kirana, किराना, किराणा |
| dining | Dining | भोजन | जेवण | restaurant, cafe, dining, hotel |
| fuel | Fuel | ईंधन | इंधन | petrol, diesel, fuel, पेट्रोल, डीजल |
| insurance | Insurance | बीमा | विमा | policy, premium, बीमा, विमा |
| education | Education | शिक्षा | शिक्षण | school, tuition, fees, फीस |
| repairs | Repairs | मरम्मत | दुरुस्ती | repair, service, मरम्मत, दुरुस्ती |
| rent | Rent | किराया | भाडे | rent, lease, किराया, भाडे |

---

## 6. API

Conventions:
- `Authorization: Bearer <supabase access token>` on every request.
- `X-Household-Id` optional; resolved from membership when omitted. Reject if
  the user is not a member.
- Errors: `{ "error": { "code": "...", "message": "...", "details": {} } }`.
- All receipt routes require household membership.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/households` | Create household + owner membership |
| POST | `/households/join` | Join with invite code; reject at 8 members |
| GET | `/households/me` | Household, members, invite code |
| POST | `/households/rotate-invite` | Owner rotates the code |
| POST | `/receipts` | Multipart upload (`files[]`, `skip_ai`); returns 202 + id |
| POST | `/receipts/{id}/process` | Run extraction; idempotent; Retry/Resume |
| GET | `/receipts/{id}` | Detail, status, pages with signed URLs, tags |
| GET | `/receipts` | Search/list: `q`, `tag`, `from`, `to`, `min`, `max`, `sort`, `page`, `page_size`; cards include a batch-generated signed thumbnail URL |
| PATCH | `/receipts/{id}` | Edit `title`, `merchant`, `amount`, `bill_date` |
| DELETE | `/receipts/{id}` | Delete rows + storage objects |
| POST | `/receipts/{id}/tags` | Add tag (`tag_id` or label; creates household tag) |
| DELETE | `/receipts/{id}/tags/{tag_id}` | Soft-remove tag |
| GET | `/tags` | System + household tags, trilingual labels, counts |
| GET | `/export` | Later: ZIP of pages + CSV of fields/tags |

### Status machine

```
processing ──(process succeeds)──▶ ready
    │                                ▲
    │ (retries exhausted)            │ (skip_ai upload)
    ▼                                │
  failed ──(process / Retry)─────────┘
```

- `POST /process` atomically claims the receipt:
  `status IN ('failed','processing')` **and** (`processing_started_at IS NULL`
  or older than 5 minutes). No claim → return current status.
- `skip_ai=true`: status `ready`, `ai_skipped=true`, `extracted={"skipped":true}`;
  no Gemini call and no automatic tags — the user tags by hand. Search still
  works on any title or merchant the user enters.
- Never log `raw_text`, `extracted`, page bytes or signed URLs.

---

## 7. Capture and extraction

### Client capture
- `<input type="file" accept="image/*,application/pdf" capture="environment">`
  plus an "Add page" button. One PDF **or** up to 10 images.
- Compress images with `createImageBitmap` + canvas/OffscreenCanvas:
  long side 1600 px, JPEG quality 0.82, EXIF orientation applied; re-encoding
  also strips GPS/EXIF.
- Preview grid with remove and reorder (arrow buttons for MVP).
- Enforce per-file 10 MB and total 25 MB before upload.

### Upload
- Validate magic bytes (`filetype`): JPEG, PNG, WebP, PDF only. Reject SVG.
- Validate PDF page count ≤10 and encrypted PDFs with `pypdf`.
- Upload all pages to Storage; insert `receipts` + `receipt_pages`.
- On any failure, delete already-uploaded objects and the inserted row.
- Return `202 { id, status: "processing" }`.

### Gemini call
- Model: `gemini-3.8-flash`; `thinking_level="low"`; no `temperature`.
- One request with all page images / the PDF.
- `response_mime_type="application/json"` and a Pydantic-backed JSON schema.
- `max_output_tokens` 4096; request timeout 120 s.
- Retry 429/5xx with exponential backoff (2 s → 8 s, 4 attempts);
  do not retry 400s.

**Prompt rules**
- Give the fixed bill-type list; `bill_type` must be one of them or `null`.
- Return `null` for any unreadable field; never guess amount or date.
- Amount = final payable total (prefer "Grand Total"/"Net Payable"), not a
  line item, not the due amount.
- Date = bill/invoice date, not due date.
- Merchant = seller/utility, not the customer.
- `raw_text` in the bill's own script.
- Up to 3 short descriptive tags, not repeating `bill_type`.
- `language`: `en` | `hi` | `mr` | `mixed` | `other`.

**Response fields:** `bill_type`, `merchant`, `amount`, `currency`,
`bill_date` (`YYYY-MM-DD`), `language`, `raw_text`, `tags: string[]`.

### Tagging
1. Rules over normalized text (Unicode NFC, lowercase) against
   `tags.keywords` in all three languages. Hit → fixed tag, `source=rule`,
   confidence 1.0.
2. If no rule hit, accept AI `bill_type` only when it is in the fixed set;
   otherwise no bill-type tag.
3. Merchant normalization: trim suffixes (`Pvt Ltd`, `Ltd`, `LLP`), collapse
   whitespace, title-case; merge with an existing household merchant tag when
   trigram similarity > 0.6; otherwise create `kind=merchant`, slug + label.
4. AI descriptive tags → `kind=custom`, `source=ai`, ≤3.
5. User edits → `source=user`; removals set `removed_at` and are skipped on
   re-runs. Re-adding a removed tag clears `removed_at` and sets
   `source=user`.
6. At most one `kind=bill_type` tag per receipt; adding another replaces the
   previous one. AI tags are deduped against existing labels and never create
   a second bill-type tag.
7. `receipts.bill_type` mirrors the active fixed tag slug (null if none);
   `title` defaults to `"{merchant or bill type} — {Mon YYYY}"`.

Reprocess is offered only for failed receipts; a ready receipt is edited
directly. The soft-delete rule still protects any future reprocess path.

### Failure handling
- Pre-AI failures (storage, validation) → 4xx, no receipt row left behind.
- AI/quota failures → `failed`, `failure_reason` in user-safe terms
  ("AI quota reached", "Could not read bill"), pages intact, Retry enabled.
- Stale `processing` (no process call / interrupted) → Resume button calls the
  same endpoint after the 5-minute lock window.

---

## 8. Search

### Query parsing (server, Python)
- Amount: `over|above|more than|> N`, `under|below|less than|< N`,
  `between N and M`. Strip matched text before FTS.
- Date: year (`2025`), month + year (`Jan 2025`), `last month`, `this month`,
  `last year`. Boundaries use `Asia/Kolkata`.
- Tags: match any system tag label/keyword or household tag label in the
  remaining query (case-insensitive, phrase-aware). Matched tags become
  filters and are removed from the text query.
- Explicit query params override parsed values.
- Remaining text → full-text + merchant similarity.

### Matching and ranking (one SQL RPC)
1. **Tag match** (any selected tag present) → rank 3.
2. **Merchant** `word_similarity(q, merchant) > 0.5` → rank 2.
3. **Full text** `search_vector @@ websearch_to_tsquery('simple', q)` → rank 1.
4. Ties: `bill_date desc nulls last`, then `created_at desc`.
5. Filters: household, active tag rows, `bill_date` range, amount range.
6. Pagination: 20/page, max 50; return `total` via window function.

Multiple selected tags are **AND** (narrowing). Empty `q` returns recent
receipts. `sort=date|amount|relevance`; relevance falls back to date when `q`
is empty.

If Postgres `simple` tokenisation underperforms on Devanagari, fall back to
`ILIKE '%q%'` on `raw_text` and tag labels; keep the same ranking order.

---

## 9. Screens

1. **Sign in** — email + password; sign up; session persistence. Password reset
   deferred (Supabase free email limit: 2/hour without custom SMTP).
2. **Onboarding** — create household or join with code; clear 8-member error.
3. **Home** — search box, tag chips with counts, recent receipts, processing
   and failed cards with Resume/Retry.
4. **Scan** — camera input, add/remove/reorder pages, skip-AI toggle with
   warning, submit + progress.
5. **Receipt detail** — page viewer (images swipe/scroll; PDF embed), status,
   editable fields, tag editor, delete, source chips (`rule`/`ai`/`user`).
6. **Household** — invite code with copy/share, rotate (owner), member list.

Mobile-first: bottom navigation (Home, Scan, Household), safe-area insets,
44 px tap targets. Desktop: centred max-width layout.

PWA: manifest `BillBox`, theme colour, 192/512 + maskable icons, standalone,
`start_url=/`, offline shell fallback only (no offline capture in MVP).
Frontend SPA fallback via Cloudflare Pages `_redirects`.

---

## 10. Security and privacy

- RLS on every table and the storage bucket; service-role key only on the
  backend; Gemini key in Secret Manager.
- JWT verification: issuer/audience/expiry; JWKS cached; 401 → client refresh
  and one retry.
- Upload allow-list by magic bytes; 10 MB/file, 25 MB/request, 10 pages.
- Signed URLs 60 min; no public bucket; no signed URLs in logs.
- No extracted text, raw text, or image bytes in logs. Log
  `receipt_id`, `household_id`, status, latency, error class.
- CORS: exact origins (`localhost:5173`, Pages domain, custom domain).
- Free-tier Gemini: submitted content may be used to improve Google products
  and read by human reviewers. The skip-AI switch is the mitigation; the UI
  warns before the first AI upload. Paid-tier switch is a one-function change.
- Do not scan Aadhaar/PAN/bank statements with AI on; the warning says so.
- Client-side image re-encoding strips EXIF/GPS.
- Delete receipt removes storage objects first, then the DB row (cascades).

---

## 11. Free-tier operations

### Cloud Run
- Free tier: 2M requests + 180k vCPU-seconds/month; a billing account and card
  are required.
- `asia-south1`, min instances 0, max instances 2, 1 vCPU / 512 MiB,
  concurrency 2, request timeout 300 s.
- Accept 2–5 s cold starts; UI shows a "waking up" state after 1.5 s.
- Budget alert (₹100, 50/90/100%); alerts do not cap spend, so max instances
  and timeouts are the real guard.
- Artifact Registry cleanup: keep the last 2 images to stay near the 0.5 GB
  free allowance.
- 32 MiB request limit → 25 MB upload cap (see §1).

### Supabase
- Free: 500 MB DB, 1 GB storage, 5 GB egress, pause after ~1 week of low DB
  activity.
- GitHub Actions cron every 2 days: `select` on `heartbeat` via PostgREST with
  the anon key. A select is enough DB activity.
- Warn: GitHub disables scheduled workflows after 60 days of repo inactivity;
  add an external uptime ping as a backup if the project goes quiet.
- Weekly export once the export endpoint exists; keep the SQL migrations in
  git as the schema backup.
- Auth: disable email confirmation for MVP (free email limit 2/hour); add
  custom SMTP before real onboarding.

### Gemini
- Retry/backoff on 429; show "processing" while queued.
- Free-tier per-minute and per-day caps apply per project, not per key.
- Confirm `gemini-3.8-flash` is in the free tier at setup; fallback
  `gemini-3.6-flash`, then `gemini-3.5-flash-lite`.

---

## 12. Build sections and E2E checkpoints

The build is split into six sections. Each section ends with an **E2E
checkpoint**; a section is not done until its checkpoint and the regression
suite pass. Checkpoints are automated except where marked **manual** (real
phone camera, live Gemini, household trial).

### 12.0 E2E harness

- **Tooling:** Playwright in `frontend/e2e/` with `desktop-chromium`,
  `mobile-chrome` (Pixel 5) and `mobile-safari` (iPhone 13), plus axe-core for
  accessibility; API-level E2E in `backend/tests/e2e/` with `pytest`.
- **Environment:** local Supabase (`supabase start`), FastAPI with
  `ENVIRONMENT=test`, Vite preview, `GEMINI_MOCK=1`. Automated tests never
  write to production; live-Gemini checks are manual or nightly with a
  separate key, and the deployed smoke is a read-only health check.
- **Mock extraction:** a deterministic `ExtractionProvider` selected by
  `GEMINI_MOCK=1`; the test-only seed endpoint is enabled only when
  `ENVIRONMENT=test`.
- **Fixtures:** synthetic English, Hindi and Marathi bills, a PDF, a `.txt`
  file and an oversized file in `frontend/e2e/fixtures/`. No real bill is
  committed.
- **Accounts:** `owner`, `member`, `outsider` seeded per run; each test creates
  a unique household; cleanup via the service role.
- **Commands:** `npm run e2e`, `npm run e2e:ui`, `pytest -m e2e`.
- **Artifacts:** trace, screenshot and video on failure; HTML report in CI.
- **Pass rule:** all tests green on desktop and mobile, no console errors and
  no 5xx responses.

### Section 1 — Day 1: Setup, auth and household

Build:
- [x] Repo scaffold, `.env.example`, README, CI skeleton with an E2E job.
- [ ] Supabase project, migrations, RLS, storage bucket, system-tag seed,
      heartbeat table.
- [x] FastAPI skeleton: config, health check, JWT dependency, membership
      resolution, error handler, CORS.
- [x] Household endpoints: create, join (cap 8), me, rotate invite.
- [x] React/Vite/PWA shell, Tailwind, Supabase auth, sign-in/up, onboarding.
- [ ] Deploy backend to Cloud Run and frontend to Cloudflare Pages early.

> **Day 1 status:** scaffold, migrations, API and PWA are in place. The
> migrations, RLS policies, storage read policy and member-cap trigger pass in
> an embedded Postgres check. A live Supabase instance, E2E-1.1–1.7, R1–R6 and
> both deployments are still pending; the checkpoint stays open until they
> pass.

E2E checkpoint:

| ID | Scenario | Expected |
| --- | --- | --- |
| E2E-1.1 | Sign up, reload, sign out | Lands on onboarding; session survives reload; sign-out returns to sign-in |
| E2E-1.2 | Create household | Invite code shown; role owner; empty Home |
| E2E-1.3 | Second account joins with code | Same household; member count 2 |
| E2E-1.4 | Ninth account joins a full household | Clear "household is full" error; no membership row |
| E2E-1.5 | Outsider reads household data via UI and user-JWT API | No rows returned; 403/empty, never another household's data |
| E2E-1.6 | Keep-alive heartbeat | Anon `select` on `heartbeat` succeeds |
| E2E-1.7 | Deployed smoke | `/health` 200; app loads; no console errors |

**Exit:** all green; both deployments live.

### Section 2 — Day 2: Capture, upload and processing

Build:
- [ ] Scan screen: camera/file inputs, multi-page, compression, reorder,
      remove, skip-AI toggle.
- [ ] Upload endpoint: validation, Storage writes, rows, 25 MB cap, PDF pages.
- [ ] Process endpoint: atomic claim, idempotency, stale lock, skip-AI path.
- [ ] Gemini client: prompt, schema, retry, mock mode for local dev.
- [ ] Detail screen: signed-URL page viewer, processing/failed/ready states,
      polling, Retry/Resume.
- [ ] Deploy and smoke-test on a phone.

E2E checkpoint:

| ID | Scenario | Expected |
| --- | --- | --- |
| E2E-2.1 | Upload one image | Preview, processing, then ready; page image renders |
| E2E-2.2 | Upload three images, reorder, remove one | Two pages stored in the chosen order |
| E2E-2.3 | Upload a PDF | One page row; PDF viewer loads; receipt ready |
| E2E-2.4 | Upload `.txt`, 11 pages, and >25 MB | Each rejected with a clear message; nothing stored |
| E2E-2.5 | Skip-AI upload | No Gemini call; ready; `ai_skipped`; manual tag works; no auto tags |
| E2E-2.6 | Forced extraction failure, then Retry | Failed + user-safe reason; Retry with mock success → ready |
| E2E-2.7 | Double-click process; backdated stale processing row | One Gemini call; stale row resumes after the 5-minute lock |
| E2E-2.8 | Signed page URL | Valid URL loads; expired or tampered URL fails |
| E2E-2.9 | Mobile capture input | `capture=environment`; `accept` allows images/PDF; file chooser works |
| E2E-2.10 | Failed upload cleanup | No orphan receipt rows or storage objects |

**Exit:** all green; no lost uploads.

### Section 3 — Day 3: Extraction quality, tagging and Gate 1

Build:
- [ ] `scripts/eval_extraction.py`; run 30 real bills (English, Hindi,
      Marathi, faded).
- [ ] Iterate prompt, image compression and preprocessing on failures.
- [ ] Rules tagging, merchant normalization, tag persistence, manual tagging.
- [ ] Record per-bill predictions vs. manual truth in `evals/results.csv`.

E2E checkpoint:

| ID | Scenario | Expected |
| --- | --- | --- |
| E2E-3.1 | **Manual/nightly:** live Gemini on 3 bills | Amount, date and merchant populated; latency recorded; no parse error |
| E2E-3.2 | Malformed or partial mock JSON | Receipt fails cleanly or nulls fields; no crash or partial write |
| E2E-3.3 | Rules on "MSEDCL" and "पाणी" | Electricity and Water tags, `source=rule` |
| E2E-3.4 | Merchant variants "Croma Pvt Ltd" / "Croma" | One merged merchant tag; "Adani Elec" is similar to "Adani Electricity" |
| E2E-3.5 | Edit fields and tags; reload; retry a failed receipt | Field edits persist on reload; user tags survive the retry |
| E2E-3.6 | Remove a tag, then re-add it | Tag disappears; re-adding it works with `source=user`; the integration test confirms a re-run cannot restore a removed tag |
| E2E-3.7 | Skip-AI receipt | No automatic tags; manual tags and search by entered title work |
| E2E-3.8 | **Manual:** 30-bill eval | Results CSV filled; Gate 1 metrics computed |

**Gate 1 (end of day 3):** on 30 real bills —
- ≥90% return valid JSON;
- ≥80% amount correct;
- ≥80% bill_date correct;
- ≥70% bill_type correct or correctly null;
- ≥90% raw_text non-empty and contains the merchant;
- median latency <15 s, p95 <30 s.
If below, fix extraction before search; if only one field is weak, ship it
editable and continue.

### Section 4 — Day 4: Tags, search, home and results

Build:
- [ ] Tags API and counts; add/remove with soft-delete semantics; bill_type
      sync.
- [ ] Search parser + SQL RPC + indexes + ranking.
- [ ] Home: search, tag chips, recent receipts, processing/failed states.
- [ ] Results: filters (tag/date/amount), sort, pagination, empty states.

E2E checkpoint:

| ID | Scenario | Expected |
| --- | --- | --- |
| E2E-4.1 | Search "electricity bill" | Electricity receipts first; no unrelated receipts above them |
| E2E-4.2 | Search "बिजली" and "पाणी" | Same receipts as the English equivalents |
| E2E-4.3 | Search "over 5000", "under 1000", "between 1000 and 5000" | Amount filters applied; boundary values correct |
| E2E-4.4 | Search "last month" and "2025" | Only receipts in the computed range |
| E2E-4.5 | Search "Adani Elec" | "Adani Electricity" found via trigram |
| E2E-4.6 | Select Electricity + Groceries chips, then clear | AND semantics; clear resets the list |
| E2E-4.7 | 25 seeded receipts, sort and paginate | No duplicates; order matches sort; page count correct |
| E2E-4.8 | Empty result, URL state, browser back | Helpful empty state; query survives reload and back/forward |
| E2E-4.9 | List thumbnails and card tap | Thumbnail loads; detail opens with the right receipt |
| E2E-4.10 | Outsider searches | Never returns another household's receipts |
| E2E-4.11 | Add, filter, remove and re-add a custom tag | All four steps reflected in list and filters |
| E2E-4.12 | Add a second bill-type tag | Previous one replaced; receipt bill_type updated |

**Exit:** all green; the search examples in §8 behave as specified.

### Section 5 — Day 5: Detail, household, PWA and Gate 2

Build:
- [ ] Detail: page viewer, inline edits, tag editor, delete.
- [ ] Household: invite code copy/share/rotate, members, cap error.
- [ ] PWA polish: icons, install prompt, bottom nav, safe areas, waking state.
- [ ] Full automated journey with 2 accounts and mocked extraction.
- [ ] Tag `v0.1`; write the release notes.

E2E checkpoint:

| ID | Scenario | Expected |
| --- | --- | --- |
| E2E-5.1 | Edit title, merchant, amount and date; reload; search | Values persist; search reflects the new merchant and amount |
| E2E-5.2 | Delete a receipt | Gone from list; detail 404; storage objects removed |
| E2E-5.3 | Copy and rotate invite code; old code; member tries to rotate | Old code rejected; new code works; member gets 403 |
| E2E-5.4 | Ninth account joins | Clear cap error |
| E2E-5.5 | PWA manifest, icons, service worker | Manifest name BillBox; icons load; service worker registered; installable (Lighthouse/manual) |
| E2E-5.6 | Mobile viewport 390×844 | No horizontal scroll; bottom nav and tap targets usable |
| E2E-5.7 | Slow API (route delay) | "Waking up" appears after 1.5 s and clears on response |
| E2E-5.8 | Full journey on desktop and mobile | Sign in → create/join → scan → search → edit tag → delete |
| E2E-5.9 | Accessibility smoke | Inputs labelled; focus visible; no critical axe violations |
| E2E-5.10 | **Manual:** Gate 2 household trial | 10 receipts from 2 accounts; metrics recorded |

**Gate 2 (end of day 5):** 10 real receipts from 2 accounts —
- ≥8/10 found via a natural query in <10 s;
- 0 lost uploads, 0 cross-household exposures;
- median processing <20 s;
- installs and runs on Android Chrome and iOS Safari;
- the household agrees to keep using it.

### Section 6 — Week 2+: Polish

Build:
- [ ] Export ZIP + CSV; tests and CI hardening; accessibility.
- [ ] Offline-friendly capture (IndexedDB queue); README, demo GIF, write-up.
- [ ] Optional later: question answering, semantic search (pgvector), email
      intake, private vaults.

E2E checkpoint:

| ID | Scenario | Expected |
| --- | --- | --- |
| E2E-6.1 | Export a household | ZIP downloads; pages + CSV present; fields and tags correct; no other household's data |
| E2E-6.2 | Offline shell (and capture queue when shipped) | Shell renders offline; queued uploads sync on reconnect |
| E2E-6.3 | Full regression + Lighthouse | All suites green; PWA installable; performance budget met |
| E2E-6.4 | **Manual/nightly:** live Gemini on 10 bills | Quality does not regress against the Gate 1 baseline |

### Regression suite (run after every section)

| ID | Regression |
| --- | --- |
| R1 | Sign in, session refresh, sign out |
| R2 | Cross-household isolation via UI and user-JWT API |
| R3 | Upload validation, 10-page and 25 MB limits |
| R4 | Process idempotency, failure/Retry, skip-AI |
| R5 | Search smoke: one keyword, one tag, one amount |
| R6 | No console errors and no 5xx during the run |

No section starts until the previous checkpoint and R1–R6 are green.

### Test data policy

- Synthetic fixtures only; no real bills, names or account numbers in git.
- `evals/` is gitignored; real bills stay on the tester's machine.
- Live Gemini runs are manual or nightly, never on pull requests.
- Test-only seed and mock endpoints are disabled unless `ENVIRONMENT=test`.

---

## 13. Test strategy

E2E coverage is defined per section in §12. This table covers the other layers.

| Layer | Scope | Tooling |
| --- | --- | --- |
| Unit | query parser, merchant normalization, slug/dedup, tag rules, prompt builder, status transitions | pytest |
| API integration | upload → process → ready, failure/retry, skip-AI, tag removal (a re-run cannot restore a removed tag), member cap, upload limits | pytest + httpx + local Supabase |
| RLS/security | two households via user JWTs, storage policy, signed URL expiry, JWT tampering | pytest + PostgREST/Storage |
| Frontend unit | compression math, URL-state parser, formatting | Vitest |
| E2E | per-section checkpoints in §12 | Playwright + pytest E2E |
| Manual | 30-bill extraction eval, 10-receipt household trial, phone install, live Gemini smoke | checklist |
| CI | lint + unit + frontend build on push; E2E job on PR and nightly with local Supabase + mock Gemini | GitHub Actions |

A section is not done until its E2E checkpoint and R1–R6 pass. Test failures
must be fixed, not skipped; a quarantined test needs an owner and a date.

Never commit real bills. `evals/` is gitignored; only the harness and a
placeholder README live in the repo.

---

## 14. Deployment runbook

1. **Supabase:** create project → `supabase link` → `supabase db push` → seed →
   create private `receipts` bucket and policies → Auth: email provider on,
   confirmation off for MVP → copy URL, anon key, service-role key.
2. **Gemini:** create API key in AI Studio; confirm free-tier model; store in
   Secret Manager.
3. **GCP:** create project, enable billing, enable Cloud Run, Cloud Build,
   Artifact Registry, Secret Manager; create secrets; set budget alerts.
4. **Backend:** `gcloud run deploy billbox-api --source backend
   --region asia-south1 --allow-unauthenticated --memory 512Mi --cpu 1
   --concurrency 2 --max-instances 2 --timeout 300 --port 8080`,
   plus `--set-env-vars` for the non-secret settings and `--set-secrets
   SUPABASE_SERVICE_ROLE_KEY=...,GEMINI_API_KEY=...`.
5. **Frontend:** Cloudflare Pages → build `npm run build`, output `dist`,
   env `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_BASE_URL`;
   add `_redirects` SPA fallback.
6. **Keep-alive:** add `SUPABASE_URL` + `SUPABASE_ANON_KEY` as GitHub Actions
   secrets; enable `keepalive.yml`.
7. **Smoke:** install PWA on a phone → create household → scan 2 bills → search
   → edit a tag → invite the second account.
8. **Regression:** run the full E2E suite against the deployed URLs, then
   R1–R6; archive the report with the release.

### Environment variables

**Backend**

```
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_JWT_SECRET=          # legacy fallback; JWKS is primary
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.8-flash
GEMINI_THINKING_LEVEL=low
CORS_ORIGINS=http://localhost:5173,https://<pages-domain>
MAX_FILE_MB=10
MAX_UPLOAD_MB=25
MAX_PAGES=10
ENVIRONMENT=prod
```

**Frontend**

```
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
VITE_API_BASE_URL=https://<cloud-run-url>
```

---

## 15. Risks and mitigations

| Risk | Effect | Mitigation |
| --- | --- | --- |
| Faded/crumpled Hindi or Marathi bills read poorly | Wrong fields and tags | 30-bill Gate 1; compression/preprocessing; every field editable; rules first |
| Free Gemini data use | Privacy exposure | Skip-AI + warning; no ID/bank docs with AI; one-function paid switch |
| Gemini 429/daily caps | Failed receipts | Backoff, retry, clear quota message, manual Retry |
| Cloud Run 32 MiB limit | Upload failures | 25 MB total cap; client compression; single PDF |
| Cloud Run cold start | Slow first action | "Waking up" UI; slim image; keep max instances low |
| Supabase project pauses | App offline | GitHub Actions ping every 2 days; external backup ping; weekly export |
| RLS or auth bug | Cross-household leak | RLS tests, service-role key server-only, signed URLs, membership check on every route |
| Supabase auth email limit | Sign-up/reset blocked | Confirmation off for MVP; custom SMTP before launch |
| Scope creep | MVP slips | Defer email, reminders, expense tracking, vaults, semantic search |

---

## 16. Out of scope for the MVP

Email intake, expense tracking, warranty tracking, recurring reminders,
private vaults, offline capture, semantic search, question answering,
transliteration search, per-page OCR retries, member removal, account deletion,
custom SMTP, export UI (week 2).

## 17. Non-blocking open items

- Native-speaker review of Hindi/Marathi tag labels and copy.
- Final icon/logo and custom domain.
- Confirm `gemini-3.8-flash` free-tier availability at setup; fallback model
  chosen already.
- Cloudflare Pages vs. Vercel (Cloudflare Pages is the default).
- Data retention/account deletion policy before public launch.

---

## 18. Definition of done for the MVP

A household member can install BillBox, sign in, create or join a household,
scan a multi-page bill (or upload a PDF), see it extracted, edit any field or
tag, find it with a keyword, tag, merchant, amount or natural phrase, and open
the original pages — on a phone and a laptop — with no cross-household data
leak and no lost uploads.

All six E2E checkpoints in §12 and the regression suite (R1–R6) are green.
