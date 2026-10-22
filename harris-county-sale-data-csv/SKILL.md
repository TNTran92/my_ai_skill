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

## Fields (extracted verbatim from the notice)

1. Date of Sale - e.g. 11/3/2026
2. Earliest Time Sale Will Begin - e.g. 10:00 AM
3. Place of Sale of Property - full section text (venue plus any fallback clause)
4. Legal Description - full section text verbatim (lot/block/subdivision/recording info)

## Procedure

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

## Pitfalls (hit in the field)

- Empty pdftotext output means image-only PDF, NOT missing content: render + vision, never report no data.
- Do not pip install into the Hermes venv (no pip); system pdftotext/pdftoppm plus vision_analyze is the working path.
- Place of Sale often includes a fallback clause (OR IN THE AREA DESIGNATED BY THE COMMISSIONER'S COURT...) - include the full clause; it is legally meaningful.
- Batch mode (all PDFs in a folder): loop over *.pdf, skip property_data.csv and already-recorded IDs unless the user asked to refresh; report per file: new / updated / unchanged.
- Notices are filed days before sale; Date of Sale later than today is normal.
