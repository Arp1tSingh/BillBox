# BillBox v0.1 release notes

Released 3 November 2026.

BillBox v0.1 is the first end-to-end build of the household receipt shelf:
capture a bill on a phone, extract the useful fields, search it later by
merchant, tag, amount, date or a natural phrase, and share the shelf with one
household.

## Highlights

- **Capture and extraction** — camera/gallery upload, multi-page images and
  PDFs, client-side compression, page reorder/remove, Gemini extraction with
  editable fields, retries and a skip-AI path for sensitive documents.
- **Tags** — deterministic merchant and bill-type rules, AI tags with confidence,
  user tags with add/remove/re-add semantics, and English/Hindi/Marathi labels.
- **Search** — full-text search, merchant trigram matching, tag chips, amount and
  date phrases, sorting, pagination and URL-preserved state. Parsed tag filters
  now combine with explicit tag chips as AND filters.
- **Detail and household** — page viewer, inline edits, delete, invite-code
  join/rotate, member list and an eight-member cap.
- **PWA** — installable manifest, icons, offline app shell, bottom navigation,
  safe-area support and a “waking up the server” banner for cold starts.
- **Offline capture** — bills saved without a connection go into a user-scoped
  IndexedDB queue and upload automatically on reconnect, with retry and discard
  controls in the header.
- **Export** — ZIP download with `receipts.csv` and the original pages.
- **Automation** — backend lint/unit/API tests, frontend typecheck/build, and a
  Playwright suite across desktop Chromium, mobile Chrome and mobile Safari.
  CI runs on push, pull request and nightly.

## Compatibility

- Modern evergreen browsers with IndexedDB and service-worker support.
- Android Chrome and iOS Safari for installability.
- Node 22+, Python 3.12+ and Docker for the full local E2E harness.

## Known limitations

- Live Gemini extraction quality, the 30-bill Gate 1 evaluation and the
  two-account Gate 2 household trial are pending manual runs.
- Cloud Run and Cloudflare Pages deployments are documented but not yet live.
- Lighthouse CI and the performance budget are not automated yet.
- Member removal and account deletion are out of scope for this release.
- The keep-alive workflow needs the Supabase repository secrets before the
  nightly heartbeat is reliable.

## Verification

- Backend: 63 passed, 8 integration tests skipped locally without Supabase.
- Frontend: typecheck and production PWA build pass.
- E2E: API-level suite plus Playwright section checkpoints (see the GitHub
  Actions run for the release commit).

## Data policy

Only synthetic fixtures are committed. Real bills, names, addresses and account
numbers stay on the tester's machine; `evals/` is gitignored.
