#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_skill_invocation.py — SKILL.md 外部技能调用名静态回归测试（v2.0.1）

背景：阶段5.2 曾写 `Skill(skill="academic-research-skills:ars-reviewer")`，
但 `ars-reviewer` 是 ARS 插件的斜杠命令（commands/ars-reviewer.md，且
`disable-model-invocation: true`），不是技能；模型侧应直接调用技能
`academic-research-skills:academic-paper-reviewer` 并显式传 re-review 模式。
原调用必然失败并触发静默降级。本测试锁定该修复，防止回归。

运行：python tests/test_paper_review/test_skill_invocation.py
"""
import io
import os
import sys
import unittest

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.normpath(os.path.join(
    HERE, "..", "..", "skills", "paper-review", "SKILL.md"))


class TestSkillInvocations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SKILL, encoding="utf-8") as f:
            cls.text = f.read()

    def test_stage5_uses_reviewer_skill(self):
        """阶段5.2 必须调用 academic-paper-reviewer 技能"""
        self.assertIn(
            'Skill(skill="academic-research-skills:academic-paper-reviewer"',
            self.text)

    def test_no_command_used_as_skill(self):
        """不得把 ars-reviewer 命令名当技能调用（历史叙述性提及不受限）"""
        self.assertNotIn(
            'Skill(skill="academic-research-skills:ars-reviewer"', self.text)

    def test_reviewer_call_specifies_re_review_mode(self):
        """复审语义应显式指定 re-review 模式"""
        idx = self.text.index(
            'academic-research-skills:academic-paper-reviewer')
        window = self.text[idx:idx + 400]
        self.assertIn("re-review", window)

    def test_reviewer_call_is_read_only(self):
        idx = self.text.index(
            'academic-research-skills:academic-paper-reviewer')
        window = self.text[idx:idx + 400]
        self.assertIn("READ-ONLY", window)


if __name__ == "__main__":
    unittest.main(verbosity=2)