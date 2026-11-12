#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extract_pdf.py — paper-review PDF 全文提取脚本（full-manuscript 专用，v2.1 条目10）

与 skills/lit-research/scripts/extract_pdf.py 的区别：lit-research 版是**节选提取器**
（前 8 页 + 后 3 页、每页 ≤3000 字符，供文献调研卡片场景）；本脚本面向**全文稿件
审阅**——全页提取无字符上限，并产出审阅流水线所需的全套产物（门禁 G1' 用户裁决：
paper-review 内独立新建，不经 shared/，因 install.py 不携带 shared 模块）。

功能（备忘 §十一 条目10）：
  1. 全页提取、无字符上限，逐页植入 `%% [PDF p.N]` 页标记
     （anchor_map.py 三轨定位中 pdf 源坐标的唯一切分依据）
  2. 无书签 PDF 按字号统计重建标题（章/节/小节 → ##/###/####），并合并被
     PDF 换行拆开的标题；有书签 PDF 按书签标题匹配标题行
  3. 过滤页眉页脚（跨页重复的版式行，如「XX大学博士学位论文」）与独立页码行、
     目录点引线行（「1.1 研究背景......5」）
  4. 图像按像素尺寸与长宽比过滤（剔除表格线、字形碎片、背景条），导出 PNG 到
     figures/ 并在 draft 中生成 `![…]()` 图片引用；统计图题/表题数
  5. 参考文献节按 `[N]` 切分写 refs.txt，供 bib_lint.py 直接消费
  6. 产出源侧计数 JSON（tables/figures/equations/pages 等），供
     conversion_audit.py --source-counts 回填（pdf 源侧不再为 null）；
     表格线性化/公式文本化按共同豁免处理（丢失清单会注入 1a 配置卡）

用法：
  python extract_pdf.py --input FILE.pdf --draft FILE.md \\
      [--figures-dir DIR] [--refs-out FILE] [--counts-out FILE] [--min-image-size N]

  --input           输入 PDF。密码保护/损坏 → exit 1 明确报错
                    （回退链见 SKILL Step 0.3：PyMuPDF 抽文本→find_tables→渲染 PNG 后 Read）
  --draft           输出 draft.md 路径（必填；父目录自动创建）
  --figures-dir     图像导出目录（默认 {draft 所在目录}/figures）
  --refs-out        参考文献切分产物（默认 {draft 所在目录}/refs.txt；未找到参考文献节则不写）
  --counts-out      源侧计数 JSON（默认 {draft 所在目录}/pdf_source_counts.json）
  --min-image-size  导出图像最小像素边长（宽高均须 ≥ 该值，默认 150；
                    R-3 回流：60 在 186 页学位论文上误导出 531 张表格/碎片图，
                    图题仅 95 个。细粒度文档可显式调低）

stdout（JSON）：
  {"success": true, "input": "...", "draft": "...", "pages": N, "bookmarks": false,
   "headings": N, "headers_footers_filtered": N, "toc_lines_filtered": N,
   "images_exported": N, "images_filtered": N,
   "figure_captions": N, "table_captions": N, "tables": N, "equations": N,
   "refs": N, "refs_out": "...|null", "figures_dir": "...", "counts_out": "..."}
  equations/tables 为启发式计数（公式编号行 / find_tables），近似值。

依赖：PyMuPDF（import fitz，回退 import pymupdf）

退出码：0=成功；1=提取失败（缺 PyMuPDF / PDF 损坏 / 密码保护 / 写入失败）；2=参数错误。
"""
import argparse
import contextlib
import io
import json
import math
import os
import re
import sys
import unicodedata
from collections import Counter

# 修复 Windows 下 GBK 编码问题，强制 UTF-8 输出
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

PAGE_MARKER = "%%%% [PDF p.%d]"

# 独立页码行：「12」/「- 12 -」/「第 12 页」/「Page 12 of 300」
PAGENUM_RE = re.compile(
    r"^[-–—\s]*\d{1,4}[-–—\s]*$|^第\s*\d{1,4}\s*页$|^Page\s+\d+", re.IGNORECASE)
# 目录点引线行：「绪论......1」「1.1 背景．．．．5」「摘要…3」
DOTLEADER_RE = re.compile(r"(?:[.·•]{4,}|…{2,}|[.·]{2,}…+)\s*\d{1,4}\s*$")
# 图题 / 表题行
FIG_CAP_RE = re.compile(r"^\s*(图|Fig(?:ure)?\.?)\s*\d", re.IGNORECASE)
TBL_CAP_RE = re.compile(r"^\s*(表|Table)\s*\d", re.IGNORECASE)
# 公式编号行尾：「(2-1)」「（3.4）」「(12)」——限 1-3 位数字，避免误吞年份
EQNUM_RE = re.compile(r"[（(]\s*\d{1,3}(?:\s*[-–.]\s*\d{1,3})?\s*[)）]\s*$")
# 编号起始（防止把「第2章 方法」+「2.1 实验」两个真标题误并为一个）
NUMBERING_RE = re.compile(
    r"^(\d+(\.\d+)*[\s、．.]|[一二三四五六七八九十]+[、．]|第\s*[0-9一二三四五六七八九十]+\s*[章节篇部条])")
# 标题行不得以句读结尾
END_PUNCT = "。！？；，、：.!?;,:…—-\""
# 参考文献节起止
REFS_HEAD_RE = re.compile(r"^(参考文献|References|Bibliography)$", re.IGNORECASE)
REFS_STOP_RE = re.compile(
    r"^(附录|致谢|致谢辞|Acknowledg(?:e?ments?)?|Appendi(?:x|ces)|攻读|作者简介|.*学位论文原创性声明.*)",
    re.IGNORECASE)

CJK_RE = re.compile(r"[　-〿㐀-䶿一-鿿＀-￯]")


def fail(msg, code=1):
    print("错误：%s" % msg, file=sys.stderr)
    sys.exit(code)


def to_posix(path):
    return path.replace("\\", "/")


def squash(text):
    return unicodedata.normalize("NFKC", text).casefold().replace(" ", "").replace("\t", "")


def hf_key(text):
    """页眉页脚归一键：去数字/空白/标点后的骨架（页码变化不影响归并）"""
    return re.sub(r"[\d\s]+", "", unicodedata.normalize("NFKC", text)).strip()


def is_cjk(ch):
    return bool(CJK_RE.match(ch or ""))


def import_fitz():
    try:
        import fitz  # PyMuPDF
        return fitz
    except ImportError:
        pass
    try:
        import pymupdf as fitz
        return fitz
    except ImportError:
        fail("未安装 PyMuPDF，无法提取 PDF：pip install pymupdf", 1)


def page_items(page):
    """单页 → 按阅读序（y0,x0）排列的 text/image 条目列表"""
    items = []
    try:
        d = page.get_text("dict")
    except Exception as e:  # 单页损坏不致命，留空
        print("警告：第 %d 页文本提取失败（%s），按空页处理" % (page.number + 1, e),
              file=sys.stderr)
        d = {"blocks": []}
    for b in d.get("blocks", []):
        if b.get("type") != 0:
            continue  # dict 的 image 块无 xref，统一走 get_image_info
        for ln in b.get("lines", []):
            spans = [s for s in ln.get("spans", []) if (s.get("text") or "").strip()]
            if not spans:
                continue
            text = "".join(s.get("text", "") for s in ln["spans"])
            text = text.replace("\t", " ").replace("\xa0", " ").strip()
            if not text:
                continue
            size = max(s.get("size", 0) or 0 for s in spans)
            x0, y0 = ln["bbox"][0], ln["bbox"][1]
            items.append({"kind": "text", "text": text,
                          "size": round(size * 2) / 2.0, "y": y0, "x": x0})
    try:
        for info in page.get_image_info(xrefs=True):
            items.append({"kind": "image", "y": info["bbox"][1], "x": info["bbox"][0],
                          "xref": info.get("xref", 0), "smask": info.get("smask", 0),
                          "w": info.get("width", 0), "h": info.get("height", 0)})
    except Exception as e:
        print("警告：第 %d 页图像清单读取失败（%s）" % (page.number + 1, e), file=sys.stderr)
    items.sort(key=lambda it: (round(it["y"], 1), round(it["x"], 1)))
    return items


def detect_header_footer(pages, npages):
    """跨页重复的版顶/版底行骨架 → 页眉页脚集合"""
    top, bottom = Counter(), Counter()
    for items in pages:
        texts = [it for it in items if it["kind"] == "text"]
        if not texts:
            continue
        for it in texts[:2]:
            k = hf_key(it["text"])
            if k:
                top[k] += 1
        for it in texts[-2:]:
            k = hf_key(it["text"])
            if k:
                bottom[k] += 1
    thr = max(2, math.ceil(npages * 0.5))
    return ({k for k, c in top.items() if c >= thr}
            | {k for k, c in bottom.items() if c >= thr})


def heading_level_fn(fitz_doc, body_size):
    """返回 (is_heading_fn, bookmarks_used)：
    有书签 → 按书签标题匹配；无书签 → 按字号 ≥ body*1.18 的短行判标题"""
    toc = []
    try:
        toc = fitz_doc.get_toc() or []
    except Exception:
        toc = []
    if toc:
        toc_map = {}
        for lvl, title, _pg in toc:
            k = squash(title)
            if k:
                toc_map.setdefault(k, max(1, min(int(lvl), 6)))

        def by_toc(text):
            return toc_map.get(squash(text))
        return by_toc, toc_map

    def by_size(text, size):
        if size < body_size * 1.18:
            return None
        if len(text) > 60 or text[-1] in END_PUNCT:
            return None
        if PAGENUM_RE.match(text) or DOTLEADER_RE.search(text):
            return None
        if FIG_CAP_RE.match(text) or TBL_CAP_RE.match(text):
            return None
        return size

    return by_size, None


def build_heading_levels(heading_sizes):
    """去重降序字号 → {size: markdown # 级}（无书签模式）"""
    uniq = sorted(set(heading_sizes), reverse=True)
    return {s: min(i + 1, 6) for i, s in enumerate(uniq)}


def join_heading(a, b):
    """合并被 PDF 换行拆开的标题：中文直接相连，西文以空格相连"""
    if is_cjk(a[-1]) or is_cjk(b[0]):
        return a + b
    return a + " " + b


def render(fitz, doc, pages, stats, figures_dir, draft_dir, min_image_size):
    """三遍扫描：body 字号 → 页眉页脚 → 逐页渲染（标题重建/图像导出/计数）"""
    npages = len(pages)
    sizes = Counter(it["size"] for items in pages for it in items
                    if it["kind"] == "text")
    body_size = sizes.most_common(1)[0][0] if sizes else 10.0
    hf_keys = detect_header_footer(pages, npages)
    is_heading, toc_map = heading_level_fn(doc, body_size)

    size_levels = {}
    if toc_map is None:
        # 预扫一遍收集标题字号，统一分级
        cand_sizes = []
        for items in pages:
            for it in items:
                if it["kind"] == "text":
                    t = it["text"]
                    if hf_key(t) in hf_keys or PAGENUM_RE.match(t) or DOTLEADER_RE.search(t):
                        continue
                    if is_heading(t, it["size"]):
                        cand_sizes.append(it["size"])
        size_levels = build_heading_levels(cand_sizes)

    exported = {}          # xref → 文件名（跨页去重）
    img_seq = Counter()    # 页内图像序号（出现次序，含去重复用）
    out = []
    stats["unique_image_files"] = 0
    for pno, items in enumerate(pages, 1):
        out.append(PAGE_MARKER % pno)
        # 文本条目先过滤，再做标题合并（只在页内合并）
        kept = []
        for it in items:
            if it["kind"] == "image":
                kept.append(it)
                continue
            t = it["text"]
            if PAGENUM_RE.match(t):
                stats["headers_footers_filtered"] += 1
                continue
            if DOTLEADER_RE.search(t):
                stats["toc_lines_filtered"] += 1
                continue
            if hf_key(t) in hf_keys:
                stats["headers_footers_filtered"] += 1
                continue
            if FIG_CAP_RE.match(t):
                stats["figure_captions"] += 1
            elif TBL_CAP_RE.match(t):
                stats["table_captions"] += 1
            if EQNUM_RE.search(t):
                stats["equations"] += 1
            kept.append(it)

        consumed = set()
        for i, it in enumerate(kept):
            if it["kind"] == "image":
                line = export_image(fitz, doc, it, pno, exported, img_seq,
                                    stats, figures_dir, draft_dir, min_image_size)
                if line:
                    out.append(line)
                continue
            if i in consumed:
                continue
            text, size = it["text"], it["size"]
            level = None
            if toc_map is not None:
                level = is_heading(text)
                if level is None and i + 1 < len(kept) and kept[i + 1]["kind"] == "text":
                    # 书签标题被 PDF 拆成两行 → 拼接后再匹配
                    nxt = kept[i + 1]["text"]
                    if is_heading(join_heading(text, nxt)):
                        level = is_heading(join_heading(text, nxt))
                        text = join_heading(text, nxt)
                        consumed.add(i + 1)
            else:
                hs = is_heading(text, size)
                if hs is not None:
                    # 合并被拆开的同级标题（下一行也是候选、同字号、非编号起始）
                    j = i + 1
                    while (j < len(kept) and kept[j]["kind"] == "text"
                           and j not in consumed):
                        nt, ns = kept[j]["text"], kept[j]["size"]
                        if (ns == size and is_heading(nt, ns)
                                and not NUMBERING_RE.match(nt)):
                            text = join_heading(text, nt)
                            consumed.add(j)
                            j += 1
                        else:
                            break
                    level = size_levels.get(size)
            if level:
                stats["headings"] += 1
                out.append("#" * level + " " + text)
            else:
                out.append(text)
        out.append("")  # 页间空行
    stats["unique_image_files"] = len(exported)
    return "\n".join(out) + "\n"


def export_image(fitz, doc, it, pno, exported, img_seq, stats,
                 figures_dir, draft_dir, min_image_size):
    """尺寸/长宽比过滤 → PNG 导出 → 返回 markdown 图片引用行（被滤返回 None）"""
    w, h, xref = it.get("w", 0), it.get("h", 0), it.get("xref", 0)
    if xref <= 0 or w < min_image_size or h < min_image_size:
        stats["images_filtered"] += 1
        return None
    if min(w / h, h / w) < 0.08:  # 表格线/背景条类细长图
        stats["images_filtered"] += 1
        return None
    fname = exported.get(xref)
    img_seq[pno] += 1
    if fname is None:
        fname = "p%d_img%d.png" % (pno, img_seq[pno])
        try:
            pix = fitz.Pixmap(doc, xref)
            if pix.n - pix.alpha > 3:  # CMYK 等 → RGB
                pix = fitz.Pixmap(fitz.csRGB, pix)
            os.makedirs(figures_dir, exist_ok=True)
            pix.save(os.path.join(figures_dir, fname))
        except Exception as e:
            print("警告：p%d 图像 xref=%d 导出失败（%s），已跳过" % (pno, xref, e),
                  file=sys.stderr)
            stats["images_filtered"] += 1
            return None
        exported[xref] = fname
    stats["images_exported"] += 1
    rel = os.path.relpath(os.path.join(figures_dir, fname), draft_dir)
    return "![图 p%d-%d](%s)" % (pno, img_seq[pno], to_posix(rel))


def extract_refs(rendered_lines):
    """从渲染行中定位参考文献节 → 按 [N] 切分条目列表"""
    start = None
    for i, ln in enumerate(rendered_lines):
        plain = ln.lstrip("#").strip()
        if REFS_HEAD_RE.match(plain):
            start = i + 1
            break
    if start is None:
        return []
    region = []
    for ln in rendered_lines[start:]:
        plain = ln.lstrip("#").strip()
        if ln.startswith("#") or REFS_STOP_RE.match(plain):
            break
        if ln.startswith("%% [PDF p."):
            continue  # 跨页页标记不打断条目
        if plain:
            region.append(plain)
    if not region:
        return []
    joined = "\n".join(region)
    if re.search(r"\[\d+\]", joined):
        parts = re.split(r"\s*(?=\[\d+\])", joined)
    else:
        parts = region
    return [re.sub(r"\s+", " ", p).strip() for p in parts if p.strip()]


def count_tables(doc):
    """find_tables 启发式计表格数（失败降级 0 并告警一次）。
    PyMuPDF ≥1.24 会向 stdout 打印 pymupdf_layout 推广行，重定向吞掉，
    保证本脚本 stdout 只有 JSON（CLAUDE.md 脚本规范）。"""
    total = 0
    warned = False
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        for page in doc:
            try:
                total += len(page.find_tables().tables)
            except Exception as e:
                if not warned:
                    print("警告：find_tables 不可用（%s），tables 计 0" % e,
                          file=sys.stderr)
                    warned = True
    return total


def main():
    parser = argparse.ArgumentParser(
        prog="extract_pdf.py",
        description="paper-review PDF 全文提取（full-manuscript 专用）：全页无字符上限、"
                    "逐页 %% [PDF p.N] 页标记、无书签按字号重建标题并合并被拆标题、"
                    "过滤页眉页脚与目录点引线、图像按尺寸过滤导出、参考文献按 [N] 切分 "
                    "refs.txt、产出 pdf_source_counts.json 供 conversion_audit.py "
                    "--source-counts 回填。文献调研节选场景请用 lit-research 版 extract_pdf.py。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", metavar="FILE", required=True, help="输入 PDF 路径")
    parser.add_argument("--draft", metavar="FILE", required=True,
                        help="输出 draft.md 路径（父目录自动创建）")
    parser.add_argument("--figures-dir", metavar="DIR", default=None,
                        help="图像导出目录（默认 {draft 目录}/figures）")
    parser.add_argument("--refs-out", metavar="FILE", default=None,
                        help="参考文献切分产物（默认 {draft 目录}/refs.txt）")
    parser.add_argument("--counts-out", metavar="FILE", default=None,
                        help="源侧计数 JSON（默认 {draft 目录}/pdf_source_counts.json）")
    parser.add_argument("--min-image-size", metavar="N", type=int, default=150,
                        help="导出图像最小像素边长（宽高均须 ≥ 该值，默认 150）")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        fail("输入 PDF 不存在: %s" % args.input, 2)
    if args.min_image_size < 1:
        fail("--min-image-size 须 ≥ 1", 2)

    fitz = import_fitz()
    try:
        doc = fitz.open(args.input)
    except Exception as e:
        fail("无法打开 PDF（%s）——损坏或非 PDF 文件" % e, 1)
    if getattr(doc, "needs_pass", False) or getattr(doc, "is_encrypted", False):
        fail("PDF 受密码保护，无法直接提取——走 SKILL Step 0.3 密码保护回退链"
             "（PyMuPDF 抽文本 → find_tables 抽表 → 渲染页 PNG 后 Read 图像）", 1)

    draft_dir = os.path.dirname(os.path.abspath(args.draft))
    figures_dir = args.figures_dir or os.path.join(draft_dir, "figures")
    refs_out = args.refs_out or os.path.join(draft_dir, "refs.txt")
    counts_out = args.counts_out or os.path.join(draft_dir, "pdf_source_counts.json")

    try:
        pages = [page_items(doc[i]) for i in range(len(doc))]
    except Exception as e:
        fail("PDF 页面解析失败：%s" % e, 1)
    npages = len(pages)
    if npages == 0:
        fail("PDF 无页面内容", 1)

    stats = Counter()
    stats["pages"] = npages
    try:
        rendered = render(fitz, doc, pages, stats, figures_dir, draft_dir,
                          args.min_image_size)
        stats["tables"] = count_tables(doc)
    except Exception as e:
        fail("提取失败：%s" % e, 1)

    os.makedirs(draft_dir, exist_ok=True)
    try:
        with open(args.draft, "w", encoding="utf-8", newline="\n") as f:
            f.write(rendered)
    except OSError as e:
        fail("draft 写入失败：%s" % e, 1)

    refs = extract_refs(rendered.splitlines())
    stats["refs"] = len(refs)
    if refs:
        try:
            with open(refs_out, "w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(refs) + "\n")
        except OSError as e:
            fail("refs.txt 写入失败：%s" % e, 1)

    bookmarks = bool(toc_safe(doc))
    # figures 源侧估计：导出图像文件数与图题数取大（矢量图无 xref 时靠图题兜底）
    figures_est = max(stats.get("unique_image_files", 0),
                      stats.get("figure_captions", 0))
    counts = {
        "format": "pdf",
        "pages": npages,
        "tables": stats.get("tables", 0),
        "figures": figures_est,
        "equations": stats.get("equations", 0),
        "refs": stats.get("refs", 0),
        "figure_captions": stats.get("figure_captions", 0),
        "table_captions": stats.get("table_captions", 0),
        "images_exported": stats.get("images_exported", 0),
        "images_filtered": stats.get("images_filtered", 0),
        "headings": stats.get("headings", 0),
        "headers_footers_filtered": stats.get("headers_footers_filtered", 0),
        "toc_lines_filtered": stats.get("toc_lines_filtered", 0),
        "generator": "paper-review extract_pdf.py (full-manuscript)",
    }
    try:
        with open(counts_out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(counts, f, ensure_ascii=False, indent=2)
    except OSError as e:
        fail("计数 JSON 写入失败：%s" % e, 1)

    result = {
        "success": True,
        "input": to_posix(args.input),
        "draft": to_posix(args.draft),
        "pages": npages,
        "bookmarks": bookmarks,
        "headings": stats.get("headings", 0),
        "headers_footers_filtered": stats.get("headers_footers_filtered", 0),
        "toc_lines_filtered": stats.get("toc_lines_filtered", 0),
        "images_exported": stats.get("images_exported", 0),
        "images_filtered": stats.get("images_filtered", 0),
        "figure_captions": stats.get("figure_captions", 0),
        "table_captions": stats.get("table_captions", 0),
        "tables": stats.get("tables", 0),
        "equations": stats.get("equations", 0),
        "refs": stats.get("refs", 0),
        "refs_out": to_posix(refs_out) if refs else None,
        "figures_dir": to_posix(figures_dir),
        "counts_out": to_posix(counts_out),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


def toc_safe(doc):
    try:
        return doc.get_toc() or []
    except Exception:
        return []


if __name__ == "__main__":
    main()
