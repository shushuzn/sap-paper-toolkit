# -*- coding: utf-8 -*-
"""稿件的结构性核验：摘要与关键词、标题层级、图表与公式引用、引文编号、缩略语。

只读，不改稿件。用法：

    python audit_doc.py [稿件.md|稿件.docx] [--data 数据层.py]

稿件与数据层的位置可用位置参数、--data、环境变量 PAPER_SRC / PAPER_DATA
指定；章节叫法与默认名不同时，在数据层写 SECTIONS 覆盖（见 README）。

两种模式自动切换：

- 结构模式：稿件带 Markdown 标题标记（.md 源文件）。检查摘要、关键词、
  标题层级跳级，引文按键名比对数据层的文献表。
- 成稿模式：稿件没有结构标记（.docx 成稿）。跳过需要标题的检查，改查
  图表与公式编号、引文编号是否连续、是否超出文献表。

本脚本只报告可在文本层面判定的问题。标题是否恰当、图表是否必要、引文
是否支持论点，属语义判断，脚本不涉及。
"""
import re
import sys

import manuscript_io as mio

FAIL, WARN = "FAIL", "WARN"
issues = []


def add(level, title, detail):
    issues.append((level, title, detail))


def locate_refs_heading(paras):
    """成稿模式下的参考文献分界：按前缀匹配段落文本。"""
    for i, p in enumerate(paras):
        if mio.squash(p).startswith(mio.squash("参考文献")):
            return i
    return -1


def main(argv):
    if "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0
    data_path, argv = mio.pop_option(argv, "--data")
    bad = [a for a in argv if a.startswith("-")]
    if bad:
        sys.exit("未知选项：%s（用 --help 看用法）" % " ".join(bad))

    src = mio.resolve_source(argv)
    data = mio.load_data(mio.resolve_data(data_path))
    paras = mio.read_paragraphs(src)
    structured = any(mio.heading_level(p) for p in paras)

    print("稿件：%s（%s 段，%s）"
          % (src.name, len(paras), "结构模式" if structured else "成稿模式"))
    if data is None:
        print("数据层：未找到，跳过缩略语与文献表比对")
    print()

    st = mio.split_structure(paras, data) if structured else None

    # ---------- 摘要与关键词（仅结构模式） ----------
    if structured:
        if st["abstract_cn"]:
            n = len(re.findall(r"[\u4e00-\u9fa5]", st["abstract_cn"]))
            print("中文摘要汉字数：%d" % n)
        else:
            add(FAIL, "缺中文摘要段",
                "按结构名找不到摘要标题，或标题下没有正文；若稿件用别的叫法，"
                "在数据层 SECTIONS 的 abstract_cn 里写明")

        if st["keywords_cn"]:
            kw = re.split(r"[：:]", st["keywords_cn"], maxsplit=1)[-1]
            items = [x for x in re.split(r"[；;、]", kw) if x.strip()]
            print("中文关键词数：%d %s" % (len(items), items))
            if not (3 <= len(items) <= 8):
                add(WARN, "中文关键词数不在常见区间",
                    "实为 %d 个；多数学术出版规范建议 3~8 个" % len(items))
        else:
            add(WARN, "缺中文关键词行", "按结构名找不到关键词段")

        if st["abstract_en"]:
            print("英文摘要词数：%d" % len(st["abstract_en"].split()))
        else:
            add(WARN, "缺英文摘要段", "按结构名找不到英文摘要")

        if st["keywords_en"]:
            kw = re.split(r"[：:]", st["keywords_en"], maxsplit=1)[-1]
            items = [x for x in kw.split(";") if x.strip()]
            print("英文关键词数：%d" % len(items))
        else:
            add(WARN, "缺英文关键词行", "按结构名找不到英文关键词")

        h1 = [p for p in paras if mio.heading_level(p) == 1]
        print("一级标题数：%d" % len(h1))
        for p in h1:
            print("  %s" % p.lstrip("#").strip())

        prev = 0
        for p in paras:
            lv = mio.heading_level(p)
            if not lv:
                continue
            if prev and lv > prev + 1:
                add(FAIL, "标题层级跳级",
                    "从 %d 级直接到 %d 级：%s" % (prev, lv, p.lstrip("#").strip()))
            prev = lv

    # ---------- 定正文 ----------
    if structured:
        body = st["body"]
        refs_start = st["index"]["references"]
        if body is None:
            add(FAIL, "定不到正文起点",
                "未找到形如「# 1 章名」的首个一级编号标题；实际标题见上方清单")
            body = "\n".join(paras)
    else:
        refs_start = locate_refs_heading(paras)
        if refs_start < 0:
            add(WARN, "定不到参考文献分界",
                "整篇都按正文统计；含文献条目时，条目开头的编号可能被当作引文，"
                "使编号检查偏松")
            body = "\n".join(paras)
        else:
            body = "\n".join(paras[:refs_start])
            print("参考文献分界：第 %d 段（之后 %d 段不计入正文）"
                  % (refs_start + 1, len(paras) - refs_start))

    # ---------- 图表与公式引用 ----------
    # 不预设编号，按正文实际提及统计，并报出编号缺口
    patterns = {
        "表": r"表\s*(\d+)",
        "图": r"图\s*(\d+)",
        "式": r"(?:式|公式)\s*[（(]\s*(\d+)\s*[）)]",
    }
    for label, pat in patterns.items():
        nums = [int(x) for x in re.findall(pat, body)]
        if not nums:
            print("正文未提及%s编号" % label)
            continue
        uniq = sorted(set(nums))
        print("正文提及%s：%d 次，编号 %s" % (label, len(nums), uniq))
        holes = sorted(set(range(1, uniq[-1] + 1)) - set(uniq))
        if holes:
            add(WARN, "%s编号不连续" % label,
                "正文提及到 %d 号，缺 %s；需确认是漏引还是编号笔误"
                % (uniq[-1], holes))

    # ---------- 引文 ----------
    cites = set()
    for m in re.finditer(r"\[(\d+(?:\s*[,-]\s*\d+)*)\]", body):
        for part in re.split(r"[,，]", m.group(1)):
            part = part.strip()
            if re.match(r"^\d+\s*-\s*\d+$", part):
                a, b = [int(x) for x in re.split(r"\s*-\s*", part)]
                if a <= b:
                    cites.update(range(a, b + 1))
            elif part.isdigit():
                cites.add(int(part))

    # 源文件用键名引用（[@键]）时，编号要到渲染阶段才产生，此时只能比对键名
    key_cites = set()
    for m in re.finditer(r"\[@([^\]]+)\]", body):
        for k in re.split(r"[,;，；\s]+", m.group(1)):
            k = k.lstrip("@").strip()
            if k:
                key_cites.add(k)

    # 文献总条数：优先数据层显式声明，否则按文献表实际条目数
    ref_total = getattr(data, "REF_TOTAL", None) if data else None
    if not ref_total and data is not None:
        ref_total = len(mio.refs_from_data(data)) or None

    if key_cites and not cites:
        print("正文引用：键名引用 %d 处，去重 %d 个"
              % (len(re.findall(r"\[@", body)), len(key_cites)))
        refs = getattr(data, "REFS", None) if data else None
        if isinstance(refs, dict) and refs:
            dangling = sorted(key_cites - set(refs))
            unused = sorted(set(refs) - key_cites)
            if dangling:
                add(FAIL, "引用了不存在的文献键",
                    "%s；正文的 [@键] 在文献表里找不到对应条目" % dangling)
            if unused:
                add(FAIL, "文献表有条目未被引用",
                    "%s；顺序编码制要求条目与引用一一对应" % unused)
            print("键名比对：文献表 %d 条，正文引用 %d 个，悬空 %d，未引用 %d"
                  % (len(refs), len(key_cites), len(dangling), len(unused)))
        else:
            print("数据层未给 REFS，无法比对键名；编号覆盖须对成稿核验")
        print("编号是否连续、覆盖是否完整，须对渲染后的成稿再跑一次本脚本")
    else:
        print("正文引用编号：%d 个，最大 %s"
              % (len(cites), max(cites) if cites else "无"))
        if ref_total:
            miss = sorted(set(range(1, ref_total + 1)) - cites)
            if miss:
                add(FAIL, "文献未被正文引用",
                    "文献表 %d 条，正文未引 %s" % (ref_total, miss))
            over = sorted(n for n in cites if n > ref_total)
            if over:
                add(FAIL, "引文编号超出文献表",
                    "正文引了 %s，文献表只有 %d 条" % (over, ref_total))
        elif cites:
            holes = sorted(set(range(1, max(cites) + 1)) - cites)
            if holes:
                add(WARN, "引文编号有缺口",
                    "正文引到 %d 号，缺 %s；可能是漏引或编号跳号"
                    % (max(cites), holes))
        else:
            print("文献总条数未知，且正文无可识别的引文标记")

    # ---------- 缩略语 ----------
    abbr = getattr(data, "ABBR", None) if data else None
    if abbr:
        for a in abbr:
            first = body.find(a)
            if first < 0:
                add(WARN, "缩略语未在正文出现", a)
                continue
            ctx = body[max(0, first - 40):first + len(a)].replace("\n", " ")
            print("  %s 首次出现：…%s" % (a, ctx))
    elif data is not None:
        print("缩略语：数据层未给 ABBR，跳过首次出现检查")

    # ---------- 汇总 ----------
    print()
    if not issues:
        print("结论：未发现可机械判定的结构问题。")
        return 0
    for lv, t, d in issues:
        print("[%s] %s：%s" % (lv, t, d))
    f = sum(1 for lv, _, _ in issues if lv == FAIL)
    print("合计：FAIL %d，WARN %d" % (f, len(issues) - f))
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
