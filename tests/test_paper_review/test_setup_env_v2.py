#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_setup_env_v2.py — setup_env.py v2.0 单元测试

覆盖（对应 handoff-20261108 §八/§九/§十⑪）：
  - 版本文件名解析：draft.md→v1/r1；draft-v2.md→v2/r2；产物路由 r<N>/
  - doctype：缺失→needs_doctype_confirmation+检测线索；同轮补声明不递增轮次；
    准则绑定表 applied_criteria（full-paper vs problem-collection 差异断言）
  - doctype 跨轮继承（r2 自动继承 r1 声明）
  - 覆盖护栏：根目录出现未登记源文件→needs_source_confirmation
  - config.json 合并保留（exemptions/withdrawals 不丢）
  - 成本预估 estimate 输出与 --quick 建议
  - v1 兼容：旧键 file_path/section_range/review_dir/rounds_max 全部保留

运行：python tests/test_paper_review/test_setup_env_v2.py
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(os.path.join(
    HERE, "..", "..", "skills", "paper-review", "scripts", "setup_env.py"))

DRAFT_V1 = """# 论文标题

## 摘要
本文研究数字孪生技术。

## 1 引言
背景介绍。

## 1.1 研究现状
现状综述。

## 2 实验
数据集与实验设置。

## 参考文献
[1] 张三. 数字孪生[J]. 学报, 2024.
"""

# 疑似非完整论文（无摘要/无参考文献/无实验）
DRAFT_PROPOSAL = """# 问题征集建议

## 一、背景
军事训练仿真需求。

## 二、问题清单
问题1：异构数据融合。定量断言：融合效率提升 30%。
"""


def run_setup(cwd, *extra):
    p = subprocess.run([sys.executable, SCRIPT] + list(extra),
                       capture_output=True, cwd=cwd)
    out = p.stdout.decode("utf-8", errors="replace")
    err = p.stderr.decode("utf-8", errors="replace")
    js = json.loads(out) if out.strip() else None
    return p.returncode, js, err


class TestV1Compat(unittest.TestCase):
    """旧键与旧行为兼容"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        with open(os.path.join(self.dir, "draft.md"), "w", encoding="utf-8") as f:
            f.write(DRAFT_V1)
        self.code, self.js, self.err = run_setup(
            self.dir, "--file", "draft.md", "--section", "1.1",
            "--rounds", "2", "--doctype", "full-paper")

    def tearDown(self):
        self.tmp.cleanup()

    def test_old_keys_present(self):
        self.assertEqual(self.code, 0, self.err)
        self.assertTrue(self.js["success"])
        self.assertEqual(self.js["section"], "1.1")
        self.assertEqual(self.js["rounds_max"], 2)
        self.assertIsNotNone(self.js["section_range"])
        self.assertIn("## 1.1", self.js["section_title"])
        self.assertTrue(self.js["review_dir"].endswith("/.review/"))
        self.assertTrue(self.js["file_path"].endswith("draft.md"))

    def test_version_round_defaults(self):
        self.assertEqual(self.js["version"], "v1")
        self.assertEqual(self.js["round"], "r1")
        self.assertTrue(self.js["run_dir"].endswith("/.review/r1/"))
        # 产物路由：日志文件建在 r1/ 下
        for name in ("revision_log.md", "convergence.md"):
            self.assertTrue(os.path.isfile(
                os.path.join(self.dir, ".review", "r1", name)))


class TestDoctype(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        with open(os.path.join(self.dir, "draft.md"), "w", encoding="utf-8") as f:
            f.write(DRAFT_PROPOSAL)

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_doctype_triggers_confirmation(self):
        code, js, err = run_setup(self.dir, "--file", "draft.md")
        self.assertEqual(code, 0, err)
        self.assertTrue(js["needs_doctype_confirmation"])
        self.assertIsNone(js["doctype"])
        # 检测线索：无摘要/无参考文献/无实验节
        self.assertTrue(any("参考文献" in h for h in js["doctype_hints"]))
        self.assertTrue(any("疑似非完整论文" in h for h in js["doctype_hints"]))

    def test_same_round_doctype_update_no_increment(self):
        run_setup(self.dir, "--file", "draft.md")
        code, js, _ = run_setup(self.dir, "--file", "draft.md",
                                "--doctype", "problem-collection")
        self.assertEqual(js["round"], "r1")   # 同轮更新，不递增
        self.assertEqual(js["doctype"], "problem-collection")
        self.assertFalse(js["needs_doctype_confirmation"])

    def test_criteria_binding_difference(self):
        """§8.4：同一稿件在 full-paper 与 problem-collection 两类型下的准则差异"""
        _, js_fp, _ = run_setup(self.dir, "--file", "draft.md", "--doctype", "full-paper")
        crit_fp = js_fp["applied_criteria"]
        required_fp = {r["item"]: r["severity_if_missing"] for r in crit_fp["required"]}
        self.assertEqual(required_fp.get("参考文献"), "P0")   # full-paper 缺参考文献=P0
        self.assertEqual(crit_fp["substituted"], [])

        # 清掉 config 换类型再跑
        os.remove(os.path.join(self.dir, ".review", "config.json"))
        _, js_pc, _ = run_setup(self.dir, "--file", "draft.md",
                                "--doctype", "problem-collection")
        crit_pc = js_pc["applied_criteria"]
        # 豁免项：参考文献不入必备清单（豁免即不报）
        self.assertIn("参考文献", crit_pc["exempt"])
        self.assertNotIn("参考文献",
                         [r["item"] for r in crit_pc["required"]])
        # 检查置换生效：数据支撑证明 → 声称↔依据
        subs = {s["from"]: s["to"] for s in crit_pc["substituted"]}
        self.assertIn("数据支撑证明", subs)
        self.assertIn("声称↔依据", subs["数据支撑证明"])
        # 定量断言出处为必备 P1
        required_pc = {r["item"]: r["severity_if_missing"] for r in crit_pc["required"]}
        self.assertEqual(required_pc.get("定量断言出处"), "P1")

    def test_invalid_doctype_exit2(self):
        code, _, err = run_setup(self.dir, "--file", "draft.md", "--doctype", "blog-post")
        self.assertEqual(code, 2)
        self.assertIn("非法取值", err)

    def test_other_doctype(self):
        code, js, _ = run_setup(self.dir, "--file", "draft.md",
                                "--doctype", "other:立项建议书")
        self.assertEqual(code, 0)
        self.assertEqual(js["doctype"], "other:立项建议书")
        self.assertIn("note", js["applied_criteria"])


class TestRoundsAndGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        with open(os.path.join(self.dir, "draft.md"), "w", encoding="utf-8") as f:
            f.write(DRAFT_V1)
        with open(os.path.join(self.dir, "draft-v2.md"), "w", encoding="utf-8") as f:
            f.write(DRAFT_V1.replace("背景介绍", "背景介绍（修订）"))
        run_setup(self.dir, "--file", "draft.md", "--doctype", "thesis")

    def tearDown(self):
        self.tmp.cleanup()

    def test_v2_re_review_new_round_and_inheritance(self):
        code, js, err = run_setup(self.dir, "--file", "draft-v2.md", "--re-review")
        self.assertEqual(code, 0, err)
        self.assertEqual(js["version"], "v2")
        self.assertEqual(js["round"], "r2")
        self.assertTrue(js["re_review"])
        # doctype 跨轮继承（本轮未声明，仍为 r1 的 thesis）
        self.assertEqual(js["doctype"], "thesis")
        self.assertFalse(js["needs_doctype_confirmation"])
        # config 登记 source_root 映射
        with open(os.path.join(self.dir, ".review", "config.json"),
                  encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(cfg["versions"]["v2"]["source_root"], "v2")
        self.assertEqual(cfg["current_round"], "r2")
        self.assertTrue(cfg["rounds"]["r2"]["re_review"])

    def test_same_version_reuse_without_new_run(self):
        run_setup(self.dir, "--file", "draft-v2.md")
        _, js, _ = run_setup(self.dir, "--file", "draft-v2.md")
        self.assertEqual(js["round"], "r2")   # 同版本重复调用复用当前轮次
        _, js2, _ = run_setup(self.dir, "--file", "draft-v2.md", "--new-run")
        self.assertEqual(js2["round"], "r3")  # 显式 --new-run 才递增

    def test_overwrite_guard(self):
        """§九规则2：根目录出现未登记源文件且已有轮次记录 → 触发确认"""
        run_setup(self.dir, "--file", "draft-v2.md")
        with open(os.path.join(self.dir, "paper_v3.docx"), "wb") as f:
            f.write(b"PK\x03\x04stub")
        _, js, _ = run_setup(self.dir, "--file", "draft-v2.md")
        self.assertTrue(js["needs_source_confirmation"])
        self.assertIn("paper_v3.docx", js["untracked_sources"])

    def test_config_merge_preserves_state(self):
        """config.json 合并：既有 exemptions/withdrawals 不被覆盖"""
        cfg_path = os.path.join(self.dir, ".review", "config.json")
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
        cfg["exemptions"] = [{"item": "致谢", "reason": "盲审版"}]
        cfg["withdrawals"] = [{"id": "R-3", "reason": "核验不成立"}]
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False)
        run_setup(self.dir, "--file", "draft-v2.md")
        with open(cfg_path, encoding="utf-8") as f:
            cfg2 = json.load(f)
        self.assertEqual(cfg2["exemptions"][0]["item"], "致谢")
        self.assertEqual(cfg2["withdrawals"][0]["id"], "R-3")


class TestEstimate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        with open(os.path.join(self.dir, "draft.md"), "w", encoding="utf-8") as f:
            f.write(DRAFT_V1)

    def tearDown(self):
        self.tmp.cleanup()

    def test_estimate_full_mode(self):
        _, js, _ = run_setup(self.dir, "--file", "draft.md", "--doctype", "full-paper")
        est = js["estimate"]
        self.assertEqual(est["mode"], "full")
        self.assertEqual(est["seats"], 7)
        self.assertEqual(est["agents"]["stage2_deai"], 5)
        self.assertGreater(est["total_agents"], 0)
        self.assertIn("total", est["est_wall_clock_min"])
        self.assertIn("建议", est["recommendation"])

    def test_estimate_quick_and_recomment(self):
        _, js, _ = run_setup(self.dir, "--file", "draft.md",
                             "--doctype", "section-draft", "--quick")
        est = js["estimate"]
        self.assertEqual(est["mode"], "quick")
        self.assertEqual(est["seats"], 2)
        self.assertEqual(est["agents"]["stage2_deai"], 0)

    def test_estimate_recommends_quick_for_short_nonfull(self):
        # 短稿 + 非完整论文类型 → 建议 quick（行数 ≤500 由夹具满足）
        with open(os.path.join(self.dir, "short.md"), "w", encoding="utf-8") as f:
            f.write(DRAFT_PROPOSAL)
        _, js, _ = run_setup(self.dir, "--file", "short.md",
                             "--doctype", "problem-collection")
        self.assertIn("--quick", js["estimate"]["recommendation"])

    def test_expert_comments_recorded(self):
        with open(os.path.join(self.dir, "expert.md"), "w", encoding="utf-8") as f:
            f.write("1. 意见一\n")
        _, js, _ = run_setup(self.dir, "--file", "draft.md", "--doctype", "full-paper",
                             "--expert-comments", "expert.md")
        self.assertTrue(js["expert_comments"].endswith("expert.md"))
        self.assertEqual(js["estimate"]["agents"]["expert_reconcile"], 1)


class TestFlatLayout(unittest.TestCase):
    """v2.1 §十一 第12条：目录扁平化（draft/ 反推、v1 二选一、source_root、INDEX、忽略目录）"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name          # 工程根
        self.paper = os.path.join(self.root, "paper1")
        os.makedirs(os.path.join(self.paper, "draft"))

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, content="# 稿\n", binary=None):
        p = os.path.join(self.paper, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if binary is not None:
            with open(p, "wb") as f:
                f.write(binary)
        else:
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
        return p

    def cfg(self):
        with open(os.path.join(self.paper, ".review", "config.json"),
                  encoding="utf-8") as f:
            return json.load(f)

    def test_paper_dir_from_draft_subdir(self):
        """paper_dir 从 draft/ 反推，不得再用 dirname(file_path)"""
        self.write("draft/draft.md", DRAFT_V1)
        code, js, err = run_setup(self.root, "--file",
                                  os.path.join("paper1", "draft", "draft.md"),
                                  "--doctype", "full-paper")
        self.assertEqual(code, 0, err)
        self.assertTrue(js["paper_dir"].endswith("/paper1"))
        self.assertTrue(js["review_dir"].endswith("/paper1/.review/"))
        self.assertTrue(os.path.isdir(os.path.join(self.paper, ".review", "r1")))
        self.assertEqual(self.cfg()["versions"]["v1"]["draft"], "draft/draft.md")
        self.assertEqual(self.cfg()["layout"], "flat-v2.1")
        self.assertEqual(js["layout"], "flat-v2.1")

    def test_legacy_root_draft_still_works(self):
        """v1.x 扁平产物只读兼容：根目录 draft.md 仍可初始化"""
        self.write("draft.md", DRAFT_V1)
        code, js, err = run_setup(self.root, "--file",
                                  os.path.join("paper1", "draft.md"),
                                  "--doctype", "full-paper")
        self.assertEqual(code, 0, err)
        self.assertTrue(js["paper_dir"].endswith("/paper1"))
        self.assertEqual(self.cfg()["versions"]["v1"]["draft"], "draft.md")

    def test_v1_dual_form_conflict_error(self):
        """v1 二选一：根单文件源与 v1/ 目录并存 → 报错"""
        self.write("draft/draft.md", DRAFT_V1)
        self.write("paper.docx", binary=b"PK\x03\x04stub")
        self.write("v1/main.tex", content="\\documentclass{article}\n")
        code, js, err = run_setup(self.root, "--file",
                                  os.path.join("paper1", "draft", "draft.md"),
                                  "--doctype", "full-paper")
        self.assertEqual(code, 1)
        self.assertFalse(js["success"])
        self.assertTrue(any("v1 双形态并存" in p for p in js["problems"]), js)

    def test_v1_form_root_single_file(self):
        """根单文件源 → source_root='.'，且登记 source_file（条目7）"""
        self.write("draft/draft.md", DRAFT_V1)
        self.write("paper.docx", binary=b"PK\x03\x04stub")
        code, js, err = run_setup(self.root, "--file",
                                  os.path.join("paper1", "draft", "draft.md"),
                                  "--doctype", "full-paper")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.cfg()["versions"]["v1"]["source_root"], ".")
        self.assertEqual(self.cfg()["versions"]["v1"]["source_file"], "paper.docx")

    def test_v1_form_latex_dir(self):
        """多文件 LaTeX 整包入 v1/ → source_root='v1'"""
        self.write("draft/draft.md", DRAFT_V1)
        self.write("v1/main.tex", content="\\documentclass{article}\n")
        self.write("v1/chapters/ch1.tex", content="chapter\n")
        code, js, err = run_setup(self.root, "--file",
                                  os.path.join("paper1", "draft", "draft.md"),
                                  "--doctype", "full-paper")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.cfg()["versions"]["v1"]["source_root"], "v1")

    def test_vn_source_root_and_legacy_compat(self):
        """v2+ → source_root='vN'；旧 sources/vN 目录仍在时只读兼容"""
        self.write("draft/draft.md", DRAFT_V1)
        self.write("draft/draft-v2.md", DRAFT_V1)
        run_setup(self.root, "--file", os.path.join("paper1", "draft", "draft.md"),
                  "--doctype", "thesis")
        self.write("v2/paper.docx", binary=b"PK\x03\x04stub")
        _, js, _ = run_setup(self.root, "--file",
                             os.path.join("paper1", "draft", "draft-v2.md"),
                             "--re-review")
        self.assertEqual(js["version"], "v2")
        self.assertEqual(self.cfg()["versions"]["v2"]["source_root"], "v2")

        # 旧形态：sources/v2 存在、v2 不存在 → 只读兼容 sources/v2
        paper2 = os.path.join(self.root, "paper2")
        os.makedirs(os.path.join(paper2, "draft"))
        os.makedirs(os.path.join(paper2, "sources", "v2"))
        for rel in ("draft/draft.md", "draft/draft-v2.md"):
            with open(os.path.join(paper2, rel), "w", encoding="utf-8") as f:
                f.write(DRAFT_V1)
        run_setup(self.root, "--file", os.path.join("paper2", "draft", "draft.md"),
                  "--doctype", "thesis")
        run_setup(self.root, "--file", os.path.join("paper2", "draft", "draft-v2.md"))
        with open(os.path.join(paper2, ".review", "config.json"),
                  encoding="utf-8") as f:
            cfg2 = json.load(f)
        self.assertEqual(cfg2["versions"]["v2"]["source_root"], "sources/v2")
        # 旧结构未迁移 → 不盖 flat-v2.1 章（migrate_layout 识别用）
        self.assertNotEqual(cfg2.get("layout"), "flat-v2.1")

    def test_guard_ignores_layout_dirs_and_old_v1_source(self):
        """护栏忽略 v1/ vN/ draft/ response/ reports/ figures/ media/；
        mtime 早于 r1 开跑时间的 v1 既有源不误报（条目7）"""
        self.write("draft/draft.md", DRAFT_V1)
        old_src = self.write("paper.docx", binary=b"PK\x03\x04stub")
        # 把源文件 mtime 拨早（早于即将记录的 r1 started_at）
        os.utime(old_src, (1000000000, 1000000000))
        run_setup(self.root, "--file", os.path.join("paper1", "draft", "draft.md"),
                  "--doctype", "thesis")
        for d in ("v2", "response", "reports", "figures", "media"):
            os.makedirs(os.path.join(self.paper, d), exist_ok=True)
        self.write("v2/new.docx", binary=b"PK\x03\x04stub")   # 目录内不报
        _, js, _ = run_setup(self.root, "--file",
                             os.path.join("paper1", "draft", "draft.md"))
        self.assertFalse(js["needs_source_confirmation"], js.get("untracked_sources"))
        # 根目录出现真正的新源文件（mtime 晚于 r1）→ 仍须报
        self.write("paper_v2.docx", binary=b"PK\x03\x04stub")
        _, js2, _ = run_setup(self.root, "--file",
                              os.path.join("paper1", "draft", "draft.md"))
        self.assertTrue(js2["needs_source_confirmation"])
        self.assertIn("paper_v2.docx", js2["untracked_sources"])

    def test_index_created_at_project_root(self):
        self.write("draft/draft.md", DRAFT_V1)
        run_setup(self.root, "--file", os.path.join("paper1", "draft", "draft.md"),
                  "--doctype", "full-paper")
        idx = os.path.join(self.root, "INDEX.md")
        self.assertTrue(os.path.isfile(idx))
        with open(idx, encoding="utf-8") as f:
            head = f.read()
        self.assertIn("| 稿件 |", head)


class TestNewCliFlags(unittest.TestCase):
    """v2.1 §十一 第13条：--source/--format/--focus/--no-fix；第21条 docx 校验；第23条非md守卫"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        with open(os.path.join(self.dir, "draft.md"), "w", encoding="utf-8") as f:
            f.write(DRAFT_V1)
        with open(os.path.join(self.dir, "src.docx"), "wb") as f:
            f.write(b"PK\x03\x04stub")

    def tearDown(self):
        self.tmp.cleanup()

    def test_source_format_passthrough(self):
        code, js, err = run_setup(self.dir, "--file", "draft.md",
                                  "--doctype", "full-paper",
                                  "--source", "src.docx", "--format", "docx")
        self.assertEqual(code, 0, err)
        self.assertTrue(js["source"].endswith("src.docx"))
        self.assertEqual(js["source_format"], "docx")
        with open(os.path.join(self.dir, ".review", "config.json"),
                  encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(cfg["versions"]["v1"]["source_format"], "docx")
        self.assertTrue(cfg["versions"]["v1"]["source"].endswith("src.docx"))

    def test_format_inferred_from_extension(self):
        _, js, _ = run_setup(self.dir, "--file", "draft.md", "--doctype", "full-paper",
                             "--source", "src.docx")
        self.assertEqual(js["source_format"], "docx")

    def test_source_missing_exit2(self):
        code, _, err = run_setup(self.dir, "--file", "draft.md",
                                 "--source", "nope.docx")
        self.assertEqual(code, 2)
        self.assertIn("--source 不存在", err)

    def test_format_without_source_exit2(self):
        code, _, err = run_setup(self.dir, "--file", "draft.md", "--format", "tex")
        self.assertEqual(code, 2)
        self.assertIn("--format 须与 --source", err)

    def test_focus_and_no_fix_recorded(self):
        code, js, err = run_setup(self.dir, "--file", "draft.md",
                                  "--doctype", "full-paper",
                                  "--focus", "panel", "--no-fix")
        self.assertEqual(code, 0, err)
        self.assertEqual(js["focus"], "panel")
        self.assertTrue(js["no_fix"])
        with open(os.path.join(self.dir, ".review", "config.json"),
                  encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(cfg["rounds"]["r1"]["focus"], "panel")
        self.assertTrue(cfg["rounds"]["r1"]["no_fix"])

    def test_focus_invalid_exit2(self):
        code, _, _ = run_setup(self.dir, "--file", "draft.md", "--focus", "stage3")
        self.assertEqual(code, 2)

    def test_non_md_input_guided_to_step00(self):
        """条目23：直接把 .docx 交给 setup_env → 明确指引先走 Step 0.0 转换"""
        code, js, _ = run_setup(self.dir, "--file", "src.docx")
        self.assertEqual(code, 1)
        self.assertTrue(any("Step 0.0" in p for p in js["problems"]), js)

    def test_expert_comments_docx_invalid_zip_exit2(self):
        """条目21：docx 原生支持，但伪 docx（非 zip）给明确错误"""
        with open(os.path.join(self.dir, "expert.docx"), "wb") as f:
            f.write(b"not a zip at all")
        code, _, err = run_setup(self.dir, "--file", "draft.md",
                                 "--expert-comments", "expert.docx")
        self.assertEqual(code, 2)
        self.assertIn("不是有效 docx", err)


class TestHistoricVersionRefusal(unittest.TestCase):
    """R-1/R-2 回流：文件版本低于 config 当前版本 → 拒绝初始化，
    不得改写既有轮次元数据；stdout 保持纯 JSON；--new-run 为显式出路"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        # q10 形态：根单文件 v1 源 + draft/ 子目录 + 既有 r1/r2/r5（r5 无 started_at）
        os.makedirs(os.path.join(self.dir, "draft"))
        os.makedirs(os.path.join(self.dir, ".review"))
        with open(os.path.join(self.dir, "paper.docx"), "wb") as f:
            f.write(b"PK\x03\x04dummy")
        with open(os.path.join(self.dir, "draft", "draft.md"), "w",
                  encoding="utf-8") as f:
            f.write(DRAFT_V1)
        with open(os.path.join(self.dir, "draft", "draft-v2.md"), "w",
                  encoding="utf-8") as f:
            f.write(DRAFT_V1.replace("背景介绍", "背景介绍（修订）"))
        cfg = {
            "schema": 2, "paper_dir": self.dir.replace("\\", "/"),
            "doctype": "thesis", "layout": "flat-v2.1",
            "versions": {"v1": {"source_root": ".", "draft": "draft/draft.md",
                                "response": None, "source_file": "paper.docx"}},
            "current_version": "v5",
            "rounds": {
                "r1": {"version": "v1", "started_at": "2026-10-01T00:00:00+08:00"},
                "r2": {"version": "v2", "started_at": "2026-10-02T00:00:00+08:00"},
                "r5": {"version": "v5"},
            },
            "current_round": "r5",
            "exemptions": [], "withdrawals": [], "adjudications": [],
        }
        self.cfg_path = os.path.join(self.dir, ".review", "config.json")
        with open(self.cfg_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        with open(self.cfg_path, "rb") as f:
            self.before = f.read()

    def tearDown(self):
        self.tmp.cleanup()

    def test_historic_version_refused_config_untouched(self):
        code, js, err = run_setup(self.dir, "--file",
                                  os.path.join("draft", "draft-v2.md"),
                                  "--re-review")
        self.assertEqual(code, 1)
        self.assertIsNotNone(js)            # stdout 仍是纯 JSON（R-2 口径）
        self.assertFalse(js["success"])
        self.assertTrue(any("--new-run" in p for p in js["problems"]), js)
        self.assertIn("r2", "\n".join(js["problems"]))   # 指出对应历史轮次
        with open(self.cfg_path, "rb") as f:
            self.assertEqual(f.read(), self.before)    # config 字节级未动

    def test_historic_version_new_run_escape(self):
        code, js, err = run_setup(self.dir, "--file",
                                  os.path.join("draft", "draft-v2.md"),
                                  "--new-run")
        self.assertEqual(code, 0, err)
        self.assertEqual(js["round"], "r6")
        with open(self.cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(cfg["current_version"], "v2")
        self.assertEqual(cfg["current_round"], "r6")
        # 既有 r5 元数据未被触碰
        self.assertNotIn("started_at", cfg["rounds"]["r5"])
        self.assertNotIn("re_review", cfg["rounds"]["r5"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
