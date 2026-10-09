#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""setup_env.py — lit-research 环境初始化脚本

功能：
  1. 检查 Python 依赖（PyMuPDF/fitz, requests）是否可用
  2. 确认文献库根目录存在、可读、可写
  3. 扫描库中 NNN_XXX/ 目录名，得出当前最大编号（下次新增从 max_number+1 起号）
  4. 确认卡片模板文件存在
  5. 以 JSON 输出结果到 stdout，供步骤间传递

用法：
  python setup_env.py --init --lib-path "d:/WS/t5/参考资料" [--template PATH]

输出（stdout，JSON）：
  {
    "max_number": 388,
    "lib_path": "d:/WS/t5/参考资料",
    "template_path": ".../references/card-template.md",
    "dependencies_ok": true,
    "missing_deps": []
  }

退出码：0=成功；1=初始化检查未通过（详见 JSON 与 stderr）；2=参数错误。
"""
import argparse
import io
import json
import os
import re
import sys
import tempfile

# 修复 Windows 下 GBK 编码问题，强制 UTF-8 输出
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 卡片模板默认路径：本脚本所在技能目录下的 references/card-template.md
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_TEMPLATE = os.path.join(SKILL_DIR, "references", "card-template.md")

REQUIRED_DEPS = [
    ("fitz", "PyMuPDF"),      # import 名 -> pip 安装名
    ("requests", "requests"),
]


def check_dependencies():
    """检查依赖模块是否可导入，返回缺失的 pip 包名列表"""
    missing = []
    for import_name, pip_name in REQUIRED_DEPS:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_name)
    return missing


def check_lib_path(lib_path):
    """检查文献库目录：存在 / 是目录 / 可读 / 可写。返回问题列表（空=通过）"""
    problems = []
    if not os.path.exists(lib_path):
        problems.append("文献库目录不存在: %s" % lib_path)
        return problems
    if not os.path.isdir(lib_path):
        problems.append("文献库路径不是目录: %s" % lib_path)
        return problems
    if not os.access(lib_path, os.R_OK):
        problems.append("文献库目录不可读: %s" % lib_path)
    if not os.access(lib_path, os.W_OK):
        problems.append("文献库目录不可写: %s" % lib_path)
    else:
        # 实际写入测试（os.access 在某些挂载/权限场景下不可靠）
        try:
            fd, probe = tempfile.mkstemp(prefix=".lit_research_probe_", dir=lib_path)
            os.close(fd)
            os.remove(probe)
        except OSError as e:
            problems.append("文献库目录写入测试失败: %s" % e)
    return problems


def scan_max_number(lib_path):
    """扫描 NNN_XXX/ 目录名，返回当前最大编号（无匹配则为 0）"""
    max_n = 0
    try:
        entries = os.listdir(lib_path)
    except OSError:
        return 0
    for name in entries:
        full = os.path.join(lib_path, name)
        if not os.path.isdir(full):
            continue
        m = re.match(r"^(\d{3})[_\-]", name)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return max_n


def main():
    parser = argparse.ArgumentParser(
        prog="setup_env.py",
        description="lit-research 环境初始化：检查依赖、文献库目录、卡片模板，扫描最大编号，输出 JSON。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--init", action="store_true",
                        help="执行初始化检查（必须显式给出）")
    parser.add_argument("--lib-path", metavar="PATH", default=None,
                        help="文献库根目录（其下为 NNN_XXX/ 子目录与 文献库索引.tsv）")
    parser.add_argument("--template", metavar="PATH", default=DEFAULT_TEMPLATE,
                        help="卡片模板路径 (card-template.md)")
    args = parser.parse_args()

    if not args.init:
        parser.print_help(sys.stderr)
        print("错误：需要 --init 才会执行初始化。", file=sys.stderr)
        sys.exit(2)

    missing_deps = check_dependencies()
    result = {
        "max_number": 0,
        "lib_path": args.lib_path,
        "template_path": args.template,
        "dependencies_ok": not missing_deps,
        "missing_deps": missing_deps,
        "lib_problems": [],
        "template_ok": False,
        "success": False,
    }

    # 文献库目录检查
    if args.lib_path:
        result["lib_path"] = os.path.abspath(args.lib_path)
        result["lib_problems"] = check_lib_path(args.lib_path)
        if not result["lib_problems"]:
            result["max_number"] = scan_max_number(args.lib_path)
    else:
        result["lib_problems"].append("未指定 --lib-path")

    # 模板检查
    if args.template and os.path.isfile(args.template):
        result["template_ok"] = True
        result["template_path"] = os.path.abspath(args.template)
    else:
        result["template_ok"] = False
        result["template_path"] = args.template

    result["success"] = (
        result["dependencies_ok"]
        and not result["lib_problems"]
        and result["template_ok"]
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))

    if not result["success"]:
        if missing_deps:
            print("提示：安装缺失依赖 -> pip install %s" % " ".join(missing_deps),
                  file=sys.stderr)
        for p in result["lib_problems"]:
            print("问题：%s" % p, file=sys.stderr)
        if not result["template_ok"]:
            print("问题：卡片模板不存在: %s" % args.template, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
