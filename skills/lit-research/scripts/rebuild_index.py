#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rebuild_index.py — 重建文献库索引

扫描文献库根目录下所有 NNN_XXX/NNN_card_*.md 卡片的「基本信息」九字段，
提取 arXiv ID 与 DOI，计算标题/作者归一化，输出 12 列 TSV：
  文献库索引.tsv（编号/作者/标题/年份/类型/出版源/DOI-URL/引用方式/arXiv/DOI提取/标题归一/作者归一）

每次新增/删除/重编号文献后重新运行本脚本即可维护索引。

用法：
  python rebuild_index.py --lib-path "d:/WS/t5/参考资料"

输出（stdout，JSON）：
  {"index_path": "...", "entries": N, "success": true}

退出码：0=成功；1=失败；2=参数错误。
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
HEADER = ["编号", "作者", "标题", "年份", "类型", "出版源",
          "DOI/URL", "引用方式", "arXiv", "DOI提取", "标题归一", "作者归一"]


def _field(txt, label):
    """从卡片文本提取 **label**：value 形式的字段值"""
    m = re.search(r"\*\*" + re.escape(label) + r"\*\*\s*[:：]\s*(.+?)\s*$", txt, re.M)
    return m.group(1).strip() if m else ""


def _norm(s):
    """归一化：去除非字母数字/非CJK字符并小写"""
    return re.sub(r"[^a-z0-9一-鿿]+", "", (s or "").lower())


def scan_cards(lib_path):
    """扫描全部卡片目录，返回按编号排序的行列表（12 列元组）"""
    rows = []
    dirs = sorted(g for g in glob.glob(os.path.join(lib_path, "[0-9]*"))
                  if os.path.isdir(g))
    for d in dirs:
        base = os.path.basename(d)
        num = base[:3]
        if not num.isdigit():
            continue
        cards = glob.glob(os.path.join(d, "%s_card_*.md" % num))
        if not cards:
            print("警告：目录 %s 下无卡片文件，跳过" % base, file=sys.stderr)
            continue
        try:
            with open(cards[0], encoding="utf-8") as f:
                txt = f.read()
        except OSError as e:
            print("警告：卡片读取失败 %s: %s" % (cards[0], e), file=sys.stderr)
            continue
        numf = re.sub(r"[\s\[\]]", "", _field(txt, "编号"))
        author = _field(txt, "作者")
        title = _field(txt, "标题")
        year = _field(txt, "年份")
        typ = _field(txt, "类型")
        src = _field(txt, "出版源")
        doi = _field(txt, "DOI/URL")
        cm = re.search(r"\*\*引用方式[^\*]*\*\*\s*[:：]\s*(.+?)\s*$", txt, re.M)
        cite = cm.group(1).strip() if cm else ""
        arxiv = ";".join(sorted(set(re.findall(
            r"(?:arxiv\.org/abs/|arXiv[:：]\s*)(\d{4}\.\d{4,5})", txt, re.I))))
        doifull = ";".join(sorted(set(re.findall(
            r"(?:doi[:：]\s*|doi\.org/)(10\.\d{4,9}/[^\s．.。；;]+)", txt, re.I))))
        n = numf if numf.isdigit() else num
        rows.append((n, author, title, year, typ, src, doi, cite,
                     arxiv, doifull, _norm(title), _norm(author)))
    rows.sort(key=lambda r: (int(r[0]) if r[0].isdigit() else 10 ** 6))
    return rows


def write_index(index_path, rows):
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("\t".join(HEADER) + "\n")
        for r in rows:
            f.write("\t".join("" if c is None else c for c in r) + "\n")


def main():
    parser = argparse.ArgumentParser(
        prog="rebuild_index.py",
        description="扫描卡片重建文献库索引（12 列 TSV），输出 JSON。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--lib-path", metavar="PATH", required=True,
                        help="文献库根目录（其下为 NNN_XXX/ 子目录）")
    args = parser.parse_args()

    lib_path = os.path.abspath(args.lib_path)
    if not os.path.isdir(lib_path):
        print("错误：文献库目录不存在: %s" % lib_path, file=sys.stderr)
        sys.exit(2)

    index_path = os.path.join(lib_path, INDEX_NAME)
    try:
        rows = scan_cards(lib_path)
        write_index(index_path, rows)
    except OSError as e:
        result = {"index_path": index_path, "entries": 0, "success": False}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("错误：索引写入失败: %s" % e, file=sys.stderr)
        sys.exit(1)

    result = {"index_path": index_path, "entries": len(rows), "success": True}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("已重建索引: %s（共 %d 条）" % (index_path, len(rows)), file=sys.stderr)


if __name__ == "__main__":
    main()
