#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_conversion_audit.py — conversion_audit.py 转换审计单元测试

覆盖：
  - tex（xue 风格夹具）：目录递归 glob、环境计数（table/table*/figure/tikzpicture/
    algorithm/equation）、draft md 计数、missing 对照、指针 "文件名:行号"
  - docx：w:tbl / w:drawing / m:oMath 计数（仿 test_anchor_map.make_docx 构造）
  - pdf：提取文本页标记计页（%% [PDF p.N] 与旧式 --- Page N ---）、
    真 .pdf 无 fitz/坏文件时 pages=null 降级、tables/figures/equations=null
  - draft 公式块（$$ 跨行 + \\[...\\]）与行内数学近似计数
  - --output 报告：计数对照表 / 疑似丢失清单 / 固定结论行
  - 参数错误退出码 2

运行：python tests/test_paper_review/test_conversion_audit.py
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(os.path.join(
    HERE, "..", "..", "skills", "paper-review", "scripts", "conversion_audit.py"))


def run(args):
    """运行 conversion_audit.py，返回 (exit_code, stdout_json, stderr)"""
    p = subprocess.run([sys.executable, SCRIPT] + args, capture_output=True)
    out = p.stdout.decode("utf-8", errors="replace")
    err = p.stderr.decode("utf-8", errors="replace")
    try:
        return p.returncode, json.loads(out), err
    except json.JSONDecodeError:
        return p.returncode, None, out + err


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def make_docx_raw(path, body):
    """构造最小合法 docx（扩展 test_anchor_map.make_docx：body 为原始 XML，
    根元素额外声明 math 命名空间 m）"""
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
           ' xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
           '<w:body>%s</w:body></w:document>' % body)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                   '</Types>')
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                   '</Relationships>')
        z.writestr("word/document.xml", doc)


class TestTexAudit(unittest.TestCase):
    """xue 风格 tex 夹具：目录源（main.tex + chapters/ch1.tex）vs 只有 1 表格的 draft"""

    # main.tex 行号：table=5，table*=8，figure=11，tikzpicture=14，
    #               algorithm=17，equation=20/23
    MAIN_TEX = r"""\documentclass{article}
\begin{document}
\section{Introduction}
Text with inline math $E=mc^2$ here.
\begin{table}[h]
\caption{表1 实验结果}
\end{table}
\begin{table*}[t]
\caption{表2 宽表（pandoc 常丢）}
\end{table*}
\begin{figure}[h]
\includegraphics{fig1.pdf}
\end{figure}
\begin{tikzpicture}
\draw (0,0) -- (1,1);
\end{tikzpicture}
\begin{algorithm}[t]
\caption{算法1}
\end{algorithm}
\begin{equation}
a = b + c
\end{equation}
\begin{equation}
d = e + f
\end{equation}
\input{chapters/ch1}
\end{document}
"""

    CH1_TEX = r"""\section{Method}
\begin{table}[h]
\caption{ch1 中的表}
\end{table}
"""

    DRAFT = """# 论文草稿

## 1. 引言

Some text about digital twins.

| Method | Accuracy |
|--------|----------|
| Baseline | 0.87 |

行内公式 $\\alpha$ 出现在这里。
"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.src = os.path.join(self.dir, "texsrc")
        os.makedirs(os.path.join(self.src, "chapters"))
        write(os.path.join(self.src, "main.tex"), self.MAIN_TEX)
        write(os.path.join(self.src, "chapters", "ch1.tex"), self.CH1_TEX)
        self.draft = os.path.join(self.dir, "draft.md")
        write(self.draft, self.DRAFT)
        self.code, self.js, self.err = run(
            ["--source", self.src, "--draft", self.draft])   # 目录 → tex 推断
        self.assertEqual(self.code, 0, self.err)

    def tearDown(self):
        self.tmp.cleanup()

    def test_format_inferred_and_output_null(self):
        self.assertTrue(self.js["success"])
        self.assertEqual(self.js["format"], "tex")        # 目录推断
        self.assertIsNone(self.js["output"])              # 缺省不写文件

    def test_source_counts(self):
        sc = self.js["source_counts"]
        self.assertEqual(sc["tables"], 3)                 # table×2 + table*×1 + ch1 表
        self.assertEqual(sc["figures"], 1)
        self.assertEqual(sc["algorithms"], 1)
        self.assertEqual(sc["diagrams"], 1)               # tikzpicture
        self.assertEqual(sc["equations"], 2)
        self.assertIsNone(sc["pages"])

    def test_draft_counts(self):
        dc = self.js["draft_counts"]
        self.assertEqual(dc["tables"], 1)
        self.assertEqual(dc["figures"], 0)
        self.assertEqual(dc["formula_blocks"], 0)
        self.assertEqual(dc["inline_math"], 1)            # $\alpha$ 一对

    def test_missing_counts(self):
        m = self.js["missing"]
        self.assertEqual(m["tables"], 2)                  # 3 - 1
        self.assertEqual(m["figures"], 1)
        self.assertEqual(m["algorithms"], 1)
        self.assertEqual(m["diagrams"], 1)
        self.assertEqual(m["equations"], 2)               # 2 - 0

    def test_missing_pointers(self):
        ptrs = self.js["missing_pointers"]
        locs = {(p["type"], p["loc"]) for p in ptrs}
        # 表指针按出现顺序取前 2 条（文件排序 chapters/ch1.tex < main.tex）
        self.assertIn(("table", "ch1.tex:2"), locs)
        self.assertTrue(any(p["type"] == "table" and p["loc"].startswith("main.tex:")
                            for p in ptrs), ptrs)
        self.assertIn(("figure", "main.tex:11"), locs)
        self.assertIn(("algorithm", "main.tex:17"), locs)
        self.assertIn(("diagram", "main.tex:14"), locs)


class TestDocxAudit(unittest.TestCase):
    """docx 夹具：1 个 w:tbl、1 个 w:drawing、1 个 m:oMath vs 无表格 draft"""

    BODY = (
        '<w:p><w:r><w:t>标题段落</w:t></w:r></w:p>'
        '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>cell</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
        '<w:p><w:r><w:drawing/></w:r></w:p>'
        '<w:p><m:oMath><m:r><m:t>x=y</m:t></m:r></m:oMath></w:p>'
    )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.src = os.path.join(self.dir, "paper.docx")
        make_docx_raw(self.src, self.BODY)
        self.draft = os.path.join(self.dir, "draft.md")
        write(self.draft, "# 草稿\n\n只有纯文本段落，没有表格。\n")
        self.code, self.js, self.err = run(
            ["--source", self.src, "--draft", self.draft])   # .docx → docx 推断
        self.assertEqual(self.code, 0, self.err)

    def tearDown(self):
        self.tmp.cleanup()

    def test_docx_source_counts(self):
        self.assertEqual(self.js["format"], "docx")
        sc = self.js["source_counts"]
        self.assertEqual(sc["tables"], 1)
        self.assertEqual(sc["figures"], 1)                  # w:drawing
        self.assertEqual(sc["equations"], 1)                # m:oMath
        self.assertIsNone(sc["algorithms"])
        self.assertIsNone(sc["diagrams"])

    def test_docx_missing(self):
        m = self.js["missing"]
        self.assertEqual(m["tables"], 1)
        self.assertEqual(m["figures"], 1)
        self.assertEqual(m["equations"], 1)
        self.assertIsNone(m["algorithms"])
        self.assertIsNone(m["diagrams"])
        self.assertEqual(self.js["missing_pointers"], [])   # docx 无逐项指针


class TestPdfAudit(unittest.TestCase):
    EXTRACT = """文件: paper.pdf
总页数: 3
============================================================

%% [PDF p.1]
Introduction text here.

%% [PDF p.2]
Method text here.

%% [PDF p.3]
Conclusion text here.
"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.draft = os.path.join(self.dir, "draft.md")
        write(self.draft, "# 草稿\n\n正文。\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_pdf_text_pages(self):
        src = os.path.join(self.dir, "101_extract_paper.txt")
        write(src, self.EXTRACT)
        code, js, err = run(["--source", src, "--draft", self.draft])  # .txt → pdf 推断
        self.assertEqual(code, 0, err)
        self.assertEqual(js["format"], "pdf")
        self.assertEqual(js["source_counts"]["pages"], 3)
        m = js["missing"]
        self.assertIsNone(m["tables"])                      # 无法机械计数 → null 不参与
        self.assertIsNone(m["figures"])
        self.assertIsNone(m["equations"])
        self.assertEqual(js["missing_pointers"], [])

    def test_pdf_legacy_markers(self):
        src = os.path.join(self.dir, "legacy.txt")
        write(src, "头\n--- Page 1 ---\nfirst\n--- Page 2 ---\nsecond\n")
        code, js, err = run(["--source", src, "--draft", self.draft, "--format", "pdf"])
        self.assertEqual(code, 0, err)
        self.assertEqual(js["source_counts"]["pages"], 2)

    def test_pdf_binary_degrades_to_null(self):
        """真 .pdf（此处为损坏文件）：fitz 缺失或打开失败均降级 pages=null，退出码 0"""
        src = os.path.join(self.dir, "broken.pdf")
        with open(src, "wb") as f:
            f.write(b"%PDF-1.4\nnot really a pdf\n")
        code, js, err = run(["--source", src, "--draft", self.draft])  # .pdf → pdf 推断
        self.assertEqual(code, 0, err)
        self.assertIsNone(js["source_counts"]["pages"])


class TestSourceCountsOverlay(unittest.TestCase):
    """--source-counts 源侧计数回填（v2.1 条目10：pdf 的 tables/figures/equations
    不再为 null——extract_pdf.py 产出 pdf_source_counts.json 供本参数消费）"""

    EXTRACT = "%% [PDF p.1]\ntext\n\n%% [PDF p.2]\nmore\n\n%% [PDF p.3]\nend\n"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.draft = os.path.join(self.dir, "draft.md")
        write(self.draft, "# 草稿\n\n正文。\n")
        self.src = os.path.join(self.dir, "extract.txt")
        write(self.src, self.EXTRACT)

    def tearDown(self):
        self.tmp.cleanup()

    def write_counts(self, data, name="pdf_source_counts.json"):
        path = os.path.join(self.dir, name)
        write(path, json.dumps(data, ensure_ascii=False))
        return path

    def test_overlay_fills_pdf_nulls(self):
        counts = self.write_counts({"format": "pdf", "pages": None, "tables": 6,
                                    "figures": 4, "equations": 12, "refs": 40})
        code, js, err = run(["--source", self.src, "--draft", self.draft,
                             "--source-counts", counts])
        self.assertEqual(code, 0, err)
        sc = js["source_counts"]
        self.assertEqual(sc["tables"], 6)
        self.assertEqual(sc["figures"], 4)
        self.assertEqual(sc["equations"], 12)
        self.assertEqual(sc["pages"], 3)          # overlay 为 null → 保留文本推断值
        m = js["missing"]                          # draft 侧全 0 → missing=源值
        self.assertEqual(m["tables"], 6)
        self.assertEqual(m["figures"], 4)
        self.assertEqual(m["equations"], 12)
        self.assertEqual(js["missing_pointers"], [])   # pdf 无指针可列
        self.assertEqual(sorted(js["overlay_applied"]),
                         ["equations", "figures", "tables"])

    def test_overlay_overrides_computed_pages(self):
        counts = self.write_counts({"pages": 186})
        code, js, err = run(["--source", self.src, "--draft", self.draft,
                             "--source-counts", counts])
        self.assertEqual(code, 0, err)
        self.assertEqual(js["source_counts"]["pages"], 186)
        self.assertEqual(js["overlay_applied"], ["pages"])

    def test_overlay_ignores_unknown_keys(self):
        counts = self.write_counts({"refs": 40, "headings": 7, "tables": 2})
        code, js, err = run(["--source", self.src, "--draft", self.draft,
                             "--source-counts", counts])
        self.assertEqual(code, 0, err)
        self.assertNotIn("refs", js["source_counts"])
        self.assertEqual(js["source_counts"]["tables"], 2)

    def test_overlay_all_null_keeps_defaults(self):
        counts = self.write_counts({"tables": None, "figures": None})
        code, js, err = run(["--source", self.src, "--draft", self.draft,
                             "--source-counts", counts])
        self.assertEqual(code, 0, err)
        self.assertIsNone(js["source_counts"]["tables"])
        self.assertEqual(js["overlay_applied"], [])
        self.assertIn("未回填", err)

    def test_overlay_missing_file_exit1(self):
        code, js, err = run(["--source", self.src, "--draft", self.draft,
                             "--source-counts", os.path.join(self.dir, "nope.json")])
        self.assertEqual(code, 1)
        self.assertIn("--source-counts", err)

    def test_overlay_invalid_json_exit1(self):
        path = os.path.join(self.dir, "bad.json")
        write(path, "{not json")
        code, js, err = run(["--source", self.src, "--draft", self.draft,
                             "--source-counts", path])
        self.assertEqual(code, 1)
        self.assertIn("--source-counts", err)


class TestDraftMath(unittest.TestCase):
    """draft 公式块（$$ 跨行 + \\[...\\]）与行内数学近似计数"""

    SRC = r"""\begin{equation}
a = b
\end{equation}
\begin{align}
c = d
\end{align}
"""

    DRAFT = """# 草稿

$$
E = mc^2
$$

Display \\[ a + b \\] block.

Inline $x$ and $y$ here.
"""

    def test_formula_blocks_and_inline_math(self):
        tmp = tempfile.TemporaryDirectory()
        d = tmp.name
        src = os.path.join(d, "main.tex")
        write(src, self.SRC)
        draft = os.path.join(d, "draft.md")
        write(draft, self.DRAFT)
        code, js, err = run(["--source", src, "--draft", draft, "--format", "tex"])
        self.assertEqual(code, 0, err)
        self.assertEqual(js["source_counts"]["equations"], 2)   # equation + align
        dc = js["draft_counts"]
        self.assertEqual(dc["formula_blocks"], 2)               # $$块 + \[\]块
        self.assertEqual(dc["inline_math"], 2)                  # $x$ 与 $y$
        self.assertEqual(js["missing"]["equations"], 0)         # 2 - 2
        tmp.cleanup()


class TestReport(unittest.TestCase):
    """--output 写出的 markdown 报告内容"""

    def test_output_report_content(self):
        tmp = tempfile.TemporaryDirectory()
        d = tmp.name
        src = os.path.join(d, "main.tex")
        write(src, "\\begin{table}[h]\nx\n\\end{table}\n\\begin{figure}[h]\ny\n\\end{figure}\n")
        draft = os.path.join(d, "draft.md")
        write(draft, "# 草稿\n\n正文。\n")
        out = os.path.join(d, ".review", "conversion_audit.md")
        code, js, err = run(["--source", src, "--draft", draft,
                             "--format", "tex", "--output", out])
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.isfile(out))
        self.assertEqual(js["output"], out.replace("\\", "/"))
        with open(out, encoding="utf-8") as f:
            md = f.read()
        self.assertIn("数值核验以编译 PDF 为准", md)            # 固定结论行
        self.assertIn("| 结构 | 源侧 | draft侧 | 疑似丢失 |", md)
        self.assertIn("## 疑似丢失清单", md)
        self.assertIn("main.tex:1", md)                        # 表指针逐行
        self.assertIn("main.tex:4", md)                        # 图指针逐行
        tmp.cleanup()


class TestErrors(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.draft = os.path.join(self.dir, "draft.md")
        write(self.draft, "# 草稿\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_source_exit2(self):
        code, js, err = run(["--source", os.path.join(self.dir, "nope.tex"),
                             "--draft", self.draft])
        self.assertEqual(code, 2)

    def test_missing_draft_exit2(self):
        src = os.path.join(self.dir, "main.tex")
        write(src, "% empty\n")
        code, js, err = run(["--source", src,
                             "--draft", os.path.join(self.dir, "nope.md")])
        self.assertEqual(code, 2)

    def test_unknown_format_exit2(self):
        src = os.path.join(self.dir, "notes.md")
        write(src, "text\n")
        code, js, err = run(["--source", src, "--draft", self.draft])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
