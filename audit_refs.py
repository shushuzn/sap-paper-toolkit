# -*- coding: utf-8 -*-
"""按顺序编码制审计参考文献条目：类型标识、作者段、卷期页、标点、编号连续性。

只读，不改稿件。用法：

    python audit_refs.py [稿件.md|稿件.docx] [--data 数据层.py] [--json 输出.json]

条目来源按以下顺序确定：
1. 数据层的 REFS（有数据层时优先，键名即条目名）；
2. 稿件的参考文献段（无数据层时，按"编号 + 条目"逐行拆）。

本脚本判定的是条目写法，不是内容真伪。作者、刊名、年卷期页是否与原文一致，
须回查出版方页面或文献数据库，脚本无法代劳。
"""
import json
import re
import sys

import manuscript_io as mio

FAIL, WARN = "FAIL", "WARN"

# 文献类型标识：常见九类
TYPE_MARK = re.compile(r"\[(J|M|S|D|C|N|R|P|Z|A|G)\]")
# 年, 卷(期): 页
YEAR_VOL = re.compile(r",\s*(\d{4})\s*,\s*([\dA-Za-z\-]+)\s*(?:\((\d+(?:\s*-\s*\d+)?)\))?\s*:\s*([\d\-–]+)")
# DOI 后缀：10.<注册号>/<其余>
DOI = re.compile(r"10\.\d{4,9}/[^\s，。；]+")
# 规范类条目：大写代号 + 可选分部 + 序号 + 半字线 + 发布年
STD_NUM = re.compile(r"[A-Z]{2,4}(?:/[A-Z]{1,2})?\s*\d{1,6}")
CJK = re.compile(r"[\u4e00-\u9fa5]")


def audit(name, text):
    """审计单条，返回 (issues, warns)。"""
    issues, warns = [], []
    s = text.strip()

    m = TYPE_MARK.search(s)
    if not m:
        issues.append("缺文献类型标识（如 [J]、[M]）")
        typ = None
    else:
        typ = m.group(1)

    if not s.endswith((".", "。", "．")):
        issues.append("条目未以句点结尾")

    # 作者段：类型标识之前、第一个句点之前的部分
    head = re.split(r"\[[A-Z]\]", s)[0]
    head = head.split(". ")[0] if ". " in head else head
    cjk_item = bool(CJK.search(head))
    if "et al" in head:
        if cjk_item:
            warns.append("中文条目用了 et al.，中文著录通常用「等」")
        n = len([x for x in head.split("et al")[0].split(",") if x.strip()])
        if n and n != 3:
            warns.append("et al. 前为 %d 位作者；常见惯例是列前 3 位，"
                         "须与目标稿件的著录要求核对" % n)
    if "等" in head and not cjk_item:
        warns.append("非中文条目用了「等」，英文著录通常用 et al.")

    # 全角标点混入西文条目
    if typ in ("J", "M", "C", "D") and not CJK.search(s):
        if re.search(r"[，。（）；：]", s):
            issues.append("西文条目中出现全角标点")

    if typ == "J":
        if not YEAR_VOL.search(s):
            if DOI.search(s):
                warns.append("缺「年, 卷(期): 起止页」，以 DOI 替代；"
                             "著录规则允许，但期刊条目宜补全")
            else:
                issues.append("缺「年, 卷(期): 起止页」")
        if not re.search(r"\[J\]\.\s*\S", s):
            issues.append("[J] 后缺刊名")

    if typ == "M":
        if not re.search(r"\[M\]\.\s*\S", s):
            issues.append("[M] 后缺出版地或出版者")

    if typ == "S":
        if re.search(STD_NUM.pattern + r"\s*[—–]\s*\d{2,4}", s):
            issues.append("编号中的年份连接应为半字线「-」，不是破折号")
        elif not re.search(STD_NUM.pattern + r"\s*-\s*\d{2,4}", s):
            issues.append("规范类条目缺「代号 + 序号 + 半字线 + 发布年」；"
                          "编号与年份须向原件核对，不得沿用二手转述")

    return issues, warns


def gather(argv, data_path=None):
    """确定稿件与数据层，返回 (条目列表, 来源说明)。

    data_path 由 main() 解析后传入。选项解析只在一处发生，否则"先校验
    未知选项、后解析已知选项"会让带 --data 的调用被判为未知选项。
    """
    data = mio.load_data(mio.resolve_data(data_path))
    if data is not None:
        refs = mio.refs_from_data(data)
        if refs:
            return refs, "数据层 REFS"

    src = mio.resolve_source(argv)
    paras = mio.read_paragraphs(src)
    st = mio.split_structure(paras, data)
    i = st["index"]["references"]
    if i < 0:
        sys.exit("既无数据层 REFS，稿件里也没有参考文献段：\n"
                 "  稿件：%s\n"
                 "  数据层：%s\n"
                 "用 --data 指定数据层，或在稿件里写出参考文献段。" %
                 (src, mio.resolve_data(data_path) or "未找到"))
    return mio.refs_from_paragraphs(paras, i), "稿件参考文献段"


def main(argv):
    if "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0
    json_out, argv = mio.pop_option(argv, "--json", "audit_refs.json")
    data_path, argv = mio.pop_option(argv, "--data")
    bad = [a for a in argv if a.startswith("-")]
    if bad:
        sys.exit("未知选项：%s（用 --help 看用法）" % " ".join(bad))

    refs, origin = gather(argv, data_path)
    if not refs:
        sys.exit("没有可审计的条目（来源：%s）。" % origin)
    print("条目来源：%s，共 %d 条\n" % (origin, len(refs)))

    rows = []
    for num, text in refs:
        iss, wr = audit(str(num), text)
        st = FAIL if iss else (WARN if wr else "PASS")
        rows.append({"no": num, "status": st, "issues": iss,
                     "warns": wr, "text": text})
        brief = "; ".join(iss + wr) or "OK"
        print("[%-4s] %-3s %s" % (st, num, brief))

    # 编号连续性（仅在有编号时判定）
    nums = [r["no"] for r in rows if isinstance(r["no"], int)]
    if nums:
        holes = sorted(set(range(min(nums), max(nums) + 1)) - set(nums))
        if holes:
            print("\n[%s] 编号不连续：缺 %s" % (WARN, holes))
        dups = sorted({n for n in nums if nums.count(n) > 1})
        if dups:
            print("[%s] 编号重复：%s" % (FAIL, dups))

    f = sum(1 for r in rows if r["status"] == FAIL)
    w = sum(1 for r in rows if r["status"] == WARN)
    print("\n合计 %d 条：FAIL %d，WARN %d，PASS %d"
          % (len(rows), f, w, len(rows) - f - w))

    with open(json_out, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=1)
    print("明细已写入：%s" % json_out)
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
