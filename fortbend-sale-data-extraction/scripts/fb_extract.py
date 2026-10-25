#!/usr/bin/env python3
"""Fort Bend County foreclosure notice pages -> sale fields.
One page = one PDF. Formats A-F; see skill fortbend-sale-data-extraction.
"""
import re, sys, os, subprocess

MONTH_NAMES = ['january','february','march','april','may','june','july','august','september','october','november','december']
MONTHS = {m: i for i, m in enumerate(MONTH_NAMES, 1)}
MONTH_NUM = {v: k for k, v in MONTHS.items()}
MONTH_PREFIX = re.compile(r'(?i)\b(' + '|'.join(m[:4] for m in MONTH_NAMES) + r'oclober?)\b', re.I)

def get_text(pdf):
    return subprocess.run(['pdftotext','-layout',pdf,'-'],capture_output=True,text=True).stdout

# --- light OCR cleanup (conservative, word-boundary only) ---
OCR_FIX = [
    (r'\bwiII+\b', 'will'),
    (r'\bWII+\b', 'WILL'),
    (r'\bw-\.i?s?\.(?=\s|$)', 'was'),
    (r'\bpluce\b', 'place'),
    (r'\b1S\b', 'IS'),
    (r'\bmE\b', 'THE'),
    (r'\bConnty\b', 'County'),
    (r'\btenns\b', 'terms'),
    (r'\bstaled\b', 'stated'), (r'\bstateli\b', 'stated'), (r'\bseated\b', 'stated'),
    (r'\bGlVEN\b', 'Given'),
    (r'\boclober\b', 'October'),
    (r'(?i)richmond\.,', 'Richmond,'),
    (r'\bTIIEREFORE\b', 'THEREFORE'),
    (r'\bslide\s+no\.?', 'plat no.'),
    (r'\bco[^.,;]{0,14}clerk\b.{0,80}?(?:\s|,|;)+(?:tfxm|tfm|txm)\b,?\s*', ' ')
]
def clean(s):
    if not s: return s
    s = re.sub(r'\s+', ' ', s).strip()
    for pat, rep in OCR_FIX:
        s = re.sub(pat, rep, s, flags=re.I)
    return s

# ---------- DATE ----------
MONTH_TOKEN = r'(?:' + '|'.join(['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'] + ['oclo','octe']) + r')[a-z]*'
def parse_date(v):
    if not v: return None
    v = re.sub(r'\s+', ' ', v).strip()
    v = re.sub(r'(?i)\boclober', 'october', v)
    # slash form: 10/06/2026, 10/6/2026, OCR mangles 10/612026, 10/06n026
    m = re.search(r'(\d{1,2})\s?[/n1l]\s?(\d{1,2})\s?[/n1l]\s?(20\d{2})', v)
    if m:
        a, b, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= a <= 12 and 1 <= b <= 31: return f"{a:02d}/{b:02d}/{yy}"
    # 'Tuesday, the 6th day of October, 2026'
    m2 = re.search(r'the\s+(\d{1,2})(?:st|nd|rd|th)?\s+day\s+of\s+([a-z]+)\s*,?\s*(20\d{2})', v, re.I)
    if m2:
        name = m2.group(2).lower()
        for mn, n in MONTHS.items():
            if name.startswith(mn[:4]):
                if 1 <= int(m2.group(1)) <= 31:
                    return f"{n:02d}/{int(m2.group(1)):02d}/{m2.group(3)}"
        return None
    # 'October 6, 2026' / 'Oclober6, 2026' / 'October 2026' (no day)
    m = re.search(r'([a-z]+)\.?\s*(\d{1,2}(?:st|nd|rd|th)?)?\s*,?\s*(20\d{2})', v, re.I)
    if m:
        name = m.group(1).lower()
        for mn, n in MONTHS.items():
            if name.startswith(mn[:4]):
                day = re.sub(r'(?:st|nd|rd|th)$', '', m.group(2) or '')
                if day and 1 <= int(day) <= 31:
                    return f"{n:02d}/{int(day):02d}/{m.group(3)}"
    return None

def find_date(t, lines):
    cands = []  # (score, date)
    for i, l in enumerate(lines):
        m = re.match(r'^\s*((?:[a-z]{0,2}da?te|ba?te) of sale|date,? time,? and place of sale|to be sold|date)\s*[:.]?\s*(.*)$', l, re.I)
        if m:
            label = m.group(1).lower()
            v = re.sub(r'\s+', ' ', m.group(2)).strip()
            v = re.split(r'(?i)earliest', v)[0].strip(' \t.,~;:|-')
            if not v:
                for nl in lines[i+1:i+4]:
                    if nl.strip(): v = nl.strip(); break
            d = parse_date(v)
            if not d: continue
            if label.startswith('date of sale') or label.startswith('date, time') or label.startswith('to be sold'):
                cands.append((5, d))
            else:
                ctx = t[t.find(l):t.find(l)+400]
                score = 4 if re.search(r'(?i)\btime\b', ctx) else 1
                cands.append((score, d))
            if re.match(r'(?i)date of sale', label):
                break
    # narrative: on <date> ... sale/sell within 250 chars
    DATE_NARR = re.compile(r'on\s+(?:[a-z]{3,9}\s*,\s*)?(?:(?P<a>\d{1,2}\s?[/n1l]\s?\d{1,2}\s?[/n1l]\s?20\d{2})|(?P<b>[a-z]+\.?\s*\d{1,2}\s*,?\s*20\d{2}))', re.I)
    for m in DATE_NARR.finditer(t):
        val = m.group('a') or m.group('b')
        win = t[m.end():m.end()+250]
        if re.search(r'(?i)\b(sale|sell|sold)\b', win):
            d = parse_date(val)
            if d: cands.append((4, d))
    cands = [(s, d) for s, d in cands if int(d.rsplit('/', 1)[1]) >= 2025]
    if not cands: return None
    cands.sort(key=lambda x: -x[0])
    return cands[0][1]

# ---------- TIME ----------
def find_time(t):
    cands = []
    for m in re.finditer(r'(?i)earliests?\s+time\s+(?:sale\s+w\w*\s+)?(?:b[\w]{1,5})\s*[:.]?\s+(\d{1,2})[:.](\d{2})\s*(a\.?m\.?|p\.?m\.?)?', t):
        cands.append((m.group(1), m.group(2), (m.group(3) or '').replace('.', '').upper()))
    for m in re.finditer(r'(?i)earliest\s+time\s+the\s+sale\s+w\w*\s+begin\s+is\s+(\d{1,2})[:.](\d{2})\s*(a\.?m\.?|p\.?m\.?)?', t):
        cands.append((m.group(1), m.group(2), (m.group(3) or '').replace('.', '').upper()))
    for m in re.finditer(r'(?i)no\s+earlier\s+than\s+(\d{1,2})[:.](\d{2})\s*(a\.?m\.?|p\.?m\.?)?', t):
        cands.append((m.group(1), m.group(2), (m.group(3) or '').replace('.', '').upper()))
    for m in re.finditer(r'(?im)^\s*(\S+)\s+of\s+sale\s*[:.]?\s*(\d{1,2})\s*[:.\s]\s*(\d{2})\s*(a\.?m\.?|p\.?m\.?)?', t):
        lb = (m.group(1) or '').lower().strip('.!1')
        if lb not in ('date', 'saledate'):
            cands.append((m.group(2), m.group(3), (m.group(4) or '').replace('.', '').upper()))
    for m in re.finditer(r'(?i)sale\s+(?:w\w*|u\s*ill|wi\w*)\s+begin\s+(?:at\s+)?([0-9Il])\s*([0-9Il]?\.?\s*)?[:.\s]\s*(\d{2})\s*(a\.?m\.?|p\.?m\.?)?', t):
        hh = (m.group(1) + (m.group(2) or '').strip()).replace('I','1').replace('l','1')
        cands.append((hh, m.group(3), (m.group(4) or '').replace('.', '').upper()))
    for m in re.finditer(r'(?im)^\s*time\s*[:.]?\s*(\d{1,2})\s*[:.\s\s]*?[:.]?\s*(\d{2})\s*(a\.?m\.?|p\.?m\.?)?', t):
        cands.append((m.group(1), m.group(2), (m.group(3) or '').replace('.', '').upper()))
    WORDHRS = {'one':'1','two':'2','three':'3','four':'4','five':'5','six':'6','seven':'7','eight':'8','nine':'9','ten':'10','eleven':'11','twelve':'12'}
    for m in re.finditer(r'(?i)between\s+(?:the\s+hours\s+of\s+)?([a-z]{3,7}|\d{1,2})\s+o[\x27.]?clock\s+(a\.?m\.?|p\.?m\.?)', t):
        hh = WORDHRS.get(m.group(1).lower(), m.group(1))
        cands.append((hh, '00', (m.group(2) or '').replace('.', '').upper()))
    for m in re.finditer(r'(?i)\bat\s+(\d{1,2})[:.](\d{2})\s*(a\.?m\.?|p\.?m\.?)\b', t):
        cands.append((m.group(1), m.group(2), (m.group(3) or '').replace('.', '').upper()))
    for m in re.finditer(r'(?i)between\s+the\s+hours\s+of\s+(\d{1,2})[:.](\d{2})\s*(a\.?m\.?|p\.?m\.?)', t):
        cands.append((m.group(1), m.group(2), (m.group(3) or '').replace('.', '').upper()))
    if not cands: return None
    hh, mm, ap = cands[0]
    hh = re.sub(r'[^0-9]', '', hh) or '1'
    ap = ap or 'PM'
    return f"{int(hh)}:{mm} {ap}"

# ---------- PLACE ----------
PLACE_STOP = re.compile(r'(?i)^(?:\d+\.\s+[a-z]|\d+[a-z]\.\s+[a-z]|terms of sale|default\s|notice is further|notices?\s+of|commonly\s+known|date of sale|earliest|sale information|substitute|trustee\s+(address|number)|filed\s+for)')
TERM = re.compile(r"(?i)commissioner'?\s?s?\s+court|posted")

def find_addr(t, lines):
    pats = [
        r'(?im)^\s*(?:and\s+more\s+|more\s+)?commonly\s+known\s+as\s*[:.]?\s*([^\n]{4,120})',
        r'(?i)(?:and\s+)?more\s+commonly\s+known\s+as\s*[:.]?\s*([^\n.;]{4,120})',
        r'(?im)^\s*property\s+address\s*[:.]?\s*([^\n]{4,120})',
        r'(?i)property\s+address\s*[:.]?\s*([^\n]{4,120})',
        r'(?i)commonly\s+known\s+as\s*[:.]?\s*([^\n;]{4,120})',
    ]
    for idx, p in enumerate(pats):
        m = re.search(p, t)
        if m:
            v = clean(m.group(1))
            if v and not re.match(r'(?i)lot\s', v):
                v = re.split(r'\s{2,}', v)[0].strip(' \t.,;:|-')
                if v:
                    if idx >= 2 and lines:
                        nxt = m.group(0)
                        after = t[m.end():]
                        nl = after.split('\n')
                        for cand in nl[0:3]:
                            cs = cand.strip()
                            if re.match(r"^[A-Za-z][A-Za-z .]+,\s*[A-Za-z]+,\s*[\x27\"]?\d{4,5}$", cs):
                                v = v + ", " + clean(cs)
                                break
                    return v
    # fallback: unlabelled property address (street number + name) in the top of the page
    street_re = re.compile(r'^\d{1,6}[-\s]?[A-Za-z][A-Za-z0-9 .\x27\-]{2,45}$')
    suffix = re.compile(r'\b(St|Street|Ave|Avenue|Blvd|Boulevard|Dr|Drive|Ln|Lane|Rd|Road|Ct|Court|Cir|Circle|Way|Cyn|Canyon|Trl|Trail|Hwy|Pike|Pkwy|Parkway|Plaza|Pl|Place|Ter|Terrace|Ridge|Bend|Run|Cove|Creek|Brook|Grove|Hollow|Knoll|Loop|Meadow|Mill|Pine|Prairie|Shore|Springs|Stone|Walk|Woods|Heights|Hills|Point|Park|Landing|Center|Centre|Crossing|Crescent|Garden|Gulf|Isle|Junction|Lake|Light|Orchard|Palms|Pass|Riverside|Row|Summit|Terrace|Vista|Wells|Woodway|Corners|Square|Squares|Station|Village|Belt|Expressway|Freeway|West|East|North|South|Spring)\b\.?', re.I)
    half = len(lines)//2 + 12
    for i, l in enumerate(lines[:half]):
        s = l.strip()
        s = re.split(r'\s+\d{5,}', s)[0].rstrip(' \t-')
        if street_re.match(s) and suffix.search(s):
            v = s
            for k in range(i+1, min(i+3, len(lines))):
                cs = lines[k].strip()
                if re.search(r'\bTX\s*\d{5}', cs, re.I):
                    v = v + ' ' + cs
                    break
            return clean(v)
    return None
def find_place(t, lines):
    # locate start anchor
    for i, l in enumerate(lines):
        m = re.match(r'^\s*(?:location|place)\s+of\s+sale\s*[:]\s*(.*)$', l, re.I)
        if m:
            return _place_collect(lines, i, m.group(1))
    for i, l in enumerate(lines):
        m = re.match(r'^\s*place\s*[:]\s*(.*)$', l, re.I)
        if m:
            return _place_collect(lines, i, m.group(1))
    m = re.search(r'(?i)the\s+sale\s+w\w*\s+take\s+place\s+at', t)
    if m:
        return _place_collect_off(t, lines, m.start())
    m = re.search(r'(?i)(?:the\s+)?(?:foreclosure|trustee.?s)?\s?sale\s+w\w*\s+be\s+conducted', t)
    if m:
        return _place_collect_off(t, lines, m.start())
    return None

def _place_collect(lines, i, firstchunk):
    out = [firstchunk.strip()] if firstchunk and firstchunk.strip() else []
    j = i + 1
    while j < len(lines) and len(out) < 10:
        s = lines[j].strip()
        if not s:
            if out: break
            j += 1; continue
        if PLACE_STOP.match(s): break
        out.append(s)
        j += 1
    return _trim_place(' '.join(out)) if out else None

def _place_collect_off(t, lines, start):
    before = t[:start]
    i = before.count('\n')
    off = start - before.rfind('\n') - 1
    first = lines[i]
    firstpart = first[off:] if off > 0 else first
    out = [firstpart.strip()] if firstpart.strip() else []
    j = i + 1
    while j < len(lines) and len(out) < 12:
        s = lines[j].strip()
        if not s:
            if out: break
            j += 1; continue
        if PLACE_STOP.match(s): break
        out.append(s)
        j += 1
    v = ' '.join(out) if out else None
    if not v: return None
    v = re.sub(r'(?i)^now,?\s*therefore,?[^,]*,\s*(that\s+)?on\s+\S+\s*,?\s*', '', v)
    return _trim_place(v)

def _trim_place(v):
    if not v: return None
    # find terminal candidates; prefer the latest whose next char is not a comma
    best = None
    for m in TERM.finditer(v):
        nxt = v[m.end():m.end()+1]
        if nxt == ',' : continue
        best = m
    if best is None:
        return clean(v)
    end = best.end()
    if v[end:end+1] == '.':
        end += 1
    return clean(v[:end])

# ---------- LEGAL ----------
LEGAL_LABEL = re.compile(r'(?i)^\s*(?:(?:subject real property\s*\()?)?\s*(?:.*?)(?P<lb>legal description|property\s+to\s+be\s+sold)\s*[:.)]*\s*(?P<rest>.*)$')
LEGAL_STOP = re.compile(r'(?i)^\s*(?:commonly|known\s+as|whereas|now\s*[,;]|notices?\s+(is|hereof|further)|date\s+of\s+sale|earliest|location\s+of\s+sale|terms\s+of\s+sale|a\s+default|the\s+sale\s+w|sale\s+w\w*\s+be\s+conducted|instruments?\s+being|default\s+has|now\s*,\s*therefore|\d+\.\s+[a-z]|property\s+(county|address)|time\s+of\s+sale|place\s+of\s+sale|substitute)')
LEGAL_GOOD = re.compile(r'(?i)[fp]ort\s*bend\s*county', re.I)

LEGAL_JUNK = re.compile(r'(?i)^(count(y|v)\s+clerk|tx|tfx|tfm|\S+\s+count(y|v)\s+\S*\s*$)', re.I)
LEGAL_STOP2 = re.compile(r'(?i)^(terms of sale|terms of (?:the\s+)?sale|notice of sale|notice of default|whereas|servicing agreement|the mortgage servicer|pursuant to the servicing|freedom clearing|morlgagee|noteholder|property county|instrument to be|instruments? (being|to be|number)|current (beneficiary|loan)|servicer|substituted trustee)', re.I)

def _collect(lines, i, initial):
    out = []
    if initial: out.append(initial)
    j = i + 1
    blanks = 0
    while j < len(lines) and len(out) < 8:
        s = lines[j].strip()
        if not s:
            blanks += 1
            if out and blanks >= 2: break
            j += 1; continue
        blanks = 0
        if LEGAL_STOP.match(s) or LEGAL_STOP2.match(s): break
        if LEGAL_JUNK.match(s):
            if out: break
            j += 1; continue
        out.append(s)
        j += 1
    v = clean(' '.join(out))
    v = re.sub(r'^[):.\s\-]+', '', v)
    if len(v) > 40 and LEGAL_GOOD.search(v):
        return v
    return None

def find_legal(t, lines):
    # 1) explicit Legal Description / Property To Be Sold / SUBJECT ... label
    for i, l in enumerate(lines):
        m = LEGAL_LABEL.match(l)
        if m:
            v = _collect(lines, i, m.group('rest').strip())
            if v: return v
    # 2) "described as (fol?ows|below)" narrative
    for i, l in enumerate(lines):
        m = re.search(r'(?i)describ\w*\s+as\s+(?:fol\w*|below)[:.]?', l)
        if m:
            rest = l[m.end():].strip(' \t.,:-;')
            v = _collect(lines, i, rest)
            if v: return v
    # 3) bare "Property:" label
    for i, l in enumerate(lines):
        m = re.match(r'^\s*property\s*[:.]\s*(.*)$', l, re.I)
        if m and not re.match(r'(?i)^\s*property\s+(county|address)', l):
            v = _collect(lines, i, m.group(1).strip())
            if v: return v
    # 4) to-wit narrative
    for i, l in enumerate(lines):
        if re.search(r'(?i)\bto[- ]wit\b', l):
            v = _collect(lines, i, None)
            if v: return v
    return None


def extract(pdf):
    t = get_text(pdf)
    lines = t.splitlines()
    return {
        'date_of_sale': find_date(t, lines),
        'earliest_time': find_time(t),
        'place_of_sale': find_place(t, lines),
        'legal_description': find_legal(t, lines),
        'property_address': find_addr(t, lines),
    }

if __name__ == '__main__':
    d = '/home/ttran/foreclose_file_fortbend/2026/October'
    for n in sys.argv[1:]:
        if '.' in n or '/' in n: continue
        p = os.path.join(d, f'October_2026_{n}.pdf')
        r = extract(p)
        print(f'===== {n} =====')
        for k, v in r.items():
            print(f'  {k}: {v!r}')
        print()
