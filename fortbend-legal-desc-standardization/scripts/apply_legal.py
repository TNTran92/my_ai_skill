#!/usr/bin/env python3
"""Apply standardized Legal Description outputs to property_data.csv, with verification.

Usage:
  python3 apply_legal.py <folder> [--progress FILE] [--fixes fixes.json] [--csv PATH]

Per row (key = File Name segment before the first comma), the cell becomes:
  1. --fixes entry for that key (manual cleanup), else
  2. best OK output from the progress JSONL, else
  3. keep whatever is there (NO_DESCRIPTION / failed / genuinely-empty descriptions).

Before writing it prints a per-row loss report: numeric tokens (3+ digits or decimals)
present in the ORIGINAL raw but missing from the replacement, plus truncated-output
signatures. Expected losses: dates, APNs, tracking/instrument numbers, $ amounts,
statute clauses. NOT acceptable: lost lot/block/plat/acreage/section numbers.
Backs up to property_data.csv.bak-legal-<ts> only when it changes something;
safe to rerun (raw text comes from the progress records, not the current cell).
"""
import argparse, csv, json, os, re, shutil, time

TRUNC_SIG = ('plat no.', 'plat reco', 'records of', 'under plat no', 'recorded under')

def nums(s):
    return set(re.findall(r'\d{3,}|\d*\.\d+', s))

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('folder')
    ap.add_argument('--csv', default=None)
    ap.add_argument('--progress', default=None)
    ap.add_argument('--fixes', default=None, help='JSON {primary_key: full_clean_text}')
    a = ap.parse_args()
    csvp = a.csv or os.path.join(a.folder, 'property_data.csv')
    prog = a.progress or os.path.join(a.folder, 'legal_progress.jsonl')
    fixes = json.load(open(a.fixes)) if a.fixes else {}

    best = {}
    if os.path.exists(prog):
        for line in open(prog):
            if line.strip() and json.loads(line).get('status') == 'OK':
                best[json.loads(line)['key']] = json.loads(line)

    rows = list(csv.reader(open(csvp)))
    header, data = rows[0], rows[1:]
    li = header.index('Legal Description')

    changes, kept, flagged, used_fixes = 0, 0, 0, 0
    for r in data:
        primary = r[0].split(',', 1)[0]
        cur = r[li]
        rec = best.get(primary)
        if primary in fixes:
            text = fixes[primary]; used_fixes += 1
            base = ''  # manual text assumed reviewed; no automated check
        elif rec is not None:
            text = rec['out']
            base = rec.get('raw') or cur
        else:
            kept += 1
            continue
        if text == cur:
            continue
        base = base if (base and base != text) else ''
        if base:
            lost = sorted(nums(base) - nums(text))
            trunc = any(text.rstrip().endswith(s) for s in TRUNC_SIG)
            if lost or trunc:
                flagged += 1
                print(f"FLAG {primary}: lost={lost} truncated={trunc}")
                print(f"   RAW: {base[:200]}")
                print(f"   OUT: {text[:200]}")
        r[li] = text
        changes += 1

    if changes:
        bak = csvp + '.bak-legal-' + time.strftime('%Y%m%d-%H%M%S')
        shutil.copy2(csvp, bak)
        with open(csvp, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(header); w.writerows(data)
        rows2 = list(csv.reader(open(csvp)))
        cols_ok = all(len(x) == len(header) for x in rows2)
        leak = [x[0] for x in rows2[1:] if 'NO_DESCRIPTION' in x[li]]
        empty_lost = [x[0] for x in zip(rows[1:], rows2[1:]) if x[0][li] and not x[1][li]]
        print(f"WROTE {csvp} | rows={len(rows2)-1} cols_ok={cols_ok} "
              f"leak={leak or 'none'} emptied={empty_lost or 'none'}")
        print(f"backup: {bak}")
        print(f"applied={changes} fixes={used_fixes} kept-raw={kept} flagged={flagged}")
        if flagged:
            print("NOTE: flagged rows received the model text anyway. Hand-clean them into a "
                  "fixes JSON and rerun with --fixes.")
    else:
        print(f"nothing to apply (changes=0, kept-raw={kept}) - CSV unchanged, no backup.")

if __name__ == '__main__':
    main()
