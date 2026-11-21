# -*- coding: utf-8 -*-
"""交叉审核：按题名向 Crossref 回查每条文献的元数据，逐字段比对。"""
import json, re, sys, time, urllib.parse, urllib.request, importlib.util, os

try:
    spec = importlib.util.spec_from_file_location("pd", "paper_data.py")
    pd = importlib.util.module_from_spec(spec); spec.loader.exec_module(pd)
except FileNotFoundError:
    sys.exit("找不到 paper_data.py：先执行 cp paper_data.example.py paper_data.py 并填入文献表")
REFS = pd.REFS

CACHE = "xcheck_cache.json"
MAILTO = os.environ.get("CROSSREF_MAILTO", "")
UA = "XCheck/1.0" + (f" (mailto:{MAILTO})" if MAILTO else "")
cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}

def fetch(title, authors_hint=""):
    key = title[:120]
    if key in cache: return cache[key]
    q = title
    params = {
        "query.bibliographic": q, "rows": 3,
        "select": "title,author,container-title,issued,volume,issue,page,DOI,type,article-number"}
    if MAILTO:
        params["mailto"] = MAILTO
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for a in range(4):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                d = json.load(r)
            items = d["message"]["items"]
            cache[key] = items; json.dump(cache, open(CACHE, "w"), ensure_ascii=False)
            return items
        except Exception as e:
            print("   retry", a, e); time.sleep(10)
    return None

def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())

report = []
for k, txt in REFS.items():
    if "[S]" in txt:
        report.append((k, "SKIP-STD", "规范类条目，须向原文核对"))
        print(f"[SKIP] {k:12} 规范类"); continue
    # 拆字段
    m = re.match(r"^(?P<au>[^.]+)\.\s*(?P<title>.+?)\[(?P<ty>[JMS])\]\.\s*(?P<rest>.+)$", txt)
    if not m:
        print(f"[FAIL] {k:12} 无法解析"); report.append((k, "PARSE-FAIL", txt[:40])); continue
    title = m.group("title")
    rest = m.group("rest")
    year = re.search(r"(\d{4})", rest); year = year.group(1) if year else ""
    vol = re.search(r"\d{4},\s*([\d]+)", rest); vol = vol.group(1) if vol else ""
    iss = re.search(r"\(([\d\-]+)\)", rest); iss = iss.group(1) if iss else ""
    pg  = re.search(r":\s*([\d\-]+)\.?$", rest); pg = pg.group(1) if pg else ""
    au1 = m.group("au").split(",")[0].strip().split()[-1] if m.group("au") else ""
    items = fetch(title)
    if items is None:
        print(f"[ERR ] {k:12} 查询失败"); report.append((k, "ERR", "")); continue
    best, score = None, 0
    for it in items:
        t = (it.get("title") or [""])[0]
        sc = len(set(norm(t).split()) & set(norm(title).split())) / max(1, len(set(norm(title).split())))
        sc = 1 if norm(t)[:60] == norm(title)[:60] else sc
        if sc > score: best, score = it, sc
    if not best or score < 0.6:
        print(f"[MISS] {k:12} 未匹配到（score={score:.2f}）" + (f" 近邻: {(best.get('title') or [''])[0][:70]}" if best else ""))
        report.append((k, "MISS", "")); continue
    t = (best.get("title") or [""])[0]
    ct = (best.get("container-title") or [""])[0]
    yr = str((best.get("issued", {}).get("date-parts", [[None]])[0] or [None])[0])
    v = str(best.get("volume") or ""); i = str(best.get("issue") or "")
    p = str(best.get("page") or best.get("article-number") or "")
    fa = (best.get("author") or [{}])[0].get("family", "")
    diff = []
    if yr and yr != year: diff.append(f"年 {year}->{yr}")
    if v and vol and v != vol: diff.append(f"卷 {vol}->{v}")
    if i and iss and i != iss: diff.append(f"期 {iss}->{i}")
    if p and pg and p.replace("-", "").replace(" ", "") != pg.replace("-", "").replace(" ", ""):
        diff.append(f"页 {pg}->{p}")
    if fa and au1 and norm(fa) not in norm(au1) and norm(au1) not in norm(fa):
        diff.append(f"首作者 {au1}->{fa}")
    if diff:
        print(f"[DIFF] {k:12} " + "; ".join(diff))
        print(f"       刊名核对: {ct} | doi:{best.get('DOI')}")
        report.append((k, "DIFF", "; ".join(diff)))
    else:
        print(f"[ OK ] {k:12} {yr} {ct[:38]} {v}({i}):{p}")
        report.append((k, "OK", ""))
    time.sleep(1.2)

print("\n汇总:", {s: sum(1 for r in report if r[1] == s) for s in set(r[1] for r in report)})
json.dump(report, open("xcheck_report.json", "w"), ensure_ascii=False, indent=1)
