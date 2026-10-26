---
name: fortbend-legal-desc-standardization
description: Use when standardizing Fort Bend legal descriptions.
version: 1.0.0
author: TNTran92
license: MIT
metadata:
  hermes:
    tags: [foreclosure, fort-bend, csv, legal-description, ollama]
    related_skills: [fortbend-monthly-pipeline, fortbend-sale-data-extraction, fortbend-foreclosure-monthly-pdfs, fortbend-legal-desc-to-address]
---

## When to Use
- `property_data.csv` exists in a Fort Bend monthly folder (built via fortbend-sale-data-extraction) and its Legal Description cells are raw OCR (ALL CAPS, boilerplate mixed in) that must be rewritten into one clean sentence each.
- Rerun for a new month's folder: same two commands.
- Pipeline position: step 3 of the full monthly pipeline (see `fortbend-monthly-pipeline`); address derivation after it is step 4 of that same pipeline. Don't mix the steps.
- Do NOT use when asked to FILL missing/empty descriptions from the PDFs — that is backfill, a separate step the user must explicitly ask for.

## Target style
Example (structure only — never copy these values; every row gets its own lot/block/plat):
"Lot Six (6) Block One (1) of Waterside Estates, Section One (1), an addition in Fort Bend County, Texas, according to the map or plat thereof, recorded under plat no. 2074/B of the plat records of Fort Bend County, Texas"

KEEP every substantive fact: lot, block, subdivision, section, replat/addition, plat no, volume/page, acreage, abstract no, exhibit/condo/field-notes details. STRIP: sale dates/times, venue & street addresses, deed-of-trust/instrument numbers, servicer/trustee boilerplate, grantor names, statute clauses (51.0076), $ amounts, APN/tax-id strings. OCR errors (l vs 1, I vs 1, O vs 0) get fixed to the numeric reading. NEVER invent facts. Word-number pairs read as 'Word (number)'. 'Volume X, Page Y' stays Volume/Page.

## Run (2 commands)
```bash
python3 <skill_dir>/scripts/standardize_legal.py /home/ttran/foreclose_file_fortbend/<year>/<Month>
python3 <skill_dir>/scripts/apply_legal.py /home/ttran/foreclose_file_fortbend/<year>/<Month>
```
1. `standardize_legal.py` probes Ollama in order: `$OLLAMA_API` (if set) → `ollamacuda.home:11434` → `127.0.0.1:11434`, and uses the first host that has the model (default `qwen3.8:27b-q4_K_M`; override with `--model`). Serial, ~3 s/row, resumable: progress JSONL at `<folder>/legal_progress.jsonl`, only `status==OK` counts as done; rerunning after an interruption continues from where it stopped. Announce WHICH host served the batch.
2. `apply_legal.py` merges (fixes → best OK output → keep raw), prints a per-row loss report against the ORIGINAL raw (stored in each progress record), backs up to `property_data.csv.bak-legal-<ts>` only if it changes anything, writes, then self-verifies (row count, 8 cols, no `NO_DESCRIPTION` leakage, no formerly-non-empty cell emptied). Safe to rerun.

## Manual fixes (the flagged list)
When the report flags rows, read that row's RAW vs OUT, write a faithful cleanup (no invented facts) into a JSON file mapping primary key (File Name before the first comma) to full text, then:
```bash
python3 <skill_dir>/scripts/apply_legal.py <folder> --fixes fixes.json
```
Rows whose raw has NO substantive description (attorney/grantor boilerplate, or truncated mid-sentence like "...INCLU[...]DING the land...") stay as-is — blank/short is correct, never fabricate.

## Verification protocol (user requires stability steps)
1. After standardize, eyeball 3 outputs (one lot/block, one field-notes/tract, one exhibit-ref) before applying.
2. Apply report: losses of lot/block/plat/acreage/section numbers = NOT OK (fix + rerun); losses of dates, APNs, tracking/instrument numbers, $ amounts, clause numbers = correctly stripped, fine to ignore.
3. Truncation signature = output ending mid-phrase ("plat no.", "records of") — always hand-complete it from the raw, which holds the missing number.
4. Apply script's self-checks (rows, cols, leakage, emptied) must all pass before reporting done.

## Hard-won pitfalls (do not rediscover)
- **Always send `"think": false` in Ollama `/api/chat`** — without it qwen3.8:27b burns the whole num_predict budget thinking and ~20–30% of rows return EMPTY content; with it, ~3 s/row with good output. (Baked into standardize_legal.py.)
- **ollamacuda.home (192.168.10.12) flaps** — it has died mid-batch, leaving the job hung on TCP timeouts. The driver falls back to the same model on local `127.0.0.1:11434` automatically; both hosts carry `qwen3.8:27b-q4_K_M`. Don't block waiting on the remote box.
- **Serial only** on the GPU box (concurrency-limited endpoint; parallel calls stall). ~3 s/row serial is fine.
- **Known model failure modes, all actually hit and all catchable**: (a) truncated output ending mid-sentence; (b) Volume/Page recording rewritten as "plat no. 20/9" (format confusion — must stay "recorded in Volume 20, Page 9 of the plat records..."); (c) digit misreads ("LOT 1 4" → "Lot One" instead of Fourteen); (d) NO_DESCRIPTION given on describable condo-unit/Exhibit-A rows. (a)–(c) surface in the loss report; (d) by scanning NO_DESCRIPTION keys and reading their raw — some are hand-cleanable, some are genuinely boilerplate.
- **Do the loss check per-row inside the loop.** An inline recheck that reuses the loop variable after the loop ends reports the LAST row's text for every flagged row (false alarm, cost an hour once). `apply_legal.py` does it right; don't improvise sloppier checks in scratch Python.
- **Merged rows**: File Name may be "A.pdf,B.pdf" (same property collapsed into one row) — always key on the segment before the first comma.
- **Interrupted `execute_code` rolls back patches made inside it** — after any driver edit, verify on disk before rerunning.
- October 2026 reference anchor: 197 rows → 142 standardized, 4 kept as raw (boilerplate/truncated sources), 51 genuinely empty. Expect similar ratios in other months; big deviations mean check the extractor upstream.
