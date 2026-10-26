---
name: harris-county-monthly-pipeline
description: Use when running the monthly Harris County FRCL pipeline.
version: 1.0.0
author: TNTran92
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [foreclosure, harris-county, pipeline, csv, monthly]
    category: productivity
    related_skills: [harris-county-foreclosure-downloads, harris-county-sale-data-csv]
---

## When to Use
- The user asks to "run the pipeline" / "process the month" for a Harris County FRCL window — i.e. turn one (year, month) into that month's notice PDFs plus its finished `property_data.csv`.
- Monthly cadence: pull that filing month's FRCL notices from the clerk, then extract the four sale fields from each into the ledger.

This is the UMBRELLA skill: it holds only the ORDER, the HANDOFF INVARIANTS between the two steps, and the step-scope rules. Each step delegates to its dedicated skill — load that skill and follow it. This page is not a copy of either sibling.

## Required input (ask once, up front)
- **Date mode** — `FileDate` (filed in the month; default and recommended) or `SaleDate` (sold in the month).
- **Year** + **Month** (capitalized English word, e.g. October 2026).
The selected (year, month) drives BOTH steps and becomes the folder + ledger path; it must be the SAME value in both steps.

## The pipeline (strict order)

### Step 1 — Pull the month's notices
Skill: `harris-county-foreclosure-downloads`.
- Crawl ALL result pages of `FRCL_R.aspx` for (mode, year, month); collect the `a.doclinks` hrefs (never open the viewer tab — the ID token is session-bound).
- Skip any `<DocID>.pdf` already present in the target folder; download the rest to
  `/home/ttran/foreclose_file/<FilingYear>/<FilingMonth>/<DocID>.pdf`.
- Done when the folder holds every new notice PDF for that (year, month) and the report lists new vs skipped + a `file` check per new PDF.

### Step 2 — Extract the sale fields into the ledger
Skill: `harris-county-sale-data-csv`.
- Precondition (HARD): the Step 1 folder must already exist. If it does not, STOP — do not create it, do not silently rerun Step 1.
- For each unrecorded PDF: `pdftoppm -png -r 200` render, then `vision_analyze` for the four verbatim fields (Date of Sale, Earliest Time Sale Will Begin, Place of Sale of Property, Legal Description).
- Dedup key = File Name (PDF basename sans extension); skip anything already in `property_data.csv`.
- Append / update the row in `/home/ttran/foreclose_file/<FilingYear>/<FilingMonth>/property_data.csv`.
- Done when `cat` of the CSV shows each new File Name exactly once, other rows intact, and the report lists new / updated (what changed) / unchanged / skipped.

## Hard rules (cost real time when broken)
1. **Step order is enforced by the folder.** Step 1 does the `mkdir -p <year>/<month>`; Step 2 has a hard precondition that the folder already exists. So Step 1 always runs before Step 2 — and never backfill Step 2 data while "finishing" Step 1, or vice versa.
2. **One folder, one date.** Both steps read/write the SAME `/home/ttran/foreclose_file/<FilingYear>/<FilingMonth>/`. The (year, month) selected in Step 1 is the hard-rule ledger target in Step 2 — the FRCL id's FilingYear must agree with the folder's year. Never let the two steps disagree on the month.
3. **Idempotent, resumable.** Both steps skip work already done (Step 1 skips existing PDFs; Step 2 skips existing File Names). It is therefore safe to re-run after a session reset or crash. Do not force a redo unless the user explicitly asks to refresh a row (then use the sibling's compare-and-update semantics).
4. **Image-only PDFs — no text layer.** Empty `pdftotext` output means RENDER + `vision_analyze`, never "no data." Transcribe the four fields verbatim (case, punctuation, the fallback clause); never normalize street numbers or dates.
5. **Concurrency caps (host-limited endpoint).** Step 1: 8-way parallel `curl` is fine. Step 2: **2 child workers MAX**, rolling waves of 5–10 docs; merge each worker's rows into the ledger the instant that worker returns (never batch-merge at wave end); salvage a dead worker's partial `rows.jsonl` and re-list its missing PDFs.

## Handoff invariant (what binds Step 1 → Step 2)
- **Artifact:** the notice PDFs in `/home/ttran/foreclose_file/<FilingYear>/<FilingMonth>/`.
- **Dedup key consistent across both steps:** File Name = `<DocID>` (basename sans `.pdf`) — the same token Step 1 downloads and Step 2 uses as its dedup key.
- **Field scope:** Step 2 transcribes the notice's OWN Property / Legal Description section — NOT any attached metes-and-bounds EXHIBIT (a separate coordinate-table document). Multi-page notices: follow the legal description onto page 2 verbatim (one space at joins).

## Definition of done (monthly)
- `/home/ttran/foreclose_file/<FilingYear>/<FilingMonth>/` contains the month's notice PDFs AND a `property_data.csv` whose new File Names each appear exactly once.
- CSV header is exactly: `File Name,Date of Sale,Earliest Time Sale Will Begin,Place of Sale of Property,Legal Description,Date Added,Time Added`.
- Final report lists, per step: new, updated (what changed), unchanged, skipped — and every blank/failed row carries a stated reason.

## Cross-cutting pitfalls (apply to both steps)
- **Browser session resets between turns** — Step 1's navigate → select → search → collect-links must be ONE `browser_exec` call; `js()` is pinned to an attached tab and must be a zero-arg IIFE.
- **Notices are filed days before sale** — a Date of Sale later than today is normal, not a data error.
- **Place of Sale fallback clause** (OR IN THE AREA DESIGNATED BY THE COMMISSIONER'S COURT…) is legally meaningful — capture the full clause, not just the venue.
- **No pip into the Hermes venv** (there is no pip); the working path is system `pdftotext`/`pdftoppm` + `vision_analyze`.
