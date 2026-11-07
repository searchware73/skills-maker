#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""weighted_identity.py — 混合口径加权自洽检查器（S7 数值审计）

检查项输入（checks.json 单条）：
  {"id", "label", "components": [{"name","weight","value"}, ...],
   "stated_total", "tolerance"=0.01}

复算规则：
  computed   = Σ(weight × value)
  weight_sum = Σweight
  - |weight_sum − 1| > tolerance → 附加 warning "权重和≠1"，
    并给出 normalized = computed / weight_sum（判定仍用 computed vs stated_total）
  - |computed − stated_total| ≤ tolerance → pass，否则 fail
  - delta = computed − stated_total

run(check) 返回结果 dict：
  {"id","type","status","detail","label","computed","weight_sum",
   "stated_total","delta","components":[...],"warning"?,"normalized"?}

缺字段/非法数值 → 抛 ValueError（由 __main__ 统一转 status="error"）。
"""

DEFAULT_TOLERANCE = 0.01


def _num(x, field):
    """校验并转 float；bool/非数字 → ValueError"""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ValueError("字段 %s 必须是数字，实际为 %r" % (field, x))
    return float(x)


def run(check):
    cid = check.get("id") or "?"
    label = check.get("label") or ""
    components = check.get("components")
    if not isinstance(components, list) or not components:
        raise ValueError("components 必须是非空列表")
    tol = _num(check.get("tolerance", DEFAULT_TOLERANCE), "tolerance")
    stated = _num(check.get("stated_total"), "stated_total")

    computed = 0.0
    weight_sum = 0.0
    items = []
    for i, c in enumerate(components):
        if not isinstance(c, dict):
            raise ValueError("components[%d] 必须是对象" % i)
        w = _num(c.get("weight"), "components[%d].weight" % i)
        v = _num(c.get("value"), "components[%d].value" % i)
        computed += w * v
        weight_sum += w
        items.append({"name": c.get("name") or "分量%d" % (i + 1),
                      "weight": w, "value": v, "product": round(w * v, 6)})

    delta = computed - stated
    ok = abs(delta) <= tol
    result = {
        "id": cid,
        "type": "weighted_identity",
        "status": "pass" if ok else "fail",
        "label": label,
        "computed": round(computed, 6),
        "weight_sum": round(weight_sum, 6),
        "stated_total": stated,
        "delta": round(delta, 6),
        "components": items,
        "detail": "复算加权和 %.4f vs 稿件 %.4f（Δ=%+.4f，容差 %g）→ %s"
                  % (computed, stated, delta, tol, "自洽" if ok else "不自洽"),
    }
    if abs(weight_sum - 1.0) > tol:
        result["warning"] = "权重和≠1"
        if weight_sum != 0:
            result["normalized"] = round(computed / weight_sum, 6)
        result["detail"] += "；警告：权重和≠1（Σw=%.4f）" % weight_sum
    return result
