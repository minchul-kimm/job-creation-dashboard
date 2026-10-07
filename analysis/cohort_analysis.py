import zipfile
import xml.etree.ElementTree as ET
import re
import datetime

path = r"C:\Claude Work\6. Job Creation Result_26_1st\2026년 6월말 기준 일자리 창출 효과_조사결과 v3.xlsx"
out_path = r"C:\Users\dcamp\AppData\Local\Temp\claude\C--Users-dcamp\14e79e64-13ea-4d98-b2a6-917215d55715\scratchpad\cohort_result.txt"

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

def excel_date(serial):
    if serial is None or serial == '' or serial == '-':
        return None
    try:
        s = float(serial)
    except ValueError:
        return None
    epoch = datetime.date(1899, 12, 30)
    return epoch + datetime.timedelta(days=int(s))

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
    if v.get('A') is None:
        continue
    B = v.get('B')
    if B is None:
        continue
    dates = [excel_date(v.get(c)) for c in ['C','D','E','F']]
    dates = [d for d in dates if d is not None]
    entry = min(dates) if dates else None
    family.append({
        'name': v.get('I'),
        'status': B,
        'entry': entry,
        'P': to_num(v.get('P')),
        'Q': to_num(v.get('Q')),
        'R': to_num(v.get('R')),
        'N': to_num(v.get('N')),
        'O': to_num(v.get('O')),
        'is_type2_too': v.get('G') is not None,
        'deactive_reason': v.get('X'),
    })

def cohort_of(entry):
    if entry is None:
        return '미상'
    y = entry.year
    if 2013 <= y <= 2017:
        return '초기(2013-2017)'
    elif 2018 <= y <= 2022:
        return '중기(2018-2022)'
    elif 2023 <= y <= 2026:
        return '최근(2023-2026)'
    else:
        return f'기타({y})'

from collections import defaultdict
cohorts = defaultdict(list)
for f in family:
    cohorts[cohort_of(f['entry'])].append(f)

with open(out_path, 'w', encoding='utf-8') as out:
    out.write(f"총 패밀리사 레코드: {len(family)}\n\n")

    for key in ['초기(2013-2017)', '중기(2018-2022)', '최근(2023-2026)']:
        recs = cohorts.get(key, [])
        n = len(recs)
        sumP = sum(r['P'] for r in recs if r['P'] is not None)
        sumR = sum(r['R'] for r in recs if r['R'] is not None)
        sumN = sum(r['N'] for r in recs if r['N'] is not None)
        sumO = sum(r['O'] for r in recs if r['O'] is not None and r['O'] != None)
        n_with_both_PR = len([r for r in recs if r['P'] is not None and r['R'] is not None])
        avg_per_company = sumN / n if n else 0
        growth_pct = (sumN / sumP * 100) if sumP else 0
        inc = len([r for r in recs if r['N'] is not None and r['N'] > 0])
        flat = len([r for r in recs if r['N'] is not None and r['N'] == 0])
        dec = len([r for r in recs if r['N'] is not None and r['N'] < 0])
        avg_entry_emp = (sumP / n_with_both_PR) if n_with_both_PR else 0

        # half-year (O) stats, excluding N/A
        o_vals = [r['O'] for r in recs if r['O'] is not None]
        sumO_valid = sum(o_vals)
        inc_half = len([x for x in o_vals if x > 0])
        flat_half = len([x for x in o_vals if x == 0])
        dec_half = len([x for x in o_vals if x < 0])

        out.write(f"=== {key} ===\n")
        out.write(f"기업 수: {n}개사\n")
        out.write(f"과거(편입시) 고용인원 합계: {sumP:.0f}명 (평균 {avg_entry_emp:.1f}명/개사)\n")
        out.write(f"현재 고용인원 합계: {sumR:.0f}명\n")
        out.write(f"누적 증감: {sumN:+.0f}명 (기업당 평균 {avg_per_company:+.2f}명, 증가율 {growth_pct:+.1f}%)\n")
        out.write(f"누적 기준 증가/유지/감소 기업 수: {inc}개/{flat}개/{dec}개 (비중 {inc/n*100:.0f}%/{flat/n*100:.0f}%/{dec/n*100:.0f}%)\n")
        out.write(f"최근 반기 증감 합계(유효 {len(o_vals)}개사): {sumO_valid:+.0f}명\n")
        out.write(f"반기 기준 증가/유지/감소 기업 수: {inc_half}개/{flat_half}개/{dec_half}개\n")
        # top movers
        sorted_recs = sorted([r for r in recs if r['N'] is not None], key=lambda r: r['N'], reverse=True)
        out.write("Top3 증가: " + ", ".join(f"{r['name']}(+{r['N']:.0f})" for r in sorted_recs[:3]) + "\n")
        sorted_recs_dec = sorted([r for r in recs if r['N'] is not None], key=lambda r: r['N'])
        out.write("Top3 감소: " + ", ".join(f"{r['name']}({r['N']:.0f})" for r in sorted_recs_dec[:3]) + "\n")
        out.write("\n")

    # unmatched
    misc = cohorts.get('미상', [])
    out.write(f"입주연도 미상: {len(misc)}개사\n")
    for r in misc[:10]:
        out.write(f"  {r['name']} status={r['status']}\n")

# status breakdown by cohort
with open(out_path, 'a', encoding='utf-8') as out:
    out.write("\n=== 상태(status) 분포 ===\n")
    for key in ['초기(2013-2017)', '중기(2018-2022)', '최근(2023-2026)']:
        recs = cohorts.get(key, [])
        n = len(recs)
        active = len([r for r in recs if '폐업' not in (r['status'] or '')])
        closed = len([r for r in recs if r['status'] == '폐업'])
        out.write(f"{key}: 전체{n} / 폐업표기{closed}개 ({closed/n*100:.0f}%)\n")
