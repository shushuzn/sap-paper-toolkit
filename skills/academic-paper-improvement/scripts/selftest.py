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


def main():
    ap = argparse.ArgumentParser(description="规则自检：文档列举与检测器实现是否一致")
    ap.add_argument("--quiet", action="store_true", help="只打印失败项与小结")
    args = ap.parse_args()

    mod = load_audit()
    part_a(mod)
    part_b(mod)
    part_c(mod)

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
