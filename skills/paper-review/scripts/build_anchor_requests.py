#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_anchor_requests.py — 从 merged_findings.md 自动构建 anchor_requests.json

背景（备忘 §十一 条目20，2026-11-10 两篇实测）：SKILL 3.2a 原要求手写请求表，
两篇实测都只能临时写 Python 抽行，且位置列格式不统一（L123 / 行123 / §5.2 第3段 /
表5-6），首次抽取 0 条请求。本脚本把该步骤脚本化：

  - 解析 merged_findings.md 全部表格行（内容 R-# / 语言 D-#；S-# 交叉引用行跳过，
    其对应 R-/D- 条目已各自在表中），提取 ID/位置/原句引文；
  - 位置解析兼容 `L\\d+`、`行\\s*\\d+`（→ draft_line）、`§X.Y`、`表N`/`式N`/`图N`
    （→ structural 结构坐标）；
  - 引文取「问题/建议」列中「」/“”/『』/"" 包裹的最长片段：
      · 不足 15 字，或含省略号（示意性片段非连续原句）→ weak；
      · 在 draft 中多处命中 → ambiguous；未命中 → not_in_draft
        （示意性引文跳过存在性核查，避免必然误报）；
      · 三类均进「待人工补引文」清单（needs_manual_quote），不得静默丢弃；
      · 无内嵌引文 → quote 置空，同样进待补清单（fill 侧保留为 structural_only）；
  - 无行号项（跨节/文末）显式标 structural_only；
  - draft 唯一命中时顺带回填 draft_line（与 anchor_map.py fill 的反查口径一致，
    复用其 norm/squash 归一化）。

输出文件（--output，默认 {run_dir}anchor_requests.json）：
  {"generated_by": "build_anchor_requests.py", "merged": "...", "draft": "...",
   "stats": {...}, "needs_manual_quote": [{"id": "R-1", "reason": "..."}],
   "entries": [{"id", "quote", "draft_line", "structural",
                "weak"?, "ambiguous"?, "not_in_draft"?, "structural_only"?}]}
  （anchor_map.py fill 直接读 entries 键；多余标志字段不影响 fill）

stdout（JSON）：
  {"success": true, "output": "...", "merged": "...", "draft": "...",
   "stats": {"total": N, "with_quote": N, "without_quote": N, "weak": N,
             "ambiguous": N, "not_in_draft": N, "structural_only": N},
   "needs_manual_quote": ["R-1", ...], "needs_manual_count": N}

用法：
  python build_anchor_requests.py --run-dir DIR [--merged FILE] [--draft FILE]
                                  [--output FILE]

退出码：0=成功（total=0 也成功，stderr 提示）；1=输入/输出文件失败；2=参数错误。
"""
import argparse
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anchor_map as am          # noqa: E402  norm/squash 归一化（与 fill 同口径）
import merge_findings as mf      # noqa: E402  _read_md/_v2_table_rows/_v2_pick/V2_ID_RE

# 修复 Windows 下 GBK 编码问题，强制 UTF-8 输出
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

MIN_QUOTE_LEN = 15               # 引文下限（字符数，归一化后）

# 内嵌引文：「」/『』/“”/"" 包裹的片段
QUOTE_SPAN_RES = [
    re.compile(r"「([^「」]+)」"),
    re.compile(r"『([^『』]+)』"),
    re.compile(r"“([^“”]+)”"),
    re.compile(r'"([^"]+)"'),
]

# 位置 → 行号：L142 / L 142 / 行142 / 行 142
LOC_LINE_RES = [
    re.compile(r"\bL\s*(\d+)"),
    re.compile(r"行\s*(\d+)"),
]
# 位置中剥掉行号 token 后剩余的即结构坐标（§X.Y / 表N / 式N / 第N段…）
LOC_LINE_STRIP_RE = re.compile(r"\bL\s*\d+|行\s*\d+")
# 含省略号的引文是「示意性片段」而非连续原句，draft 存在性核查必然误报
ELLIPSIS_RE = re.compile(r"…|\.\.\.")

ACCEPTED_PREFIXES = ("R", "D")   # S-# 为交叉引用行，不重复生成请求


def fail(msg, code=1):
    print("错误：%s" % msg, file=sys.stderr)
    sys.exit(code)


def extract_quote(text):
    """从问题/建议文本中抽取最长的内嵌引文片段；无则返回 ""。"""
    best = ""
    for rx in QUOTE_SPAN_RES:
        for m in rx.finditer(text or ""):
            cand = m.group(1).strip()
            if len(cand) > len(best):
                best = cand
    return best


def parse_loc(loc):
    """位置列 → (draft_line|None, structural)。兼容 L\\d+ / 行\\d+ / §X.Y / 表N / 式N。"""
    loc = (loc or "").strip()
    if not loc or loc in ("—", "-", "–"):
        return None, ""
    draft_line = None
    for rx in LOC_LINE_RES:
        m = rx.search(loc)
        if m:
            draft_line = int(m.group(1))
            break
    structural = LOC_LINE_STRIP_RE.sub("", loc)
    structural = re.sub(r"\s{2,}", " ", structural).strip(" ，,、;；")
    if structural in ("—", "-", "–"):
        structural = ""
    return draft_line, structural


def parse_merged_items(path):
    """merged_findings.md → [{id, loc, desc, sugg}]（全部表格，按出现序，id 去重）"""
    lines = mf._read_md(path)
    if lines is None:
        fail("merged_findings.md 不存在或不可读: %s（先跑阶段3.1 merge_findings.py）"
             % path)
    items, seen = [], set()
    i, n = 0, len(lines)
    while i < n:
        if lines[i].strip().startswith("|"):
            rows, j = mf._v2_table_rows(lines, i, stop_at_heading=False)
            for row in rows:
                id_cell = mf._v2_pick(row, "ID")
                m = mf.V2_ID_RE.search(id_cell)
                if not m or m.group(1) not in ACCEPTED_PREFIXES:
                    continue                    # 无 ID / S-# 交叉引用行：跳过
                rid = m.group(0)
                if rid in seen:
                    continue
                seen.add(rid)
                items.append({
                    "id": rid,
                    "loc": mf._v2_pick(row, "位置"),
                    "desc": mf._v2_pick(row, "问题"),
                    "sugg": mf._v2_pick(row, "建议"),
                })
            i = max(j, i + 1)
        else:
            i += 1
    return items


def draft_index(draft_path):
    """draft 行列表（归一化查找用）；未提供/不存在返回 None"""
    if not draft_path:
        return None
    lines = am.draft_lines_of(draft_path)
    if lines is None:
        print("警告：draft 不存在，跳过引文唯一性核查: %s" % draft_path, file=sys.stderr)
    return lines


def count_in_draft(quote, dlines):
    """引文在 draft 中的命中 (总次数, 唯一行号|None)；两级归一化与 fill 同口径。
    引文过短（两级归一化后均 <8 字符）无法可靠核查时返回 (None, None)——
    区别于「核查过但未命中」的 (0, None)，短引文只标 weak 不标 not_in_draft。"""
    if not dlines:
        return None, None
    checked = False
    for needle, transform in ((am.norm(quote), am.norm),
                              (am.squash(quote), am.squash)):
        if len(needle) < 8:
            continue
        checked = True
        total, hit_line = 0, None
        for ln, line in enumerate(dlines, 1):
            c = transform(line).count(needle)
            if c:
                total += c
                hit_line = ln
        if total:
            return total, (hit_line if total == 1 else None)
    return (0, None) if checked else (None, None)


def build_entries(items, dlines):
    entries, needs_manual = [], []
    stats = {"total": 0, "with_quote": 0, "without_quote": 0, "weak": 0,
             "ambiguous": 0, "not_in_draft": 0, "structural_only": 0}

    def _manual(rid, reason):
        needs_manual.append({"id": rid, "reason": reason})

    for it in items:
        stats["total"] += 1
        draft_line, structural = parse_loc(it["loc"])
        quote = extract_quote(it["desc"]) or extract_quote(it["sugg"])
        entry = {"id": it["id"]}
        if not quote:
            stats["without_quote"] += 1
            entry["quote"] = ""
            _manual(it["id"], "无内嵌引文（「」/“”片段缺失），需人工从 draft 摘 ≥%d 字唯一原句"
                    % MIN_QUOTE_LEN)
        else:
            stats["with_quote"] += 1
            entry["quote"] = quote
            schematic = bool(ELLIPSIS_RE.search(quote))
            short = len(am.norm(quote)) < MIN_QUOTE_LEN
            if schematic or short:
                entry["weak"] = True
                stats["weak"] += 1
                if schematic:
                    _manual(it["id"], "引文含省略号，为示意性片段而非连续原句，"
                                      "需人工从 draft 摘 ≥%d 字连续原句" % MIN_QUOTE_LEN)
                else:
                    _manual(it["id"], "引文仅 %d 字（<%d），可能不唯一，建议加长"
                            % (len(am.norm(quote)), MIN_QUOTE_LEN))
            # 示意性引文跳过存在性核查（必然 0 命中，标 not_in_draft 属误报）
            hits, uniq_line = (None, None) if schematic \
                else count_in_draft(quote, dlines)
            if hits is not None:
                if hits == 0:
                    entry["not_in_draft"] = True
                    stats["not_in_draft"] += 1
                    _manual(it["id"], "引文未在 draft 命中（可能非原句/跨行改写），需人工核对")
                elif hits > 1:
                    entry["ambiguous"] = True
                    stats["ambiguous"] += 1
                    _manual(it["id"], "引文在 draft 命中 %d 处，需人工加长引文使其唯一" % hits)
                elif draft_line is None:
                    draft_line = uniq_line      # 唯一命中：回填行号
        if draft_line is None:
            entry["structural_only"] = True     # 无行号项（跨节/文末）显式标注
            stats["structural_only"] += 1
        entry["draft_line"] = draft_line
        entry["structural"] = structural
        entries.append(entry)
    return entries, needs_manual, stats


def main():
    parser = argparse.ArgumentParser(
        prog="build_anchor_requests.py",
        description="从 merged_findings.md 自动构建 anchor_requests.json（条目20："
                    "取代 3.2a 手写请求表；weak/ambiguous/无引文项进待补清单，不静默丢弃）。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--run-dir", required=True, metavar="DIR",
                        help="本轮产物目录（.review/rN/）")
    parser.add_argument("--merged", default=None, metavar="FILE",
                        help="merged_findings.md 路径（默认 {run_dir}merged_findings.md）")
    parser.add_argument("--draft", default=None, metavar="FILE",
                        help="draft.md 路径（提供则做引文唯一性核查并回填行号）")
    parser.add_argument("--output", default=None, metavar="FILE",
                        help="输出 JSON（默认 {run_dir}anchor_requests.json）")
    args = parser.parse_args()

    merged = args.merged or os.path.join(args.run_dir, "merged_findings.md")
    output = args.output or os.path.join(args.run_dir, "anchor_requests.json")

    items = parse_merged_items(merged)
    if not items:
        print("警告：merged_findings.md 未解析出任何 R-#/D-# 条目", file=sys.stderr)
    dlines = draft_index(args.draft)
    entries, needs_manual, stats = build_entries(items, dlines)

    payload = {
        "generated_by": "build_anchor_requests.py",
        "merged": am.to_posix(os.path.abspath(merged)),
        "draft": am.to_posix(os.path.abspath(args.draft)) if args.draft else None,
        "stats": stats,
        "needs_manual_quote": needs_manual,
        "entries": entries,
    }
    try:
        d = os.path.dirname(os.path.abspath(output))
        os.makedirs(d, exist_ok=True)
        with open(output, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except OSError as e:
        fail("写入输出文件失败: %s" % e)

    result = {
        "success": True,
        "output": am.to_posix(os.path.abspath(output)),
        "merged": payload["merged"],
        "draft": payload["draft"],
        "stats": stats,
        "needs_manual_quote": [m["id"] for m in needs_manual],
        "needs_manual_count": len(needs_manual),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
