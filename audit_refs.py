# -*- coding: utf-8 -*-
"""按顺序编码制审计参考文献格式：类型标识、作者段、卷期页、标点与结尾。"""
import re, json, importlib.util, sys

try:
    spec = importlib.util.spec_from_file_location("pd", "paper_data.py")
    pd = importlib.util.module_from_spec(spec); spec.loader.exec_module(pd)
except FileNotFoundError:
    sys.exit("找不到 paper_data.py：先执行 cp paper_data.example.py paper_data.py 并填入文献表")
REFS = pd.REFS

TYPE_MARK = re.compile(r"\[(J|M|S|D|C|N|R|P|Z)\]")
YEAR_VOL = re.compile(r",\s*(\d{4}),\s*([\dA-Za-z]+)\s*(?:\((\d+(?:-\d+)?)\))?\s*:\s*([\d\-]+)")
YEAR_ONLY = re.compile(r",\s*(\d{4})")
DOI = re.compile(r"DOI:/s*10/./S+")

def audit(key, s):
    issues, warns = [], []
    m = TYPE_MARK.search(s)
    if not m:
        issues.append("缺文献类型标识（[J]/[M]/[S]）")
    typ = m.group(1) if m else None

    # 作者段
    head = s.split(". ")[0]
    if "et al" in head:
        n = len([x for x in head.split("et al")[0].split(",") if x.strip()])
        if n != 3:
            warns.append(f"et al. 前应恰为 3 位作者，实为 {n}")
    if "等" in head:
        warns.append("中文文献用“等”，英文文献应用“et al.”")

    # 中文标点误用
    if typ in ("J", "M") and re.search(r"[\u4e00-\u9fa5]", s) is None:
        if "，" in s or "（" in s:
            issues.append("英文条目中出现中文全角标点")
    # 结尾
    if not s.endswith("."):
        issues.append("条目未以英文句点结尾")

    if typ == "J":
        if not YEAR_VOL.search(s):
            if DOI.search(s):
                warns.append("缺卷(期):页码，以 DOI 替代（著录规则允许，但期刊条目宜补全）")
            else:
                issues.append("缺“年, 卷(期): 起止页”")
        if not re.search(r"\[J\]\.\s*\S", s):
            issues.append("[J] 后缺刊名")

    if typ == "S":
        num = r"[A-Z]{2,4}(?:/[A-Z]{1,2})?\s*\d{2,5}"
        if re.search(num + r"\s*[—–]\s*\d{2,4}", s):
            issues.append("编号中的年份连接应使用半字线「-」，非破折号")
        elif not re.search(num + r"\s*-\s*\d{2,4}", s):
            issues.append("规范类条目缺「代号 + 序号 + 半字线 + 发布年」")
    return issues, warns

rows = []
for k, v in REFS.items():
    iss, wr = audit(k, v)
    st = "FAIL" if iss else ("WARN" if wr else "PASS")
    rows.append({"key": k, "status": st, "issues": iss, "warns": wr, "text": v})

for r in rows:
    print(f"[{r['status']:4}] {r['key']:14} {'; '.join(r['issues']+r['warns']) or 'OK'}")
print("\n合计:", len(rows), "FAIL:", sum(r['status']=='FAIL' for r in rows), "WARN:", sum(r['status']=='WARN' for r in rows))
json.dump(rows, open("audit_refs.json","w"), ensure_ascii=False, indent=1)
