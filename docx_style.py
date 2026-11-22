# -*- coding: utf-8 -*-
"""python-docx 的中文科技论文排版函数库。

提供字体组合、富文本解析（上下标、斜体希腊字母）、三线表、OMML 公式、页脚页码。
不含论文数据与具体题名，只提供可调用的函数。
"""
import re
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import OxmlElement, parse_xml

SONG, HEI, TNR = "宋体", "黑体", "Times New Roman"
KAI = "楷体"

# ---------------- 基础排版工具 ----------------
def set_run(run, cn=SONG, en=TNR, size=12, bold=False):
    run.font.name = en
    run.font.size = Pt(size)
    run.bold = bold
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts"); rPr.append(rFonts)
    rFonts.set(qn("w:ascii"), en)
    rFonts.set(qn("w:hAnsi"), en)
    rFonts.set(qn("w:eastAsia"), cn)


GREEK = "νχφμσαβγδεθλρτωςΣΔΩ"
# 底数 + 一个或多个上下标组。φ_{p}^{2} 是同一底数先下标后上标的连写，
# 若只匹配单个后缀，第一个后缀之后剩下的 ^{2} 会以字面量留在成稿里。
AFFIX = re.compile(r"([A-Za-z0-9%s)])((?:[_^]\{[^}]*\})+)"
                   % GREEK)
PAIR = re.compile(r"([_^])\{([^}]*)\}")


def add_rich(p, text, cn=SONG, en=TNR, size=12, bold=False):
    """支持 V_{u}、q^{5/3}、φ_{p}^{2} 形式的上下标，同一底数可连写多个后缀。"""
    pos = 0
    for m in AFFIX.finditer(text):
        if m.start() > pos:
            set_run(p.add_run(text[pos:m.start()]), cn, en, size, bold)
        set_run(p.add_run(m.group(1)), cn, en, size, bold)
        for kind, body in PAIR.findall(m.group(2)):
            r = p.add_run(body)
            set_run(r, cn, en, size, bold)
            if kind == "_":
                r.font.subscript = True
            else:
                r.font.superscript = True
        pos = m.end()
    if pos < len(text):
        set_run(p.add_run(text[pos:]), cn, en, size, bold)


def para(doc, text="", cn=SONG, en=TNR, size=12, bold=False, align=None,
         first_indent=None, before=0, after=0, line=1.5, keep=False):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(before); pf.space_after = Pt(after)
    if line:
        pf.line_spacing = line
    if align is not None:
        p.alignment = align
    if first_indent:
        pf.first_line_indent = Pt(first_indent)
    if keep:
        pf.keep_with_next = True
    if text:
        add_rich(p, text, cn, en, size, bold)
    return p


def add_header_text(section):
    """页眉留空。

    格式文件若要求"格式参照某文体"，参照的是排版参数（纸张、页边距、
    行距、字号、标题层级、表格线型），不含该文体的身份标识。把该文体的
    名称写进本文页眉，等于让读者误认稿件类型，属冒用文体，故不写入任何
    页眉文字。若日后确需按该文体模板成稿，再另行启用。
    """
    return


def add_page_number_footer(section):
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    f1 = OxmlElement("w:fldChar"); f1.set(qn("w:fldCharType"), "begin")
    ins = OxmlElement("w:instrText"); ins.set(qn("xml:space"), "preserve"); ins.text = " PAGE "
    f2 = OxmlElement("w:fldChar"); f2.set(qn("w:fldCharType"), "end")
    run._r.append(f1); run._r.append(ins); run._r.append(f2)
    set_run(run, SONG, TNR, 9)


# ---------------- 公式（OMML） ----------------
MATH_RPR = ('<w:rPr><w:rFonts w:ascii="Cambria Math" w:hAnsi="Cambria Math"/>'
             '<w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>')


def _mr(t):
    return '<m:r>%s<m:t xml:space="preserve">%s</m:t></m:r>' % (MATH_RPR, t)

def _msup(b, s):
    return '<m:sSup><m:e>%s</m:e><m:sup>%s</m:sup></m:sSup>' % (b, s)

def _msub(b, s):
    return '<m:sSub><m:e>%s</m:e><m:sub>%s</m:sub></m:sSub>' % (b, s)

def _mdel(inner):
    return ('<m:d><m:dPr><m:begChr m:val="("/><m:endChr m:val=")"/></m:dPr>'
            '<m:e>%s</m:e></m:d>' % inner)


def _mfrac(n, d):
    return ('<m:f><m:fPr><m:type m:val="bar"/></m:fPr><m:num>%s</m:num>'
            '<m:den>%s</m:den></m:f>' % (n, d))


def add_omml(doc, body, number="", size=12):
    """把一段 OMML 表达式追加为独立公式段落，编号显示在右侧。"""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.5
    p._p.append(parse_xml('<m:oMath %s>%s</m:oMath>' % (nsdecls("m", "w"), body)))
    if number:
        set_run(p.add_run("　　" + number), SONG, TNR, size)
    return p


def sample_equation(doc, number="（1）"):
    """OMML 公式的组装示例：分式、上标、下标、括号各用一次。

    换其他公式时，照此用 _mr（正体）、_msup（上标）、_msub（下标）、
    _mfrac（分式）、_mdel（括号）组合出 body，再交给 add_omml。
    """
    ratio = _mfrac(_mr("a") + _mr(" + ") + _mr("b"), _mr("c"))
    bracket = _mdel(ratio + _mr(" + ") + _msub(_mr("k"), _mr("0")))
    body = _msup(_mr("y"), _mr("2")) + _mr(" ≈ ") + bracket
    return add_omml(doc, body, number)


# ---------------- 表格 ----------------
def _border(cell, edge, sz="8"):
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = tcPr.find(qn("w:tcBorders"))
    if tcBorders is None:
        tcBorders = OxmlElement("w:tcBorders"); tcPr.append(tcBorders)
    e = tcBorders.find(qn("w:" + edge))
    if e is None:
        e = OxmlElement("w:" + edge); tcBorders.append(e)
    e.set(qn("w:val"), "single"); e.set(qn("w:sz"), sz)
    e.set(qn("w:space"), "0"); e.set(qn("w:color"), "000000")


def set_cell(cell, text, bold=False, size=10.5, align=WD_ALIGN_PARAGRAPH.CENTER):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = align
    pf = p.paragraph_format
    pf.space_before = Pt(2); pf.space_after = Pt(2); pf.line_spacing = 1.15
    add_rich(p, text, SONG, TNR, size, bold)
    cell.vertical_alignment = 1


def three_line_table(doc, data, caption, widths, font=10.5):
    para(doc, caption, SONG, TNR, 9, align=WD_ALIGN_PARAGRAPH.CENTER,
         before=6, after=3, line=Pt(14), keep=True)
    t = doc.add_table(rows=len(data), cols=len(data[0]))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    tblPr = t._tbl.tblPr
    layout = OxmlElement("w:tblLayout"); layout.set(qn("w:type"), "fixed")
    tblPr.append(layout)
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement("w:" + edge)
        el.set(qn("w:val"), "single" if edge in ("top", "bottom") else "none")
        el.set(qn("w:sz"), "12" if edge in ("top", "bottom") else "0")
        el.set(qn("w:space"), "0"); el.set(qn("w:color"), "000000")
        borders.append(el)
    tblPr.append(borders)
    for j, w in enumerate(widths):
        t.columns[j].width = Cm(w)
    for i, row in enumerate(data):
        trPr_ = t.rows[i]._tr.get_or_add_trPr()
        cs = OxmlElement("w:cantSplit"); cs.set(qn("w:val"), "true"); trPr_.append(cs)
        for j, val in enumerate(row):
            cell = t.cell(i, j)
            cell.width = Cm(widths[j])
            set_cell(cell, val, bold=(i == 0), size=font,
                     align=WD_ALIGN_PARAGRAPH.LEFT if j == 0 else WD_ALIGN_PARAGRAPH.CENTER)
            if i == 0:
                _border(cell, "bottom", sz="8")
            if i < len(data) - 1:
                for pp in cell.paragraphs:
                    pp.paragraph_format.keep_with_next = True
    trPr = t.rows[0]._tr.get_or_add_trPr()
    th = OxmlElement("w:tblHeader"); th.set(qn("w:val"), "true"); trPr.append(th)


def cn_quotes(text):
    out, open_q = [], True
    for ch in text:
        if ch == '"':
            out.append("\u201c" if open_q else "\u201d"); open_q = not open_q
        else:
            out.append(ch)
    return "".join(out)
