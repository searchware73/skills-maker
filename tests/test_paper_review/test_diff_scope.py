#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_diff_scope.py — diff_scope.py 版本变更区域定位单元测试

覆盖：
  - 节内段落改写 → replace hunk 行范围正确、heading 定位到该节标题
  - 新增整节（含 ## 标题）→ insert hunk + new_headings 命中
  - 删除一行 → delete hunk（new_range=[i,i] 两行之间位置）；文件头删除 → [1,1]
  - 无变更 → hunks 空、changed_lines=0
  - --context：0 不合并；近距变更扩张合并；间距 > 2N 不合并
  - --output：markdown 含表格与「## 新增章节/标题」列表；缺省不写文件
  - 文件不存在 → exit 1；参数缺失/负 context → exit 2

运行：python tests/test_paper_review/test_diff_scope.py
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
    HERE, "..", "..", "skills", "paper-review", "scripts", "diff_scope.py"))


def run(args):
    """运行 diff_scope.py，返回 (exit_code, stdout_json, stderr)"""
    p = subprocess.run([sys.executable, SCRIPT] + args, capture_output=True)
    out = p.stdout.decode("utf-8", errors="replace")
    err = p.stderr.decode("utf-8", errors="replace")
    try:
        return p.returncode, json.loads(out), err
    except json.JSONDecodeError:
        return p.returncode, None, out + err


# ────────────────────────── 固定样本 ──────────────────────────

# 11 行；new 版第 10 行被改写 → replace hunk 定位到「## 2 方法」
REPLACE_OLD = """# 论文标题

## 1 引言

背景段落第一行。
背景段落第二行。

## 2 方法

方法描述第一行。
方法描述第二行。
"""

REPLACE_NEW = """# 论文标题

## 1 引言

背景段落第一行。
背景段落第二行。

## 2 方法

方法描述第一行（修订）。
方法描述第二行。
"""

# 在「## 1 引言」与「## 3 实验」之间插入整节（含标题）→ insert + new_headings
INSERT_OLD = """# 草稿

## 1 引言

引言内容。

## 3 实验

实验内容。
"""

INSERT_NEW = """# 草稿

## 1 引言

引言内容。

## 2 方法

方法内容。

## 3 实验

实验内容。
"""

# 删除中间一行「第二行内容。」→ delete hunk
DELETE_OLD = """# 标题

## 1 引言

第一行内容。
第二行内容。
第三行内容。
"""

DELETE_NEW = """# 标题

## 1 引言

第一行内容。
第三行内容。
"""

# 两处近距变更（第5、9行），间距3行：context=2 合并、context=1 不合并
CTX_OLD = """L1
L2
L3
L4
OLD5
L6
L7
L8
OLD9
L10
"""

CTX_NEW = """L1
L2
L3
L4
NEW5
L6
L7
L8
NEW9
L10
"""


class TmpCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        return path

    def diff(self, old_text, new_text, extra=()):
        old = self.write("old.md", old_text)
        new = self.write("new.md", new_text)
        code, js, err = run(["--old", old, "--new", new] + list(extra))
        self.assertEqual(code, 0, err)
        self.assertIsNotNone(js, err)
        return js


class TestReplaceHunk(TmpCase):
    def test_replace_in_section(self):
        js = self.diff(REPLACE_OLD, REPLACE_NEW)
        self.assertTrue(js["success"])
        for key in ("success", "old", "new", "hunks", "changed_lines",
                    "new_headings", "output"):
            self.assertIn(key, js)
        self.assertEqual(len(js["hunks"]), 1)
        h = js["hunks"][0]
        self.assertEqual(h["kind"], "replace")
        self.assertEqual(h["new_range"], [10, 10])   # 1-based 含头含尾
        self.assertEqual(h["old_range"], [10, 10])
        self.assertEqual(h["heading"], "## 2 方法")   # 定位到所在节标题
        self.assertEqual(h["lines"], 1)
        self.assertEqual(js["changed_lines"], 1)
        self.assertEqual(js["new_headings"], [])
        self.assertIsNone(js["output"])              # 缺省不写文件
        # 路径为 posix 绝对路径
        self.assertNotIn("\\", js["old"])
        self.assertTrue(js["old"].endswith("/old.md"))
        self.assertTrue(js["new"].endswith("/new.md"))


class TestInsertSection(TmpCase):
    def test_insert_whole_section(self):
        js = self.diff(INSERT_OLD, INSERT_NEW)
        self.assertEqual(len(js["hunks"]), 1)
        h = js["hunks"][0]
        self.assertEqual(h["kind"], "insert")
        self.assertEqual(h["new_range"], [7, 10])    # 新增的4行
        self.assertEqual(h["old_range"], [6, 6])     # 插入点两行之间位置
        self.assertEqual(h["heading"], "## 2 方法")   # hunk 首行即新节标题
        self.assertEqual(h["lines"], 4)
        self.assertEqual(js["changed_lines"], 4)
        self.assertEqual(js["new_headings"], ["## 2 方法"])   # 新标题命中


class TestDeleteHunk(TmpCase):
    def test_delete_one_line(self):
        js = self.diff(DELETE_OLD, DELETE_NEW)
        self.assertEqual(len(js["hunks"]), 1)
        h = js["hunks"][0]
        self.assertEqual(h["kind"], "delete")
        self.assertEqual(h["old_range"], [6, 6])     # 旧文件第6行被删
        self.assertEqual(h["new_range"], [5, 5])     # 删除点前一行行号
        self.assertEqual(h["heading"], "## 1 引言")
        self.assertEqual(h["lines"], 1)
        self.assertEqual(js["changed_lines"], 1)
        self.assertEqual(js["new_headings"], [])

    def test_delete_at_file_head(self):
        js = self.diff("x\ny\nz\n", "y\nz\n")
        self.assertEqual(len(js["hunks"]), 1)
        h = js["hunks"][0]
        self.assertEqual(h["kind"], "delete")
        self.assertEqual(h["old_range"], [1, 1])
        self.assertEqual(h["new_range"], [1, 1])     # 删在文件头 → [1,1]
        self.assertIsNone(h["heading"])              # 前方无标题


class TestNoChange(TmpCase):
    def test_identical_files(self):
        js = self.diff(REPLACE_OLD, REPLACE_OLD)
        self.assertTrue(js["success"])
        self.assertEqual(js["hunks"], [])
        self.assertEqual(js["changed_lines"], 0)
        self.assertEqual(js["new_headings"], [])


class TestContext(TmpCase):
    def test_context_zero_separate_hunks(self):
        js = self.diff(CTX_OLD, CTX_NEW)             # 缺省 context=0
        self.assertEqual(len(js["hunks"]), 2)
        self.assertEqual(js["hunks"][0]["new_range"], [5, 5])
        self.assertEqual(js["hunks"][1]["new_range"], [9, 9])
        self.assertEqual(js["changed_lines"], 2)

    def test_context_two_merges_nearby(self):
        js = self.diff(CTX_OLD, CTX_NEW, ["--context", "2"])
        self.assertEqual(len(js["hunks"]), 1)        # 间距3 ≤ 2N=4 → 合并
        h = js["hunks"][0]
        self.assertEqual(h["kind"], "replace")
        self.assertEqual(h["new_range"], [3, 10])    # 前后各扩2行
        self.assertEqual(h["old_range"], [3, 10])
        self.assertEqual(h["lines"], 2)              # 核心行数不含 context
        self.assertIsNone(h["heading"])              # 样本无标题
        self.assertEqual(js["changed_lines"], 2)

    def test_context_one_gap_too_wide(self):
        js = self.diff(CTX_OLD, CTX_NEW, ["--context", "1"])
        self.assertEqual(len(js["hunks"]), 2)        # 间距3 > 2N=2 → 不合并
        self.assertEqual(js["hunks"][0]["new_range"], [4, 6])
        self.assertEqual(js["hunks"][1]["new_range"], [8, 10])


class TestOutputMd(TmpCase):
    def test_output_markdown(self):
        out = os.path.join(self.dir, "scope.md")
        js = self.diff(INSERT_OLD, INSERT_NEW, ["--output", out])
        self.assertEqual(js["output"], out.replace("\\", "/"))
        self.assertTrue(os.path.isfile(out))
        with open(out, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("| # | 类型 | 新版行范围 | 所在章节 | 变更行数 |", content)
        self.assertIn("|---|", content)
        self.assertIn("| 1 | insert | 7-10 | ## 2 方法 | 4 |", content)
        self.assertIn("## 新增章节/标题", content)
        self.assertIn("- ## 2 方法", content)

    def test_output_empty_diff_note(self):
        out = os.path.join(self.dir, "scope.md")
        js = self.diff(REPLACE_OLD, REPLACE_OLD, ["--output", out])
        with open(out, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("## 新增章节/标题", content)
        self.assertIn("无变更", content)


class TestErrors(TmpCase):
    def test_missing_file_exit_1(self):
        old = self.write("old.md", "a\n")
        code, js, err = run(["--old", old,
                             "--new", os.path.join(self.dir, "missing.md")])
        self.assertEqual(code, 1)
        self.assertIn("错误", err)

    def test_missing_arg_exit_2(self):
        old = self.write("old.md", "a\n")
        code, js, err = run(["--old", old])
        self.assertEqual(code, 2)

    def test_negative_context_exit_2(self):
        old = self.write("old.md", "a\n")
        new = self.write("new.md", "a\n")
        code, js, err = run(["--old", old, "--new", new, "--context", "-1"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
