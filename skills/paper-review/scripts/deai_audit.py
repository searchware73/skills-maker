#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deai_audit.py — paper-review 去AI审查日志管理器

功能：
  1. --phase start : 在 review_dir 创建 deai_log.md（含表头；重复执行会覆盖重建）
  2. --log SKILL   : 追加一条技能执行记录（编号自动递增，时间为当前 HH:MM）
  3. --verify      : 校验 4 个去AI技能是否均已记录，输出 JSON

四个去AI技能（固定，顺序执行）：
  stop-slop / academic-humanizer / humanize-writing / humanizer-zh

deai_log.md 格式：
  # 去AI审查日志

  | # | 技能 | 发现数 | 修改数 | 时间 |
  |---|------|--------|--------|------|
  | 1 | stop-slop | N | M | HH:MM |
  ...

用法：
  python deai_audit.py --phase start --review-dir DIR
  python deai_audit.py --log stop-slop --findings-count 5 --edits-count 3 --review-dir DIR
  python deai_audit.py --verify --review-dir DIR

输出（stdout，JSON）：
  start  → {"success": true, "action": "start", "log_file": "..."}
  log    → {"success": true, "action": "log", "skill": "...", "record_no": N, "log_file": "..."}
  verify → {"all_logged": true/false, "logged": [...], "missing": [...], "log_file": "..."}

退出码：0=成功；1=verify 未通过或文件操作失败；2=参数错误。
"""
import argparse
import datetime
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

SKILLS = ["stop-slop", "academic-humanizer", "humanize-writing", "humanizer-zh"]

HEADER = """# 去AI审查日志

| # | 技能 | 发现数 | 修改数 | 时间 |
|---|------|--------|--------|------|
"""


def log_file_path(review_dir):
    return os.path.join(review_dir, "deai_log.md")


def read_lines(path):
    """读取文件行；不存在返回 None"""
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read().splitlines()


def parse_records(lines):
    """解析日志表格数据行，返回单元格列表的列表（跳过表头/分隔行）"""
    records = []
    for line in lines or []:
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 5:
            continue
        if cells[0] == "#" or not cells[0]:
            continue
        if all(c and set(c) <= set("-: ") for c in cells):
            continue  # 分隔行
        records.append(cells)
    return records


def ensure_dir(review_dir):
    os.makedirs(review_dir, exist_ok=True)


def do_start(review_dir):
    ensure_dir(review_dir)
    path = log_file_path(review_dir)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(HEADER)
    return {
        "success": True,
        "action": "start",
        "log_file": path.replace("\\", "/"),
    }, 0


def do_log(skill, findings, edits, review_dir):
    ensure_dir(review_dir)
    path = log_file_path(review_dir)
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8-sig") as f:
            existing = f.read()
    else:
        existing = ""
        print("警告：deai_log.md 不存在，自动创建（建议先执行 --phase start）", file=sys.stderr)
    if not existing.lstrip().startswith("# 去AI审查日志"):
        existing = HEADER + existing.lstrip("\n")  # 空文件/缺表头时补齐表头
    record_no = len(parse_records(existing.splitlines())) + 1
    now = datetime.datetime.now().strftime("%H:%M")
    row = "| %d | %s | %d | %d | %s |" % (record_no, skill, findings, edits, now)
    if existing and not existing.endswith("\n"):
        existing += "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(existing + row + "\n")
    return {
        "success": True,
        "action": "log",
        "skill": skill,
        "record_no": record_no,
        "log_file": path.replace("\\", "/"),
    }, 0


def do_verify(review_dir):
    path = log_file_path(review_dir)
    lines = read_lines(path)
    if lines is None:
        result = {
            "all_logged": False,
            "logged": [],
            "missing": list(SKILLS),
            "log_file": path.replace("\\", "/"),
        }
        print("错误：deai_log.md 不存在: %s" % path, file=sys.stderr)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1
    found = set()
    for cells in parse_records(lines):
        found.add(cells[1])
    logged = [s for s in SKILLS if s in found]
    missing = [s for s in SKILLS if s not in found]
    result = {
        "all_logged": not missing,
        "logged": logged,
        "missing": missing,
        "log_file": path.replace("\\", "/"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if missing:
        print("错误：以下去AI技能尚未记录: %s" % ", ".join(missing), file=sys.stderr)
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="deai_audit.py",
        description="paper-review 去AI审查日志管理：初始化 deai_log.md、"
                    "追加 4 个去AI技能的执行记录、校验记录完整性，输出 JSON。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--phase", choices=["start"], default=None,
                        help="start：创建 deai_log.md（含表头）")
    parser.add_argument("--log", metavar="SKILL_NAME", choices=SKILLS, default=None,
                        help="追加一条技能记录（须配合 --findings-count/--edits-count）")
    parser.add_argument("--findings-count", metavar="N", type=int, default=None,
                        help="该技能发现的问题数")
    parser.add_argument("--edits-count", metavar="M", type=int, default=None,
                        help="该技能实际修改处数")
    parser.add_argument("--verify", action="store_true",
                        help="校验 4 个技能是否均已记录，输出 JSON")
    parser.add_argument("--review-dir", metavar="DIR", required=True,
                        help="审查输出目录（.review/）")
    args = parser.parse_args()

    modes = sum([bool(args.phase), bool(args.log), bool(args.verify)])
    if modes != 1:
        parser.error("--phase start / --log / --verify 三者必须且只能指定其一")
    if args.log:
        if args.findings_count is None or args.edits_count is None:
            parser.error("--log 需要同时给出 --findings-count 与 --edits-count")
        if args.findings_count < 0 or args.edits_count < 0:
            parser.error("--findings-count/--edits-count 不能为负数")

    if args.phase == "start":
        result, code = do_start(args.review_dir)
    elif args.log:
        result, code = do_log(args.log, args.findings_count, args.edits_count,
                              args.review_dir)
    else:
        sys.exit(do_verify(args.review_dir))

    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(code)


if __name__ == "__main__":
    main()
