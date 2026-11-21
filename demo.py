# -*- coding: utf-8 -*-
"""docx_style 的最小示例：生成含题名、摘要、标题层级、三线表、公式与页码的 docx。

运行后得到 demo.docx，可直接用 audit_manuscript.py 核验。
示例内容一律用占位词，不指代任何具体论文。
"""
from docx import Document
from docx.shared import Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH

from docx_style import (SONG, HEI, KAI, TNR, para, three_line_table,
                        sample_equation, add_header_text, add_page_number_footer)

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
sec.top_margin = sec.bottom_margin = Cm(2.7)
sec.left_margin = sec.right_margin = Cm(2.7)
sec.header_distance = Cm(1.8)
sec.footer_distance = Cm(1.85)
add_header_text(sec)
add_page_number_footer(sec)

# 题名：黑体三号（16 磅）居中
para(doc, "示例题名：排版函数库的用法", HEI, TNR, 16, True,
     WD_ALIGN_PARAGRAPH.CENTER, after=12, line=None)

# 摘要与关键词：楷体五号
para(doc, "摘　要：", HEI, TNR, 10.5, True, before=6, line=None)
para(doc, "这里放摘要正文。函数库只负责排版，内容由调用者提供。", KAI, TNR, 10.5)
para(doc, "关键词：排版；三线表；公式", KAI, TNR, 10.5)

# 一级标题：楷体加粗四号（14 磅）居中
para(doc, "1 引言", KAI, TNR, 14, True,
     WD_ALIGN_PARAGRAPH.CENTER, before=6, after=6, line=None)
para(doc, "正文用宋体五号，上标与下标由 add_rich 自动解析，例如 x^{2} 与 y_{0}。",
     SONG, TNR, 10.5, first_indent=21)

# 三线表：表题在表上方，线型由三线表函数处理
data = [["项目", "方案甲", "方案乙"],
        ["条件", "条件一", "条件二"],
        ["结果", "结果一", "结果二"]]
three_line_table(doc, data, "表 1　示例三线表", [3.2, 5.4, 5.4])

# 公式：编号右对齐，公式体由 sample_equation 组装
sample_equation(doc, "（1）")

doc.save("demo.docx")
print("已生成 demo.docx")
