#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""track_revisions.py — paper-review 修改日志追踪器

功能：
  1. --log "原句|修改后|理由|来源阶段[|严重度]" : 追加一条修改记录到 revision_log.md
     - 编号自动递增，时间为当前 HH:MM
     - 严重度可作第5段显式给出（P0/P1/P2）；否则从「理由/来源」文本中识别 P 标记；
       均未标注时默认 P2。严重度最终以 [P0]/[P1]/[P2] 前缀写入「理由」列，便于统计
     - 来源阶段建议取值：阶段1-去AI / 阶段2-研讨 / 阶段3-同行评审 / 阶段5-收敛循环
  2. --summary : 统计修改记录，输出 JSON

revision_log.md 格式：
  # 修改日志

  | # | 原句 | 修改后 | 理由 | 来源 | 时间 |
  |---|------|--------|------|------|------|
  | 1 | ... | ... | [P1] ... | 阶段1-去AI | HH:MM |

用法：
  python track_revisions.py --log "原句|修改后|理由|阶段1-去AI" --review-dir DIR
  python track_revisions.py --log "原句|修改后|理由|阶段3-同行评审|P0" --review-dir DIR
  python track_revisions.py --summary --review-dir DIR

输出（stdout，JSON）：
  log     → {"success": true, "action": "log", "record_no": N, "severity": "P1",
             "source_norm": "de-ai", "log_file": "..."}
  summary → {"total": N, "by_source": {"de-ai": N, "discussion": N, "peer": N},
             "by_severity": {"P0": N, "P1": N, "P2": N}, "log_file": "..."}
             （存在无法归类的来源时，by_source 追加 "other" 键）

退出码：0=成功；1=文件操作失败；2=参数错误。
"""
import argparse
import datetime
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

HEADER = """# 修改日志

| # | 原句 | 修改后 | 理由 | 来源 | 时间 |
|---|------|--------|------|------|------|
"""

SEV_RE = re.compile(r"\bP([012])\b")


def log_file_path(review_dir):
    return os.path.join(review_dir, "revision_log.md")


def clean_cell(s):
    """单元格清洗：去换行、折叠空白、替换竖线（避免破坏表格）"""
    s = s.replace("\r", " ").replace("\n", " ").replace("|", "/")
    return re.sub(r"\s+", " ", s).strip()


def norm_source(src):
    """来源阶段 → 统计桶：de-ai / discussion / peer / other"""
    low = src.lower()
    if ("去ai" in low) or ("de-ai" in low) or ("deai" in low) or ("阶段1" in src):
        return "de-ai"
    if ("研讨" in src) or ("discussion" in low) or ("阶段2" in src):
        return "discussion"
    if ("评审" in src) or ("peer" in low) or ("ars" in low) or ("阶段3" in src):
        return "peer"
    return "other"


def parse_records(lines):
    """解析日志表格数据行（首格为数字的行），返回单元格列表的列表"""
    records = []
    for line in lines or []:
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 5 or not cells[0].isdigit():
            continue
        records.append(cells)
    return records


def do_log(record_str, review_dir):
    parts = [p.strip() for p in record_str.split("|")]
    if len(parts) not in (4, 5):
        print("错误：--log 需为 4 或 5 段（原句|修改后|理由|来源阶段[|严重度]），"
              "当前 %d 段。各段内容不得包含竖线 |" % len(parts), file=sys.stderr)
        sys.exit(2)
    orig, new, reason, source = parts[:4]
    if not orig or not new:
        print("错误：原句与修改后内容不能为空", file=sys.stderr)
        sys.exit(2)

    sev = None
    if len(parts) == 5:
        m = re.fullmatch(r"[Pp]([012])", parts[4])
        if not m:
            print("错误：第5段严重度必须为 P0/P1/P2，收到: %s" % parts[4], file=sys.stderr)
            sys.exit(2)
        sev = "P" + m.group(1)
    if sev is None:
        m = SEV_RE.search(reason + " " + source)
        sev = ("P" + m.group(1)) if m else "P2"
    if not SEV_RE.search(reason):
        reason = "[%s] %s" % (sev, reason)  # 严重度写入理由列，供 --summary 统计

    path = log_file_path(review_dir)
    try:
        os.makedirs(review_dir, exist_ok=True)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8-sig") as f:
                existing = f.read()
        else:
            existing = ""
            print("警告：revision_log.md 不存在，自动创建（含表头）", file=sys.stderr)
        if not existing.lstrip().startswith("# 修改日志"):
            existing = HEADER + existing.lstrip("\n")  # 空文件/缺表头时补齐表头
        record_no = len(parse_records(existing.splitlines())) + 1
        now = datetime.datetime.now().strftime("%H:%M")
        row = "| %d | %s | %s | %s | %s | %s |" % (
            record_no, clean_cell(orig), clean_cell(new),
            clean_cell(reason), clean_cell(source), now)
        if existing and not existing.endswith("\n"):
            existing += "\n"
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(existing + row + "\n")
    except OSError as e:
        print("错误：写入修改日志失败: %s" % e, file=sys.stderr)
        sys.exit(1)

    result = {
        "success": True,
        "action": "log",
        "record_no": record_no,
        "severity": sev,
        "source_norm": norm_source(source),
        "log_file": path.replace("\\", "/"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


def do_summary(review_dir):
    path = log_file_path(review_dir)
    records = []
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8-sig") as f:
            records = parse_records(f.read().splitlines())
    else:
        print("警告：revision_log.md 不存在，按空日志统计: %s" % path, file=sys.stderr)

    by_source = {"de-ai": 0, "discussion": 0, "peer": 0}
    by_severity = {"P0": 0, "P1": 0, "P2": 0}
    for cells in records:
        reason = cells[3] if len(cells) > 3 else ""
        source = cells[4] if len(cells) > 4 else ""
        m = SEV_RE.search(" ".join(cells))
        sev = ("P" + m.group(1)) if m else "P2"
        by_severity[sev] += 1
        bucket = norm_source(source)
        by_source[bucket] = by_source.get(bucket, 0) + 1

    result = {
        "total": len(records),
        "by_source": by_source,
        "by_severity": by_severity,
        "log_file": path.replace("\\", "/"),
    }
    if not by_source.get("other"):
        by_source.pop("other", None)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        prog="track_revisions.py",
        description="paper-review 修改日志追踪：逐条记录修改（原句/修改后/理由/来源/严重度），"
                    "输出统计 JSON。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--log", metavar="RECORD", default=None,
                        help='追加一条记录，格式："原句|修改后|理由|来源阶段[|严重度]"（4或5段，段内不含竖线）')
    parser.add_argument("--summary", action="store_true",
                        help="输出修改统计 JSON（total / by_source / by_severity）")
    parser.add_argument("--review-dir", metavar="DIR", default=".review",
                        help="审查输出目录（revision_log.md 所在处）")
    args = parser.parse_args()

    if bool(args.log) == bool(args.summary):
        parser.error("--log 与 --summary 必须且只能指定其一")

    if args.log:
        do_log(args.log, args.review_dir)
    else:
        do_summary(args.review_dir)


if __name__ == "__main__":
    main()
