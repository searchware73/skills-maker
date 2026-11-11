#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""migrate_layout.py — paper-review v2.1 存量工作空间目录扁平化迁移

把 v2.0 时代的「papers/<name>/ + output/ 平铺」工作空间迁移为 v2.1 扁平结构
（§十一 第12条）：每篇论文一目录直接放工程根，源/草稿/版本/反馈/过程/报告自包含。

  迁移前                            迁移后
  <root>/papers/<name>/             <root>/<name>/
  <root>/papers/<name>/sources/vK/  <root>/<name>/vK/
  <root>/papers/<name>/draft*.md    <root>/<name>/draft/
  <root>/papers/<name>/response*.md <root>/<name>/response/
  <root>/output/<name>-审阅报告.md  <root>/<name>/reports/r1-审阅报告.md
  <root>/output/<name>-rN-*.md      <root>/<name>/reports/rN-复审报告.md
  <root>/papers/INDEX.md            <root>/INDEX.md

原则：
  - **人工判定项写入 report，绝不猜**：LaTeX 工程整体入 v1/、v1 双形态并存、
    media|figures 图目录收敛到 draft/figures/、非标准报告名（轮次号需反推）、
    output 内疑似外部意见 docx 等 → 只列待确认项与建议，不动文件
  - **幂等**：重复 --apply 不产生二次移动（目标存在即跳过；papers/ output/
    已消失则整体 no-op）
  - **可回滚**：--apply 把每步操作记入 <root>/.migrate-layout/manifest.json
    （文件改写先备份），--rollback 按 manifest 逆序复原
  - **只移动不删除**：迁移后 papers/ → papers.bak/、output/ → output.bak/
    保留，直至用户确认后再手工删除（目标工作空间可能不是 git 仓库）
  - config.json / chain.md / RESUME.md 中的旧路径口径同步改写
    （source_root "sources/vK"→"vK"、draft/response 加目录前缀、
    layout="flat-v2.1"、paper_dir 更新）

用法：
  python migrate_layout.py --root <工作空间根>            # 缺省 dry-run：只输出计划
  python migrate_layout.py --root <root> --dry-run [--report FILE]
  python migrate_layout.py --root <root> --apply   [--report FILE]
  python migrate_layout.py --root <root> --rollback

  --root      工作空间根目录（含 papers/ 与 output/；或已迁移后的扁平根）
  --dry-run   扫描并输出迁移计划与人工判定待确认清单，零文件系统改动（缺省）
  --apply     实际执行迁移；操作记入 manifest，支持 --rollback
  --rollback  按 manifest 逆序恢复到迁移前状态（应在开始新审阅之前执行）
  --report    将 markdown 报告写入 FILE（计划/待确认项/校验命令/备份说明）

stdout（JSON）：
  {"success": true, "mode": "dry-run|apply|rollback", "root": "...",
   "scanned": {"papers": N, "output_files": M},
   "moves": [{"from": "...", "to": "..."}], "rewrites": ["<path>"],
   "pending": [{"category": "...", "paper": "...", "item": "...",
                "recommendation": "..."}],
   "notes": [...], "report": null|"...", "manifest": null|"...",
   "moved": N, "rewritten": N}        ← 仅 --apply
   {"restored": N}                    ← 仅 --rollback

pending.category 枚举（前 5 类即备忘第12条「存量实测清单」的 5 类人工判定）：
  nonstandard_report  output 报告名非标准 → 轮次号需从文件名或 chain.md 反推
  latex_project       完整 LaTeX 工程 → 建议整体入 v1/（无关文件不入检测视野）
  media_dir           pandoc media/ 图目录 → 建议收敛 draft/figures/ 并改写引用
  figures_dir         PyMuPDF figures/ 图目录 → 建议收敛 draft/figures/
  output_non_report   output 内非报告文件（外部意见/过程产物）→ 确认归属后入
                      response/、reports/ 或 .review/
  v1_dual_form        根单文件源与 v1/ 目录并存 → 二选一
  paper_dir_conflict  工程根已存在同名目录 → 该篇跳过，人工合并
  index_conflict      工程根已有 INDEX.md → papers/INDEX.md 需人工合并
  config_broken       config.json 解析失败 → 人工修复

退出码：0=成功；1=运行时失败（manifest 已记录已执行项，可 --rollback 或重跑）；
2=参数错误（--root 不存在 / 无 manifest 却 --rollback 等）。
"""
import argparse
import datetime
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

LAYOUT = "flat-v2.1"
STATE_DIR = ".migrate-layout"
SOURCE_EXTS = (".docx", ".pdf", ".tex", ".zip", ".doc")
SOURCES_V_RE = re.compile(r"^v\d+$")
SOURCES_PATH_RE = re.compile(r"sources/(v\d+)")

# output 报告名自动识别（严格模式，论文名必须命中 papers/ 目录名）
REPORT_AUTO_PATTERNS = [
    (re.compile(r"^(?P<paper>.+)-r(?P<n>\d+)-re-review-report\.md$", re.IGNORECASE),
     "r{n}-复审报告.md"),
    (re.compile(r"^(?P<paper>.+)-r(?P<n>\d+)-审阅报告\.md$"),
     "r{n}-审阅报告.md"),
    (re.compile(r"^(?P<paper>.+)-r(?P<n>\d+)-复审报告\.md$"),
     "r{n}-复审报告.md"),
    (re.compile(r"^(?P<paper>.+)-审阅报告\.md$"),      # 无轮次号 → 首轮
     "r{n}-审阅报告.md"),
]
COMPREHENSIVE_RE = re.compile(r"^(?P<paper>.+)-综合审阅意见\.(md|docx)$")
REPORT_LIKE_RE = re.compile(r"(审阅报告|复审报告|re-review-report|综合审阅意见)",
                            re.IGNORECASE)

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def to_posix(path):
    return path.replace("\\", "/")


def pabs(path):
    return to_posix(os.path.abspath(path))


def fail(msg, code=2, extra=None):
    print("错误：%s" % msg, file=sys.stderr)
    out = {"success": False, "error": msg}
    if extra:
        out.update(extra)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(code)


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def list_top(path):
    try:
        return sorted(os.listdir(path))
    except OSError:
        return []


def read_text(path):
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read(), None
        except UnicodeDecodeError:
            continue
        except OSError as e:
            return None, str(e)
    return None, "无法解码（utf-8-sig/utf-8/gbk）: %s" % path


# ────────────────────────── 扫描与计划（dry-run 零改动） ──────────────────────────

class Planner(object):
    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.actions = []        # 有序执行计划
        self.pending = []        # 人工判定项（只报告，不动文件）
        self.notes = []
        self.skipped = set()     # paper_dir_conflict 跳过的论文名
        self.scanned = {"papers": 0, "output_files": 0}

    # -- 计划原语 --
    def move(self, src, dst):
        self.actions.append({"op": "move", "from": pabs(src), "to": pabs(dst),
                             "_src": src, "_dst": dst})

    def rewrite(self, path, content):
        self.actions.append({"op": "rewrite", "path": pabs(path),
                             "content": content, "_path": path})

    def rmdir_if_empty(self, path):
        self.actions.append({"op": "rmdir", "path": pabs(path), "_path": path})

    def add_pending(self, category, paper, item, recommendation):
        self.pending.append({"category": category, "paper": paper,
                             "item": to_posix(item),
                             "recommendation": recommendation})

    # -- 主扫描 --
    def scan(self):
        papers_dir = os.path.join(self.root, "papers")
        output_dir = os.path.join(self.root, "output")
        has_papers = os.path.isdir(papers_dir)
        has_output = os.path.isdir(output_dir)
        if not has_papers and not has_output:
            self.notes.append(
                "未发现 papers/ 与 output/：已是扁平结构（flat-v2.1）或无需迁移")
            return self

        paper_names = []
        if has_papers:
            for name in list_top(papers_dir):
                p = os.path.join(papers_dir, name)
                if os.path.isdir(p):
                    paper_names.append(name)
                    self.plan_paper(p, name)
                elif name != "INDEX.md":
                    self.add_pending(
                        "output_non_report", None, p,
                        "papers/ 下的散落文件：请人工确认归属后移入对应论文目录")
            self.plan_index(papers_dir)
        if has_output:
            self.plan_output(output_dir, paper_names)

        # 备份保留：papers/ → papers.bak/，output/ → output.bak/（只移动不删除）
        for d in (("papers", "papers.bak"), ("output", "output.bak")):
            src = os.path.join(self.root, d[0])
            dst = os.path.join(self.root, d[1])
            if os.path.isdir(src):
                if os.path.exists(dst):
                    self.notes.append(
                        "%s 已存在，%s/ 保留原名不重命名（人工核对后处理）" % (pabs(dst), d[0]))
                else:
                    self.move(src, dst)
        return self

    # -- 单篇论文 --
    def plan_paper(self, src, name):
        self.scanned["papers"] += 1
        dst = os.path.join(self.root, name)
        if os.path.exists(dst):
            self.skipped.add(name)
            self.add_pending(
                "paper_dir_conflict", name, src,
                "工程根已存在同名目录 %s：该篇跳过迁移，请人工合并后重跑" % pabs(dst))
            return
        # 1) 整目录移至工程根（§十一 第12条 步骤2）
        self.move(src, dst)
        # 2) 内部规范化：sources/vK → vK；根 draft*/response* → draft/、response/
        self.plan_internal(src, dst)
        # 3) config/chain/RESUME 路径口径改写
        self.plan_review_rewrites(src, dst, name)
        # 4) 人工判定项检测（基于迁移前状态，路径按迁移后报告）
        self.detect_judgment_items(src, dst, name)

    def plan_internal(self, src, dst):
        """论文整目录移动之后的内部规范化。
        注意：扫描用 src（计划期实际位置），移动路径用 dst（执行期整目录已就位）。"""
        src_sources = os.path.join(src, "sources")
        if os.path.isdir(src_sources):
            residual = False
            for vn in list_top(src_sources):
                sp = os.path.join(src_sources, vn)
                if os.path.isdir(sp) and SOURCES_V_RE.match(vn):
                    self.move(os.path.join(dst, "sources", vn),
                              os.path.join(dst, vn))
                else:
                    residual = True
            if residual:
                self.notes.append("%s/sources/ 含非 vK 内容，保留待人工处理" % pabs(dst))
            else:
                self.rmdir_if_empty(os.path.join(dst, "sources"))
        for fn in list_top(src):
            p = os.path.join(src, fn)
            if not os.path.isfile(p):
                continue
            low = fn.lower()
            if low.startswith("draft") and low.endswith(".md"):
                self.move(os.path.join(dst, fn), os.path.join(dst, "draft", fn))
            elif low.startswith("response") and low.endswith(".md"):
                self.move(os.path.join(dst, fn), os.path.join(dst, "response", fn))

    def plan_review_rewrites(self, src, dst, name):
        review_src = os.path.join(src, ".review")
        if not os.path.isdir(review_src):
            return
        # config.json
        cfg_path = os.path.join(review_src, "config.json")
        if os.path.isfile(cfg_path):
            content, err = read_text(cfg_path)
            if err is not None:
                self.add_pending("config_broken", name, cfg_path,
                                 "config.json 读取失败（%s）：人工修复后重跑" % err)
            else:
                try:
                    cfg = json.loads(content)
                except ValueError as e:
                    cfg = None
                    self.add_pending("config_broken", name, cfg_path,
                                     "config.json 解析失败（%s）：人工修复后重跑" % e)
                if isinstance(cfg, dict):
                    new = self.normalize_config(cfg, dst)
                    if new is not None:
                        self.rewrite(os.path.join(dst, ".review", "config.json"),
                                     json.dumps(new, ensure_ascii=False, indent=2))
        # chain.md / RESUME.md：sources/vK → vK
        for fn in ("chain.md", "RESUME.md"):
            p = os.path.join(review_src, fn)
            if not os.path.isfile(p):
                continue
            content, err = read_text(p)
            if err is not None or content is None:
                continue
            new = SOURCES_PATH_RE.sub(r"\1", content)
            if new != content:
                self.rewrite(os.path.join(dst, ".review", fn), new)

    @staticmethod
    def normalize_config(cfg, paper_dst):
        """source_root "sources/vK"→"vK"、draft/response 加目录前缀、
        paper_dir 更新、layout=flat-v2.1。返回新 dict；无变化返回 None。"""
        new = json.loads(json.dumps(cfg))      # deep copy
        changed = False
        if new.get("paper_dir") != to_posix(paper_dst):
            new["paper_dir"] = to_posix(paper_dst)
            changed = True
        versions = new.get("versions")
        if isinstance(versions, dict):
            for entry in versions.values():
                if not isinstance(entry, dict):
                    continue
                sr = entry.get("source_root")
                if isinstance(sr, str) and sr.startswith("sources/"):
                    entry["source_root"] = sr[len("sources/"):]
                    changed = True
                for key, prefix in (("draft", "draft/"), ("response", "response/")):
                    val = entry.get(key)
                    if isinstance(val, str) and val and "/" not in val:
                        entry[key] = prefix + val
                        changed = True
        if new.get("layout") != LAYOUT:
            new["layout"] = LAYOUT
            changed = True
        return new if changed else None

    def detect_judgment_items(self, src, dst, name):
        """5 类人工判定（§十一 第12条存量实测清单）：只列出，不猜测、不移动"""
        root_files = list_top(src)
        root_sources = [f for f in root_files
                        if os.path.isfile(os.path.join(src, f))
                        and f.lower().endswith(SOURCE_EXTS)]
        # ① 完整 LaTeX 工程 → 建议整体入 v1/
        if self._has_tex_project(src):
            self.add_pending(
                "latex_project", name, dst,
                "检测到 LaTeX 工程（.tex/子目录）：建议将全部工程文件整体移入 v1/ "
                "（source_root=\"v1\"）；根目录 README/LICENSE/_config.yml 等无关文件"
                "不属于源，不影响 v1 二选一检测，可留根或删除")
        # ② v1 双形态并存
        v1_dir = os.path.join(src, "v1")
        v1_has_src = os.path.isdir(v1_dir) and any(
            f.lower().endswith(SOURCE_EXTS)
            for f in list_top(v1_dir)
            if os.path.isfile(os.path.join(v1_dir, f)))
        if root_sources and v1_has_src:
            self.add_pending(
                "v1_dual_form", name, dst,
                "根目录源文件 [%s] 与 v1/ 并存：约定二选一（单文件留根 source_root=\".\"，"
                "或多文件工程整体入 v1/ source_root=\"v1\"），请人工裁决"
                % ", ".join(root_sources))
        # ③ pandoc media/ 图目录（docx 转换产物）
        if os.path.isdir(os.path.join(src, "media")):
            self.add_pending(
                "media_dir", name, os.path.join(dst, "media"),
                "检测到 pandoc 提取的 media/ 图目录：建议移入 draft/figures/ 并同步改写 "
                "draft/*.md 内图片相对路径（media/xxx → figures/xxx）；脚本不自动改写正文")
        # ④ PyMuPDF figures/ 图目录（PDF 转换产物）
        if os.path.isdir(os.path.join(src, "figures")):
            self.add_pending(
                "figures_dir", name, os.path.join(dst, "figures"),
                "检测到 PyMuPDF 提取的 figures/ 图目录：建议移入 draft/figures/"
                "（draft/*.md 内 figures/xxx 相对引用随 draft.md 同移后仍有效）；"
                "脚本不自动改写正文")

    def _has_tex_project(self, src):
        """递归查 .tex（排除 .review/ draft/ vN/），命中即视为 LaTeX 工程"""
        for root, dirs, files in os.walk(src):
            dirs[:] = [d for d in dirs
                       if d != ".review" and d != "draft"
                       and not SOURCES_V_RE.match(d)]
            for fn in files:
                if fn.lower().endswith(".tex"):
                    return True
        return False

    # -- INDEX 与 output --
    def plan_index(self, papers_dir):
        idx_src = os.path.join(papers_dir, "INDEX.md")
        if not os.path.isfile(idx_src):
            return
        idx_dst = os.path.join(self.root, "INDEX.md")
        if os.path.exists(idx_dst):
            self.add_pending(
                "index_conflict", None, idx_src,
                "工程根已有 INDEX.md：papers/INDEX.md 需人工合并（一行一篇）后删除")
        else:
            self.move(idx_src, idx_dst)

    def plan_output(self, output_dir, paper_names):
        known = set(paper_names) - self.skipped   # 冲突跳过的论文不接收报告
        for fn in list_top(output_dir):
            p = os.path.join(output_dir, fn)
            if not os.path.isfile(p):
                self.add_pending("output_non_report", None, p,
                                 "output/ 下的子目录：请人工确认归属")
                continue
            self.scanned["output_files"] += 1
            dest = self.classify_output(fn, known)
            if dest is None:
                continue                       # 已记 pending
            paper, new_name = dest
            if paper not in known:
                self.add_pending(
                    "nonstandard_report", paper, p,
                    "无法归属到已知论文目录（papers/ 中无 %s）：请人工确认归属" % paper)
                continue
            self.move(p, os.path.join(self.root, paper, "reports", new_name))

    def classify_output(self, fn, known):
        """返回 (paper, 新文件名) 或 None（已记 pending/notes）。
        口径：流水线交付报告一律 .md（综合审阅意见可为 .docx，备忘第12条存量清单）；
        其余非 .md 视为外部专家意见/杂物 → 只列待确认，不猜归属。"""
        out_path = os.path.join(self.root, "output", fn)
        m = COMPREHENSIVE_RE.match(fn)
        if m and m.group("paper") in known:
            # 交付报告（综合审阅意见 md/docx 双形态）→ reports/，轮次号未标注保留原名
            paper = m.group("paper")
            self.notes.append(
                "output/%s → %s/reports/（保留原名；轮次号确认后可人工改名 rN-%s）"
                % (fn, paper, fn))
            return paper, fn
        for pat, tpl in REPORT_AUTO_PATTERNS:
            m = pat.match(fn)
            if m:
                paper = m.group("paper")
                n = m.groupdict().get("n") or "1"      # 无轮次组 → 首轮
                if paper in known:
                    return paper, tpl.format(n=n)
                self.add_pending(
                    "nonstandard_report", paper, out_path,
                    "报告名可解析但论文目录 %s 不存在：若为「<论文>-<轮次>」连写变体"
                    "（如 q10-2 即 q10 第 2 轮），请反推轮次号后改名 %s 移入 "
                    "<paper>/reports/；脚本不猜测" % (paper, tpl.format(n="N")))
                return None
        if not fn.lower().endswith(".md"):
            self.add_pending(
                "output_non_report", None, out_path,
                "output 内非 .md 文件（流水线交付报告仅 .md）：疑似外部专家意见，"
                "人工确认归属后移入 <paper>/response/expert-*.md；脚本不猜测")
            return None
        stem = os.path.splitext(fn)[0]
        if REPORT_LIKE_RE.search(stem):
            self.add_pending(
                "nonstandard_report", None, out_path,
                "报告名非标准（如 <name>-1-复审报告）：轮次号需从文件名或 chain.md "
                "反推后移入 <paper>/reports/rN-复审报告.md；脚本不猜测")
        else:
            self.add_pending(
                "output_non_report", None, out_path,
                "output 内非报告文件（过程产物或外部意见）：人工确认归属后移入 "
                "<paper>/response/（意见）、reports/（交付报告）或 .review/（过程产物）；"
                "脚本不猜测")
        return None


# ────────────────────────── --apply 执行（manifest 逐步落盘） ──────────────────────────

class Manifest(object):
    def __init__(self, root):
        self.dir = os.path.join(root, STATE_DIR)
        self.path = os.path.join(self.dir, "manifest.json")
        self.backups = os.path.join(self.dir, "backups")
        self.data = {"version": 1, "root": pabs(root), "created_at": now_iso(),
                     "rolled_back": False, "entries": []}

    def load(self):
        if not os.path.isfile(self.path):
            return False
        content, err = read_text(self.path)
        if err is not None or content is None:
            return False
        try:
            data = json.loads(content)
        except ValueError:
            return False
        if isinstance(data, dict) and isinstance(data.get("entries"), list):
            self.data = data
            return True
        return False

    def archive_if_rolled_back(self):
        """上一份 manifest 已回滚 → 归档后另起新账"""
        if self.data.get("rolled_back") and self.data.get("entries"):
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            arc = os.path.join(self.dir, "manifest-%s.json" % stamp)
            os.makedirs(self.dir, exist_ok=True)
            with open(arc, "w", encoding="utf-8", newline="\n") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            self.data = {"version": 1, "root": self.data.get("root"),
                         "created_at": now_iso(), "rolled_back": False,
                         "entries": []}

    def add(self, entry):
        os.makedirs(self.dir, exist_ok=True)
        self.data["entries"].append(entry)
        self.save()

    def save(self):
        os.makedirs(self.dir, exist_ok=True)
        with open(self.path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)


def die_progress(msg, executed):
    print("错误：%s" % msg, file=sys.stderr)
    print(json.dumps({
        "success": False, "mode": "apply", "error": msg, "executed": executed,
        "note": "manifest 已记录已执行项：可 --rollback 复原，或修复后重跑 --apply（幂等）",
    }, ensure_ascii=False, indent=2))
    sys.exit(1)


def do_move(entry, manifest, stats):
    src, dst = entry["_src"], entry["_dst"]
    if os.path.exists(dst):
        if not os.path.exists(src):
            return                            # 已迁移（幂等重跑）
        manifest.add({"op": "note", "text": "目标已存在，跳过：%s → %s"
                      % (pabs(src), pabs(dst))})
        return
    if not os.path.exists(src):
        manifest.add({"op": "note", "text": "源不存在，跳过：%s" % pabs(src)})
        return
    # 记录新建的父目录（rollback 时自底向上清理空目录）
    parent = os.path.dirname(dst)
    new_dirs = []
    probe = parent
    while probe and not os.path.isdir(probe):
        new_dirs.append(probe)
        probe = os.path.dirname(probe)
    for d in reversed(new_dirs):
        try:
            os.mkdir(d)
            manifest.add({"op": "mkdir", "path": pabs(d)})
        except OSError as e:
            die_progress("创建目录失败：%s（%s）" % (pabs(d), e), stats["moved"])
    try:
        shutil.move(src, dst)
    except (OSError, shutil.Error) as e:
        die_progress("移动失败：%s → %s（%s）" % (pabs(src), pabs(dst), e),
                     stats["moved"])
    manifest.add({"op": "move", "from": pabs(src), "to": pabs(dst)})
    stats["moved"] += 1


def do_rewrite(entry, manifest, stats):
    path = entry["_path"]
    backup_rel = None
    if os.path.isfile(path):
        content, err = read_text(path)
        if err is not None:
            die_progress("改写前读取失败：%s（%s）" % (pabs(path), err), stats["moved"])
        if content == entry["content"]:
            return                            # 内容一致，无需改写（幂等）
        os.makedirs(manifest.backups, exist_ok=True)
        backup_rel = os.path.join(
            manifest.backups, "%03d-%s" % (len(manifest.data["entries"]),
                                           os.path.basename(path)))
        try:
            # 原始字节备份（含 BOM/换行差异），保证 --rollback 逐字节复原
            with open(path, "rb") as fin, open(backup_rel, "wb") as fout:
                fout.write(fin.read())
        except OSError as e:
            die_progress("备份失败：%s（%s）" % (pabs(backup_rel), e), stats["moved"])
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(entry["content"])
    except OSError as e:
        die_progress("写入失败：%s（%s）" % (pabs(path), e), stats["moved"])
    manifest.add({"op": "rewrite", "path": pabs(path),
                  "backup": pabs(backup_rel) if backup_rel else None})
    stats["rewritten"] += 1


def do_rmdir(entry, manifest):
    path = entry["_path"]
    try:
        if os.path.isdir(path) and not os.listdir(path):
            os.rmdir(path)
            manifest.add({"op": "rmdir", "path": pabs(path)})   # 回滚=重建空目录
    except OSError:
        pass


def apply_plan(plan, manifest):
    manifest.archive_if_rolled_back()
    stats = {"moved": 0, "rewritten": 0}
    existing = 0
    if manifest.data["entries"]:
        existing = len(manifest.data["entries"])   # 续跑：追加不清账
    for entry in plan.actions:
        op = entry["op"]
        if op == "move":
            do_move(entry, manifest, stats)
        elif op == "rewrite":
            do_rewrite(entry, manifest, stats)
        elif op == "rmdir":
            do_rmdir(entry, manifest)
    return stats, existing


# ────────────────────────── --rollback ──────────────────────────

def rollback(root, manifest):
    entries = manifest.data.get("entries") or []
    if manifest.data.get("rolled_back"):
        return {"success": True, "mode": "rollback", "root": pabs(root),
                "restored": 0, "notes": ["manifest 已处于回滚状态，无需重复回滚"]}
    restored = 0
    for entry in reversed(entries):
        op = entry.get("op")
        try:
            if op == "move":
                src, dst = entry["to"], entry["from"]      # 逆向
                if os.path.exists(dst) or not os.path.exists(src):
                    continue
                parent = os.path.dirname(dst)
                if parent and not os.path.isdir(parent):
                    os.makedirs(parent, exist_ok=True)
                shutil.move(src, dst)
                restored += 1
            elif op == "rewrite":
                backup = entry.get("backup")
                path = entry["path"]
                if backup and os.path.isfile(backup):
                    with open(backup, "rb") as fin:
                        data = fin.read()
                    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                    with open(path, "wb") as fout:
                        fout.write(data)          # 原始字节复原
                    restored += 1
            elif op == "rmdir":
                os.makedirs(entry["path"], exist_ok=True)   # 被删空目录重建
                restored += 1
            elif op == "create":
                if os.path.isfile(entry["path"]):
                    os.remove(entry["path"])
                    restored += 1
            elif op == "mkdir":
                # 执行期新建的目录：逆序至此其内文件已移回，为空即撤
                # （必须在整目录逆向移动之前就地清理，否则空目录会被带走）
                path = entry["path"]
                if os.path.isdir(path) and not os.listdir(path):
                    os.rmdir(path)
        except OSError as e:
            fail("回滚失败（%s：%s）：%s；manifest 保留，可人工继续"
                 % (op, entry.get("path") or entry.get("to"), e), code=1)
    manifest.data["rolled_back"] = True
    manifest.save()
    return {"success": True, "mode": "rollback", "root": pabs(root),
            "restored": restored,
            "notes": ["已按 manifest 逆序复原；%s/ 备份目录保留至人工确认" % STATE_DIR]}


# ────────────────────────── 报告 ──────────────────────────

PENDING_TITLES = {
    "nonstandard_report": "非标准报告名（轮次号需反推）",
    "latex_project": "完整 LaTeX 工程（建议整体入 v1/）",
    "media_dir": "pandoc media/ 图目录（建议收敛 draft/figures/ 并改写引用）",
    "figures_dir": "PyMuPDF figures/ 图目录（建议收敛 draft/figures/）",
    "output_non_report": "output 内非报告文件（外部意见/过程产物）",
    "v1_dual_form": "v1 双形态并存（二选一）",
    "paper_dir_conflict": "工程根同名目录冲突（该篇跳过）",
    "index_conflict": "INDEX.md 冲突（需人工合并）",
    "config_broken": "config.json 损坏（需人工修复）",
}


def render_report(plan, mode, root):
    lines = [
        "# migrate_layout 迁移报告（%s）" % mode,
        "",
        "- 工作空间根：`%s`" % pabs(root),
        "- 生成时间：%s" % now_iso(),
        "- 扫描：papers/ %d 篇；output/ %d 个文件"
        % (plan.scanned["papers"], plan.scanned["output_files"]),
        "- 自动迁移：移动 %d 项、改写 %d 项；**人工判定 %d 项（未动文件）**"
        % (sum(1 for a in plan.actions if a["op"] == "move"),
           sum(1 for a in plan.actions if a["op"] == "rewrite"),
           len(plan.pending)),
        "",
        "## 自动迁移计划",
        "",
        "| # | 类型 | from | to |",
        "|---|------|------|-----|",
    ]
    i = 0
    for a in plan.actions:
        if a["op"] == "move":
            i += 1
            lines.append("| %d | move | `%s` | `%s` |" % (i, a["from"], a["to"]))
        elif a["op"] == "rewrite":
            i += 1
            lines.append("| %d | rewrite | `%s` | （路径口径改写） |" % (i, a["path"]))
    if not plan.actions:
        lines.append("| — | — | （无自动迁移动作） | — |")
    lines += ["", "## 人工判定项（脚本不猜测，逐项处置后重跑或手工移动）", ""]
    by_cat = {}
    for p in plan.pending:
        by_cat.setdefault(p["category"], []).append(p)
    for cat in sorted(by_cat):
        lines.append("### %s（%d 项）" % (PENDING_TITLES.get(cat, cat), len(by_cat[cat])))
        for p in by_cat[cat]:
            lines.append("- `%s`%s\n  - 建议：%s"
                         % (p["item"],
                            ("（%s）" % p["paper"]) if p["paper"] else "",
                            p["recommendation"]))
        lines.append("")
    if not plan.pending:
        lines += ["（无）", ""]
    if plan.notes:
        lines += ["## 备注", ""] + ["- %s" % n for n in plan.notes] + [""]
    setup = to_posix(os.path.join(SKILL_DIR, "scripts", "setup_env.py"))
    resume = to_posix(os.path.join(SKILL_DIR, "scripts", "resume.py"))
    lines += [
        "## 迁移后校验命令（每篇执行）",
        "",
        "```bash",
        "# 1) setup_env 能从 draft/ 反推论文根、v1 二选一检测通过",
        "python %s --file <root>/<paper>/draft/draft.md" % setup,
        "# 2) RESUME 快照自检",
        "python %s --run-dir <root>/<paper>/.review check" % resume,
        "# 3) 复审能从 vN/ 找到源（source_root 已改写）",
        "python %s --file <root>/<paper>/draft/draft-v2.md --re-review" % setup,
        "```",
        "",
        "## 备份说明",
        "",
        "- `papers.bak/`、`output.bak/` 为迁移残留备份，**用户确认迁移无误后**再手工删除",
        "- `<root>/.migrate-layout/manifest.json` 记录全部操作；`--rollback` 可逆序复原",
        "（回滚应在开始任何新审阅之前执行）",
        "",
    ]
    return "\n".join(lines)


# ────────────────────────── 入口 ──────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="migrate_layout.py",
        description="paper-review v2.1 存量工作空间目录扁平化迁移："
                    "papers/<name>+output/ → 每篇论文一目录（vN/、draft/、response/、"
                    "reports/、.review/）。缺省 dry-run 零改动；--apply 执行并记 manifest；"
                    "--rollback 逆序复原；人工判定项只写报告不猜测；幂等可重跑。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--root", metavar="DIR", required=True,
                        help="工作空间根目录（含 papers/ 与 output/）")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true",
                      help="只输出迁移计划与人工判定清单，零文件系统改动（缺省）")
    mode.add_argument("--apply", action="store_true",
                      help="实际执行迁移（操作记入 .migrate-layout/manifest.json）")
    mode.add_argument("--rollback", action="store_true",
                      help="按 manifest 逆序恢复到迁移前状态")
    parser.add_argument("--report", metavar="FILE", default=None,
                        help="将 markdown 迁移报告写入指定路径（dry-run 也可用）")
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        fail("--root 不存在或不是目录: %s" % args.root)
    mode_name = ("apply" if args.apply else
                 "rollback" if args.rollback else "dry-run")

    manifest = Manifest(root)
    if args.rollback:
        if not manifest.load():
            fail("未找到 manifest（%s）：该工作空间未执行过 --apply 或 manifest 损坏"
                 % pabs(manifest.path))
        result = rollback(root, manifest)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)

    plan = Planner(root).scan()

    if args.apply:
        manifest.load()
        stats, _ = apply_plan(plan, manifest)
        result = {
            "success": True, "mode": mode_name, "root": pabs(root),
            "scanned": plan.scanned,
            "moves": [{"from": a["from"], "to": a["to"]}
                      for a in plan.actions if a["op"] == "move"],
            "rewrites": [a["path"] for a in plan.actions if a["op"] == "rewrite"],
            "pending": plan.pending, "notes": plan.notes,
            "moved": stats["moved"], "rewritten": stats["rewritten"],
            "manifest": pabs(manifest.path) if manifest.data["entries"] else None,
        }
    else:
        result = {
            "success": True, "mode": mode_name, "root": pabs(root),
            "scanned": plan.scanned,
            "moves": [{"from": a["from"], "to": a["to"]}
                      for a in plan.actions if a["op"] == "move"],
            "rewrites": [a["path"] for a in plan.actions if a["op"] == "rewrite"],
            "pending": plan.pending, "notes": plan.notes,
            "manifest": None,
        }

    if args.report:
        try:
            rp = os.path.abspath(args.report)
            os.makedirs(os.path.dirname(rp) or ".", exist_ok=True)
            with open(rp, "w", encoding="utf-8", newline="\n") as f:
                f.write(render_report(plan, mode_name, root))
            result["report"] = pabs(rp)
        except OSError as e:
            fail("--report 写入失败: %s" % e, code=1)
    else:
        result["report"] = None

    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
