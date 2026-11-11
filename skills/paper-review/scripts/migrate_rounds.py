#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""migrate_rounds.py — paper-review「修订版另建目录」→「单目录多版本」存量迁移（v2.1 扁平结构）

背景（v2.0 §九 → v2.1 §十一 第12条扁平化）：旧习惯为修订版另建目录（如 papers/q10-1/），
现为单目录多版本 + 扁平结构：
  - v1 源留 {paper_dir} 根（单文件）或 v1/（多文件工程）；v2+ 源入 {paper_dir}/v<N>/
    （保留原名与内部结构；取代旧 sources/v<N>/，旧结构由本脚本步骤0就地规范化）
  - 草稿统一入 {paper_dir}/draft/：draft.md（v1）、draft-v<N>.md（版本快照）
  - 回复信统一入 {paper_dir}/response/：response*.md（可选输入）
  - {paper_dir}/.review/ 下分 r<N>/ 轮次目录；config.json（schema 2 +
    layout=flat-v2.1）为跨轮状态唯一权威源
  - {paper_dir}/.review/chain.md 承载版本谱系（不存在时创建骨架）

迁移计划（按序；本脚本只移动文件/目录，绝不删除任何文件，也绝不删除 {new_dir}）：
  0. {paper_dir} 就地规范化（兼容 v2.0 旧结构）：sources/v<K> → v<K>；
     根 draft*.md → draft/；根 response*.md → response/
  1. {new_dir} 下除 .review/ 与顶层 draft*.md、response*.md 外的所有文件
     → {paper_dir}/v<N>/（递归，保留原名与内部结构）
  2. {new_dir}/draft.md → {paper_dir}/draft/draft-v<N>.md
     （其余 draft-v*.md 保留原名一并移入 draft/）
  3. {new_dir}/response*.md → {paper_dir}/response/（保留原名，可选输入）
  4. {paper_dir}/.review/ 扁平旧产物（除 config.json、chain.md、RESUME.md、r*/ 目录外
     的全部文件与目录）→ {paper_dir}/.review/r1/
  5. {new_dir}/.review/ 下全部产物 → {paper_dir}/.review/r<N>/
  6. 回填/合并 {paper_dir}/.review/config.json（schema 2 + layout=flat-v2.1；
     已存在时保留既有 exemptions/withdrawals/adjudications/rounds 并继承 doctype，
     补 versions 映射；source_root="v<N>"、draft="draft/draft-v<N>.md"）
  7. {paper_dir}/.review/chain.md 不存在时创建骨架（# 版本谱系 + 每轮一节，
     含「决议：待回填」「发现状态流转表：待回填」占位）
  8. 迁移后在 warnings 提示 {new_dir} 已腾空/残留 X 个文件，确认后可手工删除

用法：
  # dry-run（缺省）：只输出迁移计划，不做任何文件系统改动
  python migrate_rounds.py --paper-dir <paper>/ --new-dir <paper>-1 \
      [--doctype problem-collection] [--new-version 2]

  # 实际执行移动与 config.json / chain.md 写入
  python migrate_rounds.py --paper-dir <paper>/ --new-dir <paper>-1 \
      --doctype problem-collection --confirm

stdout（JSON）：
  {"success": true, "dry_run": true|false,
   "moves": [{"from": "<posix绝对路径>", "to": "<posix绝对路径>"}, ...],
   "config": {计划写入的完整 config.json}, "warnings": [...],
   "moved": N}          ← moved 仅 --confirm 时输出

退出码：0=成功；1=运行时失败（--confirm 中途 OSError 时已移动项不回滚，
stdout 输出 {"success": false, "moved": k, ...} 说明进度）；
2=参数错误（目录不存在 / 两目录相同或互相包含 / --new-version < 2）。
"""
import argparse
import fnmatch
import io
import json
import os
import re
import shutil
import sys

# 修复 Windows 下 GBK 编码问题，强制 UTF-8 输出
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SCHEMA = 2
LAYOUT = "flat-v2.1"

# 步骤4：.review/ 扁平产物中不移入 r1/ 的文件名（小写比较）
KEEP_FLAT_FILES = ("config.json", "chain.md", "resume.md")

# 步骤0：旧结构 sources/v<K> 的版本目录名模式
SOURCES_V_RE = re.compile(r"^v\d+$")


def to_posix(path):
    return path.replace("\\", "/")


def pabs(path):
    return to_posix(os.path.abspath(path))


def fail(msg, code=2):
    print("错误：%s" % msg, file=sys.stderr)
    sys.exit(code)


def _glob(name, pattern):
    """大小写不敏感的 glob 匹配（跨平台一致；pattern 须为小写）"""
    return fnmatch.fnmatchcase(name.lower(), pattern)


def _under(child, parent):
    """child（posix 绝对路径）是否严格位于 parent 目录内"""
    return child.startswith(parent.rstrip("/") + "/")


def list_top(path):
    try:
        return sorted(os.listdir(path))
    except OSError:
        return []


def count_files(path):
    total = 0
    for _, _, files in os.walk(path):
        total += len(files)
    return total


# ────────────────────────── config.json / chain.md ──────────────────────────

def _normalize_version_entry(entry):
    """既有 versions 条目路径口径规范化（v2.0 → v2.1 扁平）：
    draft/response 基名 → draft/、response/ 前缀；source_root "sources/vK" → "vK"
    （与步骤0 的物理移动保持一致）"""
    if not isinstance(entry, dict):
        return entry
    e = dict(entry)
    for key, prefix in (("draft", "draft/"), ("response", "response/")):
        val = e.get(key)
        if isinstance(val, str) and val and "/" not in val:
            e[key] = prefix + val
    sr = e.get("source_root")
    if isinstance(sr, str) and sr.startswith("sources/"):
        e["source_root"] = sr[len("sources/"):]
    return e


def build_config(paper_dir, doctype, n, response_name, existing=None):
    """构造 schema 2 + layout=flat-v2.1 的 config.json；existing 为既有 config 时做合并：
    保留既有 exemptions/withdrawals/adjudications/rounds/versions 条目与 doctype，
    补齐 v1/v<N> 版本映射与 r1/r<N> 轮次映射（严格 schema，不保留未知键）；
    既有 versions 条目按 v2.1 路径口径规范化。"""
    vk, rk = "v%d" % n, "r%d" % n
    # v1 形态：v1/ 目录（多文件工程）→ "v1"；否则根单文件 → "."
    v1_root = "v1" if os.path.isdir(os.path.join(paper_dir, "v1")) else "."
    # 步骤0 落定后 v1 草稿位于 draft/draft.md（dry-run 时按当前存在性预判）
    v1_draft = None
    for cand in (os.path.join(paper_dir, "draft", "draft.md"),
                 os.path.join(paper_dir, "draft.md")):
        if os.path.isfile(cand):
            v1_draft = "draft/draft.md"
            break
    versions = {"v1": {"source_root": v1_root, "draft": v1_draft, "response": None}}
    versions[vk] = {
        "source_root": vk,
        "draft": "draft/draft-v%d.md" % n,
        "response": ("response/%s" % response_name) if response_name else None,
    }
    rounds = {"r1": {"version": "v1"}, rk: {"version": vk}}
    cfg = {
        "schema": SCHEMA,
        "layout": LAYOUT,
        "paper_dir": pabs(paper_dir),
        "doctype": doctype,
        "versions": versions,
        "current_version": vk,
        "rounds": rounds,
        "current_round": rk,
        "exemptions": [],
        "withdrawals": [],
        "adjudications": [],
    }
    if isinstance(existing, dict):
        for k in ("exemptions", "withdrawals", "adjudications"):
            if isinstance(existing.get(k), list):
                cfg[k] = existing[k]
        if isinstance(existing.get("rounds"), dict):
            merged = dict(existing["rounds"])
            for key, val in rounds.items():
                merged.setdefault(key, val)
            cfg["rounds"] = merged
        if isinstance(existing.get("versions"), dict):
            merged = {k: _normalize_version_entry(v)
                      for k, v in existing["versions"].items()}
            for key, val in versions.items():
                merged.setdefault(key, val)
            cfg["versions"] = merged
        if cfg["doctype"] is None and existing.get("doctype") is not None:
            cfg["doctype"] = existing["doctype"]   # 未显式指定时继承既有值
    return cfg


def _round_key(rk):
    if rk[:1] == "r" and rk[1:].isdigit():
        return (0, int(rk[1:]), "")
    return (1, 0, rk)


def chain_skeleton(cfg):
    """chain.md 骨架：# 版本谱系 + 每轮一节（决议/发现状态流转表占位）"""
    lines = [
        "# 版本谱系",
        "",
        "> migrate_rounds.py 生成的骨架：各轮「决议」与「发现状态流转表」待回填（v2.0 §9.5）。",
    ]
    versions = cfg.get("versions") or {}
    rounds = cfg.get("rounds") or {}
    for rk in sorted(rounds, key=_round_key):
        ver = (rounds.get(rk) or {}).get("version") or "?"
        src_root = (versions.get(ver) or {}).get("source_root") or "?"
        lines += [
            "",
            "## %s（版本 %s）" % (rk, ver),
            "",
            "- source_root: %s" % src_root,
            "- 决议：待回填",
            "- 发现状态流转表：待回填",
        ]
    return "\n".join(lines) + "\n"


def read_existing_config(review):
    """读取既有 config.json（utf-8-sig）；不存在返回 None，解析失败按运行时错误退出"""
    path = os.path.join(review, "config.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        fail("既有 config.json 读取/解析失败（%s）: %s" % (path, e), code=1)
    return data if isinstance(data, dict) else None


# ────────────────────────── 迁移计划（dry-run 安全，零改动） ──────────────────────────

def plan_migration(paper_dir, new_dir, n):
    """按步骤 0–5 生成移动计划。返回 (moves, warnings, response_names)。
    目标已存在或已在计划中 → 记 warning 并跳过（绝不覆盖、绝不删除）。"""
    review = os.path.join(paper_dir, ".review")
    new_review = os.path.join(new_dir, ".review")
    src_root = os.path.join(paper_dir, "v%d" % n)
    moves, warnings, planned = [], [], set()
    response_names = []

    def add(src, dst):
        s, d = pabs(src), pabs(dst)
        if d in planned or os.path.exists(dst):
            warnings.append("目标已存在或已在计划中，跳过移动：%s → %s" % (s, d))
            return False
        planned.add(d)
        moves.append({"from": s, "to": d})
        return True

    # 0) paper_dir 就地规范化（v2.0 旧结构 → v2.1 扁平；幂等：目标存在即跳过）
    sources_dir = os.path.join(paper_dir, "sources")
    if os.path.isdir(sources_dir):
        for name in list_top(sources_dir):
            sp = os.path.join(sources_dir, name)
            if os.path.isdir(sp) and SOURCES_V_RE.match(name):
                add(sp, os.path.join(paper_dir, name))     # sources/vK → vK
    for fn in list_top(paper_dir):
        p = os.path.join(paper_dir, fn)
        if not os.path.isfile(p):
            continue
        if _glob(fn, "draft*.md"):
            add(p, os.path.join(paper_dir, "draft", fn))       # 根草稿 → draft/
        elif _glob(fn, "response*.md"):
            add(p, os.path.join(paper_dir, "response", fn))    # 根回复信 → response/

    # 1) 源文件（递归，保留内部结构；排除顶层 .review/、draft*.md、response*.md）
    for root, dirs, files in os.walk(new_dir):
        dirs.sort()
        rel_root = os.path.relpath(root, new_dir)
        top = rel_root == os.curdir
        if top and ".review" in dirs:
            dirs.remove(".review")            # .review/ 由步骤 5 处理
        for fn in sorted(files):
            if top and (_glob(fn, "draft*.md") or _glob(fn, "response*.md")):
                continue                      # 由步骤 2/3 处理
            rel = fn if top else to_posix(os.path.join(rel_root, fn))
            add(os.path.join(root, fn), os.path.join(src_root, rel))

    # 2) draft.md → draft/draft-v<N>.md；其余 draft*.md 保留原名移入 draft/
    d_main = os.path.join(new_dir, "draft.md")
    if os.path.isfile(d_main):
        add(d_main, os.path.join(paper_dir, "draft", "draft-v%d.md" % n))
    for fn in list_top(new_dir):
        p = os.path.join(new_dir, fn)
        if fn != "draft.md" and _glob(fn, "draft*.md") and os.path.isfile(p):
            add(p, os.path.join(paper_dir, "draft", fn))

    # 3) response*.md → {paper_dir}/response/（保留原名，可选输入）
    for fn in list_top(new_dir):
        p = os.path.join(new_dir, fn)
        if _glob(fn, "response*.md") and os.path.isfile(p):
            if add(p, os.path.join(paper_dir, "response", fn)):
                response_names.append(fn)

    # 4) {paper_dir}/.review/ 扁平旧产物 → r1/（config.json、chain.md、RESUME.md、r*/ 除外）
    if os.path.isdir(review):
        r1 = os.path.join(review, "r1")
        for fn in list_top(review):
            p = os.path.join(review, fn)
            if os.path.isdir(p):
                if _glob(fn, "r*"):
                    continue                  # r1/r2/… 轮次目录不再搬动
            elif fn.lower() in KEEP_FLAT_FILES:
                continue
            add(p, os.path.join(r1, fn))

    # 5) {new_dir}/.review/ 下全部产物 → r<N>/
    if os.path.isdir(new_review):
        rn = os.path.join(review, "r%d" % n)
        for fn in list_top(new_review):
            add(os.path.join(new_review, fn), os.path.join(rn, fn))

    # {new_dir} 无任何可迁移文件 → 提示（仍可执行：config 回填与 r1 归档有意义）
    prefix = pabs(new_dir) + "/"
    if not any(m["from"].startswith(prefix) for m in moves):
        warnings.append("%s 未发现可迁移文件，仅执行 config.json 回填与 r1 归档" % pabs(new_dir))
    return moves, warnings, response_names


def predict_remaining(new_dir, moves):
    """dry-run 下预测迁移后 {new_dir} 残留文件数（计划移动的文件/目录内文件均扣除）"""
    prefix = pabs(new_dir) + "/"
    total = count_files(new_dir)
    moved_files = 0
    for m in moves:
        f = m["from"]
        if not f.startswith(prefix):
            continue
        if os.path.isfile(f):
            moved_files += 1
        elif os.path.isdir(f):
            moved_files += count_files(f)
    return max(total - moved_files, 0)


def remaining_warning(new_dir, remaining, dry):
    prefix = "预计迁移后" if dry else "迁移后"
    if remaining <= 0:
        return "%s%s 已腾空（仅剩空目录骨架），确认后可手工删除" % (prefix, pabs(new_dir))
    return "%s%s 残留 %d 个文件，确认后可手工删除" % (prefix, pabs(new_dir), remaining)


# ────────────────────────── --confirm 执行 ──────────────────────────

def die_progress(msg, moved):
    """运行时失败：已移动项不回滚，输出进度说明并 exit 1"""
    print("错误：%s" % msg, file=sys.stderr)
    print(json.dumps({
        "success": False, "dry_run": False, "moved": moved, "error": msg,
        "note": "已移动项不回滚；请依据 moved 计数与错误信息检查进度后重试或手工修复",
    }, ensure_ascii=False, indent=2))
    sys.exit(1)


def execute_moves(moves, warnings):
    """按序执行移动（os.makedirs + shutil.move），返回成功移动数"""
    moved = 0
    for m in moves:
        src, dst = m["from"], m["to"]
        try:
            if not os.path.exists(src):
                warnings.append("源不存在，跳过：%s" % src)
                continue
            if os.path.exists(dst):
                warnings.append("目标已存在，跳过：%s" % dst)
                continue
            parent = os.path.dirname(dst)
            if parent:
                os.makedirs(parent, exist_ok=True)
            shutil.move(src, dst)
            moved += 1
        except OSError as e:
            die_progress("移动失败（第 %d/%d 项）：%s → %s：%s"
                         % (moved + 1, len(moves), src, dst, e), moved)
    return moved


def write_outputs(paper_dir, cfg, moved):
    """步骤 6/7：写 config.json（覆盖为合并结果）；chain.md 仅在不存在时创建骨架"""
    review = os.path.join(paper_dir, ".review")
    cfg_path = os.path.join(review, "config.json")
    chain_path = os.path.join(review, "chain.md")
    try:
        os.makedirs(review, exist_ok=True)
        with open(cfg_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        if not os.path.isfile(chain_path):
            with open(chain_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(chain_skeleton(cfg))
    except OSError as e:
        die_progress("写入 .review 输出失败：%s" % e, moved)


# ────────────────────────── 入口 ──────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="migrate_rounds.py",
        description="paper-review 存量迁移：「修订版另建目录」→「单目录多版本」v2.1 扁平结构"
                    "（v<N>/ + draft/ + response/ + .review/r<N>/ + config.json schema2"
                    "（layout=flat-v2.1）+ chain.md；含旧 sources/v<N> 就地规范化）。"
                    "缺省 dry-run 只输出计划；--confirm 实际执行移动（绝不删除任何文件/目录）。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--paper-dir", metavar="DIR", required=True,
                        help="论文主目录（如 <paper>/）")
    parser.add_argument("--new-dir", metavar="DIR", required=True,
                        help="修订版另建目录（如 <paper>-1/），迁移后不删除，仅提示手工处理")
    parser.add_argument("--doctype", metavar="T", default=None,
                        help="稿件类型（如 problem-collection），写入 config.json；"
                             "缺省且既有 config 有值时继承，否则为 null")
    parser.add_argument("--new-version", metavar="N", type=int, default=2,
                        help="新版本号（须 ≥2，v1 为根目录原版）")
    parser.add_argument("--confirm", action="store_true",
                        help="实际执行移动与 config.json/chain.md 写入（缺省为 dry-run）")
    args = parser.parse_args()

    paper_dir, new_dir, n = args.paper_dir, args.new_dir, args.new_version
    if not os.path.isdir(paper_dir):
        fail("--paper-dir 不存在或不是目录: %s" % paper_dir)
    if not os.path.isdir(new_dir):
        fail("--new-dir 不存在或不是目录: %s" % new_dir)
    if n < 2:
        fail("--new-version 须 ≥2（v1 为根目录原版），收到: %d" % n)
    pp, np_ = pabs(paper_dir), pabs(new_dir)
    if pp == np_:
        fail("--paper-dir 与 --new-dir 不能为同一目录: %s" % pp)
    if _under(np_, pp) or _under(pp, np_):
        fail("--paper-dir 与 --new-dir 不能互相包含: %s / %s" % (pp, np_))

    moves, warnings, response_names = plan_migration(paper_dir, new_dir, n)

    review = os.path.join(paper_dir, ".review")
    existing = read_existing_config(review)
    rn_name = "response-v%d.md" % n
    if response_names:
        response = sorted(response_names)[0]
    elif (os.path.isfile(os.path.join(paper_dir, "response", rn_name))
          or os.path.isfile(os.path.join(paper_dir, rn_name))):
        response = rn_name
    else:
        response = None
    cfg = build_config(paper_dir, args.doctype, n, response, existing)

    if not os.path.isfile(os.path.join(review, "chain.md")):
        warnings.append("chain.md 不存在，%s版本谱系骨架"
                        % ("本次将创建" if args.confirm else "--confirm 执行时将创建"))

    if not args.confirm:
        warnings.append(remaining_warning(new_dir, predict_remaining(new_dir, moves), dry=True))
        result = {"success": True, "dry_run": True, "moves": moves,
                  "config": cfg, "warnings": warnings}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)

    moved = execute_moves(moves, warnings)
    write_outputs(paper_dir, cfg, moved)
    warnings.append(remaining_warning(new_dir, count_files(new_dir), dry=False))
    result = {"success": True, "dry_run": False, "moves": moves,
              "config": cfg, "warnings": warnings, "moved": moved}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
