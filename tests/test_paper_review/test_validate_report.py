#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_validate_report.py — validate_report.py 单元测试（v2.1 条目17）

背景（备忘 §十一 条目17）：于小岚稿实测出现 7→9 P0、39→47 项的中间态数字，
全靠人工发现。本套用例锁定「报告计数不一致时 fail」及各项核对：

  - 全对齐 → success；合并统计/质量评分/决议/反查统计任一不符 → exit 1 + problems
  - 三轨启用但报告缺「反查统计」行 → fail；anchor_map.json 缺失 → 跳过不 fail
  - seat_reports 缺份数（--seats）或空文件 → fail
  - 交付副本缺失 / 内容不一致 / INDEX.md 缺行 → fail；--re-review 命名
  - chain.md 缺本轮节 → fail；--paper-dir 未给 --round → exit 2

夹具中 merged_findings.md 由 merge_findings.py 真跑生成（不手写，保证统计节
格式与被核对方一致）。

运行：python tests/test_paper_review/test_validate_report.py
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
SCRIPTS = os.path.normpath(os.path.join(
    HERE, "..", "..", "skills", "paper-review", "scripts"))
SCRIPT = os.path.join(SCRIPTS, "validate_report.py")
MERGE = os.path.join(SCRIPTS, "merge_findings.py")

ROADMAP = """# Revision Roadmap

## 决议
Major Revision（映射评分 6）

## P0 — 必须修改
| ID | 位置 | 问题 | 建议 | 来源席 | 工作量 | 验收标准 |
|----|------|------|------|--------|--------|----------|
| R-1 | §3.2 | 加权综合分与分项不一致 | 复算并更正 | S7 | 1h | pass |
| R-2 | 摘要 | 过度声明无检验支撑 | 弱化措辞 | S6 | 0.5h | 匹配 |

## P1 — 重要修改
| ID | 位置 | 问题 | 建议 | 来源席 | 工作量 | 验收标准 |
|----|------|------|------|--------|--------|----------|
| R-3 | §2.1 | 术语混用 | 统一术语表 | S4 | 1h | 一致 |
"""

DEAI = """# 确认AI问题清单

| ID | 位置 | 问题 | 建议 | 支持技能 | 严重度 | 重叠标记 |
|----|------|------|------|----------|--------|----------|
| D-1 | §2.1 第3段 | 对仗排比堆叠 | 拆散句式 | stop-slop | P2 | — |
| D-2 | 摘要 | 过度声明属夸大 | 弱化 | academic-humanizer | P1 | R-2 |

确认总数 confirmed_total: 2
计分总数 scored_total: 1
质量评分: 45/50
"""

# 与 merge 输出对齐的报告骨架：内容3 + 语言1（D-2 重叠）；P0 2 / P1 1 / P2 1 总 4
REPORT = """# 最终审查报告

## 2. 定位坐标说明

工作坐标=draft 行号；源坐标=tex 文件:行；结构坐标=编号+引文。
- 反查统计：resolved 1 / ambiguous 1 / not_found 1 / structural_only 1（共 4 条）

## 3. 阶段1 合并面板

- Editorial Decision：**Major Revision**（盲审口径；映射评分 6）

## 4. 阶段2 去AI审查

- 确认AI问题清单：语言级 1 条 / 声称级 1 条；重叠打标 1 条
- 质量评分：**45/50**

## 5. 合并发现与修改执行

- 合并统计：P0 2 / P1 1 / P2 1，总计 4（内容 3 + 语言 1；
  交叉引用 1 不重复计入；撤回跳过 0）
"""

ANCHOR_MAP = {"entries": [
    {"id": "R-1", "status": "resolved"},
    {"id": "R-2", "status": "ambiguous"},
    {"id": "R-3", "status": "not_found"},
    {"id": "D-1", "status": "structural_only"},
]}


def run_script(args):
    p = subprocess.run([sys.executable, SCRIPT] + args, capture_output=True)
    out = p.stdout.decode("utf-8", errors="replace")
    err = p.stderr.decode("utf-8", errors="replace")
    try:
        return p.returncode, json.loads(out), err
    except json.JSONDecodeError:
        return p.returncode, None, out + err


class Base(unittest.TestCase):
    """搭一套完整对齐的产物树：paper/.review/{chain.md, r1/...} + reports + INDEX"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.paper = os.path.join(self.tmp.name, "paper")
        self.review = os.path.join(self.paper, ".review")
        self.run = os.path.join(self.review, "r1")
        os.makedirs(os.path.join(self.run, "seat_reports"))
        with open(os.path.join(self.run, "revision_roadmap.md"), "w",
                  encoding="utf-8") as f:
            f.write(ROADMAP)
        with open(os.path.join(self.run, "deai_confirmed.md"), "w",
                  encoding="utf-8") as f:
            f.write(DEAI)
        # merged_findings.md 由 merge_findings.py 真跑生成
        p = subprocess.run([sys.executable, MERGE, "--run-dir", self.run],
                           capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8", "replace"))
        self.merge_js = json.loads(p.stdout.decode("utf-8"))
        self.report_path = os.path.join(self.run, "final_report.md")
        self._write_report(REPORT)
        with open(os.path.join(self.run, "anchor_map.json"), "w",
                  encoding="utf-8") as f:
            json.dump(ANCHOR_MAP, f, ensure_ascii=False)
        for seat in ("S1", "S2"):
            with open(os.path.join(self.run, "seat_reports", seat + ".md"), "w",
                      encoding="utf-8") as f:
                f.write("# %s 席位报告\n\n发现问题若干。\n" % seat)
        with open(os.path.join(self.review, "chain.md"), "w",
                  encoding="utf-8") as f:
            f.write("# 版本谱系 — paper\n\n## r1（v1，2026-11-11）\n\n- 决议：Major Revision\n")
        os.makedirs(os.path.join(self.paper, "reports"))
        self.copy_path = os.path.join(self.paper, "reports", "r1-审阅报告.md")
        shutil.copyfile(self.report_path, self.copy_path)
        with open(os.path.join(self.tmp.name, "INDEX.md"), "w",
                  encoding="utf-8") as f:
            f.write("# INDEX\n\n| 论文 | 类型 | 轮次 | 决议 | 日期 | 报告 |\n"
                    "|------|------|------|------|------|------|\n"
                    "| paper | thesis | r1 | Major Revision | 2026-11-11 "
                    "| paper/reports/r1-审阅报告.md |\n")

    def tearDown(self):
        self.tmp.cleanup()

    def _write_report(self, text):
        with open(self.report_path, "w", encoding="utf-8") as f:
            f.write(text)

    def validate(self, *extra):
        args = ["--run-dir", self.run, "--paper-dir", self.paper,
                "--round", "1", "--seats", "2"] + list(extra)
        return run_script(args)

    def assertPass(self, *extra):
        code, js, err = self.validate(*extra)
        self.assertEqual(code, 0, json.dumps(js, ensure_ascii=False) if js else err)
        self.assertTrue(js["success"])
        self.assertEqual(js["problems"], [])
        return js

    def assertFail(self, keyword, *extra):
        code, js, err = self.validate(*extra)
        self.assertEqual(code, 1, err)
        self.assertFalse(js["success"])
        joined = "\n".join(js["problems"])
        self.assertIn(keyword, joined)
        return js


class TestAligned(Base):
    def test_all_pass(self):
        js = self.assertPass()
        self.assertEqual(js["checks"]["merge_stats"]["report"],
                         js["checks"]["merge_stats"]["merged"])
        self.assertEqual(js["checks"]["decision"]["report"], "Major")
        self.assertEqual(js["checks"]["quality"]["merged"], "45/50")
        self.assertEqual(js["checks"]["anchor"]["computed"], [1, 1, 1, 1, 4])
        self.assertEqual(js["checks"]["seats"]["found"], 2)
        self.assertTrue(js["checks"]["delivery"]["identical"])
        self.assertTrue(js["checks"]["delivery"]["index_row_found"])

    def test_no_paper_dir_skips_delivery(self):
        code, js, err = run_script(["--run-dir", self.run])
        self.assertEqual(code, 0, err)
        self.assertTrue(any("delivery" in s for s in js["skipped"]))

    def test_no_anchor_map_skips_check(self):
        os.remove(os.path.join(self.run, "anchor_map.json"))
        report = REPORT.replace(
            "- 反查统计：resolved 1 / ambiguous 1 / not_found 1 / structural_only 1（共 4 条）\n", "")
        self._write_report(report)
        shutil.copyfile(self.report_path, self.copy_path)
        js = self.assertPass()
        self.assertTrue(any("anchor" in s for s in js["skipped"]))


class TestBoldStatsTolerated(Base):
    """R-5 回流：合并统计行数字被 **粗体** 包裹不应报「未找到」"""

    def test_bold_stats_line_passes(self):
        report = REPORT.replace("合并统计：P0 2", "合并统计：**P0 2")
        report = report.replace("总计 4（内容", "总计 4**（内容")
        self.assertNotEqual(report, REPORT)
        self._write_report(report)
        shutil.copyfile(self.report_path, self.copy_path)
        js = self.assertPass()
        self.assertEqual(js["checks"]["merge_stats"]["report"],
                         js["checks"]["merge_stats"]["merged"])

    def test_bold_everywhere_stats_passes(self):
        """整行加粗 + 折行变化仍容错（squash 去空白与星号）"""
        report = REPORT.replace(
            "- 合并统计：P0 2 / P1 1 / P2 1，总计 4（内容 3 + 语言 1；",
            "- **合并统计：P0 2 / P1 1 / P2 1，总计 4（内容 3 + 语言 1；**")
        self.assertNotEqual(report, REPORT)
        self._write_report(report)
        shutil.copyfile(self.report_path, self.copy_path)
        self.assertPass()


class TestCountMismatchFails(Base):
    """核心回归：报告计数不一致时 fail（备忘条目17 实测缺陷）"""

    def test_total_mismatch(self):
        self._write_report(REPORT.replace("总计 4（", "总计 9（"))
        js = self.assertFail("总计 报告写 9")
        self.assertEqual(js["checks"]["merge_stats"]["merged"][3], 4)

    def test_p0_mismatch(self):
        self._write_report(REPORT.replace("P0 2 / P1 1", "P0 7 / P1 1"))
        self.assertFail("P0 报告写 7")

    def test_cross_ref_mismatch(self):
        self._write_report(REPORT.replace("交叉引用 1 不重复计入", "交叉引用 3 不重复计入"))
        self.assertFail("交叉引用 报告写 3")

    def test_merge_stats_line_missing(self):
        self._write_report(REPORT.replace("- 合并统计：", "- 统计说明："))
        self.assertFail("合并统计")

    def test_quality_mismatch(self):
        self._write_report(REPORT.replace("**45/50**", "**38/50**"))
        self.assertFail("质量评分不符")

    def test_decision_mismatch(self):
        self._write_report(REPORT.replace("**Major Revision**（盲审",
                                          "**Minor Revision**（盲审"))
        self.assertFail("决议不符")

    def test_anchor_stats_mismatch(self):
        self._write_report(REPORT.replace("resolved 1 /", "resolved 3 /"))
        self.assertFail("resolved 报告写 3")

    def test_anchor_line_missing_while_map_exists(self):
        self._write_report(REPORT.replace(
            "- 反查统计：resolved 1 / ambiguous 1 / not_found 1 / structural_only 1（共 4 条）\n", ""))
        self.assertFail("反查统计")


class TestSeatsAndDelivery(Base):
    def test_seat_count_mismatch(self):
        self.assertFail("席位报告数不符", "--seats", "7")

    def test_empty_seat_file_fails(self):
        with open(os.path.join(self.run, "seat_reports", "S2.md"), "w",
                  encoding="utf-8") as f:
            f.write("  \n")
        self.assertFail("S2.md")

    def test_copy_missing(self):
        os.remove(self.copy_path)
        self.assertFail("交付副本不存在")

    def test_copy_differs(self):
        with open(self.copy_path, "a", encoding="utf-8") as f:
            f.write("\n多出来的一行\n")
        self.assertFail("内容不一致")

    def test_index_row_missing(self):
        with open(os.path.join(self.tmp.name, "INDEX.md"), "w",
                  encoding="utf-8") as f:
            f.write("# INDEX\n\n| 论文 | 类型 | 轮次 | 决议 | 日期 | 报告 |\n"
                    "|------|------|------|------|------|------|\n")
        self.assertFail("INDEX.md 缺该篇报告行")

    def test_re_review_copy_name(self):
        os.remove(self.copy_path)
        copy2 = os.path.join(self.paper, "reports", "r1-复审报告.md")
        shutil.copyfile(self.report_path, copy2)
        with open(os.path.join(self.tmp.name, "INDEX.md"), "a",
                  encoding="utf-8") as f:
            f.write("| paper | thesis | r1 | Major Revision | 2026-11-11 "
                    "| paper/reports/r1-复审报告.md |\n")
        self.assertPass("--re-review")

    def test_chain_round_missing(self):
        with open(os.path.join(self.review, "chain.md"), "w",
                  encoding="utf-8") as f:
            f.write("# 版本谱系 — paper\n")
        self.assertFail("未见本轮 r1 节")

    def test_paper_dir_without_round_exit2(self):
        code, js, err = run_script(["--run-dir", self.run,
                                    "--paper-dir", self.paper])
        self.assertEqual(code, 2)
        self.assertIsNone(js)
        self.assertIn("--round", err)


class TestCli(unittest.TestCase):
    def test_help(self):
        p = subprocess.run([sys.executable, SCRIPT, "--help"], capture_output=True)
        out = p.stdout.decode("utf-8", errors="replace")
        self.assertEqual(p.returncode, 0)
        self.assertIn("usage", out)
        for flag in ("--run-dir", "--paper-dir", "--round", "--re-review",
                     "--seats", "--report", "--merged", "--index"):
            self.assertIn(flag, out)

    def test_missing_report_fails(self):
        tmp = tempfile.TemporaryDirectory()
        run = os.path.join(tmp.name, "r1")
        os.makedirs(run)
        code, js, err = run_script(["--run-dir", run])
        self.assertEqual(code, 1)
        self.assertIn("final_report.md 不存在", "\n".join(js["problems"]))
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
