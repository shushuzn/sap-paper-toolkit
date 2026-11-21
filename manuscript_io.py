# -*- coding: utf-8 -*-
"""稿件与数据层的定位、读取与结构切分，供各核验脚本共用。

本模块只做定位与解析，不绑定任何具体稿件、目录或机构要求：

- 稿件与数据层的位置一律可由命令行选项、环境变量或当前目录默认名确定，
  优先级为 选项 > 环境变量 > 默认名。
- 章节锚点取体裁通用名（如中文摘要、英文摘要、关键词、参考文献）。
  目标稿件若用别的叫法，在数据层里写 SECTIONS 覆盖，不必改脚本。
"""
import importlib.util
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

# 体裁通用结构名。只是常见叫法，不是对某篇稿件的规定。
DEFAULT_SECTIONS = {
    "abstract_cn": ("摘要",),
    "keywords_cn": ("关键词",),
    "abstract_en": ("Abstract",),
    "keywords_en": ("Key words", "Keywords"),
    "references": ("参考文献", "References"),
}

SRC_SUFFIXES = (".md", ".markdown", ".docx")
DATA_NAME = "paper_data.py"
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


# ---------- 命令行 ----------
def pop_option(argv, flag, default=None):
    """从 argv 中取出 --flag VALUE 或 --flag=VALUE，取到即删除，返回 (value, argv)。"""
    argv = list(argv)
    for i, a in enumerate(argv):
        if a == flag:
            if i + 1 >= len(argv):
                sys.exit("%s 缺少值" % flag)
            val = argv[i + 1]
            del argv[i:i + 2]
            return val, argv
        if a.startswith(flag + "="):
            val = a.split("=", 1)[1]
            del argv[i]
            return val, argv
    return default, argv


def pop_flag(argv, flag):
    """从 argv 中取出布尔开关，返回 (present, argv)。"""
    argv = list(argv)
    if flag in argv:
        argv.remove(flag)
        return True, argv
    return False, argv


# ---------- 定位 ----------
def resolve_source(argv, cwd="."):
    """确定稿件路径：位置参数 > 环境变量 PAPER_SRC > 当前目录唯一的候选文件。"""
    rest = [a for a in argv if not a.startswith("-")]
    if rest:
        p = Path(rest[0])
        if not p.is_file():
            sys.exit("找不到稿件：%s" % p)
        return p

    env = os.environ.get("PAPER_SRC")
    if env:
        p = Path(env)
        if not p.is_file():
            sys.exit("环境变量 PAPER_SRC 指向的文件不存在：%s" % p)
        return p

    cands = sorted(p for p in Path(cwd).iterdir()
                   if p.is_file() and p.suffix.lower() in SRC_SUFFIXES
                   and not p.name.startswith("~$"))
    if not cands:
        sys.exit("当前目录没有 .md 或 .docx 稿件；请用位置参数指定，"
                 "或设环境变量 PAPER_SRC。")
    if len(cands) > 1:
        names = "\n  ".join(c.name for c in cands)
        sys.exit("当前目录有多个候选稿件，请用位置参数指定其一：\n  %s" % names)
    return cands[0]


def resolve_data(explicit=None):
    """确定数据层文件：显式值 > 环境变量 PAPER_DATA > 当前目录默认名。

    找不到时返回 None，调用方须按"数据层缺失"处理，不得填入默认数据。
    """
    for cand in (explicit, os.environ.get("PAPER_DATA"), DATA_NAME):
        if not cand:
            continue
        p = Path(cand)
        if p.is_file():
            return p
    return None


def load_data(path):
    """载入数据层模块；path 为 None 时返回 None。"""
    if path is None:
        return None
    spec = importlib.util.spec_from_file_location("paper_data", str(path))
    if spec is None or spec.loader is None:
        sys.exit("数据层无法载入：%s" % path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------- 读取 ----------
def read_docx_paragraphs(path):
    """从 .docx 直接取段落文本，不依赖 Word。

    只读 word/document.xml 的 w:p / w:t，取不到域代码与批注文本，
    因此适合结构检查，不适合替代文字处理软件的字数统计。
    """
    try:
        with zipfile.ZipFile(str(path)) as z:
            xml = z.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as e:
        sys.exit("无法读取 .docx：%s（%s）" % (path, e))

    root = ET.fromstring(xml)
    out = []
    for para in root.iter(W_NS + "p"):
        text = "".join(t.text or "" for t in para.iter(W_NS + "t"))
        if text.strip():
            out.append(text.strip())
    return out


def read_paragraphs(path):
    """按文件类型返回段落列表（非空、已去首尾空白）。"""
    path = Path(path)
    if path.suffix.lower() == ".docx":
        return read_docx_paragraphs(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def heading_level(line):
    """返回 Markdown 标题级别；非标题返回 0。"""
    m = re.match(r"^(#{1,6})\s+(\S.*)$", line)
    return len(m.group(1)) if m else 0


def squash(text):
    """去掉全部空白，便于比对标题名。"""
    return re.sub(r"\s+", "", text or "")


# ---------- 结构 ----------
def resolve_sections(data):
    """合并数据层覆盖项与体裁通用默认名。"""
    sections = {k: tuple(v) for k, v in DEFAULT_SECTIONS.items()}
    override = getattr(data, "SECTIONS", None) if data else None
    if isinstance(override, dict):
        for k, v in override.items():
            if isinstance(v, str):
                v = (v,)
            sections[k] = tuple(v)
    return sections


def find_heading(paragraphs, names, level=None):
    """找第一个标题名匹配的段落下标；names 支持前缀匹配（如"1　引言"）。

    返回 -1 表示未找到，调用方须提示可用的标题清单而不是继续取下一段。
    """
    for i, line in enumerate(paragraphs):
        lv = heading_level(line)
        if level is not None and lv != level:
            continue
        body = line[lv:].strip() if lv else line
        key = squash(body)
        for name in names:
            n = squash(name)
            if key == n or key.startswith(n):
                return i
    return -1


def split_structure(paragraphs, data=None):
    """切出摘要、关键词、正文、参考文献四块。

    返回 dict，缺失的键为 None；同时返回一份可读的诊断信息，
    便于调用方在锚点缺失时告诉使用者实际找到了哪些标题。
    """
    sec = resolve_sections(data)
    idx = {
        "abstract_cn": find_heading(paragraphs, sec["abstract_cn"]),
        "keywords_cn": find_heading(paragraphs, sec["keywords_cn"]),
        "abstract_en": find_heading(paragraphs, sec["abstract_en"]),
        "keywords_en": find_heading(paragraphs, sec["keywords_en"]),
        "references": find_heading(paragraphs, sec["references"]),
    }

    body_start = -1
    for i, line in enumerate(paragraphs):
        if heading_level(line) == 1 and re.match(r"^#\s*\d", line):
            body_start = i
            break
    idx["body"] = body_start

    def after(key):
        i = idx[key]
        return paragraphs[i + 1] if 0 <= i < len(paragraphs) - 1 else None

    def inline_or_after(key):
        """关键词这类可能写成"关键词：a；b"同段，也可能单列一段。

        同段带冒号时取冒号之后，否则取下一段。
        """
        i = idx[key]
        if i < 0:
            return None
        line = paragraphs[i]
        if re.search(r"[：:]", line):
            return line
        return paragraphs[i + 1] if i < len(paragraphs) - 1 else None

    refs_end = idx["references"] if idx["references"] >= 0 else len(paragraphs)
    body_end = refs_end if idx["body"] >= 0 else -1
    body = "\n".join(paragraphs[idx["body"]:body_end]) if body_end > idx["body"] else None

    return {
        "abstract_cn": after("abstract_cn"),
        "keywords_cn": inline_or_after("keywords_cn"),
        "abstract_en": after("abstract_en"),
        "keywords_en": inline_or_after("keywords_en"),
        "body": body,
        "references": paragraphs[idx["references"]:],
        "index": idx,
    }


def heading_inventory(paragraphs):
    """列出稿件里实际出现的标题，供锚点缺失时打印。"""
    return [line for line in paragraphs if heading_level(line)]


# ---------- 参考文献 ----------
REF_ITEM = re.compile(r"^\[?(\d+)\]?[\.\s、]*(.+)$")


def refs_from_paragraphs(paragraphs, start_index):
    """从参考文献段起，按"编号 + 条目"逐行拆出 (编号, 条目)。

    兼容 "[1] 条目" 与 "1. 条目" 两种写法；无编号的行按顺序续排。
    """
    items = []
    seq = 0
    for line in paragraphs[max(0, start_index) + 1:]:
        if heading_level(line):
            break
        m = REF_ITEM.match(line)
        if m and (m.group(1) or "").isdigit():
            seq = int(m.group(1))
            items.append((seq, m.group(2).strip()))
        elif items:
            num, txt = items[-1]
            items[-1] = (num, txt + " " + line)
    return items


def refs_from_data(data):
    """从数据层的 REFS 取条目，保持定义顺序。"""
    refs = getattr(data, "REFS", None) if data else None
    if not refs:
        return []
    if isinstance(refs, dict):
        return [(i, v) for i, v in enumerate(refs.values(), 1)]
    return list(enumerate(refs, 1))
