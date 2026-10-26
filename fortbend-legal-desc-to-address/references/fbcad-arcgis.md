# FBCAD tax roll FeatureServer (legal description → address)

Endpoint (layer 0 is the full county tax roll):

```
https://services2.arcgis.com/D4saGHECICkCeoJm/arcgis/rest/services/FBCAD_Public_Data/FeatureServer/0/query
```

Sibling service `FortBendCADAdditionalLayers/FeatureServer` also exists but is not needed for address work.

## Useful fields
- `LEGAL` — full subdivision legal description, upper-case, e.g. `THE HIGHLANDS SEC 1, BLOCK 4, LOT 52` (may embed street names for ROW/utility parcels)
- `SITUS` — the physical street address, e.g. `1919 Barons GLN, Sugar Land, TX  77478` (double space before ZIP)
- `SITUSSTP`, `SITUSAPT`, `SITUSPODIR` — street type / apt / postal directional split fields
- `PROPNUMBER` — APN, format `zone-section-block(lot)-lot-907`, e.g. `3801-40-001-0300-907`
- `OWNERNAME` — current owner

## Query shape
GET or POST with:

- `where` — SQL on the fields, e.g.
  `UPPER(LEGAL) LIKE '%STONECREEK ESTATES%' AND UPPER(LEGAL) LIKE '%SECTION 9%' AND UPPER(LEGAL) LIKE '%BLOCK 1%' AND UPPER(LEGAL) LIKE '%LOT 1%'`
- `outFields=PROPNUMBER,OWNERNAME,SITUS,LEGAL`
- `resultRecordCount=<n>` — **hard cap on returned features; if `len(features) == n` the result is truncated.** Keep pools small via the WHERE clause and check the count.
- `returnGeometry=false`
- `f=json`

## Python (use this, not curl)

```python
import json, urllib.parse, urllib.request
URL = ("https://services2.arcgis.com/D4saGHECICkCeoJm/arcgis/rest/services/"
       "FBCAD_Public_Data/FeatureServer/0/query")
def q(where, limit=200):
    p = urllib.parse.urlencode({"where": where,
        "outFields": "PROPNUMBER,OWNERNAME,SITUS,LEGAL",
        "resultRecordCount": str(limit), "returnGeometry": "false", "f": "json"}).encode()
    with urllib.request.urlopen(urllib.request.Request(URL, p), timeout=120) as r:
        return json.loads(r.read()).get("features", [])
```

Or the one-line CLI: `python3 <skill_dir>/scripts/arcgis_query.py "UPPER(LEGAL) LIKE '%NAME%'" [limit] ["<second where term>"]` (second term is ANDed).

## Selection (scoring)
- Split each candidate's `LEGAL` on `,` — tokens like `HARVEST GREEN SEC 40`, `BLOCK 2`, `Lot 30` (lot token case varies).
- Required: subdivision-name token, section, block all present; lot present (equality as int; allow `N 2' OF LOT X` fragment = prefix match).
- Tie-break: more matching tokens wins; never take row order as rank.
- ROW/utility detection: `LEGAL` contains `ROW` with a street name and no residential lot, or `SITUS` is the road/line itself — exclude from residential selection.

## Name-dump trick (when the name is OCR-corrupted)
Query the longest distinctive token only (limit ~300), then extract distinct subdivision name prefixes client-side:

```python
import re, collections
c = collections.Counter()
for f in q("UPPER(LEGAL) LIKE '%TAMARRON%'", 300):
    u = (f['attributes'].get('LEGAL') or '').upper()
    m = re.search(r"([A-Z0-9 '\\.,() -]{0,40}TAMARRON[A-Z0-9 '\\.,() -]{0,20}(?=,|LOT|$))", u)
    if m: c[' '.join(m.group(1).split())[-45:]] += 1
print(sorted(c.items(), key=lambda kv: -kv[1])[:25])
```

This surfaces the roll's actual spelling (e.g. `TAMARRON SEC 7`) vs the notice text (`TALLARRON SEC 7`).
