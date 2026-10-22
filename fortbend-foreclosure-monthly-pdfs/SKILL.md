---
name: fortbend-foreclosure-monthly-pdfs
description: Use when pulling Fort Bend monthly foreclosure PDFs.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [Fort Bend County, Foreclosure, FRCL, PDF, monthly-list, burst]
    category: productivity
    related_skills: [frcl-property-address-csv, harris-county-foreclosure-downloads, harris-county-sale-data-csv]
---

# Fort Bend County — Monthly Foreclosure List PDF → per-page PDFs

Fetch the official Fort Bend County clerk **monthly foreclosure sales notice** PDF and split it into one-PDF-per-page. Proven end-to-end Oct 22, 2026 (October-2026.pdf → 480 pages).

## When to Use
Load this for any ask like "pull/save the [month] Fort Bend (foreclosure) PDF", "download the Fort Bend clerk monthly foreclosure list", or "burst the Fort Bend October PDF into pages" — i.e. getting the official monthly list into `/home/ttran/foreclose_file_fortbend/` and/or splitting it. Do **not** use for Harris County (different clerk site) or for per-case data extraction (see the related skills).

## Output locations (exact)
- Base dir: `/home/ttran/foreclose_file_fortbend/[year]/[month]/` — `year` 4-digit (`2026`), `month` full English name (`October`). `mkdir -p` it.
- Full list PDF: `October-2026.pdf` (Month-Year, dash).
- Burst pages: `October_2026_001.pdf` … `October_2026_NNN.pdf` (Month_Year, underscore, 3-digit zero pad). Keep the original alongside.

## Steps (all verified — just run them)
1. **Find the month link** — official page lists `October 2026 [PDF]`, `November 2026 [PDF]`, …:
   ```
   curl -sL --max-time 60 -A "Mozilla/5.0 (X11; Linux x86_64)" \
     "https://www.fortbendcountytx.gov/government/departments/county-clerk/search-for-foreclosures" \
     | grep -oiE 'href="[^"]*pdf"' | sort -u
   ```
   PDF URL pattern (may change — always grep the page, don't hardcode): `.../document-central/county-clerk-documents/home-page-county-clerk/research-foreclosures/October-2026.pdf`.
2. **Download** (plain curl works — no login wall, no bot wall):
   ```
   curl -sL --max-time 180 -A "Mozilla/5.0 (X11; Linux x86_64)" -o October-2026.pdf "<PDF URL>"
   ```
3. **Verify it's really the official list:
   ```
   file October-2026.pdf          # "PDF document, version 1.6"
   pdftotext -f 1 -l 2 October-2026.pdf - | head -30
   ```
   Must contain `FORECLOSURE SALES NOTICE` + `Fort Bend County` + Commissioners Court order. If `file`/`pdftotext` shows HTML, a 403/error page was downloaded — retry with the UA header.
4. **Burst** (`pdftk` is at `/usr/bin/pdftk` on this host):
   ```
   pdftk October-2026.pdf burst output October_2026_%03d.pdf
   ```
5. **Verify:** `ls October_2026_*.pdf | wc -l` equals `pdfinfo October-2026.pdf | grep Pages` (Oct 2026: 480). Spot-check first/mid/last file each show `Pages: 1`.

## Facts (grounding, not steps)
- Sales are held **first Tuesday of each month, 10 AM–4 PM**; since Dec 2 2025 the venue is **Gus George Law Enforcement Academy, Patton Hall, 1521 Eugene Heimann Circle, Richmond, TX 77469** (moved per Commissioners Court order 2025082537) — NOT the courthouse as in the old clerk boilerplate.
- List is published on/before the 20th of each month; it's a scanned list (front-matter pages have an OCR text layer via `pdftotext`; notice pages may not — use the same render+vision flow as the Harris County skills when reading them).
- The clerk office says it "is not involved with the sales" — the PDFs are just the posted notices.
- If later extracting sale details/addresses, mirror the Harris County skills: per-page PDFs are the unit of work; one notice may span several pages (check continuation text before splitting a case across files).
