---
name: harris-county-sale-data-csv
description: Record FRCL notice sale details into property_data.csv.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Harris County, Foreclosure, FRCL, PDF, CSV, data-extraction]
    category: productivity
    related_skills: [harris-county-foreclosure-downloads, pdf]
---

# FRCL Notice Sale Data to CSV Ledger

## When to Use

User asks to read a Harris County FRCL-YYYY-NNNN notice PDF (in /home/ttran/foreclose_file or the folder the user names) and record its sale details into property_data.csv.

## Ledger location (hard rule)

CSV target: /home/ttran/foreclose_file/<FilingYear>/<FilingMonth>/property_data.csv — the PDF's own directory (FilingYear, FilingMonth from the /home/ttran/foreclose_file/<year>/<month> layout; the FilingYear in the FRCL-XXXX-NNNN doc ID must agree).
**Precondition: that directory must already exist.** If it does NOT exist when the skill runs, STOP immediately — report that the folder is missing and do nothing else. Do NOT create it (no mkdir), do NOT save the CSV elsewhere, do NOT proceed to extraction.

## Duplicate check (hard rule)

The **File Name** column (PDF basename WITHOUT .pdf extension, e.g. FRCL-2026-7208) is the deduplication key.
- BEFORE processing ANY PDF, read the ledger and build the set of File Names already in it.
- Process ONLY listings whose File Name is NOT in that set — in both single-doc and batch mode anything already recorded is skipped: no re-render, no re-extraction, no re-merge, never reported as new or updated.
- Report already-recorded IDs separately: "skipped (already in ledger)".
- When merging extracted rows (including salvaged rows.jsonl from crashed workers), drop any row whose File Name is already in the ledger.
- Re-extracting/updating an existing row happens only when the user explicitly asks to refresh or correct it (then follow the compare-and-update write semantics).

## Fields (extracted verbatim from the notice)

1. Date of Sale - e.g. 11/3/2026
2. Earliest Time Sale Will Begin - e.g. 10:00 AM
3. Place of Sale of Property - full section text (venue plus any fallback clause)
4. Legal Description - full section text verbatim (lot/block/subdivision/recording info)

## Procedure

Gate (before step 1): run the Duplicate check above — build the set of File Names from the ledger and confirm the target PDF's File Name is not in it. If it is, stop and report "skipped (already in ledger)"; do not extract.

1. Extract. These PDFs are image-only (no text layer; pdftotext returns empty). Do NOT try to pip install pypdf/pdfplumber - the Hermes venv python has no pip.
   - Render: pdftoppm -png -r 200 <pdf> <scratchdir>/page (system poppler works)
   - Then vision_analyze on the rendered PNG asking to transcribe EXACTLY, verbatim, the four fields above, quoting each section's full text.
   - Read the attached screenshot yourself and copy field text verbatim (keep case, punctuation, clause text). Never normalize street numbers or dates.
2. Timestamps: run date '+%Y-%m-%d %H:%M' for Date Added / Time Added (actual clock, not document dates).
3. Ledger path is the hard-rule target above: /home/ttran/foreclose_file/<FilingYear>/<FilingMonth>/property_data.csv (verify the directory exists FIRST — if not, stop per Precondition). Exact header:
   File Name,Date of Sale,Earliest Time Sale Will Begin,Place of Sale of Property,Legal Description,Date Added,Time Added
   - File Name = PDF filename WITHOUT extension (e.g. FRCL-2026-7208) - the dedup key.
   - Wrap any field containing commas (Place, Legal Description) in double quotes; escape inner quotes by doubling.
4. Write semantics (user-stated, follow exactly):
   - File missing: create with header plus this row.
   - File exists, File Name not in it: append row; do NOT rewrite the header.
   - File exists, File Name present: compare the 4 data fields to the existing row. Identical: do nothing, report already recorded. Different: update that row in place (keep the ORIGINAL Date Added/Time Added unless asked), report exactly what changed.
   - For multi-row work never drop other rows; when appending a single row, check the file first with cat, then write.
5. Verify: cat the CSV back; confirm the File Name row appears exactly once and other rows are intact. Report: path, row written / updated (what changed) / unchanged.

## Parallel Batch Mode (proved in the field)

For all PDFs in the folder:
- **Concurrency cap: 2 parallel child workers, NO MORE.** 10-way and 4-way both died: 'Provider has been unresponsive (no response received) for 5 consecutive stale attempts' / 'Operation interrupted: waiting for model response'. The shared model endpoint is concurrency-limited; the parent session's own turns can hit the same stall — retry on the next turn, nothing is lost.
- **Rolling waves**: split the unrecorded list into small waves (5-10 docs per child). The unrecorded list = all *.pdf in the folder MINUS the File Names already in the ledger (File Name = basename without .pdf extension — the dup-check hard rule); rebuild it fresh before EVERY wave so rows merged mid-batch are reflected in the next worklist. Prepare each wave as `runs/<wave>/<n>/list.txt` (one PDF basename per line). Dispatch exactly 2 children via delegate_task (one list each), wait for the consolidated result.
- **Child brief (what each child needs)**: full pipeline from Procedure steps 1-2; exact per-PDF steps: rm -f *.png; `pdftoppm -png -r 200 <pdf> <workdir>/pg`; vision_analyze pg-1.png asking the verbatim four-field question; if a field continues, vision_analyze the next page and combine verbatim (one space at joins); `date '+%Y-%m-%d %H:%M'` → date_added/time_added; append one JSON line to `runs/<wave>/<n>/rows.jsonl`: ok = {fn, sale_date, earliest_time, place_of_sale, legal_description, date_added, time_added, status=ok}; failed = {fn, status=failed, error}.
- **Salvage + merge after EACH wave**: a stalled/dead child still leaves partial `rows.jsonl` — parse it line by line, keep valid ok rows, re-run only the missing PDFs (re-list them). Then merge new rows into the ledger per the Write semantics above (append; never drop other rows; skip File Names already in the ledger). Continue to the next wave.
- **Multi-page notices (1-5 pages)**: the legal description may continue on page 2 - follow it verbatim. Metes-and-bounds EXHIBITS are separate attached documents (coordinate tables) - record the notice's own Property/Legal Description section, do NOT transcribe exhibit coordinate tables into the legal_description field.
- **Throughput**: ~10 min per doc per child (7-8 API calls each) → ~12 docs/hour at 2 parallel. A 600-doc folder is a ~1.5-day run at this pace; set expectations before starting.

## Pitfalls (hit in the field)

- Empty pdftotext output means image-only PDF, NOT missing content: render + vision, never report no data.
- Do not pip install into the Hermes venv (no pip); system pdftotext/pdftoppm plus vision_analyze is the working path.
- Place of Sale often includes a fallback clause (OR IN THE AREA DESIGNATED BY THE COMMISSIONER'S COURT...) - include the full clause; it is legally meaningful.
- Batch mode (all PDFs in a folder): see Parallel Batch Mode — 2 parallel child workers max, rolling waves of 5-10 docs, salvage partial rows.jsonl of dead workers and re-list missing PDFs; skip property_data.csv and already-recorded IDs; report per wave: new / failed.
- Notices are filed days before sale; Date of Sale later than today is normal.
