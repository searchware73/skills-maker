#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""abstract_numbers.py — 摘要数字↔正文交叉检查器（S7 数值审计）

检查项输入（checks.json 单条）：
  {"id", "abstract", "body_values": [{"value","label"}, ...],
   "require_numbers"=true, "tolerance"=0.01, "near_threshold"=0.05}

抽取规则：正则 \\d+(?:\\.\\d+)? 提取摘要数字，跳过：
  - 1900–2099 的整数年份
  - 纯序号（"1." "2." 等：单独整数后跟 "."，其后为标点/空白/行尾）

判定规则：
  - 摘要数字逐个在 body_values 找 |差| ≤ tolerance 的匹配；
    找不到 → fail 项 "摘要数字 X 正文无对应"，若最接近正文值的相对差
    < near_threshold（默认 5%）则附注 "（正文相近值：value/label）"
  - require_numbers 且摘要无数字 → warn "摘要零数字"
  - 全部匹配 → pass

run(check) 返回结果 dict：
  {"id","type","status","detail","label","numbers":[原文数字串,...],
   "unmatched":[{"value","text","nearest_value"?,"nearest_label"?,
                 "nearest_gap"?,"near_hint"?}, ...]}

缺字段/非法数值 → 抛 ValueError（由 __main__ 统一转 status="error"）。
"""
import re

DEFAULT_TOLERANCE = 0.01
DEFAULT_NEAR = 0.05          # 「正文相近值」提示阈值：相对差 < 5%
NUM_RE = re.compile(r"\d+(?:\.\d+)?")
YEAR_LO, YEAR_HI = 1900, 2099
# 整数后跟 "." 且其后为下列字符（或行尾）→ 视为纯序号跳过
_ORDINAL_NEXT = set("，。；：、！？,;:!?）)】》〉》\"'“”‘’ 　\t\r\n")


def _num(x, field):
    """校验并转 float；bool/非数字 → ValueError"""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ValueError("字段 %s 必须是数字，实际为 %r" % (field, x))
    return float(x)


def extract_numbers(text):
    """抽取摘要数字 → [(float, 原始字符串), ...]，跳过年份与纯序号"""
    out = []
    for m in NUM_RE.finditer(text):
        s = m.group(0)
        if "." not in s:                       # 单独整数才可能是年份/序号
            n = int(s)
            if YEAR_LO <= n <= YEAR_HI:
                continue                       # 年份
            rest = text[m.end():]
            if rest.startswith("."):
                tail = rest[1:2]
                if tail == "" or tail in _ORDINAL_NEXT:
                    continue                   # 纯序号 1./2.
        out.append((float(s), s))
    return out


def run(check):
    cid = check.get("id") or "?"
    label = check.get("label") or ""
    abstract = check.get("abstract")
    if not isinstance(abstract, str) or not abstract.strip():
        raise ValueError("abstract 必须是非空字符串")
    body = check.get("body_values")
    if body is None:
        body = []
    if not isinstance(body, list):
        raise ValueError("body_values 必须是列表")
    tol = _num(check.get("tolerance", DEFAULT_TOLERANCE), "tolerance")
    near = _num(check.get("near_threshold", DEFAULT_NEAR), "near_threshold")
    require = bool(check.get("require_numbers", True))

    pairs = []
    for i, b in enumerate(body):
        if not isinstance(b, dict):
            raise ValueError("body_values[%d] 必须是对象" % i)
        pairs.append((_num(b.get("value"), "body_values[%d].value" % i),
                      b.get("label") or ""))

    nums = extract_numbers(abstract)
    result = {"id": cid, "type": "abstract_numbers", "label": label,
              "numbers": [s for _, s in nums], "unmatched": []}
    if not nums:
        if require:
            result["status"] = "warn"
            result["detail"] = "摘要零数字（require_numbers=true，摘要应含关键定量结果）"
        else:
            result["status"] = "pass"
            result["detail"] = "摘要无数字（require_numbers=false，不强制）"
        return result

    unmatched = []
    for val, s in nums:
        if any(abs(val - bv) <= tol for bv, _ in pairs):
            continue
        item = {"value": val, "text": s}
        if pairs:
            bv, bl = min(pairs, key=lambda p: abs(val - p[0]))
            gap = abs(val - bv)
            rel = gap / abs(val) if val != 0 else float("inf")
            item["nearest_value"] = bv
            item["nearest_label"] = bl
            item["nearest_gap"] = round(gap, 6)
            if rel < near:
                item["near_hint"] = "正文相近值：%g/%s" % (bv, bl) if bl \
                    else "正文相近值：%g" % bv
        unmatched.append(item)

    result["unmatched"] = unmatched
    if unmatched:
        parts = []
        for it in unmatched:
            p = "摘要数字 %s 正文无对应" % it["text"]
            if it.get("near_hint"):
                p += "（%s）" % it["near_hint"]
            parts.append(p)
        result["status"] = "fail"
        result["detail"] = "；".join(parts)
    else:
        result["status"] = "pass"
        result["detail"] = "摘要 %d 个数字均在正文找到对应（容差 %g）" % (len(nums), tol)
    return result
