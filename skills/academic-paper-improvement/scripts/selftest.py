#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selftest.py — 规则自检：文档列举与检测器实现是否仍然一致

为什么需要这个文件：
    禁令与检测器的对应关系写在两处，一处是 SKILL.md 的列举，一处是
    audit_manuscript.py 的正则与词表。两处靠人记住保持同步，结果就是
    「列举补到九种、计数仍写七种」这类漂移，改完还能通过全部核验。
    本文件把一致性写成断言，把「检测器能用」从声明变成证据。

检查三类：
    A 检测器能触发：每条禁令给一个正样本，命中即通过
    B 不误报：干净句子与单个连接号「—」不得触发
    C 文档与代码对齐：禁令条数、形态条数、词表内容三处互相印证
    D–H 逐组补充：解析层、编号误报边界、元话语、摘要体裁，各带正负样本

用法：
    python selftest.py            # 全部用例，逐条打印
    python selftest.py --quiet    # 只打印失败项与小结

退出码：0 全部通过；1 存在失败。
"""
import argparse
import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIT = os.path.join(HERE, "audit_manuscript.py")
SKILL = os.path.join(HERE, os.pardir, "SKILL.md")
ROOT = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir, os.pardir))


def load_audit():
    if not os.path.exists(AUDIT):
        sys.exit("找不到 %s，本文件须与 audit_manuscript.py 同目录" % AUDIT)
    spec = importlib.util.spec_from_file_location("audit_manuscript", AUDIT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


results = []


def record(name, ok, note=""):
    results.append((name, ok, note))


def expect_hit(label, items, code):
    hit = [i for i in items if i.get("code") == code]
    record(label, bool(hit), "" if hit else "未触发 %s" % code)


def expect_clean(label, items):
    fails = [i for i in items if i.get("level") == "FAIL"]
    note = "" if not fails else "误报 %s" % "，".join(i.get("code", "?") for i in fails)
    record(label, not fails, note)


# ---------- A 检测器能触发 ----------

def part_a(mod):
    # 禁令 1：词表中每个词各给一句
    for word in mod.BANNED:
        items = mod.check_prohibited("本段涉及%s的相关说明。" % word)
        expect_hit("F5 命中「%s」" % word, items, "F5")

    # 禁令 2：破折号
    items = mod.check_prohibited("结构——性能的关系需要重述。")
    expect_hit("F6 命中破折号", items, "F6")

    # 禁令 6：九种形态，逐个对应 PAIRWISE 的顺序
    samples = {
        "不是 A 而是 B": "关键不是名称，而是先后次序。",
        "并非 A 而是 B": "该现象并非记录误差，而是真实的滞后。",
        "不在 A 而在 B": "差距不在条文，而在执行的均匀性。",
        "不在 A 而是 B": "修订重点不在措辞，而是收紧判定条件。",
        "不在于 A 而在于 B": "限制因素不在于设备，而在于操作精度。",
        "与其说 A 不如说 B": "与其说是阈值，不如说是操作窗口。",
        "不是 A，是 B": "这一轮不是压缩，是纠错。",
        "A 而非 B": "这属于改写而非压缩。",
        "而不是 B": "把两件事分开处理，而不是要求一次兼得。",
    }
    names = [name for _, name in mod.PAIRWISE]
    record("PAIRWISE 形态名与正样本一一对应",
           set(names) == set(samples),
           "代码有而样本缺：%s；样本有而代码缺：%s" % (
               sorted(set(names) - set(samples)), sorted(set(samples) - set(names))))
    for name, text in samples.items():
        items = mod.check_pairwise(text)
        record("F7 命中「%s」" % name, bool(items), "" if items else "未触发")

    # 「不在…而在于」不得被「不在…而在」重复计数
    items = mod.check_pairwise("限制因素不在于设备，而在于操作精度。")
    record("F7 「不在于…而在于」只报一次", len(items) == 1,
           "报了 %d 次：%s" % (len(items), [i["title"] for i in items]))

    # 禁令 4：文献表含教学材料
    refs = "[1] 某某. 某主题课件[Z]. 内部资料."
    expect_hit("R7 命中教学材料条目", mod.check_teaching_refs(refs), "R7")


# ---------- B 不误报 ----------

def part_b(mod):
    clean = [
        "甲方案的价值在于降低误差，成本只是附带效果。",
        "本次修订将判定条件收紧，其余限值维持不变。",
        "结论的强度随证据等级下降，判断依据取全文最弱一环。",
        "教学材料只算传递环节，够不上出处。",
    ]
    for i, s in enumerate(clean, 1):
        expect_clean("干净句 %d 不触发禁令" % i, mod.check_prohibited(s) + mod.check_pairwise(s))

    # 单字线「—」属连接号，不是破折号
    expect_clean("单个连接号「—」不触发 F6", mod.check_prohibited("结构—性能关系"))

    normal_refs = "[1] 某某. 某主题研究[J]. 某刊, 1(1): 1-9."
    expect_clean("正常文献条目不触发 R7", mod.check_teaching_refs(normal_refs))


# ---------- C 文档与代码对齐 ----------

def part_c(mod):
    if not os.path.exists(SKILL):
        record("SKILL.md 可读", False, "找不到 %s" % SKILL)
        return
    text = open(SKILL, encoding="utf-8").read()

    m = re.search(r"^## 零、(\S+?)条硬性禁令", text, re.M)
    record("SKILL.md 有禁令节标题", bool(m), "未匹配「## 零、N 条硬性禁令」")
    rows = re.findall(r"^\| \*\*禁令 (\d+)\*\*", text, re.M)
    record("禁令表条目数与标题一致",
           bool(m) and len(rows) == len(set(rows)),
           "标题 %s，实际 %d 行" % (m.group(1) if m else "?", len(rows)))

    # 禁令 1 的词表须与 BANNED 同集
    row1 = re.search(r"^\| \*\*禁令 1\*\* \|(.+)$", text, re.M)
    if not row1:
        record("禁令 1 行可解析", False, "未找到禁令 1 行")
    else:
        body = row1.group(1)
        missing = [w for w in mod.BANNED if w not in body]
        record("BANNED 每个词都在禁令 1 列举中", not missing,
               "文档缺：%s（代码有、文档无，执行者不会去扫）" % missing)

    # 禁令 6 的形态数与 PAIRWISE 长度须一致
    row6 = re.search(r"^\| \*\*禁令 6\*\* \|(.+)$", text, re.M)
    if not row6:
        record("禁令 6 行可解析", False, "未找到禁令 6 行")
    else:
        seg = re.search(r"对偶否定句式\*\*：(.+?)。", row6.group(1))
        if not seg:
            record("禁令 6 列举可解析", False, "未匹配「对偶否定句式**：…。」")
        else:
            listed = [s for s in seg.group(1).split("、") if s.strip()]
            record("禁令 6 形态数与 PAIRWISE 一致",
                   len(listed) == len(mod.PAIRWISE),
                   "文档 %d 种、代码 %d 种；文档：%s" % (
                       len(listed), len(mod.PAIRWISE), "、".join(listed)))

    # 形态名双向覆盖
    doc_forms = set(x.strip() for x in listed) if row6 and seg else set()
    code_forms = set(n for _, n in mod.PAIRWISE)
    if doc_forms:
        record("形态名文档与代码同集", doc_forms == code_forms,
               "文档独有：%s；代码独有：%s" % (sorted(doc_forms - code_forms),
                                              sorted(code_forms - doc_forms)))

    # 元话语各类别名须在文档中逐一列出，否则执行者不知道要扫哪几类
    meta_names = [n for n, _, _ in getattr(mod, "META", [])]
    missing = [n for n in meta_names if n not in text]
    record("元话语类别名都在 SKILL.md 列举中", meta_names and not missing,
           "文档缺：%s（代码有、文档无，执行者不会去扫）" % missing)

    # 摘要体裁同理：代码里有五类，文档不写就等于没约束
    abs_names = [n for n, _, _ in getattr(mod, "ABSTRACT_GENRE", [])]
    missing = [n for n in abs_names if n not in text]
    record("摘要体裁类别名都在 SKILL.md 列举中", abs_names and not missing,
           "文档缺：%s" % missing)


# ---------- D 共用解析层 ----------
def load_io():
    """manuscript_io.py 在仓库根目录。skill 被单独安装到别处时找不到，
    本组断言跳过：安装位置只镜像 skill 目录，不带根目录的脚本。"""
    for base in (ROOT, HERE):
        p = os.path.join(base, "manuscript_io.py")
        if os.path.exists(p):
            spec = importlib.util.spec_from_file_location("manuscript_io", p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    return None


def part_d():
    import types

    mio = load_io()
    if mio is None:
        print("（跳过解析层断言：未找到 manuscript_io.py）")
        return

    paras = [
        "# 题名",
        "## 摘要",
        "摘要正文一句。",
        "关键词：甲；乙；丙",
        "## Abstract",
        "Abstract body.",
        "Key words: a; b; c",
        "# 1　引言",
        "正文见文献[1]。",
        "# 参考文献",
        "[1] 作者. 题名[J]. 刊名, 1(2): 3-4.",
        "续行文字并入上一条。",
    ]
    st = mio.split_structure(paras, None)
    record("D1 关键词取同段冒号之后",
           st["keywords_cn"] == "关键词：甲；乙；丙",
           "实为 %r" % (st["keywords_cn"],))
    record("D2 正文切到参考文献之前",
           "作者. 题名" not in (st["body"] or ""),
           "正文尾部：%r" % ((st["body"] or "")[-30:],))
    record("D3 摘要取标题下一段而非标题本身",
           st["abstract_cn"] == "摘要正文一句。",
           "实为 %r" % (st["abstract_cn"],))

    items = mio.refs_from_paragraphs(paras, 9)
    record("D4 无编号续行并入上一条",
           len(items) == 1 and "续行" in items[0][1],
           "实为 %r" % (items,))

    fake = types.SimpleNamespace(SECTIONS={"references": ("引用文献",)})
    st2 = mio.split_structure(["# 1　引言", "正文。", "引用文献", "[1] 条目."], fake)
    record("D5 数据层 SECTIONS 覆盖默认章节名",
           st2["index"]["references"] == 2,
           "实为 %r" % (st2["index"],))


# ---------- E 编号类检测的误报边界 ----------
def part_e(mod):
    """B1 的判定对象是标准编号，不能把题名式文献编号也算进去。

    标准编号的序号不超过五位、年后无续写；专利与公开号把年份编进号码，
    连续数字远超五位。若不区分，五位窗口会截出残片再判成「缺发布年」，
    于是正确著录的专利被报成错误，执行者会去改一条本没有错的条目。
    """
    hits = mod.check_standard_status("依据 XX 1234 执行。")
    record("E1 标准号无年份仍报 B1", any(h["code"] == "B1" for h in hits),
           "未报：%s" % hits)

    # 样本中的年份一律用哨兵值 9999，避免公开版出现真实发布年
    ok = mod.check_standard_status("按 XX 1234-9999 执行。")
    record("E2 标准号带年份不报 B1", not ok, "误报：%s" % [h["code"] for h in ok])

    for label, s in (("连写", "见 US99999999999A1 与 WO99999999999A1。"),
                     ("七位", "见 US9999999B2。"),
                     ("斜线", "见 US 9999/9999999 A1。")):
        r = mod.check_standard_status(s)
        record("E3 文献编号（%s）不报 B1" % label,
               not any(h["code"] == "B1" for h in r),
               "误报：%s" % [h["detail"][:40] for h in r])

    r = mod.check_standard_status("按 XX 3100～3102 执行。")
    record("E4 系列编号波浪号写法不报 B1",
           not any(h["code"] == "B1" for h in r), "误报：%s" % r)


def part_g(mod):
    """元话语：交代写作安排、宣告写作决策、代替读者判断、模糊回指。

    这类句子不含禁令词、不是破折号、不构成对偶否定、也不是条目化，前面
    各组检查一组都不会命中。若不单列，作者向读者交代"接下来写什么"的
    句子会一路通过全部核验，而那正是论文体与非论文体的分界。
    """
    hits = [
        ("铺垫", "沿此思路有两条路径值得展开。"),
        ("留待", "该判读方式留待下一章讨论。"),
        ("下面", "下面将给出三项措施。"),
        ("宣告", "本文认为应优先处理这一环节。"),
        ("代替判断", "不难看出，两者互为因果。"),
        ("回指", "如前所述，该量随温度上升。"),
    ]
    for label, s in hits:
        r = mod.check_metadiscourse(s)
        record("G1 元话语（%s）命中 W2" % label,
               any(h["code"] == "W2" for h in r), "未报：%s" % s)

    clean = [
        "该量随温度上升。",
        "两种估法的差别来自参数取值。",
        "第 4 节给出的上限约束了这一换算。",
    ]
    for i, s in enumerate(clean, 1):
        r = mod.check_metadiscourse(s)
        record("G2 直接陈述 %d 不误报" % i, not r,
               "误报：%s" % [h["detail"][:30] for h in r])

    # 「一是…二是…」不带序数词形，旧正则只认「其一」「第一」，整段清单会漏过
    r = mod.check_listy("有三点。一是甲。二是乙。三是丙。四是丁。")
    record("G3 一二式清单化命中 S2",
           any(h["code"] == "S2" for h in r), "未报：%s" % r)

    # 只认句首，嵌在词中的「一是」不算
    r = mod.check_listy("统一是一个过程。单一是他。")
    record("G4 词内一是、单是不误报 S2",
           not any(h["code"] == "S2" for h in r), "误报：%s" % r)


def part_h(mod):
    """摘要体裁：摘要只写问题、方法、结果、结论。

    研究边界与证据等级（未做实验、仅为推断、尚待中试、数据均取自文献）
    属方法学交代，位置在引言；写进摘要等于在读者看到论证之前先替自己
    降级。这类句子通顺、不含禁令词、不是破折号、不构成对偶否定，前面
    各组都不命中，若单列之前无人拦，本轮即由此漏过。
    """
    cases = [
        ("A1", "免责声明", "本文未开展新的实验，结论属机理推断。"),
        ("A2", "来源交代", "数据均取自公开文献与现行标准。"),
        ("A3", "引注标记", "该判据的依据见文献[3]。"),
        ("A4", "图表指引", "三条路线的差别见表 1。"),
    ]
    for code, label, sent in cases:
        body = "## 摘要\n\n%s\n\n关键词：甲；乙\n" % sent
        items = mod.check_abstract_genre(body)
        record("H1 摘要%s命中 %s" % (label, code),
               any(i["code"] == code for i in items), "未报：%s" % sent)

    en = "## Abstract\n\nNo new experiments were performed.\n\nKey words: a\n"
    record("H1 英文摘要免责命中 A5",
           any(i["code"] == "A5" for i in mod.check_abstract_genre(en)),
           "未报英文样本")

    # 摘要范围须止于关键词行：正文里的同一句属正常交代，不得误伤
    body = "## 摘要\n\n甲给出一个判据。\n\n关键词：甲\n\n# 1　引言\n\n本文未开展新的实验。\n"
    record("H2 正文同句话不报 A1",
           not mod.check_abstract_genre(body),
           "误报：%s" % [i["detail"][:30] for i in mod.check_abstract_genre(body)])

    # 对后续工作的展望是摘要的常规内容，不算免责
    body = "## 摘要\n\n甲给出一个判据。进一步研究尚需开展。\n\n关键词：甲\n"
    record("H3 未来工作表述不误报",
           not mod.check_abstract_genre(body),
           "误报：%s" % [i["detail"][:30] for i in mod.check_abstract_genre(body)])

    record("H4 无摘要时不报", not mod.check_abstract_genre("# 1　引言\n\n正文。\n"),
           "误报：%s" % [i["detail"][:30] for i in mod.check_abstract_genre("# 1　引言\n\n正文。\n")])

    # 「摘要：正文」同段写法也要能取出正文
    spans = mod.abstract_spans("摘要：甲给出一个判据。\n\n关键词：甲\n")
    record("H5 同段冒号写法可取正文",
           bool(spans) and "判据" in spans[0][2], "实为 %r" % (spans,))


def main():
    ap = argparse.ArgumentParser(description="规则自检：文档列举与检测器实现是否一致")
    ap.add_argument("--quiet", action="store_true", help="只打印失败项与小结")
    args = ap.parse_args()

    mod = load_audit()
    part_a(mod)
    part_b(mod)
    part_c(mod)
    part_d()
    part_e(mod)
    part_g(mod)
    part_h(mod)

    failed = [(n, note) for n, ok, note in results if not ok]
    if not args.quiet:
        for name, ok, note in results:
            print("%s %s%s" % ("ok  " if ok else "FAIL", name,
                               "" if ok else "  " + note))
    else:
        for name, note in failed:
            print("FAIL %s  %s" % (name, note))

    print("-" * 56)
    print("用例 %d 项，通过 %d 项，失败 %d 项" % (len(results),
                                                len(results) - len(failed),
                                                len(failed)))
    if failed:
        print("自检未通过：文档与检测器已经不一致，或检测器漏掉了列举过的形态。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
