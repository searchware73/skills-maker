#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_docs_cli_consistency.py — 条目24 守卫①：文档 ↔ 脚本 CLI 一致性

背景（备忘 §十一 条目13/24）：SKILL.md 用法表曾教 --source/--format/--focus，
而 setup_env.py argparse 不接受，用户照文档执行直接 unrecognized arguments——
「文档教一套、脚本收另一套」。本守卫把这类漂移变成测试失败：

  A. SKILL.md 用法块（/paper-review …）与用法表（`--flag` 行）⊆ setup_env.py argparse
  B. setup_env.py argparse ⊆ 用法块 ∪ 用法表 ∪ setup_env 调用行 ∪ {--help}
  C. SKILL.md 与 references/*.md 中提及 `scripts/<name>` 的行上出现的全部 --flag
     ⊆ 该脚本 argparse（含全部子命令；numeric_checks/ 取目录内 .py 并集）
  D. 全部 scripts/*.py 与 numeric_checks/ 实测 --help 退出码 0（CLAUDE.md 脚本规范）

排除项：--help 为 argparse 自动旗标、不在 AST 常量中，A–C 比较时剔除（由 D 实测覆盖）。
旗标提取用 AST（add_argument 字符串常量），不执行脚本、不依赖 --help 文本格式。

运行：python tests/test_paper_review/test_docs_cli_consistency.py
"""
import ast
import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SKILL_DIR = os.path.join(REPO_ROOT, "skills", "paper-review")
SCRIPTS_DIR = os.path.join(SKILL_DIR, "scripts")
REFERENCES_DIR = os.path.join(SKILL_DIR, "references")
SKILL_MD = os.path.join(SKILL_DIR, "SKILL.md")

# 行内 --flag token（markdown 表格分隔线 |---| 不含字母开头段，天然不匹配）
FLAG_TOKEN_RE = re.compile(r"--[A-Za-z][A-Za-z0-9_-]*")
# scripts/<name>[.py] 提及（脚本清单表用裸名、无 scripts/ 前缀，不会被误扫；
# 「## 脚本清单（scripts/，均支持 --help…」的全角逗号不满足 [A-Za-z] 起始，同样不匹配）
SCRIPT_MENTION_RE = re.compile(r"scripts/([A-Za-z][A-Za-z0-9_-]*)(?:\.py)?")

SETUP_ENV = "setup_env"
# 用法表至少应覆盖这些参数（防止正则失配导致的空集假通过）
EXPECTED_TABLE_FLAGS = {
    "--section", "--source", "--format", "--doctype", "--focus", "--quick",
    "--rounds", "--no-fix", "--re-review", "--response", "--panel",
    "--new-run", "--expert-comments",
}
# 文档中至少应出现这些脚本调用（防止提及扫描空转）
EXPECTED_MENTIONED_SCRIPTS = {
    SETUP_ENV, "resume", "conversion_audit", "anchor_map", "bib_lint",
    "diff_scope", "numeric_checks", "expert_reconcile", "merge_findings",
    "track_revisions", "convergence_check", "migrate_rounds", "migrate_layout",
}


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def ast_flags(py_path):
    """AST 收集该文件全部 add_argument("--x") 字符串常量（含子命令，取并集）。"""
    tree = ast.parse(read(py_path), filename=py_path)
    flags = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument"):
            for arg in node.args:
                if (isinstance(arg, ast.Constant)
                        and isinstance(arg.value, str)
                        and arg.value.startswith("--")):
                    flags.add(arg.value)
    return flags


def script_flags(name):
    """脚本名（不带 .py）→ argparse 旗标集合；numeric_checks 为目录并集；
    脚本不存在返回 None（由 test_referenced_files_exist.py 负责存在性，
    本文件仅在 C 项断言中给出明确报错）。"""
    py = os.path.join(SCRIPTS_DIR, name + ".py")
    if os.path.isfile(py):
        return ast_flags(py)
    directory = os.path.join(SCRIPTS_DIR, name)
    if os.path.isdir(directory):
        flags = set()
        for fn in sorted(os.listdir(directory)):
            if fn.endswith(".py"):
                flags |= ast_flags(os.path.join(directory, fn))
        return flags
    return None


def doc_files():
    """SKILL.md + references/*.md（条目24 规定的扫描范围）。"""
    files = [SKILL_MD]
    for fn in sorted(os.listdir(REFERENCES_DIR)):
        if fn.endswith(".md"):
            files.append(os.path.join(REFERENCES_DIR, fn))
    return files


def usage_table_flags(text):
    """SKILL.md 用法表（| 参数 | 说明 | 默认 |）首列 `--flag` 集合。"""
    flags = set()
    in_table = False
    for line in text.splitlines():
        if line.startswith("| 参数 |"):
            in_table = True
            continue
        if in_table:
            if not line.startswith("|"):
                in_table = False
                continue
            m = re.match(r"^\|\s*`(--[A-Za-z0-9_-]+)", line)
            if m:
                flags.add(m.group(1))
    return flags


def usage_block_flags(text):
    """## 用法 后 ``` 围栏内 /paper-review 用法块的全部 --flag。"""
    m = re.search(r"## 用法\s*\n+```\n(.*?)```", text, re.DOTALL)
    return set(FLAG_TOKEN_RE.findall(m.group(1))) if m else set()


def invocation_flags(texts):
    """{脚本名: 该行出现的旗标集合}——仅统计提及 scripts/<name> 的行（同行范围）。"""
    result = {}
    for text in texts:
        for line in text.splitlines():
            names = SCRIPT_MENTION_RE.findall(line)
            if not names:
                continue
            flags = set(FLAG_TOKEN_RE.findall(line)) - {"--help"}
            for name in names:
                result.setdefault(name, set()).update(flags)
    return result


class TestUsageTableVsSetupEnv(unittest.TestCase):
    """A/B 双向：用法块+用法表 ↔ setup_env.py argparse（条目13 逐项对齐）。"""

    @classmethod
    def setUpClass(cls):
        cls.text = read(SKILL_MD)
        cls.table = usage_table_flags(cls.text)
        cls.block = usage_block_flags(cls.text)
        cls.argv = script_flags(SETUP_ENV)
        cls.invoked = invocation_flags([cls.text]).get(SETUP_ENV, set())

    def test_meta_table_not_vacuous(self):
        # 正则失配会得空集 → A/B 全部假通过；先用期望集合钉死下限
        self.assertTrue(self.table >= EXPECTED_TABLE_FLAGS,
                        "用法表解析缺旗标: %s" % sorted(EXPECTED_TABLE_FLAGS - self.table))
        self.assertTrue(self.block, "未找到 /paper-review 用法块")

    def test_meta_argparse_not_vacuous(self):
        self.assertIsNotNone(self.argv, "setup_env.py 不存在或无法解析")
        self.assertIn("--file", self.argv)

    def test_table_flags_accepted_by_setup_env(self):
        diff = self.table - self.argv
        self.assertFalse(diff, "用法表教了 setup_env.py 不接受的参数: %s" % sorted(diff))

    def test_usage_block_flags_accepted_by_setup_env(self):
        diff = self.block - self.argv - {"--help"}
        self.assertFalse(diff, "用法块教了 setup_env.py 不接受的参数: %s" % sorted(diff))

    def test_setup_env_flags_all_documented(self):
        # B 反向：脚本收了但三处文档面都没教的旗标 = 隐藏参数漂移
        documented = self.table | self.block | self.invoked | {"--help", "--file"}
        diff = self.argv - documented
        self.assertFalse(
            diff,
            "setup_env.py 接受但用法块/用法表/0.1 调用行均未提及的参数: %s" % sorted(diff))

    def test_setup_env_expected_flags_present(self):
        # 防止文档与脚本「同步删除」某参数绕过 B 项（G1 基线旗标清单）
        missing = (EXPECTED_TABLE_FLAGS | {"--file"}) - self.argv
        self.assertFalse(missing, "setup_env.py 缺少基线参数: %s" % sorted(missing))


class TestInvocationsVsScripts(unittest.TestCase):
    """C 项：文档全部脚本调用行的旗标 ⊆ 对应脚本 argparse。"""

    @classmethod
    def setUpClass(cls):
        cls.files = doc_files()
        cls.inv = invocation_flags([read(p) for p in cls.files])

    def test_meta_expected_scripts_mentioned(self):
        missing = EXPECTED_MENTIONED_SCRIPTS - set(self.inv)
        self.assertFalse(missing, "文档中未见这些脚本的调用行: %s" % sorted(missing))

    def test_invocation_flags_accepted(self):
        problems = []
        for name in sorted(self.inv):
            flags = self.inv[name]
            argv = script_flags(name)
            if argv is None:
                problems.append("%s: 脚本不存在（scripts/%s[.py]）" % (name, name))
                continue
            diff = flags - argv - {"--help"}
            if diff:
                problems.append("%s: 文档调用行用了脚本不接受的参数 %s"
                                % (name, sorted(diff)))
        self.assertFalse(problems, "\n".join(problems))


class TestHelpExitZero(unittest.TestCase):
    """D 项：CLAUDE.md 脚本规范——全部脚本 --help 可用（退出码 0）。"""

    def targets(self):
        for fn in sorted(os.listdir(SCRIPTS_DIR)):
            path = os.path.join(SCRIPTS_DIR, fn)
            if fn.endswith(".py") and os.path.isfile(path):
                yield path
            elif os.path.isdir(path) and not fn.startswith(("_", ".")):
                # numeric_checks/：python <dir> --help 走 __main__.py
                if os.path.isfile(os.path.join(path, "__main__.py")):
                    yield path

    def test_all_help_exit_zero(self):
        failures = []
        for path in self.targets():
            proc = subprocess.run(
                [sys.executable, path, "--help"],
                capture_output=True, timeout=60)
            out = proc.stdout.decode("utf-8", errors="replace")
            if proc.returncode != 0 or "usage" not in out.lower():
                failures.append("%s: rc=%d stderr=%s" % (
                    os.path.basename(path), proc.returncode,
                    proc.stderr.decode("utf-8", errors="replace")[:200]))
        self.assertFalse(failures, "--help 不可用:\n" + "\n".join(failures))

    def test_meta_targets_not_vacuous(self):
        names = [os.path.basename(p) for p in self.targets()]
        self.assertIn("setup_env.py", names)
        self.assertIn("numeric_checks", names)
        self.assertGreaterEqual(len(names), 13, "脚本目标数异常: %s" % names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
