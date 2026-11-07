#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""percent_basis.py — 百分比 vs 百分点口径检查器（S7 数值审计）

检查项输入（checks.json 单条）：
  {"id", "label", "before", "after", "stated_change",
   "stated_kind": "percent"|"point", "tolerance"=0.1}

复算规则：
  relative = (after − before) / before × 100   # before=0 → 记 error detail
  points   = after − before
  - stated_kind="percent" → 比对 relative；="point" → 比对 points
  - |expected − stated_change| ≤ tolerance → pass，否则 fail
  - 本口径不匹配但恰好匹配另一口径 → fail 且
    detail = "疑似百分比/百分点口径混淆（另一口径下为 X）"

run(check) 返回结果 dict：
  {"id","type","status","detail","label","before","after","stated_change",
   "stated_kind","relative","points","expected","delta"}

缺字段/非法数值 → 抛 ValueError（由 __main__ 统一转 status="error"）。
"""

DEFAULT_TOLERANCE = 0.1
KINDS = ("percent", "point")


def _num(x, field):
    """校验并转 float；bool/非数字 → ValueError"""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ValueError("字段 %s 必须是数字，实际为 %r" % (field, x))
    return float(x)


def run(check):
    cid = check.get("id") or "?"
    label = check.get("label") or ""
    before = _num(check.get("before"), "before")
    after = _num(check.get("after"), "after")
    stated = _num(check.get("stated_change"), "stated_change")
    kind = check.get("stated_kind")
    if kind not in KINDS:
        raise ValueError("stated_kind 必须是 percent 或 point，实际为 %r" % (kind,))
    tol = _num(check.get("tolerance", DEFAULT_TOLERANCE), "tolerance")

    if before == 0:
        return {"id": cid, "type": "percent_basis", "status": "error",
                "label": label,
                "detail": "before=0，相对百分比变化 (after−before)/before×100 无定义，"
                          "无法按 %s 口径复算" % kind}

    relative = (after - before) / before * 100.0
    points = after - before
    if kind == "percent":
        expected, other, kind_cn, other_cn = relative, points, "百分比", "百分点差"
    else:
        expected, other, kind_cn, other_cn = points, relative, "百分点", "相对百分比"
    delta = expected - stated

    result = {"id": cid, "type": "percent_basis", "label": label,
              "before": before, "after": after,
              "stated_change": stated, "stated_kind": kind,
              "relative": round(relative, 6), "points": round(points, 6),
              "expected": round(expected, 6), "delta": round(delta, 6)}
    if abs(delta) <= tol:
        result["status"] = "pass"
        result["detail"] = "%s口径复算 %.4f vs 稿件 %.4f（容差 %g）→ 一致" % (
            kind_cn, expected, stated, tol)
    elif abs(other - stated) <= tol:
        result["status"] = "fail"
        result["detail"] = ("疑似百分比/百分点口径混淆（另一口径下为 %.4f）：稿件按%s口径"
                            "声称变化 %.4f，但本口径复算为 %.4f，恰与%s吻合"
                            % (other, kind_cn, stated, expected, other_cn))
    else:
        result["status"] = "fail"
        result["detail"] = "%s口径复算 %.4f vs 稿件 %.4f（Δ=%+.4f，容差 %g）→ 不符" % (
            kind_cn, expected, stated, delta, tol)
    return result
