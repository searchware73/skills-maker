#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""merge_findings.py — paper-review 审查发现合并脚本（v2.0 双模式）

═══ v2 模式（--run-dir，v2.0 起默认）═══
  输入为两份权威结构化清单（不再是三来源自由文本）：
    revision_roadmap.md  → 阶段1 面板 Revision Roadmap（内容发现，稳定 ID R-#）
    deai_confirmed.md    → 阶段2 确认AI问题清单（语言发现，稳定 ID D-#）
  仅对重叠打标项做交叉引用（S-#），不做跨源模糊去重；
  config.json 撤回记录中的 ID 不得复活（withdrawn_skipped）。

  用法：
    python merge_findings.py --run-dir DIR [--roadmap FILE] [--deai FILE] [--output FILE]

  输出（stdout，JSON）：
    {"success": true, "mode": "v2", "p0": N, "p1": N, "p2": N, "total": N,
     "content_items": N, "deai_items": N, "cross_refs": N,
     "withdrawn_skipped": [...], "decision": "...", "quality_score": "38/50",
     "output": "...", "sources_missing": [...]}

═══ v1 兼容模式（--review-dir，保留一个版本后移除）═══
  功能：
  1. 读取 review_dir 下三个来源文件（存在哪个读哪个，缺失跳过并提示）：
       deai_log.md           → 来源标签「去AI审查」
       discussion_minutes.md → 来源标签「多智能体研讨」
       peer_reports.md       → 来源标签「同行评审」
  2. 从各文件解析结构化发现（两类格式均支持）：
       a) Markdown 表格：含「位置/问题/建议」类列的表（严重度取所在小节标题 P0/P1/P2）
       b) 列表条目：形如「1. [P0] 位置：§1.2 第3段 / 问题：… / 建议：…」
     discussion_minutes.md 启用小节白名单：只解析「共识发现」及 P0/P1/P2 小节，
     叙述性小节（参与角色/分歧记录/评分汇总/决议信散文）内的表格行与
     含严重度字样的文字不解析为发现（防噪声）。
  3. 按「位置 + 问题类型」去重（同类同位置视为同一问题，合并来源标注）
  4. 严重度分级（显式 [P0]/[P1]/[P2] 标注优先，否则按关键词推断）：
       P0 必须修改：事实错误、引用错误、逻辑断裂
       P1 重要修改：AI痕迹、结构问题、术语错误
       P2 建议修改：措辞润色、语句打磨
  5. 输出合并清单 merged_findings.md + stdout JSON

  用法：
    python merge_findings.py --review-dir DIR [--output FILE]

  输出（stdout，JSON）：
    {"mode": "v1", "p0": N, "p1": N, "p2": N, "total": N, "output": "...",
     "sources_parsed": [...], "sources_missing": [...], "duplicates_removed": N}

退出码：0=成功（即使发现数为0）；1=输入/输出文件读写失败；2=参数错误。
"""
import argparse
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

SOURCES = [
    # (文件名, 来源标签, 是否启用小节白名单)
    # 白名单：discussion_minutes.md 的叙述性小节（参与角色/分歧记录/评分汇总）中
    # 含 P0/P1/P2 字样或表格行的散文会被误解析为发现（实测噪声来源），
    # 故只解析「共识发现」及 P0/P1/P2 严重度小节下的内容。
    ("deai_log.md", "去AI审查", False),
    ("discussion_minutes.md", "多智能体研讨", True),
    ("peer_reports.md", "同行评审", False),
]

# 白名单模式下允许解析的小节标题（## / ### 级）
ALLOWED_SECTION_RE = re.compile(
    r"(共识发现|结构化发现|\bP[012]\b|必须修改|重要修改|建议修改)", re.IGNORECASE)
# 明确排除的叙述性小节（即使其中出现严重度字样也不解析）
PROSE_SECTION_RE = re.compile(r"(参与角色|分歧记录|评分汇总|背景|说明|决议信)")

# 关键词 → (级别, 类型标签)。类型标签用于「位置+类型」去重。
P0_RULES = [
    ("事实错误", "factual"), ("数据错误", "factual"), ("factual", "factual"),
    ("引用错误", "citation"), ("引用不实", "citation"), ("与原文不符", "citation"),
    ("过度延伸", "citation"), ("citation", "citation"),
    ("逻辑断裂", "logic"), ("逻辑漏洞", "logic"), ("逻辑错误", "logic"),
    ("逻辑跳跃", "logic"), ("因果", "logic"), ("跳跃", "logic"),
    ("循环论证", "logic"), ("自相矛盾", "logic"),
    ("结论超出", "logic"), ("逻辑", "logic"),
    ("过度声明", "over-claim"), ("over-claim", "over-claim"), ("overclaim", "over-claim"),
]
P1_RULES = [
    ("ai痕迹", "ai-trace"), ("ai味", "ai-trace"), ("ai写作", "ai-trace"),
    ("对仗", "ai-trace"), ("排比", "ai-trace"), ("空洞总结", "ai-trace"),
    ("套话", "ai-trace"), ("tier1", "ai-trace"), ("tier2", "ai-trace"),
    ("跨节引用", "structure"), ("结构", "structure"), ("字数", "structure"),
    ("重复", "structure"), ("引用格式", "citation-format"), ("编号", "citation-format"),
    ("遗漏", "missing-lit"), ("术语", "terminology"),
]
P2_RULES = [
    ("措辞", "wording"), ("润色", "wording"), ("句式", "wording"), ("语句", "wording"),
    ("表达", "wording"), ("过渡", "wording"), ("wording", "wording"), ("polish", "wording"),
    ("标点", "punctuation"), ("错别字", "typo"),
]

SEV_TITLES = [("P0", "P0 — 必须修改"), ("P1", "P1 — 重要修改"), ("P2", "P2 — 建议修改")]

SEV_MARKER_RE = re.compile(r"(?:严重度\s*[:：]?\s*)?\[?\b(P[012])\b\]?", re.IGNORECASE)
LIST_START_RE = re.compile(r"^(?:\d+[.、)]|[-*•])\s+")
LABELED_RES = [
    ("loc", re.compile(r"位置[:：]\s*(.+)$")),
    ("desc", re.compile(r"问题[:：]\s*(.+)$")),
    ("sugg", re.compile(r"建议[:：]\s*(.+)$")),
]


def classify(desc, explicit=None):
    """返回 (severity, type_tag)。explicit 显式标注优先；否则按关键词推断；默认 P2/other。"""
    text = desc.lower()
    sev, tag = None, "other"
    for rules, level in ((P0_RULES, "P0"), (P1_RULES, "P1"), (P2_RULES, "P2")):
        for kw, t in rules:
            if kw in text:
                sev, tag = level, t
                break
        if sev:
            break
    if explicit in ("P0", "P1", "P2"):
        sev = explicit
    return sev or "P2", tag


def heading_severity(line):
    """若为标题行，返回 (True, P0/P1/P2 或 None)；否则 (False, None)"""
    if not line.lstrip().startswith("#"):
        return False, None
    up = line.upper()
    if "P0" in up or "必须修改" in line:
        return True, "P0"
    if "P1" in up or "重要修改" in line:
        return True, "P1"
    if "P2" in up or "建议修改" in line:
        return True, "P2"
    return True, None


def is_sep_row(cells):
    return all(c and set(c) <= set("-: ") for c in cells)


def find_col(header, names, excludes=()):
    for idx, h in enumerate(header):
        hl = h.lower()
        if hl in [x.lower() for x in excludes]:
            continue
        for nm in names:
            if nm.lower() in hl:
                return idx
    return None


def parse_table(block, cur_sev, source_label):
    """解析一个 Markdown 表格块（连续的 | 开头行），返回 finding 列表"""
    rows = [[c.strip() for c in r.strip("|").split("|")] for r in block]
    if len(rows) < 2:
        return []
    header = rows[0]
    loc_i = find_col(header, ["位置", "行号", "段落", "章节"])
    desc_i = find_col(header, ["问题", "描述", "发现"], excludes=["发现数"])
    sugg_i = find_col(header, ["建议"])
    sev_i = find_col(header, ["严重度", "级别"])
    src_i = find_col(header, ["来源", "支持角色", "角色", "技能"])
    if desc_i is None:
        return []  # 非发现类表格（如去AI日志汇总表、评分汇总表）→ 跳过
    findings = []
    for r in rows[1:]:
        if is_sep_row(r) or len(r) <= desc_i:
            continue
        desc = r[desc_i].strip()
        if not desc or desc in ("...", "…", "—"):
            continue
        loc = r[loc_i].strip() if loc_i is not None and len(r) > loc_i else ""
        sugg = r[sugg_i].strip() if sugg_i is not None and len(r) > sugg_i else ""
        explicit = None
        if sev_i is not None and len(r) > sev_i:
            m = re.search(r"P[012]", r[sev_i].upper())
            explicit = m.group(0) if m else None
        if explicit is None:
            m = re.search(r"\bP([012])\b", desc)
            explicit = ("P" + m.group(1)) if m else cur_sev
        sev, tag = classify(desc, explicit)
        source = source_label
        if src_i is not None and len(r) > src_i and r[src_i].strip():
            source = "%s·%s" % (source_label, r[src_i].strip())
        findings.append({"source": source, "loc": loc, "desc": desc,
                         "sugg": sugg, "sev": sev, "tag": tag})
    return findings


LABEL_LINE_RE = re.compile(r"^(?:位置|问题|建议)\s*[:：]")


def is_item_start(s):
    """判断（去表格后的）行是否为一个新的条目式发现的起点"""
    if LIST_START_RE.match(s) and SEV_MARKER_RE.search(s):
        return True
    if "严重度" in s and SEV_MARKER_RE.search(s):
        return True
    if re.match(r"^问题\s*[:：]", s):
        return True
    return False


def is_new_item(s):
    """条目内部扫描用的「下一条目起点」判定：标签行（位置/问题/建议：）视为本条目的延续"""
    if LABEL_LINE_RE.match(s):
        return False
    return is_item_start(s)


def parse_block_item(lines, i, source_label):
    """解析条目式发现（列表项 + 位置/问题/建议 标签行），返回 (finding_or_None, next_i)"""
    s0 = lines[i].strip()
    m = SEV_MARKER_RE.search(s0)
    explicit = m.group(1).upper() if m else None
    fields = {"loc": None, "desc": None, "sugg": None}
    last_key = None
    j = i
    while j < len(lines):
        s = lines[j].strip()
        if j > i and (not s or s.startswith("#") or s.startswith("|") or is_new_item(s)):
            break
        t = s
        if j == i:
            if explicit:
                t = SEV_MARKER_RE.sub("", s, count=1)
            t = LIST_START_RE.sub("", t).strip("[]【】 \t")
        matched = False
        for key, rx in LABELED_RES:
            mm = rx.search(t)
            if mm:
                fields[key] = mm.group(1).strip()
                last_key = key
                matched = True
                break
        if not matched:
            clean = re.sub(r"^[\s:：*\-]+", "", t)
            if clean and last_key and fields[last_key]:
                fields[last_key] += " " + clean          # 标签字段的续行
            elif clean and not fields["desc"]:
                fields["desc"] = clean                   # 无标签首行视为问题描述
                last_key = "desc"
        j += 1
    if not fields["desc"]:
        return None, i + 1
    desc = fields["desc"]
    if explicit is None:
        mm = re.search(r"\bP([012])\b", desc)
        explicit = ("P" + mm.group(1)) if mm else None
    sev, tag = classify(desc, explicit)
    return {"source": source_label, "loc": fields["loc"] or "", "desc": desc,
            "sugg": fields["sugg"] or "", "sev": sev, "tag": tag}, j


def parse_source(path, source_label, whitelist=False):
    """解析单个来源文件，返回 finding 列表。
    whitelist=True 时启用小节白名单：只解析标题匹配 ALLOWED_SECTION_RE 的小节，
    叙述性小节（参与角色/分歧记录/评分汇总等）内的表格行与含严重度字样的散文一律跳过。"""
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    findings = []
    cur_sev = None
    allowed = not whitelist          # 白名单模式下，文件头（首个标题前）不解析
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        is_head, sev = heading_severity(line)
        if is_head:
            cur_sev = sev
            if whitelist:
                head_text = line.lstrip("#").strip()
                if PROSE_SECTION_RE.search(head_text):
                    allowed = False
                elif ALLOWED_SECTION_RE.search(head_text):
                    allowed = True
                elif sev is None:
                    allowed = False  # 其他无严重度标题：保守关闭
                # 含 P0/P1/P2 的标题已被 ALLOWED_SECTION_RE 覆盖 → allowed=True
            i += 1
            continue
        if not allowed:
            i += 1
            continue
        s = line.strip()
        if s.startswith("|"):
            block = []
            while i < n and lines[i].strip().startswith("|"):
                block.append(lines[i].strip())
                i += 1
            findings.extend(parse_table(block, cur_sev, source_label))
            continue
        if s and is_item_start(s):
            item, next_i = parse_block_item(lines, i, source_label)
            if item:
                findings.append(item)
                i = next_i
                continue
        i += 1
    return findings


def norm_loc(loc):
    """归一化位置：提取章节号/第N段/行号，用于去重键"""
    if not loc:
        return ""
    secs = [m.replace("§", "").replace(" ", "")
            for m in re.findall(r"§?\s*\d+(?:\.\d+)*", loc)]
    paras = ["第%s段" % p for p in re.findall(r"第\s*(\d+)\s*段", loc)]
    lns = ["L%s" % l for l in re.findall(r"(\d+)\s*行", loc)]
    return ",".join(secs + paras + lns)


def dedup(findings):
    """按「位置 + 问题类型」去重；无位置时退化为「描述前缀 + 类型」"""
    seen, out, dups = {}, [], 0
    for f in findings:
        loc = norm_loc(f["loc"])
        if loc:
            key = (loc, f["tag"])
        else:
            prefix = re.sub(r"[\s，。；：、,.:;！？!?]+", "", f["desc"])[:12]
            key = ("desc:" + prefix, f["tag"])
        if key in seen:
            dups += 1
            if f["source"] not in seen[key]["source"]:
                seen[key]["source"] += "、" + f["source"]
            continue
        seen[key] = f
        out.append(f)
    return out, dups


def md_escape(s):
    return s.replace("|", "\\|").replace("\n", " ").strip()


def write_output(path, findings, dups, missing):
    counts = {"P0": 0, "P1": 0, "P2": 0}
    for f in findings:
        counts[f["sev"]] += 1
    total = len(findings)
    out = ["# 合并审查发现", ""]
    for sev, title in SEV_TITLES:
        out.append("## " + title)
        out.append("")
        items = [f for f in findings if f["sev"] == sev]
        if items:
            out.append("| # | 来源 | 位置 | 问题描述 | 建议修改 |")
            out.append("|---|------|------|----------|----------|")
            for k, f in enumerate(items, 1):
                out.append("| %d | %s | %s | %s | %s |" % (
                    k, md_escape(f["source"]), md_escape(f["loc"] or "—"),
                    md_escape(f["desc"]), md_escape(f["sugg"] or "—")))
        else:
            out.append("（无）")
        out.append("")
    out.append("## 统计")
    out.append("")
    out.append("P0: %d项 | P1: %d项 | P2: %d项 | 总计: %d项"
               % (counts["P0"], counts["P1"], counts["P2"], total))
    if dups:
        out.append("")
        out.append("（已按「位置+问题类型」去重合并 %d 项重复发现）" % dups)
    if missing:
        out.append("")
        out.append("（缺失来源文件，未纳入合并：%s）" % ", ".join(missing))
    out.append("")
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out))
    return counts, total


def main():
    parser = argparse.ArgumentParser(
        prog="merge_findings.py",
        description="paper-review 发现合并（v2 双模式）：--run-dir 走双权威清单"
                    "（revision_roadmap.md + deai_confirmed.md，稳定ID/交叉引用/撤回不复活）；"
                    "--review-dir 走 v1 三来源兼容模式（保留一个版本）。输出 JSON。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run-dir", metavar="DIR",
                       help="v2 模式：本轮运行产物目录（.review/r<N>/）")
    group.add_argument("--review-dir", metavar="DIR",
                       help="v1 兼容模式：审查输出目录（读取三个来源文件）")
    parser.add_argument("--roadmap", metavar="FILE", default=None,
                        help="v2：Revision Roadmap 路径（默认 {run_dir}/revision_roadmap.md）")
    parser.add_argument("--deai", metavar="FILE", default=None,
                        help="v2：确认AI问题清单路径（默认 {run_dir}/deai_confirmed.md）")
    parser.add_argument("--output", metavar="FILE", default=None,
                        help="合并清单输出路径（默认 {run_dir|review_dir}/merged_findings.md）")
    args = parser.parse_args()

    if args.run_dir:
        sys.exit(run_v2(args))
    sys.exit(run_v1(args))


def run_v1(args):
    output = args.output or os.path.join(args.review_dir, "merged_findings.md")

    all_findings, parsed, missing = [], [], []
    for fname, label, whitelist in SOURCES:
        fpath = os.path.join(args.review_dir, fname)
        found = parse_source(fpath, label, whitelist)
        if found is None:
            missing.append(fname)
            print("警告：来源文件不存在，跳过: %s" % fpath, file=sys.stderr)
        else:
            parsed.append(fname)
            all_findings.extend(found)

    deduped, dups = dedup(all_findings)
    try:
        counts, total = write_output(output, deduped, dups, missing)
    except OSError as e:
        print("错误：写入输出文件失败: %s" % e, file=sys.stderr)
        return 1

    result = {
        "mode": "v1",
        "p0": counts["P0"],
        "p1": counts["P1"],
        "p2": counts["P2"],
        "total": total,
        "output": os.path.abspath(output).replace("\\", "/"),
        "sources_parsed": parsed,
        "sources_missing": missing,
        "duplicates_removed": dups,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


# ═══════════════════════ v2 模式：双权威清单 ═══════════════════════
#
# 输入格式约定（SKILL.md 阶段1d / 阶段2c 产物，列名固定）：
#   revision_roadmap.md：## P0|P1|P2 小节，表格列
#     | ID | 位置 | 问题 | 建议 | 来源席 | 工作量 | 验收标准 |
#     头部 ## 决议 行含 Decision（Accept/Minor/Major/Reject）
#   deai_confirmed.md：单表，列
#     | ID | 位置 | 问题 | 建议 | 支持技能 | 严重度 | 重叠标记 |
#     重叠标记=R-# 时该条不重复计入，转入交叉引用表（S-#）
#     「质量评分: N/50」行被提取进 JSON

V2_SEV_HEAD_RE = re.compile(r"^#{2,3}\s*P([012])\b")
V2_DECISION_RE = re.compile(
    r"(Accept|Minor Revision|Major Revision|Reject|Minor|Major)", re.IGNORECASE)
V2_QUALITY_RE = re.compile(r"质量评分\s*[:：]\s*(\d+\s*/\s*50)")
V2_ID_RE = re.compile(r"\b([RDS])-(\d+)\b")


def _read_md(path):
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read().splitlines()


def _v2_table_rows(lines, start=0):
    """从 start 起解析第一个 markdown 表格，返回 (dict行列表, 下一行号)；列按表头名映射"""
    i = start
    n = len(lines)
    while i < n and not lines[i].strip().startswith("|"):
        i += 1
    if i >= n:
        return [], i
    header = [c.strip() for c in lines[i].strip().strip("|").split("|")]
    i += 1
    if i < n and is_sep_row([c.strip() for c in lines[i].strip().strip("|").split("|")]):
        i += 1
    rows = []
    while i < n and lines[i].strip().startswith("|"):
        cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
        if not is_sep_row(cells):
            rows.append({h: (cells[k] if k < len(cells) else "")
                         for k, h in enumerate(header)})
        i += 1
    return rows, i


def _v2_pick(row, *names):
    for nm in names:
        for key, val in row.items():
            if nm in key:
                return val.strip()
    return ""


def _next_id(prefix, used):
    k = 1
    while "%s-%d" % (prefix, k) in used:
        k += 1
    nid = "%s-%d" % (prefix, k)
    used.add(nid)
    return nid


def parse_roadmap(path):
    """解析 revision_roadmap.md → (items, decision)。
    items: [{id, sev, loc, desc, sugg, seats, effort, accept}]"""
    lines = _read_md(path)
    if lines is None:
        return None, None
    decision = None
    items, used = [], set()
    cur_sev = None
    auto_no = 0
    for i, line in enumerate(lines):
        if line.lstrip().startswith("#") and "决议" in line:
            for j in range(i + 1, min(i + 4, len(lines))):
                m = V2_DECISION_RE.search(lines[j])
                if m:
                    decision = m.group(1)
                    break
            continue
        m = V2_SEV_HEAD_RE.match(line.strip())
        if m:
            cur_sev = "P" + m.group(1)
            rows, _ = _v2_table_rows(lines, i + 1)
            for row in rows:
                desc = _v2_pick(row, "问题")
                if not desc:
                    continue
                rid = _v2_pick(row, "ID")
                m2 = V2_ID_RE.search(rid)
                rid = m2.group(0) if m2 else None
                if rid is None:
                    auto_no += 1
                    rid = "R-%d" % (1000 + auto_no)   # 占位，稍后重排
                used.add(rid)
                items.append({
                    "id": rid, "sev": cur_sev or "P2",
                    "loc": _v2_pick(row, "位置"), "desc": desc,
                    "sugg": _v2_pick(row, "建议"),
                    "seats": _v2_pick(row, "来源席", "来源"),
                    "effort": _v2_pick(row, "工作量"),
                    "accept": _v2_pick(row, "验收"),
                })
    # 占位 ID（R-1001+）重排为不冲突的连续 R-#
    real_ids = set(it["id"] for it in items if not _is_placeholder(it["id"]))
    k = 0
    for it in items:
        if _is_placeholder(it["id"]):
            while True:
                k += 1
                if "R-%d" % k not in real_ids:
                    it["id"] = "R-%d" % k
                    real_ids.add(it["id"])
                    break
    return items, decision


def _is_placeholder(rid):
    m = re.fullmatch(r"R-(\d+)", rid)
    return bool(m) and int(m.group(1)) > 1000


def parse_deai_confirmed(path):
    """解析 deai_confirmed.md → (items, quality_score)。
    items: [{id, sev, loc, desc, sugg, skills, overlap}]"""
    lines = _read_md(path)
    if lines is None:
        return None, None
    quality = None
    for line in lines:
        m = V2_QUALITY_RE.search(line)
        if m:
            quality = re.sub(r"\s+", "", m.group(1))
            break
    rows, _ = _v2_table_rows(lines)
    items, used = [], set()
    auto_no = 0
    for row in rows:
        desc = _v2_pick(row, "问题")
        if not desc:
            continue
        did = _v2_pick(row, "ID")
        m2 = V2_ID_RE.search(did)
        did = m2.group(0) if m2 and m2.group(1) == "D" else None
        if did is None:
            auto_no += 1
            while "D-%d" % auto_no in used:
                auto_no += 1
            did = "D-%d" % auto_no
        used.add(did)
        sev_m = re.search(r"P[012]", _v2_pick(row, "严重度").upper())
        overlap = _v2_pick(row, "重叠")
        ov_m = V2_ID_RE.search(overlap)
        items.append({
            "id": did, "sev": sev_m.group(0) if sev_m else "P2",
            "loc": _v2_pick(row, "位置"), "desc": desc,
            "sugg": _v2_pick(row, "建议"),
            "skills": _v2_pick(row, "支持技能", "技能"),
            "overlap": ov_m.group(0) if ov_m and ov_m.group(1) == "R" else None,
        })
    return items, quality


def load_withdrawn(run_dir):
    """从 config.json（run_dir 或其父目录）读取撤回记录 ID 集合"""
    for cand in (os.path.join(run_dir, "config.json"),
                 os.path.join(os.path.dirname(os.path.abspath(run_dir)), "config.json")):
        if os.path.isfile(cand):
            try:
                with open(cand, "r", encoding="utf-8-sig") as f:
                    cfg = json.load(f)
                return set(w.get("id") for w in cfg.get("withdrawals", [])
                           if w.get("id")), cfg
            except (OSError, ValueError):
                pass
    return set(), None


def write_output_v2(path, content_items, deai_items, cross_refs, withdrawn,
                    decision, quality, missing):
    counts = {"P0": 0, "P1": 0, "P2": 0}
    for f in content_items + deai_items:
        counts[f["sev"]] = counts.get(f["sev"], 0) + 1
    total = len(content_items) + len(deai_items)
    out = ["# 合并审查发现（v2 双权威清单）", ""]
    if decision:
        out.append("决议：**%s**" % decision)
        out.append("")
    out.append("## 内容发现（阶段1 Revision Roadmap）")
    out.append("")
    for sev, title in SEV_TITLES:
        items = [f for f in content_items if f["sev"] == sev]
        out.append("### %s" % title)
        out.append("")
        if items:
            out.append("| ID | 位置 | 问题 | 建议 | 来源席 | 工作量 | 验收标准 |")
            out.append("|----|------|------|------|--------|--------|----------|")
            for f in items:
                out.append("| %s | %s | %s | %s | %s | %s | %s |" % (
                    f["id"], md_escape(f["loc"] or "—"), md_escape(f["desc"]),
                    md_escape(f["sugg"] or "—"), md_escape(f["seats"] or "—"),
                    md_escape(f["effort"] or "—"), md_escape(f["accept"] or "—")))
        else:
            out.append("（无）")
        out.append("")
    out.append("## 语言发现（阶段2 确认AI问题清单，未重叠项）")
    out.append("")
    if deai_items:
        out.append("| ID | 严重度 | 位置 | 问题 | 建议 | 支持技能 |")
        out.append("|----|--------|------|------|------|----------|")
        for f in deai_items:
            out.append("| %s | %s | %s | %s | %s | %s |" % (
                f["id"], f["sev"], md_escape(f["loc"] or "—"), md_escape(f["desc"]),
                md_escape(f["sugg"] or "—"), md_escape(f["skills"] or "—")))
    else:
        out.append("（无）")
    out.append("")
    out.append("## 重叠交叉引用（去AI与阶段1同源，以阶段1为准）")
    out.append("")
    if cross_refs:
        out.append("| S-ID | 去AI项 | 内容项 | 说明 |")
        out.append("|------|--------|--------|------|")
        for c in cross_refs:
            out.append("| %s | %s | %s | %s |" % (
                c["sid"], c["deai_id"], c["content_id"], md_escape(c["note"])))
    else:
        out.append("（无）")
    out.append("")
    if withdrawn:
        out.append("## 已撤回项（不得复活）")
        out.append("")
        for w in withdrawn:
            out.append("- %s（撤回记录见 config.json）" % w)
        out.append("")
    if quality:
        out.append("去AI质量评分：%s" % quality)
        out.append("")
    out.append("## 统计")
    out.append("")
    out.append("P0: %d项 | P1: %d项 | P2: %d项 | 总计: %d项"
               % (counts["P0"], counts["P1"], counts["P2"], total))
    out.append("")
    out.append("（内容 %d 项 + 语言 %d 项；交叉引用 %d 项不重复计入；撤回跳过 %d 项）"
               % (len(content_items), len(deai_items), len(cross_refs), len(withdrawn)))
    if missing:
        out.append("")
        out.append("（缺失输入清单，未纳入合并：%s）" % ", ".join(missing))
    out.append("")
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out))
    return counts, total


def run_v2(args):
    roadmap_path = args.roadmap or os.path.join(args.run_dir, "revision_roadmap.md")
    deai_path = args.deai or os.path.join(args.run_dir, "deai_confirmed.md")
    output = args.output or os.path.join(args.run_dir, "merged_findings.md")

    missing = []
    content_items, decision = parse_roadmap(roadmap_path)
    if content_items is None:
        missing.append(os.path.basename(roadmap_path))
        print("警告：Revision Roadmap 不存在，跳过: %s" % roadmap_path, file=sys.stderr)
        content_items, decision = [], None

    deai_items, quality = parse_deai_confirmed(deai_path)
    if deai_items is None:
        missing.append(os.path.basename(deai_path))
        print("警告：确认AI问题清单不存在，跳过: %s" % deai_path, file=sys.stderr)
        deai_items, quality = [], None
    if len(missing) == 2:
        print("错误：两份权威清单均缺失，无可合并输入", file=sys.stderr)
        return 1

    withdrawn_ids, _cfg = load_withdrawn(args.run_dir)
    withdrawn = []

    def _drop_withdrawn(f):
        if f["id"] in withdrawn_ids:
            withdrawn.append(f["id"])
            return True
        return False

    content_items = [f for f in content_items if not _drop_withdrawn(f)]
    deai_items = [f for f in deai_items if not _drop_withdrawn(f)]

    # 重叠打标 → 交叉引用（S-#），不重复计入
    cross_refs, kept_deai = [], []
    s_no = 0
    for f in deai_items:
        if f["overlap"]:
            s_no += 1
            cross_refs.append({
                "sid": "S-%d" % s_no, "deai_id": f["id"], "content_id": f["overlap"],
                "note": "内容问题，阶段1 已辖（以 %s 为准）" % f["overlap"],
            })
        else:
            kept_deai.append(f)

    try:
        counts, total = write_output_v2(output, content_items, kept_deai, cross_refs,
                                        withdrawn, decision, quality, missing)
    except OSError as e:
        print("错误：写入输出文件失败: %s" % e, file=sys.stderr)
        return 1

    result = {
        "success": True,
        "mode": "v2",
        "p0": counts["P0"], "p1": counts["P1"], "p2": counts["P2"],
        "total": total,
        "content_items": len(content_items),
        "deai_items": len(kept_deai),
        "cross_refs": len(cross_refs),
        "withdrawn_skipped": withdrawn,
        "decision": decision,
        "quality_score": quality,
        "sources_missing": missing,
        "output": os.path.abspath(output).replace("\\", "/"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    main()
