#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lookup_lib.py — 文献库查重（4 信号）

对候选文献清单与本地「文献库索引.tsv」做 4 信号查重：
  1. 标题归一化子串双向匹配（title）
  2. DOI 精确匹配（doi）
  3. arXiv ID 精确匹配（arxiv）
  4. 第一作者 + 标题交叉匹配（author+title）

判定规则：
  - 命中信号 1/2/3 任一 -> duplicate
  - 仅命中信号 4        -> uncertain（需人工复核）
  - 均未命中           -> new

用法：
  python lookup_lib.py --check candidates.json --lib-path "d:/WS/t5/参考资料" > _step3_lookup.json

  candidates.json 为 JSON 数组：
    [{"title": "...", "doi": "...", "arxiv": "...", "authors": "..."}]
    （各字段均可省略；至少应有 title）

输出（stdout，JSON）：
  {"new": [...], "duplicate": [...], "uncertain": [...]}
  每项形如：{"candidate": {原始候选}, "match_info": {"signals": [...], "matches": [库内条目...]}}

退出码：0=成功；1=索引缺失或输入错误；2=参数错误。
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

INDEX_NAME = "文献库索引.tsv"
# 索引列：0编号 1作者 2标题 3年份 4类型 5出版源 6DOI/URL 7引用方式 8arXiv 9DOI提取 10标题归一 11作者归一
COL_NUM, COL_AUTHOR, COL_TITLE = 0, 1, 2
COL_URL, COL_CITE, COL_ARXIV, COL_DOIEXT = 6, 7, 8, 9
COL_TITLE_NORM, COL_AUTHOR_NORM = 10, 11


def _norm(s):
    """归一化：去除非字母数字/非CJK字符并小写"""
    if not s:
        return ""
    return re.sub(r"[^a-z0-9一-鿿]+", "", s.lower())


def _norm_doi(s):
    """DOI 归一化：去 URL 前缀与空白，小写"""
    if not s:
        return ""
    s = s.strip().lower()
    s = re.sub(r"^https?://(dx\.)?doi\.org/", "", s)
    s = re.sub(r"^doi:\s*", "", s)
    return s.rstrip(".,;")


def _norm_arxiv(s):
    """arXiv ID 归一化：仅保留 NNNN.NNNNN 形式（含旧式带版本号的也剥离版本）"""
    if not s:
        return ""
    m = re.search(r"(\d{4}\.\d{4,5})", s)
    if m:
        return m.group(1)
    m = re.search(r"([a-z\-]+/\d{7})", s, re.I)
    return m.group(1).lower() if m else s.strip().lower()


def _title_tokens(s):
    """提取标题中长度>=4的英数词（用于作者+标题交叉信号）"""
    return set(w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(w) >= 4)


def _first_author_keys(authors):
    """从作者串提取第一作者的候选归一化键（首词与末词，兼顾 名 姓 / 姓, 名 两种写法）"""
    if not authors:
        return []
    first = re.split(r"[,;，、;]|\sand\s", authors.strip())[0].strip()
    if not first:
        return []
    keys = {_norm(first)}                       # 中文全名 / 单词作者
    toks = first.split()
    if len(toks) > 1:
        keys.add(_norm(toks[0]))                # 姓在前（GB/T 7714: WANG P）
        keys.add(_norm(toks[-1]))               # 姓在后（Peiran Wang）
    return [k for k in keys if len(k) >= 2]


def load_index(lib_path):
    index_path = os.path.join(lib_path, INDEX_NAME)
    if not os.path.isfile(index_path):
        print("错误：索引文件不存在: %s\n请先运行 rebuild_index.py --lib-path %s 生成。"
              % (index_path, lib_path), file=sys.stderr)
        sys.exit(1)
    rows = []
    with open(index_path, encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f if l.strip()]
    for line in lines[1:]:  # 跳过表头
        cols = line.split("\t")
        while len(cols) < 12:
            cols.append("")
        rows.append(cols)
    return rows


def check_candidate(cand, rows):
    """对单个候选执行 4 信号查重，返回 (category, signals, matches)"""
    title = cand.get("title", "") or ""
    nt = _norm(title)
    nd = _norm_doi(cand.get("doi", ""))
    na = _norm_arxiv(cand.get("arxiv", ""))
    akeys = _first_author_keys(cand.get("authors", ""))
    ttoks = _title_tokens(title)

    signals = set()
    matches = {}   # 编号 -> {"number","author","title","year","signals":[...]}

    def _hit(row, sig):
        signals.add(sig)
        num = row[COL_NUM]
        if num not in matches:
            matches[num] = {
                "number": num,
                "author": row[COL_AUTHOR],
                "title": row[COL_TITLE],
                "year": row[3],
                "signals": [],
            }
        if sig not in matches[num]["signals"]:
            matches[num]["signals"].append(sig)

    for row in rows:
        # 信号 2：DOI 精确匹配（对 索引DOI提取列 + DOI/URL列 + 引用方式列）
        if nd:
            hay = (row[COL_DOIEXT] + " " + row[COL_URL] + " " + row[COL_CITE]).lower()
            if nd in hay:
                _hit(row, "doi")
        # 信号 3：arXiv ID 精确匹配
        if na and na in row[COL_ARXIV].lower():
            _hit(row, "arxiv")
        # 信号 1：标题归一化子串双向匹配
        if nt and row[COL_TITLE_NORM] and (
                nt in row[COL_TITLE_NORM] or row[COL_TITLE_NORM] in nt):
            _hit(row, "title")
        # 信号 4：第一作者 + 标题交叉匹配（作者命中 且 标题词重合率 >= 0.5）
        if akeys and ttoks and "title" not in signals:
            lib_author_norm = row[COL_AUTHOR_NORM] or _norm(row[COL_AUTHOR])
            author_hit = any(k in lib_author_norm for k in akeys)
            if author_hit:
                lib_toks = _title_tokens(row[COL_TITLE])
                if lib_toks:
                    overlap = len(ttoks & lib_toks) / float(min(len(ttoks), len(lib_toks)))
                    if overlap >= 0.5:
                        _hit(row, "author+title")

    strong = signals & {"title", "doi", "arxiv"}
    if strong:
        category = "duplicate"
    elif signals:
        category = "uncertain"
    else:
        category = "new"
    return category, sorted(signals), [matches[k] for k in sorted(matches)]


def main():
    parser = argparse.ArgumentParser(
        prog="lookup_lib.py",
        description="文献库 4 信号查重（标题/DOI/arXiv/作者+标题），输出 JSON。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--check", metavar="FILE", required=True,
                        help="候选清单 JSON 文件（数组：[{title,doi,arxiv,authors}, ...]）")
    parser.add_argument("--lib-path", metavar="PATH", required=True,
                        help="文献库根目录（其下应有 %s）" % INDEX_NAME)
    args = parser.parse_args()

    if not os.path.isfile(args.check):
        print("错误：候选清单文件不存在: %s" % args.check, file=sys.stderr)
        sys.exit(1)
    if not os.path.isdir(args.lib_path):
        print("错误：文献库目录不存在: %s" % args.lib_path, file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.check, encoding="utf-8") as f:
            candidates = json.load(f)
    except (OSError, ValueError) as e:
        print("错误：候选清单 JSON 解析失败: %s" % e, file=sys.stderr)
        sys.exit(1)
    if not isinstance(candidates, list):
        print("错误：候选清单必须是 JSON 数组", file=sys.stderr)
        sys.exit(1)

    rows = load_index(args.lib_path)

    out = {"new": [], "duplicate": [], "uncertain": []}
    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        category, signals, matches = check_candidate(cand, rows)
        out[category].append({
            "candidate": cand,
            "match_info": {"signals": signals, "matches": matches},
        })

    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("查重完成：new=%d duplicate=%d uncertain=%d（库内 %d 条）"
          % (len(out["new"]), len(out["duplicate"]), len(out["uncertain"]), len(rows)),
          file=sys.stderr)


if __name__ == "__main__":
    main()
