#!/usr/bin/env python3
"""Resolve missing Property Address from Legal Description via the FBCAD tax roll.

Policy (fortbend-legal-desc-to-address skill):
- AUTO-RESOLVED only when the row has block AND lot and a candidate agrees on
  name token, section (no conflict), block, lot (all integer equality).
- Embedded "address at ..." in notice text -> EMBEDDED.
- Parcels/tracts/exhibit-only -> blank (legitimately absent).
- Everything else -> AMBIGUOUS / NOT_FOUND with pool info; human/web pass decides.

Progress JSONL is append-only and resumable.
"""
import csv, json, os, re, sys, time, urllib.parse, urllib.request
import collections

URL = ("https://services2.arcgis.com/D4saGHECICkCeoJm/arcgis/rest/services/"
       "FBCAD_Public_Data/FeatureServer/0/query")
import sys as _sys
OS = _sys.argv[1] if len(_sys.argv) > 1 else '/home/ttran/foreclose_file_fortbend/2026/October'
PROG = _sys.argv[2] if len(_sys.argv) > 2 else os.path.join(_sys.path and _sys.path[0] or '.', 'address_progress.jsonl')
FINAL = ('RESOLVED','EMBEDDED','NOT_FOUND','PARCEL_BLANK','EXHIBIT_BLANK')

STOP = {'OF','THE','FINAL','PLAT','ESTATES','VILLAGE','SECTION','SECT','REPLAT','RANCH',
        'COLONY','MEADOWS','LANDING','GREEN','GREENS','PARK','GLEN','GROVE','COMMONS',
        'PHASE','ADDITION','TOWN','SQUARE','AT','ON','IN','SOUTH','NORTH','WEST','EAST',
        'SOUTHWEST','NORTHWEST','FORT','BEND','COUNTY','TEXAS','TOWNHOME','VILLAS','LAKE'}

def q(where, limit=300):
    params = {"where": where, "outFields": "PROPNUMBER,OWNERNAME,SITUS,LEGAL",
              "resultRecordCount": str(limit), "returnGeometry": "false", "f": "json"}
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(urllib.request.Request(URL, data=data), timeout=120) as r:
        return json.loads(r.read()).get("features", [])

def parse(legal):
    d = {'name': None, 'section': None, 'block': None, 'lot': None}
    m = re.search(r'([A-Za-z0-9 \'\.\-]+)[,.;]\s*(?:Partial\s+)?(?:Replat|Section)', legal)
    span = m.group(1) if m else re.sub(r'^(?:Lot|Tract).*?\bof\b', '', legal, flags=re.I)
    d['name'] = span.strip(' ,.')
    d['tokens'] = sorted({t.upper() for t in re.findall(r"[A-Za-z][A-Za-z'\-]{3,}", span)
                          if t.upper() not in STOP}, key=len, reverse=True)
    m = re.search(r'Section\s+(?:\d+|[A-Za-z][A-Za-z0-9\- ]*?)\s*\((\d+[A-Za-z\-]*)\)', legal)
    d['section'] = int(re.match(r'\d+', m.group(1)).group(0)) if m else None
    m = re.search(r'Block\s+(?:\d+|[A-Za-z][A-Za-z0-9\- ]*?)\s*\((\d+)\)', legal)
    d['block'] = int(m.group(1)) if m else None
    m = re.search(r'Lot\s+(?:\d+|[A-Za-z][A-Za-z0-9\- ]*?)\s*\((\d+)\)', legal)
    d['lot'] = int(m.group(1)) if m else None
    return d

def ints(s, pat):
    return [int(x) for x in re.findall(pat, s.upper())]

def score(f, d, tokens):
    a = f['attributes']
    legal = (a.get('LEGAL') or '').upper()
    situs = (a.get('SITUS') or '').strip()
    lots = ints(legal, r'\bLOT\s+(\d+)')
    if re.search(r'\bROW\b', legal) and not lots:
        return None
    if not situs or not re.search(r'\d+\s+\w', situs):
        return None
    if tokens and not any(t in legal for t in tokens):
        return None
    blks = ints(legal, r'\b(?:BLOCK|BLK)\s+(\d+)')
    secs = ints(legal, r'\b(?:SECTION|SEC)\s+(\d+)')
    if d['block'] is not None and d['block'] not in blks: return None
    if d['lot'] is not None and d['lot'] not in lots: return None
    if d['section'] is not None and secs and d['section'] not in secs: return None
    s = (2 if tokens else 1)
    if d['section'] is not None and secs and d['section'] in secs: s += 2
    if d['block'] is not None: s += 1
    if d['lot'] is not None: s += 2
    return s, situs, (a.get('LEGAL') or '')[:160]

def sec_w(n): return "(UPPER(LEGAL) LIKE '%%SECTION %s%%' OR UPPER(LEGAL) LIKE '%%SEC %s%%')" % (n, n)
def blk_w(n): return "(UPPER(LEGAL) LIKE '%%BLOCK %s%%' OR UPPER(LEGAL) LIKE '%%BLK %s%%')" % (n, n)
def lot_w(n): return "UPPER(LEGAL) LIKE '%%LOT %s%%'" % n

def query_pool(where, d, tokens, limit=300):
    try:
        feats = q(where, limit)
    except Exception as e:
        return None, f'{type(e).__name__}: {e}'
    cands = {}
    for f in feats:
        s = score(f, d, tokens)
        if s: cands[f['attributes']['PROPNUMBER']] = s
    return cands, f'{len(feats)} pool'

def resolve_row(legal):
    m = (re.search(r'address at\s+(.+?(?:Texas|TX)\s+[\d,]{3,})', legal, re.I) or
         re.search(r'address at\s+(.+?)[,\.]+?\s*[\d,]{3,}', legal, re.I) or
         re.search(r'[Cc]ommonly known as:\s*(.+?)[\.\,]', legal))
    if m:
        return 'EMBEDDED', m.group(1).strip()[:120], legal[:80], 'address stated in notice text'
    if re.search(r'\bexhibit a\b|\bcondominium', legal, re.I):
        return 'EXHIBIT_BLANK', '', None, 'exhibit/condo reference, no parcel in roll'
    if re.search(r'survey,?\s+abstract no|field notes|acre tract|tract of \d', legal, re.I) \
       and not re.search(r'Block\s+.*?\(\d+\)', legal):
        return 'PARCEL_BLANK', '', None, 'raw tract/parcel, no street in roll'
    d = parse(legal)
    tokens = d['tokens'][:2]
    parts = []
    if tokens: parts.append(f"UPPER(LEGAL) LIKE '%{tokens[0]}%'")
    if d['section'] is not None: parts.append(sec_w(d['section']))
    if d['block'] is not None: parts.append(blk_w(d['block']))
    if d['lot'] is not None: parts.append(lot_w(d['lot']))
    if not parts:
        return 'NOT_FOUND', '', None, 'unparseable legal description'
    where = ' AND '.join(parts)
    cands, info = query_pool(where, d, tokens)
    if cands is None:
        return 'NOT_FOUND', '', None, info
    need = (7 if d['section'] is not None else 5)
    if d['block'] is not None and d['lot'] is not None:
        ok = [(apn, c) for apn, c in cands.items() if c[0] >= need]
        if ok:
            apn, (s, situs, matched) = max(ok, key=lambda kv: kv[1][0])
            return 'RESOLVED', situs, f'{apn}: {matched}', f'score={s}; {info}'
    # review pass: collect best candidates from variant/narrower queries (never auto-fill)
    pools = []
    for t in tokens:
        c2, i2 = query_pool(f"UPPER(LEGAL) LIKE '%{t}%'", d, [t])
        if c2:
            pools.append((max(c2.values())[0], f"tok {t}: {i2}; best={max(c2.values())[1]} | {max(c2.values())[2]}"))
    if d['section'] is not None and d['block'] is not None and d['lot'] is not None:
        c3, i3 = query_pool(sec_w(d['section']) + ' AND ' + blk_w(d['block']) + ' AND ' + lot_w(d['lot']), d, [])
        if c3:
            pools.append((max(c3.values())[0], f"no-name: {i3}; best={max(c3.values())[1]} | {max(c3.values())[2]}"))
    if pools:
        pools.sort(reverse=True)
        return 'AMBIGUOUS', '', None, f'{info}; ' + ' || '.join(p[1] for p in pools[:3])
    return 'NOT_FOUND', '', None, f'{info}; tokens={tokens} sec={d["section"]} blk={d["block"]} lot={d["lot"]}'

def main():
    rows = list(csv.reader(open(OS + '/property_data.csv')))
    header, data = rows[0], rows[1:]
    ai = header.index('Property Address'); li = header.index('Legal Description')
    done = {}
    if os.path.exists(PROG):
        for line in open(PROG):
            if line.strip():
                rec = json.loads(line)
                done[rec['key']] = rec
    todo = []
    for r in data:
        if r[ai].strip() or not r[li].strip():
            continue
        k = r[0].split(',',1)[0]
        if k in done and done[k]['status'] in FINAL:
            continue
        todo.append((k, r[li].strip()))
    print(f"to-do={len(todo)} already-final={len(done)}", flush=True)
    pf = open(PROG, 'a')
    for n,(k,legal) in enumerate(todo,1):
        t0=time.time()
        try:
            status, situs, matched, note = resolve_row(legal)
        except Exception as e:
            status, situs, matched, note = 'ERR', '', None, f'{type(e).__name__}: {e}'
        rec = {'key':k,'status':status,'situs':situs,'matched':matched,'note':note,'wall':round(time.time()-t0,1)}
        pf.write(json.dumps(rec)+'\n'); pf.flush()
        print(f"[{n}/{len(todo)}] {k} -> {status} ({rec['wall']}s)" + (f" | {situs}" if situs else ""), flush=True)
    pf.close()
    last = {}
    for l in open(PROG):
        if l.strip():
            rec = json.loads(l); last[rec['key']] = rec['status']
    print("final per-row:", dict(collections.Counter(last.values())))

if __name__ == '__main__':
    main()
