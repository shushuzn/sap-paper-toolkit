# -*- coding: utf-8 -*-
"""交叉审核：按题名向 Crossref 回查每条文献的元数据，与条目原文逐字段比对。

用法：

    python xcheck_refs.py [稿件.md|稿件.docx] [--data 数据层.py]
                          [--cache 缓存.json] [--report 报告.json]

条目来源同 audit_refs.py：有数据层用 REFS，否则取稿件的参考文献段。
规范类与其他非期刊条目不在 Crossref 覆盖面内，直接跳过并在汇总里计数，
不得据此判为通过。

网络请求会带邮箱标识以进入礼貌池（设环境变量 CROSSREF_MAILTO）；
未设也能用，但并发高时更容易被限流。回查结果只能证明元数据是否一致，
不能证明该文献确实支持正文的论断。
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import manuscript_io as mio

UA_BASE = "ref-xcheck/2.0"
MIN_SCORE = 0.60
RETRY = 3
TIMEOUT = 45

REF_PARSE = re.compile(
    r"^(?P<au>[^.]+)\.\s*(?P<title>.+?)\[(?P<ty>[A-Z])\]\.\s*(?P<rest>.+)$")
CJK = re.compile(r"[\u4e00-\u9fa5]")


def norm(s):
    return re.sub(r"[^a-z0-9\u4e00-\u9fa5]", "", (s or "").lower())


class Crosscheck:
    def __init__(self, cache_path, mailto=""):
        self.path = cache_path
        self.mailto = mailto
        self.ua = UA_BASE + ((" (mailto:%s)" % mailto) if mailto else "")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, encoding="utf-8") as fh:
                    self.cache = json.load(fh)
            except (json.JSONDecodeError, OSError):
                print("缓存无法解析，按空缓存重来：%s" % cache_path)
                self.cache = {}
        else:
            self.cache = {}

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(self.cache, fh, ensure_ascii=False)
        except OSError as e:
            print("缓存写入失败（不影响本次结果）：%s" % e)

    def fetch(self, title):
        key = norm(title)[:120]
        if key in self.cache:
            return self.cache[key]
        params = {
            "query.bibliographic": title,
            "rows": 3,
            "select": "title,author,container-title,issued,volume,issue,"
                      "page,DOI,type,article-number",
        }
        if self.mailto:
            params["mailto"] = self.mailto
        url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        for attempt in range(RETRY):
            try:
                with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                    items = json.load(r)["message"]["items"]
                self.cache[key] = items
                self.save()
                return items
            except urllib.error.HTTPError as e:
                if e.code in (429, 503):
                    time.sleep(5 * (attempt + 1))
                    continue
                print("   HTTP %s，停止重试" % e.code)
                return None
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
                print("   第 %d 次请求失败：%s" % (attempt + 1, e))
                time.sleep(5 * (attempt + 1))
        return None


def pick(items, title):
    best, score = None, 0.0
    tset = set(norm(title))
    for it in items:
        t = (it.get("title") or [""])[0]
        if not t:
            continue
        inter = len(tset & set(norm(t)))
        sc = inter / max(1, len(tset))
        if norm(t)[:60] == norm(title)[:60]:
            sc = 1.0
        if sc > score:
            best, score = it, sc
    return best, score


def compare(text, item):
    """返回字段差异列表，空列表表示一致。"""
    rest = text
    year = re.search(r"(\d{4})", rest)
    year = year.group(1) if year else ""
    vol = re.search(r"\d{4},\s*([\d]+)", rest)
    vol = vol.group(1) if vol else ""
    iss = re.search(r"\(([\d\-]+)\)", rest)
    iss = iss.group(1) if iss else ""
    pg = re.search(r":\s*([\d\-–]+)\s*[\.。]?$", rest)
    pg = pg.group(1) if pg else ""

    y = item.get("issued", {}).get("date-parts", [[None]])[0]
    y = str(y[0]) if y and y[0] else ""
    v = str(item.get("volume") or "")
    i = str(item.get("issue") or "")
    p = str(item.get("page") or item.get("article-number") or "")

    diff = []
    if y and year and y != year:
        diff.append("年 %s→%s" % (year, y))
    if v and vol and v != vol:
        diff.append("卷 %s→%s" % (vol, v))
    if i and iss and i != iss:
        diff.append("期 %s→%s" % (iss, i))
    if p and pg:
        a = re.sub(r"[-–\s]", "", p)
        b = re.sub(r"[-–\s]", "", pg)
        if a and b and a != b:
            diff.append("页 %s→%s" % (pg, p))
    return diff


def main(argv):
    if "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0
    data_path, argv = mio.pop_option(argv, "--data")
    cache, argv = mio.pop_option(argv, "--cache", "xcheck_cache.json")
    report_path, argv = mio.pop_option(argv, "--report", "xcheck_report.json")
    bad = [a for a in argv if a.startswith("-")]
    if bad:
        sys.exit("未知选项：%s（用 --help 看用法）" % " ".join(bad))

    data = mio.load_data(mio.resolve_data(data_path))
    refs = mio.refs_from_data(data) if data is not None else []
    origin = "数据层 REFS"
    if not refs:
        src = mio.resolve_source(argv)
        paras = mio.read_paragraphs(src)
        st = mio.split_structure(paras, data)
        i = st["index"]["references"]
        if i < 0:
            sys.exit("既无数据层 REFS，稿件里也没有参考文献段，无法回查。")
        refs = mio.refs_from_paragraphs(paras, i)
        origin = "稿件参考文献段"
    if not refs:
        sys.exit("没有可回查的条目。")

    mailto = os.environ.get("CROSSREF_MAILTO", "")
    if not mailto:
        print("提示：未设 CROSSREF_MAILTO，未进礼貌池，频繁请求可能被限流。\n")
    print("条目来源：%s，共 %d 条\n" % (origin, len(refs)))

    cc = Crosscheck(cache, mailto)
    report = []
    for num, text in refs:
        m = REF_PARSE.match(text.strip())
        if not m:
            print("[PARSE] %-3s 拆不出作者/题名/类型：%s" % (num, text[:50]))
            report.append((num, "PARSE-FAIL", text[:60]))
            continue
        typ = m.group("ty")
        if typ not in ("J", "M", "C"):
            print("[SKIP ] %-3s 类型 [%s] 不在 Crossref 覆盖面内，须另行核对"
                  % (num, typ))
            report.append((num, "SKIP-TYPE", typ))
            continue

        title = m.group("title")
        if CJK.search(title):
            print("[SKIP ] %-3s 题名含中文，Crossref 以英文题名为主，回查不可靠"
                  % num)
            report.append((num, "SKIP-LANG", title[:40]))
            continue

        items = cc.fetch(title)
        if items is None:
            print("[ERR  ] %-3s 请求失败，结论未知" % num)
            report.append((num, "ERR", ""))
            continue

        best, score = pick(items, title)
        if not best or score < MIN_SCORE:
            near = (best.get("title") or [""])[0][:70] if best else ""
            print("[MISS ] %-3s 未匹配（score=%.2f）%s" % (num, score, near))
            report.append((num, "MISS", "score=%.2f" % score))
            continue

        diff = compare(text, best)
        ct = (best.get("container-title") or [""])[0]
        if diff:
            print("[DIFF ] %-3s %s" % (num, "; ".join(diff)))
            print("        刊名 %s | DOI %s" % (ct or "—", best.get("DOI") or "—"))
            report.append((num, "DIFF", "; ".join(diff)))
        else:
            print("[ OK  ] %-3s %s %s" % (num, ct[:40] or "—", best.get("DOI") or ""))
            report.append((num, "OK", ""))
        time.sleep(1.2)

    cc.save()
    tally = {}
    for _, st, _ in report:
        tally[st] = tally.get(st, 0) + 1
    print("\n汇总：%s" % tally)
    skipped = sum(v for k, v in tally.items() if k.startswith("SKIP"))
    if skipped:
        print("其中 %d 条未做回查，不得计入通过。" % skipped)

    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    print("明细已写入：%s" % report_path)
    return 1 if tally.get("DIFF") else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
