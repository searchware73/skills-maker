#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_artifacts.py — 阶段产物完整性门禁（v2.1 条目11/18）

背景（备忘 §十一 条目11，2026-11-10 连续两篇实测）：Workflow harness 会把启动时的
最新用户消息作为「triggering user request」注入每个子代理并声明最高优先级，席位代理
可能被无关提问劫持（全昌寿稿 S4、于小岚稿 S3 未产出报告），而 Workflow 只按
「代理是否正常结束」计数（agents_done=9, agents_error=0），不校验约定产物是否存在。
条目18：阶段2 四技能审计同理。

本脚本是两处门禁（1b 之后 1c 之前；2a 之后 2b 之前）与 Step 6 复核的共用校验器：
  - 校验 {run_dir}{subdir}/ 下**恰好** --expect 列表的产物存在且非空；
  - expect 记号按前缀匹配文件主名（`S1` 匹配 `S1-EIC统筹.md`；也接受全名）；
  - 缺失/空文件 → redispatch 清单（**只重派缺失席位，不重跑整阶段**）；
  - 不在 expect 列表内的多余文件 → unexpected（可能是被劫持代理写错位置的产物，
    须人工核对，同样判不完整）；
  - 不完整 exit 1（门禁不通过，不得进入 1c/1d 或 2b/2c）。

stdout（JSON）：
  {"success": bool, "complete": bool, "subdir": "...", "dir": "...",
   "expected": [...], "found": {"S1": ["S1-EIC统筹.md"]}, "missing": [...],
   "empty": [...], "unexpected": [...], "redispatch": [...], "problems": [...]}

用法：
  python check_artifacts.py --run-dir DIR --subdir seat_reports \
      --expect S1,S2,S3,S4,S5,S6,S7 [--ext .md]
  python check_artifacts.py --run-dir DIR --subdir deai_audits \
      --expect stop-slop,academic-humanizer,humanize-writing,humanizer-zh

退出码：0=完整；1=不完整（见 redispatch/problems）；2=参数错误。
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


def fail(msg, code=1):
    print("错误：%s" % msg, file=sys.stderr)
    sys.exit(code)


def nonempty(path):
    """文件存在且去除空白后非空"""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return bool(f.read().strip())
    except OSError:
        return False


def main():
    parser = argparse.ArgumentParser(
        prog="check_artifacts.py",
        description="阶段产物完整性门禁（条目11/18）：{run_dir}{subdir}/ 下恰好 "
                    "--expect 列表的产物存在且非空；缺失/空文件进 redispatch 清单"
                    "（只重派缺失席位，不重跑整阶段）；不完整 exit 1。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--run-dir", required=True, metavar="DIR",
                        help="本轮产物目录（.review/rN/）")
    parser.add_argument("--subdir", required=True, metavar="NAME",
                        help="产物子目录名（seat_reports / deai_audits）")
    parser.add_argument("--expect", required=True, metavar="LIST",
                        help="预期产物记号，逗号分隔（前缀匹配文件主名："
                             "S1 匹配 S1-EIC统筹.md）")
    parser.add_argument("--ext", default=".md", metavar="EXT",
                        help="产物文件扩展名")
    args = parser.parse_args()

    tokens = [t.strip() for t in args.expect.split(",") if t.strip()]
    if not tokens:
        fail("--expect 不能为空", code=2)

    target = os.path.join(args.run_dir, args.subdir)
    problems = []
    result = {"success": False, "complete": False, "subdir": args.subdir,
              "dir": os.path.abspath(target), "expected": tokens,
              "found": {}, "missing": [], "empty": [], "unexpected": [],
              "redispatch": [], "problems": problems}

    if not os.path.isdir(target):
        problems.append("产物目录不存在：%s（阶段未执行或代理未落盘）" % target)
        result["missing"] = list(tokens)
        result["redispatch"] = list(tokens)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("门禁不通过：目录缺失，全部 %d 项待重派。" % len(tokens), file=sys.stderr)
        return 1

    ext = args.ext if args.ext.startswith(".") else "." + args.ext
    files = sorted(f for f in os.listdir(target) if f.endswith(ext))

    matched = set()
    for tok in tokens:
        hits = [f for f in files
                if os.path.splitext(f)[0] == tok
                or os.path.splitext(f)[0].startswith(tok)]
        if not hits:
            result["missing"].append(tok)
            continue
        result["found"][tok] = hits
        matched.update(hits)
        if not any(nonempty(os.path.join(target, f)) for f in hits):
            result["empty"].append(tok)

    result["unexpected"] = [f for f in files if f not in matched]

    for tok in result["missing"]:
        problems.append("缺失产物：%s/%s*%s（该席代理未落盘——可能被 triggering "
                        "request 劫持）" % (args.subdir, tok, ext))
    for tok in result["empty"]:
        problems.append("空文件产物：%s/%s*%s（代理结束但未写内容）"
                        % (args.subdir, tok, ext))
    for f in result["unexpected"]:
        problems.append("预期外文件：%s/%s（不在 --expect 列表，须人工核对来源；"
                        "「恰好 N 份」判定不通过）" % (args.subdir, f))

    result["redispatch"] = result["missing"] + result["empty"]
    result["complete"] = not (result["missing"] or result["empty"]
                              or result["unexpected"])
    result["success"] = result["complete"]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["complete"]:
        print("门禁不通过：%d 个问题；redispatch=%s（只重派这些席位/审计，"
              "≤3 轮，每轮后重跑本门禁；仍缺则如实降级并告知用户，不得伪装齐席）。"
              % (len(problems), result["redispatch"]), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
