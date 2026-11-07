#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""table_sums.py — 表格行列和/勾稽检查器（S7 数值审计）

检查项输入（checks.json 单条）：
  {"id", "label", "rows": [{"label","cells":[数字,...],"stated_sum"}, ...],
   "tolerance"=0.05}

复算规则：
  每行 Σcells vs stated_sum，|差| ≤ tolerance → 该行 pass，否则 fail；
  整体 status = 全部行 pass 才 pass。

run(check) 返回结果 dict：
  {"id","type","status","detail","label","failed_rows",
   "rows":[{"label","cells","computed","stated_sum","delta","status"}, ...]}

缺字段/非法数值 → 抛 ValueError（由 __main__ 统一转 status="error"）。
"""

DEFAULT_TOLERANCE = 0.05


def _num(x, field):
    """校验并转 float；bool/非数字 → ValueError"""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ValueError("字段 %s 必须是数字，实际为 %r" % (field, x))
    return float(x)


def run(check):
    cid = check.get("id") or "?"
    label = check.get("label") or ""
    rows = check.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("rows 必须是非空列表")
    tol = _num(check.get("tolerance", DEFAULT_TOLERANCE), "tolerance")

    details = []
    n_fail = 0
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            raise ValueError("rows[%d] 必须是对象" % i)
        cells = r.get("cells")
        if not isinstance(cells, list):
            raise ValueError("rows[%d].cells 必须是列表" % i)
        nums = [_num(c, "rows[%d].cells[%d]" % (i, j))
                for j, c in enumerate(cells)]
        computed = sum(nums)
        stated = _num(r.get("stated_sum"), "rows[%d].stated_sum" % i)
        delta = computed - stated
        ok = abs(delta) <= tol
        if not ok:
            n_fail += 1
        details.append({
            "label": r.get("label") or "行%d" % (i + 1),
            "cells": nums,
            "computed": round(computed, 6),
            "stated_sum": stated,
            "delta": round(delta, 6),
            "status": "pass" if ok else "fail",
        })

    overall = "pass" if n_fail == 0 else "fail"
    detail = "共 %d 行，%d 行勾稽失败（容差 %g）" % (len(details), n_fail, tol)
    if n_fail:
        detail += "：" + "；".join(
            "%s 复算 %.4f vs 稿件 %.4f（Δ=%+.4f）"
            % (d["label"], d["computed"], d["stated_sum"], d["delta"])
            for d in details if d["status"] == "fail")
    return {"id": cid, "type": "table_sums", "status": overall,
            "label": label, "rows": details, "failed_rows": n_fail,
            "detail": detail}
