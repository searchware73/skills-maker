#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_migrate_layout.py — migrate_layout.py v2.1 目录扁平化迁移单元测试

夹具：tests/test_paper_review/fixtures/layout_legacy/（备忘 §十一 第12条
「存量实测清单」5 类人工判定最小样例 + 1 篇可全自动迁移的干净论文 simple）。
所有用例一律先 copytree 到 tmpdir 再操作，**绝不就地修改仓库夹具**；
唯一直接读夹具的 test_repo_fixture_dry_run_untouched 验证 dry-run 零改动
（对应技能 Step 1 验证命令）。

覆盖：
  - dry-run：文件系统零改动；计划完整（moves/rewrites/pending/notes）
  - 5 类人工判定：nonstandard_report / latex_project / media_dir /
    figures_dir / output_non_report —— 只列出，不猜测、不移动
  - --apply：扁平结构正确（每篇自包含、sources/vK→vK、draft/response 归位、
    报告落 reports/、config/chain/RESUME 口径改写、papers.bak/output.bak
    保留、根 INDEX.md）；二次执行幂等（moved==0）
  - --rollback：全树逐字节复原；二次回滚 no-op；回滚后可重新 --apply
    （旧 manifest 归档）
  - --report：markdown 含 5 类待确认项与校验命令
  - 合成树：v1 双形态、LaTeX 子目录工程、同名目录冲突、INDEX 冲突、
    config 损坏、无 legacy 目录 no-op、sources/ 残留非 vK 内容
  - 参数错误 exit 2：--root 不存在、无 manifest 回滚、模式互斥

运行：python tests/test_paper_review/test_migrate_layout.py
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(os.path.join(
    HERE, "..", "..", "skills", "paper-review", "scripts", "migrate_layout.py"))
FIXTURE = os.path.join(HERE, "fixtures", "layout_legacy")

PAPER_NAMES = ["q10", "li-paper-v13", "simple", "xue-paper-latex",
               "yu-paper", "仿真稿件-20261105"]
OUTPUT_FILES = [
    "q10-1-复审报告.md", "q10-2-审阅报告.md", "q10-3-审阅报告.md",
    "q10-去AI替换对照清单-全量.md", "q10-r5-re-review-report.md",
    "simple-审阅报告.md", "何论文意见.20261011.docx",
    "仿真稿件-20261105-审阅报告（张审查第一轮）.20261109.docx",
    "仿真稿件-20261105-综合审阅意见.md",
]
# 人工判定滞留 output.bak 的 6 个文件（3 自动迁移：simple r1 / q10 r5 / 综合审阅意见）
PENDING_OUTPUT_FILES = [
    "q10-1-复审报告.md", "q10-2-审阅报告.md", "q10-3-审阅报告.md",
    "q10-去AI替换对照清单-全量.md", "何论文意见.20261011.docx",
    "仿真稿件-20261105-审阅报告（张审查第一轮）.20261109.docx",
]
FIVE_CATEGORIES = {"nonstandard_report", "latex_project", "media_dir",
                   "figures_dir", "output_non_report"}


def run(args):
    """运行 migrate_layout.py，返回 (exit_code, stdout_json, stderr)"""
    p = subprocess.run([sys.executable, SCRIPT] + args, capture_output=True)
    out = p.stdout.decode("utf-8", errors="replace")
    err = p.stderr.decode("utf-8", errors="replace")
    try:
        return p.returncode, json.loads(out), err
    except json.JSONDecodeError:
        return p.returncode, None, out + err


def px(path):
    """绝对 posix 路径（与脚本输出 from/to/path 同构）"""
    return os.path.abspath(path).replace("\\", "/")


def snapshot(root):
    """目录+文件相对路径快照（排除 .migrate-layout 脚本自留地）"""
    out = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != ".migrate-layout")
        rel = os.path.relpath(dirpath, root).replace("\\", "/")
        prefix = "" if rel == "." else rel + "/"
        for d in dirnames:
            out.add(prefix + d)
        for f in filenames:
            out.add(prefix + f)
    return sorted(out)


def tree_bytes(root):
    """全部文件内容字节快照（排除 .migrate-layout）"""
    data = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".migrate-layout"]
        for f in filenames:
            p = os.path.join(dirpath, f)
            rel = os.path.relpath(p, root).replace("\\", "/")
            with open(p, "rb") as fh:
                data[rel] = fh.read()
    return data


def write(path, content="placeholder\n"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


class FixtureCase(unittest.TestCase):
    """复制 layout_legacy 夹具到 tmpdir 后操作"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = os.path.join(self.tmp.name, "ws")
        shutil.copytree(FIXTURE, self.ws)

    def tearDown(self):
        self.tmp.cleanup()

    def j(self, *rel):
        return os.path.join(self.ws, *rel)


class TestDryRun(FixtureCase):
    def test_dry_run_zero_fs_change(self):
        before = snapshot(self.ws)
        bytes_before = tree_bytes(self.ws)
        code, js, err = run(["--root", self.ws, "--dry-run"])
        self.assertEqual(code, 0, err)
        self.assertTrue(js["success"])
        self.assertEqual(js["mode"], "dry-run")
        self.assertIsNone(js["manifest"])
        self.assertEqual(snapshot(self.ws), before)
        self.assertEqual(tree_bytes(self.ws), bytes_before)
        self.assertFalse(os.path.exists(self.j(".migrate-layout")))

    def test_dry_run_default_mode_is_dry_run(self):
        before = snapshot(self.ws)
        code, js, err = run(["--root", self.ws])       # 不带模式参数
        self.assertEqual(code, 0, err)
        self.assertEqual(js["mode"], "dry-run")
        self.assertEqual(snapshot(self.ws), before)

    def test_dry_run_plan_counts(self):
        code, js, err = run(["--root", self.ws, "--dry-run"])
        self.assertEqual(code, 0, err)
        self.assertEqual(js["scanned"], {"papers": 6, "output_files": 9})
        self.assertEqual(len(js["pending"]), 10)
        self.assertEqual({p["category"] for p in js["pending"]}, FIVE_CATEGORIES)
        # 5 处口径改写：q10 config+chain；simple config+chain+RESUME
        self.assertEqual(
            sorted(r.split("/layout_legacy/")[-1] if "/layout_legacy/" in r
                   else os.path.relpath(r, px(self.ws)).replace("\\", "/")
                   for r in js["rewrites"]),
            ["q10/.review/chain.md", "q10/.review/config.json",
             "simple/.review/RESUME.md", "simple/.review/chain.md",
             "simple/.review/config.json"])

    def test_dry_run_auto_moves(self):
        code, js, err = run(["--root", self.ws, "--dry-run"])
        self.assertEqual(code, 0, err)
        pairs = {(m["from"], m["to"]) for m in js["moves"]}
        expected = {
            # 整目录移根
            (px(self.j("papers", "simple")), px(self.j("simple"))),
            (px(self.j("papers", "q10")), px(self.j("q10"))),
            (px(self.j("papers", "xue-paper-latex")), px(self.j("xue-paper-latex"))),
            # 内部规范化（from 为整目录移动后的执行期路径）
            (px(self.j("simple", "sources", "v2")), px(self.j("simple", "v2"))),
            (px(self.j("simple", "draft.md")), px(self.j("simple", "draft", "draft.md"))),
            (px(self.j("simple", "draft-v2.md")),
             px(self.j("simple", "draft", "draft-v2.md"))),
            (px(self.j("simple", "response-v2.md")),
             px(self.j("simple", "response", "response-v2.md"))),
            (px(self.j("q10", "draft-v5.md")),
             px(self.j("q10", "draft", "draft-v5.md"))),
            # INDEX 上移工程根
            (px(self.j("papers", "INDEX.md")), px(self.j("INDEX.md"))),
            # output 报告自动归位
            (px(self.j("output", "simple-审阅报告.md")),
             px(self.j("simple", "reports", "r1-审阅报告.md"))),
            (px(self.j("output", "q10-r5-re-review-report.md")),
             px(self.j("q10", "reports", "r5-复审报告.md"))),
            (px(self.j("output", "仿真稿件-20261105-综合审阅意见.md")),
             px(self.j("仿真稿件-20261105", "reports",
                       "仿真稿件-20261105-综合审阅意见.md"))),
            # 备份保留
            (px(self.j("papers")), px(self.j("papers.bak"))),
            (px(self.j("output")), px(self.j("output.bak"))),
        }
        self.assertTrue(expected.issubset(pairs), "缺失计划: %s" % (expected - pairs))

    def test_dry_run_pending_detail(self):
        code, js, err = run(["--root", self.ws, "--dry-run"])
        self.assertEqual(code, 0, err)
        by_cat = {}
        for p in js["pending"]:
            by_cat.setdefault(p["category"], []).append(p)
        # ① 非标准报告名：q10-1/q10-2/q10-3（轮次号需反推，不猜）
        items = {os.path.basename(p["item"]) for p in by_cat["nonstandard_report"]}
        self.assertEqual(items, {"q10-1-复审报告.md", "q10-2-审阅报告.md",
                                 "q10-3-审阅报告.md"})
        for p in by_cat["nonstandard_report"]:
            self.assertIn("反推", p["recommendation"])
        # ② 完整 LaTeX 工程
        self.assertEqual([p["paper"] for p in by_cat["latex_project"]],
                         ["xue-paper-latex"])
        self.assertIn("v1/", by_cat["latex_project"][0]["recommendation"])
        # ③ pandoc media/
        self.assertEqual(sorted(p["paper"] for p in by_cat["media_dir"]),
                         ["li-paper-v13", "仿真稿件-20261105"])
        # ④ PyMuPDF figures/
        self.assertEqual([p["paper"] for p in by_cat["figures_dir"]], ["yu-paper"])
        # ⑤ output 非报告文件（外部意见/过程产物）
        items = {os.path.basename(p["item"]) for p in by_cat["output_non_report"]}
        self.assertEqual(items, {
            "q10-去AI替换对照清单-全量.md", "何论文意见.20261011.docx",
            "仿真稿件-20261105-审阅报告（张审查第一轮）.20261109.docx"})
        # docx 外部意见的建议指向 response/
        rec = "\n".join(p["recommendation"] for p in by_cat["output_non_report"])
        self.assertIn("response/", rec)

    def test_dry_run_comprehensive_report_note(self):
        code, js, err = run(["--root", self.ws, "--dry-run"])
        self.assertEqual(code, 0, err)
        joined = "\n".join(js["notes"])
        self.assertIn("综合审阅意见", joined)
        self.assertIn("保留原名", joined)

    def test_repo_fixture_dry_run_untouched(self):
        """技能 Step 1 验证命令：直接对仓库夹具 dry-run，零改动 + 5 类待确认"""
        before = snapshot(FIXTURE)
        code, js, err = run(["--root", FIXTURE, "--dry-run"])
        self.assertEqual(code, 0, err)
        self.assertTrue(js["success"])
        self.assertEqual({p["category"] for p in js["pending"]}, FIVE_CATEGORIES)
        self.assertEqual(snapshot(FIXTURE), before)
        self.assertFalse(os.path.exists(os.path.join(FIXTURE, ".migrate-layout")))


class TestApply(FixtureCase):
    def test_apply_structure(self):
        code, js, err = run(["--root", self.ws, "--apply"])
        self.assertEqual(code, 0, err)
        self.assertTrue(js["success"])
        self.assertEqual(js["mode"], "apply")
        self.assertGreater(js["moved"], 0)
        self.assertEqual(js["rewritten"], 5)
        self.assertIsNotNone(js["manifest"])
        # 验收标准：根目录不再存在 papers/、output/；.bak 保留
        self.assertFalse(os.path.exists(self.j("papers")))
        self.assertFalse(os.path.exists(self.j("output")))
        self.assertTrue(os.path.isdir(self.j("papers.bak")))
        self.assertTrue(os.path.isdir(self.j("output.bak")))
        self.assertEqual(sorted(os.listdir(self.j("papers.bak"))), [])  # 全部迁出
        self.assertEqual(sorted(os.listdir(self.j("output.bak"))),
                         sorted(PENDING_OUTPUT_FILES))                 # 待判定滞留
        # 根 INDEX.md
        self.assertTrue(os.path.isfile(self.j("INDEX.md")))
        # simple：自包含（源/版本/草稿/回复/报告/过程）
        for rel in ["paper.docx",
                    os.path.join("v2", "paper-v2.docx"),
                    os.path.join("draft", "draft.md"),
                    os.path.join("draft", "draft-v2.md"),
                    os.path.join("response", "response-v2.md"),
                    os.path.join("reports", "r1-审阅报告.md"),
                    os.path.join(".review", "r1", "final_report.md")]:
            self.assertTrue(os.path.isfile(self.j("simple", rel)), "缺: %s" % rel)
        self.assertFalse(os.path.exists(self.j("simple", "sources")))
        self.assertFalse(os.path.exists(self.j("simple", "draft.md")))
        self.assertFalse(os.path.exists(self.j("simple", "response-v2.md")))
        # simple config 口径改写
        with open(self.j("simple", ".review", "config.json"),
                  encoding="utf-8-sig") as f:
            cfg = json.load(f)
        self.assertEqual(cfg["layout"], "flat-v2.1")
        self.assertEqual(cfg["paper_dir"], px(self.j("simple")))
        self.assertEqual(cfg["doctype"], "full-paper")
        self.assertEqual(cfg["versions"]["v1"],
                         {"source_root": ".", "draft": "draft/draft.md",
                          "response": None})
        self.assertEqual(cfg["versions"]["v2"],
                         {"source_root": "v2", "draft": "draft/draft-v2.md",
                          "response": "response/response-v2.md"})
        self.assertEqual(cfg["rounds"], {"r1": {"version": "v1"},
                                         "r2": {"version": "v2"}})
        # simple chain/RESUME：sources/v2 → v2
        with open(self.j("simple", ".review", "chain.md"), encoding="utf-8") as f:
            chain = f.read()
        self.assertNotIn("sources/v2", chain)
        self.assertIn('v2="v2/"', chain)
        with open(self.j("simple", ".review", "RESUME.md"), encoding="utf-8") as f:
            self.assertNotIn("sources/v2", f.read())
        # q10：多草稿 + sources 规范化 + r5 报告
        for n in ["", "-v2", "-v3", "-v4", "-v5"]:
            self.assertTrue(os.path.isfile(
                self.j("q10", "draft", "draft%s.md" % n)), "缺 draft%s.md" % n)
        self.assertTrue(os.path.isfile(self.j("q10", "v2", "paper-v2.docx")))
        self.assertTrue(os.path.isfile(self.j("q10", "reports", "r5-复审报告.md")))
        with open(self.j("q10", ".review", "config.json"),
                  encoding="utf-8-sig") as f:
            cfg10 = json.load(f)
        self.assertEqual(cfg10["versions"]["v2"]["source_root"], "v2")
        self.assertEqual(cfg10["versions"]["v2"]["draft"], "draft/draft-v2.md")
        self.assertEqual(cfg10["layout"], "flat-v2.1")
        # xue：LaTeX 工程未被猜测移动（main.tex 仍在论文根，未入 v1/）
        self.assertTrue(os.path.isfile(self.j("xue-paper-latex", "main.tex")))
        self.assertFalse(os.path.exists(self.j("xue-paper-latex", "v1")))
        self.assertTrue(os.path.isfile(
            self.j("xue-paper-latex", "chapters", "ch1.tex")))
        self.assertTrue(os.path.isfile(self.j("xue-paper-latex", "README.md")))
        self.assertTrue(os.path.isfile(
            self.j("xue-paper-latex", "draft", "draft.md")))
        # li/yu/仿真：图目录滞留论文根（待人工判定），draft 已归位
        self.assertTrue(os.path.isfile(self.j("li-paper-v13", "media", "img1.png")))
        self.assertTrue(os.path.isfile(self.j("yu-paper", "figures", "p1.png")))
        self.assertTrue(os.path.isfile(
            self.j("仿真稿件-20261105", "media", "fig.png")))
        self.assertTrue(os.path.isfile(self.j("li-paper-v13", "draft", "draft.md")))
        self.assertTrue(os.path.isfile(
            self.j("仿真稿件-20261105", "reports",
                   "仿真稿件-20261105-综合审阅意见.md")))
        # manifest 落盘
        self.assertTrue(os.path.isfile(
            self.j(".migrate-layout", "manifest.json")))

    def test_apply_idempotent(self):
        code, js1, err = run(["--root", self.ws, "--apply"])
        self.assertEqual(code, 0, err)
        snap1 = snapshot(self.ws)
        bytes1 = tree_bytes(self.ws)
        code2, js2, err2 = run(["--root", self.ws, "--apply"])
        self.assertEqual(code2, 0, err2)
        self.assertTrue(js2["success"])
        self.assertEqual(js2["moved"], 0)          # 二次执行零移动
        self.assertEqual(js2["rewritten"], 0)
        self.assertEqual(snapshot(self.ws), snap1)
        self.assertEqual(tree_bytes(self.ws), bytes1)
        self.assertIn("无需迁移", "\n".join(js2["notes"]))


class TestRollback(FixtureCase):
    def test_rollback_restores_bytes(self):
        snap0 = snapshot(self.ws)
        bytes0 = tree_bytes(self.ws)
        code, _, err = run(["--root", self.ws, "--apply"])
        self.assertEqual(code, 0, err)
        self.assertNotEqual(snapshot(self.ws), snap0)   # 确实迁移过
        code, js, err = run(["--root", self.ws, "--rollback"])
        self.assertEqual(code, 0, err)
        self.assertTrue(js["success"])
        self.assertGreater(js["restored"], 0)
        # 全树逐字节复原（.migrate-layout 除外）
        self.assertEqual(snapshot(self.ws), snap0)
        self.assertEqual(tree_bytes(self.ws), bytes0)
        self.assertFalse(os.path.exists(self.j("simple")))
        self.assertFalse(os.path.exists(self.j("INDEX.md")))
        self.assertTrue(os.path.isfile(self.j("papers", "INDEX.md")))
        self.assertFalse(os.path.exists(self.j("papers.bak")))
        self.assertFalse(os.path.exists(self.j("output.bak")))

    def test_rollback_twice_noop(self):
        run(["--root", self.ws, "--apply"])
        code, _, err = run(["--root", self.ws, "--rollback"])
        self.assertEqual(code, 0, err)
        code2, js2, err2 = run(["--root", self.ws, "--rollback"])
        self.assertEqual(code2, 0, err2)
        self.assertTrue(js2["success"])
        self.assertEqual(js2["restored"], 0)
        self.assertIn("回滚状态", "\n".join(js2["notes"]))

    def test_reapply_after_rollback(self):
        run(["--root", self.ws, "--apply"])
        run(["--root", self.ws, "--rollback"])
        code, js, err = run(["--root", self.ws, "--apply"])
        self.assertEqual(code, 0, err)
        self.assertTrue(js["success"])
        self.assertGreater(js["moved"], 0)
        self.assertTrue(os.path.isdir(self.j("simple")))
        self.assertTrue(os.path.isfile(self.j("INDEX.md")))
        # 旧 manifest 已归档
        archives = [f for f in os.listdir(self.j(".migrate-layout"))
                    if f.startswith("manifest-") and f.endswith(".json")]
        self.assertEqual(len(archives), 1)


class TestReport(FixtureCase):
    def test_report_markdown(self):
        report = os.path.join(self.tmp.name, "report.md")   # ws 之外
        code, js, err = run(["--root", self.ws, "--dry-run", "--report", report])
        self.assertEqual(code, 0, err)
        self.assertEqual(js["report"], px(report))
        self.assertTrue(os.path.isfile(report))
        # dry-run + --report 仍不改被迁移树
        self.assertFalse(os.path.exists(self.j(".migrate-layout")))
        with open(report, encoding="utf-8") as f:
            md = f.read()
        for kw in ["人工判定项", "非标准报告名", "LaTeX", "media/", "figures/",
                   "q10-1-复审报告", "何论文意见", "自动迁移计划",
                   "迁移后校验命令", "papers.bak", "setup_env.py", "resume.py"]:
            self.assertIn(kw, md)
        # 5 类分组标题齐全
        for kw in ["（3 项）", "（2 项）", "（1 项）"]:
            self.assertIn(kw, md)


class TestSynthetic(unittest.TestCase):
    """合成小树：判定项与参数错误"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = os.path.join(self.tmp.name, "ws")
        os.makedirs(self.ws)

    def tearDown(self):
        self.tmp.cleanup()

    def j(self, *rel):
        return os.path.join(self.ws, *rel)

    def dry(self):
        code, js, err = run(["--root", self.ws, "--dry-run"])
        self.assertEqual(code, 0, err)
        return js

    def cats(self, js):
        return {p["category"] for p in js["pending"]}

    def test_v1_dual_form_pending(self):
        write(self.j("papers", "dual", "paper.docx"), "PK stub\n")
        write(self.j("papers", "dual", "v1", "main.tex"), "\\documentclass\n")
        write(self.j("papers", "dual", "draft.md"), "# d\n")
        js = self.dry()
        self.assertIn("v1_dual_form", self.cats(js))
        # v1/ 内的 .tex 不算独立 LaTeX 工程判定（vN/ 已在检测视野外）
        self.assertNotIn("latex_project", self.cats(js))

    def test_latex_project_subdir_only(self):
        write(self.j("papers", "tex2", "chapters", "ch1.tex"), "\\section{x}\n")
        write(self.j("papers", "tex2", "draft.md"), "# d\n")
        js = self.dry()
        self.assertIn("latex_project", self.cats(js))

    def test_paper_dir_conflict_skip(self):
        write(self.j("papers", "dup", "paper.docx"), "PK new\n")
        write(self.j("dup", "keep.txt"), "原有内容\n")
        js = self.dry()
        self.assertIn("paper_dir_conflict", self.cats(js))
        code, js2, err = run(["--root", self.ws, "--apply"])
        self.assertEqual(code, 0, err)
        # 原有目录内容分毫未动，冲突篇滞留 papers.bak
        with open(self.j("dup", "keep.txt"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "原有内容\n")
        self.assertFalse(os.path.exists(self.j("dup", "paper.docx")))
        self.assertTrue(os.path.isfile(self.j("papers.bak", "dup", "paper.docx")))

    def test_index_conflict(self):
        write(self.j("papers", "p1", "draft.md"), "# d\n")
        write(self.j("papers", "INDEX.md"), "# 旧索引\n")
        write(self.j("INDEX.md"), "# 新索引（保留）\n")
        js = self.dry()
        self.assertIn("index_conflict", self.cats(js))
        code, _, err = run(["--root", self.ws, "--apply"])
        self.assertEqual(code, 0, err)
        with open(self.j("INDEX.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "# 新索引（保留）\n")
        self.assertTrue(os.path.isfile(self.j("papers.bak", "INDEX.md")))

    def test_config_broken_pending(self):
        write(self.j("papers", "bad", "draft.md"), "# d\n")
        write(self.j("papers", "bad", ".review", "config.json"), "{{{not json")
        js = self.dry()
        self.assertIn("config_broken", self.cats(js))
        code, _, err = run(["--root", self.ws, "--apply"])
        self.assertEqual(code, 0, err)
        # 论文照常迁移，坏 config 原样保留待人工修复
        with open(self.j("bad", ".review", "config.json"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "{{{not json")

    def test_no_legacy_dirs_noop(self):
        js = self.dry()
        self.assertTrue(js["success"])
        self.assertEqual(js["moves"], [])
        self.assertIn("无需迁移", "\n".join(js["notes"]))
        code, js2, err = run(["--root", self.ws, "--apply"])
        self.assertEqual(code, 0, err)
        self.assertEqual(js2["moved"], 0)
        self.assertFalse(os.path.exists(self.j(".migrate-layout")))

    def test_sources_residual_kept(self):
        write(self.j("papers", "res", "draft.md"), "# d\n")
        write(self.j("papers", "res", "sources", "v2", "p.docx"), "PK\n")
        write(self.j("papers", "res", "sources", "notes.txt"), "非版本内容\n")
        code, js, err = run(["--root", self.ws, "--apply"])
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.isfile(self.j("res", "v2", "p.docx")))
        # 非 vK 内容滞留 sources/（不删不猜）
        self.assertTrue(os.path.isfile(self.j("res", "sources", "notes.txt")))
        self.assertIn("非 vK 内容", "\n".join(js["notes"]))


class TestArgErrors(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = os.path.join(self.tmp.name, "ws")
        os.makedirs(self.ws)

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_root_exit2(self):
        code, js, _ = run(["--root", os.path.join(self.tmp.name, "nope"),
                           "--dry-run"])
        self.assertEqual(code, 2)
        self.assertFalse(js["success"])

    def test_rollback_without_manifest_exit2(self):
        code, js, _ = run(["--root", self.ws, "--rollback"])
        self.assertEqual(code, 2)
        self.assertFalse(js["success"])

    def test_mutex_modes_exit2(self):
        p = subprocess.run([sys.executable, SCRIPT, "--root", self.ws,
                            "--apply", "--rollback"], capture_output=True)
        self.assertEqual(p.returncode, 2)

    def test_help_works(self):
        p = subprocess.run([sys.executable, SCRIPT, "--help"],
                           capture_output=True)
        self.assertEqual(p.returncode, 0)
        text = p.stdout.decode("utf-8", errors="replace")
        for flag in ["--root", "--dry-run", "--apply", "--rollback", "--report"]:
            self.assertIn(flag, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
