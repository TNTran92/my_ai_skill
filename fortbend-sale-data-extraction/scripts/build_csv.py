#!/usr/bin/env python3
"""Build/update property_data.csv from single-page foreclosure notice PDFs.

Usage: python3 build_csv.py <folder_with_pdfs>

- Keeps only pages that look like sale notices (date + time/place, or legal desc).
- Date Added / Time Added = wall-clock entry time; existing rows rebuild their
  original values (read back from the current property_data.csv).
- Prints per-column fill stats for verification.
"""
import sys, os, csv, time, importlib.util

HDR = ['File Name', 'Date of Sale', 'Earliest Time Sale Will Begin', 'Place of Sale of Property',
       'Legal Description', 'Date Added', 'Time Added', 'Property Address']

def load_extract():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, 'fb_extract.py')
    spec = importlib.util.spec_from_file_location('fb_extract', path)
    fb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fb)
    return fb

def is_notice(r):
    return bool((r['date_of_sale'] and (r['earliest_time'] or r['place_of_sale'])) or r['legal_description'])

def main():
    if len(sys.argv) < 2:
        sys.exit('usage: build_csv.py <folder_with_pdfs>')
    d = sys.argv[1].rstrip('/')
    if not os.path.isdir(d):
        sys.exit(f'not a directory: {d}')
    csv_path = os.path.join(d, 'property_data.csv')
    existing = {}
    if os.path.exists(csv_path):
        with open(csv_path) as fh:
            for row in csv.DictReader(fh):
                existing[row['File Name']] = (row['Date Added'], row['Time Added'])
    now = time.strftime('%Y-%m-%d %H:%M')
    date_added, time_added = now.split(' ')
    fb = load_extract()
    files = sorted(f for f in os.listdir(d) if f.lower().endswith('.pdf'))
    rows, errors = [], []
    for f in files:
        fn = f[:-4]
        try:
            r = fb.extract(os.path.join(d, f))
            if not is_notice(r):
                continue
            da, ta = existing.get(fn, (date_added, time_added))
            rows.append([fn, r['date_of_sale'] or '', r['earliest_time'] or '',
                         r['place_of_sale'] or '', r['legal_description'] or '',
                         da, ta, r['property_address'] or ''])
        except Exception as e:
            errors.append((fn, str(e)[:120]))
    with open(csv_path, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(HDR)
        w.writerows(rows)
    # verify
    back = list(csv.reader(open(csv_path)))
    names = [r[0] for r in back[1:]]
    print(f'{len(files)} PDFs scanned -> {len(rows)} notice rows -> {csv_path}')
    print(f'verify: on-disk {len(back)} lines | header exact {back[0] == HDR} | file names unique {len(set(names)) == len(names)}')
    for i, h in enumerate(HDR[1:], 1):
        if h in ('Date Added', 'Time Added'):
            continue
        blanks = sum(1 for r in back[1:] if not r[i])
        print(f'  {h:32s} {len(rows) - blanks}/{len(rows)} filled')
    print('  all 5 data fields filled: ', sum(1 for r in back[1:] if all(r[1:5]) and r[7]))
    if errors:
        print('ERRORS:')
        for fn, msg in errors:
            print(f'  {fn}: {msg}')

if __name__ == '__main__':
    main()
