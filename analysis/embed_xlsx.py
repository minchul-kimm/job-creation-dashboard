import base64

xlsx_path = r"C:\Claude Work\6. Job Creation Result_26_1st\2026년 6월말 기준 일자리 창출 효과_조사결과 v3.xlsx"
html_path = r"C:\Claude Work\6. Job Creation Result_26_1st\index.html"

with open(xlsx_path, 'rb') as f:
    b64 = base64.b64encode(f.read()).decode('ascii')

with open(html_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

target_prefix = 'const XLSX_B64='
found = False
for i, line in enumerate(lines):
    if line.startswith(target_prefix):
        lines[i] = f'{target_prefix}"{b64}";\n'
        found = True
        print(f"replaced line {i+1}, old length vs new b64 length={len(b64)}")
        break

if not found:
    raise SystemExit("XLSX_B64 line not found!")

with open(html_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("done")
