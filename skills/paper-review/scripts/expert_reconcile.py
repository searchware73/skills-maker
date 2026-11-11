#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""expert_reconcile.py — paper-review 专家意见对账脚本（v2.0 决策⑨）

阶段1面板完成后，将用户提供的外部专家意见与面板合并发现对账：
专家意见逐条 × merged_findings.md 面板发现 → 三态：
  matched            吻合：面板已有对应发现
  omission_candidate 疑似遗漏：面板未覆盖 → 进入隔离区，未核实原文不得入报告
  conflict           冲突：对应面板发现标注「已撤回/不成立/误报」

铁律（隔离区机制强制执行）：
  疑似遗漏项必须经 verify --result confirmed 读原文核实后才计入
  counted_from_expert；confirmed 必须同时给出 --severity(P0|P1|P2) 与
  非空 --evidence；rejected（专家误判）永不计入；未核实的遗漏候选永不计入。
  （实测教训：he-paper 案中专家称「多域客户端」概念缺失，但该词全文
   根本不存在，属专家误判——不经原文核实不得收录。）

匹配算法（squash 归一：NFKC + casefold + 去空白标点）：
  1. 文本吻合：专家条目 × 发现「问题描述」字符 bigram Dice 相似度 ≥ 0.30
  2. 位置吻合：专家条目文本包含发现「位置」串（如 §3.2 / 表4.1）
     且 bigram 相似度 ≥ 0.15
  取相似度最高的发现为该条目的对账结果。

用法（--run-dir 为全局参数，置于子命令之前）：
  python expert_reconcile.py --run-dir DIR init --comments FILE
  python expert_reconcile.py --run-dir DIR match [--findings FILE]
  python expert_reconcile.py --run-dir DIR verify --id E-3 \\
      --result confirmed|rejected --evidence TEXT [--severity P0|P1|P2]
  python expert_reconcile.py --run-dir DIR report --paper-dir DIR --round N \\
      [--merged FILE] [--output FILE] [--index FILE]
  python expert_reconcile.py --run-dir DIR show

  init    解析专家意见（.md 或 .docx，docx 用 zipfile+ElementTree 原生解析
          word/document.xml，零第三方依赖；Word 自动列表段落转 `- ` 条目行）。
          支持 `1.` `1、` `- ` `* ` 开头行及 `E-N` 显式编号，
          多行续接归并到前一条目，分配 ID E-1..E-n
  match   与面板合并发现对账（--findings 缺省 {run_dir}/merged_findings.md），
          重写条目 state 并生成/覆盖 {run_dir}/expert_reconcile.md
  verify  核实隔离区条目：confirmed（须 --severity 与 --evidence）计入，
          rejected（专家误判，须 --evidence）永不计入；核实记录追加一行
  report  交付后同轮追加对账（v2.1 条目22，门禁 G2' 裁决：同轮追加，不递增轮次）：
          产出 {paper_dir}/reports/r{N}-综合审阅意见.md（三态对账表 + 未决分歧 +
          合并后严重度分布，新增项标来源=专家），chain.md 该轮节追加「专家对账」行
          （原决议不变，重复运行幂等替换），INDEX.md 报告路径同步（失败仅告警）。
          计数规则：吻合不重复计；专家新增按 verify 严重度计入分布；
          冲突与未核实遗漏入未决分歧不计入。存在 pending 条目 → exit 1 先 match
  show    输出对账状态 JSON

输出文件：
  {run_dir}/expert_items.json
    {"comments_file": "...", "entries": [
       {"id": "E-1", "text": "...", "state": "pending|matched|omission_candidate|
        conflict|confirmed|rejected", "severity": null|"P0|P1|P2",
        "evidence": null|"...", "matched_finding": null|"前30字"}, ...],
     "verifications": [{"id", "result", "severity", "evidence"}, ...]}
  {run_dir}/expert_reconcile.md
    三节（## 吻合 / ## 疑似遗漏（隔离区，未核实不入报告） / ## 冲突）
    各一张表 | ID | 专家意见 | 对账结果 |，加「## 核实记录」表
    | ID | 结果 | 严重度 | 证据 |
  {paper_dir}/reports/r{N}-综合审阅意见.md（report 子命令，交付后追加对账产物）
    三态对账表 + 未决分歧 + 合并后严重度分布；chain.md/INDEX.md 同步更新

stdout（JSON）：
  match/show → {"success":true,"total":N,"matched":N,"omission_candidates":N,
                "unverified_omissions":N,"conflicts":N,"confirmed":N,
                "rejected":N,"counted_from_expert":N,"items":[...]}
  match 的 stdout 与 show 同构，外加 {"reconcile_file": "..."}
  report → 在 show 结构外加 {"report":"...","round":N,
            "distribution":{"panel":{...},"expert_added":{...},"combined":{...}},
            "chain":"...","chain_updated":true,"index":"...","index_updated":bool}
  counted_from_expert 只含 confirmed；omission_candidates 计的是 state 仍为
  omission_candidate（未核实）的条数。

退出码：0=成功；1=文件读写失败；2=参数错误。
"""
import argparse
import datetime
import io
import json
import os
import re
import sys
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter

# 修复 Windows 下 GBK 编码问题，强制 UTF-8 输出
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SEVERITIES = ("P0", "P1", "P2")
CONFLICT_WORDS = ("已撤回", "不成立", "误报")

# 匹配阈值：文本吻合 / 位置吻合
TEXT_SIM = 0.30
LOC_SIM = 0.15

# 归一化：需要剔除的空白与常见标点（压缩匹配）
SQUASH_DROP_RE = re.compile(r"[\s，。；：、,.:;！？!?·…—\-–~\"'“”‘’()\[\]{}<>$\\§#@|/｜]")

# 专家意见条目起始：`1.` `1、` `1)` `- ` `* ` `• ` 或显式 `E-N` 编号
ITEM_START_RE = re.compile(
    r"^(?:\d+\s*[.、)）]\s*|[-*•]\s+|E-\d+\s*[:：.、]?\s*)", re.IGNORECASE)

# 位置串中的定位记号：§3.2 / 3.2 / 表4.1 / 图2 / 第3节 等
LOC_TOKEN_RE = re.compile(
    r"§\s*\d+(?:[.．]\d+)*|表\s*\d+(?:[.．]\d+)*|图\s*\d+(?:[.．]\d+)*"
    r"|第\s*\d+\s*[节章段]|\d+(?:[.．]\d+)+")


def to_posix(path):
    return path.replace("\\", "/")


def fail(msg, code=2):
    print("错误：%s" % msg, file=sys.stderr)
    sys.exit(code)


# ────────────────────────── 文本归一化与相似度 ──────────────────────────

def norm(text):
    """NFKC 归一（全半角统一）+ 大小写折叠 + 去 markdown 强调符 + 空白折叠"""
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", text).strip().casefold()


def squash(text):
    """压缩形态：norm 后再剔除全部空白与标点"""
    return SQUASH_DROP_RE.sub("", norm(text))


def bigram_sim(a, b):
    """字符 bigram Dice 相似度（输入为 squash 后字符串），范围 [0,1]"""
    if not a or not b:
        return 0.0
    if len(a) < 2 or len(b) < 2:
        return 1.0 if a == b else 0.0
    ca = Counter(a[i:i + 2] for i in range(len(a) - 1))
    cb = Counter(b[i:i + 2] for i in range(len(b) - 1))
    inter = sum((ca & cb).values())
    denom = (len(a) - 1) + (len(b) - 1)
    return 2.0 * inter / denom if denom else 0.0


def loc_hit(loc, text):
    """专家条目 text 是否包含发现的位置串（§3.2 / 表4.1 / 第3节 等）"""
    if not loc or not loc.strip():
        return False
    nt, st = norm(text), squash(text)
    nl, sl = norm(loc), squash(loc)
    if len(nl) >= 2 and nl in nt:
        return True
    if len(sl) >= 3 and sl in st:
        return True
    for tok in LOC_TOKEN_RE.findall(loc):
        stok = squash(tok)
        if len(stok) >= 2 and stok in st:
            return True
    return False


# ────────────────────────── 文件读写 ──────────────────────────

def read_text_file(path):
    """utf-8-sig 优先、gbk 兜底读取文本文件"""
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
        except OSError as e:
            fail("读取文件失败: %s (%s)" % (path, e), code=1)
    fail("无法解码文件（已尝试 utf-8-sig/utf-8/gbk）: %s" % path, code=1)


W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def read_docx_text(path):
    """docx → 纯文本：zipfile+ElementTree 解析 word/document.xml（无第三方依赖，
    与 conversion_audit.count_docx 同一模式）。每个 w:p 段落输出一行（段内 w:t
    拼接）；Word 自动编号/项目符号段落（编号在 numPr 而不在正文）转 `- ` 前缀，
    使 parse_comments 能识别为条目。表格单元格文本按段落同样提取。"""
    try:
        with zipfile.ZipFile(path) as z:
            xml_bytes = z.read("word/document.xml")
        root = ET.fromstring(xml_bytes)
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as e:
        fail("无法解析 docx（%s）: %s；请确认为有效 Word 文件，"
             "或先转换为 .md 再对账" % (path, e), code=1)
    lines = []
    for para in root.iter(W_NS + "p"):
        text = "".join(t.text or "" for t in para.iter(W_NS + "t")).strip()
        if not text:
            lines.append("")                   # 空段落 → 空行（终止多行续接）
            continue
        if para.find("%spPr/%snumPr" % (W_NS, W_NS)) is not None:
            text = "- " + text                 # Word 列表段落 → md 条目行
        lines.append(text)
    return "\n".join(lines)


def read_comments_file(path):
    """专家意见入口：.docx 走原生解析（v2.1 门禁 G2 裁决），其余按文本读取"""
    if path.lower().endswith(".docx"):
        return read_docx_text(path)
    return read_text_file(path)


def items_path(run_dir):
    return os.path.join(run_dir, "expert_items.json")


def reconcile_path(run_dir):
    return os.path.join(run_dir, "expert_reconcile.md")


def load_items(run_dir):
    path = items_path(run_dir)
    if not os.path.isfile(path):
        fail("expert_items.json 不存在，请先执行 init: %s" % path, code=1)
    try:
        data = json.loads(read_text_file(path))
    except json.JSONDecodeError as e:
        fail("expert_items.json 解析失败: %s" % e, code=1)
    if not isinstance(data.get("entries"), list):
        fail("expert_items.json 缺少 entries 列表: %s" % path, code=1)
    return data


def save_state(run_dir, data):
    """写回 JSON 状态并重新生成对账报告 md"""
    try:
        with open(items_path(run_dir), "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        with open(reconcile_path(run_dir), "w", encoding="utf-8", newline="\n") as f:
            f.write(render_md(data))
    except OSError as e:
        fail("写入对账状态失败: %s" % e, code=1)


def write_json(path, data):
    d = os.path.dirname(os.path.abspath(path))
    try:
        os.makedirs(d, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        fail("写入文件失败: %s (%s)" % (path, e), code=1)


# ────────────────────────── init：专家意见解析 ──────────────────────────

def parse_comments(content):
    """专家意见 md → 条目列表。
    识别 `1.` `1、` `- ` `* ` 开头行及 `E-N` 显式编号为条目起点；
    紧随其后的非空普通行视为多行续接，归并到前一条目；
    空行/标题行/表格行终止续接。ID 统一按顺序分配 E-1..E-n。"""
    entries, cur = [], None
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("|"):
            cur = None
            continue
        m = ITEM_START_RE.match(line)
        if m:
            text = line[m.end():].strip()
            if not text:
                cur = None
                continue
            cur = {"id": "E-%d" % (len(entries) + 1), "text": text,
                   "state": "pending", "severity": None, "evidence": None}
            entries.append(cur)
        elif cur is not None:
            cur["text"] += " " + line          # 多行续接归并
    return entries


def do_init(args):
    if not os.path.isfile(args.comments):
        fail("专家意见文件不存在: %s" % args.comments)
    entries = parse_comments(read_comments_file(args.comments))
    if not entries:
        print("警告：未解析出任何专家意见条目，请检查文件格式", file=sys.stderr)
    data = {
        "comments_file": to_posix(os.path.abspath(args.comments)),
        "entries": entries,
    }
    write_json(items_path(args.run_dir), data)
    return {
        "success": True, "action": "init", "count": len(entries),
        "items_file": to_posix(os.path.abspath(items_path(args.run_dir))),
    }, 0


# ────────────────────────── match：面板发现解析与对账 ──────────────────────────

def is_sep_row(cells):
    return all(c and set(c) <= set("-: ") for c in cells)


def find_col(header, names):
    for nm in names:
        for idx, h in enumerate(header):
            if nm in h:
                return idx
    return None


def parse_table_block(block):
    """解析一个 Markdown 表格块（连续 | 行），取「问题描述」与「位置」列"""
    rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in block]
    if len(rows) < 2:
        return []
    header = rows[0]
    desc_i = find_col(header, ["问题描述", "问题", "描述", "发现"])
    loc_i = find_col(header, ["位置", "章节", "行号", "段落"])
    if desc_i is None:
        return []                      # 非发现类表格（统计/评分表）→ 跳过
    out = []
    for r in rows[1:]:
        if is_sep_row(r) or len(r) <= desc_i:
            continue
        desc = r[desc_i].strip()
        if not desc or desc in ("...", "…", "—", "（无）"):
            continue
        loc = r[loc_i].strip() if loc_i is not None and len(r) > loc_i else ""
        out.append({"desc": desc, "loc": loc})
    return out


def parse_findings(path):
    """merged_findings.md → [{"desc", "loc"}, ...]"""
    lines = read_text_file(path).splitlines()
    findings, i, n = [], 0, len(lines)
    while i < n:
        if lines[i].strip().startswith("|"):
            block = []
            while i < n and lines[i].strip().startswith("|"):
                block.append(lines[i].strip())
                i += 1
            findings.extend(parse_table_block(block))
            continue
        i += 1
    return findings


def match_entry(text, findings):
    """单条专家意见 × 面板发现 → (best_finding|None, similarity)。
    文本吻合：bigram ≥ 0.30；位置吻合：条目含位置串且 bigram ≥ 0.15。"""
    st = squash(text)
    best, best_sim = None, 0.0
    for f in findings:
        sim = bigram_sim(st, squash(f["desc"]))
        hit = sim >= TEXT_SIM
        if not hit and f["loc"] and sim >= LOC_SIM and loc_hit(f["loc"], text):
            hit = True
        if hit and sim > best_sim:
            best, best_sim = f, sim
    return best, best_sim


def do_match(args):
    data = load_items(args.run_dir)
    fpath = args.findings or os.path.join(args.run_dir, "merged_findings.md")
    if not os.path.isfile(fpath):
        fail("面板合并发现文件不存在: %s（请先完成阶段3合并 merge_findings.py）"
             % fpath, code=1)
    findings = parse_findings(fpath)
    for e in data["entries"]:
        if e.get("state") in ("confirmed", "rejected"):
            continue                   # 已核实条目不重复对账
        best, _sim = match_entry(e["text"], findings)
        if best is None:
            e["state"] = "omission_candidate"      # 隔离区，待核实
            e["matched_finding"] = None
        else:
            desc = best["desc"]
            e["matched_finding"] = desc[:30]
            if any(w in desc for w in CONFLICT_WORDS):
                e["state"] = "conflict"
            else:
                e["state"] = "matched"
    data.setdefault("verifications", [])
    save_state(args.run_dir, data)
    result = build_stats(data)
    result["reconcile_file"] = to_posix(os.path.abspath(reconcile_path(args.run_dir)))
    return result, 0


# ────────────────────────── verify：隔离区核实 ──────────────────────────

def do_verify(args):
    data = load_items(args.run_dir)
    entry = None
    for e in data["entries"]:
        if e["id"] == args.id:
            entry = e
            break
    if entry is None:
        fail("条目不存在: %s" % args.id)
    state = entry.get("state")
    if state == "pending":
        fail("条目 %s 尚未对账，请先执行 match" % args.id)
    if state == "matched":
        fail("条目 %s 已与面板发现吻合，无需核实" % args.id)
    if state in ("confirmed", "rejected"):
        fail("条目 %s 已核实（%s），不可重复核实" % (args.id, state))

    evidence = (args.evidence or "").strip()
    if not evidence:
        fail("--evidence 不能为空（confirmed/rejected 均须给出原文核实证据）")
    if args.result == "confirmed" and args.severity not in SEVERITIES:
        fail("confirmed 必须同时给出 --severity（P0|P1|P2）")

    entry["evidence"] = evidence
    if args.result == "confirmed":
        entry["state"] = "confirmed"               # source=专家，按 severity 计入
        entry["severity"] = args.severity
        entry["source"] = "专家"
    else:
        entry["state"] = "rejected"                # 专家误判，永不计入
        entry["severity"] = None
    data.setdefault("verifications", []).append({
        "id": entry["id"], "result": args.result,
        "severity": args.severity if args.result == "confirmed" else None,
        "evidence": evidence,
    })
    save_state(args.run_dir, data)
    result = build_stats(data)
    result["reconcile_file"] = to_posix(os.path.abspath(reconcile_path(args.run_dir)))
    return result, 0


# ────────────────────────── report：交付后同轮追加对账（v2.1 条目22） ──────────────────────────

# merged_findings.md 统计行（与 merge_findings.py 输出格式一致，空白压缩后匹配）
MERGED_STATS_RE = re.compile(
    r"P0[:：](\d+)项\|P1[:：](\d+)项\|P2[:：](\d+)项\|总计[:：](\d+)项")

REPORT_STATE_LABEL = {
    "matched": "吻合",
    "confirmed": "新增（来源=专家）",
    "conflict": "冲突（未决分歧）",
    "omission_candidate": "未核实遗漏（不计入）",
    "rejected": "排除（专家误判）",
    "pending": "未对账",
}
REPORT_STATE_ORDER = ("matched", "confirmed", "conflict",
                      "omission_candidate", "rejected")


def find_chain_file(run_dir):
    """chain.md 在 .review/ 根（跨轮共享）；run_dir 可能是 .review/ 或 .review/rN/"""
    for cand in (os.path.join(run_dir, "chain.md"),
                 os.path.join(os.path.dirname(os.path.abspath(run_dir)), "chain.md")):
        if os.path.isfile(cand):
            return cand
    return None


def parse_merged_stats(path):
    if not os.path.isfile(path):
        fail("面板合并发现文件不存在: %s（report 需在阶段3合并完成、报告交付后运行）"
             % path, code=1)
    text = read_text_file(path)
    m = MERGED_STATS_RE.search(re.sub(r"\s+", "", text))
    if not m:
        fail("merged_findings.md 未解析到统计行「P0: N项 | P1: N项 | P2: N项 | 总计: N项」: %s"
             % path, code=1)
    p0, p1, p2, total = (int(g) for g in m.groups())
    return {"P0": p0, "P1": p1, "P2": p2, "total": total}


def render_report_md(round_no, date, data, base, additions, combined):
    entries = data["entries"]
    out = [
        "# r%d 综合审阅意见（交付后专家对账 · 同轮追加）" % round_no,
        "",
        "> 原 r%d 审阅报告与其决议**不变**；本文件是报告交付后收到的外部专家意见" % round_no,
        "> 与面板合并发现（merged_findings.md）逐条对账后的综合视图",
        "> （v2.1 条目22，门禁 G2' 用户裁决：同轮追加模式）。",
        "> 生成：expert_reconcile.py report · %s" % date,
        "",
        "## 三态对账表",
        "",
        "| ID | 专家意见 | 状态 | 严重度 | 对应面板发现 / 核实证据 |",
        "|----|----------|------|--------|--------------------------|",
    ]
    ordered = []
    for state in REPORT_STATE_ORDER:
        ordered += sorted((e for e in entries if e.get("state") == state),
                          key=lambda e: e["id"])
    for e in ordered:
        state = e.get("state")
        label = REPORT_STATE_LABEL.get(state, state)
        sev = e.get("severity") or "—"
        if state == "matched":
            note = "→ %s" % (e.get("matched_finding") or "")
        elif state == "confirmed":
            note = "证据：%s" % (e.get("evidence") or "")
        elif state == "conflict":
            note = "面板对应发现已标注撤回/不成立/误报 → %s" % (e.get("matched_finding") or "")
        elif state == "omission_candidate":
            note = "隔离区，待用户裁决（未核实不计入）"
        else:
            note = "专家误判：%s" % (e.get("evidence") or "")
        out.append("| %s | %s | %s | %s | %s |" % (
            e["id"], md_escape(e["text"]), label, sev, md_escape(note)))
    out += ["", "## 未决分歧（交用户裁决）", ""]
    pending_rows = [e for e in ordered
                    if e.get("state") in ("conflict", "omission_candidate")]
    if pending_rows:
        out += ["| ID | 类型 | 说明 |", "|----|------|------|"]
        for e in pending_rows:
            kind = ("冲突：面板认定不成立，专家提出异议"
                    if e.get("state") == "conflict" else "疑似遗漏：未经原文核实")
            out.append("| %s | %s | %s |" % (e["id"], kind.split("：")[0],
                                              md_escape(e["text"])))
    else:
        out.append("（无）")
    out += [
        "",
        "## 合并后严重度分布",
        "",
        "| 严重度 | 面板 | 专家新增（来源=专家） | 合并后 |",
        "|--------|------|------------------------|--------|",
    ]
    for k in ("P0", "P1", "P2"):
        out.append("| %s | %d | %d | %d |" % (k, base[k], additions.get(k, 0),
                                              combined[k]))
    out.append("| 总计 | %d | %d | %d |" % (
        base["total"], sum(additions.values()), combined["total"]))
    out += [
        "",
        "计数规则：吻合项不重复计数；专家新增项（verify confirmed）按面板严重度规则",
        "定级并计入分布；冲突项与未核实遗漏入未决分歧，不计入分布；",
        "排除项（专家误判）永不计入。",
        "",
    ]
    return "\n".join(out)


def update_chain(chain_path, round_no, line):
    """在 chain.md 的 r{N} 节末追加「专家对账」行（不改原决议）；同轮重复运行则替换旧行"""
    text = read_text_file(chain_path)
    sec_re = re.compile(r"^##\s*r%d(?!\d)" % round_no, re.MULTILINE)
    m = sec_re.search(text)
    if not m:
        fail("chain.md 无 r%d 节，无法追加专家对账行: %s" % (round_no, chain_path),
             code=1)
    nxt = re.compile(r"^##\s", re.MULTILINE).search(text, m.end())
    end = nxt.start() if nxt else len(text)
    section = text[m.end():end]
    # 幂等：剔除本节既有的专家对账行
    kept = [ln for ln in section.splitlines() if not ln.startswith("- 专家对账（")]
    while kept and not kept[-1].strip():
        kept.pop()
    kept.append(line)
    new_section = "\n".join(kept) + "\n\n"
    new_text = text[:m.end()] + new_section + text[end:]
    try:
        with open(chain_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_text)
    except OSError as e:
        fail("chain.md 写入失败: %s" % e, code=1)


def update_index(index_path, paper_name, rel_report):
    """INDEX.md 中该稿件行的报告路径列追加综合意见路径；失败仅告警（非致命）"""
    if not index_path or not os.path.isfile(index_path):
        print("警告：INDEX.md 不存在，跳过报告路径同步: %s" % index_path,
              file=sys.stderr)
        return False
    lines = read_text_file(index_path).splitlines()
    changed = False
    for i, ln in enumerate(lines):
        if ln.startswith("|") and paper_name and paper_name in ln:
            cells = ln.split("|")
            if len(cells) >= 3 and rel_report not in cells[-2]:
                cells[-2] = cells[-2].rstrip() + " + " + rel_report + " "
                lines[i] = "|".join(cells)
                changed = True
            break
    if not changed:
        print("警告：INDEX.md 未找到稿件行或路径已在，未更新: %s" % paper_name,
              file=sys.stderr)
        return False
    try:
        with open(index_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
    except OSError as e:
        print("警告：INDEX.md 写入失败（%s），未同步" % e, file=sys.stderr)
        return False
    return True


def do_report(args):
    data = load_items(args.run_dir)
    entries = data["entries"]
    pending = [e["id"] for e in entries if e.get("state") == "pending"]
    if pending:
        fail("存在 %d 条未对账条目（%s），请先执行 match"
             % (len(pending), ",".join(pending)), code=1)
    for e in entries:
        if e.get("state") == "confirmed" and e.get("severity") not in SEVERITIES:
            fail("条目 %s 状态 confirmed 但缺严重度，数据不一致" % e["id"], code=1)

    merged = args.merged or os.path.join(args.run_dir, "merged_findings.md")
    base = parse_merged_stats(merged)
    additions = Counter(e["severity"] for e in entries
                        if e.get("state") == "confirmed")
    combined = {k: base[k] + additions.get(k, 0) for k in ("P0", "P1", "P2")}
    combined["total"] = base["total"] + sum(additions.values())

    paper_dir = args.paper_dir
    if not os.path.isdir(paper_dir):
        fail("论文目录不存在: %s" % paper_dir)
    rel_report = "reports/r%d-综合审阅意见.md" % args.round
    out_path = args.output or os.path.join(paper_dir, "reports",
                                           "r%d-综合审阅意见.md" % args.round)
    date = datetime.date.today().isoformat()
    report_md = render_report_md(args.round, date, data, base, additions, combined)
    try:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(report_md)
    except OSError as e:
        fail("综合审阅意见写入失败: %s" % e, code=1)

    # chain.md 追加「专家对账」行（原决议不动）
    s = build_stats(data)
    add_by_sev = " / ".join("%s %d" % (k, additions.get(k, 0)) for k in ("P0", "P1", "P2"))
    chain_line = ("- 专家对账（%s，交付后追加）：条目 %d → 吻合 %d / 新增 %d"
                  "（来源=专家：%s）/ 冲突 %d / 未核实遗漏 %d / 排除 %d；"
                  "合并后 P0 %d / P1 %d / P2 %d（总计 %d）；原决议不变"
                  % (date, s["total"], s["matched"], s["confirmed"], add_by_sev,
                     s["conflicts"], s["omission_candidates"], s["rejected"],
                     combined["P0"], combined["P1"], combined["P2"],
                     combined["total"]))
    chain_path = find_chain_file(args.run_dir)
    if chain_path is None:
        fail("未找到 chain.md（在 %s 或其上级），无法追加专家对账行"
             % args.run_dir, code=1)
    update_chain(chain_path, args.round, chain_line)

    # INDEX.md 报告路径同步（失败仅告警）
    index_path = args.index or os.path.join(
        os.path.dirname(os.path.abspath(paper_dir)), "INDEX.md")
    index_updated = update_index(index_path, os.path.basename(
        os.path.abspath(paper_dir)), rel_report)

    result = build_stats(data)
    result.update({
        "report": to_posix(os.path.abspath(out_path)),
        "round": args.round,
        "distribution": {"panel": base,
                         "expert_added": dict(additions),
                         "combined": combined},
        "chain": to_posix(chain_path),
        "chain_updated": True,
        "index": to_posix(index_path),
        "index_updated": index_updated,
    })
    return result, 0


# ────────────────────────── show / 报告生成 ──────────────────────────

def build_stats(data):
    entries = data["entries"]

    def cnt(*states):
        return sum(1 for e in entries if e.get("state") in states)

    return {
        "success": True,
        "total": len(entries),
        "matched": cnt("matched"),
        "omission_candidates": cnt("omission_candidate"),
        "unverified_omissions": cnt("omission_candidate"),
        "conflicts": cnt("conflict"),
        "confirmed": cnt("confirmed"),
        "rejected": cnt("rejected"),
        "counted_from_expert": cnt("confirmed"),   # 铁律：只含已核实 confirmed
        "items": entries,
    }


def do_show(args):
    return build_stats(load_items(args.run_dir)), 0


def md_escape(s):
    return (s or "").replace("|", "\\|").replace("\n", " ").strip()


def render_md(data):
    entries = data["entries"]
    verifs = data.get("verifications", [])

    def result_text(e):
        if e["state"] == "matched":
            return "吻合 → %s" % (e.get("matched_finding") or "")
        if e["state"] == "conflict":
            return "面板对应发现已标注撤回/不成立/误报 → %s" % (e.get("matched_finding") or "")
        return "面板无对应发现，待读原文核实"

    out = ["# 专家意见对账", "",
           "> 铁律：疑似遗漏项位于隔离区，必须经 verify 读原文核实（confirmed + 严重度 + 证据）",
           "> 后方可计入报告；未核实的遗漏候选不计入 counted_from_expert，rejected（专家误判）永不计入。",
           ""]
    sections = [("## 吻合", "matched"),
                ("## 疑似遗漏（隔离区，未核实不入报告）", "omission_candidate"),
                ("## 冲突", "conflict")]
    for title, state in sections:
        rows = [e for e in entries if e.get("state") == state]
        out.append(title)
        out.append("")
        out.append("| ID | 专家意见 | 对账结果 |")
        out.append("|----|----------|----------|")
        for e in rows:
            out.append("| %s | %s | %s |" % (e["id"], md_escape(e["text"]),
                                              md_escape(result_text(e))))
        if not rows:
            out.append("")
            out.append("（无）")
        out.append("")
    out.append("## 核实记录")
    out.append("")
    out.append("| ID | 结果 | 严重度 | 证据 |")
    out.append("|----|------|--------|------|")
    for v in verifs:
        out.append("| %s | %s | %s | %s |" % (
            v["id"], v["result"], v.get("severity") or "—",
            md_escape(v.get("evidence"))))
    out.append("")
    return "\n".join(out)


# ────────────────────────── CLI ──────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="expert_reconcile.py",
        description="paper-review 专家意见对账：专家意见逐条 × 面板合并发现 → "
                    "吻合/疑似遗漏（隔离区）/冲突 三态，维护 {run_dir}/expert_items.json "
                    "与 expert_reconcile.md。遗漏项必须 verify 核实后方可入报告。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--run-dir", metavar="DIR", default=".review",
                        help="运行输出目录（expert_items.json / expert_reconcile.md 所在）")
    sub = parser.add_subparsers(dest="action", required=True)

    p_init = sub.add_parser("init", help="解析专家意见 md/docx → expert_items.json（E-1..E-n）")
    p_init.add_argument("--comments", metavar="FILE", required=True,
                        help="专家意见文件 .md 或 .docx（docx 原生解析，零第三方依赖；"
                             "支持 1. / 1、 / - / * / E-N 条目及 Word 列表段落）")

    p_match = sub.add_parser("match", help="与面板合并发现对账（阶段3合并完成后）")
    p_match.add_argument("--findings", metavar="FILE", default=None,
                        help="面板合并发现 md（默认 {run_dir}/merged_findings.md）")

    p_verify = sub.add_parser("verify", help="核实隔离区条目（confirmed 须 --severity 与 --evidence）")
    p_verify.add_argument("--id", metavar="EID", required=True, help="条目 ID（如 E-3）")
    p_verify.add_argument("--result", choices=["confirmed", "rejected"], required=True,
                          help="核实结果：confirmed=属实计入 / rejected=专家误判永不计入")
    p_verify.add_argument("--evidence", metavar="TEXT", default=None,
                          help="原文核实证据（confirmed/rejected 均必填）")
    p_verify.add_argument("--severity", choices=list(SEVERITIES), default=None,
                          help="严重度（confirmed 必填：P0|P1|P2）")

    p_report = sub.add_parser(
        "report", help="交付后同轮追加对账：产出 rN-综合审阅意见.md 并同步 chain/INDEX")
    p_report.add_argument("--paper-dir", metavar="DIR", required=True,
                          help="论文目录（<project-root>/<paper-name>）")
    p_report.add_argument("--round", metavar="N", type=int, required=True,
                          dest="round", help="已交付轮次号（产物 rN-综合审阅意见.md）")
    p_report.add_argument("--merged", metavar="FILE", default=None,
                          help="面板合并发现 md（默认 {run_dir}/merged_findings.md）")
    p_report.add_argument("--output", metavar="FILE", default=None,
                          help="综合意见输出路径（默认 {paper_dir}/reports/rN-综合审阅意见.md）")
    p_report.add_argument("--index", metavar="FILE", default=None,
                          help="工程根 INDEX.md（默认 {paper_dir}/../INDEX.md）")

    sub.add_parser("show", help="输出对账状态 JSON")

    args = parser.parse_args()
    if args.action == "init":
        result, code = do_init(args)
    elif args.action == "match":
        result, code = do_match(args)
    elif args.action == "verify":
        result, code = do_verify(args)
    elif args.action == "report":
        result, code = do_report(args)
    else:
        result, code = do_show(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(code)


if __name__ == "__main__":
    main()
