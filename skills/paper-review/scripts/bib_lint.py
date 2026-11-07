#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bib_lint.py — paper-review 引文格式检查脚本（v2.0 S3 确定性检查）

引文格式问题属确定性重复劳动（li/xue/he 三篇各约 20 处），脚本化后
S3 领域席只做语义核对，不再逐字排查格式。

输入两种模式（按扩展名自动判定）：
  .bib            → BibTeX 模式：正则解析 @type{key, ...} 条目（字段支持 {}
                    与 "" 定界，嵌套花括号正确配对），提取 author/title/year/
                    journal/booktitle/note/eprint 等
  其他（.md/.txt）→ GB/T 7714 模式：条目 = 以 [N] 开头的行块（直到下一个
                    [N] 或空行分界；一行多条被换行折断的情形按 [N] 切块）

检查项（每项产出 级别 error|warn + 证据片段）：
  1. empty_conference  error  `[C]//` 后紧跟 `.`、`,`、`[` 或空白到行尾（空会议名/空出版者）
  2. double_period     error  出现 `..`（排除 `...` 省略号）
  3. comma_space       warn   拉丁字母间逗号后无空格（排除数字千分位 `,000` 与 URL/DOI）
  4. page_format       warn   页码区间含空格 `数字 - 数字`；或 [J]/@article 条目缺页码
  5. key_year          warn   （仅 .bib）citekey 首个 4 位年份（19|20 开头）≠ year 字段
  6. arxiv             warn   venue/journal/note/eprint 含 arxiv → "arXiv 预印本，
                              核实是否已正式发表"；--online 且 requests 可用时查
                              CrossRef（query.title，rows=3，超时10s，标题归一后
                              前 40 字符相似即命中）→ 命中升级 error "存在正式发表
                              版本"；网络失败/无 requests 保持 warn 且 JSON
                              online:false + online_error
  7. name_order        warn   （仅 .bib）author 拉丁姓名（and 分割）不含逗号且
                              ≥2 词 → "疑似未按 GB/T 姓前名后倒装"
  8. bilingual_pairing warn   条目含 CJK 字符 → "核实是否需双语著录配对"

用法：
  python bib_lint.py --input FILE [--run-dir DIR] [--output FILE] [--online]

输出文件（markdown 逐条判定表）：
  --output 指定 → 该路径；否则给了 --run-dir → {run_dir}/bib_lint.md；
  否则 → 输入文件同目录 bib_lint.md
  表头：| 条目 | 检查 | 级别 | 证据 | 判定 |（error=需修改，warn=需核实）
  末尾统计行：合计: N 条目, E errors, W warnings。

stdout（JSON）：
  {"success": true, "mode": "bib"|"gbt", "entries": N, "errors": N,
   "warnings": N, "by_check": {检查名: 计数}, "online": bool,
   "online_error": str|null, "output": path}

退出码：0=成功；1=文件读写失败；2=参数错误。条目数为 0 → success 但 stderr 警告。
"""
import argparse
import difflib
import io
import json
import os
import re
import sys

try:
    import requests
except ImportError:
    requests = None

# 修复 Windows 下 GBK 编码问题，强制 UTF-8 输出
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

CJK_RE = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
YEAR4_RE = re.compile(r"(?:19|20)\d{2}")
ARXIV_RE = re.compile(r"arxiv", re.IGNORECASE)
URL_MASK_RE = re.compile(r"(?:https?://|doi\s*:|www\.)\S+", re.IGNORECASE)
EMPTY_CONF_RE = re.compile(r"\[C\]//[ \t]*(?:[.,\[]|[ \t]*$)", re.MULTILINE)
DOUBLE_PERIOD_RE = re.compile(r"(?<!\.)\.\.(?!\.)")
COMMA_NOSPACE_RE = re.compile(r"(?<=[A-Za-z]),(?=\S)")
PAGE_SPACE_RE = re.compile(r"\d+[ \t]+-[ \t]*\d+|\d+[ \t]*-[ \t]+\d+")
PAGE_COLON_RE = re.compile(r":[ \t]*\d+")
GBT_MARK_RE = re.compile(r"\[\d+\]")
FIELD_RE = re.compile(r"([A-Za-z][A-Za-z0-9_.-]*)\s*=\s*")

VERDICT = {"error": "需修改", "warn": "需核实"}

# bib venue 类字段（arxiv 检查范围：venue/journal/note/eprint 等）
BIB_VENUE_FIELDS = ("journal", "booktitle", "note", "eprint", "howpublished",
                    "publisher", "venue", "school", "institution")


def to_posix(path):
    return path.replace("\\", "/")


def fail(msg, code=2):
    print("错误：%s" % msg, file=sys.stderr)
    sys.exit(code)


def _read_text(path):
    """utf-8-sig 优先，gbk 兜底"""
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    return None


def snippet(text, start, end, pad=20):
    """命中位置附近证据片段（单行化、截断、去 | 防表格破坏）"""
    a = max(0, start - pad)
    b = min(len(text), end + pad)
    s = re.sub(r"\s+", " ", text[a:b]).strip()
    if len(s) > 80:
        s = s[:80] + "…"
    return ("…" if a > 0 else "") + s.replace("|", "/") + ("…" if b < len(text) else "")


# ────────────────────────── BibTeX 解析 ──────────────────────────

def _match_brace(s, start):
    """s[start]=='{'，返回配对 '}' 下标（嵌套正确配对，跳过 "" 引用段），失败 -1"""
    depth = 0
    i = start
    n = len(s)
    while i < n:
        c = s[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        elif c == '"':
            i += 1
            while i < n and s[i] != '"':
                i += 1
        i += 1
    return -1


def _parse_fields(body):
    """条目体（key 之后部分）→ {字段名小写: 值}；值支持 {} 与 "" 定界及裸值"""
    fields = {}
    pos = 0
    n = len(body)
    while pos < n:
        m = FIELD_RE.search(body, pos)
        if not m:
            break
        name = m.group(1).lower()
        j = m.end()
        if j < n and body[j] == "{":
            k = _match_brace(body, j)
            if k == -1:
                k = n - 1
            val = body[j + 1:k]
            pos = k + 1
        elif j < n and body[j] == '"':
            k = body.find('"', j + 1)
            if k == -1:
                k = n
            val = body[j + 1:k]
            pos = k + 1
        else:
            k = body.find(",", j)
            if k == -1:
                k = n
            val = body[j:k]
            pos = k + 1
        fields[name] = val.strip()
    return fields


def parse_bib(text):
    """.bib 文本 → [{"key","type","fields","raw"}, ...]"""
    entries = []
    for m in re.finditer(r"@(\w+)\s*\{", text):
        ob = m.end() - 1
        cb = _match_brace(text, ob)
        if cb == -1:
            continue
        body = text[ob + 1:cb]
        ci = body.find(",")
        if ci == -1:
            key, fbody = body.strip(), ""
        else:
            key, fbody = body[:ci].strip(), body[ci + 1:]
        entries.append({
            "key": key or "(无key)",
            "type": m.group(1).lower(),
            "fields": _parse_fields(fbody),
            "raw": text[m.start():cb + 1],
        })
    return entries


# ────────────────────────── GB/T 7714 解析 ──────────────────────────

def parse_gbt(text):
    """[N] 开头行块（到下一个 [N] 或空行分界；一行多条按 [N] 切块）
    → [{"label","text"}, ...]"""
    entries = []
    marks = list(GBT_MARK_RE.finditer(text))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        chunk = text[m.start():end]
        blank = re.search(r"\n[ \t]*\n", chunk)
        if blank:
            chunk = chunk[:blank.start()]
        chunk = chunk.strip()
        if chunk:
            entries.append({"label": m.group(0), "text": chunk})
    return entries


# ────────────────────────── 检查项 ──────────────────────────

def mk(entry, check, level, evidence):
    return {"entry": entry, "check": check, "level": level, "evidence": evidence}


def add_hits(findings, entry, check, level, text, matches, msg=None):
    """按匹配列表产出一条 finding（证据=首处片段，多处标注计数）"""
    if not matches:
        return
    m0 = matches[0]
    ev = snippet(text, m0.start(), m0.end())
    if len(matches) > 1:
        ev += "（等%d处）" % len(matches)
    if msg:
        ev = "%s：%s" % (msg, ev)
    findings.append(mk(entry, check, level, ev))


def _norm_title(s):
    """标题归一：小写、去非字母数字，取前 40 字符"""
    return re.sub(r"[^a-z0-9]", "", s.lower())[:40]


def crossref_hit(title):
    """CrossRef 查正式发表版本。返回 (hit, info)；网络/依赖失败抛 RuntimeError"""
    if requests is None:
        raise RuntimeError("requests 模块不可用")
    try:
        resp = requests.get("https://api.crossref.org/works",
                            params={"query.title": title, "rows": 3},
                            timeout=10)
        resp.raise_for_status()
        items = resp.json().get("message", {}).get("items", [])
    except Exception as e:
        raise RuntimeError("CrossRef 查询失败: %s" % e)
    nq = _norm_title(title)
    if not nq:
        return False, ""
    for it in items:
        t = " ".join(it.get("title") or [])
        nt = _norm_title(t)
        if nt and (nq == nt
                   or difflib.SequenceMatcher(None, nq, nt).ratio() >= 0.85):
            return True, "CrossRef 命中: %s (doi:%s)" % (t[:60], it.get("DOI", "?"))
    return False, ""


def arxiv_finding(entry_label, text, match, title, ctx, findings):
    """arxiv 检查：默认 warn；--online 命中 CrossRef 升级 error，失败保持 warn"""
    ev = "arXiv 预印本，核实是否已正式发表：%s" % snippet(text, match.start(), match.end())
    level = "warn"
    if ctx["enabled"] and title.strip():
        try:
            hit, info = crossref_hit(title)
            if hit:
                level = "error"
                ev = "存在正式发表版本：%s" % info
        except RuntimeError as e:
            ctx["enabled"] = False      # 后续条目不再重试
            ctx["ok"] = False
            ctx["error"] = str(e)
    findings.append(mk(entry_label, "arxiv", level, ev))


def check_gbt_entry(entry, findings, ctx):
    label, text = entry["label"], entry["text"]
    # 1. empty_conference
    add_hits(findings, label, "empty_conference", "error", text,
             list(EMPTY_CONF_RE.finditer(text)), "空会议名/出版者")
    # 2. double_period
    add_hits(findings, label, "double_period", "error", text,
             list(DOUBLE_PERIOD_RE.finditer(text)))
    # 3. comma_space（掩蔽 URL/DOI，保持偏移不变）
    masked = URL_MASK_RE.sub(lambda m: " " * len(m.group(0)), text)
    add_hits(findings, label, "comma_space", "warn", text,
             list(COMMA_NOSPACE_RE.finditer(masked)), "逗号后缺空格")
    # 4. page_format
    ranges = list(PAGE_SPACE_RE.finditer(text))
    if ranges:
        add_hits(findings, label, "page_format", "warn", text, ranges, "页码区间含空格")
    elif re.search(r"\[J\]", text, re.IGNORECASE) and not PAGE_COLON_RE.search(text):
        findings.append(mk(label, "page_format", "warn", "[J] 条目缺页码"))
    # 6. arxiv
    m = ARXIV_RE.search(text)
    if m:
        tm = re.search(r"\.(.*?)\[[A-Za-z]\]", text, re.S)
        title = tm.group(1).strip() if tm else re.sub(r"^\[\d+\]\s*", "", text)
        arxiv_finding(label, text, m, title, ctx, findings)
    # 8. bilingual_pairing
    if CJK_RE.search(text):
        findings.append(mk(label, "bilingual_pairing", "warn", "核实是否需双语著录配对"))


def check_bib_entry(entry, findings, ctx):
    label, raw, fields = entry["key"], entry["raw"], entry["fields"]
    # 2. double_period
    add_hits(findings, label, "double_period", "error", raw,
             list(DOUBLE_PERIOD_RE.finditer(raw)))
    # 3. comma_space
    masked = URL_MASK_RE.sub(lambda m: " " * len(m.group(0)), raw)
    add_hits(findings, label, "comma_space", "warn", raw,
             list(COMMA_NOSPACE_RE.finditer(masked)), "逗号后缺空格")
    # 4. page_format
    ranges = list(PAGE_SPACE_RE.finditer(raw))
    if ranges:
        add_hits(findings, label, "page_format", "warn", raw, ranges, "页码区间含空格")
    elif entry["type"] == "article" and "pages" not in fields:
        findings.append(mk(label, "page_format", "warn", "@article 条目缺 pages 字段"))
    # 5. key_year
    km = YEAR4_RE.search(label)
    year = fields.get("year", "").strip("{} ").strip()
    if km and year and km.group(0) != year:
        findings.append(mk(label, "key_year", "warn",
                           "citekey 年份 %s ≠ year 字段 %s" % (km.group(0), year)))
    # 7. name_order
    author = fields.get("author", "")
    for name in re.split(r"\s+and\s+", author, flags=re.IGNORECASE):
        nm = name.strip().strip("{}").strip()
        if not nm or "," in nm:
            continue
        if len(nm.split()) >= 2 and re.fullmatch(r"[A-Za-z][A-Za-z .'\-]*", nm):
            findings.append(mk(label, "name_order", "warn",
                               "疑似未按 GB/T 姓前名后倒装：%s" % nm))
            break
    # 6. arxiv（venue 类字段）
    venue = " ".join(fields.get(k, "") for k in BIB_VENUE_FIELDS)
    if ARXIV_RE.search(venue):
        rm = ARXIV_RE.search(raw)
        if rm:
            arxiv_finding(label, raw, rm, fields.get("title", ""), ctx, findings)
    # 8. bilingual_pairing
    if CJK_RE.search(raw):
        findings.append(mk(label, "bilingual_pairing", "warn", "核实是否需双语著录配对"))


# ────────────────────────── 输出 ──────────────────────────

def write_md(path, mode, input_path, n_entries, findings, errors, warnings, online):
    lines = ["# bib_lint 引文格式检查报告", ""]
    lines.append("- 输入: `%s`" % to_posix(os.path.abspath(input_path)))
    lines.append("- 模式: %s" % ("BibTeX" if mode == "bib" else "GB/T 7714"))
    lines.append("- 条目: %d ｜ 错误: %d ｜ 警告: %d ｜ 在线核验: %s"
                 % (n_entries, errors, warnings, "是" if online else "否"))
    lines += ["", "| 条目 | 检查 | 级别 | 证据 | 判定 |",
              "| --- | --- | --- | --- | --- |"]
    for f in findings:
        ev = f["evidence"].replace("|", "\\|")
        lines.append("| %s | %s | %s | %s | %s |"
                     % (f["entry"], f["check"], f["level"], ev, VERDICT[f["level"]]))
    lines += ["", "合计: %d 条目, %d errors, %d warnings。" % (n_entries, errors, warnings), ""]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(
        prog="bib_lint.py",
        description="paper-review 引文格式确定性检查：.bib（BibTeX）或 .md/.txt（GB/T 7714 "
                    "著录列表）→ markdown 逐条判定表 + stdout JSON 汇总。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", metavar="FILE", required=True,
                        help="待检查文件（.bib → BibTeX 模式；其他 → GB/T 7714 模式）")
    parser.add_argument("--run-dir", metavar="DIR", default=None,
                        help="运行目录（缺省输出时为 {run_dir}/bib_lint.md）")
    parser.add_argument("--output", metavar="FILE", default=None,
                        help="markdown 报告输出路径（缺省：run-dir 或输入同目录 bib_lint.md）")
    parser.add_argument("--online", action="store_true",
                        help="arXiv 条目查 CrossRef 核实正式发表版本（需 requests；失败优雅降级）")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        fail("输入文件不存在: %s" % args.input, code=1)
    text = _read_text(args.input)
    if text is None:
        fail("无法读取输入文件（编码非 utf-8/gbk）: %s" % args.input, code=1)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    mode = "bib" if os.path.splitext(args.input)[1].lower() == ".bib" else "gbt"
    entries = parse_bib(text) if mode == "bib" else parse_gbt(text)
    if not entries:
        print("警告：未解析到任何条目: %s" % args.input, file=sys.stderr)

    ctx = {"enabled": False, "ok": False, "error": None}
    if args.online:
        if requests is None:
            ctx["error"] = "requests 模块不可用"
        else:
            ctx["enabled"] = True
            ctx["ok"] = True

    findings = []
    for e in entries:
        if mode == "bib":
            check_bib_entry(e, findings, ctx)
        else:
            check_gbt_entry(e, findings, ctx)

    errors = sum(1 for f in findings if f["level"] == "error")
    warnings = len(findings) - errors
    by_check = {}
    for f in findings:
        by_check[f["check"]] = by_check.get(f["check"], 0) + 1

    if args.output:
        out = args.output
    elif args.run_dir:
        out = os.path.join(args.run_dir, "bib_lint.md")
    else:
        out = os.path.join(os.path.dirname(os.path.abspath(args.input)), "bib_lint.md")
    try:
        outdir = os.path.dirname(os.path.abspath(out))
        if outdir:
            os.makedirs(outdir, exist_ok=True)
        write_md(out, mode, args.input, len(entries), findings,
                 errors, warnings, bool(ctx["enabled"] and ctx["ok"]))
    except OSError as e:
        fail("写入报告失败: %s" % e, code=1)

    result = {
        "success": True,
        "mode": mode,
        "entries": len(entries),
        "errors": errors,
        "warnings": warnings,
        "by_check": by_check,
        "online": bool(ctx["enabled"] and ctx["ok"]),
        "online_error": ctx["error"],
        "output": to_posix(os.path.abspath(out)),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
