#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""conversion_audit.py — paper-review v2.0 转换审计脚本（Step 0 前置）

背景：pandoc 等 tex→md 转换会系统性丢失 table*、tikzpicture、algorithmic
等结构（实测 xue-paper 案）。v2.0 将转换审计前置到 Step 0：源侧结构计数
vs draft.md 计数对照，产出疑似丢失清单（含源侧指针）注入评审配置卡，
提醒评审人优先核对丢失结构，勿被转换稿误导。

用法：
  python conversion_audit.py --source PATH --draft FILE [--format tex|docx|pdf] [--output FILE]

  --source  源文件或目录（tex 目录 / .tex / .docx / pdf提取.txt / .pdf）
  --draft   工作稿 draft.md
  --format  源格式，缺省按扩展名推断：目录→tex；.tex→tex；.docx→docx；.txt/.pdf→pdf
  --output  markdown 审计报告输出路径（缺省不写文件）

源侧计数 source_counts：
  tex  ：正则计数 \\begin{table|table*|figure|figure*|algorithm|algorithmic|
         tikzpicture|equation|align}（先去行内注释）；
         tables=table+table*，figures=figure+figure*，
         algorithms=algorithm+algorithmic，diagrams=tikzpicture，
         equations=equation+align；并为每个 table/figure/algorithm/tikzpicture
         环境记录指针 "文件名:行号"（文件按路径排序、行序、列序）
  docx ：zipfile+ElementTree 解析 word/document.xml（无第三方依赖）：
         w:tbl→tables；w:drawing+w:pict→figures；m:oMath→equations
  pdf  ：提取文本按页标记（%% [PDF p.N] / --- Page N ---）计 pages；
         真 .pdf 走 PyMuPDF(fitz)，ImportError/打开失败时降级 pages=null
         并向 stderr 告警；tables/figures/equations 记 null（无法机械计数）

draft 侧计数 draft_counts（markdown）：
  tables         = 连续以 | 开头且含分隔行（---）的表格块数
  figures        = ![...](...) 图片引用数
  formula_blocks = $$...$$ 块数（跨行配对）+ \\[...\\] 块数
  inline_math    = 不成对 $...$ 片段计数（近似：剔除 $$ 块后单行内 $ 成对数）

missing：tables/figures/equations 各 max(0, 源-draft)；algorithms/diagrams
markdown 无对应物，draft 侧恒 0；源值为 null 时记 null 不参与。
missing_pointers：丢失数>0 时按出现顺序列出源侧对应指针（源计数-draft计数 条）。

--output 写出的 markdown 报告含：计数对照表（| 结构 | 源侧 | draft侧 | 疑似丢失 |）、
「## 疑似丢失清单」（指针逐行）、固定结论行「数值核验以编译 PDF 为准」。

stdout（JSON）：
  {"success": true, "format": "tex", "source": "...", "draft": "...",
   "source_counts": {"tables":3,"figures":1,"algorithms":1,"diagrams":1,
                     "equations":2,"pages":null},
   "draft_counts": {"tables":1,"figures":0,"formula_blocks":0,"inline_math":1},
   "missing": {"tables":2,"figures":1,"equations":2,"algorithms":1,"diagrams":1},
   "missing_pointers": [{"type":"table","loc":"ch1.tex:2"}, ...],
   "output": null}

退出码：0=成功；1=文件读写失败；2=参数错误。
"""
import argparse
import glob
import io
import json
import os
import re
import sys
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
COUNT_KEYS = ("tables", "figures", "algorithms", "diagrams", "equations", "pages")

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
M_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"

# pdf 提取文本中的页标记（与 anchor_map.py / extract_pdf.py 一致）
PDF_PAGE_RES = [
    re.compile(r"^%%\s*\[PDF\s*p\.(\d+)\]", re.IGNORECASE),
    re.compile(r"^---\s*Page\s+(\d+)", re.IGNORECASE),
]

# tex 环境正则：\begin{table} 不会命中 \begin{table*}（} 锚定），分开计数
TEX_ENV_RES = {
    "table": re.compile(r"\\begin\{table\}"),
    "table*": re.compile(r"\\begin\{table\*\}"),
    "figure": re.compile(r"\\begin\{figure\}"),
    "figure*": re.compile(r"\\begin\{figure\*\}"),
    "algorithm": re.compile(r"\\begin\{algorithm\}"),
    "algorithmic": re.compile(r"\\begin\{algorithmic\}"),
    "tikzpicture": re.compile(r"\\begin\{tikzpicture\}"),
    "equation": re.compile(r"\\begin\{equation\}"),
    "align": re.compile(r"\\begin\{align\}"),
}

# 类别归并：source_counts 键 → tex 环境名
TEX_CATEGORIES = {
    "tables": ("table", "table*"),
    "figures": ("figure", "figure*"),
    "algorithms": ("algorithm", "algorithmic"),
    "diagrams": ("tikzpicture",),
    "equations": ("equation", "align"),
}
ENV_CATEGORY = {env: cat for cat, envs in TEX_CATEGORIES.items() for env in envs}

# 需要记录指针的类别（equations 不记指针）；指针 type = 类别单数
POINTER_CATEGORIES = ("tables", "figures", "algorithms", "diagrams")


def to_posix(path):
    return path.replace("\\", "/")


def fail(msg, code=2):
    print("错误：%s" % msg, file=sys.stderr)
    sys.exit(code)


def _read_text(path):
    """utf-8-sig 优先、gbk 兜底读取文本；解码/IO 失败返回 None"""
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
        except OSError:
            return None
    return None


def _empty_pointers():
    return {cat: [] for cat in POINTER_CATEGORIES}


def infer_format(source):
    if os.path.isdir(source):
        return "tex"
    ext = os.path.splitext(source)[1].lower()
    if ext == ".tex":
        return "tex"
    if ext == ".docx":
        return "docx"
    if ext in (".txt", ".pdf"):
        return "pdf"
    return None


# ────────────────────────── 源侧计数 ──────────────────────────

def count_tex(source):
    """tex 源（文件或目录，目录时递归 glob **/*.tex）→ (counts, pointers)"""
    if os.path.isdir(source):
        files = sorted(glob.glob(os.path.join(source, "**", "*.tex"), recursive=True))
    else:
        files = [source]
    env_counts = {env: 0 for env in TEX_ENV_RES}
    pointers = _empty_pointers()
    for fp in files:
        content = _read_text(fp)
        if content is None:
            print("警告：无法读取 %s，已跳过" % to_posix(fp), file=sys.stderr)
            continue
        base = os.path.basename(fp)
        for ln, line in enumerate(content.splitlines(), 1):
            code = re.sub(r"(?<!\\)%.*$", "", line)      # 去行内注释后计数
            hits = []
            for env, rx in TEX_ENV_RES.items():
                for m in rx.finditer(code):
                    hits.append((m.start(), env))
            for _, env in sorted(hits):                  # 同行多环境按列序
                env_counts[env] += 1
                cat = ENV_CATEGORY[env]
                if cat in POINTER_CATEGORIES:
                    pointers[cat].append("%s:%d" % (base, ln))
    counts = {cat: sum(env_counts[e] for e in envs) for cat, envs in TEX_CATEGORIES.items()}
    counts["pages"] = None
    return counts, pointers


def count_docx(source):
    """docx → (counts, pointers)：w:tbl / w:drawing+w:pict / m:oMath 计数。
    docx 无行号概念，不产出逐项指针。"""
    try:
        with zipfile.ZipFile(source) as z:
            xml_bytes = z.read("word/document.xml")
        root = ET.fromstring(xml_bytes)
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as e:
        raise ValueError("无法解析 docx（%s）: %s" % (source, e))
    counts = {
        "tables": sum(1 for _ in root.iter(W_NS + "tbl")),
        "figures": (sum(1 for _ in root.iter(W_NS + "drawing"))
                    + sum(1 for _ in root.iter(W_NS + "pict"))),
        "algorithms": None,
        "diagrams": None,
        "equations": sum(1 for _ in root.iter(M_NS + "oMath")),
        "pages": None,
    }
    return counts, _empty_pointers()


def _pdf_pages_fitz(source):
    """真 .pdf → fitz 计页；未安装/打开失败降级 None 并 stderr 告警"""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("警告：未安装 PyMuPDF(fitz)，无法对 .pdf 计页，pages 降级为 null", file=sys.stderr)
        return None
    try:
        doc = fitz.open(source)
        try:
            return doc.page_count
        finally:
            doc.close()
    except Exception as e:
        print("警告：fitz 打开失败（%s），pages 降级为 null" % e, file=sys.stderr)
        return None


def _pdf_pages_from_text(source):
    """pdf 提取文本 → 按页标记计 unique 页码数；无标记返回 None"""
    content = _read_text(source)
    if content is None:
        raise ValueError("无法读取 pdf 提取文本: %s" % source)
    pages = set()
    for line in content.splitlines():
        s = line.strip()
        for rx in PDF_PAGE_RES:
            m = rx.match(s)
            if m:
                pages.add(int(m.group(1)))
                break
    return len(pages) if pages else None


def count_pdf(source):
    """pdf（提取 .txt 或真 .pdf）→ (counts, pointers)：仅 pages 可机械计数"""
    counts = {k: None for k in COUNT_KEYS}
    if os.path.splitext(source)[1].lower() == ".pdf":
        counts["pages"] = _pdf_pages_fitz(source)
    else:
        counts["pages"] = _pdf_pages_from_text(source)
    return counts, _empty_pointers()


# ────────────────────────── draft 侧计数 ──────────────────────────

def _is_table_sep(s):
    """markdown 表格分隔行：仅由 | - : 空白构成，且至少 3 个 -"""
    return bool(s) and set(s) <= set("|-: ") and s.count("-") >= 3


def count_draft(draft_path):
    """draft.md → {tables, figures, formula_blocks, inline_math}"""
    content = _read_text(draft_path)
    if content is None:
        raise ValueError("无法读取 draft: %s" % draft_path)

    # tables：连续以 | 开头且含分隔行的块计 1 个表格
    tables, run = 0, []
    for line in content.splitlines() + [""]:
        if line.lstrip().startswith("|"):
            run.append(line.strip())
        elif run:
            if len(run) >= 2 and any(_is_table_sep(l) for l in run):
                tables += 1
            run = []

    # figures：![...](...) 图片引用
    figures = len(re.findall(r"!\[[^\]]*\]\([^)]*\)", content))

    # 公式块：$$...$$（跨行配对，按 $$ 记号成对数）+ \[...\]
    formula_blocks = content.count("$$") // 2
    formula_blocks += len(re.findall(r"\\\[[\s\S]*?\\\]", content))

    # 行内数学（近似）：剔除 $$ 块后，单行内 $ 成对数
    no_display = re.sub(r"\$\$[\s\S]*?\$\$", " ", content)
    inline_math = sum(l.count("$") // 2 for l in no_display.splitlines())

    return {"tables": tables, "figures": figures,
            "formula_blocks": formula_blocks, "inline_math": inline_math}


# ────────────────────────── 丢失对照 ──────────────────────────

def compute_missing(source_counts, draft_counts):
    def diff(src, dst):
        if src is None:
            return None
        return max(0, src - dst)
    return {
        "tables": diff(source_counts["tables"], draft_counts["tables"]),
        "figures": diff(source_counts["figures"], draft_counts["figures"]),
        "equations": diff(source_counts["equations"], draft_counts["formula_blocks"]),
        # markdown 无算法/tikz 对应物，draft 侧恒 0
        "algorithms": diff(source_counts["algorithms"], 0),
        "diagrams": diff(source_counts["diagrams"], 0),
    }


def collect_missing_pointers(missing, pointers):
    """丢失数>0 的类别，按出现顺序取前 (源-draft) 条指针"""
    ptrs = []
    for cat in POINTER_CATEGORIES:
        n = missing.get(cat)
        if not n:
            continue
        ptype = cat[:-1]                      # tables→table, diagrams→diagram
        for loc in pointers.get(cat, [])[:n]:
            ptrs.append({"type": ptype, "loc": loc})
    return ptrs


# ────────────────────────── 报告 ──────────────────────────

def render_report(fmt, source, draft, sc, dc, missing, missing_pointers):
    def cell(v):
        return "—" if v is None else str(v)

    zero_if_counted = lambda v: 0 if v is not None else None  # noqa: E731
    rows = [
        ("表格（table/table* ↔ md 表格块）", sc["tables"], dc["tables"], missing["tables"]),
        ("图片（figure ↔ ![](...)）", sc["figures"], dc["figures"], missing["figures"]),
        ("算法（algorithm/algorithmic）", sc["algorithms"],
         zero_if_counted(sc["algorithms"]), missing["algorithms"]),
        ("tikz 示意图（tikzpicture）", sc["diagrams"],
         zero_if_counted(sc["diagrams"]), missing["diagrams"]),
        ("公式（equation/align ↔ $$ 块）", sc["equations"],
         dc["formula_blocks"], missing["equations"]),
        ("页数", sc["pages"], None, None),
    ]
    lines = [
        "# 转换审计报告",
        "",
        "- 源：%s（格式：%s）" % (source, fmt),
        "- 工作稿：%s" % draft,
        "",
        "## 计数对照",
        "",
        "| 结构 | 源侧 | draft侧 | 疑似丢失 |",
        "|------|------|---------|----------|",
    ]
    for name, s, d, m in rows:
        lines.append("| %s | %s | %s | %s |" % (name, cell(s), cell(d), cell(m)))
    lines += [
        "",
        "（draft 行内数学片段 inline_math=%d，不参与丢失对照）" % dc["inline_math"],
        "",
        "## 疑似丢失清单",
        "",
    ]
    if missing_pointers:
        for p in missing_pointers:
            lines.append("- [%s] %s" % (p["type"], p["loc"]))
    elif any(v for v in missing.values() if v is not None):
        lines.append("（源侧无逐项指针，丢失数量见计数对照表）")
    else:
        lines.append("（未发现疑似结构丢失）")
    lines += [
        "",
        "> 注：以上为机械计数对照，仅标记疑似丢失；数值核验以编译 PDF 为准。",
        "",
    ]
    return "\n".join(lines)


# ────────────────────────── 主流程 ──────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="conversion_audit.py",
        description="paper-review v2.0 转换审计（Step 0 前置）：源侧结构计数 vs draft.md 计数，"
                    "产出疑似丢失清单注入评审配置卡。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--source", metavar="PATH", required=True,
                        help="源文件或目录（tex 目录 / .tex / .docx / pdf提取.txt / .pdf）")
    parser.add_argument("--draft", metavar="FILE", required=True,
                        help="工作稿 draft.md 路径")
    parser.add_argument("--format", choices=FORMATS, default=None,
                        help="源格式（缺省按扩展名推断：目录→tex，.tex→tex，.docx→docx，.txt/.pdf→pdf）")
    parser.add_argument("--output", metavar="FILE", default=None,
                        help="markdown 审计报告输出路径（缺省不写文件）")
    args = parser.parse_args()

    fmt = args.format or infer_format(args.source)
    if fmt not in FORMATS:
        fail("无法推断源格式，请用 --format 显式指定（tex|docx|pdf）")
    if not os.path.exists(args.source):
        fail("源文件/目录不存在: %s" % args.source)
    if not os.path.isfile(args.draft):
        fail("draft 文件不存在: %s" % args.draft)

    try:
        if fmt == "tex":
            source_counts, pointers = count_tex(args.source)
        elif fmt == "docx":
            source_counts, pointers = count_docx(args.source)
        else:
            source_counts, pointers = count_pdf(args.source)
        draft_counts = count_draft(args.draft)
    except ValueError as e:
        fail(str(e), code=1)

    missing = compute_missing(source_counts, draft_counts)
    missing_pointers = collect_missing_pointers(missing, pointers)

    src_posix = to_posix(os.path.abspath(args.source))
    draft_posix = to_posix(os.path.abspath(args.draft))
    out_path = None
    if args.output:
        report = render_report(fmt, src_posix, draft_posix,
                               source_counts, draft_counts, missing, missing_pointers)
        out_path = to_posix(os.path.abspath(args.output))
        try:
            parent = os.path.dirname(out_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(out_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(report)
        except OSError as e:
            fail("写入审计报告失败: %s" % e, code=1)

    result = {
        "success": True,
        "format": fmt,
        "source": src_posix,
        "draft": draft_posix,
        "source_counts": source_counts,
        "draft_counts": draft_counts,
        "missing": missing,
        "missing_pointers": missing_pointers,
        "output": out_path,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
