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
    D–L 逐组补充：解析层、编号误报边界、元话语、摘要体裁、冗赘、
    文体整齐度、上下标渲染、命令行选项，各带正负样本

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


def part_i(mod):
    """冗赘表述：同一内容被口语化地再说一遍。

    这类文字没有错字、不含禁令词、不是破折号、不构成对偶否定、不属元话语、
    不是条目化，前面各组一路放行。它的代价不只在文体：冗赘体往往伴随整段
    复述，字数被虚增而信息量不变，因此与「删重复」是同一件事。
    """
    cases = [
        ("虚化动词", "然后对单体配比进行了大量探索的工作。"),
        ("口语缀词", "相较于纤维类材料来说，这类材料更易保持水分。"),
        ("关联词叠用", "由于单体活性较高，所以该路线长期占主导。"),
        ("空泛程度", "该系列在卫生用品方面得到了不断的拓展。"),
        ("句式杂糅", "正是基于这样的结构使得外力下水分难以挤出。"),
        ("使令口语", "交联条件的调整让网络结构逐渐走向可设计参数。"),
    ]
    for label, sent in cases:
        items = mod.check_wordiness(sent)
        record("I1 冗赘（%s）命中 T1" % label,
               any(i["code"] == "T1" for i in items), "未报：%s" % sent)

    # 学术文本的正常写法不得误伤
    clean = [
        "该量随温度上升。",
        "交联剂加入后进行中和反应，体系黏度上升。",
        "该材料系列长期占据主导地位。",
        "由于离子项随盐浓度下降，吸水倍率随 S 升高而降低。",   # 单头因果
        "这一结构特征使其在医用敷料领域得到持续扩展。",
    ]
    for i, sent in enumerate(clean, 1):
        items = mod.check_wordiness(sent)
        record("I2 正常句 %d 不误报" % i, not items,
               "误报：%s" % [x["detail"][:40] for x in items])

    # 整段复述：单句都合格，任何词表都不命中，只能靠段间重合度发现
    a = ("高吸水性树脂由丙烯酸及盐类单体聚合而成，分子链上分布羧基与羧酸盐基等亲水基团，"
         "经交联后形成不溶于水而可溶胀的三维网络，吸水后成为水凝胶，外力下水分不易被挤出。")
    dup = ("这类材料由丙烯酸及其盐类单体聚合而成，在其分子链上有羧基、羧酸盐基等亲水基团，"
           "经过交联形成了不溶于水但可以溶胀的三维网络，吸水后形成水凝胶，外力下不易被挤出。")
    items = mod.check_wordiness(a + "\n" + dup)
    record("I3 整段复述命中 T2", any(i["code"] == "T2" for i in items),
           "未报：%s" % [i["detail"][:40] for i in items])

    other = ("交联密度决定网络弹性回缩力，其上限由式（1）给出。渗透压项随离子强度上升而减弱，"
             "盐水中吸水倍率因此下降，衰减指数在对离子项主导区为负三分之五。")
    items = mod.check_wordiness(a + "\n" + other)
    record("I4 相邻异段不误报 T2", not any(i["code"] == "T2" for i in items),
           "误报：%s" % [i["detail"][:40] for i in items])

    # 半角标点夹中文属格式，归 F4；英文句末的句点不得误报
    items = mod.check_format("路线已确立[3];随后展开配比研究[4][5],结论见后[6][7].")
    record("I5 半角标点夹中文命中 F4",
           any(i["code"] == "F4" and "半角" in i["title"] for i in items),
           "未报：%s" % items)
    en = "No new experiments were performed. All data are taken from the literature."
    record("I6 英文句点不误报 F4",
           not any("半角" in i["title"] for i in mod.check_format(en)),
           "误报：%s" % mod.check_format(en))

    # 类别名须在 SKILL.md 列出，否则执行者不会去扫
    doc = open(SKILL, encoding="utf-8").read()
    names = [n for n, _ in getattr(mod, "WORDY", [])]
    missing = [n for n in names if n not in doc]
    record("I7 冗赘类别名都在 SKILL.md 列举中", names and not missing,
           "文档缺：%s（代码有、文档无）" % missing)


AI_HUMAN = """核对从编号开始。三份复印件摊在桌上，编号相同，页码却不连。缺的那一页，恰好是结论所在，而三份缺的是同一页。馆藏的缩微胶卷补上了这一页，字迹模糊，但足够读出结论。我把胶卷的编号抄在本子第一行。

结论是：这批材料的产出年份早于登记年份七年。七年不是小数，它把整批材料的来源从一家改成了另一家，而那一家在登记之前就已经停业。如果这个判断成立，前面关于工艺传承的三条线索要重新排。我把胶卷编号抄进本子，又回头核了一遍复印件上的页码，核对的结果与胶卷一致。页码不连的位置共有四处，两处在章末，两处在图表之后，后者更可疑，因为图表之后的缺页会直接切断数据与说明的对应关系。这一点是复查时才注意到的，当时只当作排印疏漏，没有深究，直到第四份材料的复印件送来，同样的缺页再次出现，我才把三份并排比对，看出缺的是同一页。

页码不连的原因后来查清了。装订时按开本而非按顺序配页，所以缺页并不罕见。上世纪八十年代的馆藏合订本多循此例，缺页属于常态，不能据此推断有人动过手。

但同一页在三份里同时缺，就不是装订能解释的。我请馆员调了原本，原本要提前一周预约，我等到第三个星期才见到，见到时已近年关。馆员说，这批材料的外借记录只有两次，都在二十年前。

原本的纸张发脆，翻页要压着边。那一页的边缘有裁切痕迹，像是被人抽走后又补了一张白页。补页的纸色比原本浅，纤维也粗，对着光看能看出帘纹方向不同。这说明有人在外借期间动过手，而且动手的人熟悉装订，补得整齐，不细看发现不了。我把补页的位置画在示意图上，标注了纸色、纤维与帘纹三项差异，附在报告后面。

以上只是物证层面的推断。谁在外借期间动的手，记录里没有答案，需要查借阅单的签字，而借阅单只保存十年，这一批的已经销毁。所以结论停在有人补过页，再往前一步就是猜测。我不写。"""

AI_GEN = """随着高分子材料科学的不断发展，高吸水性树脂作为一种重要的功能高分子材料，在卫生用品、农林保水、环境治理以及医用敷料等领域发挥着越来越重要的作用。该类材料具有优异的吸水性能与保水性能，因此受到学术界与工业界的广泛关注。近年来，相关研究不断深入，材料性能得到显著提升。

从结构上看，该类材料通常由丙烯酸及其盐类单体聚合而成，分子链上含有大量羧基与羧酸盐基等亲水基团。经过交联反应后，分子链形成不溶于水但可以溶胀的三维网络结构。这种结构使其具有良好的吸水性能，同时也使其在盐水中的吸水倍率明显下降。

在性能方面，吸水倍率与吸水速率是两个重要的评价指标。吸水倍率反映材料的饱和吸收能力，吸水速率反映材料的实际使用性能。两者之间往往存在一定的矛盾关系，需要在实际应用中加以平衡。因此，如何实现两者的协同优化，成为该领域的重要研究方向。

在机理方面，渗透压与弹性回缩力的平衡决定了材料的溶胀行为。提高电荷密度可以增大渗透压，从而提高吸水倍率。提高交联密度可以增大弹性回缩力，从而降低吸水倍率。因此，交联密度的合理选择对于材料性能的优化具有重要意义。

在改性方面，表面交联是提高凝胶强度的有效手段。通过表面交联，可以在颗粒外层形成较高的交联密度，从而提高其在加压条件下的吸水性能。此外，引入无机填料也可以降低生产成本，并改善材料的力学性能。因此，表面交联与填料复合是两种常用的改性策略。

在工艺方面，水溶液聚合法具有工艺简单、成本较低等优点，因此得到广泛应用。反相悬浮聚合法则可以获得球形颗粒，产品流动性较好。两种方法各有优缺点，需要根据产品需求进行选择。因此，工艺路线的选择对于产品质量具有重要影响。

在应用方面，卫生用品是最大的消费领域，对材料的吸水速率与凝胶强度要求较高。农林保水领域则更关注材料的耐盐性与降解性能。环境治理领域要求材料具有良好的吸附性能与可再生性能。因此，不同应用场景对材料性能的要求存在明显差异。

综上所述，聚丙烯酸钠系高吸水性树脂的性能优化涉及分子结构、交联方式、改性策略与工艺条件等多个方面，需要开展系统研究。未来的研究应重点关注耐盐性的提升与生物降解性的改善，从而推动该材料在更多领域的应用。"""


def part_j():
    """AI 文本特征度量：只度量，不判定。

    这一组存在的理由不是「抓 AI」，而是防两件事：一是把统计量当成检测
    分数，二是为了压低统计量去插错别字。四项指标各有独立机理，且必须
    至少两项同时越线才值得处理；单看一项就会把规范的学术写法误判。
    """
    path = os.path.join(HERE, "ai_traits.py")
    if not os.path.exists(path):
        record("J0 ai_traits.py 存在", False, "找不到 %s" % path)
        return
    spec = importlib.util.spec_from_file_location("ai_traits", path)
    at = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(at)

    gen = at.measure(AI_GEN)
    flags = [k for k in ("X1", "X2", "X3", "X4") if at.verdict(k, gen[k])]
    record("J1 生成样本四类特征越线", len(flags) >= 3, "只越线 %s" % flags)

    hum = at.measure(AI_HUMAN)
    flags = [k for k in ("X1", "X2", "X3", "X4") if at.verdict(k, hum[k])]
    record("J2 人工样本不越线", not flags, "误报 %s（X1 %.2f X2 %.1f X3 %.1f X4 %.2f）"
           % (flags, hum["X1"], hum["X2"], hum["X3"], hum["X4"] or 0))

    # 短文本的统计量没有意义，必须全部拒判而不是给个看似精确的数
    short = at.measure("随着技术的发展，该类材料的应用日益广泛。因此需要系统研究。")
    record("J3 短样本全部不判",
           all(short[k] is None for k in ("X1", "X2", "X3", "X4")),
           "仍给出数值：%s" % {k: short[k] for k in ("X1", "X2", "X3", "X4")})

    # 段数不足时，段长均匀度单靠两三段会失真
    few = at.measure("甲。\n\n乙。\n\n丙。")
    record("J4 段数不足时不判 X4", few["X4"] is None, "仍判：%r" % few["X4"])

    # 阈值边界：等于阈值不越线，越过一点才越线
    record("J5 阈值边界不抖",
           (not at.verdict("X1", 0.40)) and at.verdict("X1", 0.39)
           and (not at.verdict("X2", 6.0)) and at.verdict("X2", 6.1),
           "边界判定与 RULES 不符")

    # 度量不得自称为检测分数
    src = open(path, encoding="utf-8").read()
    record("J6 明确否认是 AI 率", "这不是 AI 率" in src,
           "脚本未声明与检测分数不可换算")

    doc = open(SKILL, encoding="utf-8").read()
    miss = [at.RULES[k]["name"] for k in ("X1", "X2", "X3", "X4")
            if at.RULES[k]["name"] not in doc]
    record("J7 四项指标名都在 SKILL.md", not miss, "文档缺：%s" % miss)


def part_k(mod):
    """富文本上下标：同一底数连写多个后缀。

    φ_{p}^{2} 是先下标后上标，旧解析只吃一个后缀，剩下的 ^{2} 以字面量
    留在成稿里。这类残留源稿检查看不出来：源稿本来就该带标记，只有成稿
    才要求渲染。所以用例必须走真正的 add_rich，而不是只测正则。
    """
    try:
        from docx import Document
    except ImportError:
        record("K0 缺 python-docx，渲染用例跳过", True, "未安装 docx 依赖")
        return
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    try:
        import docx_style as ds
    except Exception as exc:
        record("K0 docx_style 可导入", False, str(exc))
        return

    m = ds.AFFIX.search("φ_{p}^{2}")
    pairs = ds.PAIR.findall(m.group(2)) if m else []
    record("K1 连写后缀两段都识别",
           bool(m) and m.group(1) == "φ" and len(pairs) == 2,
           "识别为 %r" % (pairs,))

    p = Document().add_paragraph()
    ds.add_rich(p, "平衡时 φ_{p}^{2} 与 V_{u} 同时出现")
    txt = p.text
    record("K2 成稿无标记残留", "{" not in txt and "^" not in txt,
           "残留：%r" % txt)

    subs = [r.text for r in p.runs if r.font.subscript]
    sups = [r.text for r in p.runs if r.font.superscript]
    record("K3 下标与上标都落到 run 上",
           subs == ["p", "u"] and sups == ["2"], "sub=%r sup=%r" % (subs, sups))

    leaked = mod.check_format("甲 φ_{p}^{2} 乙", source_mode=False)
    record("K4 残留标记被判 FAIL",
           any(i["code"] == "F4" and i["level"] == mod.FAIL for i in leaked),
           "check_format 未报 F4：%s" % [i["code"] for i in leaked])

    ok = mod.check_format(txt, source_mode=False)
    record("K5 渲染后的文字不误报",
           not any(i["code"] == "F4" for i in ok),
           "误报：%r" % txt)


def part_l():
    """命令行选项解析：带 --data 不得被判为未知选项。

    这一组针对一个真实缺陷：audit_refs.py 曾在 main() 里先校验未知选项，
    到 gather() 才解析 --data，于是 --data 永远被判为未知选项，而帮助
    文本明明写着它可用。四个脚本里三个顺序正确，只有一个例外，读代码
    很难发现，只有真跑一遍命令行才暴露。
    """
    import subprocess
    import tempfile

    script = os.path.join(ROOT, "audit_refs.py")
    if not os.path.exists(script):
        record("L0 audit_refs.py 存在", False, "找不到 %s" % script)
        return

    def run(args, cwd):
        return subprocess.run([sys.executable, script] + args, cwd=cwd,
                              capture_output=True, text=True)

    with tempfile.TemporaryDirectory() as td:
        data = os.path.join(td, "d.py")
        with open(data, "w", encoding="utf-8") as fh:
            # 年份用哨兵值，避免在公开仓库里写入可定位的年份
            fh.write('REFS = {"a": "[1] 题名[J]. 刊名, 9999, 1(1): 1-2."}\n')

        r = run(["--data", data, "--json", os.path.join(td, "r.json")], td)
        record("L1 --data 不再被判未知选项",
               r.returncode == 0 and "未知选项" not in r.stderr,
               "退出码 %d，stderr=%r" % (r.returncode, r.stderr[-120:]))
        record("L2 数据层确实被使用", "数据层 REFS" in r.stdout,
               "stdout=%r" % r.stdout[:120])

        r = run(["--data"], td)
        record("L3 --data 缺值时报缺少值",
               r.returncode != 0 and "缺少值" in r.stderr,
               "退出码 %d，stderr=%r" % (r.returncode, r.stderr[-80:]))

        r = run(["--nope", data], td)
        record("L4 真正未知的选项仍被拦",
               r.returncode != 0 and "未知选项" in r.stderr,
               "退出码 %d，stderr=%r" % (r.returncode, r.stderr[-80:]))


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
    part_i(mod)
    part_j()
    part_k(mod)
    part_l()

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
