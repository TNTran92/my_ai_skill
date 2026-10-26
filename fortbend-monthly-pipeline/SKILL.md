---
name: fortbend-monthly-pipeline
description: Use when processing a monthly Fort Bend foreclosure folder.
version: 1.0.0
author: TNTran92
license: MIT
metadata:
  hermes:
    tags: [foreclosure, fort-bend, pipeline, csv]
    related_skills: [fortbend-foreclosure-monthly-pdfs, fortbend-sale-data-extraction, fortbend-legal-desc-standardization, fortbend-legal-desc-to-address]
---

## When to Use
- The user asks to "process" a monthly Fort Bend folder (`/home/ttran/foreclose_file_fortbend/<year>/<Month>/`) — i.e. get `property_data.csv` from raw PDFs into its finished state.
- Monthly refresh: new month's PDFs downloaded (fortbend-foreclosure-monthly-pdfs), now turn them into the finished ledger.

This is the UMBRELLA skill: it is the ordered checklist. Each step below delegates to its dedicated skill — load that skill and follow it; this page holds only the order, the handoff invariants, and the step-scope rules.

## Hard rules (cost real time when broken)
1. **Steps are separate and user-scoped.** Do exactly the step the user named, in the order named. Never pull a later step's work in as part of an earlier one (e.g. never backfill blanks during sort/collapse; never address-draw during standardization). When a step is done, stop and report.
2. **Never modify `property_data.csv` without a backup first.** Convention: `property_data.csv.bak-<step>-<YYYYMMDD-HHMMSS>` (plain `.bak-YYYYMMDD` for sort/collapse). Keep them — they are the only undo.
3. **Blank is a valid final state.** Boilerplate-only rows, exhibit-only rows, raw rural tracts, and roll-absent properties stay blank. Fabricating a value to "finish" a row is the one unforgivable failure. Every blank gets a reason in the final report.
4. **Verification protocol is non-negotiable** (user requires stability steps): pilot a few rows → full run → spot-check a sample against the source (PDF text or tax-roll readback) → report counts + exception list before declaring done.

## The pipeline (in order)

### Step 0 — PDFs are in the folder
Check ~300–500 files `<Month>_<YYYY>_NNN.pdf`. If absent, run `fortbend-foreclosure-monthly-pdfs` first.

### Step 1 — Extraction → `property_data.csv`
Skill: `fortbend-sale-data-extraction`.
```bash
python3 /home/ttran/.hermes/skills/my_ai_skill/fortbend-sale-data-extraction/scripts/build_csv.py /home/ttran/foreclose_file_fortbend/<year>/<Month>
```
Exits with per-column fill stats. Expected shape (Oct 2026 anchor): ~199 notice rows out of ~480 PDFs; date ~140, time ~125, place ~140, legal ~150, address ~105 filled. Big deviations → upstream PDF change or extractor regression; use that skill's regression set.

### Step 2 — Sort + same-property collapse
Procedure: the `csv-collapse.md` reference file of the fortbend-sale-data-extraction skill (load via skill_view) — backup → sort by numeric suffix → prove pair identity on T.S. no / DOCUMENT NO, never similarity alone → union-merge → verify diff vs backup). Oct 2026 anchor: 199 → 197 rows (242+244, 426+434 collapsed; six "11988 exit 5 pkwy" rows kept separate — mail-to address).

### Step 3 — Legal Description standardization
Skill: `fortbend-legal-desc-standardization`.
```bash
python3 /home/ttran/.hermes/skills/my_ai_skill/fortbend-legal-desc-standardization/scripts/standardize_legal.py /home/ttran/foreclose_file_fortbend/<year>/<Month>
python3 /home/ttran/.hermes/skills/my_ai_skill/fortbend-legal-desc-standardization/scripts/apply_legal.py /home/ttran/foreclose_file_fortbend/<year>/<Month> [--fixes fixes.json]
```
~3 s/row on Ollama; resumable; read the loss report, hand-fix flagged rows. Oct 2026 anchor: 142 standardized, 4 boilerplate kept raw, 51 genuinely empty.

### Step 4 — Physical Address derivation (ONLY when asked)
Skill: `fortbend-legal-desc-to-address`.
```bash
python3 /home/ttran/.hermes/skills/fortbend-legal-desc-to-address/scripts/resolve_addresses.py /home/ttran/foreclose_file_fortbend/<year>/<Month> <path to progress.jsonl>
```
Auto-resolve strict (sec/blk/lot integer equality + name token vs FBCAD roll) → manual review pass over AMBIGUOUS/NOT_FOUND rows (name-variants.md token probes + plat-number web search) → write only decided rows, backup first. Oct 2026 anchor: 71 blank rows in → 61 filled, 10 left blank (boilerplate/exhibit/roll-absent), 165/197 with address.

## Definition of done (monthly)
- `property_data.csv`: 8-column header intact, sorted, one row per property, Legal Description standardized, Property Address filled wherever derivable — every remaining blank has a stated reason.
- Backup chain present; final report lists: row counts, filled/kept/blank per step, and the exception list (boilerplate rows, unresolvable addresses with WHY).

## Cross-cutting pitfalls (apply to every step)
- **Interrupted `execute_code` calls roll back in-cell patches** — after any in-cell edit to a script, verify it on disk before rerunning.
- **Subagent fan-out on this host is unreliable** (concurrency-limited endpoint) — batch jobs run directly in the session, serial; they are minutes, not hours.
- **Merged rows key on the File Name segment before the first comma** ("A.pdf,B.pdf" is one property).
- **Local Ollama `think:false` is mandatory** (documented in the standardization skill); ollamacuda.home flaps — the drivers auto-fall-back.
