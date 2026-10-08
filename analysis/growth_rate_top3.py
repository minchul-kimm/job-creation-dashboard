import zipfile
import xml.etree.ElementTree as ET
import re

path = r"C:\Claude Work\6. Job Creation Result_26_1st\2026년 6월말 기준 일자리 창출 효과_조사결과 v3.xlsx"
out_path = r"C:\Claude Work\6. Job Creation Result_26_1st\analysis\growth_rate_top3_result.txt"

z = zipfile.ZipFile(path)
ns = {'a': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
ss_root = ET.fromstring(z.read('xl/sharedStrings.xml'))
shared = []
for si in ss_root.findall('a:si', ns):
    texts = si.findall('.//a:t', ns)
    shared.append(''.join(t.text or '' for t in texts))

def col_letters(cellref):
    m = re.match(r'([A-Z]+)(\d+)', cellref)
    return m.group(1), int(m.group(2))

root = ET.fromstring(z.read('xl/worksheets/sheet2.xml'))
sheetData = root.find('a:sheetData', ns)
rows = sheetData.findall('a:row', ns)

def get_row_values(row):
    vals = {}
    for c in row.findall('a:c', ns):
        ref = c.get('r')
        col, rn = col_letters(ref)
        t = c.get('t')
        v = c.find('a:v', ns)
        val = v.text if v is not None else None
        if t == 's' and val is not None:
            val = shared[int(val)]
        vals[col] = val
    return vals

def to_num(v):
    if v in (None, '', '-', 'N/A'):
        return None
    try:
        return float(v)
    except ValueError:
        return None

family = []
for row in rows[16:]:
    v = get_row_values(row)
    if v.get('A') is None or v.get('B') is None:
        continue
    family.append({
        'name': v.get('I'),
        'P': to_num(v.get('P')),
        'Q': to_num(v.get('Q')),
        'R': to_num(v.get('R')),
        'N': to_num(v.get('N')),
        'O': to_num(v.get('O')),
    })

with open(out_path, 'w', encoding='utf-8') as out:
    # 누적 증가율 = N/P, P>0 required
    cum = [f for f in family if f['P'] not in (None, 0) and f['N'] is not None]
    cum_sorted = sorted(cum, key=lambda f: f['N']/f['P'], reverse=True)
    out.write("=== 패밀리사 누적 증가율 Top 10 (N/P, 과거 고용인원 대비) ===\n")
    for f in cum_sorted[:10]:
        rate = f['N']/f['P']*100
        out.write(f"{f['name']}: 과거 {f['P']:.0f}명 -> 현재 {f['R']:.0f}명 ({f['N']:+.0f}명, {rate:+.1f}%)\n")

    out.write("\n(참고) 과거 고용인원 0명(신규/N/A)이라 비율 계산 제외된 기업 수: ")
    excluded = [f for f in family if f['P'] in (None, 0) and f['N'] is not None and f['N'] > 0]
    out.write(f"{len(excluded)}개\n")
    for f in excluded[:15]:
        out.write(f"  {f['name']}: 과거 {f['P']} -> 현재 {f['R']:.0f}명 ({f['N']:+.0f}명)\n")

    out.write("\n=== 패밀리사 최근 6개월 증가율 Top 10 (O/Q, '25년말 고용인원 대비) ===\n")
    half = [f for f in family if f['Q'] not in (None, 0) and f['O'] is not None]
    half_sorted = sorted(half, key=lambda f: f['O']/f['Q'], reverse=True)
    for f in half_sorted[:10]:
        rate = f['O']/f['Q']*100
        out.write(f"{f['name']}: '25년말 {f['Q']:.0f}명 -> 현재 {f['R']:.0f}명 ({f['O']:+.0f}명, {rate:+.1f}%)\n")

    out.write("\n(참고) '25년말 고용인원 0명(신규)이라 비율 계산 제외된 기업 수: ")
    excluded_h = [f for f in family if f['Q'] in (None, 0) and f['O'] not in (None,) and isinstance(f['O'], float) and f['O'] > 0]
    out.write(f"{len(excluded_h)}개\n")
    for f in excluded_h[:15]:
        out.write(f"  {f['name']}: '25년말 {f['Q']} -> 현재 {f['R']:.0f}명 ({f['O']:+.0f}명)\n")
