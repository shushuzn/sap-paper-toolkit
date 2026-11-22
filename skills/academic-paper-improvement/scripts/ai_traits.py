#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 文本特征度量：四个可解释的统计量，用于自查文体是否过于整齐。

不做什么
    不给出「AI 率」。市面上的检测器是各自训练的深度模型，其分数不可
    复现，也不可换算：知网的「知识增强」、朱雀的多模型集成、GPTZero
    已改用深度学习架构而不再以困惑度与突发性为基础，均无公开的特征
    权重。任何声称「用几个统计量算出某平台 AI 率」的说法都不成立。本
    脚本只度量四个维度，供作者判断哪一段过于平整，不产出分数，也不
    预测检测结果。

做什么
    四项指标，各自对应一个公开讨论中反复出现的观察：
      X1 句长变异系数   机器写的句子长度趋于一致，人写会长短交错
      X2 句首连接词密度 段首「此外」「因此」「同时」的堆叠
      X3 名词化后缀密度 「性」「化」结尾的抽象名词
      X4 段长均匀度     各段字数是否几乎相同
    前三项与第四项合起来若同时越线，说明文体整齐到不自然，可对照
    修改；单看一项不作判断。

参考区间的来源
    公开讨论中的数字（例如「AI 每千字 8 至 15 个连接词、人写 2 至 6
    个」）多为二手转述，无原始实验，只能当方向。本项目另用对照实测
    校准：一篇经人工逐句改定的学术稿与数段生成文本相比，句长 CV 为
    0.61 与 0.12 至 0.36，句首连接词为 0.8 与 8.4 至 10.5 每千字，名词化
    后缀为 14.4 与 28.1 至 33.7 每千字，段长 CV 为 0.45 与 0.06 至 0.08。
    阈值取两者之间，宁松勿紧：误报一条，作者会去改本来没问题的句子。
    样本量不足 600 汉字或不足 15 句时不出结论，短文本的这些统计量没有
    意义。

用法
    python ai_traits.py <manuscript.md|.docx> [--json out.json]
    退出码恒为 0：这是度量，不是判定。
"""
import argparse
import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_manuscript as am  # noqa: E402  复用解析与字数口径，不另写一份

SENT_SPLIT = re.compile(r"[。！？；\n]")
LEAD_CONN = re.compile(r"^(而|但|因此|然而|此外|同时|从而|首先|其次|最后|综上|总之"
                       r"|进而|并且|而且|换言之|值得注意的是|由此可见|另外)")
NOMINAL = re.compile(r"[\u4e00-\u9fa5](性|化)")

# 阈值：(下界, 上界, 越线方向, 说明)。None 表示该侧不判。
RULES = {
    "X1": dict(name="句长变异系数", th=0.40, side="low",
               ref="改定稿 0.5–0.65／生成 0.12–0.36",
               why="句子长度趋于一致，缺少长短交错"),
    "X2": dict(name="句首连接词密度", th=6.0, side="high", unit="每千字",
               ref="改定稿 ≤2／生成 6–12",
               why="段首「此外」「因此」「同时」堆叠"),
    "X3": dict(name="名词化后缀密度", th=28.0, side="high", unit="每千字",
               ref="改定稿 ≤18／生成 ≥28",
               why="「性」「化」结尾的抽象名词过多"),
    "X4": dict(name="段长均匀度", th=0.15, side="low",
               ref="改定稿 ≥0.3／生成 ≤0.1",
               why="各段字数几乎相同，缺少详略"),
}


def sentences(text):
    return [s.strip() for s in SENT_SPLIT.split(text) if am.hanzi(s) >= 2]


def measure(text):
    """返回四项的实测值；样本不足的项给 None。"""
    body, _ = am.split_body_refs(text)
    sents = sentences(body)
    lengths = [am.hanzi(s) for s in sents]
    paras = [p for p in am.para_list(body) if am.hanzi(p) >= 40]
    n = am.hanzi(body)

    out = dict(chars=n, sent_count=len(sents), para_count=len(paras))

    if len(lengths) >= 15:
        mu = statistics.mean(lengths)
        out["X1"] = statistics.pstdev(lengths) / mu if mu else None
        out["_sent_mean"] = mu
        out["_sent_min"], out["_sent_max"] = min(lengths), max(lengths)
    else:
        out["X1"] = None

    if n >= 600:
        lead = sum(1 for s in sents if LEAD_CONN.match(s))
        out["X2"] = lead / n * 1000
        out["X3"] = len(NOMINAL.findall(body)) / n * 1000
    else:
        out["X2"] = out["X3"] = None

    if len(paras) >= 5:
        pl = [am.hanzi(p) for p in paras]
        out["X4"] = statistics.pstdev(pl) / statistics.mean(pl)
    else:
        out["X4"] = None
    return out


def verdict(key, val):
    """返回 True 表示越线（偏向生成文本一侧）。"""
    if val is None:
        return False
    r = RULES[key]
    return val < r["th"] if r["side"] == "low" else val > r["th"]


def report(path, m):
    print(f"# AI 文本特征度量：{os.path.basename(path)}")
    print()
    print("这不是 AI 率。四项统计量各自对应一种「写得过于整齐」的表现，")
    print("与任何厂商的检测分数不可换算；单看一项不作判断。")
    print()
    print(f"样本：正文 {m['chars']} 汉字，{m['sent_count']} 句，{m['para_count']} 段（≥40 字）")
    print()
    print("| 项 | 指标 | 实测 | 参考（人工改定／生成文本） | 判断 |")
    print("|---|---|---|---|---|")
    flags = 0
    for key in ("X1", "X2", "X3", "X4"):
        r = RULES[key]
        v = m.get(key)
        show = "样本不足" if v is None else (
            f"{v:.2f}" if key in ("X1", "X4") else f"{v:.1f} {r['unit']}")
        if v is None:
            mark = "不判"
        elif verdict(key, v):
            mark = f"越线（{r['why']}）"
            flags += 1
        else:
            mark = "正常"
        print(f"| {key} | {r['name']} | {show} | {r['ref']} | {mark} |")

    print()
    if flags >= 2:
        print(f"结论：{flags} 项同时偏向生成文本一侧。这不是违规，也不是检测结论，")
        print("      说明文体过于整齐。可行的改法是按内容重新分句：把一处需要强调的")
        print("      判断压成短句，把一处因果展开成长句；段首连接词删到语义自明；")
        print("      抽象名词还原为具体动作。**不要**为了拉低指标而插错别字、随机断句，")
        print("      那是欺骗检测，且会真的损害可读性。")
    elif flags == 1:
        print("结论：1 项偏向生成文本一侧，属可解释的写法差异，通常不必单独处理。")
    else:
        print("结论：四项均未越线。")
    print()
    print("注意：不越线不等于人类所写，越线也不等于机器所写。学术文本、规范表述、")
    print("      方法步骤天然接近这些特征，公开资料中作者自述被误判的案例多集中于此。")
    print("      本度量用于定位需要人工复核的段落，不能作为作者身份的依据。")
    return flags


def main():
    ap = argparse.ArgumentParser(description="AI 文本特征的统计度量（非 AI 率）")
    ap.add_argument("path")
    ap.add_argument("--json")
    args = ap.parse_args()

    if not os.path.exists(args.path):
        sys.exit(f"文件不存在：{args.path}")

    m = measure(am.extract(args.path))
    flags = report(args.path, m)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(dict(path=args.path, metrics=m, flags=flags), f,
                      ensure_ascii=False, indent=2)
        print(f"\nJSON 已写入 {args.json}")
    sys.exit(0)


if __name__ == "__main__":
    main()
