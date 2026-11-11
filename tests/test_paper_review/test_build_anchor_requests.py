#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_build_anchor_requests.py — build_anchor_requests.py 单元测试（v2.1 条目20）

覆盖：
  - merged_findings.md 全表解析：R-#/D-# 收集、S-# 交叉引用行跳过、id 去重
  - 位置解析四形态：L142 / 行 88 / §5.2 第3段 / 表3.1（structural 剥离行号）
  - 引文抽取：「」/“” 最长片段；<15字 weak；draft 多处命中 ambiguous；
    未命中 not_in_draft；无内嵌引文 without_quote——全部进 needs_manual_quote
  - 无行号项显式 structural_only；draft 唯一命中回填 draft_line
  - 与 anchor_map.py fill 串成闭环（条目14 校验：requests 数 == entries 数）
  - merged 缺失 exit 1；--help 可用；默认路径约定 {run_dir}

运行：python tests/test_paper_review/test_build_anchor_requests.py
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
SCRIPTS = os.path.normpath(os.path.join(
    HERE, "..", "..", "skills", "paper-review", "scripts"))
SCRIPT = os.path.join(SCRIPTS, "build_anchor_requests.py")
ANCHOR_MAP = os.path.join(SCRIPTS, "anchor_map.py")

MERGED = """# 合并审查发现（v2 双权威清单）

决议：**Major Revision**

## 内容发现（阶段1 Revision Roadmap）

### P0 — 必须修改

| ID | 位置 | 问题 | 建议 | 来源席 | 工作量 | 验收标准 |
|----|------|------|------|--------|--------|----------|
| R-1 | L142 §3.2 表3.1 | 加权综合分不一致，原文「加权综合分为69.11分，与分项汇总明显不符」 | 复算并更正 | S7 | 1h | pass |
| R-2 | §5.2 第3段 | 术语混用 digital twin/数字孪生 | 统一术语表 | S4 | 1h | 一致 |

### P1 — 重要修改

| ID | 位置 | 问题 | 建议 | 来源席 | 工作量 | 验收标准 |
|----|------|------|------|--------|--------|----------|
| R-3 | 行 88 | 摘要夸大其词 | 弱化「显著提升」措辞 | S6 | 0.5h | 匹配 |

## 语言发现（阶段2 确认AI问题清单，未重叠项）

| ID | 严重度 | 位置 | 问题 | 建议 | 支持技能 |
|----|--------|------|------|------|----------|
| D-1 | P2 | §2.1 第3段 | 三段连续「不仅…而且…」对仗排比 | 拆散句式 | stop-slop |

## 重叠交叉引用（去AI与阶段1同源，以阶段1为准）

| S-ID | 去AI项 | 内容项 | 说明 |
|------|--------|--------|------|
| S-1 | D-2 | R-2 | 内容问题，阶段1 已辖（以 R-2 为准） |

## 统计

P0: 2项 | P1: 1项 | P2: 1项 | 总计: 4项
"""

DRAFT = """# 论文标题

## 1 引言

无关的引言内容行。

## 3.2 结果

加权综合分为69.11分，与分项汇总明显不符，需要复核。

## 5.2 讨论

数字孪生与 digital twin 混用出现在这一段。
"""


def run_script(args):
    p = subprocess.run([sys.executable, SCRIPT] + args, capture_output=True)
    out = p.stdout.decode("utf-8", errors="replace")
    err = p.stderr.decode("utf-8", errors="replace")
    try:
        return p.returncode, json.loads(out), err
    except json.JSONDecodeError:
        return p.returncode, None, out + err


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run_dir = os.path.join(self.tmp.name, ".review", "r1")
        os.makedirs(self.run_dir)
        self.merged_path = os.path.join(self.run_dir, "merged_findings.md")
        with open(self.merged_path, "w", encoding="utf-8") as f:
            f.write(MERGED)
        self.draft_path = os.path.join(self.tmp.name, "draft.md")
        with open(self.draft_path, "w", encoding="utf-8") as f:
            f.write(DRAFT)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, *extra):
        args = ["--run-dir", self.run_dir, "--draft", self.draft_path] + list(extra)
        code, js, err = run_script(args)
        self.assertEqual(code, 0, err)
        out = js["output"]
        with open(out, encoding="utf-8") as f:
            payload = json.load(f)
        return js, payload

    def entry(self, payload, eid):
        for e in payload["entries"]:
            if e["id"] == eid:
                return e
        self.fail("entry %s not found in %s"
                  % (eid, [e["id"] for e in payload["entries"]]))


class TestParsing(Base):
    def test_default_paths(self):
        """--run-dir 默认约定：merged_findings.md 读入、anchor_requests.json 写出"""
        js, payload = self.build()
        self.assertTrue(js["output"].endswith("anchor_requests.json"))
        self.assertEqual(payload["generated_by"], "build_anchor_requests.py")

    def test_ids_collected_and_s_skipped(self):
        js, payload = self.build()
        ids = [e["id"] for e in payload["entries"]]
        self.assertEqual(ids, ["R-1", "R-2", "R-3", "D-1"])   # S-1 交叉引用行不生成
        self.assertEqual(js["stats"]["total"], 4)

    def test_loc_formats(self):
        _js, payload = self.build()
        e1 = self.entry(payload, "R-1")
        self.assertEqual(e1["draft_line"], 142)               # L142
        self.assertEqual(e1["structural"], "§3.2 表3.1")      # 行号已剥离
        self.assertFalse(e1.get("structural_only"))
        e3 = self.entry(payload, "R-3")
        self.assertEqual(e3["draft_line"], 88)                # 行 88
        e2 = self.entry(payload, "R-2")
        self.assertIsNone(e2["draft_line"])
        self.assertEqual(e2["structural"], "§5.2 第3段")
        self.assertTrue(e2["structural_only"])                # 无行号 → 显式标注

    def test_quote_extraction_and_flags(self):
        js, payload = self.build()
        e1 = self.entry(payload, "R-1")
        self.assertEqual(e1["quote"], "加权综合分为69.11分，与分项汇总明显不符")
        self.assertNotIn("weak", e1)
        self.assertNotIn("ambiguous", e1)
        e3 = self.entry(payload, "R-3")                       # 「显著提升」4字 → weak
        self.assertEqual(e3["quote"], "显著提升")
        self.assertTrue(e3["weak"])
        d1 = self.entry(payload, "D-1")                       # 「不仅…而且…」→ weak
        self.assertTrue(d1["weak"])
        # 含省略号的示意性引文跳过存在性核查，不得误报 not_in_draft
        self.assertNotIn("not_in_draft", d1)
        self.assertEqual(js["stats"]["not_in_draft"], 0)
        e2 = self.entry(payload, "R-2")                       # 无内嵌引文
        self.assertEqual(e2["quote"], "")
        self.assertEqual(js["stats"]["without_quote"], 1)
        self.assertEqual(js["stats"]["with_quote"], 3)
        self.assertEqual(js["stats"]["weak"], 2)

    def test_needs_manual_quote_listed(self):
        """weak / 无引文项都进待补清单，不得静默丢弃"""
        js, payload = self.build()
        manual_ids = {m["id"] for m in payload["needs_manual_quote"]}
        self.assertTrue({"R-2", "R-3", "D-1"} <= manual_ids)
        self.assertEqual(set(js["needs_manual_quote"]), manual_ids)
        # count 统计条目数（同一 id 可有多条原因），与清单长度一致
        self.assertEqual(js["needs_manual_count"], len(payload["needs_manual_quote"]))
        reasons = {m["id"]: m["reason"] for m in payload["needs_manual_quote"]}
        self.assertIn("无内嵌引文", reasons["R-2"])

    def test_stats_structural_only(self):
        js, _payload = self.build()
        self.assertEqual(js["stats"]["structural_only"], 2)   # R-2、D-1 无行号

    def test_no_draft_skips_uniqueness(self):
        """不提供 --draft：跳过唯一性核查，不报 not_in_draft/ambiguous"""
        code, js, err = run_script(["--run-dir", self.run_dir])
        self.assertEqual(code, 0, err)
        self.assertEqual(js["stats"]["ambiguous"], 0)
        self.assertEqual(js["stats"]["not_in_draft"], 0)


class TestDraftChecks(Base):
    def test_unique_hit_backfills_draft_line(self):
        """位置无行号但引文在 draft 唯一命中 → 回填 draft_line，撤掉 structural_only"""
        merged = MERGED.replace(
            "| R-2 | §5.2 第3段 | 术语混用 digital twin/数字孪生 | 统一术语表 | S4 | 1h | 一致 |",
            "| R-2 | §5.2 | 混用问题，原文「数字孪生与 digital twin 混用出现在这一段」 | 统一 | S4 | 1h | 一致 |")
        with open(self.merged_path, "w", encoding="utf-8") as f:
            f.write(merged)
        _js, payload = self.build()
        e2 = self.entry(payload, "R-2")
        self.assertEqual(e2["draft_line"], 13)                # DRAFT 中该行行号
        self.assertFalse(e2.get("structural_only"))

    def test_ambiguous_quote_in_draft(self):
        draft = DRAFT + "\n加权综合分为69.11分，与分项汇总明显不符，需要复核。（重复段）\n"
        with open(self.draft_path, "w", encoding="utf-8") as f:
            f.write(draft)
        js, payload = self.build()
        e1 = self.entry(payload, "R-1")
        self.assertTrue(e1["ambiguous"])
        self.assertEqual(js["stats"]["ambiguous"], 1)
        manual_ids = {m["id"] for m in payload["needs_manual_quote"]}
        self.assertIn("R-1", manual_ids)

    def test_not_in_draft_flagged(self):
        merged = MERGED.replace(
            "加权综合分为69.11分，与分项汇总明显不符",
            "这句话根本不在草稿里面出现的所谓原文引文")
        with open(self.merged_path, "w", encoding="utf-8") as f:
            f.write(merged)
        js, payload = self.build()
        e1 = self.entry(payload, "R-1")
        self.assertTrue(e1["not_in_draft"])
        self.assertEqual(js["stats"]["not_in_draft"], 1)
        manual_ids = {m["id"] for m in payload["needs_manual_quote"]}
        self.assertIn("R-1", manual_ids)


class TestErrorsAndCli(unittest.TestCase):
    def test_missing_merged_exit1(self):
        tmp = tempfile.TemporaryDirectory()
        run_dir = os.path.join(tmp.name, "r1")
        os.makedirs(run_dir)
        code, js, err = run_script(["--run-dir", run_dir])
        self.assertEqual(code, 1)
        self.assertIsNone(js)
        self.assertIn("merged_findings.md", err)
        tmp.cleanup()

    def test_help(self):
        p = subprocess.run([sys.executable, SCRIPT, "--help"], capture_output=True)
        out = p.stdout.decode("utf-8", errors="replace")
        self.assertEqual(p.returncode, 0)
        for flag in ("--run-dir", "--merged", "--draft", "--output"):
            self.assertIn(flag, out)

    def test_id_dedup_across_tables(self):
        """同一 ID 出现在两个表（如手工误贴）只生成一条请求"""
        tmp = tempfile.TemporaryDirectory()
        run_dir = os.path.join(tmp.name, "r1")
        os.makedirs(run_dir)
        merged = MERGED.replace(
            "## 统计",
            "### P2 — 建议修改\n\n"
            "| ID | 位置 | 问题 | 建议 | 来源席 | 工作量 | 验收标准 |\n"
            "|----|------|------|------|--------|--------|----------|\n"
            "| R-1 | L200 | 重复出现的 R-1「另一段完全不同的引文内容测试」 | — | S4 | — | — |\n\n"
            "## 统计")
        with open(os.path.join(run_dir, "merged_findings.md"), "w",
                  encoding="utf-8") as f:
            f.write(merged)
        code, js, err = run_script(["--run-dir", run_dir])
        self.assertEqual(code, 0, err)
        with open(js["output"], encoding="utf-8") as f:
            payload = json.load(f)
        ids = [e["id"] for e in payload["entries"]]
        self.assertEqual(ids.count("R-1"), 1)
        tmp.cleanup()


class TestFillClosure(Base):
    """条目20 与条目14 串成闭环：build 产物直接喂 anchor_map.py fill"""

    def test_build_then_fill(self):
        js, payload = self.build()
        # tex 源含 R-1 引文原句 → 应 resolved
        tex = os.path.join(self.tmp.name, "main.tex")
        with open(tex, "w", encoding="utf-8") as f:
            f.write("\\begin{document}\n加权综合分为69.11分，与分项汇总明显不符。\n"
                    "\\end{document}\n")
        review = self.run_dir
        p = subprocess.run([sys.executable, ANCHOR_MAP, "--review-dir", review,
                            "init", "--source", tex, "--format", "tex",
                            "--draft", self.draft_path], capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8", "replace"))
        p = subprocess.run([sys.executable, ANCHOR_MAP, "--review-dir", review,
                            "fill", "--requests", js["output"]], capture_output=True)
        out = p.stdout.decode("utf-8", "replace")
        self.assertEqual(p.returncode, 0, out + p.stderr.decode("utf-8", "replace"))
        fill_js = json.loads(out)
        # requests 数 == entries 数（条目14 校验由 fill 内部执行，等式破坏会 exit 1）
        self.assertEqual(fill_js["entries_total"], js["stats"]["total"])
        with open(os.path.join(review, "anchor_map.json"), encoding="utf-8") as f:
            data = json.load(f)
        by_id = {e["id"]: e for e in data["entries"]}
        self.assertEqual(by_id["R-1"]["status"], "resolved")
        self.assertEqual(by_id["R-1"]["source_loc"], "main.tex:2")
        # 无引文的 R-2 → structural_only 保留，不静默丢弃
        self.assertEqual(by_id["R-2"]["status"], "structural_only")
        self.assertEqual(by_id["R-2"]["structural"], "§5.2 第3段")


if __name__ == "__main__":
    unittest.main(verbosity=2)
