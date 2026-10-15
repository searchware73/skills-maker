#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""anchor_map.py — paper-review 源位置三轨定位脚本

三轨定位（每条发现同时给出，见 references/anchor-locator.md）：
  1. 工作坐标：draft.md 行号（流水线的现有工作坐标）
  2. 源坐标  ：tex = 文件:行号；docx = 段落序号；pdf = 页码
               （利用提取时植入的 %% [PDF p.N] / --- Page N --- 页标记）
  3. 结构坐标：章/节/表/公式编号 + 原句引文（跨格式最稳，反查失败时的兜底锚点）

机制：将发现的原句引文（≥15字）在源文件中做归一化文本反查：
  - tex  ：逐行匹配（去注释/去命令/去花括号后比较；源可为目录，遍历 *.tex）
  - docx ：按段落序匹配（zipfile+XML 解析 word/document.xml，无第三方依赖）
  - pdf  ：按页标记切分提取文本，页内匹配

用法：
  # Step 0 之后生成空表
  python anchor_map.py init --draft draft.md --source 源文件或目录 --format tex|docx|pdf \
      [--review-dir DIR]

  # 阶段4 合并时填充（requests 为 JSON：[{quote, draft_line?, structural?, id?}, ...]）
  python anchor_map.py fill --requests anchor_requests.json [--review-dir DIR]

输出文件：{review_dir}/anchor_map.json
  {"format": "tex", "source": "...", "draft": "...", "entries": [
     {"id": "a1", "quote": "...", "draft_line": 42, "source_loc": "main.tex:88",
      "structural": "§2.1 表1", "status": "resolved", "ambiguous": false}, ...]}

反查失败/歧义（多处命中）时 status=not_found/ambiguous，source_loc=null，
回退结构坐标（structural + quote 永远保留，作为兜底锚点）。

stdout（JSON）：
  init → {"success": true, "action": "init", "anchor_map": "...", "format": "tex", ...}
  fill → {"success": true, "action": "fill", "processed": N, "resolved": N,
          "ambiguous": N, "not_found": N, "anchor_map": "..."}

退出码：0=成功；1=文件读写失败；2=参数错误。
"""
import argparse
import glob
import io
import json
import os
import re
import sys
import unicodedata
import zipfile
import xml.etree.ElementTree as ET

# 修复 Windows 下 GBK 编码问题，强制 UTF-8 输出
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

FORMATS = ("tex", "docx", "pdf")

# pdf 提取文本中的页标记：%% [PDF p.N]（标准）或 --- Page N ---（extract_pdf.py 旧式）
PDF_PAGE_RES = [
    re.compile(r"^%%\s*\[PDF\s*p\.(\d+)\]", re.IGNORECASE),
    re.compile(r"^---\s*Page\s+(\d+)", re.IGNORECASE),
]

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# 归一化：需要剔除的空白与常见标点（用于「压缩匹配」兜底）
SQUASH_DROP_RE = re.compile(r"[\s，。；：、,.:;！？!?·…—\-–~\"'“”‘’()\[\]{}<>$\\]")


def to_posix(path):
    return path.replace("\\", "/")


def fail(msg, code=2):
    print("错误：%s" % msg, file=sys.stderr)
    sys.exit(code)


# ────────────────────────── 文本归一化 ──────────────────────────

def _strip_tex(text):
    """tex 行 → 可比对文本：去注释、去命令、去花括号/数学定界符"""
    text = re.sub(r"(?<!\\)%.*$", "", text)               # 行内注释
    text = re.sub(r"\\(?:begin|end)\s*\{[^}]*\}", " ", text)
    text = re.sub(r"\\[a-zA-Z@]+\*?\s*", " ", text)       # 命令（保留其参数文字）
    text = text.replace("{", " ").replace("}", " ")
    text = text.replace("$", " ").replace("\\(", " ").replace("\\)", " ")
    return text


def norm(text, fmt=None):
    """NFKC 归一（全半角统一）+ 大小写折叠 + 可选 tex 清理 + 空白折叠"""
    if fmt == "tex":
        text = _strip_tex(text)
    text = unicodedata.normalize("NFKC", text)
    # markdown 强调符/代码符不属于源文本表面形式
    text = text.replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", text).strip().casefold()


def squash(text, fmt=None):
    """压缩形态：norm 后再剔除全部空白与标点（应对转换改标点/断词）"""
    t = norm(text, fmt)
    return SQUASH_DROP_RE.sub("", t)


# ────────────────────────── 源单元切分 ──────────────────────────

def _read_text(path):
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    return None


def tex_units(source):
    """tex 源 → [(loc, raw_line), ...]；source 为目录时遍历其下 *.tex"""
    if os.path.isdir(source):
        files = sorted(glob.glob(os.path.join(source, "**", "*.tex"), recursive=True))
    else:
        files = [source]
    units = []
    for fp in files:
        content = _read_text(fp)
        if content is None:
            continue
        base = os.path.basename(fp)
        for ln, line in enumerate(content.splitlines(), 1):
            if line.strip():
                units.append(("%s:%d" % (base, ln), line))
    return units


def docx_units(source):
    """docx → [("段落N", raw_text), ...]（python-docx 兼容的 0-based 段落序号，
    loc 显示为 1-based「段落N」便于人工核对；JSON 另存 para_index）"""
    try:
        with zipfile.ZipFile(source) as z:
            xml = z.read("word/document.xml")
    except (OSError, KeyError, zipfile.BadZipFile) as e:
        raise ValueError("无法解析 docx（%s）: %s" % (source, e))
    root = ET.fromstring(xml)
    units = []
    for idx, p in enumerate(root.iter(W_NS + "p")):
        text = "".join(t.text or "" for t in p.iter(W_NS + "t"))
        if text.strip():
            units.append(("段落%d" % idx, text))   # python-docx paragraph index（0-based）
    return units


def pdf_units(source):
    """pdf 提取文本 → [("p.N", page_text), ...]，按 %% [PDF p.N] / --- Page N --- 标记切分"""
    content = _read_text(source)
    if content is None:
        raise ValueError("无法读取 pdf 提取文本: %s" % source)
    units, cur_no, cur = [], None, []
    for line in content.splitlines():
        page_no = None
        for rx in PDF_PAGE_RES:
            m = rx.match(line.strip())
            if m:
                page_no = int(m.group(1))
                break
        if page_no is not None:
            if cur_no is not None:
                units.append(("p.%d" % cur_no, "\n".join(cur)))
            cur_no, cur = page_no, []
        elif cur_no is not None:
            cur.append(line)
    if cur_no is not None:
        units.append(("p.%d" % cur_no, "\n".join(cur)))
    return units


def build_units(source, fmt):
    if fmt == "tex":
        return tex_units(source)
    if fmt == "docx":
        return docx_units(source)
    if fmt == "pdf":
        return pdf_units(source)
    raise ValueError("未知格式: %s" % fmt)


def infer_format(source):
    if os.path.isdir(source):
        return "tex"
    ext = os.path.splitext(source)[1].lower()
    if ext == ".tex":
        return "tex"
    if ext == ".docx":
        return "docx"
    if ext in (".txt",) or ext == ".pdf":
        return "pdf"
    return None


# ────────────────────────── 反查匹配 ──────────────────────────

def _count_in(hay, needle):
    if not needle:
        return 0
    return hay.count(needle)


def locate(quote, units, fmt):
    """在源单元中反查引文。返回 (source_loc|None, status, hits)。
    status ∈ resolved（恰1处命中）/ ambiguous（多处）/ not_found（0处）"""
    levels = [
        (norm(quote, fmt), lambda u: norm(u, fmt)),
        (squash(quote, fmt), lambda u: squash(u, fmt)),
    ]
    for needle, transform in levels:
        if len(needle) < 8:
            continue
        total, hit_loc = 0, None
        for loc, raw in units:
            c = _count_in(transform(raw), needle)
            if c:
                total += c
                hit_loc = loc
        if total == 1:
            return hit_loc, "resolved", 1
        if total > 1:
            return None, "ambiguous", total
    return None, "not_found", 0


def draft_lines_of(draft_path):
    content = _read_text(draft_path)
    if content is None:
        return None
    return content.splitlines()


def find_draft_line(quote, lines):
    """在 draft 行中反查引文，唯一命中返回 1-based 行号，否则 None"""
    if not lines:
        return None
    nq = norm(quote)
    hits = [i for i, ln in enumerate(lines, 1) if nq and nq in norm(ln)]
    if len(hits) == 1:
        return hits[0]
    sq = squash(quote)
    hits = [i for i, ln in enumerate(lines, 1) if sq and sq in squash(ln)]
    if len(hits) == 1:
        return hits[0]
    return None


# ────────────────────────── init / fill ──────────────────────────

def map_path(review_dir):
    return os.path.join(review_dir, "anchor_map.json")


def do_init(args):
    fmt = args.format or infer_format(args.source)
    if fmt not in FORMATS:
        fail("无法推断源格式，请用 --format 显式指定（tex|docx|pdf）")
    if not os.path.exists(args.source):
        fail("源文件/目录不存在: %s" % args.source)
    if args.draft and not os.path.isfile(args.draft):
        fail("draft 文件不存在: %s" % args.draft)
    data = {
        "format": fmt,
        "source": to_posix(os.path.abspath(args.source)),
        "draft": to_posix(os.path.abspath(args.draft)) if args.draft else None,
        "entries": [],
    }
    os.makedirs(args.review_dir, exist_ok=True)
    path = map_path(args.review_dir)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return {
        "success": True, "action": "init", "format": fmt,
        "source": data["source"], "draft": data["draft"],
        "anchor_map": to_posix(os.path.abspath(path)),
    }, 0


def do_fill(args):
    path = map_path(args.review_dir)
    if not os.path.isfile(path):
        fail("anchor_map.json 不存在，请先执行 init: %s" % path, code=1)
    with open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    with open(args.requests, "r", encoding="utf-8-sig") as f:
        req = json.load(f)
    requests = req.get("entries", req) if isinstance(req, dict) else req
    if not isinstance(requests, list):
        fail("requests 必须是列表或含 entries 键的对象", code=1)

    fmt = data.get("format")
    source = data.get("source")
    try:
        units = build_units(source, fmt)
    except ValueError as e:
        fail(str(e), code=1)

    dlines = draft_lines_of(data["draft"]) if data.get("draft") else None

    existing = {e.get("id") or e.get("quote"): e for e in data["entries"]}
    stats = {"resolved": 0, "ambiguous": 0, "not_found": 0}
    processed = 0
    for i, r in enumerate(requests, 1):
        quote = (r.get("quote") or "").strip()
        if not quote:
            print("警告：第%d条 request 缺少 quote，跳过" % i, file=sys.stderr)
            continue
        processed += 1
        src_loc, status, hits = locate(quote, units, fmt)
        draft_line = r.get("draft_line")
        if draft_line is None and dlines:
            draft_line = find_draft_line(quote, dlines)
        entry = {
            "id": r.get("id") or "a%d" % len(existing),
            "quote": quote,
            "draft_line": draft_line,
            "source_loc": src_loc,               # 反查失败/歧义时为 null
            "structural": r.get("structural") or "",
            "status": status,
            "ambiguous": status == "ambiguous",
            "hits": hits,
        }
        stats[status] += 1
        key = entry["id"] if entry["id"] in existing else quote
        existing[key] = entry
    data["entries"] = list(existing.values())
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        fail("写入 anchor_map.json 失败: %s" % e, code=1)
    return {
        "success": True, "action": "fill", "processed": processed,
        "resolved": stats["resolved"], "ambiguous": stats["ambiguous"],
        "not_found": stats["not_found"],
        "anchor_map": to_posix(os.path.abspath(path)),
    }, 0


def main():
    parser = argparse.ArgumentParser(
        prog="anchor_map.py",
        description="paper-review 源位置三轨定位：md行 ↔ 源定位（tex行/docx段/pdf页）↔ 结构坐标，"
                    "维护 {review_dir}/anchor_map.json。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--review-dir", metavar="DIR", default=".review",
                        help="审查输出目录（anchor_map.json 所在）")
    sub = parser.add_subparsers(dest="action", required=True)

    p_init = sub.add_parser("init", help="生成空 anchor_map.json（Step 0 之后）")
    p_init.add_argument("--draft", metavar="FILE", default=None,
                        help="工作稿 draft.md 路径（用于行号反查，可选）")
    p_init.add_argument("--source", metavar="PATH", required=True,
                        help="源文件或源目录（tex 目录 / .tex / .docx / pdf提取.txt）")
    p_init.add_argument("--format", choices=FORMATS, default=None,
                        help="源格式（缺省按扩展名推断：目录→tex）")

    p_fill = sub.add_parser("fill", help="按 requests 填充定位（阶段4 合并时）")
    p_fill.add_argument("--requests", metavar="FILE", required=True,
                        help="JSON 请求文件：[{quote, draft_line?, structural?, id?}, ...]")

    args = parser.parse_args()
    if args.action == "init":
        result, code = do_init(args)
    else:
        result, code = do_fill(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(code)


if __name__ == "__main__":
    main()
