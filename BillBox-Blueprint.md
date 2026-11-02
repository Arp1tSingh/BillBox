# BillBox — Blueprint

Nov 2, 2026 · @Arpit Singh

## Overview

BillBox is a household web app (PWA) that turns a photo of a bill into a searchable, auto-tagged record, so typing "electricity bill" returns every electricity bill in seconds. It exists because a paper receipt was lost at home and could not be found when it was needed.

**In the MVP (a few days)**

- Scan with the phone camera, multi-page bills supported; also upload PDFs and images
- AI reads each bill in English, Hindi or Marathi and extracts bill type, merchant, amount and date
- Tags are assigned automatically: a fixed set where one fits, AI-generated otherwise; every tag can be added, edited or removed
- Search by keyword, tag, merchant or amount, plus natural-language questions such as "when did I buy the router"
- One shared household store (up to 8 members), with sign-in and an invite code
- Works on phone and laptop, installable as a PWA

Each build section ends with an E2E checkpoint and a shared regression suite; the detailed plan is in `PLAN.md`.

**Later (polish weeks)**

- Export (ZIP of files plus CSV of fields), offline-friendly capture, UI polish, expanded E2E coverage and a portfolio write-up

**Out of scope for now**

- Email intake, expense tracking, warranty tracking, recurring-bill reminders, and private per-person vaults (the data model leaves room for vaults)

## Locked decisions

Six choices from the discovery round fix the shape of the build. Four more questions were settled during planning.

| Area | Decision | Reason |
| --- | --- | --- |
| Client | React PWA, camera capture on phone, search on phone and laptop | One codebase, no app store, matches existing skills |
| Backend | FastAPI (Python) on Google Cloud Run, Mumbai (`asia-south1`) | Owns AI calls, search logic and validation; scale-to-zero on the free tier |
| Data and auth | Supabase free tier: Postgres, file storage, auth | Free, covers three needs in one service |
| AI | Gemini 3.8 Flash vision, free tier, one call per bill | Handles English, Hindi and Marathi, returns structured JSON; Gemini 3 uses a thinking level, not temperature |
| Access | Individual accounts joined to a household by invite code, capped at 8 members | Shared store now, private vaults later without a rewrite |
| Email intake | Deferred past MVP | Hardest part to do free; upload and share-to-app cover the gap |

| Settled during planning | Decision |
| --- | --- |
| App name | BillBox — PWA name, icon label, page title, README and repo folder |
| Backend host | Google Cloud Run, `asia-south1` (Mumbai), scale-to-zero, max 2 instances |
| Sensitive documents | Allowed with a skip-AI switch and a first-upload warning; no automated blocking |
| Household size | Cap 8 members at launch; test the invite flow with 3 accounts |

Two trade-offs to accept knowingly. On the free Gemini API tier, Google may use submitted content to improve its models; bills carry names, addresses and account numbers. Cloud Run's free tier needs a billing account and card, so budget alerts and a low instance cap are required. The security section covers both.

## Architecture

The React PWA, FastAPI on Cloud Run, and Supabase carry the app, all on free tiers.

&#91;embedded content: architecture · 6 parts\]

Page images reach the browser through short-lived signed URLs; only FastAPI holds the Gemini key and the database service key, both in Secret Manager. FastAPI runs in `asia-south1` with scale-to-zero; uploads are proxied through it before storage.

Cloud Run caps an HTTP request at 32 MiB, so uploads are limited to 25 MB total. Client-side compression keeps ten phone pages around 3–5 MB; one PDF may be up to 10 MB.

## Data model

Six user-data tables plus one operational heartbeat table in Supabase carry everything; every row that holds user data points back to a household, which keeps access control to one rule.

| Table | Key columns | Notes |
| --- | --- | --- |
| households | id, name, invite\_code, created\_by | One per home; the invite code is rotatable |
| household\_members | household\_id, user\_id, role | role is owner or member; user\_id comes from Supabase auth; one household per account at MVP; cap 8 |
| receipts | id, household\_id, created\_by, title, merchant, amount, currency (default INR), bill\_date, bill\_type, language, status, ai\_skipped, failure\_reason, processing\_started\_at, processed\_at, raw\_text, extracted (jsonb), search\_vector, vault\_id (nullable) | status is processing, ready or failed; failure\_reason is user-safe, never bill text; vault\_id stays empty until private vaults ship |
| receipt\_pages | id, receipt\_id, page\_no, storage\_path, mime\_type, size\_bytes | One row per scanned page; a PDF is one row with mime application/pdf; files live in a private storage bucket |
| tags | id, household\_id (null for system tags), slug, label\_en, label\_hi, label\_mr, kind, keywords | kind is bill\_type, merchant or custom; keywords hold trilingual trigger words; system tags are the fixed set |
| receipt\_tags | receipt\_id, tag\_id, source, confidence, removed\_at, removed\_by | source is rule, ai or user; soft delete records a removal so a re-run cannot bring the tag back |
| heartbeat | id, last\_ping | Operational only; anon select for the keep-alive cron |

**Access rule.** Row-level security allows a user to read or write a row only when they are a member of its household. A user belongs to one household at MVP; a household is capped at 8 members. Storage paths start with the household id, and the bucket policy checks the same membership.

**Search columns.** search\_vector combines title, merchant, tag labels in all three languages and raw\_text, using the `simple` text-search config. A trigram index on merchant handles spelling drift such as "Adani Electricity" versus "Adani Elec.". If `simple` tokenisation underperforms on Devanagari, fall back to ILIKE on raw\_text and tag labels.

**Future vaults.** A private vault is a second kind of container with its own members; setting receipts.vault\_id moves a receipt into it without a schema change.

## Capture and AI pipeline

Each scan runs through six steps plus a failure path, and the page files are stored before any AI call is made. The client triggers extraction with `POST /receipts/{id}/process`, and it runs inside that request rather than in a background task: Cloud Run throttles CPU after a response, so post-response work is unreliable.

&#91;embedded content: capture and AI pipeline · 6 steps, 1 failure path\]

If Gemini errors or hits a rate limit, the receipt stays in the household as failed, with its pages intact, until someone presses Retry. Retry is the same idempotent endpoint; a stale processing row can be resumed after five minutes.

**What the Gemini call returns.** One request with all pages of a bill, using `gemini-3.8-flash` with `thinking_level` set to low and strict JSON: bill\_type, merchant, amount, currency, bill\_date, language, raw\_text and up to three descriptive tags. Gemini 3.8 Flash supports image and PDF input, structured output and a 1M-token context; the free-tier lineup changes, so confirm the model at setup (fallback: `gemini-3.6-flash`).

**Prompt rules**

- Give the model the fixed tag list and tell it to choose bill\_type from that list or return null.
- Tell it to return null for any field it cannot read, never to guess an amount or date.
- Ask for raw\_text in the bill's own script, so Hindi and Marathi text stays searchable.
- Use thinking level `low` and a response schema so the output parses every time; Gemini 3.8 Flash does not accept `temperature`.
- Ask for the final payable total, the bill date (not the due date) and the seller or utility as merchant.
- Retry 429 and 5xx up to four times with backoff; do not retry 400s.

## Tagging system

Every receipt gets one bill-type tag from a fixed set, a merchant tag, and up to three free-form AI tags; the user can change all of them. At most one bill-type tag is active per receipt; adding another replaces it.

**Fixed set (starter list, seeded from config)**

| Tag | Example trigger words |
| --- | --- |
| Electricity | electricity, MSEDCL, Adani Electricity, बिजली, वीज |
| Water | water, पानी, पाणी |
| Gas | LPG, PNG, gas cylinder, गैस, गॅस |
| Internet and Phone | broadband, recharge, postpaid |
| Maintenance | society maintenance, मेंटेनेंस, देखभाल |
| Property Tax | property tax, मालमत्ता कर |
| Electronics and Appliances | router, laptop, mixer, warranty card |
| Medical | pharmacy, clinic, दवाई, औषध |
| Groceries, Dining, Fuel, Insurance, Education, Repairs, Rent | added the same way |

Every fixed tag carries labels and trigger words in English, Hindi and Marathi, stored in the tags table; the starter list is seeded from config. Hindi and Marathi labels need a native speaker's review before launch.

**How a receipt gets its tags**

1. Rules run first: keyword match on the extracted text against the table above, in all three languages. A hit gives the bill-type tag with source rule.
2. The Gemini response supplies bill\_type, merchant and up to three descriptive tags. If no rule hit, the AI bill\_type is accepted only when it is in the fixed set; otherwise the receipt gets the AI's free-form tags and no bill-type tag.
3. Merchant becomes a tag (for example "Croma"), normalised so spelling variants merge; existing household merchant tags are matched with trigram similarity.
4. Amount is stored as a field and shown as a tag-style chip; it is searchable ("over 5000") but is not a tag row, since every amount would create a new tag.
5. Tags store kind (bill\_type, merchant or custom) and keywords; receipt\_tags stores source (rule, ai or user) and confidence.

**Editing rules**

- Add, rename or remove any tag on a receipt; the change is stored with source user.
- Removing an AI or rule tag records the removal, so re-running extraction does not bring it back. Re-adding a removed tag clears the removal and records source user.
- At most one bill-type tag per receipt; adding another replaces the previous one.
- Each fixed tag has labels in English, Hindi and Marathi, so a search in any language finds the same receipts.

## Search

Postgres full-text search plus tag and field filters is enough for a household's volume (thousands of receipts), so the MVP needs no separate search service.

1. **Parse the query.** Pull out structured parts: amounts ("over 5000", "under 2000"), years and months ("2025", "last month"), and words that match a tag label or keyword in any of the three languages. Explicit filters override parsed values.
2. **Match.** Tag matches, then merchant (trigram, so typos still hit), then title and extracted text through full-text search.
3. **Rank.** Exact tag match first, merchant second, text hit third; ties broken by newest bill\_date.
4. **Return** receipt cards with thumbnail, merchant, amount, date and tags; tapping a card opens the page images. Cards include short-lived signed thumbnail URLs.

**Question-style queries.** "When did I buy the router" works in the MVP through step 2: "router" matches the extracted text, and the result card shows the bill date prominently. A later version sends the question and the top five matches' text (no images) to Gemini to answer in one sentence.

**Filters on the results screen:** tag chips, date range, amount range, sort by date or amount.

**Later:** semantic search with pgvector embeddings if keyword search misses too often; transliteration so a query typed in English finds Hindi or Marathi text.

## API and screens

The client signs in through Supabase and sends its JWT to FastAPI, which checks it and the household membership on every call.

| Endpoint | Purpose |
| --- | --- |
| POST /households, POST /households/join, GET /households/me, POST /households/rotate-invite | Create a household; join with an invite code (cap 8); read it; rotate the code |
| POST /receipts | Upload one or more page images or a PDF (10 pages, 25 MB total); optional skip\_ai; returns id with status processing |
| POST /receipts/{id}/process | Run extraction; idempotent; also used for Retry and Resume |
| GET /receipts/{id} | Detail and status; signed page URLs; the client polls every 2 seconds until ready or failed |
| GET /receipts | Search and list: q, tag, from, to, min, max, sort, page; cards include signed thumbnail URLs |
| PATCH /receipts/{id} | Edit title, merchant, amount, date |
| DELETE /receipts/{id} | Delete the receipt, its rows and its stored pages |
| POST and DELETE /receipts/{id}/tags | Add or soft-remove a tag |
| GET /tags | Fixed and household tags with trilingual labels and counts |
| GET /export | Later: ZIP of files plus CSV of fields |

**Screens**

1. **Sign in:** email and password; session persists; password reset deferred until custom SMTP.
2. **Household onboarding:** create a household or join with a code.
3. **Home:** one search box, tag chips, recent receipts, processing and failed states with Resume/Retry.
4. **Scan:** camera, add page, remove page, skip-AI toggle, submit.
5. **Receipt detail:** page viewer, editable fields, editable tags, delete.
6. **Household:** invite code, members.

**Build notes**

- Vite plus vite-plugin-pwa for installability; the service worker precaches the shell only.
- Capture with a file input set to the rear camera (`capture="environment"`); it is the most reliable route on mobile browsers. Live edge detection can come later.
- Compress each page in the browser to about 1600 px on the long side before upload; this saves storage and Gemini tokens. Enforce 10 MB per file and 25 MB total, under Cloud Run's 32 MiB request limit.
- The upload is stored first; the client then calls `POST /receipts/{id}/process`. A receipt is never lost if the AI call fails; it shows as failed with a retry button.
- Show a "waking up" state if the first request takes more than 1.5 seconds; Cloud Run cold starts are seconds, not minutes.
- Use Supabase email/password auth with confirmation disabled for the MVP; add custom SMTP before real onboarding (the free email limit is 2 per hour).

## Security, privacy and limits

The app stores financial documents, so the privacy trade-off of the free AI tier is the main thing to manage, followed by free-tier hosting quirks.

**Privacy**

- On the free Gemini API tier, submitted content may be used by Google to improve its products, and human reviewers may read it; the paid tier does not do this. Treat free-tier use as acceptable for utility and shop bills, not for ID cards, bank statements or anything with Aadhaar or PAN numbers. Check Google's current terms before launch.
- Sensitive documents are allowed, but only with the skip-AI switch and a first-upload warning; there is no automated blocking. A skip-AI receipt is stored and tagged by hand, marked ai\_skipped, and never sent to Gemini.
- Exit route: the AI call sits behind one function, so moving to a paid tier, a different model, or the hybrid on-device OCR design is a one-file change.

**Security basics**

- Row-level security on every table; private storage bucket with short-lived signed URLs (60 minutes).
- FastAPI verifies the Supabase JWT (issuer, audience, expiry; JWKS cached) and household membership on each request; the service-role key never reaches the browser and lives in Secret Manager.
- Limit uploads to 10 pages, 10 MB per file and 25 MB per request; accept only JPEG, PNG, WebP and PDF; validate magic bytes; validate PDF page count with pypdf.
- Do not log extracted text, raw text, page bytes or signed URLs; keep secrets in environment variables or Secret Manager.
- CORS allows only the app origins; the client never receives the service-role or Gemini key.

**Free-tier behaviour to plan around** (figures are approximate; confirm current terms when setting up)

| Service | What to expect | Handling |
| --- | --- | --- |
| Supabase free | 500 MB database, 1 GB file storage, 5 GB egress; projects pause after about a week of low database activity | Compress images; ping a heartbeat table every 2 days from GitHub Actions; export as backup |
| FastAPI on Cloud Run | Scale-to-zero; 2–5 s cold start; 2M requests and 180k vCPU-seconds per month; needs a billing account; 32 MiB request cap | Show a "waking up" state; max 2 instances; budget alerts; 25 MB upload cap |
| Gemini free tier | Per-minute and per-day request caps; free-tier content may be used to improve Google products | Skip-AI for sensitive bills; retry with backoff; show "processing" until done; confirm the model lineup at setup |

**Cost guard.** Budget alerts notify, they do not stop spend. Keep max instances at 2, request timeout at 300 seconds, and Artifact Registry to the last two images; revisit before any public launch.

## Roadmap

The MVP is four short phases with two checkpoints; the phase lengths are a proposal, not a measured estimate. The detailed five-day plan lives in `PLAN.md`, split into six build sections that subdivide these four phases; each section ends with its own E2E checkpoint.

&#91;embedded content: roadmap · 4 phases, 2 gates\]

Extraction quality is the first gate on purpose: if reads of real Hindi, Marathi and faded bills are poor, fix the prompt or the image preparation before building search on top. On 30 real bills, aim for at least 80% correct amount and date and 70% correct bill type. The second gate is real use: 10 receipts from two accounts, at least 8 found by natural queries, since the goal is a tool the household actually opens.

## Risks and open questions

The biggest unknown is how well extraction reads faded thermal prints and Marathi or Hindi text, so test that before polishing anything else.

| Risk | Effect | Mitigation |
| --- | --- | --- |
| Poor reads on faded or crumpled bills | Wrong or missing tags and amounts | Test with 30 real household bills on day 3; every field and tag stays editable |
| Wrong bill-type guess | Receipt hidden from the search a user expects | Rules first, AI restricted to the fixed set, user edits are final |
| Free-tier limits or sleeping services | Slow or paused app | Retry and backoff; 2-day Supabase heartbeat; weekly export |
| Cloud Run request limit or cold start | Uploads fail or the first action is slow | 25 MB cap plus client compression; "waking up" state; max 2 instances |
| Sensitive documents sent to a free AI tier | Privacy exposure | Skip-AI switch; document what not to scan; one-file switch to a paid tier |
| Supabase auth email limit | Sign-up or password reset blocked | Confirmation off for MVP; custom SMTP before launch |
| Scope creep into email, reminders, expense tracking | MVP slips past a few days | Keep them on the later list until search feels good in daily use |

**Resolved during planning**

- [x] App name: **BillBox** (PWA name, icon label, page title and repo folder).
- [x] FastAPI host: **Google Cloud Run**, `asia-south1` (Mumbai), scale-to-zero with a billing account and budget alerts.
- [x] ID and bank documents: **allowed with skip-AI**, plus a first-upload warning; no automated blocking.
- [x] Household members: **cap 8**, tested with 3 accounts.

**Remaining, non-blocking**

- [ ] Native-speaker review of Hindi and Marathi labels and copy.
- [ ] Icon/logo and custom domain.
- [ ] Confirm `gemini-3.8-flash` free-tier availability at setup; fallback `gemini-3.6-flash`.
- [ ] Cloudflare Pages vs Vercel for the frontend host (Cloudflare Pages is the default).
- [ ] Data retention and account-deletion policy before public launch.
