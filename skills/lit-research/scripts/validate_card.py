#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_card.py — 资料卡片 V1–V6 验证

对指定编号的卡片执行 6 项验证：
  V1 卡片文件存在：NNN_XXX/NNN_card_XXX.md
  V2 查重已执行：查重输出文件存在，或给出 --skip-dedup
  V3 9 个基本信息字段齐全且顺序正确：
     编号/作者/标题/年份/类型/出版源/DOI-URL/引用方式/验证状态
  V4 内容概要 800–1000 字，含结构标记（背景/方法/结论/关联）
  V5 去AI化技能已调用：--extract-log 中含 stop-slop / academic-humanizer / humanize-writing
  V6 入库集成：目录命名 NNN_XXX/ 正确、文件名前缀与编号一致、索引含该条目

用法：
  python validate_card.py --number 104 --lib-path "d:/WS/t5/参考资料" \\
      --extract-log _step6_deai_log.txt [--skip-dedup]

输出（stdout，JSON）：
  {"v1": true, ..., "v6": true, "all_pass": true,
   "details": {"v1": "...", ..., "v6": "..."}}

退出码：0=全部通过；1=存在未通过项；2=参数错误。
"""
import argparse
import glob
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

INDEX_NAME = "文献库索引.tsv"
# V3 九字段（顺序即正确顺序）；匹配时对标签做前缀匹配（如「引用方式（GB/T 7714）」）
V3_FIELDS = ["编号", "作者", "标题", "年份", "类型", "出版源",
             "DOI/URL", "引用方式", "验证状态"]
V4_MIN, V4_MAX = 800, 1000
V4_MARKERS = ["背景", "方法", "结论", "关联"]
V5_SKILLS = ["stop-slop", "academic-humanizer", "humanize-writing"]


def find_lib_dir(lib_path, num):
    """定位 NNN_XXX/ 目录，返回 (目录路径或None, 是否命名规范)"""
    pattern = os.path.join(lib_path, "%s_*" % num)
    hits = [d for d in glob.glob(pattern) if os.path.isdir(d)]
    if not hits:
        # 也接受 NNN-XXX / NNNXXX 命名，但视为不规范
        hits = [d for d in glob.glob(os.path.join(lib_path, "%s*" % num))
                if os.path.isdir(d)]
        if hits:
            return hits[0], False
        return None, False
    d = hits[0]
    ok = re.match(r"^\d{3}_.+$", os.path.basename(d)) is not None
    return d, ok


def v1_card_exists(lib_dir, num):
    if not lib_dir:
        return False, None, "未找到编号 %s 的文献目录" % num
    cards = glob.glob(os.path.join(lib_dir, "%s_card_*.md" % num))
    if not cards:
        return False, None, "目录 %s 下无 %s_card_*.md" % (os.path.basename(lib_dir), num)
    return True, cards[0], "卡片文件存在: %s" % os.path.basename(cards[0])


def v2_dedup_done(num, skip_dedup, search_dirs):
    if skip_dedup:
        return True, "查重跳过（--skip-dedup，需用户明确授权）"
    patterns = ["_step3_lookup*.json", "_dedup_%s.json" % num,
                "_lookup_%s.json" % num, "*lookup*.json"]
    for d in search_dirs:
        if not d:
            continue
        for pat in patterns:
            hits = glob.glob(os.path.join(d, pat))
            for h in hits:
                try:
                    with open(h, encoding="utf-8") as f:
                        content = f.read()
                except OSError:
                    continue
                # 文件中应出现该编号或候选标题痕迹（宽松：出现编号即可）
                if num in content or num.lstrip("0") in content:
                    return True, "查重输出存在: %s" % h
    return False, "未找到含编号 %s 的查重输出文件（_step3_lookup*.json 等），且未给 --skip-dedup" % num


def v3_basic_info(card_text, num):
    """9 字段齐全、顺序正确、编号一致、值非空"""
    m = re.search(r"##\s*基本信息(.*?)(?=\n##\s|\Z)", card_text, re.S)
    if not m:
        return False, "缺少「## 基本信息」小节"
    section = m.group(1)
    # 按出现顺序抽取所有加粗标签
    labels = re.findall(r"\*\*([^*]+?)\*\*\s*[:：]\s*(.*)$", section, re.M)
    seen = []
    problems = []
    for raw_label, value in labels:
        label = raw_label.strip()
        seen.append((label, value.strip()))
    # 顺序与齐全性检查：V3_FIELDS 依次前缀匹配
    idx = 0
    matched_order = []
    for label, value in seen:
        if idx < len(V3_FIELDS) and label.startswith(V3_FIELDS[idx].split("/")[0]):
            matched_order.append(V3_FIELDS[idx])
            if not value:
                problems.append("字段「%s」值为空" % V3_FIELDS[idx])
            idx += 1
    missing = [f for f in V3_FIELDS if f not in matched_order]
    if missing:
        problems.append("缺失字段: %s" % "/".join(missing))
    if matched_order != [f for f in V3_FIELDS if f in matched_order]:
        problems.append("字段顺序不正确（应为 %s）" % "/".join(V3_FIELDS))
    # 编号一致性
    num_m = re.search(r"\*\*编号\*\*\s*[:：]\s*\[?(\d+)\]?", section)
    if num_m and int(num_m.group(1)) != int(num):
        problems.append("卡片编号 [%s] 与目录编号 [%s] 不一致"
                        % (num_m.group(1), num))
    if problems:
        return False, "；".join(problems)
    return True, "9 字段齐全且顺序正确"


def v4_summary(card_text):
    m = re.search(r"##\s*内容概要(.*?)(?=\n##\s|\Z)", card_text, re.S)
    if not m:
        return False, "缺少「## 内容概要」小节"
    body = m.group(1)
    # 去掉「来源/依据」附注行后统计正文字数（去除全部空白字符）
    lines = [l for l in body.splitlines()
             if not re.match(r"^\s*(来源|依据)\s*[:：]", l)]
    text = re.sub(r"\s+", "", "\n".join(lines))
    n = len(text)
    problems = []
    if not (V4_MIN <= n <= V4_MAX):
        problems.append("字数 %d 不在 %d–%d 范围" % (n, V4_MIN, V4_MAX))
    missing_markers = [k for k in V4_MARKERS if k not in body]
    if missing_markers:
        problems.append("缺少结构标记: %s" % "/".join(missing_markers))
    if problems:
        return False, "；".join(problems)
    return True, "字数 %d，结构标记齐全（%s）" % (n, "/".join(V4_MARKERS))


def v5_deai_log(log_path):
    if not log_path:
        return False, "未提供 --extract-log（去AI技能调用日志）"
    if not os.path.isfile(log_path):
        return False, "去AI日志文件不存在: %s" % log_path
    try:
        with open(log_path, encoding="utf-8") as f:
            content = f.read().lower()
    except OSError as e:
        return False, "去AI日志读取失败: %s" % e
    missing = [s for s in V5_SKILLS if s.lower() not in content]
    if missing:
        return False, "日志中未见调用记录: %s" % ", ".join(missing)
    return True, "三个去AI技能（%s）均有调用记录" % ", ".join(V5_SKILLS)


def v6_integration(lib_dir, dir_name_ok, num, lib_path):
    problems = []
    if not lib_dir:
        return False, "文献目录不存在，无法验证集成"
    if not dir_name_ok:
        problems.append("目录命名不符合 NNN_XXX/ 规范: %s"
                        % os.path.basename(lib_dir))
    # 目录内所有产物文件名前缀应为 NNN_
    for fn in os.listdir(lib_dir):
        if fn.startswith("."):
            continue
        if not fn.startswith("%s_" % num):
            problems.append("文件名前缀与编号不符: %s" % fn)
    # 三件套齐全
    has_card = bool(glob.glob(os.path.join(lib_dir, "%s_card_*.md" % num)))
    has_extract = bool(glob.glob(os.path.join(lib_dir, "%s_extract_*" % num)))
    has_src = bool(glob.glob(os.path.join(lib_dir, "%s_src_*" % num)))
    if not (has_card and has_extract and has_src):
        lack = [n for n, ok in (("card", has_card), ("extract", has_extract),
                                ("src", has_src)) if not ok]
        problems.append("三件套不齐，缺: %s" % "/".join(lack))
    # 索引含条目
    index_path = os.path.join(lib_path, INDEX_NAME)
    if not os.path.isfile(index_path):
        problems.append("索引不存在: %s（需先运行 rebuild_index.py）" % index_path)
    else:
        found = False
        with open(index_path, encoding="utf-8") as f:
            for line in f:
                if line.split("\t", 1)[0].strip() == str(int(num)):
                    found = True
                    break
        if not found:
            problems.append("索引中无编号 %d 条目（需运行 rebuild_index.py）" % int(num))
    if problems:
        return False, "；".join(problems)
    return True, "目录/文件名规范、三件套齐全、索引含条目"


def main():
    parser = argparse.ArgumentParser(
        prog="validate_card.py",
        description="资料卡片 V1–V6 验证，输出 JSON。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--number", metavar="NNN", required=True,
                        help="文献编号（3 位数字）")
    parser.add_argument("--lib-path", metavar="PATH", required=True,
                        help="文献库根目录")
    parser.add_argument("--extract-log", metavar="FILE", default=None,
                        help="去AI技能调用日志文件路径（V5 用）")
    parser.add_argument("--skip-dedup", action="store_true",
                        help="跳过 V2 查重文件检查（需用户明确授权）")
    args = parser.parse_args()

    num = args.number.strip()
    if not num.isdigit():
        print("错误：--number 必须是数字，收到 %r" % args.number, file=sys.stderr)
        sys.exit(2)
    num = "%03d" % int(num)
    if not os.path.isdir(args.lib_path):
        print("错误：文献库目录不存在: %s" % args.lib_path, file=sys.stderr)
        sys.exit(2)

    lib_dir, dir_name_ok = find_lib_dir(args.lib_path, num)

    # V1
    v1_ok, card_path, v1_detail = v1_card_exists(lib_dir, num)
    card_text = ""
    if v1_ok:
        try:
            with open(card_path, encoding="utf-8") as f:
                card_text = f.read()
        except OSError as e:
            v1_ok, v1_detail = False, "卡片读取失败: %s" % e

    # V2
    search_dirs = [os.getcwd(), args.lib_path, lib_dir]
    v2_ok, v2_detail = v2_dedup_done(num, args.skip_dedup, search_dirs)

    # V3 / V4
    if card_text:
        v3_ok, v3_detail = v3_basic_info(card_text, num)
        v4_ok, v4_detail = v4_summary(card_text)
    else:
        v3_ok, v3_detail = False, "卡片不存在，无法验证"
        v4_ok, v4_detail = False, "卡片不存在，无法验证"

    # V5
    v5_ok, v5_detail = v5_deai_log(args.extract_log)

    # V6
    v6_ok, v6_detail = v6_integration(lib_dir, dir_name_ok, num, args.lib_path)

    result = {
        "v1": v1_ok, "v2": v2_ok, "v3": v3_ok,
        "v4": v4_ok, "v5": v5_ok, "v6": v6_ok,
        "all_pass": all([v1_ok, v2_ok, v3_ok, v4_ok, v5_ok, v6_ok]),
        "details": {
            "v1": v1_detail, "v2": v2_detail, "v3": v3_detail,
            "v4": v4_detail, "v5": v5_detail, "v6": v6_detail,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["all_pass"] else 1)


if __name__ == "__main__":
    main()
