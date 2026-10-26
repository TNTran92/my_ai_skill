# OCR-corrupted subdivision names in Fort Bend FRCL notices

Foreclosure-notice text comes from OCR'd PDFs; subdivision names routinely arrive garbled while section/block/lot survive intact. Strategy: **match on sec/blk/lot, not on the name** — query distinctive tokens, dump the roll's actual names (name-dump trick in `fbcad-arcgis.md`), and confirm the sec/blk/lot match before mapping.

Observed mappings (October 2026 notice batch — expect this kind of drift, not these exact pairs):

| Notice text (OCR) | Roll name (FBCAD) | Notes |
|---|---|---|
| Tallarron | TAMARRON | one-letter swap; sec/blk/lot exact |
| Bunter's (Glen) | HUNTERS GLEN | "Bunter's" is corruption; lot fragment (`N 2'`) matched |
| HARB / "Harb" | LAKE SHORE HARBOUR | partial/abbreviated name in notice |
| The Idglands | THE HIGHLANDS | vowel/ligature loss |
| Sidpans Cove | (likely SHIPMANS / cove subdivision) | unresolved — verify by token probe + web before filling |
| Woods Edge Estates | WOODS EDGE | suffix variation is fine |
| Canyon Gate at Wesibeimer Lakes | Canyon Gate At Westheimer Lakes | name drift in both the modifier and the parent plat |
| Wilkin's Crossing | WILKINS CROSSING | apostrophe dropped in roll; query the no-apostrophe form |
| Hunter's Glen | HUNTERS GLEN | apostrophe->S in roll; `LIKE '%HUNTER%'` (no S) matches both — probe the stem |
| Quail Valley Subdivision, El Dorado Section | QUAIL VALLEY ELDORADO | "El Dorado Section" is part of the roll name, not a numbered Section |
| Replat of Lake Colony | LAKE COLONY | "Replat of" prefix is dropped in the roll |
| Sienna Section 43, A | Sienna Sec 43, ... | section number is INSIDE the roll's name token; query `UPPER(LEGAL) LIKE '%SEC 43%'`, not `%SECTION 43%` |
| Silver Ranch Sec. 9 | Silver Ranch Sec 9 | roll keeps `Sec N` in the name; case-insensitive query is fine |
| Harvest Green, Section Four (plat 20220255) | — (Sec 4, Block 1 has NO Lot 30 in roll) | replat-absent case: same block+lot exists in Secs 1,2,3,5,9,11-15,40-42 but never in Sec 4; left blank rather than guessing a section |

Rules:
- A name is confirmed only when the roll's own name string appears in the chosen row's `LEGAL` AND sec/blk/lot agree. Never fill an address from a name guess alone.
- **Apostrophe rule:** probe the stem without the apostrophe (`HUNTER`, `WILKIN`) — it matches both `NAME'S` and `NAMES`-style roll strings and is immune to OCR apostrophe loss.
- **Name-inside-name:** some rolls embed the section in the name token ("Sienna Sec 43", "Silver Ranch Sec 9"). If `SECTION <n>` LIKE fails, also try `%SEC <n>%` and treat name token + sec as one phrase.
- **Zero-pool triage:** if name+sec+blk+lot returns 0, re-run name-only (300-cap) first. If the pool is non-empty, the failure is sec/blk/lot formatting (lot fragments, R/P reserves, `S4` vs `SEC 4`), not an absent property. Only declare absence after the name-only pool has been scanned for the stated blk/lot.
- Prefer the roll's spelling in any downstream report; keep the notice spelling in the audit note.
- When the token probe returns several candidates in one county, disambiguate by city (`SITUS`) — e.g. a "Westheimer Lakes" name exists in both Katy and Richmond.
