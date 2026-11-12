#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_extract_pdf.py — extract_pdf.py PDF 全文提取单元测试（v2.1 条目10）

夹具：PyMuPDF 构造的合成多页 PDF（无外部文件依赖）——字号分级标题
（24/16/13/10.5）、跨页页眉「某某大学博士学位论文」+ 独立页码页脚、
目录点引线行、被换行拆开的标题（「2.1 实验」+「环境与数据集」）、
三种图像（正常 200x150 / 微小 10x10 / 细长 300x4）、公式编号行、
图/表题行、线框表格、参考文献节（[1]–[3]，含跨行条目）与「致谢」停止边界。

覆盖：
  - CLI：--help exit 0、--input 不存在 exit 2、密码保护 PDF exit 1（回退链提示）
  - 页标记 %% [PDF p.N] 逐页有序（anchor_map pdf 源坐标切分依据）
  - 页眉页脚/独立页码/点引线过滤
  - 无书签按字号重建标题（#/##/###）+ 被拆标题合并
  - 有书签 PDF 按 get_toc 标题匹配（bookmarks=true）
  - 图像尺寸过滤导出（微小/细长剔除）+ markdown 引用 + figures/ 产物
  - 参考文献 [N] 切分 refs.txt（跨行条目归并、致谢处停止）
  - pdf_source_counts.json：tables/figures/equations/pages 均非 null
    （供 conversion_audit.py --source-counts 回填）
  - stdout JSON 计数字段与产物路径

需要 PyMuPDF；未安装时夹具类跳过（CLI 参数类用例不依赖）。

运行：python tests/test_paper_review/test_extract_pdf.py
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
SCRIPT = os.path.normpath(os.path.join(
    HERE, "..", "..", "skills", "paper-review", "scripts", "extract_pdf.py"))

try:
    import fitz  # PyMuPDF
except ImportError:
    try:
        import pymupdf as fitz
    except ImportError:
        fitz = None

HAS_FITZ = fitz is not None
HEADER = "某某大学博士学位论文"


def run(args):
    """运行 extract_pdf.py，返回 (exit_code, stdout_json, stderr)"""
    p = subprocess.run([sys.executable, SCRIPT] + args, capture_output=True)
    out = p.stdout.decode("utf-8", errors="replace")
    err = p.stderr.decode("utf-8", errors="replace")
    try:
        return p.returncode, json.loads(out), err
    except json.JSONDecodeError:
        return p.returncode, None, out + err


def put(page, x, y, text, size):
    page.insert_text((x, y), text, fontsize=size, fontname="china-s")


def make_fixture_pdf(path):
    """3 页合成学位论文风格 PDF（详见模块 docstring）"""
    doc = fitz.open()

    def decorate(num):
        p = doc.new_page(width=595, height=842)
        put(p, 72, 40, HEADER, 9)          # 页眉（跨页重复 → 应过滤）
        put(p, 290, 810, str(num), 9)       # 页码页脚（独立数字行 → 应过滤）
        return p

    # ── 第 1 页：大标题 + 章 + 节 + 正文 + 点引线 + 三种图像 ──
    p1 = decorate(1)
    put(p1, 72, 100, "面向审阅流程的全文提取研究", 24)
    put(p1, 72, 160, "第1章 绪论", 16)
    put(p1, 72, 190, "1.1 研究背景", 13)
    put(p1, 72, 214, "本文研究PDF全文提取方法。", 10.5)
    put(p1, 72, 238, "1.2 章节安排......7", 10.5)   # 目录点引线 → 应过滤
    pix_ok = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 200, 150))
    p1.insert_image(fitz.Rect(72, 300, 172, 375), pixmap=pix_ok)
    pix_tiny = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 10, 10))
    p1.insert_image(fitz.Rect(72, 400, 77, 405), pixmap=pix_tiny)
    pix_sliver = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 300, 4))
    p1.insert_image(fitz.Rect(72, 430, 372, 434), pixmap=pix_sliver)

    # ── 第 2 页：章 + 被拆标题 + 正文 + 公式行 + 图/表题 + 线框表格 ──
    p2 = decorate(2)
    put(p2, 72, 100, "第2章 方法", 16)
    put(p2, 72, 130, "2.1 实验", 13)               # 与下行同字号 → 应合并
    put(p2, 72, 152, "环境与数据集", 13)
    put(p2, 72, 182, "实验使用公开数据集进行验证。", 10.5)
    put(p2, 72, 206, "E = mc2 (2-1)", 10.5)        # 公式编号行
    put(p2, 72, 230, "图2.1 实验结果对比", 10.5)    # 图题
    put(p2, 72, 254, "表2.1 参数设置", 10.5)        # 表题
    for yy in (300, 320, 340):                      # 2x2 线框表格
        p2.draw_line(fitz.Point(72, yy), fitz.Point(272, yy))
    for xx in (72, 172, 272):
        p2.draw_line(fitz.Point(xx, 300), fitz.Point(xx, 340))
    put(p2, 80, 314, "参数", 9)
    put(p2, 180, 314, "取值", 9)

    # ── 第 3 页：参考文献（含跨行条目）+ 致谢（停止边界）──
    p3 = decorate(3)
    put(p3, 72, 100, "参考文献", 16)
    put(p3, 72, 130, "[1] 张三. 深度学习方法综述[J]. 计算机学报, 2020.", 10.5)
    put(p3, 72, 152, "[2] 李四. 论文写作实验[M]. 学术出版社, 2019.", 10.5)
    put(p3, 72, 174, "[3] 王五. 跨行条目示例[J]. 学报,", 10.5)
    put(p3, 72, 190, "2021, 12(3): 45-67.", 10.5)  # 条目 [3] 的续行
    put(p3, 72, 230, "致谢", 16)
    put(p3, 72, 258, "感谢导师的悉心指导。", 10.5)

    doc.save(path)
    doc.close()


def make_encrypted_pdf(path):
    doc = fitz.open()
    p = doc.new_page(width=595, height=842)
    put(p, 72, 100, "加密文档", 16)
    doc.save(path, encryption=fitz.PDF_ENCRYPT_AES_256,
             user_pw="secret", owner_pw="secret")
    doc.close()


def make_bookmarked_pdf(path):
    doc = fitz.open()
    p = doc.new_page(width=595, height=842)
    put(p, 72, 100, "第一章 绑定书签的标题", 16)
    put(p, 72, 140, "正文内容按书签模式渲染。", 10.5)
    doc.set_toc([[1, "第一章 绑定书签的标题", 1]])
    doc.save(path)
    doc.close()


@unittest.skipUnless(HAS_FITZ, "需要 PyMuPDF 构造夹具")
class Base(unittest.TestCase):
    """公共装置：合成夹具 PDF → 跑一次 extract_pdf.py"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="extract_pdf_test_")
        cls.pdf = os.path.join(cls.tmp, "thesis.pdf")
        make_fixture_pdf(cls.pdf)
        cls.draft = os.path.join(cls.tmp, "paper", "draft", "draft.md")
        code, js, err = run(["--input", cls.pdf, "--draft", cls.draft])
        assert code == 0, "夹具提取失败: %s" % err
        cls.js = js
        with open(cls.draft, encoding="utf-8") as f:
            cls.draft_text = f.read()
        cls.draft_dir = os.path.dirname(cls.draft)
        with open(os.path.join(cls.draft_dir, "pdf_source_counts.json"),
                  encoding="utf-8") as f:
            cls.counts = json.load(f)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)


@unittest.skipUnless(HAS_FITZ, "需要 PyMuPDF 构造夹具")
class TestPageMarkers(Base):
    def test_markers_per_page_in_order(self):
        idx = [self.draft_text.index("%% [PDF p.%d]" % n) for n in (1, 2, 3)]
        self.assertEqual(idx, sorted(idx))

    def test_no_truncation_all_pages_present(self):
        # 全文提取无字符上限：三页的正文内容都必须在
        for frag in ("本文研究PDF全文提取方法。", "实验使用公开数据集进行验证。",
                     "感谢导师的悉心指导。"):
            self.assertIn(frag, self.draft_text)

    def test_stdout_pages_and_success(self):
        self.assertTrue(self.js["success"])
        self.assertEqual(self.js["pages"], 3)


@unittest.skipUnless(HAS_FITZ, "需要 PyMuPDF 构造夹具")
class TestFiltering(Base):
    def test_header_filtered(self):
        self.assertNotIn(HEADER, self.draft_text)
        self.assertGreaterEqual(self.js["headers_footers_filtered"], 6)  # 3页眉+3页码

    def test_pagenum_lines_filtered(self):
        lines = [l.strip() for l in self.draft_text.splitlines()]
        for n in ("1", "2", "3"):
            self.assertNotIn(n, lines)

    def test_dot_leader_filtered(self):
        self.assertNotIn("......", self.draft_text)
        self.assertEqual(self.js["toc_lines_filtered"], 1)


@unittest.skipUnless(HAS_FITZ, "需要 PyMuPDF 构造夹具")
class TestHeadings(Base):
    def test_heading_levels_by_font_size(self):
        self.assertIn("# 面向审阅流程的全文提取研究", self.draft_text)   # 24 → H1
        self.assertIn("## 第1章 绪论", self.draft_text)                   # 16 → H2
        self.assertIn("### 1.1 研究背景", self.draft_text)                # 13 → H3
        self.assertIn("## 参考文献", self.draft_text)

    def test_split_heading_merged(self):
        self.assertIn("### 2.1 实验环境与数据集", self.draft_text)
        # 合并后不得残留拆开的半行
        lines = [l.strip() for l in self.draft_text.splitlines()]
        self.assertNotIn("环境与数据集", lines)

    def test_real_headings_not_over_merged(self):
        # 「第2章 方法」与其后的「2.1 实验…」是两级标题，不得被并成一行
        self.assertIn("## 第2章 方法", self.draft_text)

    def test_body_not_heading(self):
        self.assertIn("本文研究PDF全文提取方法。", self.draft_text)
        self.assertNotIn("# 本文研究", self.draft_text)


@unittest.skipUnless(HAS_FITZ, "需要 PyMuPDF 构造夹具")
class TestImages(Base):
    def test_normal_image_exported(self):
        figs = os.path.join(self.draft_dir, "figures")
        pngs = sorted(fn for fn in os.listdir(figs) if fn.endswith(".png"))
        self.assertEqual(pngs, ["p1_img1.png"])
        self.assertGreater(os.path.getsize(os.path.join(figs, pngs[0])), 0)

    def test_tiny_and_sliver_filtered(self):
        self.assertEqual(self.js["images_exported"], 1)
        self.assertEqual(self.js["images_filtered"], 2)  # 10x10 微小 + 300x4 细长

    def test_markdown_reference_in_draft(self):
        self.assertIn("![图 p1-1](figures/p1_img1.png)", self.draft_text)


@unittest.skipUnless(HAS_FITZ, "需要 PyMuPDF 构造夹具")
class TestRefs(Base):
    def setUp(self):
        with open(os.path.join(self.draft_dir, "refs.txt"), encoding="utf-8") as f:
            self.refs = [l for l in f.read().splitlines() if l.strip()]

    def test_split_by_bracket_number(self):
        self.assertEqual(len(self.refs), 3)
        self.assertTrue(self.refs[0].startswith("[1]"))
        self.assertTrue(self.refs[1].startswith("[2]"))

    def test_multiline_entry_merged(self):
        self.assertIn("王五", self.refs[2])
        self.assertIn("45-67", self.refs[2])   # 续行已归并到 [3]
        self.assertNotIn("\n", self.refs[2])

    def test_stops_at_acknowledgement(self):
        joined = "\n".join(self.refs)
        self.assertNotIn("致谢", joined)
        self.assertNotIn("感谢导师", joined)

    def test_stdout_refs_count(self):
        self.assertEqual(self.js["refs"], 3)


@unittest.skipUnless(HAS_FITZ, "需要 PyMuPDF 构造夹具")
class TestSourceCounts(Base):
    def test_no_null_counters(self):
        # 备忘条目10：回填 conversion_audit 源侧计数，不再为 null
        for key in ("pages", "tables", "figures", "equations"):
            self.assertIsNotNone(self.counts[key], key)
        self.assertEqual(self.counts["pages"], 3)

    def test_heuristic_counts(self):
        self.assertEqual(self.counts["equations"], 1)        # (2-1) 公式编号行
        self.assertEqual(self.counts["figure_captions"], 1)  # 图2.1
        self.assertEqual(self.counts["table_captions"], 1)   # 表2.1
        self.assertEqual(self.counts["refs"], 3)
        self.assertEqual(self.counts["headings"], 7)
        self.assertEqual(self.counts["format"], "pdf")

    def test_figures_estimate_at_least_captions(self):
        self.assertGreaterEqual(self.counts["figures"], self.counts["figure_captions"])

    def test_generator_stamp(self):
        self.assertIn("full-manuscript", self.counts["generator"])


@unittest.skipUnless(HAS_FITZ, "需要 PyMuPDF 构造夹具")
class TestBookmarks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="extract_pdf_bm_")
        self.pdf = os.path.join(self.tmp, "bm.pdf")
        make_bookmarked_pdf(self.pdf)
        self.draft = os.path.join(self.tmp, "draft.md")
        self.code, self.js, self.err = run(["--input", self.pdf, "--draft", self.draft])
        with open(self.draft, encoding="utf-8") as f:
            self.text = f.read()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_bookmark_mode(self):
        self.assertEqual(self.code, 0, self.err)
        self.assertTrue(self.js["bookmarks"])
        self.assertIn("# 第一章 绑定书签的标题", self.text)
        self.assertIn("正文内容按书签模式渲染。", self.text)


@unittest.skipUnless(HAS_FITZ, "需要 PyMuPDF 构造夹具")
class TestEncrypted(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="extract_pdf_enc_")
        self.pdf = os.path.join(self.tmp, "locked.pdf")
        make_encrypted_pdf(self.pdf)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_encrypted_exit1_with_guidance(self):
        draft = os.path.join(self.tmp, "draft.md")
        code, js, err = run(["--input", self.pdf, "--draft", draft])
        self.assertEqual(code, 1)
        self.assertIn("密码", err)
        self.assertIn("Step 0.3", err)   # 指向 SKILL 回退链
        self.assertFalse(os.path.exists(draft))


class TestCli(unittest.TestCase):
    """不依赖 PyMuPDF 的 CLI 约定用例（CLAUDE.md 脚本规范）"""

    def test_help_exit_zero(self):
        p = subprocess.run([sys.executable, SCRIPT, "--help"], capture_output=True)
        out = p.stdout.decode("utf-8", errors="replace")
        self.assertEqual(p.returncode, 0)
        self.assertIn("usage", out.lower())
        self.assertIn("--min-image-size", out)

    def test_missing_input_exit2(self):
        tmp = tempfile.mkdtemp(prefix="extract_pdf_cli_")
        try:
            code, js, err = run(["--input", os.path.join(tmp, "nope.pdf"),
                                 "--draft", os.path.join(tmp, "d.md")])
            self.assertEqual(code, 2)
            self.assertIn("不存在", err)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


@unittest.skipUnless(HAS_FITZ, "需要 PyMuPDF 构造夹具")
class TestDefaultMinImageSize(unittest.TestCase):
    """R-3 回流：默认 --min-image-size 提到 150
    （60 曾在 186 页学位论文上把表格/碎片误当图片导出 531 张，图题仅 95）"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.pdf = os.path.join(self.dir, "frag.pdf")
        doc = fitz.open()
        p = doc.new_page(width=595, height=842)
        put(p, 72, 100, "碎片图像阈值夹具", 16)
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 100))
        p.insert_image(fitz.Rect(72, 200, 172, 300), pixmap=pix)
        doc.save(self.pdf)
        doc.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_filters_sub_150(self):
        draft = os.path.join(self.dir, "a", "draft.md")
        code, js, err = run(["--input", self.pdf, "--draft", draft])
        self.assertEqual(code, 0, err)
        self.assertEqual(js["images_exported"], 0)
        self.assertEqual(js["images_filtered"], 1)

    def test_explicit_60_still_exports(self):
        draft = os.path.join(self.dir, "b", "draft.md")
        code, js, err = run(["--input", self.pdf, "--draft", draft,
                             "--min-image-size", "60"])
        self.assertEqual(code, 0, err)
        self.assertEqual(js["images_exported"], 1)
        self.assertEqual(js["images_filtered"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
