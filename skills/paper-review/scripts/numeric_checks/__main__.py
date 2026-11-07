#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""__main__.py — paper-review v2.0 S7 数值审计：复算检查库入口

用法（Python 直接执行目录即运行本 __main__.py，任意 cwd 可用）：
  python skills/paper-review/scripts/numeric_checks --input checks.json [--output recalc.md]

输入 JSON：{"checks": [{...}, ...]}，按每条 "type" 分发到四个检查器：
  - weighted_identity：混合口径加权自洽（Σweight×value vs stated_total）
  - table_sums       ：表格行列和/勾稽（逐行 Σcells vs stated_sum）
  - abstract_numbers ：摘要数字↔正文交叉（正则抽取 + 容差匹配）
  - percent_basis    ：百分比 vs 百分点口径（relative/points 双口径比对）
未知 type → 该条 status="error"（detail 说明），整体仍 exit 0。

--output 写「S7 复算表」markdown（缺省不写文件）：
  | ID | 检查 | 标签 | 复算值 | 稿件值 | Δ | 判定 |
  每 check 一行；table_sums 每失败行单独一行（ID 加行标签后缀，如 c2/Ex）；
  判定列 ∈ pass/fail/warn/error。

stdout（JSON）：
  {"success": true, "total": N, "pass": N, "fail": N, "warn": N, "error": N,
   "results": [{"id","type","status","detail",...每条完整明细...}],
   "output": "path"|null}

退出码：0=成功（含存在 fail/warn/error 检查项）；
        1=输入文件读不了/JSON 非法/复算表写不出；2=参数错误。
"""
import argparse
import io
import json
import os
import sys

# 修复 Windows 下 GBK 编码问题，强制 UTF-8 输出
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 以 `python <目录>` 方式运行时包内相对导入不可用：
# 把自身目录插入 sys.path 后按模块名绝对导入，保证从任意 cwd 可运行
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import abstract_numbers    # noqa: E402
import percent_basis       # noqa: E402
import table_sums          # noqa: E402
import weighted_identity   # noqa: E402

HANDLERS = {
    "weighted_identity": weighted_identity.run,
    "table_sums": table_sums.run,
    "abstract_numbers": abstract_numbers.run,
    "percent_basis": percent_basis.run,
}

MD_HEADER = ("| ID | 检查 | 标签 | 复算值 | 稿件值 | Δ | 判定 |\n"
             "|----|------|------|--------|--------|------|------|")


def to_posix(path):
    return path.replace("\\", "/")


def fail(msg, code=2):
    print("错误：%s" % msg, file=sys.stderr)
    sys.exit(code)


# ────────────────────────── 分发 ──────────────────────────

def run_check(check):
    """单条检查 → 结果 dict；未知 type / 非法输入 / 检查器异常 → status=error"""
    if not isinstance(check, dict):
        return {"id": "?", "type": None, "status": "error",
                "detail": "检查项必须是 JSON 对象，实际为 %s" % type(check).__name__}
    ctype = check.get("type")
    cid = check.get("id") or "?"
    handler = HANDLERS.get(ctype)
    if handler is None:
        return {"id": cid, "type": ctype, "status": "error",
                "label": check.get("label") or "",
                "detail": "未知检查类型: %r（支持：%s）"
                          % (ctype, "、".join(sorted(HANDLERS)))}
    try:
        return handler(check)
    except ValueError as e:
        return {"id": cid, "type": ctype, "status": "error",
                "label": check.get("label") or "",
                "detail": "检查项输入不合法：%s" % e}
    except Exception as e:   # 兜底：单条崩溃不影响整体审计
        return {"id": cid, "type": ctype, "status": "error",
                "label": check.get("label") or "",
                "detail": "检查器异常：%s: %s" % (type(e).__name__, e)}


# ────────────────────────── S7 复算表 markdown ──────────────────────────

def _fmt(v):
    """单元格显示：None → —；float → %g（去尾零）；其余 str"""
    if v is None:
        return "—"
    if isinstance(v, float):
        return "%g" % round(v, 6)
    return str(v)


def _display_values(r):
    """按类型取（复算值, 稿件值, Δ）用于表格显示"""
    rtype = r.get("type")
    if rtype == "weighted_identity":
        return r.get("computed"), r.get("stated_total"), r.get("delta")
    if rtype == "percent_basis":
        return r.get("expected"), r.get("stated_change"), r.get("delta")
    if rtype == "abstract_numbers":
        unmatched = "、".join(it.get("text", "?") for it in r.get("unmatched", []))
        return None, (unmatched or None), None
    return None, None, None


def md_rows(results):
    """结果列表 → 表格行 [(id, type, label, computed, stated, delta, status)]
    table_sums 每失败行单独一行（ID 加行标签后缀）；其余每 check 一行"""
    rows = []
    for r in results:
        rid = r.get("id") or "?"
        rtype = r.get("type") or "?"
        label = r.get("label") or ""
        status = r.get("status") or "?"
        if rtype == "table_sums" and r.get("failed_rows"):
            for d in r.get("rows", []):
                if d.get("status") != "fail":
                    continue
                rows.append(("%s/%s" % (rid, d.get("label") or "?"), rtype, label,
                             d.get("computed"), d.get("stated_sum"),
                             d.get("delta"), "fail"))
        else:
            computed, stated, delta = _display_values(r)
            rows.append((rid, rtype, label, computed, stated, delta, status))
    return rows


def write_markdown(results, path):
    lines = ["# S7 复算表", "", MD_HEADER]
    for rid, rtype, label, computed, stated, delta, status in md_rows(results):
        lines.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            rid, rtype, label or "—", _fmt(computed), _fmt(stated),
            _fmt(delta), status))
    lines.append("")
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


# ────────────────────────── 主流程 ──────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="numeric_checks",
        description="paper-review v2.0 S7 数值审计复算检查库：按 checks.json 逐条复算"
                    "（weighted_identity/table_sums/abstract_numbers/percent_basis），"
                    "stdout 输出 JSON 汇总，可选写「S7 复算表」markdown。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", metavar="FILE", required=True,
                        help='检查项 JSON 文件：{"checks": [{...}, ...]}')
    parser.add_argument("--output", metavar="FILE", default=None,
                        help="S7 复算表 markdown 输出路径（缺省不写文件）")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        fail("输入文件不存在: %s" % args.input, code=1)
    try:
        with open(args.input, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:   # ValueError 覆盖 json.JSONDecodeError
        fail("读取/解析输入 JSON 失败: %s" % e, code=1)
    checks = data.get("checks") if isinstance(data, dict) else None
    if not isinstance(checks, list):
        fail('输入 JSON 必须是含 "checks" 列表的对象', code=1)

    results = [run_check(c) for c in checks]
    counts = {"pass": 0, "fail": 0, "warn": 0, "error": 0}
    for r in results:
        counts[r.get("status") if r.get("status") in counts else "error"] += 1

    out_path = None
    if args.output:
        try:
            write_markdown(results, args.output)
        except OSError as e:
            fail("写入 S7 复算表失败: %s" % e, code=1)
        out_path = to_posix(os.path.abspath(args.output))

    print(json.dumps({
        "success": True,
        "total": len(results),
        "pass": counts["pass"],
        "fail": counts["fail"],
        "warn": counts["warn"],
        "error": counts["error"],
        "results": results,
        "output": out_path,
    }, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
