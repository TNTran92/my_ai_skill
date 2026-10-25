---
name: fortbend-sale-data-extraction
description: Use when filling property_data.csv from Fort Bend sale PDFs.
version: 1.0.0
author: TNTran92
license: MIT
metadata:
  hermes:
    tags: [foreclosure, fort-bend, pdf, csv, extraction]
    related_skills: [fortbend-foreclosure-monthly-pdfs, harris-county-foreclosure-downloads, harris-county-sale-data-csv]
---

## When to Use
- Monthly Fort Bend FRCL folder (`foreclose_file_fortbend/<year>/<Month>/`) has been downloaded and needs `property_data.csv` built.
- Rebuilding/refreshing an existing `property_data.csv` for that folder (preserves each row's original Date/Time Added).
- Debugging why one PDF's field came out null — use the per-PDF probe below.
- Do NOT use for Harris County clerk-site downloads (see harris-county-* skills) or Fort Bend PDF collection (see fortbend-foreclosure-monthly-pdfs).

# Fort Bend Sale-Data CSV Extraction

Capture sale fields from single-page Fort Bend foreclosure notice PDFs into `property_data.csv` in the same folder. Text layer already exists — never OCR.

## Inputs / output
- Folder: `/home/ttran/foreclose_file_fortbend/<year>/<Month>/` — ~300-500 single-page PDFs named `<Month>_<YYYY>_NNN.pdf`. Only ~40% are real sale notices; the rest are covers, notary certificates, exhibits, servicer boilerplate.
- Output: `property_data.csv` in that folder with EXACTLY this header:
  `File Name, Date of Sale, Earliest Time Sale Will Begin, Place of Sale of Property, Legal Description, Date Added, Time Added, Property Address`
- Date Added / Time Added = wall-clock entry time (date `YYYY-MM-DD`, time `HH:MM`), NOT any date from the document. When rebuilding, preserve each existing row's original values (driver does this automatically).
- Keep all extracted text VERBATIM (OCR quirks included) — no normalization of legal descriptions.

## Run (the whole job, 1 command)
```bash
python3 <skill_dir>/scripts/build_csv.py /home/ttran/foreclose_file_fortbend/<year>/<Month>
```
`build_csv.py` scans the folder, keeps only notice pages, writes the CSV, and prints per-column fill stats + verification. ~15s for 480 PDFs. Dependencies: `pdftotext` (poppler-utils), system python3 stdlib only.

Per-PDF probe (debug a single file):
```bash
python3 -c "import importlib.util as u; s=u.spec_from_file_location('fb','<skill_dir>/scripts/fb_extract.py'); m=u.module_from_spec(s); s.loader.exec_module(m); print(m.extract('<pdf_path>'))"
```
(`fb_extract.py`'s bare `__main__` mode is hard-coded to 2026/October; use the import form for other months.)

## Validation protocol (user requires stability steps — never skip)
1. Pilot 2 diverse files (one labeled-block, one narrative) and eyeball every field against raw `pdftotext -layout` output.
2. Regression set (October 2026 proven cases): 012, 062, 087, 205, 060, 100, 024, 023, 057, 076, 082, 090 — all should extract date+time; 057/033/016/042 legal desc is a genuine null (exhibit not scanned).
3. Full run; expect roughly: ~199/480 notice rows; date ~140, time ~125, place ~140, legal ~150, address ~105 filled; 30-ish rows fully complete; 0 errors.
4. Verify: header exact, unique file names, row count, blank counts printed. Spot-check 3 random rows + any row you suspect.

## Template families (all handled by fb_extract.py)
- **A** labeled: `Legal Description:` / `Date of Sale: 10/14/2026   Earliest Time Sale Will Begin: 10:00 AM` / `Location of Sale: <venue … Commissioners Court>`
- **B** narrative: `to-wit; <desc> … on 10/21/2026 at 1:00 PM … The sale will take place at <venue> as follows: …`
- **C** numbered: `1. Date, Time, and Place of Sale.` + `Date:`/`Time:`/`Place:`; `2. Property To Be Sold.` + `Commonly known as: <addr>`
- **D** deed-form: `SUBJECT REAL PROPERTY (LEGAL DESCRIPTION): <desc>`; `no earlier than 10:00 AM`
- **E** Auction.com spaced `SALE INFORMATION` block (`Property Address:` label)
- **F** DEED-info form: `Property To Be Sold - The Property described as follows:` + `Sale Information: October 06, 2026, at 1:00 PM ... at The Fart Bend County Gus George Academy...`

## Anchor phrases used
- legal label: `legal description`, `property to be sold`, `subject real property (legal description)`, `described as fo?llows/below`, bare `property:`, `to-wit`
- date: `date of sale` / `date, time, and place of sale` / bare `date:` / narrative `on <date> … sale` within 250 chars
- time: `earliest time sale will begin`, `no earlier than`, bare `TIME:`, `sale will begin at H:MM`, `between ... o'clock`, `at H:MM A/PM`
- place: `location of sale:`, `place:`, `the sale will take place at`, `sale will be conducted` — collect until terminator `Commissioner(s) Court`/`posted` (trim there) or a section-stop (numbered heading, `terms of sale`, etc.)
- address: `commonly known as`, `property address`, else unlabelled street line in top ~60% of page (numeral + name + street suffix; strip trailing 5+digit tracking number; append next `City, TX 12345` line)

## Hard-won pitfalls (do not rediscover)
- **Python `re.I`/casefold does NOT map `l`↔`I`.** OCR turns `will`→`wiI`/`wiII`. Every `will` pattern must be written `w\w*`, never `will` with `re.I`. Same for `begin`-style variants.
- Year sanity: candidate sale dates must be `>= 2025` or deed/recording dates leak into `Date of Sale` (e.g. a 2026 sale grabbed a 2021 deed date).
- OCR variants seen (handled in OCR_FIX + tolerance patterns): `wiI/wiII`, `pluce`, `Connty`, `1S`, `mE`, `tenns`, `staled/stateli/seated`, `Oclober/oclober` (no trailing `\b` — breaks on `Oclober6`), `TIIE`, `slide no.`→`plat no.`, `foDows`→`follows` (hence `fol\w*`), `Port Bend`→`Fort Bend` (hence `[fp]ort\s*bend`), `bate of sale`, o'clock word hours, `Fart Bend`, hour digits mangled to `I` (`I :00 PM` = 1:00).
- Inline routing-stamp junk (e.g. `CO~lliY'CLERK , FORT BENO COUNTY TFXM`) can sit on the label line or between label and description — stripped by the OCR_FIX entry and the LEGAL_JUNK line rule.
- Address lines can have a long tracking digit run appended — cut at `\s+\d{5,}` before matching.
- Legal description `_collect`: allow up to 1 blank line before content, break at 2 consecutive blanks after content started; requires `len>40` AND `LEGAL_GOOD` (Fort Bend County mention) so servicer addresses never pass as legal desc.
- **True nulls are normal**: ~50 pages say "described in the attached Exhibit A" and the exhibit page isn't in the folder; ~60 pages have no day digit or time, or only a city line without a street line. Blank is CORRECT — never fabricate, never treat as failure.
- **Interrupted `execute_code` calls roll back patches made inside them.** After any batch of patches, re-verify on disk (check each marker string is present) before re-running. (Bit us twice in October 2026.)
- **Subagent fan-out is unreliable on this host for this work** (concurrency-limited endpoint stalls). Do the whole batch directly in the session — it's fast (~15s) anyway.
- Dates normalize to `M/D/YYYY`; times to `H:MM AM|PM` (default PM when missing). Everything else stays verbatim.

## When a new month has misses
1. `pdftotext -layout file.pdf -` and find the raw label phrasing.
2. Add the pattern to the matching finder in `fb_extract.py`, NOT ad-hoc in the driver.
3. Re-run the regression set, then the full folder. The extractor is deliberately conservative — prefer missing a field over grabbing the wrong one (servicer addresses, deed dates).