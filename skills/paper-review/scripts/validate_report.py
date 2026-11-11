#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_report.py — final_report.md 交付前机器校验（v2.1 条目17）

背景（备忘 §十一 条目17，2026-11-09 于小岚稿实测）：final_report.md 手工按模板
生成，P0/P1/P2、总数、anchor resolved 数、交付副本路径全靠人工同步，曾出现
7→9 P0、39→47 项、75→81 项的中间态数字，均靠人工偶然发现。本脚本把「报告说的」
与「产物里实际是的」逐项机器核对，**收集全部问题后统一报告**，任一不符 exit 1：

  A. 合并统计：报告 §5「合并统计：P0 a / P1 b / P2 c，总计 N（内容 X + 语言 Y；
     交叉引用 Z 不重复计入；撤回跳过 W）」↔ merged_findings.md「## 统计」节，7 数逐项；
  B. 决议：报告「Editorial Decision」↔ merged「决议」（↔ roadmap 决议，如可解析）；
  C. 质量评分：报告 §4「质量评分: N/50」↔ merged「去AI质量评分」（阶段2 存在时）；
  D. 反查统计：报告 §2「反查统计：resolved/ambiguous/not_found/structural_only
     （共 N 条）」↔ anchor_map.json entries 状态计数（三轨启用时；报告缺该行
     本身也是问题——模板 §2 要求必含）；
  E. 每席报告：seat_reports/*.md 全部存在且非空；给 --seats N 时数量必须恰好 N
     （补派席位后须先重跑 1d + merge_findings 再校验，不得直接交付）；
  F. 交付副本：{paper_dir}/reports/r{N}-审阅报告.md（--re-review 时为复审报告）
     存在且与 final_report.md **字节一致**；工程根 INDEX.md 含对应行；
  G. chain.md：存在、非空、含本轮 r{N} 节（校验应在 Step 6.5 chain 更新之后跑）。

stdout（JSON）：
  {"success": bool, "problems": [...], "skipped": [...],
   "checks": {"merge_stats": {...}, "decision": {...}, "quality": {...},
              "anchor": {...}, "seats": {...}, "delivery": {...}, "chain": {...}}}

用法：
  python validate_report.py --run-dir DIR [--paper-dir DIR --round N]
                            [--re-review] [--seats N] [--report FILE]
                            [--merged FILE] [--index FILE]

退出码：0=全部通过；1=存在问题（见 problems）；2=参数错误。
"""
import argparse
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import merge_findings as mf      # noqa: E402  parse_roadmap（决议三方核对）

# 修复 Windows 下 GBK 编码问题，强制 UTF-8 输出
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

DECISION_WORDS = r"Accept|Minor\s+Revision|Major\s+Revision|Reject|Minor|Major"


def fail(msg, code=1):
    print("错误：%s" % msg, file=sys.stderr)
    sys.exit(code)


def read_text(path):
    """宽容读取（utf-8-sig/utf-8/gbk）；不存在或不可读返回 None"""
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with open(path, encoding=enc) as f:
                return f.read()
        except (OSError, UnicodeDecodeError):
            continue
    return None


def squash(text):
    """去掉全部空白——模板行允许换行折行，核对口径与空白无关"""
    return re.sub(r"\s+", "", text or "")


def canon_decision(dec):
    if not dec:
        return None
    d = dec.lower()
    for key, canon in (("accept", "Accept"), ("reject", "Reject"),
                       ("major", "Major"), ("minor", "Minor")):
        if key in d:
            return canon
    return None


# ────────────────────────── 各项核对 ──────────────────────────

MERGE_STATS_RE = re.compile(
    r"P0[:：](\d+)项\|P1[:：](\d+)项\|P2[:：](\d+)项\|总计[:：](\d+)项")
MERGE_STATS2_RE = re.compile(
    r"内容(\d+)项\+语言(\d+)项[;；]交叉引用(\d+)项不重复计入[;；]撤回跳过(\d+)项")
REPORT_STATS_RE = re.compile(
    r"合并统计[:：]P0(\d+)/P1(\d+)/P2(\d+)[,，]总计(\d+)"
    r"[（(]内容(\d+)\+语言(\d+)[;；]交叉引用(\d+)不重复计入[;；]撤回跳过(\d+)[)）]")
STATS_NAMES = ("P0", "P1", "P2", "总计", "内容", "语言", "交叉引用", "撤回跳过")

ANCHOR_RE = re.compile(
    r"反查统计[:：]resolved(\d+)/ambiguous(\d+)/not_found(\d+)"
    r"/structural_only(\d+)[（(]共(\d+)条[^）)]*[)）]")
ANCHOR_KEYS = ("resolved", "ambiguous", "not_found", "structural_only", "共")


def check_merge_stats(report_sq, merged_text, problems, checks):
    """A. 报告合并统计 ↔ merged 统计节（7+1 数逐项）"""
    m_rep = REPORT_STATS_RE.search(report_sq)
    m1 = MERGE_STATS_RE.search(squash(merged_text))
    m2 = MERGE_STATS2_RE.search(squash(merged_text))
    checks["merge_stats"] = {"report": None, "merged": None}
    if not (m1 and m2):
        problems.append("merged_findings.md 缺「## 统计」节计数行，无法核对合并统计")
        return
    merged_nums = [int(x) for x in m1.groups()] + [int(x) for x in m2.groups()]
    checks["merge_stats"]["merged"] = merged_nums
    if not m_rep:
        problems.append("final_report.md 未找到「合并统计：P0 …/P1 …/P2 …，总计 …」行"
                        "（模板 §5 必含；数字须与 merged_findings.md 统计节一致）")
        return
    report_nums = [int(x) for x in m_rep.groups()]
    checks["merge_stats"]["report"] = report_nums
    for name, got, want in zip(STATS_NAMES, report_nums, merged_nums):
        if got != want:
            problems.append("合并统计不符：%s 报告写 %d，merged_findings.md 实为 %d"
                            % (name, got, want))


def check_decision(report_text, merged_text, roadmap_path, problems, checks):
    """B. 决议三方核对（报告 / merged / roadmap）"""
    m_rep = re.search(r"Editorial\s*Decision[:：]\s*\**\s*(%s)" % DECISION_WORDS,
                      report_text, re.IGNORECASE)
    m_merged = re.search(r"决议[:：]\s*\**\s*(%s)" % DECISION_WORDS,
                         merged_text, re.IGNORECASE)
    dec_roadmap = None
    if roadmap_path and os.path.exists(roadmap_path):
        try:
            _items, dec, _declared = mf.parse_roadmap(roadmap_path)
            dec_roadmap = dec
        except Exception:
            dec_roadmap = None
    rep = canon_decision(m_rep.group(1) if m_rep else None)
    merged = canon_decision(m_merged.group(1) if m_merged else None)
    road = canon_decision(dec_roadmap)
    checks["decision"] = {"report": rep, "merged": merged, "roadmap": road}
    if not rep:
        problems.append("final_report.md 未找到「Editorial Decision：…」决议行")
    if merged and rep and rep != merged:
        problems.append("决议不符：报告写 %s，merged_findings.md 实为 %s" % (rep, merged))
    if road and merged and road != merged:
        problems.append("决议不符：merged_findings.md 写 %s，revision_roadmap.md 实为 %s"
                        % (merged, road))


def check_quality(report_text, merged_text, problems, checks):
    """C. 质量评分 N/50（仅 merged 含去AI评分时核对）"""
    m_merged = re.search(r"去AI质量评分[:：]\s*(\d+)\s*/\s*50", merged_text)
    checks["quality"] = {"report": None, "merged": None}
    if not m_merged:
        return                              # --quick 跳过阶段2：无评分可核
    want = m_merged.group(1) + "/50"
    checks["quality"]["merged"] = want
    m_rep = re.search(r"质量评分[:：]\s*\**\s*(\d+)\s*/\s*50", report_text)
    if not m_rep:
        problems.append("merged 含去AI质量评分 %s，但报告 §4 缺「质量评分: N/50」行" % want)
        return
    got = m_rep.group(1) + "/50"
    checks["quality"]["report"] = got
    if got != want:
        problems.append("质量评分不符：报告写 %s，merged_findings.md 实为 %s" % (got, want))


def check_anchor(report_sq, anchor_path, problems, checks):
    """D. 反查统计 ↔ anchor_map.json entries 状态计数"""
    checks["anchor"] = {"report": None, "computed": None}
    m_rep = ANCHOR_RE.search(report_sq)
    if not os.path.exists(anchor_path):
        if m_rep:
            problems.append("报告含「反查统计」行，但 anchor_map.json 不存在：%s"
                            % anchor_path)
        return False                        # 双轨模式：跳过
    try:
        with open(anchor_path, encoding="utf-8") as f:
            data = json.load(f)
        entries = data.get("entries", [])
    except (OSError, ValueError) as e:
        problems.append("anchor_map.json 不可读或非法 JSON：%s" % e)
        return True
    counts = {k: 0 for k in ANCHOR_KEYS[:-1]}
    for ent in entries:
        st = ent.get("status")
        if st in counts:
            counts[st] += 1
    computed = [counts[k] for k in ANCHOR_KEYS[:-1]] + [len(entries)]
    checks["anchor"]["computed"] = computed
    if not m_rep:
        problems.append("anchor_map.json 存在（三轨启用），但报告 §2 缺"
                        "「反查统计：resolved …/ambiguous …/not_found …/"
                        "structural_only …（共 N 条）」行")
        return True
    report_nums = [int(x) for x in m_rep.groups()]
    checks["anchor"]["report"] = report_nums
    for name, got, want in zip(ANCHOR_KEYS, report_nums, computed):
        if got != want:
            problems.append("反查统计不符：%s 报告写 %d，anchor_map.json 实为 %d"
                            % (name, got, want))
    return True


def check_seats(run_dir, seats_expected, problems, checks):
    """E. 每席报告存在且非空；--seats 时数量恰好"""
    seat_dir = os.path.join(run_dir, "seat_reports")
    checks["seats"] = {"found": 0, "expected": seats_expected, "empty": []}
    if not os.path.isdir(seat_dir):
        problems.append("seat_reports/ 不存在：%s（阶段1 产物缺失，不得直接交付）"
                        % seat_dir)
        return
    files = sorted(f for f in os.listdir(seat_dir) if f.endswith(".md"))
    empty = []
    for fn in files:
        text = read_text(os.path.join(seat_dir, fn))
        if not (text or "").strip():
            empty.append(fn)
    checks["seats"]["found"] = len(files)
    checks["seats"]["empty"] = empty
    if not files:
        problems.append("seat_reports/ 无任何席位报告（%s）" % seat_dir)
    for fn in empty:
        problems.append("席位报告为空文件：seat_reports/%s（补派该席后重跑 1d 与 "
                        "merge_findings，再重跑本校验）" % fn)
    if seats_expected is not None and len(files) != seats_expected:
        problems.append("席位报告数不符：seat_reports/ 实有 %d 份，预期 %d 份（%s）"
                        % (len(files), seats_expected,
                           "缺失席位须单独补派，不得静默降席交付"
                           if len(files) < seats_expected else "多出预期，核对是否误留"))


def check_delivery(report_path, paper_dir, round_n, re_review, index_path,
                   problems, checks):
    """F. 交付副本字节一致 + INDEX.md 行"""
    copy_name = "r%d-%s.md" % (round_n, "复审报告" if re_review else "审阅报告")
    copy_path = os.path.join(paper_dir, "reports", copy_name)
    paper_name = os.path.basename(os.path.abspath(paper_dir))
    checks["delivery"] = {"copy": copy_path, "exists": False,
                          "identical": False, "index_row_found": False}
    if not os.path.exists(copy_path):
        problems.append("交付副本不存在：%s（先执行 Step 6.4 复制）" % copy_path)
    else:
        checks["delivery"]["exists"] = True
        try:
            with open(copy_path, "rb") as f1, open(report_path, "rb") as f2:
                same = f1.read() == f2.read()
        except OSError as e:
            same = False
            problems.append("交付副本不可读：%s" % e)
        checks["delivery"]["identical"] = same
        if not same:
            problems.append("交付副本与 %s 内容不一致（须字节相同；报告改后须重新复制）"
                            % os.path.basename(report_path))
    if index_path is None:
        index_path = os.path.join(os.path.dirname(os.path.abspath(paper_dir)),
                                  "INDEX.md")
    index_text = read_text(index_path)
    if index_text is None:
        problems.append("INDEX.md 不存在或不可读：%s" % index_path)
    else:
        rel = "reports/%s" % copy_name
        found = any(paper_name in line and rel in line
                    for line in index_text.splitlines())
        checks["delivery"]["index_row_found"] = found
        checks["delivery"]["index"] = index_path
        if not found:
            problems.append("INDEX.md 缺该篇报告行（应含 %s 与 %s）：%s"
                            % (paper_name, rel, index_path))


def check_chain(run_dir, round_n, problems, checks):
    """G. chain.md 存在、非空、含本轮节"""
    review_dir = os.path.dirname(os.path.abspath(run_dir))
    chain_path = os.path.join(review_dir, "chain.md")
    checks["chain"] = {"path": chain_path, "exists": False, "round_section": None}
    text = read_text(chain_path)
    if text is None:
        problems.append("chain.md 不存在或不可读：%s（Step 6.5 须先追加本轮谱系）"
                        % chain_path)
        return
    checks["chain"]["exists"] = True
    if not text.strip():
        problems.append("chain.md 为空文件：%s" % chain_path)
        return
    if round_n is not None:
        has_round = bool(re.search(r"r%d(?!\d)" % round_n, text))
        checks["chain"]["round_section"] = has_round
        if not has_round:
            problems.append("chain.md 未见本轮 r%d 节（Step 6.5 须先追加）" % round_n)


def main():
    parser = argparse.ArgumentParser(
        prog="validate_report.py",
        description="final_report.md 交付前机器校验（条目17）：合并统计/决议/质量评分/"
                    "反查统计/席位报告数/交付副本与 INDEX 行/chain 本轮节，任一不符 exit 1。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--run-dir", required=True, metavar="DIR",
                        help="本轮产物目录（.review/rN/）")
    parser.add_argument("--paper-dir", default=None, metavar="DIR",
                        help="论文目录（提供则核对交付副本 reports/rN-*.md 与 INDEX.md 行）")
    parser.add_argument("--round", type=int, default=None, metavar="N",
                        help="轮次（交付副本命名与 chain.md 本轮节核对）")
    parser.add_argument("--re-review", action="store_true",
                        help="复审轮：交付副本名为 rN-复审报告.md")
    parser.add_argument("--seats", type=int, default=None, metavar="N",
                        help="预期席位报告数（正式 7 / quick 2；不给则只查非空）")
    parser.add_argument("--report", default=None, metavar="FILE",
                        help="final_report.md 路径（默认 {run_dir}final_report.md）")
    parser.add_argument("--merged", default=None, metavar="FILE",
                        help="merged_findings.md 路径（默认 {run_dir}merged_findings.md）")
    parser.add_argument("--index", default=None, metavar="FILE",
                        help="INDEX.md 路径（默认 {paper_dir}/../INDEX.md）")
    args = parser.parse_args()

    if args.paper_dir and args.round is None:
        fail("--paper-dir 提供时必须同时给 --round（交付副本命名依赖轮次）", code=2)

    run_dir = args.run_dir
    report_path = args.report or os.path.join(run_dir, "final_report.md")
    merged_path = args.merged or os.path.join(run_dir, "merged_findings.md")
    roadmap_path = os.path.join(run_dir, "revision_roadmap.md")
    anchor_path = os.path.join(run_dir, "anchor_map.json")

    problems, skipped, checks = [], [], {}

    report_text = read_text(report_path)
    if report_text is None:
        problems.append("final_report.md 不存在或不可读：%s" % report_path)
    merged_text = read_text(merged_path)
    if merged_text is None:
        problems.append("merged_findings.md 不存在或不可读：%s（先跑 merge_findings.py）"
                        % merged_path)

    if report_text is not None and merged_text is not None:
        report_sq = squash(report_text)
        check_merge_stats(report_sq, merged_text, problems, checks)
        check_decision(report_text, merged_text, roadmap_path, problems, checks)
        check_quality(report_text, merged_text, problems, checks)
        if not check_anchor(report_sq, anchor_path, problems, checks):
            skipped.append("anchor（anchor_map.json 不存在，双轨模式）")
    else:
        skipped.append("报告级核对（final_report.md 或 merged_findings.md 缺失）")

    check_seats(run_dir, args.seats, problems, checks)

    if args.paper_dir and report_text is not None:
        check_delivery(report_path, args.paper_dir, args.round, args.re_review,
                       args.index, problems, checks)
    else:
        skipped.append("delivery（未提供 --paper-dir 或报告缺失）")

    check_chain(run_dir, args.round, problems, checks)

    success = not problems
    result = {"success": success, "report": report_path,
              "problems": problems, "problem_count": len(problems),
              "skipped": skipped, "checks": checks}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not success:
        print("校验失败：%d 个问题（逐条见 problems）。修复产物或报告后重跑；"
              "不得带着不一致交付。" % len(problems), file=sys.stderr)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
