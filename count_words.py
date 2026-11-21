# -*- coding: utf-8 -*-
"""用 Word 统计正文（引言→结论）的字数：只读，不改文档。"""
import os, sys, glob
import win32com.client as win32

doc_path = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                           [p for p in glob.glob("*.docx") if not p.startswith("~$")][0])
word = win32.genclient.DispatchEx("Word.Application")
word.Visible = False
word.DisplayAlerts = 0
doc = word.Documents.Open(doc_path, ReadOnly=True)

# 定位正文起止段
start = end = None
for i, p in enumerate(doc.Paragraphs, 1):
    t = p.Range.Text.strip()
    if start is None and t.startswith("1") and "引言" in t:
        start = i
    if start and t.startswith("参考文献"):
        end = i - 1
        break

rng = doc.Range(doc.Paragraphs(start).Range.Start, doc.Paragraphs(end).Range.End)
print("正文起止段:", start, "→", end)
print("正文 字数(Words):", rng.ComputeStatistics(0))
print("正文 字符数(不计空格):", rng.ComputeStatistics(3))
print("正文 字符数(计空格):", rng.ComputeStatistics(5))
print("全文 字符数(不计空格):", doc.ComputeStatistics(3))
print("页数:", doc.ComputeStatistics(2))
doc.Close(False)
word.Quit()
