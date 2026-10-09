#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""共享卡片验证模块

供 lit-research 和 paper-review 技能共用的卡片格式验证逻辑。

用法（作为模块导入）:
    from card_validator import validate_card, validate_directory

用法（命令行）:
    python card_validator.py --card PATH [--number NNN]
"""
import argparse
import json
import os
import re
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 9个基本信息字段（顺序固定）
REQUIRED_FIELDS = [
    "编号", "作者", "标题", "年份", "类型",
    "出版源", "DOI/URL", "引用方式", "验证状态"
]

# 6个卡片 section
REQUIRED_SECTIONS = [
    "基本信息", "摘要", "内容概要", "资料下载", "引用情况", "其他"
]

# 文献类型标识
VALID_TYPES = ["[J]", "[M]", "[C]", "[R]", "[D]", "[S]", "[N]", "[EB/OL]"]


def _extract_field(text: str, label: str) -> str:
    """从卡片 markdown 中提取字段值"""
    m = re.search(
        r"\*\*" + re.escape(label) + r"[^\*]*\*\*\s*[:：]\s*(.+?)\s*$",
        text, re.M
    )
    return m.group(1).strip() if m else ""


def _extract_section(text: str, heading: str) -> str:
    """提取指定 section 的内容"""
    pattern = r"##\s+" + re.escape(heading) + r"\s*\n(.*?)(?=\n##\s|\Z)"
    m = re.search(pattern, text, re.S)
    return m.group(1).strip() if m else ""


def validate_card(card_path: str, expected_number: str = None) -> dict:
    """验证单个卡片文件

    Args:
        card_path: 卡片文件路径
        expected_number: 期望的编号（3位数字字符串），None则不检查

    Returns:
        dict with validation results per field
    """
    results = {
        "file_exists": False,
        "sections_present": [],
        "sections_missing": [],
        "fields_present": [],
        "fields_missing": [],
        "number_match": None,
        "type_valid": None,
        "summary_chars": 0,
        "summary_in_range": False,
        "abstract_has_source": False,
        "errors": []
    }

    if not os.path.isfile(card_path):
        results["errors"].append(f"卡片文件不存在: {card_path}")
        return results

    results["file_exists"] = True
    text = open(card_path, encoding="utf-8").read()

    # Check sections
    for sec in REQUIRED_SECTIONS:
        if re.search(r"##\s+" + re.escape(sec), text):
            results["sections_present"].append(sec)
        else:
            results["sections_missing"].append(sec)
            results["errors"].append(f"缺少 section: {sec}")

    # Check basic info fields
    basic_info = _extract_section(text, "基本信息")
    for field in REQUIRED_FIELDS:
        val = _extract_field(basic_info, field)
        if val:
            results["fields_present"].append(field)
        else:
            results["fields_missing"].append(field)
            results["errors"].append(f"缺少字段: {field}")

    # Check number consistency
    num_val = _extract_field(basic_info, "编号")
    num_clean = re.sub(r"[\s\[\]]", "", num_val)
    if expected_number:
        results["number_match"] = (num_clean == expected_number)
        if not results["number_match"]:
            results["errors"].append(
                f"编号不匹配: 卡片={num_clean}, 期望={expected_number}"
            )

    # Check type validity
    type_val = _extract_field(basic_info, "类型")
    results["type_valid"] = any(t in type_val for t in VALID_TYPES)
    if not results["type_valid"] and type_val:
        results["errors"].append(f"类型标识无效: {type_val}")

    # Check summary length
    summary = _extract_section(text, "内容概要")
    # Remove source/basis annotations from char count
    summary_clean = re.sub(r"(来源|依据)[:：].*$", "", summary, flags=re.M).strip()
    results["summary_chars"] = len(summary_clean)
    results["summary_in_range"] = 800 <= results["summary_chars"] <= 1000
    if summary_clean and not results["summary_in_range"]:
        results["errors"].append(
            f"内容概要字数 {results['summary_chars']} 不在 800-1000 范围"
        )

    # Check abstract has source annotation
    abstract = _extract_section(text, "摘要")
    results["abstract_has_source"] = bool(
        re.search(r"来源[:：]", abstract)
    )

    return results


def validate_directory(dir_path: str) -> dict:
    """验证文献子目录的完整性

    Args:
        dir_path: NNN_XXX/ 目录路径

    Returns:
        dict with directory validation results
    """
    results = {
        "dir_exists": False,
        "dir_name_valid": False,
        "number": None,
        "card_file": None,
        "extract_file": None,
        "src_files": [],
        "number_consistent": False,
        "errors": []
    }

    if not os.path.isdir(dir_path):
        results["errors"].append(f"目录不存在: {dir_path}")
        return results

    results["dir_exists"] = True
    dirname = os.path.basename(dir_path)

    # Validate directory name format NNN_XXX
    m = re.match(r"^(\d{3})_(.+)$", dirname)
    if not m:
        results["errors"].append(f"目录名格式错误: {dirname} (应为 NNN_XXX)")
        return results

    results["dir_name_valid"] = True
    num = m.group(1)
    results["number"] = num

    # Find files
    for f in os.listdir(dir_path):
        fpath = os.path.join(dir_path, f)
        if not os.path.isfile(fpath):
            continue
        if f.startswith(f"{num}_card_") and f.endswith(".md"):
            results["card_file"] = f
        elif f.startswith(f"{num}_extract_") and f.endswith(".txt"):
            results["extract_file"] = f
        elif f.startswith(f"{num}_src_"):
            results["src_files"].append(f)

    # Check required files
    if not results["card_file"]:
        results["errors"].append(f"缺少卡片文件 {num}_card_*.md")
    if not results["extract_file"]:
        results["errors"].append(f"缺少提取文件 {num}_extract_*.txt")
    if not results["src_files"]:
        results["errors"].append(f"缺少源文件 {num}_src_*")

    # Number consistency: all files should start with NNN_
    results["number_consistent"] = all(
        f.startswith(f"{num}_")
        for f in os.listdir(dir_path)
        if os.path.isfile(os.path.join(dir_path, f))
    )
    if not results["number_consistent"]:
        results["errors"].append("文件名前缀与目录编号不一致")

    return results


def main():
    parser = argparse.ArgumentParser(description="卡片格式验证工具")
    parser.add_argument("--card", help="卡片文件路径")
    parser.add_argument("--dir", help="文献子目录路径")
    parser.add_argument("--number", help="期望编号（3位数字）")
    parser.add_argument("--json", action="store_true", help="输出JSON格式")
    args = parser.parse_args()

    if not args.card and not args.dir:
        parser.print_help()
        sys.exit(1)

    results = {}
    if args.card:
        results["card"] = validate_card(args.card, args.number)
    if args.dir:
        results["directory"] = validate_directory(args.dir)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for section, data in results.items():
            print(f"\n=== {section} ===")
            if data.get("errors"):
                for e in data["errors"]:
                    print(f"  ✗ {e}")
            else:
                print("  ✓ 全部通过")
            # Print details
            for k, v in data.items():
                if k != "errors":
                    print(f"  {k}: {v}")

    # Exit code: 0 if no errors, 1 otherwise
    has_errors = any(
        d.get("errors") for d in results.values()
    )
    sys.exit(1 if has_errors else 0)


if __name__ == "__main__":
    main()
