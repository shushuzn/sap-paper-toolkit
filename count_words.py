# -*- coding: utf-8 -*-
"""统计正文（从正文首章到参考文献之前）的篇幅，只读，不改文档。

用法：

    python count_words.py [稿件.md|稿件.docx] [--engine auto|plain|word]
                          [--start 锚点] [--end 锚点]

两条通道，口径不同，不可混用：

- plain：直接解析 .md 或 .docx 的段落文本，给出汉字数、非空白字符数、
  切分单元数。跨平台可用，但**不是**文字处理软件报出的"字数"。
- word：调用本机已安装的文字处理软件取它自己统计的数值，只在 Windows
  且装有相应组件时可用。引用"字数"这一口径时应以此通道为准。

auto 为默认：能用 word 通道就用，否则回落 plain，并明确打印所用通道。
"""
import re
import sys

import manuscript_io as mio

# 两条通道共用的区间锚点，由 main 按命令行填充
# 默认取正文首章常见名；稿件用别的叫法时用 --start 覆盖
start_key = "引言"
end_key = "参考文献"


def count_plain(text):
    """按字符类别统计，返回 (汉字数, 非空白字符数, 切分单元数)。"""
    han = len(re.findall(r"[\u4e00-\u9fa5]", text))
    nonspace = len(re.sub(r"\s", "", text))
    # 切分单元：连续西文/数字算一个，每个汉字算一个，近似文字处理软件的口径
    units = len(re.findall(r"[\u4e00-\u9fa5]|[A-Za-z0-9]+", text))
    return han, nonspace, units


def slice_body(paras, start_key, end_key):
    """按锚点切出正文段落；返回 (起段下标, 止段下标, 诊断信息)。"""
    def locate(key):
        if not key:
            return -1
        i = mio.find_heading(paras, (key,))
        if i >= 0:
            return i
        # 段落不是标题时，退回包含式匹配
        for j, p in enumerate(paras):
            if mio.squash(key) in mio.squash(p):
                return j
        return -1

    s = locate(start_key)
    if s < 0:
        # 兜底一：Markdown 一级编号标题
        for i, p in enumerate(paras):
            if mio.heading_level(p) == 1 and re.match(r"^#\s*\d", p):
                s = i
                break
    if s < 0:
        # 兜底二：成稿里的编号标题段，如「1　引言」或「1 引言」
        for i, p in enumerate(paras):
            if re.match(r"^\d+(\.\d+)*[\s　]", p) and len(p) < 40:
                s = i
                break
    e = locate(end_key)
    if e < 0:
        e = len(paras)
    return s, e, (start_key, end_key)


def run_plain(src):
    paras = mio.read_paragraphs(src)
    s, e, keys = slice_body(paras, start_key, end_key)
    if s < 0:
        head = ["%d. %s" % (i + 1, p[:40]) for i, p in enumerate(paras[:8])]
        sys.exit("定不到正文起点：没找到 --start 指定的锚点（当前为「%s」），"
                 "也没有形如「# 1 章名」或「1 章名」的编号标题。\n"
                 "稿件开头几段：\n  %s\n用 --start 指定正文首段里的一个特征词。"
                 % (start_key, "\n  ".join(head)))
    if e <= s:
        sys.exit("正文区间为空：起点在第 %d 段，止点在第 %d 段。"
                 "检查 --end 是否指到了 --start 之前。" % (s + 1, e))
    body = "\n".join(paras[s:e])
    han, nonspace, units = count_plain(body)

    print("通道：plain（直接解析文件文本，非文字处理软件口径）")
    print("正文区间：第 %d 段 → 第 %d 段（共 %d 段）" % (s + 1, e, e - s))
    print("汉字数：%d" % han)
    print("非空白字符数：%d" % nonspace)
    print("切分单元数（近似字数）：%d" % units)
    print()
    print("说明：以上三项都不是文字处理软件报出的「字数」。需要在正式表格或")
    print("字数限制处填写时，用 --engine word，或直接在软件里查看统计信息。")
    if src.suffix.lower() != ".docx":
        print("另注：表格文字若不在源文件中（例如由数据层单独提供），本通道不计入；")
        print("源文件与成稿的差值通常来自这部分，需计表格时以成稿为准。")
    return 0


def run_word(src):
    try:
        import win32com.client as win32
    except ImportError:
        sys.exit("word 通道需要本机的文字处理组件（Windows 专用），当前环境"
                 "不可用。改用 --engine plain，或直接在软件里查看字数统计。")

    import os
    app = win32.DispatchEx("Word.Application")
    app.Visible = False
    app.DisplayAlerts = 0
    try:
        doc = app.Documents.Open(os.path.abspath(str(src)), ReadOnly=True)
        s, e = 0, 0
        for i, p in enumerate(doc.Paragraphs, 1):
            t = p.Range.Text.strip()
            if s == 0 and start_key and mio.squash(start_key) in mio.squash(t):
                s = i
            if s and end_key and mio.squash(end_key) in mio.squash(t):
                e = i - 1
                break
        if not s:
            sys.exit("word 通道定不到正文起点：用 --start 指定正文首段的关键词。")
        if e <= s:
            e = doc.Paragraphs.Count

        rng = doc.Range(doc.Paragraphs(s).Range.Start, doc.Paragraphs(e).Range.End)
        print("通道：word（本机文字处理软件口径）")
        print("正文区间：第 %d 段 → 第 %d 段" % (s, e))
        print("字数：%d" % rng.ComputeStatistics(0))
        print("字符数（不计空格）：%d" % rng.ComputeStatistics(3))
        print("字符数（计空格）：%d" % rng.ComputeStatistics(5))
        print("全文字符数（不计空格）：%d" % doc.ComputeStatistics(3))
        print("页数：%d" % doc.ComputeStatistics(2))
        doc.Close(False)
    finally:
        app.Quit()
    return 0


def main(argv):
    global start_key, end_key
    if "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0

    engine, argv = mio.pop_option(argv, "--engine", "auto")
    start_key, argv = mio.pop_option(argv, "--start", "引言")
    end_key, argv = mio.pop_option(argv, "--end", "参考文献")

    if engine not in ("auto", "plain", "word"):
        sys.exit("--engine 只能是 auto、plain、word 之一，收到：%s" % engine)
    bad = [a for a in argv if a.startswith("-")]
    if bad:
        sys.exit("未知选项：%s（用 --help 看用法）" % " ".join(bad))

    src = mio.resolve_source(argv)
    print("稿件：%s\n" % src.name)

    if engine == "plain":
        return run_plain(src)
    if engine == "word":
        return run_word(src)

    # auto：先试 word，不可用则回落 plain
    try:
        import win32com.client  # noqa: F401
    except ImportError:
        print("auto：本机无文字处理组件，回落 plain 通道。\n")
        return run_plain(src)
    return run_word(src)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
