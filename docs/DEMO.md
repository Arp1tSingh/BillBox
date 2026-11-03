# BillBox demo

The 25-second walkthrough is in [`demo.gif`](demo.gif). The still frames used
for the demo live in [`screens/`](screens/).

A 60–90 second walkthrough of the core loop: capture, extract, find, share.

The demo uses **synthetic fixtures only** — generated demo bills
(`docs/screens/demo-electricity.png`, `docs/screens/demo-water.png`) and seeded
values. Never record a real bill, name, address or account number. The
committed GIF was captured against intercepted fake auth/API routes, not a
live Supabase backend.

## Storyboard

| Time | Screen | Action | Caption |
| --- | --- | --- | --- |
| 0:00 | Home | Empty shelf with the search box and “Scan a bill” CTA | “Bills end up in a drawer. BillBox gives the household one searchable shelf.” |
| 0:08 | Scan | Tap **Take a photo** or **Add pages or a PDF**, choose the synthetic bill | “Capture one page or a ten-page bill — or upload a PDF.” |
| 0:18 | Scan | Show the preview, reorder/remove affordance and **Skip AI** note | “Pages can be reordered. Sensitive documents stay out of the model.” |
| 0:28 | Detail | Save, wait for **Ready**, show extracted merchant, amount, date and tags | “One Gemini call extracts the fields; every field stays editable.” |
| 0:42 | Detail | Edit the merchant and add a tag | “Rules and the model propose tags; the household has the final say.” |
| 0:52 | Home | Search `electricity over 5000`, then tap a tag chip | “Search the way you talk about bills, in English, Hindi or Marathi.” |
| 1:05 | Household | Show invite code, member list and export | “Invite the household, then export everything as a ZIP.” |
| 1:15 | Offline | Turn off the network, save a bill, show the queue banner | “No connection? The bill is queued on the device.” |
| 1:22 | Home | Reconnect; the banner clears and the receipt appears | “BillBox uploads it automatically when you are back online.” |

## Capture

Record at a phone viewport (390×844) for the primary cut and optionally repeat
the search segment at desktop width.

### Option A — screen recording (recommended for the final GIF)

1. Start local Supabase, the API and the PWA as described in the
   [README](../README.md).
2. Sign in with two synthetic accounts and create a household.
3. Record the storyboard with OBS, ScreenToGif or the OS recorder.
4. Trim to the actions above, then export a GIF at 480–640 px wide and 12–15 fps.
5. Save the result as `docs/demo.gif` and link it from the README.

### Option B — Playwright video

The Playwright config already records video on failure. For a deliberate demo,
run a short script with `recordVideo` enabled against the local stack, then
convert the `.webm` output:

```powershell
ffmpeg -i demo.webm -vf "fps=12,scale=480:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" docs/demo.gif
```

## Notes for the recording

- Use a fresh household so the empty state and first receipt are visible.
- Keep the browser zoom at 100% and hide bookmarks/extensions.
- Use the synthetic `bill-en.png` fixture; do not show real document data.
- Keep API latency natural. If the local API is instant, the “waking up” banner
  will not appear; that is expected.
- For the offline segment, use DevTools → Network → Offline rather than stopping
  local Supabase, so the app shell stays loaded.

## Still images

If a GIF is too large for the repository, capture four stills instead:

1. Empty home with search and CTA.
2. Scan preview with two pages.
3. Receipt detail with extracted fields and tags.
4. Search results plus the offline queue banner.

Store them under `docs/screens/` and embed the best one in the README.
