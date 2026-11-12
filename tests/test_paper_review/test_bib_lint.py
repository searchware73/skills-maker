#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_bib_lint.py — bib_lint.py 引文格式检查单元测试

覆盖：
  - GB/T 7714 模式（li/xue 风格夹具）：empty_conference / double_period /
    comma_space / page_format / bilingual_pairing / arxiv（离线 warn），
    by_check 计数与 markdown 判定表内容
  - BibTeX 模式：key_year / name_order / arxiv；嵌套花括号字段解析
  - 干净条目零告警回归（防误报：`: 45-50` 冒号后空格属正常）
  - 无条目文件 → success + stderr 警告；输入不存在 exit 1；无 --input exit 2
  - 输出路径解析：--run-dir 缺省 / --output 覆盖 / 输入同目录兜底

运行：python tests/test_paper_review/test_bib_lint.py
（测试一律不传 --online，不触网）
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
    HERE, "..", "..", "skills", "paper-review", "scripts", "bib_lint.py"))


def run(args, cwd=None):
    """运行 bib_lint.py，返回 (exit_code, stdout_json, stderr)"""
    p = subprocess.run([sys.executable, SCRIPT] + args,
                       capture_output=True, cwd=cwd)
    out = p.stdout.decode("utf-8", errors="replace")
    err = p.stderr.decode("utf-8", errors="replace")
    try:
        return p.returncode, json.loads(out), err
    except json.JSONDecodeError:
        return p.returncode, None, out + err


def write(path, content):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def to_posix(path):
    return os.path.abspath(path).replace("\\", "/")


class TestGbtMode(unittest.TestCase):
    """li/xue 风格 GB/T 7714 著录列表：6 条问题条目 + 1 条干净条目"""

    GBT = (
        "[1] ZHANG W, LI M. Conference paper title[C]//. Beijing: Press, 2019: 12-20.\n"
        "[2] SMITH J. Methods of things.. Misc Notes[J]. Some Journal, 2020, 5(2): 30-35.\n"
        "[3] Smith J,2020. Another title[J]. Some Journal, 2020, 8(1): 10-15.\n"
        "[4] BROWN A. Big study[J]. Wide Pages, 2021, 3(2): 2020 - 2025.\n"
        "[5] 张三, 李四. 中文论文题目[J]. 中国期刊, 2020, 10(2): 45-50.\n"
        "[6] DOE J. Preprint title[EB/OL]. arXiv:2001.12345, 2020.\n"
        "[7] WILSON K. Clean study[J]. Journal Name, 2021, 12(3): 45-50.\n"
    )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.run_dir = os.path.join(self.dir, "run")
        self.src = os.path.join(self.dir, "refs.md")
        write(self.src, self.GBT)
        self.code, self.js, self.err = run(
            ["--input", self.src, "--run-dir", self.run_dir])
        self.md = os.path.join(self.run_dir, "bib_lint.md")

    def tearDown(self):
        self.tmp.cleanup()

    def test_json_summary(self):
        self.assertEqual(self.code, 0, self.err)
        self.assertTrue(self.js["success"])
        self.assertEqual(self.js["mode"], "gbt")
        self.assertEqual(self.js["entries"], 7)
        self.assertEqual(self.js["errors"], 2)     # empty_conference + double_period
        self.assertEqual(self.js["warnings"], 4)   # comma_space/page_format/arxiv/bilingual
        self.assertEqual(self.js["by_check"], {
            "empty_conference": 1,
            "double_period": 1,
            "comma_space": 1,
            "page_format": 1,
            "arxiv": 1,
            "bilingual_pairing": 1,
        })
        self.assertFalse(self.js["online"])          # 未传 --online，离线
        self.assertIsNone(self.js["online_error"])
        self.assertEqual(self.js["output"], to_posix(self.md))
        self.assertTrue(os.path.isfile(self.md))

    def test_md_table(self):
        with open(self.md, encoding="utf-8-sig") as f:
            content = f.read()
        self.assertIn("| 条目 | 检查 | 级别 | 证据 | 判定 |", content)
        self.assertIn("| [1] | empty_conference | error |", content)
        self.assertIn("| [2] | double_period | error |", content)
        self.assertIn("| [3] | comma_space | warn |", content)
        self.assertIn("| [4] | page_format | warn |", content)
        self.assertIn("| [5] | bilingual_pairing | warn |", content)
        self.assertIn("| [6] | arxiv | warn |", content)
        self.assertIn("arXiv 预印本，核实是否已正式发表", content)
        self.assertIn("需修改", content)   # error 判定
        self.assertIn("需核实", content)   # warn 判定
        self.assertIn("合计: 7 条目, 2 errors, 4 warnings。", content)
        # 干净条目 [7] 不出现在判定表
        self.assertNotIn("| [7] |", content)

    def test_default_output_next_to_input(self):
        """无 --run-dir / --output 时输出到输入同目录 bib_lint.md"""
        code, js, err = run(["--input", self.src])
        self.assertEqual(code, 0, err)
        expected = to_posix(os.path.join(self.dir, "bib_lint.md"))
        self.assertEqual(js["output"], expected)
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "bib_lint.md")))


class TestBibMode(unittest.TestCase):
    """BibTeX 模式：key_year / name_order / arxiv；嵌套花括号解析"""

    BIB = """@article{smith2019fast,
  author = {John Smith},
  title = {A Fast Method for {Nested Braces} Handling},
  journal = {Journal of Speed},
  year = {2020},
  pages = {10--20}
}

@inproceedings{li2021deep,
  author = {Li, Ming and Wang Fang},
  title = {Deep Learning for Simulation},
  booktitle = {Proc. of Intl. Conf.},
  year = {2021},
  note = {arXiv preprint arXiv:2101.00001}
}
"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.src = os.path.join(self.dir, "refs.bib")
        write(self.src, self.BIB)
        self.out = os.path.join(self.dir, "sub", "report.md")
        self.code, self.js, self.err = run(
            ["--input", self.src, "--output", self.out])

    def tearDown(self):
        self.tmp.cleanup()

    def test_bib_checks(self):
        self.assertEqual(self.code, 0, self.err)
        self.assertTrue(self.js["success"])
        self.assertEqual(self.js["mode"], "bib")
        self.assertEqual(self.js["entries"], 2)
        self.assertEqual(self.js["errors"], 0)
        self.assertEqual(self.js["warnings"], 4)
        self.assertEqual(self.js["by_check"], {
            "key_year": 1,      # smith2019fast: 2019 ≠ year 2020
            "name_order": 2,    # John Smith / Wang Fang
            "arxiv": 1,         # li2021deep note 含 arXiv（离线保持 warn）
        })
        self.assertFalse(self.js["online"])
        self.assertIsNone(self.js["online_error"])

    def test_bib_output_flag_and_table(self):
        """--output 覆盖路径（含不存在子目录）+ 判定表内容"""
        self.assertEqual(self.js["output"], to_posix(self.out))
        self.assertTrue(os.path.isfile(self.out))
        with open(self.out, encoding="utf-8-sig") as f:
            content = f.read()
        self.assertIn("| smith2019fast | key_year | warn |", content)
        self.assertIn("citekey 年份 2019 ≠ year 字段 2020", content)
        self.assertIn("| smith2019fast | name_order | warn |", content)
        self.assertIn("疑似未按 GB/T 姓前名后倒装：John Smith", content)
        self.assertIn("| li2021deep | arxiv | warn |", content)
        self.assertIn("| li2021deep | name_order | warn |", content)
        self.assertIn("合计: 2 条目, 0 errors, 4 warnings。", content)


class TestCleanRegression(unittest.TestCase):
    """干净条目零告警回归（防误报）"""

    CLEAN_GBT = (
        "[1] WILSON K. Clean study[J]. Journal Name, 2021, 12(3): 45-50.\n"
        "[2] DOE J, SMITH A. Another clean work[C]//Proc. of Conf. Berlin: "
        "Springer, 2019: 100-110.\n"
        "[3] LEE B, et al. See https://example.com/a,b for details[J]. "
        "Tools J, 2022, 1(1): 3-9.\n"
    )

    CLEAN_BIB = """@article{wang2021clean,
  author = {Wang, Fang},
  title = {A Clean Paper},
  journal = {Clean Journal},
  year = {2021},
  pages = {1--9}
}
"""

    def _assert_clean(self, filename, content, mode):
        tmp = tempfile.TemporaryDirectory()
        src = os.path.join(tmp.name, filename)
        write(src, content)
        code, js, err = run(["--input", src, "--run-dir", tmp.name])
        self.assertEqual(code, 0, err)
        self.assertTrue(js["success"])
        self.assertEqual(js["mode"], mode)
        self.assertEqual(js["errors"], 0, err)
        self.assertEqual(js["warnings"], 0, "误报: %s" % js["by_check"])
        self.assertEqual(js["by_check"], {})
        tmp.cleanup()

    def test_clean_gbt_zero_findings(self):
        # `: 45-50` 冒号后空格属正常；URL 中逗号不计 comma_space；[C]//有会议名
        self._assert_clean("clean.md", self.CLEAN_GBT, "gbt")

    def test_clean_bib_zero_findings(self):
        self._assert_clean("clean.bib", self.CLEAN_BIB, "bib")


class TestPandocEscaped(unittest.TestCase):
    """R-6 回流：pandoc 把 [N]/[J]/[C] 转义为 \\[N\\]/\\[J\\]/\\[C\\]，
    修复前整节参考文献被解析为 0 条（易误判「无参考文献」）"""

    ESCAPED = (
        "\\[1\\] ZHANG W, LI M. Conference paper title\\[C\\]//. "
        "Beijing: Press, 2019: 12-20.\n"
        "\\[2\\] 张三, 李四. 中文论文题目\\[J\\]. 中国期刊, 2020, 10(2): 45-50.\n"
        "\\[3\\] WILSON K. Clean study\\[J\\]. Journal Name, 2021, 12(3): 45-50.\n"
    )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.run_dir = os.path.join(self.dir, "run")
        self.src = os.path.join(self.dir, "refs.md")
        write(self.src, self.ESCAPED)

    def tearDown(self):
        self.tmp.cleanup()

    def test_escaped_entries_parsed(self):
        code, js, err = run(["--input", self.src, "--run-dir", self.run_dir])
        self.assertEqual(code, 0, err)
        self.assertTrue(js["success"])
        self.assertEqual(js["mode"], "gbt")
        self.assertEqual(js["entries"], 3)      # 修复前为 0
        self.assertNotIn("未解析到任何条目", err)

    def test_escaped_checks_still_fire(self):
        """还原后 [C]//. 空会议名与 CJK 双语配对检查照常触发"""
        code, js, err = run(["--input", self.src, "--run-dir", self.run_dir])
        self.assertEqual(code, 0, err)
        self.assertEqual(js["by_check"].get("empty_conference"), 1)
        self.assertEqual(js["by_check"].get("bilingual_pairing"), 1)


class TestEmptyAndErrors(unittest.TestCase):
    def test_no_entries_success_with_stderr_warning(self):
        tmp = tempfile.TemporaryDirectory()
        src = os.path.join(tmp.name, "prose.md")
        write(src, "这里没有任何著录条目\njust prose lines\n")
        code, js, err = run(["--input", src, "--run-dir", tmp.name])
        self.assertEqual(code, 0, err)
        self.assertTrue(js["success"])
        self.assertEqual(js["entries"], 0)
        self.assertEqual(js["errors"], 0)
        self.assertEqual(js["warnings"], 0)
        self.assertIn("警告", err)   # stderr 警告
        self.assertTrue(os.path.isfile(os.path.join(tmp.name, "bib_lint.md")))
        tmp.cleanup()

    def test_missing_input_exit1(self):
        tmp = tempfile.TemporaryDirectory()
        code, js, err = run(["--input", os.path.join(tmp.name, "nope.md")])
        self.assertEqual(code, 1)
        self.assertIn("不存在", err)
        tmp.cleanup()

    def test_no_input_exit2(self):
        code, js, err = run([])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
