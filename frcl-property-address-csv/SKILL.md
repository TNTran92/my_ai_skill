---
name: frcl-property-address-csv
description: Use when adding a FRCL case address to the sale CSV.
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [Harris County, Foreclosure, FRCL, CSV, property-address, parallel]
    category: productivity
    related_skills: [harris-county-sale-data-csv, harris-county-foreclosure-downloads]
---

# FRCL Property Address → CSV

Given a Harris County FRCL (foreclosure) case number + filing month folder, find the property's **physical/street address** and record it in that month's `property_data.csv` on the **correct row**. Built to be run per-case, safely in parallel, with almost no thinking required.

## When to Use
Load this when you must record a physical/street **property address** for one or more Harris County **FRCL (foreclosure)** cases into a month's `property_data.csv` — e.g. "find/record the address for FRCL-2026-####", "fill in the Property Address column", or a **parallel batch** across many case numbers. Do **not** use for non-FRCL addresses or other CSVs.

## Canonical paths
- CSV: `/home/ttran/foreclose_file/[year]/[month]/property_data.csv` — `year` is 4-digit (`2026`), `month` is the full English name (`October`).
- FRCL notice PDF (same folder): `FRCL-[year]-[seq].pdf` (e.g. `FRCL-2026-7606.pdf`).
- Backups go to `~/.hermes/cache/scratch/`, **never** into the data folder.

## CSV shape
Typical columns: `File Name, Date of Sale, Earliest Time Sale Will Begin, Place of Sale of Property, Legal Description, Date Added, Time Added`.
This skill **appends** a `Property Address` column (last position) on first run; on later runs it just fills the existing column. Match rows by **File Name exactly equal to `FRCL-<seq>`** — there are near-duplicates (…7601 / …7602 / …7606); never match by substring or digit tail.

## Workflow (per case)
1. **Read the row & skip if already recorded.** Find the case in the CSV. If its `Property Address` cell is already non-empty, **skip this File Name entirely** — no PDF rendering, no searches, no write. Only proceed when the cell is blank (or the user explicitly asks for a re-lookup / `--force`). When proceeding, grab `Legal Description` (it's plain text in the CSV — no OCR needed here).
2. **Parse lot / block / subdivision.** Pattern: `…LOT <lot>, IN BLOCK <block>, OF <SUBDIVISION>, SECTION <section>…`
   - **Subdivision** = the name(s) after the `OF` that follows the block number. E.g. `BLOCK SEVENTEEN (17), OF ALMEDA PLAZA, SECTION THREE` → subdivision **ALMEDA PLAZA**.
   - Keep numeric values as-is (e.g. 443, 17).
3. **Get the physical address — prefer the local FRCL notice PDF** (it states `Property Address: …` verbatim).
   ```
   mkdir -p ~/.hermes/cache/scratch
   pdftoppm -png -r 200 "FRCL-2026-7606.pdf" ~/.hermes/cache/scratch/f7606   # -> f7606-1.png, f7606-2.png, ...
   ```
   The PDF is **scanned, no text layer** (pdftotext returns blank) → render, then `vision_analyze` each `f7606-N.png` and read the **`Property Address:`** line (usually page 2). Confirm it's consistent with the legal description.
   - **Fallback only if the PDF is missing:** clerk RP.aspx search — see the FLAKY section below.
4. **Write it back with the helper only** (never hand-edit the CSV for a write):
   ```
   python3 <skill_dir>/scripts/append_address.py \
     --csv   /home/ttran/foreclose_file/2026/October/property_data.csv \
     --case  FRCL-2026-7606 \
     --address "2847 Trail Lake Drive, Houston, TX 77045"
   ```
   `<skill_dir>` = this skill's folder (the one containing `scripts/append_address.py`); run with its full path if you're in another cwd.
   - If the case's cell already has an address, the helper prints `SKIPPED: …` and changes **nothing** (safe for parallel workers). `--force` overwrites an existing value deliberately.
5. **Verify:** the script prints `OK: …` (or `SKIPPED: …` if already recorded); re-read the row, confirm **exactly one** row has the address and the total row count is unchanged.

## Concurrency (parallel, non-conflicting) — MUST FOLLOW
Many workers may append to the same CSV at once. All address **writes** must go through `scripts/append_address.py`. It, per call:
- takes an **exclusive `fcntl.flock`** on sidecar `<csv>.lock`,
- adds/updates the `Property Address` column, sets the cell for `--case` only,
- writes a **temp file then `os.replace`** (atomic),
- releases the lock.

Because writers serialize on the lock and the final swap is atomic, N parallel workers each call with their own `--case/--address` and never corrupt one another; a reader always sees a whole file. Idempotent and safe — if the case's cell is already filled the call `SKIPPED`s without touching the file; `--force` overwrites deliberately.
- Reads (steps 1–2) need no lock; only the write locks.
- Back up first: `cp <csv> ~/.hermes/cache/scratch/property_data_<Month>.bak.csv`.
- On this host keep concurrency modest (subagent fan-out is unreliable here), but the lock guarantees correctness at any level.

## Address-extraction rules
- Use the **verbatim** `Property Address:` text (street number, street name, city, state, zip).
- If the notice has a legal description but **no street number**, say so — do **not** invent a number.
- One address per case row; leave every other row's `Property Address` blank.

## No street address in the notice (common — do this before the clerk RP.aspx fallback)
Many single-page notices carry only the legal description. Fast + reliable: the HCAD parcels GeoJSON layer via REST (no auth):
```
https://www.gis.hctx.net/arcgis/rest/services/HCAD/Parcels/MapServer/0/query?where=<W>&outFields=*&f=json
```
- Fields: `dscr` (subdivision, often re-platted variants — e.g. `WEST U,SOUTHWEST & KENT PLACE 1-2` for WEST UNIVERSITY PARK), `legal_dscr_1` (abbreviated, e.g. `LT 3 BLK 8` / `TR 8A BLK 27`), `LOT_NUM`/`BLK_NUM` (zero-padded, and often zero — don't trust them; use `legal_dscr_1`), `site_str_num/name/sfx`, `site_city`, `site_zip`, `owner_name_1/2`.
- Query with `UPPER(dscr) LIKE '%SUBDIV%'` + `UPPER(legal_dscr_1) LIKE '%LT 3 BLK 8%'`. **Validate by cross-checking `owner_name_1` against the notice's Grantor/Mortgagor** — that is the decisive match.
- Watch for HCAD spelling variants (`WILLIAMSBURG PARRISH #1` — double R; `FOUNDARY` not `FOUNDRY`), and street-suffix codes (`DR`, `ST`).
- Proven in Oct 2026 for FRCL-2026-7209 (2334 Foundary Drive, Katy 77493) and FRCL-2026-7210 (6411 Mercer Street, Houston 77005).

## Clerk search (RP.aspx) — FALLBACK only; it is FLAKY (learned the hard way)
`https://www.cclerk.hctx.net/applications/websearch/RP.aspx` → fill `Subdivision or Description` (id `...txtDesc`), `Lot` (`...txtLot`), `Block` (`...txtBlock`), click **Search**. Results land on `RP_R.aspx?ID=...`; doc links are the `RP-...` File Numbers (`a.doclinks`) → `EComm/ViewEdocs.aspx?ID=<TOKEN>`.
Gotchas that all bite:
- **The ID TOKEN is long and must be captured UNTRUNCATED.** A clipped/copied ID → the site's **error page `Maintenance.aspx`** ("This Search is currently unavailable. Please check back soon.") — that is not always genuine maintenance.
- The edocs viewer is **plugin/Adobe-based and renders a blank page in headless Chrome** — you usually cannot read the REMAP images here. **This is why the local PDF is preferred.**
- Login wall: `User Name or Email` (`...Login1_UserName`) + `Password` (`...Login1_Password`) + `Login1_LoginButton`. Credentials come **from the user**; never invent them.
- **Tabs reset between tool calls** — do search → grab the full href → login → open in as few calls as possible, and re-run the search to mint a fresh token if a previous one expired/errored.

## Copy-paste recipe (single worker, typical case)
```
CSV=/home/ttran/foreclose_file/2026/October/property_data.csv   # year/month per task
CASE=FRCL-2026-7606
# 0) skip if this File Name already has a Property Address
python3 -c "import csv;r=list(csv.reader(open('$CSV')));h=r[0];row=[x for x in r[1:] if x and x[0]=='$CASE'][0];a=row[h.index('Property Address')].strip();print('SKIP — already recorded:',a) if a else print('EMPTY — proceed')"
# 1) confirm row + legal description exist
python3 -c "import csv;r=list(csv.reader(open('$CSV')));h=r[0];row=[x for x in r[1:] if x and x[0]=='$CASE'][0];print(row[h.index('Legal Description')][:120])"
# 2) grab the address: render + read the local PDF, page 2 'Property Address:'
pdftoppm -png -r 200 "/home/ttran/foreclose_file/2026/October/$CASE.pdf" ~/.hermes/cache/scratch/$CASE
# vision_analyze ~/.hermes/cache/scratch/$CASE-1.png (and -2.png) — look for 'Property Address:'
# 3) write (locked + atomic)
python3 <skill_dir>/scripts/append_address.py --csv "$CSV" --case "$CASE" --address "<ADDRESS FROM NOTICE>"
```
