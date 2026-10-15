#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_merge_findings.py — merge_findings.py 单元测试（含 B4 白名单防噪声）

覆盖：
  - discussion_minutes.md 小节白名单：叙述性小节（参与角色/分歧记录/评分汇总）
    中含 P0/P1/P2 字样的散文与表格行不得解析为发现（li-paper 6条/xue 7条噪声的回归）
  - 共识发现小节（### P0/P1/P2 — 必须/重要/建议修改）表格正常解析
  - deai_log.md 残留问题条目解析（白名单不适用于该文件）
  - peer_reports.md 结构化发现解析
  - 去重与统计 JSON 输出

运行：python tests/test_paper_review/test_merge_findings.py
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

# 含叙述性噪声的研讨纪要（复现 li-paper/xue-paper 实测噪声场景）
MINUTES = """# 多智能体研讨纪要

## 参与角色
本次研讨由 A1-方法论批评家、A2-领域专家 参与。角色分工见 P1 级说明文档，
另有一位角色临时缺席。

## 共识发现
### P0 — 必须修改
| # | 位置 | 问题 | 建议 | 支持角色 |
|---|------|------|------|----------|
| 1 | §2.1 第3段 | 引用错误：文献[12]结论与原文不符 | 核对原文后改写引用句 | A1、A2 |

### P1 — 重要修改
| # | 位置 | 问题 | 建议 | 支持角色 |
|---|------|------|------|----------|
| 1 | §3.2 第1段 | AI痕迹：三段连续「不仅…而且…」对仗排比 | 拆散句式 | A3 |

### P2 — 建议修改
| # | 位置 | 问题 | 建议 | 支持角色 |
|---|------|------|------|----------|
| 1 | §4 第2段 | 措辞：过渡生硬 | 增加过渡句 | A5 |

## 分歧记录
- [P0] 分歧：A4 认为结论过度延伸属 P0，A2 认为仅 P1；记录各方观点如下，交用户裁决。
- 角色 A1 补充：此处涉及数据错误争议，未达成共识。

## 评分汇总
| 角色 | 方法论 | 写作 | 创新性 | 总体 |
|------|--------|------|--------|------|
| A1 | 7 | 6 | 7 | 6.5 |
| A2 | 8 | 7 | 7 | 7.3 |

## 决议信
尊敬的作者：您的稿件存在结构问题，我们建议 Major Revision。此散文段不应成为发现。
"""

DEAI_LOG = """# 去AI审查日志

| # | 技能 | 发现数 | 修改数 | 时间 |
|---|------|--------|--------|------|
| 1 | stop-slop | 5 | 3 | 10:00 |
| 2 | academic-humanizer | 4 | 4 | 10:05 |
| 3 | humanize-writing | 2 | 2 | 10:10 |
| 4 | humanizer-zh | 3 | 1 | 10:15 |

## 残留问题
- [P1] 位置：§1.1 第2段
  问题：套话残留「综上所述」未清除
  建议：删除或改写
"""

PEER_REPORTS = """# 同行评审报告

Editorial Decision: Major Revision

## 结构化发现
- [P0] 位置：§2.3 第4段
  问题：逻辑断裂：实验设置与结论之间缺乏因果链
  建议：补充消融实验或弱化结论
- [P1] 位置：§1.2 第1段
  问题：术语不一致：digital twin 与 数字孪生 混用
  建议：统一术语表
"""


def run_merge(review_dir):
    p = subprocess.run([sys.executable, SCRIPT, "--review-dir", review_dir],
                       capture_output=True)
    out = p.stdout.decode("utf-8", errors="replace")
    err = p.stderr.decode("utf-8", errors="replace")
    return p.returncode, json.loads(out), err


class TestMergeWhitelist(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.review = self.tmp.name
        for name, content in (("discussion_minutes.md", MINUTES),
                              ("deai_log.md", DEAI_LOG),
                              ("peer_reports.md", PEER_REPORTS)):
            with open(os.path.join(self.review, name), "w", encoding="utf-8") as f:
                f.write(content)
        self.code, self.js, self.err = run_merge(self.review)
        with open(os.path.join(self.review, "merged_findings.md"), encoding="utf-8") as f:
            self.merged = f.read()

    def tearDown(self):
        self.tmp.cleanup()

    def test_exit_and_sources(self):
        self.assertEqual(self.code, 0, self.err)
        self.assertTrue(self.js["success"] if "success" in self.js else True)
        self.assertEqual(sorted(self.js["sources_parsed"]),
                         ["deai_log.md", "discussion_minutes.md", "peer_reports.md"])
        self.assertEqual(self.js["sources_missing"], [])

    def test_prose_sections_not_parsed(self):
        """B4 回归：参与角色/分歧记录/评分汇总/决议信 中的 P0/P1 字样散文与表格不得入清单"""
        for noise in ("分歧", "交用户裁决", "临时缺席", "尊敬的作者", "Major Revision。此散文段",
                      "A1 | 7 | 6"):
            self.assertNotIn(noise, self.merged,
                             "叙述性小节内容泄漏进合并清单: %r" % noise)

    def test_consensus_tables_parsed(self):
        """共识发现三小节各1条应全部入清单"""
        self.assertIn("引用错误：文献[12]结论与原文不符", self.merged)
        self.assertIn("三段连续「不仅…而且…」对仗排比", self.merged)
        self.assertIn("过渡生硬", self.merged)

    def test_deai_residual_parsed(self):
        self.assertIn("套话残留「综上所述」未清除", self.merged)

    def test_peer_findings_parsed(self):
        self.assertIn("逻辑断裂：实验设置与结论之间缺乏因果链", self.merged)
        self.assertIn("术语不一致", self.merged)

    def test_counts(self):
        # P0: 纪要1 + 同行评审1 = 2；P1: 纪要1 + 去AI残留1 + 同行评审1 = 3；P2: 纪要1 = 1
        self.assertEqual(self.js["p0"], 2)
        self.assertEqual(self.js["p1"], 3)
        self.assertEqual(self.js["p2"], 1)
        self.assertEqual(self.js["total"], 6)


class TestMissingSources(unittest.TestCase):
    def test_missing_ignored(self):
        tmp = tempfile.TemporaryDirectory()
        with open(os.path.join(tmp.name, "peer_reports.md"), "w", encoding="utf-8") as f:
            f.write(PEER_REPORTS)
        code, js, err = run_merge(tmp.name)
        self.assertEqual(code, 0, err)
        self.assertEqual(js["sources_parsed"], ["peer_reports.md"])
        self.assertEqual(sorted(js["sources_missing"]),
                         ["deai_log.md", "discussion_minutes.md"])
        self.assertEqual(js["total"], 2)
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
