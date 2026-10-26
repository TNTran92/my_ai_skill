# Sort & same-property collapse (post-processing, no backfill)

Post-processing step on a monthly `property_data.csv` AFTER extraction. Rule that governs the whole step: use ONLY values already in the CSV — a blank cell stays blank. Backfilling from the PDFs is the prior, separate step; the user does not want the two mixed.

## Procedure
1. Back up first: `cp property_data.csv property_data.csv.bak-YYYYMMDD`. Never modify in place without a backup.
2. Parse with the `csv` module (fields contain quotes/newlines). Assert the exact 8-column header and 8 cells per row; count distinct File Names (typically already one row per file).
3. Sort ascending by numeric File Name suffix: `int(name.split('_')[-1])`.
4. Find candidate same-property pairs — union of:
   - exact normalized match on `Property Address`
   - pairwise `difflib.SequenceMatcher` ratio on normalized `Legal Description` (report every pair > 0.70)
   - identical Date of Sale + Place of Sale (weak evidence alone)
5. PROVE identity — similarity or a shared address is NEVER sufficient on its own:
   - Subdivision boilerplate inflates ratios: DIFFERENT lots in the same subdivision score 0.70–0.93 against each other. Only pairs ≥ ~0.95 are candidates, and even then diff the differing chunks and confirm LOT / BLOCK / SECTION / tract acreage are genuinely identical, not just the boilerplate.
   - A shared `Property Address` is often an attorney/mail-to address reused across many DISTINCT sales. Verify per PDF with `pdftotext -layout` and compare `T.S. #` / `APN`: different T.S. number = different sale = keep separate.
   - Strong same-property evidence across two PDFs: same borrower + trustee + beneficiary + recorded `DOCUMENT NO` (same loan, two notices), or identical street address with descriptions differing only in OCR.
6. Merge ONLY proven pairs, per column:
   - union of non-empty values; on conflict take the LONGER value (more complete). Never rewrite/normalize text — keep verbatim.
   - `File Name`: keep BOTH names, numeric order, joined with ", ".
7. Write with `csv.writer`, then verify:
   - re-read: assert sort order, 8 cells per row, exact header, distinct primary File Names
   - diff every row against the backup to prove only the intended collapsed rows changed (expected differences = collapsed rows only).

## Verified anchors (Oct 2026) — regression cases for this step
- KEEP SEPARATE: six rows all carrying "11988 exit 5 pkwy bldg 4" = six distinct sales (T.S. 26045/26221/26220/23797/23269/25977) — that string is a servicer mail-to address; ~20 legal-desc pairs at 0.70–0.93 similarity were all different lots (e.g. 235/312/315/321 Sienna, 068/146 Southern Colony, 060/144); 372 vs 376 = 16.081 vs 26.081 acre tracts in the same abstract despite 0.977 desc similarity.
- COLLAPSED: 242+244 (same loan DOCUMENT NO 2022014797, borrower Gohar Hameed — two notices of one sale); 426+434 (both 126 Annes Way, desc similarity 0.999). Result: 199 rows → 197.
