#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""diff_scope.py — paper-review 版本变更区域定位脚本

定位 v(N-1)→vN 两版 markdown 稿件的变更区域，输出行范围清单，
供核验式复审面板分域扫查（规格：变更区域全扫、未变更区域只做回归）。

机制：difflib.SequenceMatcher 对行序列求 opcodes，相邻变更合并为 hunk；
context>0 时每个 hunk 前后各扩 N 行，扩张后重叠/相接的 hunk 再合并。

hunk 字段：
  kind       replace / insert / delete（合并了多种类型 → replace）
  new_range  [起,止]，1-based 含头含尾；纯 delete 时新文件侧为空区间，
             表示为删除点所在两行之间位置 [i,i]（i=删除点前一行行号，
             删在文件头 → [1,1]）；纯 insert 的 old_range 同理
  old_range  同上（旧文件侧坐标）
  heading    新文件中该 hunk 之前最近的 markdown ATX 标题行文本
             （整行含 # 号；无则 null）；hunk 首行本身是标题时取该标题
  lines      涉及行数（新旧两侧核心行数取大者，不含 context 扩张）

new_headings：新文件有而旧文件没有的标题行文本列表（视同变更区域全扫）。

用法：
  python diff_scope.py --old v1.md --new v2.md [--output diff_scope.md] [--context 0]

输出文件（仅 --output 给出时写）：markdown 变更区域清单
  | # | 类型 | 新版行范围 | 所在章节 | 变更行数 | 表 + 「## 新增章节/标题」列表

stdout（JSON）：
  {"success": true, "old": "...", "new": "...", "hunks": [...],
   "changed_lines": N, "new_headings": [...], "output": "路径或null"}

退出码：0=成功；1=文件读写失败；2=参数错误。
"""
import argparse
import difflib
import io
import json
import os
import re
import sys

# 修复 Windows 下 GBK 编码问题，强制 UTF-8 输出
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# markdown ATX 标题：至多3个前导空格 + 1~6个# + 空白 + 正文
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S")


def to_posix(path):
    return path.replace("\\", "/")


def fail(msg, code=2):
    print("错误：%s" % msg, file=sys.stderr)
    sys.exit(code)


def read_lines(path):
    """读文件按行切分（utf-8-sig 优先，gbk 兜底）；失败返回 None"""
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read().splitlines()
        except UnicodeDecodeError:
            continue
        except OSError:
            return None
    return None


# ────────────────────────── 变更区域计算 ──────────────────────────

def to_range(start0, end0):
    """0-based 半开区间 → [起,止]（1-based 含头含尾）。
    空区间 → 插入/删除点位置 [i,i]：i=该位置前一行行号；文件头 → [1,1]"""
    if end0 > start0:
        return [start0 + 1, end0]
    pos = max(start0, 1)
    return [pos, pos]


def heading_at_or_before(new_lines, j1, j2):
    """新文件中 hunk（0-based 新文件侧区间 [j1,j2)）之前最近的标题行文本；
    hunk 首行本身是标题时取该标题；无则 None"""
    if j2 > j1 and HEADING_RE.match(new_lines[j1]):
        return new_lines[j1].strip()
    for k in range(min(j1, len(new_lines)) - 1, -1, -1):
        if HEADING_RE.match(new_lines[k]):
            return new_lines[k].strip()
    return None


def collect_new_headings(old_lines, new_lines):
    """新文件有而旧文件没有的标题行文本（保序去重）"""
    old_set = {ln.strip() for ln in old_lines if HEADING_RE.match(ln)}
    seen, out = set(), []
    for ln in new_lines:
        if HEADING_RE.match(ln):
            t = ln.strip()
            if t not in old_set and t not in seen:
                seen.add(t)
                out.append(t)
    return out


def compute_hunks(old_lines, new_lines, ctx):
    """opcodes → hunk 列表：按 context 扩张并合并重叠/相接的 hunk"""
    sm = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    spans = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        h = {
            "tags": [tag],
            "i1": max(0, i1 - ctx), "i2": min(len(old_lines), i2 + ctx),
            "j1": max(0, j1 - ctx), "j2": min(len(new_lines), j2 + ctx),
            "old_core": i2 - i1, "new_core": j2 - j1,
        }
        if spans and h["i1"] <= spans[-1]["i2"] and h["j1"] <= spans[-1]["j2"]:
            p = spans[-1]
            p["i2"] = max(p["i2"], h["i2"])
            p["j2"] = max(p["j2"], h["j2"])
            p["tags"] += h["tags"]
            p["old_core"] += h["old_core"]
            p["new_core"] += h["new_core"]
        else:
            spans.append(h)
    hunks = []
    for h in spans:
        kind = h["tags"][0] if len(set(h["tags"])) == 1 else "replace"
        hunks.append({
            "kind": kind,
            "new_range": to_range(h["j1"], h["j2"]),
            "old_range": to_range(h["i1"], h["i2"]),
            "heading": heading_at_or_before(new_lines, h["j1"], h["j2"]),
            "lines": max(h["old_core"], h["new_core"]),
        })
    return hunks


# ────────────────────────── markdown 清单输出 ──────────────────────────

def fmt_range(r):
    return str(r[0]) if r[0] == r[1] else "%d-%d" % (r[0], r[1])


def write_output(path, result):
    lines = [
        "# 变更区域清单（旧版 → 新版）",
        "",
        "- 旧版：%s" % result["old"],
        "- 新版：%s" % result["new"],
        "- 变更 hunk 数：%d；变更行数：%d" % (len(result["hunks"]), result["changed_lines"]),
        "",
        "| # | 类型 | 新版行范围 | 所在章节 | 变更行数 |",
        "|---|------|--------------|----------|----------|",
    ]
    for i, h in enumerate(result["hunks"], 1):
        lines.append("| %d | %s | %s | %s | %d |" % (
            i, h["kind"], fmt_range(h["new_range"]),
            (h["heading"] or "—").replace("|", "\\|"), h["lines"]))
    if not result["hunks"]:
        lines += ["", "（两版之间无变更）"]
    lines += ["", "## 新增章节/标题", ""]
    if result["new_headings"]:
        lines += ["- %s" % t for t in result["new_headings"]]
    else:
        lines.append("（无）")
    lines.append("")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


# ────────────────────────── 入口 ──────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="diff_scope.py",
        description="paper-review 版本变更区域定位：求 v(N-1)→vN 两版 markdown 稿件的"
                    "变更 hunk 行范围清单，供核验式复审面板分域扫查"
                    "（变更区域全扫、未变更区域只做回归）。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--old", metavar="FILE", required=True,
                        help="v(N-1) 版 markdown 稿件")
    parser.add_argument("--new", metavar="FILE", required=True,
                        help="vN 版 markdown 稿件")
    parser.add_argument("--output", metavar="FILE", default=None,
                        help="markdown 变更区域清单输出路径（缺省不写文件）")
    parser.add_argument("--context", metavar="N", type=int, default=0,
                        help="每个 hunk 前后各扩的上下文行数，扩张后重叠的 hunk 合并")
    args = parser.parse_args()

    if args.context < 0:
        fail("--context 不能为负数: %d" % args.context)
    for label, path in (("--old", args.old), ("--new", args.new)):
        if not os.path.isfile(path):
            fail("%s 文件不存在: %s" % (label, path), code=1)
    old_lines = read_lines(args.old)
    if old_lines is None:
        fail("无法读取 --old 文件: %s" % args.old, code=1)
    new_lines = read_lines(args.new)
    if new_lines is None:
        fail("无法读取 --new 文件: %s" % args.new, code=1)

    hunks = compute_hunks(old_lines, new_lines, args.context)
    result = {
        "success": True,
        "old": to_posix(os.path.abspath(args.old)),
        "new": to_posix(os.path.abspath(args.new)),
        "hunks": hunks,
        "changed_lines": sum(h["lines"] for h in hunks),
        "new_headings": collect_new_headings(old_lines, new_lines),
        "output": None,
    }
    if args.output:
        try:
            write_output(args.output, result)
        except OSError as e:
            fail("写入变更清单失败: %s" % e, code=1)
        result["output"] = to_posix(os.path.abspath(args.output))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
