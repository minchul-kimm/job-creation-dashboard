import zipfile
import xml.etree.ElementTree as ET
import re
import datetime

path = r"C:\Claude Work\6. Job Creation Result_26_1st\2026년 6월말 기준 일자리 창출 효과_조사결과 v3.xlsx"
out_path = r"C:\Users\dcamp\AppData\Local\Temp\claude\C--Users-dcamp\14e79e64-13ea-4d98-b2a6-917215d55715\scratchpad\concentration_result.txt"

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
type2 = []
for row in rows[16:]:
    v = get_row_values(row)
    if v.get('A') is None:
        continue
    N = to_num(v.get('N'))
    rec = {
        'name': v.get('I'),
        'status_fam': v.get('B'),
        'status_t2': v.get('G'),
        'N': N,
        'O': to_num(v.get('O')),
    }
    if v.get('B') is not None:
        family.append(rec)
    if v.get('G') is not None:
        type2.append(rec)

def analyze(label, recs):
    lines = []
    n = len(recs)
    total_N = sum(r['N'] for r in recs if r['N'] is not None)
    closed = len([r for r in recs if (r['status_fam'] == '폐업' or r['status_t2'] == '폐업')])
    with_N = [r for r in recs if r['N'] is not None]
    pos = [r for r in with_N if r['N'] > 0]
    zero = [r for r in with_N if r['N'] == 0]
    neg = [r for r in with_N if r['N'] < 0]
    sum_pos = sum(r['N'] for r in pos)

    sorted_desc = sorted(with_N, key=lambda r: r['N'], reverse=True)
    lines.append(f"=== {label} (전체 {n}개사, 폐업 {closed}개사 {closed/n*100:.1f}%) ===")
    lines.append(f"전체 순증감 합계: {total_N:+.0f}명")
    lines.append(f"증가 기업: {len(pos)}개 ({len(pos)/n*100:.1f}%), 증가분 합계 {sum_pos:+.0f}명")
    lines.append(f"유지(변화없음) 기업: {len(zero)}개 ({len(zero)/n*100:.1f}%)")
    lines.append(f"감소 기업: {len(neg)}개 ({len(neg)/n*100:.1f}%), 감소분 합계 {sum(r['N'] for r in neg):+.0f}명")
    lines.append("")
    lines.append("-- 상위 기업 집중도 (증가분 합계 대비) --")
    cum = 0
    for topn in [1,3,5,10,20,30]:
        top = sorted_desc[:topn]
        cum = sum(r['N'] for r in top)
        pct_of_pos = cum/sum_pos*100 if sum_pos else 0
        pct_of_total = cum/total_N*100 if total_N else 0
        lines.append(f"상위 {topn}개사 증가분 합계: {cum:+.0f}명 (전체 증가분의 {pct_of_pos:.1f}%, 전체 순증감의 {pct_of_total:.1f}%)")
    lines.append("")
    lines.append("상위 10개사 명단:")
    for r in sorted_desc[:10]:
        lines.append(f"  {r['name']}: {r['N']:+.0f}명")
    lines.append("")
    return "\n".join(lines)

with open(out_path, 'w', encoding='utf-8') as out:
    out.write(analyze("패밀리사", family))
    out.write("\n\n")
    out.write(analyze("Type2", type2))
    out.write("\n\n")
    out.write(analyze("패밀리사+Type2 전체(중복포함 레코드 기준)", family+type2))
