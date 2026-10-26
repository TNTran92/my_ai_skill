#!/usr/bin/env python3
"""Batch-standardize the 'Legal Description' column of a Fort Bend foreclosure CSV.

Usage:
  python3 standardize_legal.py <folder> [--api BASE] [--model NAME] [--progress FILE] [--csv PATH]

- Serial Ollama calls (~3 s/row with think:false on qwen3.8:27b). Do NOT parallelize.
- Resumable: append-only JSONL progress at <folder>/legal_progress.jsonl; rows already
  status==OK are skipped on rerun. Records store the ORIGINAL raw text for later
  verification (apply_legal.py).
"""
import argparse, csv, json, os, sys, time, urllib.request

CANDIDATES = [c for c in [
    os.environ.get('OLLAMA_API', '').rstrip('/'),
    'http://ollamacuda.home:11434',
    'http://127.0.0.1:11434',
] if c]
DEFAULT_MODEL = 'qwen3.8:27b-q4_K_M'

SYS = (
    "You rewrite messy OCR'd legal property descriptions from Fort Bend County, Texas, "
    "foreclosure sale notices into ONE clean sentence in standard deed style.\n"
    "Target style example (structure only; NEVER copy these values onto other properties): "
    '"Lot Six (6) Block One (1) of Waterside Estates, Section One (1), an addition in Fort Bend County, '
    'Texas, according to the map or plat thereof, recorded under plat no. 2074/B of the plat records of '
    'Fort Bend County, Texas."\n'
    "Rules:\n"
    "- Preserve EVERY substantive fact exactly: lot, block, subdivision name, section, replat/addition, "
    "plat number, county, acreage, abstract number, volume/page references. Render word-number pairs as "
    "'Word (number)'. 'Volume X, Page Y' references stay Volume/Page - never rewrite them as 'plat no. X/Y'.\n"
    "- Fix obvious OCR errors (l vs 1, I vs 1, O vs 0, mangled words) sensibly; keep the numeric reading "
    "when ambiguous.\n"
    "- Strip everything non-substantive: sale dates/times, venues, street addresses, deed-of-trust and "
    "instrument numbers, servicer/trustee boilerplate, grantor names, statute clauses (e.g. 51.0076), "
    "$ amounts, APN/tax-id strings.\n"
    "- Keep Exhibit-A / condominium / field-notes descriptions: clean their wording but retain the exhibit "
    "reference, project/unit/phase info, and every measured boundary present in the input.\n"
    "- NEVER invent facts not present in the input. Do not truncate: if a plat number or boundary is in "
    "the input, it must appear in your output.\n"
    "- Output ONLY the rewritten description text. If the input contains no substantive property "
    "description at all, output exactly NO_DESCRIPTION."
)

def pick_api(model, candidates):
    for base in candidates:
        try:
            with urllib.request.urlopen(base + '/api/tags', timeout=4) as r:
                names = [t['name'] for t in json.loads(r.read()).get('models', [])]
            if model in names:
                return base
            print(f"  ({base} up but no '{model}'; has: {names[:6]})", flush=True)
        except Exception:
            print(f"  ({base} unreachable)", flush=True)
    sys.exit("ERROR: no reachable Ollama serving model " + model)

def call(api, model, raw):
    body = json.dumps({
        "model": model, "stream": False, "think": False,   # think:false is REQUIRED or rows come back empty
        "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 700},
        "messages": [{"role": "system", "content": SYS},
                     {"role": "user", "content": raw}],
    }).encode()
    last, t0 = 'empty', time.time()
    for i in range(4):
        t0 = time.time()
        try:
            req = urllib.request.Request(api + '/api/chat', data=body,
                                         headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=900) as r:
                d = json.loads(r.read())
            out = (d.get('message') or {}).get('content', '')
            wall = round(time.time() - t0, 1)
            if out and 'NO_DESCRIPTION' not in out:
                return 'OK', out, wall, i + 1
            if out:
                return 'NO_DESCRIPTION', out, wall, i + 1
            last = 'empty content'
        except Exception as e:
            last = f'{type(e).__name__}: {e}'
        print(f"     retry {i+1}: {last}", flush=True)
        time.sleep(3 * (i + 1))
    return 'FAILED', '', round(time.time() - t0, 1), 4

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('folder')
    ap.add_argument('--csv', default=None)
    ap.add_argument('--api', default=None)
    ap.add_argument('--model', default=DEFAULT_MODEL)
    ap.add_argument('--progress', default=None)
    a = ap.parse_args()
    csvp = a.csv or os.path.join(a.folder, 'property_data.csv')
    prog = a.progress or os.path.join(a.folder, 'legal_progress.jsonl')
    api = a.api or pick_api(a.model, CANDIDATES)
    print(f"API: {api}   MODEL: {a.model}", flush=True)

    rows = list(csv.reader(open(csvp)))
    header, data = rows[0], rows[1:]
    li = header.index('Legal Description')
    done = set()
    if os.path.exists(prog):
        for line in open(prog):
            if line.strip() and json.loads(line).get('status') == 'OK':
                done.add(json.loads(line)['key'])
    targets = [r for r in data if r[li].strip() and r[0].split(',', 1)[0] not in done]
    print(f"{len(data)} rows | already OK: {len(done)} | to process: {len(targets)}", flush=True)

    pf = open(prog, 'a')
    for n, row in enumerate(targets, 1):
        key = row[0].split(',', 1)[0]
        raw = row[li].strip()
        print(f"[{n}/{len(targets)}] {key}", flush=True)
        status, out, wall, att = call(api, a.model, raw)
        rec = {'key': key, 'status': status, 'out': out, 'wall': wall,
               'raw': raw, 'attempt': att}
        pf.write(json.dumps(rec) + '\n'); pf.flush()
        print(f"     -> {status} ({wall}s)", flush=True)
    pf.close()
    print("done. progress:", prog)

if __name__ == '__main__':
    main()
