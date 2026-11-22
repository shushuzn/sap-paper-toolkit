#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_manuscript.py — 论文机械可核验项检查

最先检查两条硬性禁令（不可豁免，见 SKILL.md 第零节）：
    F5 禁词：课程／课程论文／本课程／课件／讲义／课堂／教材／结课／学时／课后
    F6 破折号：——
    F7 对偶否定：不是 A 而是 B、并非 A 而是 B、不在 A 而在 B、不在 A 而是 B、
       不在于 A 而在于 B、不是 A，是 B、与其说 A 不如说 B、A 而非 B、而不是 B
    R7 文献表含教学材料（禁令 4：教学材料不得作为引用来源）

其余可规则判定项：字数口径、参考文献编号与引用覆盖、
摘要与关键词、风险表述、数字与单位格式、条目化程度、图表编号、
规范状态（B1 缺发布年 / B2 草案当现行）、证据等级虚报（B3 实测类措辞无引注）。

不做语义判断（论证是否成立、引文是否错配由模型负责）。

用法：
    python audit_manuscript.py <manuscript.md|.txt|.docx>
        [--min-chars 3000] [--min-refs 25]
        [--count 汉字|word|char]     字数口径，默认 汉字
        [--json report.json]

退出码：0 全部通过；1 存在 FAIL。
"""
import argparse
import json
import os
import re
import sys

FAIL, WARN, INFO = "FAIL", "WARN", "INFO"


# ---------- 读取 ----------

def extract(path):
    low = path.lower()
    if low.endswith(".docx"):
        try:
            from docx import Document
        except ImportError:
            sys.exit("需要 python-docx 才能读取 .docx")
        doc = Document(path)
        parts = [p.text for p in doc.paragraphs]
        for t in doc.tables:
            for r in t.rows:
                parts.append(" | ".join(c.text.strip() for c in r.cells))
        return "\n".join(parts)
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read()


# ---------- 通用 ----------

def hanzi(s):
    return len(re.findall(r"[\u4e00-\u9fa5]", s))


def word_like(s):
    """近似 Word“字数”：汉字 + 英文/数字词。"""
    return hanzi(s) + len(re.findall(r"[A-Za-z0-9]+(?:[\-\.][A-Za-z0-9]+)*", s))


def split_body_refs(text):
    m = re.search(r"^\s*#{0,3}\s*参考文献\s*$", text, re.M)
    if not m:
        return text, ""
    return text[: m.start()], text[m.start():]


def para_list(text):
    return [ln.strip() for ln in text.split("\n") if ln.strip()]


# ---------- 检查项 ----------

def check_metrics(body, args):
    out = []
    hz, wl, ch = hanzi(body), word_like(body), len(re.sub(r"\s", "", body))
    out.append(dict(level=INFO, code="M1", title="字数",
                    detail=f"汉字 {hz} / 近似 Word 字数 {wl} / 字符(不含空白) {ch}；"
                           f"本报告按口径「{args.count}」判定"))
    val = {"hanzi": hz, "word": wl, "char": ch}[args.count]
    if val < args.min_chars:
        out.append(dict(level=FAIL, code="M2", title="正文不足下限",
                        detail=f"口径「{args.count}」计 {val}，要求 ≥{args.min_chars}"))
    else:
        out.append(dict(level=INFO, code="M2", title="正文下限",
                        detail=f"口径「{args.count}」计 {val}，满足 ≥{args.min_chars}"))
    return out


CITE = re.compile(r"\[(\d+(?:\s*[,，\-–—]\s*\d+)*)\]")


def expand_cite(inner):
    nums = []
    for piece in re.split(r"[,，]", inner):
        piece = piece.strip()
        if re.fullmatch(r"\d+", piece):
            nums.append(int(piece))
        else:
            m = re.fullmatch(r"(\d+)\s*[\-–—]\s*(\d+)", piece)
            if m:
                a, b = int(m.group(1)), int(m.group(2))
                nums.extend(range(min(a, b), max(a, b) + 1))
    return nums


def check_teaching_refs(refs):
    """禁令 4 / R7：文献表不得含教学材料类条目。"""
    out = []
    pat = re.compile(r"课件|讲义|教案|PPT|幻灯片|网络课程|mooc|授课|课堂|习题|试题|教学视频", re.I)
    hits = []
    for ln in refs.split("\n"):
        m = re.match(r"^\s*\[(\d+)\]\s*(\S.*)$", ln)
        if m and pat.search(m.group(2)):
            hits.append((m.group(1), m.group(2)[:60]))
    if hits:
        sample = "；".join(f"[{i}] {t}…" for i, t in hits[:3])
        out.append(dict(level=FAIL, code="R7", title="文献表含教学材料",
                        detail=f"{len(hits)} 条；{sample}。教学材料不得作为引用来源（禁令 4），"
                               f"须改为公开文献，或删除该处论断"))
    return out


def check_refs(body, refs, args):
    out = []
    # 源文件（Markdown 写作稿）常用 [@key] 占位 + 构建脚本生成文献表，
    # 此时引注与文献表不在此文件中，机械核验须对构建后的 docx 执行。
    if re.search(r"\[@[A-Za-z0-9_\-]+\]", body + refs):
        out.append(dict(level=INFO, code="R0", title="源文件模式",
                        detail="检出 [@key] 占位符：引注与文献表由构建脚本生成，"
                               "R1–R6 跳过，请对构建后的 .docx 复跑本脚本"))
        return out
    entries = re.findall(r"^\s*\[(\d+)\]", refs, re.M)
    n = len(entries)
    if n < args.min_refs:
        out.append(dict(level=FAIL, code="R1", title="参考文献条数不足",
                        detail=f"{n} 条，要求 ≥{args.min_refs}"))
    else:
        out.append(dict(level=INFO, code="R1", title="参考文献条数", detail=f"{n} 条"))

    if entries:
        nums = [int(x) for x in entries]
        if nums != list(range(1, n + 1)):
            gaps = [i for i in range(1, max(nums) + 1) if i not in nums]
            dup = sorted({x for x in nums if nums.count(x) > 1})
            out.append(dict(level=FAIL, code="R2", title="条目编号不连续",
                            detail=f"缺号 {gaps}，重号 {dup}"))

    seq, seen = [], set()
    for m in CITE.finditer(body):
        for k in expand_cite(m.group(1)):
            if k not in seen:
                seen.add(k)
                seq.append((k, m.start()))
    if seq:
        order = [k for k, _ in seq]
        expect = sorted(order)
        if order != expect:
            bad = [(k, i + 1) for i, (k, _) in enumerate(seq) if k != expect[i]][:5]
            out.append(dict(level=FAIL, code="R3", title="顺序编码制被破坏",
                            detail=f"正文首次出现顺序应为 1,2,3…；实测前 5 处错位：{bad}"))
        uncited = [k for k in range(1, n + 1) if k not in seen]
        if uncited:
            out.append(dict(level=FAIL, code="R4", title="文献未被正文引用",
                            detail=f"未被引用的编号：{uncited}"))
        missing = sorted(k for k in seen if k > n)
        if missing:
            out.append(dict(level=FAIL, code="R5", title="引用了不存在的条目",
                            detail=f"正文引用但文后无此条：{missing}"))
        out.append(dict(level=INFO, code="R6", title="引注覆盖",
                        detail=f"正文引用编号 {len(seen)} 个，引注标记 {len(CITE.findall(body))} 处"))
    elif n:
        out.append(dict(level=FAIL, code="R6", title="正文无引注",
                        detail="文后有文献条目但正文查不到 [n] 标记"))
    return out


def check_front(body):
    out = []
    has_cn = bool(re.search(r"摘\s*要", body))
    has_en = bool(re.search(r"\bAbstract\b", body, re.I))
    if not has_cn:
        out.append(dict(level=FAIL, code="F1", title="缺中文摘要", detail="未检出「摘要」"))
    if not has_en:
        out.append(dict(level=FAIL, code="F2", title="缺英文摘要", detail="未检出 Abstract"))
    m = re.search(r"关键词[:：]?\s*(.+)", body)
    if not m:
        out.append(dict(level=FAIL, code="F3", title="缺关键词", detail="未检出「关键词」"))
    else:
        kws = [k for k in re.split(r"[；;，,、]\s*", m.group(1).strip()) if k]
        if not 3 <= len(kws) <= 8:
            out.append(dict(level=WARN, code="F3", title="关键词数量",
                            detail=f"{len(kws)} 个（宜 3~8 个）：{kws}"))
        else:
            out.append(dict(level=INFO, code="F3", title="关键词", detail=f"{len(kws)} 个"))
    return out


RISK = [
    ("应试语", r"需要记住|应当记住|不难看出|显而易见|众所周知|大家都知道|试想|同学们"),
    ("第一人称", r"我们|我校|笔者以为"),
    ("无出处断言", r"已有研究(表明|指出|显示)|据工业实践|据悉|大量研究(表明|显示)|一般认为|业界普遍认为"),
    ("绝对化", r"完全(可以|能够|解决)|必然|毫无疑问|公认的"),
    ("程式化填充", r"综上所述|总而言之|值得注意的是|需要指出的是"),
]

# 禁令 1：稿件中一律不得出现的词。按长词优先排列，避免短词吞掉长词的定位。
BANNED = [
    "课程论文", "本课程", "课程", "课件", "讲义", "课堂", "教材", "结课", "学时", "课后",
]

# 禁令 2：破折号。单字线「—」属连接号，不在其列。
DASH = "——"


def check_prohibited(text):
    """禁令 1（禁词）与禁令 2（破折号）。FAIL 且不可豁免。"""
    out = []
    lines = text.split("\n")
    for word in BANNED:
        hits = []
        for i, ln in enumerate(lines, 1):
            if word in ln:
                j = ln.index(word)
                hits.append((i, ln[max(0, j - 12): j + len(word) + 12]))
        if hits:
            sample = "；".join(f"行{i}: …{s}…" for i, s in hits[:3])
            out.append(dict(level=FAIL, code="F5", title=f"禁词「{word}」",
                            detail=f"{len(hits)} 处；{sample}。"
                                   f"改为「文献」「公开报道」或省去来源，不得为避词而编出处"))
    n_dash = text.count(DASH)
    if n_dash:
        where = []
        for i, ln in enumerate(lines, 1):
            j = ln.find(DASH)
            if j >= 0:
                where.append((i, ln[max(0, j - 14): j + 16]))
        sample = "；".join(f"行{i}: …{s}…" for i, s in where[:3])
        out.append(dict(level=FAIL, code="F6", title="破折号「——」",
                        detail=f"{n_dash} 处；{sample}。"
                               f"改用冒号（解释）、逗号（补充）、句号（独立判断）"))
    return out


# 禁令 6：对偶否定句式。先否后立把两个判断压进一句，容易用对比代替论证。
PAIRWISE = [
    (r"不是[^。；！？\n]{0,40}?而是", "不是 A 而是 B"),
    (r"并非[^。；！？\n]{0,40}?而是", "并非 A 而是 B"),
    (r"不在(?!于)[^。；！？\n]{0,24}?而在", "不在 A 而在 B"),
    (r"不在(?!于)[^。；！？\n]{0,30}?而是", "不在 A 而是 B"),
    (r"不在于[^。；！？\n]{0,24}?而在于", "不在于 A 而在于 B"),
    (r"与其说[^。；！？\n]{0,40}?不如说", "与其说 A 不如说 B"),
    (r"不是[^。；！？\n]{0,30}?，\s*是", "不是 A，是 B"),
    (r"而非", "A 而非 B"),
    (r"而不是", "而不是 B"),
]


def check_pairwise(text):
    """禁令 6：对偶否定句式。FAIL；引号内的引述须人工核对后保留。"""
    out = []
    lines = text.split("\n")
    for pat, name in PAIRWISE:
        rx = re.compile(pat)
        hits = []
        for i, ln in enumerate(lines, 1):
            for m in rx.finditer(ln):
                hits.append((i, ln[max(0, m.start() - 14): m.end() + 14]))
        if hits:
            sample = "；".join(f"行{i}: …{s}…" for i, s in hits[:3])
            out.append(dict(level=FAIL, code="F7", title=f"对偶否定「{name}」",
                            detail=f"{len(hits)} 处；{sample}。"
                                   f"改为直接陈述：先给肯定命题，否定另起一句；"
                                   f"引述原文须加引号并标明来源"))
    return out


def check_language(text):
    out = []
    paras = para_list(text)
    for name, pat in RISK:
        rx = re.compile(pat)
        hits = [(i + 1, p) for i, p in enumerate(paras) if rx.search(p)]
        if not hits:
            continue
        # 无出处断言：句内若带引注则降级为 OK
        if name == "无出处断言":
            hits = [(i, p) for i, p in hits if not CITE.search(p)]
            if not hits:
                continue
        level = WARN if name in ("程式化填充", "绝对化") else FAIL
        sample = [f"段{i}: {p[:40]}…" for i, p in hits[:3]]
        out.append(dict(level=level, code="W1", title=f"风险表述·{name}",
                        detail=f"{len(hits)} 处；例：{'；'.join(sample)}"))
    return out


def check_format(text, source_mode=False):
    out = []
    checks = [
        ("数字范围用 ~", r"\d\s*~\s*\d", "数值范围用浪纹线「～」，不用半角波浪号", FAIL),
        ("℃ 前缺空格", r"\d℃", "数值与单位符号间留空隙", WARN),
        ("编号连接号", r"[A-Z]{2,4}(?:/[A-Z]{1,2})?\s*\d{2,5}\s*[—–]\s*\d{4}", "编号中的年份连接须用半字线", FAIL),
        ("连续标点", r"[，。、；：]{2,}", "重复标点，多为编辑残留", FAIL),
        ("叠字残留", r"的的|了了|是是", "编辑残留", FAIL),
        ("半角括号夹中文", r"\([^)]*[\u4e00-\u9fa5][^)]*\)", "中文语境宜用全角括号", WARN),
        ("英文与汉字间空格", r"[\u4e00-\u9fa5][A-Za-z]{2,}|[A-Za-z]{2,}[\u4e00-\u9fa5]", "中文夹用英文宜加空格", WARN),
        ("上标标记泄漏", r"[\^_]\{", "公式标记未渲染", FAIL),
    ]
    for name, pat, why, level in checks:
        if source_mode and name == "上标标记泄漏":
            continue  # 写作稿中的 ^{} / _{} 是构建脚本的输入语法，不是渲染缺陷
        n = len(re.findall(pat, text))
        if n:
            out.append(dict(level=level, code="F4", title=f"格式·{name}",
                            detail=f"{n} 处；{why}"))
    return out


def check_listy(text):
    out = []
    # 序号后必须跟实质内容；「（1）」单独成行是公式编号，不算条目
    lead = len(re.findall(r"^[ \t\u3000]*[（(]\d+[）)][ \t\u3000]*[^\s]", text, re.M))
    ordinals = len(re.findall(r"(第一|第二|第三|第四|第五|其一|其二|其三)[，、是]", text))
    # 「一是…二是…」与「首先…其次…」和序数式是同一类清单化，只是不带序数词形。
    # 只认句首，避免把「统一是」「单一是」一类误算进来。
    chain = len(re.findall(r"[。；：][ \t\u3000]*(一是|二是|三是|四是|首先|其次|再次)", text))
    if lead:
        out.append(dict(level=WARN, code="S1", title="行首编号条目",
                        detail=f"{lead} 处；论文正文与结论宜为连贯论述，非条目清单"))
    if ordinals + chain >= 4:
        out.append(dict(level=WARN, code="S2", title="序数式列举",
                        detail=f"{ordinals + chain} 处（序数 {ordinals}、一二式 {chain}）；"
                               f"条目化会把论证降级为清单"))
    return out


# 元话语：作者向读者交代自己接下来打算写什么、替读者下判断、用「显然」跳过推理。
# 这类句子不含禁用词、不是破折号、不构成对偶否定，也不触犯引注规则，前面各组
# 检查都不会命中；它的问题是把论述变成对写作过程的叙述，读者读到的是作者的
# 安排而非研究内容，因此单列一组。
META = [
    ("交代写作安排", r"值得(展开|讨论|单独)"
                    r"|留待[^，。；]{0,12}(讨论|展开|说明|交代)"
                    r"|下面(将|先|讨论)|接下来(将|先)|本节(将|先)"
                    r"|本文要做的是|(不再|恕不)赘述|限于篇幅", WARN),
    ("宣告写作决策", r"本文(认为|以为|选择|拟|打算)|笔者", WARN),
    ("代替读者判断", r"不难(看出|发现|理解)|由此可见|显然", WARN),
    ("模糊回指", r"(如前|如上|上文|前文|后文)所述|前文(已|中)", WARN),
]


def check_metadiscourse(text):
    out = []
    paras = para_list(text)
    for name, pat, level in META:
        rx = re.compile(pat)
        hits = []
        for i, p in enumerate(paras):
            m = rx.search(p)
            if m:
                hits.append((i + 1, m.group(0)))
        if not hits:
            continue
        sample = [f"段{i}「{w}」" for i, w in hits[:3]]
        out.append(dict(level=level, code="W2", title=f"元话语·{name}",
                        detail=f"{len(hits)} 处；{'、'.join(sample)}；"
                               f"改为直接陈述内容，不叙述写作安排"))
    return out


def check_figs(body):
    out = []
    for kind in ("表", "图"):
        nums = [int(x) for x in re.findall(kind + r"\s*(\d+)", body)]
        if not nums:
            continue
        uniq = sorted(set(nums))
        if uniq != list(range(1, max(uniq) + 1)):
            out.append(dict(level=FAIL, code="S3", title=f"{kind}编号不连续",
                            detail=f"出现编号 {uniq}"))
        else:
            out.append(dict(level=INFO, code="S3", title=f"{kind}编号", detail=f"1–{max(uniq)} 连续"))
    return out


STD_NUM = re.compile(r"\b[A-Z]{2,4}(?:/[A-Z]{1,2})?\s*\d{2,5}(?:\.\d+)?")
DRAFT_WORD = re.compile(r"征求意见稿|修订计划|报批稿|送审稿|草案|计划号")
CURRENT_VERB = re.compile(r"规定为|限值为|要求为|应不大于|应不超过|不得高于")
MEASURED = re.compile(r"实测|测定为|实验测得|实验表明|实测表明")


def _is_doc_number(m, text):
    """判断题名式文献编号（专利、公开号）而非标准编号。

    两类编号的写法不同：标准以「代号 + 序号 + 半字线 + 发布年」构成，
    序号不超过五位，年后无续写；文献编号则把年份编进号码本身，序号
    长达七位以上，或写成「年份/序号」。若不排除，五位窗口会把长号码
    截断成 `US20210` 一类残片，再判成「缺发布年」，属误报。
    """
    nxt = text[m.end():m.end() + 1]
    if nxt.isdigit():
        return True   # 序号未结束，超过五位的连续数字不是标准序号
    if re.match(r"\s*/\s*\d", text[m.end():m.end() + 8]):
        return True   # 年份/序号 写法
    return False


def check_standard_status(text):
    """B1 编号引用缺发布年；B2 草案当现行（铁律 5 配套，见 C2-17）。"""
    out = []

    miss = []
    for m in STD_NUM.finditer(text):
        if _is_doc_number(m, text):
            continue
        tail = text[m.end():m.end() + 8]
        if re.match(r"\s*[-—–]\s*\d{4}", tail):
            continue  # 已带发布年份
        if re.match(r"\s*[~～]\s*\d", tail):
            continue  # 系列编号的波浪号写法
        miss.append(m.group(0))
    if miss:
        uniq = sorted(set(miss))
        out.append(dict(level=FAIL, code="B1", title="编号引用缺发布年",
                        detail=f"{len(miss)} 处；{uniq[:5]}。编号须带发布年份，"
                               f"否则读者无法判断版本；修改单另注（含某年第 N 号修改单）"))

    bad = []
    for sent in re.split(r"[。；;\n]", text):
        dm = DRAFT_WORD.search(sent)
        if not dm:
            continue
        vm = CURRENT_VERB.search(sent[dm.start():])
        if vm and vm.start() < 24:
            bad.append(sent[max(0, dm.start() - 6):dm.start() + 44].strip())
    if bad:
        out.append(dict(level=WARN, code="B2", title="草案当现行",
                        detail=f"{len(bad)} 处；例：{bad[0]}…。修订计划／征求意见稿只能写"
                               f"「拟调整」，不得与「规定为」「限值为」同句，须人工复核原文"))
    return out


def check_claim_strength(text):
    """B3 实测类措辞无引注：声称实测却指不出文献，属虚报证据等级（铁律 5）。"""
    out = []
    hits = []
    for sent in re.split(r"[。\n]", text):
        if not MEASURED.search(sent):
            continue
        if re.search(r"(未|不)(做|进行)?实测|未做实验|不作实验", sent):
            continue
        if CITE.search(sent) or "[@" in sent or re.search(r"式\s*（\d+）", sent):
            continue
        hits.append(sent.strip()[:70])
    if hits:
        out.append(dict(level=WARN, code="B3", title="实测类措辞无引注",
                        detail=f"{len(hits)} 处；例：{hits[0]}…。本文实测须给方法与数据，"
                               f"引自文献须补引注，仅机理推断则改为「机理上应」（E4）"))
    return out


# ---------- 输出 ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--min-chars", type=int, default=3000)
    ap.add_argument("--min-refs", type=int, default=25)
    ap.add_argument("--count", choices=["hanzi", "word", "char"], default="hanzi")
    ap.add_argument("--json")
    args = ap.parse_args()

    if not os.path.exists(args.path):
        sys.exit(f"文件不存在：{args.path}")

    text = extract(args.path)
    source_mode = bool(re.search(r"\[@[A-Za-z0-9_\-]+\]", text))
    body, refs = split_body_refs(text)

    items = []
    items += check_prohibited(text)
    items += check_pairwise(body)
    items += check_teaching_refs(refs)
    items += check_metrics(body, args)
    items += check_refs(body, refs, args)
    items += check_front(body)
    items += check_language(body)
    items += check_format(text, source_mode)
    items += check_listy(body)
    items += check_metadiscourse(body)
    items += check_figs(body)
    items += check_standard_status(text)
    items += check_claim_strength(body)

    n_fail = sum(1 for i in items if i["level"] == FAIL)
    n_warn = sum(1 for i in items if i["level"] == WARN)

    print(f"# 机械核验报告：{os.path.basename(args.path)}")
    print(f"\n口径：字数={args.count}，文献下限={args.min_refs}，正文下限={args.min_chars}")
    print(f"结果：FAIL {n_fail} 项，WARN {n_warn} 项\n")
    for lv in (FAIL, WARN, INFO):
        rows = [i for i in items if i["level"] == lv]
        if not rows:
            continue
        print(f"## {lv}")
        for i in rows:
            print(f"- [{i['code']}] {i['title']}：{i['detail']}")
        print()

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(dict(path=args.path, count=args.count, items=items), f,
                      ensure_ascii=False, indent=2)
        print(f"JSON 已写入 {args.json}")

    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
