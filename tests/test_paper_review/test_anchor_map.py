#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_anchor_map.py — anchor_map.py 三轨定位单元测试

覆盖：
  - init：tex 源（目录推断）/ docx / pdf 提取文本
  - fill：resolved（tex 行号反查、去命令归一化、全半角标点容差）
          ambiguous（同句多处命中 → 回退结构坐标）
          not_found（宏展开改变表面文字 → 回退结构坐标）
          draft_line 缺省时从 draft 反查
  - pdf 页标记 %% [PDF p.N] 与旧式 --- Page N --- 双格式切分

运行：python tests/test_paper_review/test_anchor_map.py
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
    HERE, "..", "..", "skills", "paper-review", "scripts", "anchor_map.py"))


def run(args, cwd=None):
    """运行 anchor_map.py，返回 (exit_code, stdout_json, stderr)"""
    p = subprocess.run([sys.executable, SCRIPT] + args,
                       capture_output=True, cwd=cwd)
    out = p.stdout.decode("utf-8", errors="replace")
    err = p.stderr.decode("utf-8", errors="replace")
    try:
        return p.returncode, json.loads(out), err
    except json.JSONDecodeError:
        return p.returncode, None, out + err


def make_docx(path, paragraphs):
    """构造最小合法 docx（仅 word/document.xml，段落文本为单 run）"""
    paras = "".join(
        '<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>' % t
        for t in paragraphs)
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           '<w:body>%s</w:body></w:document>' % paras)
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


class TestInit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.review = os.path.join(self.dir, ".review")

    def tearDown(self):
        self.tmp.cleanup()

    def test_init_tex_dir_infer(self):
        src = os.path.join(self.dir, "texsrc")
        os.makedirs(src)
        open(os.path.join(src, "main.tex"), "w", encoding="utf-8").write("% empty\n")
        code, js, err = run(["--review-dir", self.review, "init",
                             "--source", src])
        self.assertEqual(code, 0, err)
        self.assertTrue(js["success"])
        self.assertEqual(js["format"], "tex")     # 目录 → tex 推断
        self.assertTrue(os.path.isfile(os.path.join(self.review, "anchor_map.json")))

    def test_init_missing_source_fails(self):
        code, js, err = run(["--review-dir", self.review, "init",
                             "--source", os.path.join(self.dir, "nope.tex")])
        self.assertEqual(code, 2)


class TestFillTex(unittest.TestCase):
    """tex 三轨反查：resolved / ambiguous / not_found / 归一化容差"""

    TEX = """\\documentclass{article}
\\newcommand{\\method}{XYZ-Net}
\\begin{document}
\\section{Introduction}
Digital twin technology enables high-fidelity simulation of training ranges.
The proposed \\textbf{framework} achieves state-of-the-art performance on benchmarks.
\\begin{table}[h]
\\caption{实验结果对比}
重复句式出现在这里。重复句式出现在这里。
\\end{table}
The proposed framework achieves state-of-the-art performance on benchmarks.
\\end{document}
"""

    DRAFT = """# 论文草稿

## 2.1 方法

数字孪生技术能够实现训练场的高保真仿真。重复句式出现在这里。

The proposed framework achieves state-of-the-art performance on benchmarks.
"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.review = os.path.join(self.dir, ".review")
        self.src = os.path.join(self.dir, "main.tex")
        with open(self.src, "w", encoding="utf-8") as f:
            f.write(self.TEX)
        self.draft = os.path.join(self.dir, "draft.md")
        with open(self.draft, "w", encoding="utf-8") as f:
            f.write(self.DRAFT)
        code, js, err = run(["--review-dir", self.review, "init",
                             "--draft", self.draft, "--source", self.src,
                             "--format", "tex"])
        self.assertEqual(code, 0, err)

    def fill(self, requests):
        req_path = os.path.join(self.dir, "anchor_requests.json")
        with open(req_path, "w", encoding="utf-8") as f:
            json.dump(requests, f, ensure_ascii=False)
        code, js, err = run(["--review-dir", self.review, "fill",
                             "--requests", req_path])
        self.assertEqual(code, 0, err)
        with open(os.path.join(self.review, "anchor_map.json"), encoding="utf-8") as f:
            return js, json.load(f)

    def entry(self, data, eid):
        for e in data["entries"]:
            if e["id"] == eid:
                return e
        self.fail("entry %s not found" % eid)

    def test_resolved_line_number(self):
        js, data = self.fill([{
            "id": "f1",
            "quote": "Digital twin technology enables high-fidelity simulation",
            "structural": "§1 Introduction",
        }])
        self.assertEqual(js["resolved"], 1)
        e = self.entry(data, "f1")
        self.assertEqual(e["status"], "resolved")
        self.assertEqual(e["source_loc"], "main.tex:5")   # 1-based 行号
        self.assertFalse(e["ambiguous"])

    def test_tex_command_stripped(self):
        """\\textbf{framework} 归一化后应命中 framework"""
        js, data = self.fill([{
            "id": "f2",
            "quote": "The proposed framework achieves state-of-the-art",
        }])
        e = self.entry(data, "f2")
        # 该句在 TEX 中出现两次（第6行与第10行）→ ambiguous
        self.assertEqual(e["status"], "ambiguous")
        self.assertTrue(e["ambiguous"])
        self.assertIsNone(e["source_loc"])
        self.assertEqual(js["ambiguous"], 1)

    def test_not_found_macro_expansion(self):
        """宏展开：draft 中的 XYZ-Net 字面量在源中不存在 → not_found，回退结构坐标"""
        js, data = self.fill([{
            "id": "f3",
            "quote": "XYZ-Net achieves state-of-the-art performance on benchmarks",
            "structural": "§2.1 式(3)",
        }])
        e = self.entry(data, "f3")
        self.assertEqual(e["status"], "not_found")
        self.assertIsNone(e["source_loc"])
        self.assertEqual(e["structural"], "§2.1 式(3)")   # 结构坐标兜底保留

    def test_draft_line_inferred(self):
        """请求缺 draft_line 时从 draft 反查唯一行号"""
        js, data = self.fill([{
            "id": "f4",
            "quote": "数字孪生技术能够实现训练场的高保真仿真",
        }])
        e = self.entry(data, "f4")
        # 中文引文在英文 tex 源中必然 not_found，但 draft_line 应反查成功（draft 第5行）
        self.assertEqual(e["draft_line"], 5)

    def test_punctuation_tolerance(self):
        """全半角标点/大小写差异经 NFKC 归一后仍命中"""
        js, data = self.fill([{
            "id": "f5",
            "quote": "digital twin TECHNOLOGY enables high-fidelity simulation of training ranges",
        }])
        e = self.entry(data, "f5")
        self.assertEqual(e["status"], "resolved")
        self.assertEqual(e["source_loc"], "main.tex:5")


class TestFillDocx(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.review = os.path.join(self.dir, ".review")
        self.src = os.path.join(self.dir, "paper.docx")
        make_docx(self.src, [
            "标题段落",                                     # index 0
            "第一段正文：数字孪生建模方法综述。",             # index 1
            "第二段正文：The second paragraph in English.",  # index 2
        ])
        code, js, err = run(["--review-dir", self.review, "init",
                             "--source", self.src])
        self.assertEqual(code, 0, err)
        self.assertEqual(js["format"], "docx")   # 扩展名推断

    def test_paragraph_index(self):
        req = os.path.join(self.dir, "req.json")
        with open(req, "w", encoding="utf-8") as f:
            json.dump([{"id": "d1", "quote": "The second paragraph in English"}], f)
        code, js, err = run(["--review-dir", self.review, "fill", "--requests", req])
        self.assertEqual(code, 0, err)
        with open(os.path.join(self.review, "anchor_map.json"), encoding="utf-8") as f:
            data = json.load(f)
        e = data["entries"][0]
        self.assertEqual(e["status"], "resolved")
        self.assertEqual(e["source_loc"], "段落2")   # python-docx 0-based index


class TestFillPdf(unittest.TestCase):
    EXTRACT = """文件: paper.pdf
总页数: 3
============================================================

%% [PDF p.1]
--- Page 1 ---
Introduction. Digital twin simulation for military training.

%% [PDF p.2]
--- Page 2 ---
Section two describes the proposed method in detail.

%% [PDF p.3]
--- Page 3 (near end) ---
References list here.
"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.review = os.path.join(self.dir, ".review")
        self.src = os.path.join(self.dir, "101_extract_paper.txt")
        with open(self.src, "w", encoding="utf-8") as f:
            f.write(self.EXTRACT)
        code, js, err = run(["--review-dir", self.review, "init",
                             "--source", self.src, "--format", "pdf"])
        self.assertEqual(code, 0, err)

    def fill(self, quote):
        req = os.path.join(self.dir, "req.json")
        with open(req, "w", encoding="utf-8") as f:
            json.dump([{"id": "p1", "quote": quote}], f)
        code, js, err = run(["--review-dir", self.review, "fill", "--requests", req])
        self.assertEqual(code, 0, err)
        with open(os.path.join(self.review, "anchor_map.json"), encoding="utf-8") as f:
            return js, json.load(f)

    def test_page_marker_standard(self):
        js, data = self.fill("the proposed method in detail")
        e = data["entries"][0]
        self.assertEqual(e["status"], "resolved")
        self.assertEqual(e["source_loc"], "p.2")

    def test_page_not_found(self):
        js, data = self.fill("这句话在提取文本中根本不存在的片段内容")
        e = data["entries"][0]
        self.assertEqual(e["status"], "not_found")
        self.assertIsNone(e["source_loc"])


class TestFillPdfLegacyMarker(unittest.TestCase):
    """旧式 --- Page N --- 标记（无 %% [PDF p.N]）也应能切分"""

    def test_legacy(self):
        tmp = tempfile.TemporaryDirectory()
        d = tmp.name
        review = os.path.join(d, ".review")
        src = os.path.join(d, "extract.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("头\n--- Page 1 ---\nfirst page text\n--- Page 2 ---\nsecond page text\n")
        code, js, err = run(["--review-dir", review, "init", "--source", src, "--format", "pdf"])
        self.assertEqual(code, 0, err)
        req = os.path.join(d, "req.json")
        with open(req, "w", encoding="utf-8") as f:
            json.dump([{"id": "L1", "quote": "second page text"}], f)
        code, js, err = run(["--review-dir", review, "fill", "--requests", req])
        self.assertEqual(code, 0, err)
        with open(os.path.join(review, "anchor_map.json"), encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["entries"][0]["source_loc"], "p.2")
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
