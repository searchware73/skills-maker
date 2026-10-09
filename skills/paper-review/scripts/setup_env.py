#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""setup_env.py — paper-review 环境初始化脚本

功能：
  1. 校验论文文件存在、可读、可解码（UTF-8 优先，GBK 兜底）
  2. 若指定 --section X.Y，解析 Markdown 标题定位该小节起止行号
     （1-based，含头含尾；小节范围覆盖其下所有子小节，如 1.1 含 1.1.1/1.1.2）
  3. 在论文文件所在目录创建 .review/ 输出目录
  4. 初始化三个日志文件为空（deai_log.md / revision_log.md / convergence.md）
  5. 以 JSON 输出结果到 stdout，供步骤间传递

用法：
  python setup_env.py --file 论文.md [--section 1.1] [--rounds 3]

输出（stdout，JSON）：
  {
    "file_path": "d:/WS/t5/论文.md",
    "section": "1.1",
    "section_range": [20, 87],
    "review_dir": "d:/WS/t5/.review/",
    "rounds_max": 3,
    "total_lines": 500,
    "section_title": "## 1.1 创新建模范式",
    "success": true
  }
  （未指定 --section 时 section/section_range 为 null；失败时附 problems 列表）

退出码：0=成功；1=初始化检查未通过（详见 JSON 与 stderr）；2=参数错误。
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

LOG_FILES = ["deai_log.md", "revision_log.md", "convergence.md"]

# 带编号标题：## 1.1 xxx / ### 1.1.1 xxx / # 1 xxx
NUMBERED_HEADING_RE = re.compile(r"^(#{1,6})\s+(\d+(?:\.\d+)*)(?=[^\d.]|$)")
# 任意标题（含无编号标题，如 # 参考文献）
ANY_HEADING_RE = re.compile(r"^(#{1,6})\s+")


def to_posix(path):
    """Windows 反斜杠路径转正斜杠，便于 JSON 传递"""
    return path.replace("\\", "/")


def read_paper_lines(path):
    """读取论文文件。返回 (行列表, 错误信息)。UTF-8（含BOM）优先，GBK 兜底。"""
    for enc in ("utf-8-sig", "gbk"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read().splitlines(), None
        except UnicodeDecodeError:
            continue
        except OSError as e:
            return None, "文件无法读取: %s" % e
    return None, "文件既非 UTF-8 也非 GBK 编码，请先转为 UTF-8: %s" % path


def in_section(num, section):
    """标题编号 num 是否属于小节 section（本身或其子小节）"""
    return num == section or num.startswith(section + ".")


def find_section_range(lines, section):
    """定位小节起止行（1-based，含头含尾）。

    返回 (range_list_or_None, 标题行文本, 匹配方式, 错误信息)。
    结束边界：第一个「编号不属于本小节」的编号标题，
    或第一个「层级不深于起始标题」的无编号标题（如 # 参考文献），或文件末尾。
    """
    start_idx = None
    start_level = None
    match_kind = "exact"
    for i, line in enumerate(lines):
        m = NUMBERED_HEADING_RE.match(line)
        if m and m.group(2) == section:
            start_idx, start_level = i, len(m.group(1))
            break
    if start_idx is None:
        # 宽松匹配：无精确编号标题时，取其下第一个子小节标题为起点
        for i, line in enumerate(lines):
            m = NUMBERED_HEADING_RE.match(line)
            if m and in_section(m.group(2), section):
                start_idx, start_level = i, len(m.group(1))
                match_kind = "subsection"
                break
    if start_idx is None:
        return None, None, None, "未找到编号为 %s 的章节标题" % section

    end_idx = len(lines)  # 排他边界（0-based），即最后一行的 1-based 行号
    for j in range(start_idx + 1, len(lines)):
        line = lines[j]
        m = NUMBERED_HEADING_RE.match(line)
        if m:
            if not in_section(m.group(2), section):
                end_idx = j
                break
        else:
            m2 = ANY_HEADING_RE.match(line)
            if m2 and len(m2.group(1)) <= start_level:
                end_idx = j
                break
    return [start_idx + 1, end_idx], lines[start_idx].strip(), match_kind, None


def main():
    parser = argparse.ArgumentParser(
        prog="setup_env.py",
        description="paper-review 环境初始化：校验论文文件、定位章节行号范围、"
                    "创建 .review/ 目录并初始化日志文件，输出 JSON。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--file", metavar="PATH", required=True,
                        help="待审查论文文件路径（Markdown）")
    parser.add_argument("--section", metavar="X.Y", default=None,
                        help="限定审查范围到某小节（如 1.1，自动覆盖其子小节）")
    parser.add_argument("--rounds", metavar="N", type=int, default=3,
                        help="收敛循环最大轮数")
    args = parser.parse_args()

    if args.rounds < 1:
        print("错误：--rounds 必须 >= 1", file=sys.stderr)
        sys.exit(2)

    section = args.section.strip().lstrip("§").rstrip(".") if args.section else None
    result = {
        "file_path": None,
        "section": section,
        "section_range": None,
        "review_dir": None,
        "rounds_max": args.rounds,
        "success": False,
    }
    problems = []

    path = args.file
    if not os.path.exists(path):
        problems.append("论文文件不存在: %s" % path)
    elif not os.path.isfile(path):
        problems.append("论文路径不是文件: %s" % path)
    else:
        result["file_path"] = to_posix(os.path.abspath(path))
        lines, err = read_paper_lines(path)
        if err:
            problems.append(err)
        else:
            result["total_lines"] = len(lines)
            if section:
                rng, title, kind, serr = find_section_range(lines, section)
                if serr:
                    problems.append(serr)
                else:
                    result["section_range"] = rng
                    result["section_title"] = title
                    result["section_match"] = kind
                    if kind == "subsection":
                        print("警告：未找到编号 %s 的标题，已从其第一个子小节开始定位" % section,
                              file=sys.stderr)

    if not problems:
        review_dir = os.path.join(os.path.dirname(os.path.abspath(path)), ".review")
        try:
            os.makedirs(review_dir, exist_ok=True)
            for name in LOG_FILES:
                with open(os.path.join(review_dir, name), "w",
                          encoding="utf-8", newline="\n") as f:
                    f.write("")  # 初始化为空文件
            result["review_dir"] = to_posix(review_dir) + "/"
        except OSError as e:
            problems.append("创建 .review/ 目录或初始化日志失败: %s" % e)

    result["success"] = not problems
    if problems:
        result["problems"] = problems
    print(json.dumps(result, ensure_ascii=False, indent=2))
    for p in problems:
        print("问题：%s" % p, file=sys.stderr)
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
