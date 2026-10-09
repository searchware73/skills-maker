#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""convergence_check.py — paper-review 收敛判定脚本

功能：
  1. 记录本轮质量数据（去AI评分 / 同行评审评分 / P0/P1/P2 计数）到 convergence.md
     （同一轮次重复提交会覆盖该轮记录，便于重评）
  2. 读取历史轮次数据，判定是否收敛 / 是否停滞，给出下一步动作

收敛条件（全部满足才算收敛）：
  c1. 去AI评分 ≥ 8          c2. 同行评审评分 ≥ 7      c3. P0 数 = 0
  c4. P1 数 ≤ 3             c5. 连续2轮无新增 P0/P1
      （c5 近似判定：当前轮与上一轮均 P0=0 且当前 P1 不高于上一轮；首轮恒不满足）

停滞检测：
  连续2个轮次间隔中，去AI评分与同行评审评分改善均 < 0.5 分 → stagnant，
  action=escalate（暂停循环，请用户决策：继续/停止/调整策略）

动作优先级：converged(stop) > 达到最大轮数(stop) > 停滞(escalate) > continue

用法：
  python convergence_check.py --round 2 --deai-score 8.0 --peer-score 7.5 \
      --p0-count 0 --p1-count 3 [--p2-count 5] [--rounds-max 3] --review-dir DIR

convergence.md 格式：
  # 收敛记录

  | 轮次 | 去AI评分 | 同行评审 | P0 | P1 | P2 | 状态 |
  |------|---------|---------|----|----|----|----|
  | 1    | 6.5     | 6.0     | 2  | 5  | 8  | continue |

输出（stdout，JSON）：
  {"round": N, "converged": bool, "scores": {"deai": x, "peer": y},
   "p0_count": N, "p1_count": N, "stagnant": bool,
   "action": "continue"|"stop"|"escalate", "reason": "...",
   "criteria": {...}, "p2_count": N, "rounds_max": N, "convergence_file": "..."}

退出码：0=成功；1=文件写入失败；2=参数错误。
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

HEADER = """# 收敛记录

| 轮次 | 去AI评分 | 同行评审 | P0 | P1 | P2 | 状态 |
|------|---------|---------|----|----|----|----|
"""

ROW_RE = re.compile(
    r"^\|\s*(\d+)\s*\|\s*(\d+(?:\.\d+)?)\s*\|\s*(\d+(?:\.\d+)?)\s*\|"
    r"\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]*?)\s*\|")

DEAI_MIN = 8.0      # c1 阈值
PEER_MIN = 7.0      # c2 阈值
P1_MAX = 3          # c4 阈值
STAGNANT_DELTA = 0.5  # 停滞判定：单轮改善小于此值视为无改善


def conv_file_path(review_dir):
    return os.path.join(review_dir, "convergence.md")


def read_history(path):
    """解析 convergence.md，返回 {round: record} 字典"""
    history = {}
    if not os.path.isfile(path):
        return history
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f.read().splitlines():
            m = ROW_RE.match(line.strip())
            if m:
                rnd = int(m.group(1))
                history[rnd] = {
                    "round": rnd,
                    "deai": float(m.group(2)),
                    "peer": float(m.group(3)),
                    "p0": int(m.group(4)),
                    "p1": int(m.group(5)),
                    "p2": int(m.group(6)),
                    "status": m.group(7).strip(),
                }
    return history


def write_history(path, history):
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    lines = [HEADER.rstrip("\n")]  # 标题+空行+表头（HEADER 内部已含空行）
    for rnd in sorted(history):
        r = history[rnd]
        lines.append("| %d | %.1f | %.1f | %d | %d | %d | %s |" % (
            rnd, r["deai"], r["peer"], r["p0"], r["p1"], r["p2"], r["status"]))
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def no_improve(a, b):
    """轮次对 a→b 是否「无改善」：两维度评分提升均 < STAGNANT_DELTA"""
    return (b["deai"] - a["deai"]) < STAGNANT_DELTA and (b["peer"] - a["peer"]) < STAGNANT_DELTA


def fmt_score(x):
    return ("%.1f" % x).rstrip("0").rstrip(".") if x != int(x) else str(int(x))


def main():
    parser = argparse.ArgumentParser(
        prog="convergence_check.py",
        description="paper-review 收敛判定：记录本轮质量数据到 convergence.md，"
                    "按5项收敛条件与停滞规则输出 action(continue/stop/escalate) JSON。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--round", metavar="N", type=int, required=True,
                        help="当前轮次（从1开始）")
    parser.add_argument("--deai-score", metavar="X", type=float, required=True,
                        help="本轮去AI评分（1-10）")
    parser.add_argument("--peer-score", metavar="X", type=float, required=True,
                        help="本轮同行评审评分（1-10，Decision映射：Accept=9/Minor=8/Major=6/Reject=4）")
    parser.add_argument("--p0-count", metavar="N", type=int, required=True,
                        help="本轮 P0 问题数")
    parser.add_argument("--p1-count", metavar="N", type=int, required=True,
                        help="本轮 P1 问题数")
    parser.add_argument("--p2-count", metavar="N", type=int, default=0,
                        help="本轮 P2 问题数")
    parser.add_argument("--rounds-max", metavar="N", type=int, default=3,
                        help="收敛循环最大轮数")
    parser.add_argument("--review-dir", metavar="DIR", required=True,
                        help="审查输出目录（convergence.md 所在处）")
    args = parser.parse_args()

    if args.round < 1:
        parser.error("--round 必须 >= 1")
    if not (0 <= args.deai_score <= 10) or not (0 <= args.peer_score <= 10):
        parser.error("评分必须在 0-10 范围内")
    if min(args.p0_count, args.p1_count, args.p2_count) < 0:
        parser.error("问题计数不能为负")
    if args.rounds_max < 1:
        parser.error("--rounds-max 必须 >= 1")

    path = conv_file_path(args.review_dir)
    history = read_history(path)
    prev = history.get(args.round - 1)
    prev2 = history.get(args.round - 2)

    cur = {
        "round": args.round,
        "deai": args.deai_score,
        "peer": args.peer_score,
        "p0": args.p0_count,
        "p1": args.p1_count,
        "p2": args.p2_count,
    }

    # ── 5项收敛条件 ──
    c1 = cur["deai"] >= DEAI_MIN
    c2 = cur["peer"] >= PEER_MIN
    c3 = cur["p0"] == 0
    c4 = cur["p1"] <= P1_MAX
    c5 = (prev is not None and cur["p0"] == 0
          and prev["p0"] == 0 and cur["p1"] <= prev["p1"])
    converged = c1 and c2 and c3 and c4 and c5

    # ── 停滞检测：连续2个轮次间隔无改善（需至少3轮数据）──
    stagnant = bool(prev and prev2
                    and no_improve(prev2, prev) and no_improve(prev, cur))

    # ── 动作判定 ──
    if converged:
        action = "stop"
        status = "converged"
        reason = "已收敛：5项条件全部满足（去AI≥8、同行评审≥7、P0=0、P1≤3、连续2轮无新增P0/P1）"
    elif args.round >= args.rounds_max:
        action = "stop"
        status = "stop"
        reason = "达到最大轮数 %d 仍未满足全部收敛条件，终止循环，输出当前状态与未解决问题清单" % args.rounds_max
    elif stagnant:
        action = "escalate"
        status = "escalate"
        reason = "连续2轮去AI与同行评审评分改善均 < %.1f 分（停滞），暂停循环，请用户决策：继续 / 停止 / 调整策略" % STAGNANT_DELTA
    else:
        action = "continue"
        status = "continue"
        fails = []
        if not c1:
            fails.append("去AI评分 %s < %s" % (fmt_score(cur["deai"]), fmt_score(DEAI_MIN)))
        if not c2:
            fails.append("同行评审评分 %s < %s" % (fmt_score(cur["peer"]), fmt_score(PEER_MIN)))
        if not c3:
            fails.append("P0 = %d（需 = 0）" % cur["p0"])
        if not c4:
            fails.append("P1 = %d（需 ≤ %d）" % (cur["p1"], P1_MAX))
        if not c5:
            fails.append("连续2轮无新增P0/P1 未满足（历史轮次不足或 P0/P1 未清零回落）")
        reason = "未收敛：" + "；".join(fails)

    cur["status"] = status
    history[args.round] = cur  # 同轮次重复提交 → 覆盖
    try:
        write_history(path, history)
    except OSError as e:
        print("错误：写入收敛记录失败: %s" % e, file=sys.stderr)
        sys.exit(1)

    result = {
        "round": args.round,
        "converged": converged,
        "scores": {"deai": cur["deai"], "peer": cur["peer"]},
        "p0_count": cur["p0"],
        "p1_count": cur["p1"],
        "stagnant": stagnant,
        "action": action,
        "reason": reason,
        "criteria": {"c1_deai>=8": c1, "c2_peer>=7": c2, "c3_p0==0": c3,
                     "c4_p1<=3": c4, "c5_no_new_p0p1_2rounds": c5},
        "p2_count": cur["p2"],
        "rounds_max": args.rounds_max,
        "convergence_file": path.replace("\\", "/"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
