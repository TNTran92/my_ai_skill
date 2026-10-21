---
name: harris-county-foreclosure-downloads
description: Download Harris County Clerk FRCL foreclosure docs as PDFs.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Harris County, Foreclosure, FRCL, PDF, Web Scraping, cclerk.hctx.net]
    related_skills: [blocked-page-recovery]
---

# Harris County Foreclosure Doc Downloads (cclerk.hctx.net)

## When to Use

User asks to open, view, or download a Harris County Clerk foreclosure (FRCL-YYYY-NNNN) document from `cclerk.hctx.net` — one doc or a batch from a result set (e.g. "download FRCL-2026-7209 to ~/... as pdf") — or to pull the listing pages for a date range.

Verified working flow. Documents are image-only PDFs (no text layer) — verify visually.

## Output convention (READ FIRST)

- **Save location**: `/home/ttran/foreclose_file/<FilingYear>/<FilingMonth>/<DocID>.pdf`
  - `<FilingYear>`: the filing year, the year value you SELECT on the search form (the `ddlYear` control).
  - `<FilingMonth>`: the filing month, a **capitalized English word** taken from the `ddlMonth` drop-down you SELECT (e.g. `October`, `November`, `March`). Never use a numeric month.
  - `mkdir -p /home/ttran/foreclose_file/<FilingYear>/<FilingMonth>` before writing the PDF.
- Before downloading, scan the **target (YEAR, MONTH) subdirectory only** for existing `<DocID>.pdf` and **skip** any IDs already present (no overwrite, no re-fetch). Do NOT check sibling folders or the bare base folder.
- Report: skipped IDs (already present in that folder), and for new downloads — full path under `/home/ttran/foreclose_file/<FilingYear>/<FilingMonth>/<DocID>.pdf`, HTTP status, `file` output, and key document facts (title, party, sale date) so provenance is visible.

## 1. Search form (FRCL_R.aspx)

Open `https://www.cclerk.hctx.net/applications/websearch/FRCL_R.aspx`. Elements (ASP.NET WebForms IDs):

- Radio: `input[name='ctl00$ContentPlaceHolder1$rbtlDate']`, values `SaleDate` / `FileDate`
- Year: `#ctl00_ContentPlaceHolder1_ddlYear` · Month: `#ctl00_ContentPlaceHolder1_ddlMonth`
- Search button: an `<input>` with value `Search` (NOT a `<button>`; match with `/^search$/i` on `.value`)

Selecting `FileDate` changes the month list to a rolling window (e.g. October back to January) and triggers a **partial postback**: during that re-render the selects are `null` in the DOM. So:

1. Click the FileDate radio; **poll** until `ddlMonth` options include 'October' before touching any select.
2. Set a select with `el.value=<opt.value>; el.dispatchEvent(new Event('change',{bubbles:true})).` Each change can re-render and reset the other control, so loop until `selectedOptions` actually report the wanted year AND month AND FileDate checked — assert these three before clicking Search.

## 2. Document URLs (the key trick)

- Result rows are links: `<a class='doclinks' href='ViewECdocs.aspx?ID=<token>' target='_blank'>FRCL-YYYY-NNNN</a>`. **Read the href from the results grid; never open the viewer tab** (direct navigation of the URL from a fresh/different context bounces to the search page — the ID token is session-bound).
- `ViewECdocs.aspx?ID=...` responds `Content-Type: Application/pdf` — the server serves the real PDF; the browser just renders it in the built-in viewer. No print-to-PDF needed.
- Page columns: Doc ID, Sale Date, File Date, Pgs (page count). 10 rows/page; pagination `1..10...`.

## 3. Download

1. **Skip existing docs first**: before downloading (and before paging more results), list the target folder (default `/home/ttran/foreclose_file`) and drop any doc IDs that already have a `<DocID>.pdf` there — no re-download, no overwrite; filter the href list and download loop by this set.
2. In one `browser_exec` call: `cdp('Network.getAllCookies')['cookies']` → filter `domain` containing `hctx.net` → join as `name=value; ...` → write to a scratch file; also write each doc URL to a scratch file.
3. Terminal: `curl -sS -L -o <name>.pdf -H 'Cookie: <pair>' -H 'Referer: https://www.cclerk.hctx.net/applications/websearch/FRCL_R.aspx' -H 'User-Agent: <chrome UA>' '<docurl>'` — expect `HTTP:200 TYPE:Application/pdf`.
4. Verify: `file <pdf>` (should say `PDF document, version 1.4, N page(s)`); render `pdftoppm -png -r 80 <pdf> <prefix>` and visually check the scan (clerk stamp should match the Doc ID).

## Pitfalls (all hit in the field)

- **Browser session resets between turns**: repeated resets to `about:blank`/newtab mid-task. Do navigate → select → search → grab links as **ONE** `browser_exec` call. If you must span calls, first line of every call = state check (`location.href`, is the form present, are doc links present) and redo the flow if lost.
- The `js()` helper is pinned to its attached tab. Use `list_tabs(include_chrome=True)` + `switch_tab(t, activate=True)` to move between tabs; `ensure_real_tab()` to recover from internal tabs.
- Submitting Search while month is still `Select -` silently produces no target row — hence the assert before submit.
- Batch mode: grab all `a.doclinks` (id+href) from a results page in one JS call, then curl the 10 with the same cookie pair — no per-doc UI needed. Flip pagination the same way.
- The site runs under an already-logged-in profile (user banner + clerk watermark on docs). If a login wall appears, stop and ask the user (or browser_vault); never guess credentials.

## Output convention

Default target folder is `/home/ttran/foreclose_file`; save as `<DocID>.pdf` (e.g. `FRCL-2026-7209.pdf`). Before downloading, scan the folder and skip any `<DocID>.pdf` already present (no overwrite, no re-fetch). Report: skipped IDs (already present) plus, for what was downloaded, HTTP status, `file` output, and key document facts (title, party, sale date) so provenance is visible.
