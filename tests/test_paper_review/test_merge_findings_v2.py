#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_merge_findings_v2.py — merge_findings.py v2 双权威清单模式测试

覆盖（对应 handoff-20261108 §四/§七）：
  - revision_roadmap.md（R-#）+ deai_confirmed.md（D-#）双清单解析
  - 重叠打标项 → S-# 交叉引用，不重复计入 total
  - config.json 撤回记录 ID 不得复活（withdrawn_skipped）
  - 决议（Decision）与去AI质量评分提取
  - 缺 ID 时自动分配连续 R-#/D-#
  - 单侧清单缺失容忍；双缺 exit 1
  - v1 兼容模式回归见 test_merge_findings.py（本文件不重复）

运行：python tests/test_paper_review/test_merge_findings_v2.py
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
    HERE, "..", "..", "skills", "paper-review", "scripts", "merge_findings.py"))

ROADMAP = """# Revision Roadmap

## 决议
Major Revision（映射评分 6）

## P0 — 必须修改
| ID | 位置 | 问题 | 建议 | 来源席 | 工作量 | 验收标准 |
|----|------|------|------|--------|--------|----------|
| R-1 | §3.2 表3.1 | 加权综合分与分项不一致（69.11 vs 66.54） | 复算并更正 | S7,S2 | 1h | weighted_identity pass |
| R-2 | 摘要 | 过度声明「显著提升」无统计检验支撑 | 弱化措辞或补检验 | S6,S1 | 0.5h | 声明与证据匹配 |

## P1 — 重要修改
| ID | 位置 | 问题 | 建议 | 来源席 | 工作量 | 验收标准 |
|----|------|------|------|--------|--------|----------|
| R-3 | §2.1 | 术语混用 digital twin/数字孪生 | 统一术语表 | S4 | 1h | 全文一致 |
| R-9 | §4 | 数据集规模指控（已被撤回） | — | S6 | — | — |

## P2 — 建议修改
| ID | 位置 | 问题 | 建议 | 来源席 | 工作量 | 验收标准 |
|----|------|------|------|--------|--------|----------|
| R-4 | §5 第2段 | 过渡生硬 | 增加过渡句 | S4 | 0.2h | 编辑认可 |
"""

DEAI_CONFIRMED = """# 确认AI问题清单

| ID | 位置 | 问题 | 建议 | 支持技能 | 严重度 | 重叠标记 |
|----|------|------|------|----------|--------|----------|
| D-1 | §2.1 第3段 | 三段连续「不仅…而且…」对仗排比 | 拆散句式 | stop-slop,humanize-writing | P2 | — |
| D-2 | 摘要 | 过度声明属声称级AI夸大 | 弱化 | academic-humanizer | P1 | R-2 |
| D-3 | §6 | 综上所述空洞总结 | 删除 | humanizer-zh | P2 | — |

质量评分: 38/50
"""

CONFIG = {
    "schema": 2,
    "withdrawals": [{"id": "R-9", "reason": "文献核验不成立，撤回"}],
    "exemptions": [], "adjudications": [],
}


def run_merge(run_dir, *extra):
    p = subprocess.run([sys.executable, SCRIPT, "--run-dir", run_dir] + list(extra),
                       capture_output=True)
    out = p.stdout.decode("utf-8", errors="replace")
    err = p.stderr.decode("utf-8", errors="replace")
    js = json.loads(out) if out.strip().startswith("{") else None
    return p.returncode, js, err


class TestV2Merge(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run = os.path.join(self.tmp.name, "r1")
        os.makedirs(self.run)
        with open(os.path.join(self.run, "revision_roadmap.md"), "w",
                  encoding="utf-8") as f:
            f.write(ROADMAP)
        with open(os.path.join(self.run, "deai_confirmed.md"), "w",
                  encoding="utf-8") as f:
            f.write(DEAI_CONFIRMED)
        with open(os.path.join(self.tmp.name, "config.json"), "w",
                  encoding="utf-8") as f:
            json.dump(CONFIG, f, ensure_ascii=False)
        self.code, self.js, self.err = run_merge(self.run)
        with open(os.path.join(self.run, "merged_findings.md"),
                  encoding="utf-8") as f:
            self.merged = f.read()

    def tearDown(self):
        self.tmp.cleanup()

    def test_basic_counts(self):
        """内容4项（R-9撤回除外）+ 语言2项（D-2重叠除外）=6；P0=2 P1=1 P2=3"""
        self.assertEqual(self.code, 0, self.err)
        self.assertEqual(self.js["mode"], "v2")
        self.assertEqual(self.js["content_items"], 4)
        self.assertEqual(self.js["deai_items"], 2)
        self.assertEqual(self.js["p0"], 2)
        self.assertEqual(self.js["p1"], 1)
        self.assertEqual(self.js["p2"], 3)
        self.assertEqual(self.js["total"], 6)

    def test_withdrawn_not_revived(self):
        """撤回铁律：R-9 在 config.withdrawals → 不入清单，记入 withdrawn_skipped"""
        self.assertEqual(self.js["withdrawn_skipped"], ["R-9"])
        self.assertNotIn("数据集规模指控（已被撤回）", self.merged.split("## 已撤回项")[0])
        self.assertIn("R-9", self.merged)   # 已撤回节留痕

    def test_overlap_cross_reference(self):
        """D-2 重叠标记 R-2 → S-1 交叉引用，不重复计入"""
        self.assertEqual(self.js["cross_refs"], 1)
        self.assertIn("S-1", self.merged)
        self.assertIn("| S-1 | D-2 | R-2 |", self.merged)
        self.assertNotIn("过度声明属声称级AI夸大",
                         self.merged.split("## 语言发现")[1].split("## 重叠")[0])

    def test_decision_and_quality(self):
        self.assertEqual(self.js["decision"], "Major Revision")
        self.assertEqual(self.js["quality_score"], "38/50")
        self.assertIn("决议：**Major Revision**", self.merged)
        self.assertIn("38/50", self.merged)

    def test_ids_and_sections(self):
        for rid in ("R-1", "R-2", "R-3", "R-4", "D-1", "D-3"):
            self.assertIn(rid, self.merged)
        self.assertIn("## 内容发现（阶段1 Revision Roadmap）", self.merged)
        self.assertIn("## 语言发现（阶段2 确认AI问题清单，未重叠项）", self.merged)


class TestV2AutoIds(unittest.TestCase):
    """缺 ID 表格 → 自动分配连续 R-#/D-#"""

    def test_auto_ids(self):
        tmp = tempfile.TemporaryDirectory()
        run = os.path.join(tmp.name, "r1")
        os.makedirs(run)
        roadmap = ROADMAP.replace("| R-1 |", "|  |").replace("| R-2 |", "|  |")
        with open(os.path.join(run, "revision_roadmap.md"), "w",
                  encoding="utf-8") as f:
            f.write(roadmap)
        deai = DEAI_CONFIRMED.replace("| D-1 |", "|  |").replace(
            "| D-2 |", "|  |").replace("| D-3 |", "|  |")
        with open(os.path.join(run, "deai_confirmed.md"), "w",
                  encoding="utf-8") as f:
            f.write(deai)
        code, js, err = run_merge(run)
        with open(os.path.join(run, "merged_findings.md"), encoding="utf-8") as f:
            merged = f.read()
        self.assertEqual(code, 0, err)
        # R-9 位置被清空后自动编号仍应连续且不冲突
        self.assertIn("R-1", merged)
        self.assertIn("D-1", merged)
        self.assertEqual(js["total"], js["content_items"] + js["deai_items"])
        tmp.cleanup()


class TestV2MissingInputs(unittest.TestCase):
    def test_one_side_missing(self):
        tmp = tempfile.TemporaryDirectory()
        run = os.path.join(tmp.name, "r1")
        os.makedirs(run)
        with open(os.path.join(run, "revision_roadmap.md"), "w",
                  encoding="utf-8") as f:
            f.write(ROADMAP)
        code, js, err = run_merge(run)
        self.assertEqual(code, 0, err)
        self.assertEqual(js["sources_missing"], ["deai_confirmed.md"])
        self.assertEqual(js["content_items"], 5)   # 无 config：R-9 不撤回
        self.assertEqual(js["deai_items"], 0)
        tmp.cleanup()

    def test_both_missing_exit1(self):
        tmp = tempfile.TemporaryDirectory()
        run = os.path.join(tmp.name, "r1")
        os.makedirs(run)
        code, js, err = run_merge(run)
        self.assertEqual(code, 1)
        self.assertIn("两份权威清单均缺失", err)
        tmp.cleanup()


class TestV21Integrity(unittest.TestCase):
    """v2.1 条目15/16：空行不截断表格、R-ID 完整性校验、双口径计分。

    回归背景（备忘 §十一）：
    - 条目15：表格中间的手工空行曾使其后 R-40~R-45 全部静默丢失，
      而 sources_missing 仍为空；
    - 条目16：质量评分把重叠项也计入扣分（31 条 vs 实际保留 26 条），
      与协议「重叠不重复计入」矛盾。
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run = os.path.join(self.tmp.name, "r1")
        os.makedirs(self.run)

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, roadmap=None, deai=None, config=None):
        with open(os.path.join(self.run, "revision_roadmap.md"), "w",
                  encoding="utf-8") as f:
            f.write(roadmap if roadmap is not None else ROADMAP)
        if deai is not None:
            with open(os.path.join(self.run, "deai_confirmed.md"), "w",
                      encoding="utf-8") as f:
                f.write(deai)
        if config is not None:
            with open(os.path.join(self.tmp.name, "config.json"), "w",
                      encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False)

    def _merged(self):
        with open(os.path.join(self.run, "merged_findings.md"),
                  encoding="utf-8") as f:
            return f.read()

    def test_blank_line_mid_table_keeps_rows(self):
        """P0 表格中间插空行：空行后的行不得丢失（R-40~R-42 全进 merged）"""
        roadmap = ROADMAP.replace(
            "| R-2 | 摘要 | 过度声明「显著提升」无统计检验支撑 | 弱化措辞或补检验 | S6,S1 | 0.5h | 声明与证据匹配 |",
            "| R-2 | 摘要 | 过度声明「显著提升」无统计检验支撑 | 弱化措辞或补检验 | S6,S1 | 0.5h | 声明与证据匹配 |\n"
            "\n"
            "| R-40 | §6 | 结论段数据与表4不符 | 复算更正 | S7 | 1h | table_sums pass |\n"
            "| R-41 | §6.1 | 展望段空话 | 具体化 | S4 | 0.5h | 编辑认可 |\n"
            "| R-42 | 附录A | 附录表编号错乱 | 重排 | S1 | 0.5h | 编号连续 |")
        self._write(roadmap=roadmap)
        code, js, err = run_merge(self.run)
        merged = self._merged()
        self.assertEqual(code, 0, err)
        for rid in ("R-40", "R-41", "R-42"):
            self.assertIn(rid, merged)
        self.assertEqual(js["content_items"], 8)   # 原5（R-9未撤回）+3

    def test_second_table_in_section_collected(self):
        """同一 P 小节内散文后的第二个表格也被解析（本节全部表格口径）"""
        roadmap = ROADMAP.replace(
            "## P2 — 建议修改",
            "补充（主持人手记）：以下另表追加两项。\n"
            "\n"
            "| ID | 位置 | 问题 | 建议 | 来源席 | 工作量 | 验收标准 |\n"
            "|----|------|------|------|--------|--------|----------|\n"
            "| R-50 | §1 | 引言第二段冗长 | 压缩 | S4 | 0.3h | 编辑认可 |\n"
            "\n"
            "## P2 — 建议修改")
        self._write(roadmap=roadmap)
        code, js, err = run_merge(self.run)
        self.assertEqual(code, 0, err)
        self.assertIn("R-50", self._merged())

    def test_declared_id_lost_fails_exit1(self):
        """ID 列有 R-5 但「问题」列为空 → 不得静默丢行：exit 1 并列出 ID"""
        roadmap = ROADMAP.replace(
            "| R-4 | §5 第2段 | 过渡生硬 | 增加过渡句 | S4 | 0.2h | 编辑认可 |",
            "| R-4 | §5 第2段 | 过渡生硬 | 增加过渡句 | S4 | 0.2h | 编辑认可 |\n"
            "| R-5 | §7 |  | 待补 | S2 | 1h | — |")
        self._write(roadmap=roadmap)
        code, js, err = run_merge(self.run)
        self.assertEqual(code, 1)
        self.assertIsNone(js)
        self.assertIn("R-5", err)
        self.assertIn("未进入合并清单", err)
        # 失败的合并不得留下半成品输出
        self.assertFalse(os.path.exists(
            os.path.join(self.run, "merged_findings.md")))

    def test_declared_id_withdrawn_exempt(self):
        """desc 为空但 ID 在撤回记录中 → 豁免完整性校验，不 fail"""
        roadmap = ROADMAP.replace(
            "| R-9 | §4 | 数据集规模指控（已被撤回） | — | S6 | — | — |",
            "| R-9 | §4 |  | — | S6 | — | — |")
        self._write(roadmap=roadmap, config=CONFIG)
        code, js, err = run_merge(self.run)
        self.assertEqual(code, 0, err)
        self.assertNotIn("未进入合并清单", err)
        self.assertNotIn("R-9", self._merged().split("## 已撤回项")[0])

    def test_scored_total_basis(self):
        """条目16：confirmed_total=3（含重叠 D-2），scored_total=2；口径入 JSON 与产物"""
        self._write(deai=DEAI_CONFIRMED)
        code, js, err = run_merge(self.run)
        self.assertEqual(code, 0, err)
        self.assertEqual(js["deai_confirmed_total"], 3)
        self.assertEqual(js["deai_scored_total"], 2)
        self.assertEqual(js["deai_items"], 2)
        self.assertEqual(js["quality_score_basis"], "scored_total")
        self.assertEqual(js["quality_basis_warnings"], [])
        merged = self._merged()
        self.assertIn("scored_total=2", merged)
        self.assertIn("confirmed_total=3", merged)
        self.assertIn("38/50", merged)

    def test_declared_counts_mismatch_warns(self):
        """2c 声明的 confirmed_total 与表格实际不符 → stderr 告警 + JSON 记录，不中断"""
        deai = DEAI_CONFIRMED.replace(
            "质量评分: 38/50",
            "确认总数 confirmed_total: 9\n计分总数 scored_total: 8\n质量评分: 38/50")
        self._write(deai=deai)
        code, js, err = run_merge(self.run)
        self.assertEqual(code, 0, err)
        self.assertEqual(len(js["quality_basis_warnings"]), 2)
        self.assertIn("confirmed_total=9", err)
        self.assertIn("scored_total=8", err)

    def test_declared_counts_match_no_warning(self):
        deai = DEAI_CONFIRMED.replace(
            "质量评分: 38/50",
            "确认总数 confirmed_total: 3\n计分总数 scored_total: 2\n质量评分: 38/50")
        self._write(deai=deai)
        code, js, err = run_merge(self.run)
        self.assertEqual(code, 0, err)
        self.assertEqual(js["quality_basis_warnings"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
