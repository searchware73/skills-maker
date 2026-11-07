#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""resume.py — paper-review 跨终端续跑快照维护脚本

维护 {run_dir}/RESUME.md（v2.0 强制产物）：每阶段边界更新阶段状态与恢复点，
新终端会话通过 show/check 恢复进度，避免长流水线中断后重跑。

RESUME.md 结构（本脚本自产自得，格式稳定，人类可读）：
  1. 头部元信息列表：- 论文: / - 版本: / - 轮次: / - 类型: / - 更新时间:
  2. 「## 阶段状态」表：| 阶段 | 状态 | 产物 | 备注 |（固定 7 个阶段全量列出）
  3. 「## 恢复点」节：- 下一步动作: / - 恢复命令: / - 环境备忘:（可多行）

用法（--run-dir 为全局参数，放在子命令前）：
  python resume.py --run-dir DIR init [--paper P] [--version vN] [--round rN] \
      [--doctype T] [--force]
  python resume.py --run-dir DIR set --stage STAGE --status STATUS \
      [--artifact PATH] [--note TEXT]
  python resume.py --run-dir DIR next --action TEXT [--cmd TEXT] [--env TEXT]...
  python resume.py --run-dir DIR show
  python resume.py --run-dir DIR check

语义说明：
  - init：创建 RESUME.md（全部 stage=pending）；已存在时不覆盖（existed=true），
    除非 --force
  - set ：就地改写对应阶段行的 状态/产物/备注 列，并刷新头部「更新时间」；
    --artifact/--note 未提供时保留原值
  - next：重写「## 恢复点」节；--cmd/--env 未提供时保留原值；--env 可多次
    提供（每次提供即整体替换环境备忘行组）
  - check：校验文件存在、7 阶段齐全、状态合法、存在 in_progress 阶段时
    「下一步动作」非空

stdout（JSON）：
  init  → {"success": true, "action": "init", "existed": false, "resume_file": "..."}
  set   → {"success": true, "action": "set", "stage": "...", "status": "...", ...}
  next  → {"success": true, "action": "next", "next_action": "...", ...}
  show  → {"success": true, "meta": {paper, version, round, doctype, updated},
           "stage_status": {stage: status}, "artifacts": {stage: path},
           "next": {"action": "...", "cmd": "...", "env": [...]}, "resume_file": "..."}
  check → 通过 {"valid": true, "problems": [], ...}；
          否则 {"valid": false, "problems": [...], ...}

退出码：0=成功（check 为校验通过）；1=运行时失败（文件缺失/损坏、check 未通过）；
        2=参数错误（含非法 stage/status 枚举值）。
"""
import argparse
import io
import json
import os
import re
import sys
from datetime import datetime

# 修复 Windows 下 GBK 编码问题，强制 UTF-8 输出
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

STAGES = ("step0-env", "stage1-panel", "stage2-deai", "stage3-merge",
          "stage4-fix", "stage5-converge", "step6-report")
STATUSES = ("pending", "in_progress", "done", "failed", "skipped")

RESUME_NAME = "RESUME.md"
TS_FMT = "%Y-%m-%d %H:%M"

# 头部元信息标签 → show JSON meta 键
META_LABELS = (("论文", "paper"), ("版本", "version"), ("轮次", "round"),
               ("类型", "doctype"), ("更新时间", "updated"))

NEXT_SECTION = "恢复点"
STAGE_SECTION = "阶段状态"

UPDATED_RE = re.compile(r"^-\s*更新时间\s*:")
ACTION_RE = re.compile(r"^-\s*下一步动作\s*:\s*(.*)$")
CMD_RE = re.compile(r"^-\s*恢复命令\s*:\s*(.*)$")
ENV_RE = re.compile(r"^-\s*环境备忘\s*:\s*(.*)$")
META_RE = re.compile(r"^-\s*([^:]+):\s*(.*)$")
ROW_SPLIT_RE = re.compile(r"(?<!\\)\|")   # 单元格分隔符（跳过转义的 \|）


def to_posix(path):
    return path.replace("\\", "/")


def fail(msg, code=2):
    print("错误：%s" % msg, file=sys.stderr)
    sys.exit(code)


def now_str():
    return datetime.now().strftime(TS_FMT)


def resume_path(run_dir):
    return os.path.join(run_dir, RESUME_NAME)


def sanitize_text(text):
    """md 内文本必须单行：换行折叠为空格"""
    return re.sub(r"\s*\n\s*", " ", text or "").strip()


def escape_cell(text):
    """表格单元格：单行化 + 转义竖线"""
    return sanitize_text(text).replace("|", "\\|")


def _read_text(path):
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    return None


def read_resume_text(path):
    """读取 RESUME.md，缺失/不可读时按运行时失败退出（code=1）"""
    if not os.path.isfile(path):
        fail("RESUME.md 不存在，请先执行 init: %s" % to_posix(path), code=1)
    text = _read_text(path)
    if text is None:
        fail("无法读取 RESUME.md: %s" % to_posix(path), code=1)
    return text


def write_lines(path, lines):
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
    except OSError as e:
        fail("写入 RESUME.md 失败: %s" % e, code=1)


# ────────────────────────── 解析 ──────────────────────────

def parse_table_row(line):
    """'| a | b | c | d |' → ['a','b','c','d']（去转义）；非表格行返回 None"""
    s = line.strip()
    if not s.startswith("|"):
        return None
    parts = ROW_SPLIT_RE.split(s)
    if parts and parts[0].strip() == "":
        parts = parts[1:]
    if parts and parts[-1].strip() == "":
        parts = parts[:-1]
    return [p.strip().replace("\\|", "|") for p in parts]


def parse_resume(text):
    """RESUME.md 全文 → {"meta", "stage_status", "artifacts", "next"}"""
    meta = {}
    stage_status = {}
    artifacts = {}
    nxt = {"action": "", "cmd": "", "env": []}
    section = None
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("## "):
            section = stripped[3:].strip()
            continue
        if section == NEXT_SECTION:
            m = ACTION_RE.match(stripped)
            if m:
                nxt["action"] = m.group(1).strip()
                continue
            m = CMD_RE.match(stripped)
            if m:
                nxt["cmd"] = m.group(1).strip()
                continue
            m = ENV_RE.match(stripped)
            if m:
                if m.group(1).strip():
                    nxt["env"].append(m.group(1).strip())
                continue
        cells = parse_table_row(raw)
        if cells is not None:
            if len(cells) >= 2 and cells[0] in STAGES:
                stage_status[cells[0]] = cells[1]
                artifact = cells[2] if len(cells) > 2 else ""
                if artifact:
                    artifacts[cells[0]] = artifact
            continue
        if section is None:      # 头部元信息区（首个 ## 节之前）
            m = META_RE.match(stripped)
            if m:
                label = m.group(1).strip()
                for zh, key in META_LABELS:
                    if label == zh:
                        meta[key] = m.group(2).strip()
                        break
    return {"meta": meta, "stage_status": stage_status,
            "artifacts": artifacts, "next": nxt}


# ────────────────────────── 生成 ──────────────────────────

def build_resume_lines(paper="", version="", round_="", doctype=""):
    lines = [
        "# RESUME — paper-review 续跑快照",
        "",
        "- 论文: %s" % sanitize_text(paper),
        "- 版本: %s" % sanitize_text(version),
        "- 轮次: %s" % sanitize_text(round_),
        "- 类型: %s" % sanitize_text(doctype),
        "- 更新时间: %s" % now_str(),
        "",
        "## %s" % STAGE_SECTION,
        "",
        "| 阶段 | 状态 | 产物 | 备注 |",
        "| --- | --- | --- | --- |",
    ]
    for s in STAGES:
        lines.append("| %s | pending |  |  |" % s)
    lines += [
        "",
        "## %s" % NEXT_SECTION,
        "",
        "- 下一步动作: ",
        "- 恢复命令: ",
        "- 环境备忘: ",
    ]
    return lines


def build_next_section(action, cmd, env):
    section = [
        "## %s" % NEXT_SECTION,
        "",
        "- 下一步动作: %s" % sanitize_text(action),
        "- 恢复命令: %s" % sanitize_text(cmd),
    ]
    env = [sanitize_text(e) for e in env if sanitize_text(e)]
    if env:
        section += ["- 环境备忘: %s" % e for e in env]
    else:
        section.append("- 环境备忘: ")
    section.append("")
    return section


def touch_updated(lines):
    """刷新头部「更新时间」行；未找到时输出警告（stderr）"""
    ts = now_str()
    for i, ln in enumerate(lines):
        if UPDATED_RE.match(ln.strip()):
            lines[i] = "- 更新时间: %s" % ts
            return True
    print("警告：未找到「更新时间」行，跳过刷新", file=sys.stderr)
    return False


# ────────────────────────── 子命令 ──────────────────────────

def do_init(args):
    path = resume_path(args.run_dir)
    existed = os.path.isfile(path)
    rf = to_posix(os.path.abspath(path))
    if existed and not args.force:
        print("警告：RESUME.md 已存在，未覆盖（如需重建请加 --force）: %s" % rf,
              file=sys.stderr)
        return {"success": True, "action": "init", "existed": True,
                "resume_file": rf}, 0
    try:
        os.makedirs(args.run_dir, exist_ok=True)
    except OSError as e:
        fail("创建 run-dir 失败: %s" % e, code=1)
    lines = build_resume_lines(args.paper or "", args.version or "",
                               args.round or "", args.doctype or "")
    write_lines(path, lines)
    return {"success": True, "action": "init", "existed": False,
            "resume_file": rf}, 0


def do_set(args):
    path = resume_path(args.run_dir)
    text = read_resume_text(path)
    lines = text.splitlines()
    row_idx, cells = None, None
    for i, ln in enumerate(lines):
        c = parse_table_row(ln)
        if c and len(c) >= 4 and c[0] == args.stage:
            row_idx, cells = i, c
            break
    if row_idx is None:
        fail("RESUME.md 中未找到阶段行 '%s'（文件可能损坏，可 init --force 重建）"
             % args.stage, code=1)
    artifact = to_posix(args.artifact) if args.artifact is not None else cells[2]
    note = args.note if args.note is not None else cells[3]
    lines[row_idx] = "| %s | %s | %s | %s |" % (
        args.stage, args.status, escape_cell(artifact), escape_cell(note))
    touch_updated(lines)
    write_lines(path, lines)
    rf = to_posix(os.path.abspath(path))
    return {"success": True, "action": "set", "stage": args.stage,
            "status": args.status,
            "artifact": to_posix(artifact) if artifact else None,
            "resume_file": rf}, 0


def do_next(args):
    path = resume_path(args.run_dir)
    text = read_resume_text(path)
    lines = text.splitlines()
    old = parse_resume(text)["next"]
    cmd = args.cmd if args.cmd is not None else old["cmd"]
    env = args.env if args.env else old["env"]
    try:
        h = next(i for i, ln in enumerate(lines)
                 if ln.strip() == "## %s" % NEXT_SECTION)
    except StopIteration:
        fail("RESUME.md 缺少「## %s」节（文件可能损坏，可 init --force 重建）"
             % NEXT_SECTION, code=1)
    end = len(lines)
    for j in range(h + 1, len(lines)):
        if lines[j].strip().startswith("## "):
            end = j
            break
    lines[h:end] = build_next_section(args.next_action, cmd, env)
    touch_updated(lines)
    write_lines(path, lines)
    rf = to_posix(os.path.abspath(path))
    return {"success": True, "action": "next",
            "next_action": sanitize_text(args.next_action), "resume_file": rf}, 0


def do_show(args):
    path = resume_path(args.run_dir)
    data = parse_resume(read_resume_text(path))
    meta = data["meta"]
    return {
        "success": True,
        "meta": {
            "paper": meta.get("paper") or None,
            "version": meta.get("version") or None,
            "round": meta.get("round") or None,
            "doctype": meta.get("doctype") or None,
            "updated": meta.get("updated") or None,
        },
        "stage_status": data["stage_status"],
        "artifacts": data["artifacts"],
        "next": data["next"],
        "resume_file": to_posix(os.path.abspath(path)),
    }, 0


def do_check(args):
    path = resume_path(args.run_dir)
    rf = to_posix(os.path.abspath(path))
    if not os.path.isfile(path):
        return {"valid": False, "problems": ["RESUME.md 不存在: %s" % rf],
                "resume_file": rf}, 1
    text = _read_text(path)
    if text is None:
        return {"valid": False, "problems": ["无法读取 RESUME.md: %s" % rf],
                "resume_file": rf}, 1
    data = parse_resume(text)
    ss = data["stage_status"]
    problems = []
    for s in STAGES:
        if s not in ss:
            problems.append("缺少阶段: %s" % s)
        elif ss[s] not in STATUSES:
            problems.append("阶段 %s 状态非法: %s（合法值: %s）"
                            % (s, ss[s], "|".join(STATUSES)))
    for s in ss:
        if s not in STAGES:
            problems.append("未知阶段: %s" % s)
    in_progress = [s for s in STAGES if ss.get(s) == "in_progress"]
    if in_progress and not data["next"]["action"].strip():
        for s in in_progress:
            problems.append("阶段 %s 为 in_progress 但「下一步动作」为空"
                            "（请执行: resume.py --run-dir ... next --action ...）" % s)
    valid = not problems
    return {"valid": valid, "problems": problems, "in_progress": in_progress,
            "resume_file": rf}, (0 if valid else 1)


def main():
    parser = argparse.ArgumentParser(
        prog="resume.py",
        description="paper-review 跨终端续跑快照：维护 {run_dir}/RESUME.md"
                    "（头部元信息 + 阶段状态表 + 恢复点），供新会话恢复进度。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--run-dir", metavar="DIR", default=".",
                        help="运行目录（RESUME.md 所在）")
    sub = parser.add_subparsers(dest="action", required=True)

    p_init = sub.add_parser("init", help="创建 RESUME.md（全部阶段 pending）；已存在时不覆盖，除非 --force")
    p_init.add_argument("--paper", metavar="TEXT", default=None,
                        help="论文标题/标识")
    p_init.add_argument("--version", metavar="vN", default=None,
                        help="稿件版本（如 v2）")
    p_init.add_argument("--round", metavar="rN", default=None,
                        help="审查轮次（如 r1）")
    p_init.add_argument("--doctype", metavar="T", default=None,
                        help="文档类型（如 journal/conference）")
    p_init.add_argument("--force", action="store_true",
                        help="已存在时强制覆盖重建")

    p_set = sub.add_parser("set", help="更新某阶段的 状态/产物/备注，并刷新「更新时间」")
    p_set.add_argument("--stage", metavar="STAGE", required=True, choices=STAGES,
                        help="阶段名: %s" % " | ".join(STAGES))
    p_set.add_argument("--status", metavar="STATUS", required=True, choices=STATUSES,
                        help="状态: %s" % " | ".join(STATUSES))
    p_set.add_argument("--artifact", metavar="PATH", default=None,
                        help="阶段产物路径（可选，未提供时保留原值）")
    p_set.add_argument("--note", metavar="TEXT", default=None,
                        help="备注（可选，未提供时保留原值）")

    p_next = sub.add_parser("next", help="更新「恢复点」（下一步动作/恢复命令/环境备忘）")
    # dest 不能叫 action：会与子命令名（dest="action"）在同一命名空间冲突
    p_next.add_argument("--action", metavar="TEXT", required=True,
                        dest="next_action", help="下一步动作描述")
    p_next.add_argument("--cmd", metavar="TEXT", default=None,
                        help="恢复命令（可选，未提供时保留原值）")
    p_next.add_argument("--env", metavar="TEXT", action="append", default=None,
                        help="环境备忘行，可多次提供（未提供时保留原有行组）")

    sub.add_parser("show", help="解析 RESUME.md 并输出 JSON 快照")
    sub.add_parser("check", help="校验 RESUME.md 完整性/合法性（0=通过，1=未通过）")

    args = parser.parse_args()
    handlers = {"init": do_init, "set": do_set, "next": do_next,
                "show": do_show, "check": do_check}
    result, code = handlers[args.action](args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(code)


if __name__ == "__main__":
    main()
