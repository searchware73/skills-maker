#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""setup_env.py — paper-review 环境初始化脚本（v2.1 扁平目录）

功能：
  1. 校验论文文件存在、可读、可解码（UTF-8 优先，GBK 兜底）；
     非 Markdown 输入（.pdf/.docx/.tex/目录）给出「先走 Step 0.0 输入类型
     分派转换出 draft/draft.md」的明确指引
  2. 若指定 --section X.Y，解析 Markdown 标题定位该小节起止行号
     （1-based，含头含尾；小节范围覆盖其下所有子小节）
  3. 目录扁平化（v2.1 §十一 第12条）：
     - paper_dir 从 draft/ 反推：<paper>/draft/draft-vN.md → <paper>；
       旧扁平形态 <paper>/draft-vN.md（v1.x 只读兼容）→ <paper>
     - v1 二选一检测：根单文件源（source_root="."）与 v1/ 目录
       （多文件 LaTeX 整包，source_root="v1"）不得并存，并存即报错
     - v2+ 源一律 vN/（source_root="vN"）；旧 sources/vN 记录在目录
       仍存在时只读兼容
     - 工程根 INDEX.md 不存在时创建骨架（Step 6 追加行）
  4. 版本与轮次解析（v2.0 §九）：
     - draft.md → v1；draft-vN.md → vN（第 N 个收到的稿件版本）
     - r<N> = 第 N 次审阅运行；产物一律路由到 {review_dir}/r<N>/；
       rounds.rN 记录 started_at（覆盖护栏 v1 跟踪判定用）
     - .review/config.json 为跨轮状态唯一权威源（doctype/source_root/
       豁免清单/撤回记录/用户裁决），已存在时合并保留；
       新结构写入 "layout": "flat-v2.1"（迁移脚本识别用）
  5. --doctype 稿件类型声明与准则绑定（v2.0 §八）：
     - 未声明且无历史继承时 needs_doctype_confirmation=true，
       附自动检测线索 doctype_hints，SKILL.md 必须 AskUserQuestion 确认后
       带 --doctype 重跑（同轮更新，不递增轮次），禁止臆测 full-paper
     - applied_criteria 输出该类型的 必备/豁免/置换/合规 四组规则
  6. 覆盖护栏（§九规则2 + §十一 第7条修正）：已有 r≥1 轮记录且根目录出现
     未登记源文件时 needs_source_confirmation=true；判定排除已登记文件、
     v1/ vN/ draft/ response/ reports/ figures/ media/ 目录、以及
     mtime 早于 r1 开跑时间的 v1 既有源
  7. --source/--format/--focus/--no-fix（§十一 第13条）：源路径与格式
     登记进 config.versions 并输出，透传给 conversion_audit / anchor_map；
     --focus 在 Step 0 记录后由 SKILL 路由
  8. Step 0 成本与模式预估（§十 ⑪）：按 doctype 与行数输出 estimate，
     给出 --quick vs 正式模式建议，用户可当场改判

用法：
  python setup_env.py --file <paper>/draft/draft.md [--section 1.1] [--rounds 3]
      [--source <源文件|源目录>] [--format tex|docx|pdf]
      [--doctype full-paper|thesis|proposal|problem-collection|extended-abstract
                |technical-report|section-draft|review|other:<描述>]
      [--focus panel|de-ai] [--quick] [--no-fix]
      [--re-review] [--response <paper>/response/response-v2.md]
      [--expert-comments 专家意见.md|.docx] [--panel default|full] [--new-run]

  轮次判定规则：
    - 无 config.json → r1
    - 有 config.json：解析版本 > 记录版本 → 新轮次 r<N+1>
      同版本时默认复用 current_round（用于补 --doctype 等同轮更新）；
      对同一版本做全量重审须显式 --new-run

输出（stdout，JSON；含 v1.x/v2.0 全部旧键，向后兼容）：
  {
    "file_path": "...", "section": "1.1", "section_range": [20, 87],
    "paper_dir": "...", "layout": "flat-v2.1", "index_path": ".../INDEX.md",
    "review_dir": ".../.review/", "run_dir": ".../.review/r2/",
    "rounds_max": 3, "total_lines": 500, "section_title": "...",
    "version": "v2", "round": "r2", "config_path": "...",
    "source": "...", "source_format": "docx", "focus": null, "no_fix": false,
    "doctype": "problem-collection", "applied_criteria": {...},
    "needs_doctype_confirmation": false, "doctype_hints": [...],
    "needs_source_confirmation": false, "untracked_sources": [...],
    "re_review": true, "expert_comments": "...", "estimate": {...},
    "success": true
  }

退出码：0=成功；1=初始化检查未通过（详见 JSON 与 stderr）；2=参数错误。
"""
import argparse
import datetime
import io
import json
import os
import re
import sys
import zipfile

# 修复 Windows 下 GBK 编码问题，强制 UTF-8 输出
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

LOG_FILES = ["deai_log.md", "revision_log.md", "convergence.md"]

LAYOUT = "flat-v2.1"

# 带编号标题：## 1.1 xxx / ### 1.1.1 xxx / # 1 xxx
NUMBERED_HEADING_RE = re.compile(r"^(#{1,6})\s+(\d+(?:\.\d+)*)(?=[^\d.]|$)")
# 任意标题（含无编号标题，如 # 参考文献）
ANY_HEADING_RE = re.compile(r"^(#{1,6})\s+")

# 版本文件名：draft-vN.md / 论文-vN.md（v1 无后缀）
VERSION_FILE_RE = re.compile(r"-v(\d+)\.(?:md|markdown)$", re.IGNORECASE)

DOCTYPES = ("full-paper", "thesis", "proposal", "problem-collection",
            "extended-abstract", "technical-report", "section-draft", "review")

# 根目录源文件类型（覆盖护栏扫描用）
SOURCE_EXTS = (".docx", ".pdf", ".tex", ".zip", ".doc")

# 非 Markdown 输入（Step 0.0 输入类型分派应先转换）
NON_MD_INPUT_EXTS = (".pdf", ".docx", ".doc", ".tex")

# 覆盖护栏忽略目录（v2.1 扁平结构约定目录；vN/ 另按正则匹配）
IGNORED_DIRS = ("draft", "response", "reports", "figures", "media")
VN_DIR_RE = re.compile(r"^v\d+$", re.IGNORECASE)

INDEX_HEADER = """# 论文审查索引

> 一行一篇（paper-review Step 6 追加；路径相对论文目录）。

| 稿件 | doctype | 当前轮次 | 决议 | 日期 | 报告路径 |
|------|---------|----------|------|------|----------|
"""

# ── doctype 准则绑定表（§八；人类/代理可读版见 references/doctype-criteria.md，
#    两处必须同步修改。required=(要素, 缺失严重度)；exempt=缺失一律不报；
#    substituted=(原检查, 置换后检查)；compliance=绑定的合规清单组）──
DOCTYPE_CRITERIA = {
    "full-paper": {
        "required": [("摘要", "P1"), ("参考文献", "P0"),
                     ("实验/数据支撑", "P0"), ("结论", "P1")],
        "exempt": [],
        "substituted": [],
        "compliance": ["数据/代码可得性声明", "AI 使用披露",
                       "人类被试/数据伦理声明（涉及时）"],
    },
    "thesis": {
        "required": [("中英文摘要", "P1"), ("参考文献", "P0"),
                     ("致谢", "P2"), ("独创性声明页", "P2")],
        "exempt": [],
        "substituted": [],
        "compliance": ["AI 使用披露", "保密审查/地名脱敏声明（涉及时）"],
    },
    "proposal": {
        "required": [("定量断言出处", "P1"), ("可行性论证", "P1")],
        "exempt": ["摘要", "参考文献", "实验节", "统计审查", "可复现性"],
        "substituted": [("数据支撑证明", "声称↔依据（初步数据/权威出处/可行性论证）"),
                        ("引用检查", "支柱性定量断言须注明数据来源，叙述性背景可无引用")],
        "compliance": ["保密审查/地名脱敏声明（军事·边防类）"],
    },
    "problem-collection": {
        "required": [("定量断言出处", "P1"), ("问题遴选方法说明", "P2")],
        "exempt": ["摘要", "参考文献", "实验节", "统计审查", "可复现性", "结论节"],
        "substituted": [("数据支撑证明", "声称↔依据（初步数据/权威出处（白皮书·标准·官方口径）/可行性论证）"),
                        ("引用检查", "支柱性定量断言须注明数据来源，叙述性背景可无引用")],
        "compliance": ["保密审查/地名脱敏声明（军事·边防类）"],
    },
    "extended-abstract": {
        "required": [("核心贡献陈述", "P1")],
        "exempt": ["独立摘要节", "参考文献", "结论节", "统计审查"],
        "substituted": [],
        "compliance": [],
    },
    "technical-report": {
        "required": [("数据来源说明", "P1")],
        "exempt": ["摘要", "参考文献"],
        "substituted": [("可复现性", "实现环境描述完整性")],
        "compliance": ["数据/代码可得性声明"],
    },
    "section-draft": {
        "required": [],
        "exempt": ["摘要", "参考文献", "结论节", "结构完整性"],
        "substituted": [],
        "compliance": [],
    },
    "review": {
        "required": [("参考文献（覆盖度）", "P0"), ("文献谱系梳理", "P1"),
                     ("摘要", "P1"), ("结论与展望", "P1")],
        "exempt": ["实验节", "可复现性"],
        "substituted": [("统计审查", "文献计量口径一致性")],
        "compliance": ["AI 使用披露"],
    },
}
OTHER_CRITERIA = {
    "required": [], "exempt": [], "substituted": [],
    "compliance": [],
    "note": "other 类型无预置准则：1a 配置卡阶段由 S1（EIC）依用户描述"
            "现场出具类型适配判定，必备/豁免要素经 AskUserQuestion 与用户确认",
}


def to_posix(path):
    """Windows 反斜杠路径转正斜杠，便于 JSON 传递"""
    return path.replace("\\", "/")


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def read_paper_lines(path):
    """读取论文文件。返回 (行列表, 错误信息)。UTF-8（含BOM）优先，GBK 兜底。"""
    for enc in ("utf-8-sig", "utf-8", "gbk"):
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
        for i, line in enumerate(lines):
            m = NUMBERED_HEADING_RE.match(line)
            if m and in_section(m.group(2), section):
                start_idx, start_level = i, len(m.group(1))
                match_kind = "subsection"
                break
    if start_idx is None:
        return None, None, None, "未找到编号为 %s 的章节标题" % section

    end_idx = len(lines)
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


# ────────────────────────── v2.1：扁平目录解析 ──────────────────────────

def resolve_paper_dir(path):
    """paper_dir 从 draft/ 反推（不得再用 dirname(file_path)）：
    <paper>/draft/draft-vN.md → <paper>；旧扁平形态 <paper>/draft.md → <paper>"""
    d = os.path.dirname(os.path.abspath(path))
    if os.path.basename(d).lower() == "draft":
        d = os.path.dirname(d)
    return d


def draft_rel_path(paper_dir, abs_file):
    """draft 在 config 中的登记路径：相对 paper_dir 的 posix 路径
    （新结构 draft/draft-vN.md；旧扁平结构 draft-vN.md）"""
    return to_posix(os.path.relpath(os.path.abspath(abs_file), paper_dir))


def _dir_has_source(d):
    try:
        for name in os.listdir(d):
            fp = os.path.join(d, name)
            if os.path.isfile(fp) and name.lower().endswith(SOURCE_EXTS):
                return True
    except OSError:
        pass
    return False


def root_source_files(paper_dir):
    """论文根目录的源文件清单（SOURCE_EXTS；目录不计）"""
    found = []
    try:
        for name in sorted(os.listdir(paper_dir)):
            fp = os.path.join(paper_dir, name)
            if os.path.isfile(fp) and name.lower().endswith(SOURCE_EXTS):
                found.append(name)
    except OSError:
        pass
    return found


def detect_v1_form(paper_dir):
    """v1 二选一检测（§十一 第12条）：
    根单文件源 → "."；v1/ 目录（含源文件，多文件 LaTeX 整包）→ "v1"；
    两者并存 → 错误。返回 (form|None, root_sources, error|None)"""
    root_sources = root_source_files(paper_dir)
    v1_dir = os.path.join(paper_dir, "v1")
    has_v1_dir = os.path.isdir(v1_dir) and _dir_has_source(v1_dir)
    if root_sources and has_v1_dir:
        return None, root_sources, (
            "v1 双形态并存：根目录源文件 [%s] 与 v1/ 目录同时存在。"
            "约定二选一：单文件源留根目录（source_root=\".\"），"
            "或多文件工程整体入 v1/（source_root=\"v1\"）；请移除其一后重试"
            % ", ".join(root_sources))
    if has_v1_dir:
        return "v1", root_sources, None
    if root_sources:
        return ".", root_sources, None
    return None, root_sources, None      # 无源文件（纯 draft 审查），不报错


def resolve_source_root(paper_dir, version_no, v1_form, recorded):
    """source_root 取值："." | "v1" | "vN"（旧 "sources/vN" 仅在目录仍在时只读兼容）"""
    if version_no == 1:
        return v1_form or recorded or "."
    new = "v%d" % version_no
    legacy = "sources/v%d" % version_no
    if os.path.isdir(os.path.join(paper_dir, new)):
        return new
    if os.path.isdir(os.path.join(paper_dir, *legacy.split("/"))):
        return legacy                    # 未迁移的 v2.0 工作空间，只读兼容
    if recorded and not recorded.startswith("sources/"):
        return recorded
    return new


def ensure_index(paper_dir):
    """工程根 INDEX.md 不存在时创建骨架。返回 (path|None, warning|None)"""
    project_root = os.path.dirname(paper_dir)
    path = os.path.join(project_root, "INDEX.md")
    if os.path.exists(path):
        return path, None
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(INDEX_HEADER)
        return path, None
    except OSError as e:
        return None, "INDEX.md 创建失败（不阻塞）: %s" % e


# ────────────────────────── v2.0：版本/轮次/config ──────────────────────────

def parse_version(path):
    """从文件名解析版本号：draft-vN.md → N；无版本后缀 → 1"""
    m = VERSION_FILE_RE.search(os.path.basename(path))
    return int(m.group(1)) if m else 1


def load_config(config_path):
    if not os.path.isfile(config_path):
        return None
    try:
        with open(config_path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        print("警告：config.json 损坏（%s），按无配置处理" % e, file=sys.stderr)
        return None


def doctype_hints(lines):
    """自动检测线索：疑似非完整论文的结构信号（§八 8.2-1）"""
    text = "\n".join(lines[:400]).lower()
    hints = []
    if not re.search(r"^#{1,6}\s*(摘要|abstract)", "\n".join(lines[:200]),
                     re.IGNORECASE | re.MULTILINE):
        hints.append("未检测到「摘要」节")
    if "参考文献" not in text and "references" not in text:
        hints.append("未检测到「参考文献」节")
    if not re.search(r"(实验|数据集|evaluation|experiment)", text):
        hints.append("未检测到实验/数据节 → 疑似非完整论文（proposal/征集/报告类）")
    return hints


def criteria_for(doctype):
    if doctype is None:
        return None
    if doctype.startswith("other:"):
        crit = dict(OTHER_CRITERIA)
        crit["description"] = doctype.split(":", 1)[1]
        return crit
    return DOCTYPE_CRITERIA.get(doctype)


def _r1_cutoff_ts(config):
    """r1 开跑时间（epoch 秒）；无记录返回 None（条目7 护栏修正用）"""
    started = ((config.get("rounds") or {}).get("r1") or {}).get("started_at")
    if not started:
        return None
    try:
        return datetime.datetime.fromisoformat(started).timestamp()
    except (ValueError, TypeError):
        return None


def unregistered_sources(paper_dir, config):
    """覆盖护栏：根目录出现未登记进 config.versions 的源文件。

    排除（§十一 第7/12条）：
      - 已登记文件（versions 各版本的 draft/response/source_file 基名）
      - 约定目录 v1/ vN/ draft/ response/ reports/ figures/ media/（目录不计）
      - mtime 早于 r1 开跑时间的文件（v1 既有源，防误报）
    """
    known = set()
    for v in (config.get("versions") or {}).values():
        for key in ("draft", "response", "source_file"):
            if v.get(key):
                known.add(os.path.basename(v[key]))
    cutoff = _r1_cutoff_ts(config)
    found = []
    try:
        names = sorted(os.listdir(paper_dir))
    except OSError:
        return found
    for name in names:
        if name in IGNORED_DIRS or VN_DIR_RE.match(name):
            continue
        fp = os.path.join(paper_dir, name)
        if not (os.path.isfile(fp) and name.lower().endswith(SOURCE_EXTS)):
            continue
        if name in known:
            continue
        if cutoff is not None:
            try:
                if os.path.getmtime(fp) <= cutoff:
                    continue
            except OSError:
                pass
        found.append(name)
    return found


def infer_format(source):
    """--format 缺省推断（与 conversion_audit.py 口径一致）：
    目录→tex；.tex→tex；.docx/.doc→docx；.pdf/.txt→pdf"""
    if source is None:
        return None
    if os.path.isdir(source):
        return "tex"
    ext = os.path.splitext(source)[1].lower()
    return {".tex": "tex", ".docx": "docx", ".doc": "docx",
            ".pdf": "pdf", ".txt": "pdf"}.get(ext)


def make_estimate(lines_count, doctype, quick, re_review, expert, panel_full):
    """Step 0 成本与模式预估（§十 ⑪；历史均值：892行期刊稿 vs 4507行学位论文）"""
    scale = max(0.5, min(3.0, lines_count / 900.0))
    if quick:
        seats = 2
        stage1_min = round(15 * scale)
        stage2_min = round(8 * scale)
        mode = "quick"
    else:
        seats = 7
        stage1_min = round(40 * scale)
        stage2_min = round(15 * scale)
        mode = "full"
    if re_review:
        stage1_min = max(10, round(stage1_min * 0.6))   # 席位裁剪 + diff 驱动
    agents = {
        "stage1_panel": (seats + 1 + (0 if quick else 1)) if not quick else 0,
        "stage2_deai": 0 if quick else 5,
        "expert_reconcile": 1 if expert else 0,
    }
    if quick:
        agents["stage1_panel"] = 0   # 单实例扮演，不派代理
    total_agents = sum(agents.values())
    token_scale = ["~1M", "~2-4M", "~4-8M"][0 if scale < 0.8 else (1 if scale < 2 else 2)]
    quick_types = ("extended-abstract", "section-draft", "problem-collection")
    if quick:
        recommendation = "已按用户指定 --quick 执行"
    elif lines_count <= 500 and (doctype in quick_types):
        recommendation = "稿件较短且类型为 %s，建议 --quick（用户可改判）" % doctype
    else:
        recommendation = "建议正式模式（七席面板）"
    return {
        "mode": mode,
        "seats": seats,
        "panel": "full" if panel_full else ("quick-2seat" if quick else "default"),
        "agents": agents,
        "total_agents": total_agents,
        "est_wall_clock_min": {"stage1": stage1_min, "stage2": stage2_min,
                               "total": stage1_min + stage2_min},
        "est_tokens": token_scale,
        "scale_factor": round(scale, 2),
        "recommendation": recommendation,
    }


def parse_doctype(raw):
    """校验 --doctype 取值；返回 (doctype 或 None, 错误信息或 None)"""
    if raw is None:
        return None, None
    dt = raw.strip()
    if dt.startswith("other:"):
        if len(dt) <= len("other:"):
            return None, "--doctype other: 后必须附描述，如 other:立项建议书"
        return dt, None
    if dt not in DOCTYPES:
        return None, ("--doctype 非法取值 %r；合法：%s 或 other:<描述>"
                      % (dt, "|".join(DOCTYPES)))
    return dt, None


def main():
    parser = argparse.ArgumentParser(
        prog="setup_env.py",
        description="paper-review 环境初始化（v2.1 扁平目录）：校验文件、定位章节、"
                    "paper_dir 从 draft/ 反推、v1 二选一检测、版本/轮次解析与 r<N>/ "
                    "产物路由、config.json 维护（layout=flat-v2.1）、--doctype 准则绑定、"
                    "覆盖护栏、--source/--format 透传、成本预估，输出 JSON。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--file", metavar="PATH", required=True,
                        help="待审查论文文件路径（Markdown：<paper>/draft/draft.md=v1，"
                             "draft/draft-vN.md=vN；旧扁平根目录形态只读兼容）")
    parser.add_argument("--section", metavar="X.Y", default=None,
                        help="限定审查范围到某小节（如 1.1，自动覆盖其子小节）")
    parser.add_argument("--rounds", metavar="N", type=int, default=3,
                        help="收敛循环最大轮数")
    parser.add_argument("--source", metavar="PATH", default=None,
                        help="源文件/目录（tex 目录 / .docx / .pdf / pdf提取.txt），"
                             "登记进 config 并透传 conversion_audit / anchor_map（三轨定位）")
    parser.add_argument("--format", metavar="FMT", choices=["tex", "docx", "pdf"],
                        default=None,
                        help="源格式（缺省按 --source 扩展名推断：目录→tex，.tex→tex，"
                             ".docx→docx，.pdf/.txt→pdf）")
    parser.add_argument("--doctype", metavar="TYPE", default=None,
                        help="稿件类型：full-paper|thesis|proposal|problem-collection|"
                             "extended-abstract|technical-report|section-draft|review|other:<描述>")
    parser.add_argument("--focus", metavar="STAGE", choices=["panel", "de-ai"],
                        default=None,
                        help="只执行指定阶段：panel（阶段1）/ de-ai（阶段2），"
                             "Step 0 记录后由 SKILL 路由，之后直达 Step 6")
    parser.add_argument("--quick", action="store_true",
                        help="快速模式（S1+S6 两席单实例，跳过讨论轮）")
    parser.add_argument("--no-fix", action="store_true",
                        help="只审查报告，不修改稿件（跳过阶段4/5）")
    parser.add_argument("--re-review", action="store_true",
                        help="核验式复审模式（见 references/re-review-protocol.md）")
    parser.add_argument("--response", metavar="FILE", default=None,
                        help="随修订版提交的作者回复信路径（<paper>/response/response-vN.md）")
    parser.add_argument("--expert-comments", metavar="FILE", default=None,
                        help="外部专家意见文件（md 或 docx，docx 由 expert_reconcile.py "
                             "原生解析），启用阶段1后对账")
    parser.add_argument("--panel", choices=["default", "full"], default="default",
                        help="复审时面板范围：default=裁剪席位，full=七席全开")
    parser.add_argument("--new-run", action="store_true",
                        help="对同一版本强制开启新轮次 r<N+1>（全量重审）")
    args = parser.parse_args()

    if args.rounds < 1:
        print("错误：--rounds 必须 >= 1", file=sys.stderr)
        sys.exit(2)
    doctype_arg, dt_err = parse_doctype(args.doctype)
    if dt_err:
        print("错误：%s" % dt_err, file=sys.stderr)
        sys.exit(2)
    if args.response and not os.path.isfile(args.response):
        print("错误：--response 文件不存在: %s" % args.response, file=sys.stderr)
        sys.exit(2)
    if args.expert_comments:
        if not os.path.isfile(args.expert_comments):
            print("错误：--expert-comments 文件不存在: %s" % args.expert_comments,
                  file=sys.stderr)
            sys.exit(2)
        if (args.expert_comments.lower().endswith(".docx")
                and not zipfile.is_zipfile(args.expert_comments)):
            print("错误：--expert-comments 不是有效 docx（zip）文件: %s；"
                  "请确认为 Word 文档或先转换为 md 文本" % args.expert_comments,
                  file=sys.stderr)
            sys.exit(2)
    if args.source and not os.path.exists(args.source):
        print("错误：--source 不存在: %s" % args.source, file=sys.stderr)
        sys.exit(2)
    if args.format and not args.source:
        print("错误：--format 须与 --source 同时提供", file=sys.stderr)
        sys.exit(2)

    section = args.section.strip().lstrip("§").rstrip(".") if args.section else None
    result = {
        "file_path": None,
        "section": section,
        "section_range": None,
        "review_dir": None,
        "run_dir": None,
        "rounds_max": args.rounds,
        "success": False,
    }
    problems = []

    path = args.file
    lines = None
    if not os.path.exists(path):
        problems.append("论文文件不存在: %s" % path)
    elif not os.path.isfile(path):
        problems.append("论文路径不是文件: %s" % path)
    elif path.lower().endswith(NON_MD_INPUT_EXTS):
        problems.append(
            "输入不是 Markdown（%s）：请先按 SKILL Step 0.0 输入类型分派转换为 "
            "<paper>/draft/draft.md（转换命令与参数写入 conversion_audit.md）后再初始化"
            % os.path.splitext(path)[1])
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
        paper_dir = resolve_paper_dir(path)
        review_dir = os.path.join(paper_dir, ".review")
        config_path = os.path.join(review_dir, "config.json")
        version_no = parse_version(path)
        version = "v%d" % version_no
        config = load_config(config_path)

        # ── v1 二选一检测（并存即报错，§十一 第12条）──
        v1_form, root_sources, form_err = detect_v1_form(paper_dir)
        if form_err:
            problems.append(form_err)

    if not problems:
        # ── 轮次判定 ──
        if config is None:
            round_no = 1
            config = {
                "schema": 2,
                "paper_dir": to_posix(paper_dir),
                "doctype": None,
                "versions": {},
                "current_version": version,
                "rounds": {},
                "current_round": "r1",
                "exemptions": [], "withdrawals": [], "adjudications": [],
            }
            # 旧结构（sources/ 仍在）不盖 flat-v2.1 章，供 migrate_layout 识别
            if not os.path.isdir(os.path.join(paper_dir, "sources")):
                config["layout"] = LAYOUT
        else:
            cur_v = config.get("current_version") or "v1"
            cur_no = int(cur_v.lstrip("v") or 1)
            existing_rounds = config.get("rounds") or {}
            max_round = max([int(k.lstrip("r")) for k in existing_rounds] or [0])
            if version_no > cur_no or args.new_run:
                round_no = max_round + 1
                config["current_version"] = version
            else:
                round_no = max(1, max_round) if existing_rounds else max_round + 1
                if version_no < cur_no:
                    print("警告：文件版本 %s 低于 config 记录 %s，按当前轮次更新处理"
                          % (version, cur_v), file=sys.stderr)
            # 旧结构（sources/ 已不存在）才盖 flat-v2.1 章，供 migrate_layout 识别
            if not os.path.isdir(os.path.join(paper_dir, "sources")):
                config["layout"] = LAYOUT
            config["paper_dir"] = to_posix(paper_dir)
        round_id = "r%d" % round_no

        # ── versions / rounds 映射登记 ──
        versions = config.setdefault("versions", {})
        recorded = (versions.get(version) or {}).get("source_root")
        v_entry = versions.setdefault(version, {"source_root": None,
                                                "draft": None, "response": None})
        v_entry["source_root"] = resolve_source_root(
            paper_dir, version_no, v1_form, recorded)
        v_entry["draft"] = draft_rel_path(paper_dir, path)
        # v1 源登记（条目7 护栏修正：根单文件源可无歧义时记名，防误报 untracked）
        if version_no == 1 and v1_form == "." and len(root_sources) == 1:
            v_entry["source_file"] = root_sources[0]
        if args.response:
            v_entry["response"] = draft_rel_path(paper_dir, args.response)
        if args.source:
            src_abs = os.path.abspath(args.source)
            v_entry["source"] = to_posix(src_abs)
            v_entry["source_format"] = args.format or infer_format(args.source)
            if os.path.isfile(src_abs):
                v_entry["source_file"] = os.path.basename(src_abs)
        rounds = config.setdefault("rounds", {})
        r_entry = rounds.setdefault(round_id, {"version": version})
        r_entry.setdefault("started_at", now_iso())
        if args.re_review:
            r_entry["re_review"] = True
        if args.focus:
            r_entry["focus"] = args.focus
        if args.no_fix:
            r_entry["no_fix"] = True
        config["current_round"] = round_id

        # ── doctype：显式声明 > config 继承 > 待确认 ──
        if doctype_arg:
            config["doctype"] = doctype_arg
        doctype = config.get("doctype")
        needs_dt = False
        hints = []
        if doctype is None:
            needs_dt = True
            hints = doctype_hints(lines or [])
        else:
            config.setdefault("exemptions", [])
        result["doctype"] = doctype
        result["needs_doctype_confirmation"] = needs_dt
        if hints:
            result["doctype_hints"] = hints
        crit = criteria_for(doctype)
        if crit is not None:
            result["applied_criteria"] = {
                "required": [{"item": i, "severity_if_missing": s} for i, s in crit["required"]],
                "exempt": crit["exempt"],
                "substituted": [{"from": a, "to": b} for a, b in crit["substituted"]],
                "compliance": crit["compliance"],
            }
            if crit.get("note"):
                result["applied_criteria"]["note"] = crit["note"]
            if crit.get("description"):
                result["applied_criteria"]["description"] = crit["description"]

        # ── 覆盖护栏（§九规则2 + 条目7 修正）──
        needs_src = False
        untracked = []
        if rounds and len(rounds) >= 1 and not args.new_run:
            untracked = unregistered_sources(paper_dir, config)
            needs_src = bool(untracked)
        result["needs_source_confirmation"] = needs_src
        if untracked:
            result["untracked_sources"] = untracked

        # ── 其它 v2 输入 ──
        result["paper_dir"] = to_posix(paper_dir)
        result["layout"] = config.get("layout")
        result["version"] = version
        result["round"] = round_id
        result["re_review"] = bool(args.re_review)
        result["focus"] = args.focus
        result["no_fix"] = bool(args.no_fix)
        result["source"] = (to_posix(os.path.abspath(args.source))
                            if args.source else None)
        result["source_format"] = (args.format or infer_format(args.source)) \
            if args.source else None
        result["expert_comments"] = (to_posix(os.path.abspath(args.expert_comments))
                                     if args.expert_comments else None)
        if args.expert_comments:
            config["expert_comments"] = result["expert_comments"]

        # ── 工程根 INDEX.md（§十一 第5/19条：缺失时创建骨架）──
        index_path, index_warn = ensure_index(paper_dir)
        if index_warn:
            print("警告：%s" % index_warn, file=sys.stderr)
        result["index_path"] = to_posix(index_path) if index_path else None

        # ── 成本与模式预估（§十 ⑪）──
        result["estimate"] = make_estimate(
            len(lines or []), doctype, args.quick, bool(args.re_review),
            bool(args.expert_comments), args.panel == "full")

        # ── 目录与产物路由：r<N>/ ──
        run_dir = os.path.join(review_dir, round_id)
        try:
            os.makedirs(run_dir, exist_ok=True)
            for name in LOG_FILES:
                lp = os.path.join(run_dir, name)
                if not os.path.exists(lp):
                    with open(lp, "w", encoding="utf-8", newline="\n") as f:
                        f.write("")
            with open(config_path, "w", encoding="utf-8", newline="\n") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            result["review_dir"] = to_posix(review_dir) + "/"
            result["run_dir"] = to_posix(run_dir) + "/"
            result["config_path"] = to_posix(config_path)
        except OSError as e:
            problems.append("创建 .review/r<N>/ 目录或写入 config.json 失败: %s" % e)

    result["success"] = not problems
    if problems:
        result["problems"] = problems
    print(json.dumps(result, ensure_ascii=False, indent=2))
    for p in problems:
        print("问题：%s" % p, file=sys.stderr)
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
