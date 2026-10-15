#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_extract_pdf.py — extract_pdf.py 页标记植入测试（B3 固化项）

验证提取文本逐页植入双轨页标记：
  - %% [PDF p.N]  （页级锚点标准格式，paper-review anchor_map.py 依赖）
  - --- Page N ---（兼容旧格式）

运行：python tests/test_lit_research/test_extract_pdf.py
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
    HERE, "..", "..", "skills", "lit-research", "scripts", "extract_pdf.py"))

try:
    import fitz  # noqa: F401
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False


def make_pdf(path, pages):
    import fitz
    doc = fitz.open()
    for i, text in enumerate(pages, 1):
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=11)
    doc.save(path)
    doc.close()


@unittest.skipUnless(HAS_FITZ, "需要 PyMuPDF（pip install pymupdf）")
class TestPageMarkers(unittest.TestCase):
    def test_markers_planted(self):
        tmp = tempfile.TemporaryDirectory()
        d = tmp.name
        pdf = os.path.join(d, "in.pdf")
        make_pdf(pdf, ["Page one alpha text.", "Page two beta text.", "Page three gamma text."])
        p = subprocess.run(
            [sys.executable, SCRIPT, "--file", pdf, "--number", "7",
             "--name", "Marker_Test", "--output-dir", d],
            capture_output=True)
        out = p.stdout.decode("utf-8", errors="replace")
        err = p.stderr.decode("utf-8", errors="replace")
        self.assertEqual(p.returncode, 0, out + err)
        js = json.loads(out)
        self.assertTrue(js["success"], js)
        self.assertEqual(js["pages"], 3)

        with open(js["extract_path"], encoding="utf-8") as f:
            text = f.read()
        for n in (1, 2, 3):
            self.assertIn("%% [PDF p.%d]" % n, text, "缺少标准页标记 p.%d" % n)
            self.assertIn("--- Page %d" % n, text, "缺少兼容页标记 Page %d" % n)
        # 标记应在页文本之前
        self.assertLess(text.index("%% [PDF p.2]"), text.index("Page two beta text."))
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
