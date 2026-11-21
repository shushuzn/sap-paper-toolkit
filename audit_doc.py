# -*- coding: utf-8 -*-
"""稿件的结构性合规检查（摘要、关键词、编号、图表引用、缩略语、引文覆盖）。

缩略语表与文献总条数从同目录的 paper_data.py 读取（ABBR、REF_TOTAL）；
未提供时跳过对应检查，不猜默认值。
"""
import importlib.util
import os
import re
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "manuscript.md"
try:
    raw = open(path, encoding="utf-8").read()
except FileNotFoundError:
    sys.exit("找不到源文件：%s\n用法：python audit_doc.py [稿件.md]" % path)
blocks = [b.strip() for b in raw.split("\n") if b.strip()]

i_abs = next(i for i, b in enumerate(blocks) if b.startswith("## 摘要"))
i_kw = next(i for i, b in enumerate(blocks) if b.startswith("关键词"))
i_aben = next(i for i, b in enumerate(blocks) if b.startswith("## Abstract"))
i_kwen = next(i for i, b in enumerate(blocks) if b.startswith("Key words"))
i_body = next(i for i, b in enumerate(blocks) if b.startswith("# 1"))

abs_cn = blocks[i_abs + 1]
kw = blocks[i_kw].split("：", 1)[1]
abs_en = blocks[i_aben + 1]
kwen = blocks[i_kwen].split(":", 1)[1]

print("中文摘要字数(汉字):", len(re.findall(r"[\u4e00-\u9fa5]", abs_cn)))
print("中文关键词个数:", len([x for x in re.split(r"[；;]", kw) if x.strip()]))
print("英文摘要词数:", len(abs_en.split()))
print("英文关键词个数:", len([x for x in kwen.split(";") if x.strip()]))

h1 = [b[2:].strip() for b in blocks if b.startswith("# ")]
h2 = [b[3:].strip() for b in blocks if b.startswith("## ")]
print("一级标题:", len(h1), h1)

body = "\n".join(blocks[i_body:])
for tag in ["表 1", "表 2", "式（1）"]:
    print(f"正文提及 {tag}:", body.count(tag))

cites = set()
for m in re.finditer(r"\[(\d+(?:[,-]\d+)*)\]", body):
    for part in m.group(1).split(","):
        if "-" in part:
            a, b = part.split("-")
            cites.update(range(int(a), int(b) + 1))
        else:
            cites.add(int(part))
print("正文引用出现次数:", len(re.findall(r"\[\d+", body)))

# 可选数据层：缩略语表与文献总条数
abbr, ref_total = [], None
if os.path.exists("paper_data.py"):
    spec = importlib.util.spec_from_file_location("pd", "paper_data.py")
    pd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pd)
    abbr = getattr(pd, "ABBR", [])
    ref_total = getattr(pd, "REF_TOTAL", None)

if ref_total:
    print("正文引用编号覆盖:", len(cites), "缺号:", sorted(set(range(1, ref_total + 1)) - cites))
else:
    print("正文引用编号覆盖:", len(cites), "（paper_data.py 未给 REF_TOTAL，跳过缺号检查）")

if not abbr:
    print("缩略语：paper_data.py 未给 ABBR，跳过首次出现检查")
for a in abbr:
    first = body.find(a)
    if first >= 0:
        ctx = body[max(0, first - 30):first + 5].replace("\n", " ")
        print(f"  {a}: 首次出现 → …{ctx}")
