#!/usr/bin/env python3
"""One-shot FBCAD tax-roll query (legal description → address work).

Usage:
  python3 arcgis_query.py "UPPER(LEGAL) LIKE '%STONECREEK%'" [LIMIT] ["UPPER(LEGAL) LIKE '%SECTION 9%'"]

Second where term (optional) is ANDed. Prints PROPNUMBER | SITUS | LEGAL (120 chars).
Stdlib only. Prints a WARNING when the result hit the requested cap (= pool truncated).
"""
import json, sys, urllib.parse, urllib.request

URL = ("https://services2.arcgis.com/D4saGHECICkCeoJm/arcgis/rest/services/"
       "FBCAD_Public_Data/FeatureServer/0/query")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    parts = [sys.argv[1]]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 100
    if len(sys.argv) > 2 and not sys.argv[2].isdigit():
        parts.append(sys.argv[2]); limit = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    if len(sys.argv) > 3 and sys.argv[2].isdigit():
        parts.append(sys.argv[3])
    where = " AND ".join(f"({p})" if not p.startswith("(") else p for p in parts)
    params = {
        "where": where,
        "outFields": "PROPNUMBER,OWNERNAME,SITUS,LEGAL",
        "resultRecordCount": str(limit),
        "returnGeometry": "false",
        "f": "json",
    }
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(urllib.request.Request(URL, data=data), timeout=120) as r:
        doc = json.loads(r.read())
    feats = doc.get("features", [])
    print(f"== {len(feats)} features (requested cap {limit}) ==")
    for f in feats:
        a = f["attributes"]
        legal = (a.get("LEGAL") or "").replace("\n", " ")[:120]
        print(f"{a.get('PROPNUMBER')} | {(a.get('SITUS') or '')[:55]} | {legal}")
    if len(feats) >= limit:
        print("WARNING: hit the result cap — the pool is truncated. Add section/block terms to the WHERE clause.")


if __name__ == "__main__":
    main()
