#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""create_card.py — 从模板生成资料卡片

读取卡片模板（card-template.md），用 --data 指定的 JSON 内容替换占位符，
写出完整的资料卡片 markdown 文件。

占位符 -> 数据来源映射：
  {NUMBER}          <- --number（补齐 3 位）
  {AUTHOR}          <- basic_info.author
  {TITLE}           <- basic_info.title
  {YEAR}            <- basic_info.year
  {TYPE}            <- basic_info.type
  {SOURCE}          <- basic_info.source
  {DOI_URL}         <- basic_info.doi_url
  {CITATION}        <- basic_info.citation
  {VERIFICATION}    <- basic_info.verification
  {ABSTRACT}        <- abstract（字符串，或 {original, translation} 对象）
  {ABSTRACT_SOURCE} <- abstract_source
  {SUMMARY}         <- summary（字符串，或 {background, method, ...} 对象）
  {SUMMARY_SOURCE}  <- summary_source
  {SUMMARY_BASIS}   <- summary_basis
  {SRC_FILENAME}    <- download.src
  {SRC_FORMAT}      <- download.format   （默认 PDF）
  {SRC_SIZE}        <- download.size
  {SRC_PAGES}       <- download.pages
  {EXTRACT_FILENAME}<- download.extract
  {CITATION_STATUS} <- citation_status
  {OTHER}           <- other

用法：
  python create_card.py --number 104 --name Wang_PromptInjection_LLM \\
      --data _step5_card_104.json --template references/card-template.md \\
      --output "d:/WS/t5/参考资料/104_.../104_card_Wang_PromptInjection_LLM.md"

输出（stdout，JSON）：
  {"card_path": "...", "success": true, "missing_placeholders": [...]}

退出码：0=成功；1=失败；2=参数错误。
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


def _g(d, *keys, default=""):
    """从（可能为 None 的）字典中依次尝试取键，取不到返回 default"""
    if not isinstance(d, dict):
        return default
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


def _format_abstract(ab):
    """abstract 可为字符串或 {original, translation} 对象"""
    if isinstance(ab, str):
        return ab.strip()
    if isinstance(ab, dict):
        parts = []
        orig = _g(ab, "original", "text", default="")
        trans = _g(ab, "translation", "zh", default="")
        if orig:
            parts.append("**原文摘要（逐字）**：\n\n> \"%s\"" % orig.strip())
        if trans:
            parts.append("**中文翻译**：%s" % trans.strip())
        return "\n\n".join(parts) if parts else ""
    return ""


def _format_summary(sm):
    """summary 可为字符串或结构化对象（背景/方法/结论/关联）"""
    if isinstance(sm, str):
        return sm.strip()
    if isinstance(sm, dict):
        parts = []
        for label, key in (("背景", "background"), ("方法", "method"),
                           ("结论", "conclusion"), ("关联", "relevance")):
            val = _g(sm, key, default="")
            if val:
                parts.append(val.strip())
        # 也接受任意顺序的自由键
        if not parts:
            for k, v in sm.items():
                if isinstance(v, str) and v.strip():
                    parts.append(v.strip())
        return "\n\n".join(parts)
    return ""


def build_mapping(data, number):
    """根据 JSON 数据构建 占位符->值 映射"""
    bi = data.get("basic_info") if isinstance(data, dict) else {}
    dl = data.get("download") if isinstance(data, dict) else {}

    m = {
        "NUMBER": number,
        "AUTHOR": _g(bi, "author"),
        "TITLE": _g(bi, "title"),
        "YEAR": _g(bi, "year"),
        "TYPE": _g(bi, "type"),
        "SOURCE": _g(bi, "source"),
        "DOI_URL": _g(bi, "doi_url", "doi", "url"),
        "CITATION": _g(bi, "citation"),
        "VERIFICATION": _g(bi, "verification"),
        "ABSTRACT": _format_abstract(data.get("abstract") if isinstance(data, dict) else ""),
        "ABSTRACT_SOURCE": _g(data, "abstract_source", default=""),
        "SUMMARY": _format_summary(data.get("summary") if isinstance(data, dict) else ""),
        "SUMMARY_SOURCE": _g(data, "summary_source", default=""),
        "SUMMARY_BASIS": _g(data, "summary_basis", default=""),
        "SRC_FILENAME": _g(dl, "src", "src_filename"),
        "SRC_FORMAT": _g(dl, "format", default="PDF"),
        "SRC_SIZE": _g(dl, "size", default=""),
        "SRC_PAGES": _g(dl, "pages", default=""),
        "EXTRACT_FILENAME": _g(dl, "extract", "extract_filename"),
        "CITATION_STATUS": _g(data, "citation_status", default=""),
        "OTHER": _g(data, "other", default=""),
    }
    # 统一转字符串
    return {k: (v if isinstance(v, str) else str(v)) for k, v in m.items()}


def strip_comments(template):
    """去除模板中的 HTML 注释块（占位符说明不进入生成的卡片）"""
    return re.sub(r"<!--.*?-->\s*", "", template, flags=re.S)


def render(template, mapping):
    """替换 {PLACEHOLDER}；返回 (渲染文本, 未提供数据的占位符列表)"""
    template = strip_comments(template)
    missing = []

    def repl(mo):
        key = mo.group(1)
        if key in mapping and mapping[key] != "":
            return mapping[key]
        missing.append(key)
        # 保留占位符原样，便于人工发现缺漏
        return mo.group(0)

    rendered = re.sub(r"\{([A-Z_][A-Z0-9_]*)\}", repl, template)
    return rendered, sorted(set(missing))


def main():
    parser = argparse.ArgumentParser(
        prog="create_card.py",
        description="从模板生成资料卡片 markdown，输出 JSON。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--number", metavar="NNN", required=True,
                        help="文献编号（3 位数字）")
    parser.add_argument("--name", metavar="XXX", required=True,
                        help="描述性名称（用于文件命名；当 --output 缺省时拼接文件名）")
    parser.add_argument("--data", metavar="FILE", required=True,
                        help="卡片内容 JSON 文件")
    parser.add_argument("--template", metavar="FILE", required=True,
                        help="卡片模板 card-template.md 路径")
    parser.add_argument("--output", metavar="FILE", required=True,
                        help="输出卡片 .md 路径")
    args = parser.parse_args()

    num = args.number.strip()
    if not num.isdigit():
        print("错误：--number 必须是数字，收到 %r" % args.number, file=sys.stderr)
        sys.exit(2)
    num = "%03d" % int(num)

    if not os.path.isfile(args.data):
        print("错误：--data 文件不存在: %s" % args.data, file=sys.stderr)
        sys.exit(2)
    if not os.path.isfile(args.template):
        print("错误：--template 文件不存在: %s" % args.template, file=sys.stderr)
        sys.exit(2)

    try:
        with open(args.data, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        print("错误：--data JSON 解析失败: %s" % e, file=sys.stderr)
        sys.exit(1)
    if not isinstance(data, dict):
        print("错误：--data 内容必须是 JSON 对象", file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.template, encoding="utf-8") as f:
            template = f.read()
    except OSError as e:
        print("错误：模板读取失败: %s" % e, file=sys.stderr)
        sys.exit(1)

    mapping = build_mapping(data, num)
    rendered, missing = render(template, mapping)

    out_path = os.path.abspath(args.output)
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(rendered)
    except OSError as e:
        result = {"card_path": out_path, "success": False, "missing_placeholders": missing}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("错误：卡片写入失败: %s" % e, file=sys.stderr)
        sys.exit(1)

    result = {
        "card_path": out_path,
        "success": True,
        "missing_placeholders": missing,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if missing:
        print("警告：以下占位符无数据，已在卡片中保留原样待补：%s"
              % ", ".join(missing), file=sys.stderr)


if __name__ == "__main__":
    main()
