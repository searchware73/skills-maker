#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_check_artifacts.py — check_artifacts.py 单元测试（v2.1 条目11/18）

背景（备忘 §十一 条目11）：Workflow 只按代理是否正常结束计数，被 triggering
request 劫持的席位（全昌寿稿 S4、于小岚稿 S3）不写报告也算 agents_done。
本套用例锁定门禁语义：

  - 恰好 N 份且非空 → exit 0 complete
  - 缺失/空文件 → exit 1 + redispatch 只列缺失项（不重跑整阶段）
  - 预期外多余文件 → exit 1（「恰好」判定）
  - 前缀匹配：S1 匹配 S1-EIC统筹.md；同记号多文件任一非空即算齐
  - deai_audits 四技能模式（条目18）；目录不存在 → 全部 redispatch
  - --help 可用；--expect 为空 exit 2

运行：python tests/test_paper_review/test_check_artifacts.py
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
    HERE, "..", "..", "skills", "paper-review", "scripts", "check_artifacts.py"))

SEATS = ["S1-EIC统筹", "S2-方法论", "S3-领域", "S4-写作编辑",
         "S5-跨学科视角", "S6-魔鬼代言人", "S7-数值审计"]
EXPECT7 = "S1,S2,S3,S4,S5,S6,S7"
SKILLS = "stop-slop,academic-humanizer,humanize-writing,humanizer-zh"


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
        self.run = os.path.join(self.tmp.name, "r1")
        self.seats_dir = os.path.join(self.run, "seat_reports")
        os.makedirs(self.seats_dir)
        for seat in SEATS:
            with open(os.path.join(self.seats_dir, seat + ".md"), "w",
                      encoding="utf-8") as f:
                f.write("# %s 席位报告\n\n[P1] 发现一条问题。\n" % seat)

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, subdir="seat_reports", expect=EXPECT7, *extra):
        return run_script(["--run-dir", self.run, "--subdir", subdir,
                           "--expect", expect] + list(extra))

    def write_seat(self, name, content):
        with open(os.path.join(self.seats_dir, name), "w", encoding="utf-8") as f:
            f.write(content)


class TestComplete(Base):
    def test_all_seats_present(self):
        code, js, err = self.check()
        self.assertEqual(code, 0, err)
        self.assertTrue(js["complete"])
        self.assertTrue(js["success"])
        self.assertEqual(js["missing"], [])
        self.assertEqual(js["redispatch"], [])
        self.assertEqual(len(js["found"]), 7)

    def test_prefix_match_full_label_expect(self):
        """--expect 也接受全名记号（S4-写作编辑）"""
        code, js, _err = self.check(expect="S4-写作编辑")
        # 其余 6 席成为 unexpected → 不完整，但 S4 本身被找到
        self.assertEqual(code, 1)
        self.assertIn("S4-写作编辑.md", js["found"]["S4-写作编辑"])
        self.assertEqual(len(js["unexpected"]), 6)


class TestIncomplete(Base):
    def test_missing_seat_redispatch_only_that_one(self):
        """条目11 回归：S4 被劫持未落盘 → redispatch 只列 S4，不重跑整阶段"""
        os.remove(os.path.join(self.seats_dir, "S4-写作编辑.md"))
        code, js, err = self.check()
        self.assertEqual(code, 1)
        self.assertFalse(js["complete"])
        self.assertEqual(js["missing"], ["S4"])
        self.assertEqual(js["redispatch"], ["S4"])
        self.assertIn("S4", err)

    def test_empty_seat_file(self):
        self.write_seat("S3-领域.md", "  \n\n")
        code, js, _err = self.check()
        self.assertEqual(code, 1)
        self.assertEqual(js["empty"], ["S3"])
        self.assertEqual(js["redispatch"], ["S3"])

    def test_unexpected_file_fails(self):
        """「恰好 N 席」：多余文件（可能是劫持代理写错位置）→ 不完整"""
        self.write_seat("无关回答.md", "关于临时文件命令的说明……")
        code, js, _err = self.check()
        self.assertEqual(code, 1)
        self.assertEqual(js["unexpected"], ["无关回答.md"])
        self.assertEqual(js["redispatch"], [])   # 无缺失：不需重派，需人工核对

    def test_missing_and_empty_combined(self):
        os.remove(os.path.join(self.seats_dir, "S7-数值审计.md"))
        self.write_seat("S2-方法论.md", "")
        code, js, _err = self.check()
        self.assertEqual(code, 1)
        self.assertEqual(sorted(js["redispatch"]), ["S2", "S7"])

    def test_token_satisfied_by_any_nonempty_match(self):
        """同记号多文件（补派产生第二份）：任一非空即算齐，多份不判 unexpected"""
        self.write_seat("S4-写作编辑-补派.md", "# S4 补派报告\n\n内容。\n")
        code, js, err = self.check()
        self.assertEqual(code, 0, err)
        self.assertTrue(js["complete"])
        self.assertEqual(len(js["found"]["S4"]), 2)

    def test_dir_missing_all_redispatch(self):
        code, js, _err = self.check(subdir="deai_audits", expect=SKILLS)
        self.assertEqual(code, 1)
        self.assertEqual(js["missing"], SKILLS.split(","))
        self.assertEqual(len(js["redispatch"]), 4)


class TestDeaiAudits(Base):
    """条目18：阶段2 四技能审计同门禁"""

    def setUp(self):
        super().setUp()
        self.audits = os.path.join(self.run, "deai_audits")
        os.makedirs(self.audits)
        for sk in SKILLS.split(","):
            with open(os.path.join(self.audits, sk + ".md"), "w",
                      encoding="utf-8") as f:
                f.write("# %s 审计\n\n| 模式 | 位置 | 证据 |\n" % sk)

    def test_four_audits_complete(self):
        code, js, err = self.check(subdir="deai_audits", expect=SKILLS)
        self.assertEqual(code, 0, err)
        self.assertTrue(js["complete"])

    def test_missing_audit_redispatch_single(self):
        os.remove(os.path.join(self.audits, "humanizer-zh.md"))
        code, js, _err = self.check(subdir="deai_audits", expect=SKILLS)
        self.assertEqual(code, 1)
        self.assertEqual(js["redispatch"], ["humanizer-zh"])


class TestCli(unittest.TestCase):
    def test_help(self):
        p = subprocess.run([sys.executable, SCRIPT, "--help"], capture_output=True)
        out = p.stdout.decode("utf-8", errors="replace")
        self.assertEqual(p.returncode, 0)
        self.assertIn("usage", out)
        for flag in ("--run-dir", "--subdir", "--expect", "--ext"):
            self.assertIn(flag, out)

    def test_empty_expect_exit2(self):
        code, js, err = run_script(["--run-dir", ".", "--subdir", "seat_reports",
                                    "--expect", " , "])
        self.assertEqual(code, 2)
        self.assertIsNone(js)
        self.assertIn("--expect", err)


if __name__ == "__main__":
    unittest.main(verbosity=2)
