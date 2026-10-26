---
name: fortbend-legal-desc-to-address
description: Use when mapping Fort Bend legal descriptions to addresses.
version: 1.0.0
author: TNTran92
license: MIT
metadata:
  hermes:
    tags: [foreclosure, fort-bend, arcgis, address-lookup, csv]
    related_skills: [fortbend-monthly-pipeline, fortbend-sale-data-extraction, fortbend-legal-desc-standardization]
---

## When to Use
- `property_data.csv` in a Fort Bend monthly folder has non-blank Legal Description cells and the `Property Address` column needs filling or verification.
- Pipeline position: step 4 (last) of `fortbend-monthly-pipeline` — run it only when the user asks for the address step.
- Do NOT use for a cell that is boilerplate or truncated with no subdivision/section/block/lot (bare "Exhibit A" references) — nothing to match on; blank is correct, record it, move on.

## Data source (the only one that works)
- FBCAD's web portals (esearch.fbcad.org, the TrueProdigy taxpayer portal, fbcadmaps.org GeoMap) have NO legal-description search, and the public ArcGIS open-data hub is a demo without usable datasets. Do not spend time there; go straight to the tax roll.
- Tax-roll FeatureServer (fields, query shape, Python example): `references/fbcad-arcgis.md`; one-line query helper: `scripts/arcgis_query.py`.

## Workflow (per row, in this order)
1. **Check the legal text for an embedded address first** ("having an address at ...", "Commonly known as ..."). Some notices state the address in the description itself — highest-confidence source.
2. Parse: subdivision name, section, block, lot. Lots can be fragments ("LOT 27 & N 2' OF LOT 28") or combined with easement language — extract the numeric lot set.
3. If the row ALREADY has a Property Address: **verify before overwriting.** Query the subdivision + section, confirm that street appears there with the right block/lot. Consistent → keep existing. Do not clobber a good value with a weaker guess.
4. Query the roll: `UPPER(LEGAL) LIKE '%SUBDIV%' AND UPPER(LEGAL) LIKE '%SECTION <n>%' AND UPPER(LEGAL) LIKE '%BLOCK <b>%'` (add `%LOT <l>%` when the pool stays large).
5. **Score ALL candidates, pick the best** — section, block, lot all matched as integers (lot equality; fragment matching = lot prefix). Record the matched LEGAL string for the audit trail.
6. Zero hits on the name → OCR-corruption path in `references/name-variants.md` (token probes + roll name dump + web search by plat number).
7. Still nothing → web search (HAR, county plat index). Roll-absent AND web-absent → leave blank and list it in the final report. Unparsed lots, fresh splits not yet appraised, and rural tracts with no street are legitimately absent.

## Pitfalls (cost real time)
- **Embedded address beats everything — even when the same text also says "Exhibit A"** (Oct 2026 row 426: "...Exhibit A... having an address at 126 Annes Way, Stafford, Texas 77477"). The embedded extractor must capture through the state+zip ("...Texas 77477"), and the exhibit/condo reject must NOT fire before the embedded check succeeds.
- **Parser must handle standardized word-number form** (`Lot One (1)`, `Section Thirteen-A (13-A)`): capture the parenthesized number with `[A-Za-z0-9\- ]*?\((\d+...)\)` — a digit-first-only regex silently zeroes the row's lot/section and lets a wrong candidate pass.
- **Never accept a first/top match.** Candidate pools contain ROW, utility, and adjacent-section records; a top-1 hit matched the wrong lot in the right section. Require full sec+blk+lot agreement on the chosen row.
- **Compare lots as integers** (string compare false-matches: "9" vs "19", "30" vs "3").
- **Result-cap truncation:** every query returns at most `resultRecordCount` features; if `len(features) ==` the requested cap, the pool is silently cut. Add section/block terms to the WHERE to shrink it, and confirm the count drops below the cap before trusting an absence.
- **Use Python `urllib`, not `curl --get`** — AND clauses and apostrophes (e.g. `BUNTER' S`) mangle shell quoting. Generate apostrophe variants (with/without `'`) in the query.
- **Re-plats:** a new phase of an old subdivision may be appraised under a different section of the same name (a 2022 "Sec 4" replat that does NOT exist as Sec 4 in the roll). When the stated lot is absent from the old section's block, scan the whole name family for that block+lot — but a different-section hit is a *candidate*, never a confirm without sec/blk/lot corroboration.
- **OCR-corrupted subdivision names are common in notice text** (observed examples in `references/name-variants.md`). Probe distinctive tokens, read back the roll's actual names, and cross-check sec/blk/lot before mapping.
- **Never fabricate a street** for a row with genuinely none (raw land, exhibit-only). Blank + flagged list in the final report is the correct deliverable; same discipline as the extraction skill.
- **Batch discipline:** ~150 rows × several queries per row will time out in one shot. Persist per-row progress to JSON (status, chosen SITUS, matched LEGAL, note) and rerun from it; only write the CSV after every row is decided (resolved OR flagged-unresolvable). `scripts/resolve_addresses.py` implements this loop (arg1 = folder with property_data.csv, arg2 = progress file) — 71 rows in ~4 min, then a manual review pass over AMBIGUOUS/NOT_FOUND rows.

## Verification before declaring done
1. Audit a random sample of chosen rows: read the matched LEGAL string back from the roll and confirm sec/blk/lot against the CSV legal description.
2. After writing the CSV: row count unchanged, 8 columns intact, spot-check 3 rows including one hand-fixed name-variant row and one pre-existing address you preserved.
3. Final report lists: resolved count, preserved-existing count, and the flagged-unresolvable rows with the reason (roll-absent, OCR-name, exhibit-only).
