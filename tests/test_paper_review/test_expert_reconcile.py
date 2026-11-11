#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_expert_reconcile.py — expert_reconcile.py 专家意见对账单元测试

he-paper 风格夹具：8 条编号专家意见（混合 `1.` `2、` `- ` `* ` `E-N` 开头，
含一条两行续接）× 4 条面板合并发现（其中一条标注「已撤回/误报」）。

覆盖：
  - init：条目数、混合起始标记、显式 E-N 编号剥离、多行续接归并、pending 初态
  - match：三态判定（matched=3 / conflict=1 / omission_candidates=4）、
           matched_finding 前30字、「多域客户端概念未定义」入隔离区、
           findings 缺失 → exit 1 提示先完成阶段3合并
  - 隔离铁律：match 后 counted_from_expert=0、unverified_omissions=4；
           rejected（专家误判）永不计入；confirmed 须 --severity 与 --evidence
  - verify：rejected / confirmed 计数、缺参 exit 2、未知 ID exit 2、
           未 match 即 verify exit 2
  - expert_reconcile.md：隔离区节、核实记录行
  - docx 原生支持（v2.1 条目21，门禁 G2 裁决）：zipfile 构造最小 docx，
           init 解析段落/Word 列表段落（numPr → `- ` 条目）、多行续接、
           match 三态贯通；损坏 docx → exit 1 明确报错

运行：python tests/test_paper_review/test_expert_reconcile.py
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
    HERE, "..", "..", "skills", "paper-review", "scripts", "expert_reconcile.py"))


def run(args, cwd=None):
    """运行 expert_reconcile.py，返回 (exit_code, stdout_json, stderr)"""
    p = subprocess.run([sys.executable, SCRIPT] + args,
                       capture_output=True, cwd=cwd)
    out = p.stdout.decode("utf-8", errors="replace")
    err = p.stderr.decode("utf-8", errors="replace")
    try:
        return p.returncode, json.loads(out), err
    except json.JSONDecodeError:
        return p.returncode, None, out + err


# ────────────────────────── he-paper 风格夹具 ──────────────────────────

COMMENTS = """# 外部专家意见（he-paper 案）

1. §3.2 的实验基线数据描述自相矛盾，数值缺少出处。
2、图4.1 的架构图分辨率过低，图例文字无法辨认。
3. 多域客户端概念未定义，缺少术语界定。
- 结论部分过度扩展，仅凭实验结果不能主张全域适用性。
- 参考文献[12]的引用不存在，请作者核实。
* 表4.1 的数据单位标注错误。
E-7 摘要字数超标，达350字不满足300字以内的要求。
8. 方法部分描述不完整：数据预处理流程缺失，
   影响可复现性。
"""

FINDINGS = """# 合并审查发现

## P0 — 必须修改

| # | 来源 | 位置 | 问题描述 | 建议修改 |
|---|------|------|----------|----------|
| 1 | 去AI审查 | §3.2 | 实验基线数据与§3.2的描述自相矛盾，数值缺少出处 | 补充数据来源并统一描述 |
| 2 | 同行评审 | 表4.1 | 表4.1数据单位标注错误已撤回，经复核单位正确，属误报 | 无需处理 |

## P1 — 重要修改

| # | 来源 | 位置 | 问题描述 | 建议修改 |
|---|------|------|----------|----------|
| 1 | 多智能体研讨 | 图4.1 | 架构图分辨率过低，图例文字无法辨认 | 替换为矢量图 |
| 2 | 多智能体研讨 | §5.3 | 结论过度扩展，实验结果不支持全域适用性的主张 | 弱化结论表述 |

## P2 — 建议修改

（无）

## 统计

P0: 2项 | P1: 2项 | P2: 0项 | 总计: 4项
"""


class Base(unittest.TestCase):
    """公共装置：写夹具 → init（→ 可选写 findings → match）"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.run_dir = os.path.join(self.dir, ".review")
        self.comments = os.path.join(self.dir, "expert_comments.md")
        with open(self.comments, "w", encoding="utf-8", newline="\n") as f:
            f.write(COMMENTS)

    def tearDown(self):
        self.tmp.cleanup()

    # ── 步骤封装 ──

    def do_init(self):
        code, js, err = run(["--run-dir", self.run_dir, "init",
                             "--comments", self.comments])
        self.assertEqual(code, 0, err)
        return js

    def write_findings(self, content=FINDINGS, name="merged_findings.md"):
        os.makedirs(self.run_dir, exist_ok=True)
        path = os.path.join(self.run_dir, name)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        return path

    def do_match(self, findings=None):
        args = ["--run-dir", self.run_dir, "match"]
        if findings:
            args += ["--findings", findings]
        code, js, err = run(args)
        self.assertEqual(code, 0, err)
        return js

    def do_show(self):
        code, js, err = run(["--run-dir", self.run_dir, "show"])
        self.assertEqual(code, 0, err)
        return js

    def do_verify(self, eid, result, evidence=None, severity=None):
        args = ["--run-dir", self.run_dir, "verify",
                "--id", eid, "--result", result]
        if evidence is not None:
            args += ["--evidence", evidence]
        if severity is not None:
            args += ["--severity", severity]
        return run(args)

    def read_md(self):
        with open(os.path.join(self.run_dir, "expert_reconcile.md"),
                  encoding="utf-8") as f:
            return f.read()

    # ── 断言辅助 ──

    @staticmethod
    def find_item(items, sub):
        for it in items:
            if sub in it["text"]:
                return it
        return None


# ────────────────────────── init ──────────────────────────

class TestInit(Base):
    def test_init_parses_8_entries(self):
        """混合 `1.` `2、` `- ` `* ` `E-N` 开头 + 一条两行续接 → 8 条"""
        js = self.do_init()
        self.assertTrue(js["success"])
        self.assertEqual(js["count"], 8)
        with open(os.path.join(self.run_dir, "expert_items.json"),
                  encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["comments_file"].replace("\\", "/"),
                         os.path.abspath(self.comments).replace("\\", "/"))
        entries = data["entries"]
        self.assertEqual(len(entries), 8)
        self.assertEqual([e["id"] for e in entries],
                         ["E-%d" % i for i in range(1, 9)])
        for e in entries:
            self.assertEqual(e["state"], "pending")
            self.assertIsNone(e["severity"])
            self.assertIsNone(e["evidence"])

    def test_init_continuation_merged(self):
        """两行续接归并到前一条目（第8条）"""
        self.do_init()
        js = self.do_show()
        e8 = self.find_item(js["items"], "方法部分描述不完整")
        self.assertIsNotNone(e8)
        self.assertIn("影响可复现性", e8["text"])

    def test_init_explicit_id_and_mixed_markers(self):
        """`E-7` 显式编号被剥离；`- ` `* ` `2、` 起始均正确解析"""
        self.do_init()
        items = self.do_show()["items"]
        e7 = self.find_item(items, "摘要字数超标")
        self.assertIsNotNone(e7)
        self.assertEqual(e7["id"], "E-7")
        self.assertTrue(e7["text"].startswith("摘要字数超标"))   # E-7 前缀已剥离
        self.assertIsNotNone(self.find_item(items, "结论部分过度扩展"))  # `- `
        self.assertIsNotNone(self.find_item(items, "参考文献[12]"))      # `- `
        self.assertIsNotNone(self.find_item(items, "表4.1 的数据单位"))  # `* `
        self.assertIsNotNone(self.find_item(items, "图4.1 的架构图"))    # `2、`

    def test_init_missing_comments_exit2(self):
        code, js, err = run(["--run-dir", self.run_dir, "init",
                             "--comments", os.path.join(self.dir, "nope.md")])
        self.assertEqual(code, 2)


# ────────────────────────── match ──────────────────────────

class TestMatch(Base):
    def setUp(self):
        super().setUp()
        self.do_init()
        self.write_findings()
        self.js = self.do_match()

    def test_match_three_states(self):
        """4 条发现：3 吻合 + 1 含「已撤回」冲突 → 4 条遗漏候选"""
        self.assertTrue(self.js["success"])
        self.assertEqual(self.js["total"], 8)
        self.assertEqual(self.js["matched"], 3)
        self.assertEqual(self.js["conflicts"], 1)
        self.assertEqual(self.js["omission_candidates"], 4)
        self.assertTrue(self.js["reconcile_file"].endswith("expert_reconcile.md"))
        self.assertTrue(os.path.isfile(
            os.path.join(self.run_dir, "expert_reconcile.md")))

    def test_multi_domain_client_is_omission_candidate(self):
        """「多域客户端概念未定义」在面板发现中无对应 → 隔离区"""
        e = self.find_item(self.js["items"], "多域客户端概念未定义")
        self.assertIsNotNone(e)
        self.assertEqual(e["state"], "omission_candidate")
        self.assertIsNone(e.get("matched_finding"))

    def test_matched_finding_recorded(self):
        """吻合条目记录 matched_finding（发现描述前30字）"""
        e = self.find_item(self.js["items"], "§3.2 的实验基线数据")
        self.assertEqual(e["state"], "matched")
        self.assertIsNotNone(e["matched_finding"])
        self.assertLessEqual(len(e["matched_finding"]), 30)
        self.assertIn("实验基线数据", e["matched_finding"])

    def test_withdrawn_finding_is_conflict(self):
        """对应发现含「已撤回/误报」→ conflict 而非 matched"""
        e = self.find_item(self.js["items"], "表4.1 的数据单位标注错误")
        self.assertEqual(e["state"], "conflict")
        self.assertIsNotNone(e["matched_finding"])

    def test_states_persisted_to_json(self):
        """state 重写回 expert_items.json"""
        with open(os.path.join(self.run_dir, "expert_items.json"),
                  encoding="utf-8") as f:
            data = json.load(f)
        states = {e["id"]: e["state"] for e in data["entries"]}
        self.assertEqual(states["E-1"], "matched")
        self.assertEqual(states["E-3"], "omission_candidate")
        self.assertEqual(states["E-6"], "conflict")

    def test_match_missing_findings_exit1(self):
        """merged_findings.md 不存在 → exit 1 提示先完成阶段3合并"""
        tmp2 = tempfile.TemporaryDirectory()
        rd2 = os.path.join(tmp2.name, ".review")
        code, js, err = run(["--run-dir", rd2, "init", "--comments", self.comments])
        self.assertEqual(code, 0, err)
        code, js, err = run(["--run-dir", rd2, "match"])
        self.assertEqual(code, 1)
        self.assertIn("阶段3合并", err)
        tmp2.cleanup()

    def test_match_without_init_exit1(self):
        code, js, err = run(["--run-dir", os.path.join(self.dir, "empty"),
                             "match"])
        self.assertEqual(code, 1)


# ────────────────────────── 隔离铁律与 verify ──────────────────────────

class TestIsolationRule(Base):
    def setUp(self):
        super().setUp()
        self.do_init()
        self.write_findings()
        self.do_match()

    def test_nothing_counted_before_verify(self):
        """铁律：match 后未核实 → counted_from_expert=0、unverified_omissions=4"""
        js = self.do_show()
        self.assertEqual(js["counted_from_expert"], 0)
        self.assertEqual(js["unverified_omissions"], 4)
        self.assertEqual(js["omission_candidates"], 4)
        self.assertEqual(js["confirmed"], 0)
        self.assertEqual(js["rejected"], 0)

    def test_rejected_never_counted(self):
        """verify rejected（专家误判）→ counted_from_expert 仍 0"""
        e = self.find_item(self.do_show()["items"], "多域客户端概念未定义")
        code, js, err = self.do_verify(
            e["id"], "rejected",
            evidence="全文检索无「多域客户端」，专家误判")
        self.assertEqual(code, 0, err)
        show = self.do_show()
        self.assertEqual(show["rejected"], 1)
        self.assertEqual(show["counted_from_expert"], 0)
        self.assertEqual(show["unverified_omissions"], 3)

    def test_confirmed_counted(self):
        """verify confirmed --severity P1 → counted_from_expert=1"""
        e = self.find_item(self.do_show()["items"], "参考文献[12]")
        code, js, err = self.do_verify(
            e["id"], "confirmed", severity="P1",
            evidence="查原文参考文献列表，[12] 不存在，专家意见属实")
        self.assertEqual(code, 0, err)
        show = self.do_show()
        self.assertEqual(show["confirmed"], 1)
        self.assertEqual(show["counted_from_expert"], 1)
        self.assertEqual(show["unverified_omissions"], 3)
        item = self.find_item(show["items"], "参考文献[12]")
        self.assertEqual(item["state"], "confirmed")
        self.assertEqual(item["severity"], "P1")

    def test_confirmed_requires_severity_exit2(self):
        e = self.find_item(self.do_show()["items"], "参考文献[12]")
        code, js, err = self.do_verify(e["id"], "confirmed", evidence="属实")
        self.assertEqual(code, 2)

    def test_confirmed_requires_evidence_exit2(self):
        e = self.find_item(self.do_show()["items"], "参考文献[12]")
        code, js, err = self.do_verify(e["id"], "confirmed", severity="P1")
        self.assertEqual(code, 2)
        code, js, err = self.do_verify(e["id"], "confirmed",
                                       severity="P1", evidence="   ")
        self.assertEqual(code, 2)

    def test_rejected_requires_evidence_exit2(self):
        e = self.find_item(self.do_show()["items"], "多域客户端概念未定义")
        code, js, err = self.do_verify(e["id"], "rejected")
        self.assertEqual(code, 2)

    def test_verify_unknown_id_exit2(self):
        code, js, err = self.do_verify("E-99", "rejected", evidence="x")
        self.assertEqual(code, 2)

    def test_verify_before_match_exit2(self):
        """pending（未 match）条目不可 verify"""
        tmp2 = tempfile.TemporaryDirectory()
        rd2 = os.path.join(tmp2.name, ".review")
        code, js, err = run(["--run-dir", rd2, "init", "--comments", self.comments])
        self.assertEqual(code, 0, err)
        code, js, err = run(["--run-dir", rd2, "verify", "--id", "E-1",
                             "--result", "confirmed", "--severity", "P0",
                             "--evidence", "x"])
        self.assertEqual(code, 2)
        tmp2.cleanup()


# ────────────────────────── expert_reconcile.md 报告 ──────────────────────────

class TestReport(Base):
    def setUp(self):
        super().setUp()
        self.do_init()
        self.write_findings()
        self.do_match()

    def test_md_sections_present(self):
        md = self.read_md()
        self.assertIn("## 吻合", md)
        self.assertIn("## 疑似遗漏（隔离区，未核实不入报告）", md)
        self.assertIn("## 冲突", md)
        self.assertIn("## 核实记录", md)
        self.assertIn("| ID | 专家意见 | 对账结果 |", md)
        self.assertIn("| ID | 结果 | 严重度 | 证据 |", md)
        # 三态条目分别落在对应节
        self.assertIn("多域客户端概念未定义", md)
        self.assertIn("E-1", md)

    def test_md_verification_rows_appended(self):
        """verify 后核实记录表追加行；已核实条目离开隔离区节"""
        items = self.do_show()["items"]
        e_client = self.find_item(items, "多域客户端概念未定义")
        e_cite = self.find_item(items, "参考文献[12]")
        code, js, err = self.do_verify(
            e_client["id"], "rejected",
            evidence="全文检索无「多域客户端」，专家误判")
        self.assertEqual(code, 0, err)
        code, js, err = self.do_verify(
            e_cite["id"], "confirmed", severity="P1",
            evidence="原文参考文献列表无[12]，属实")
        self.assertEqual(code, 0, err)

        md = self.read_md()
        record = md.split("## 核实记录", 1)[1]
        self.assertIn("| %s | rejected | — | 全文检索无「多域客户端」，专家误判 |"
                      % e_client["id"], record)
        self.assertIn("| %s | confirmed | P1 | 原文参考文献列表无[12]，属实 |"
                      % e_cite["id"], record)
        # 隔离区节不再包含已核实条目
        quarantine = md.split("## 疑似遗漏（隔离区，未核实不入报告）", 1)[1] \
                       .split("## 冲突", 1)[0]
        self.assertNotIn(e_client["id"], quarantine)
        self.assertNotIn(e_cite["id"], quarantine)

    def test_match_stdout_same_shape_as_show(self):
        """match 的 stdout JSON 与 show 同构，外加 reconcile_file"""
        show = self.do_show()
        code, js, err = run(["--run-dir", self.run_dir, "match"])
        self.assertEqual(code, 0, err)
        for key in ("success", "total", "matched", "omission_candidates",
                    "unverified_omissions", "conflicts", "confirmed",
                    "rejected", "counted_from_expert", "items"):
            self.assertIn(key, js)
            self.assertEqual(js[key], show[key])
        self.assertIn("reconcile_file", js)


# ────────────────────────── docx 原生支持（条目21） ──────────────────────────

def _esc(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def build_docx(path, paragraphs):
    """构造最小合法 docx（仅 word/document.xml）。
    paragraphs: [(text, numbered)]，numbered=True 模拟 Word 自动列表段落
    （编号在 w:numPr 而不在正文文本中）。"""
    body = []
    for text, numbered in paragraphs:
        ppr = ("<w:pPr><w:numPr><w:ilvl w:val=\"0\"/>"
               "<w:numId w:val=\"1\"/></w:numPr></w:pPr>") if numbered else ""
        body.append("<w:p>%s<w:r><w:t xml:space=\"preserve\">%s</w:t></w:r></w:p>"
                    % (ppr, _esc(text)))
    doc = ("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
           "<w:document xmlns:w=\"http://schemas.openxmlformats.org/"
           "wordprocessingml/2006/main\"><w:body>%s</w:body></w:document>"
           % "".join(body))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", doc.encode("utf-8"))
    return path


class TestDocxComments(Base):
    """专家意见 .docx：init 原生解析（门禁 G2 裁决：零第三方依赖）"""

    def make_comments_docx(self, paragraphs):
        path = os.path.join(self.dir, "expert_comments.docx")
        return build_docx(path, paragraphs)

    def init_docx(self, paragraphs):
        self.comments = self.make_comments_docx(paragraphs)
        return self.do_init()

    def test_init_parses_docx_entries(self):
        js = self.init_docx([
            ("1. §3.2 的实验基线数据描述自相矛盾，数值缺少出处。", False),
            ("图4.1 的架构图分辨率过低，图例文字无法辨认。", True),   # Word 列表段落
            ("", False),                                              # 空段落分隔
            ("结论部分过度扩展。", True),
        ])
        self.assertEqual(js["count"], 3)
        with open(os.path.join(self.run_dir, "expert_items.json"),
                  encoding="utf-8") as f:
            data = json.load(f)
        ids = [e["id"] for e in data["entries"]]
        self.assertEqual(ids, ["E-1", "E-2", "E-3"])
        # 文本前缀剥离（md 起始标记）与 Word 列表段落（numPr → 条目）
        self.assertEqual(data["entries"][0]["text"],
                         "§3.2 的实验基线数据描述自相矛盾，数值缺少出处。")
        self.assertEqual(data["entries"][1]["text"],
                         "图4.1 的架构图分辨率过低，图例文字无法辨认。")
        self.assertTrue(data["comments_file"].endswith("expert_comments.docx"))

    def test_docx_continuation_merged(self):
        """Word 列表段落后续接的普通段落归并到前一条目"""
        js = self.init_docx([
            ("方法部分描述不完整：数据预处理流程缺失，", True),
            ("影响可复现性。", False),
        ])
        self.assertEqual(js["count"], 1)
        with open(os.path.join(self.run_dir, "expert_items.json"),
                  encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("影响可复现性。", data["entries"][0]["text"])

    def test_docx_match_pipeline(self):
        """docx init → match 三态贯通（与 md 入口同构）"""
        self.init_docx([
            ("§3.2 的实验基线数据描述自相矛盾，数值缺少出处。", True),
            ("表4.1 的数据单位标注错误。", True),
        ])
        self.write_findings()
        js = self.do_match()
        self.assertEqual(js["total"], 2)
        self.assertEqual(js["matched"], 1)          # §3.2 基线数据 → P0#1
        self.assertEqual(js["conflicts"], 1)        # 表4.1 → 已撤回/误报 → conflict
        self.assertEqual(js["counted_from_expert"], 0)   # 隔离铁律不变

    def test_corrupt_docx_exit1(self):
        """非 zip 的 .docx（如纯文本改名）→ exit 1 明确报错，不静默
        （expert_reconcile 的 fail() 契约：错误走 stderr + 非零退出码）"""
        self.comments = os.path.join(self.dir, "fake.docx")
        with open(self.comments, "w", encoding="utf-8") as f:
            f.write("这不是 docx，只是改了扩展名的文本\n")
        code, js, err = run(["--run-dir", self.run_dir, "init",
                             "--comments", self.comments])
        self.assertEqual(code, 1)
        self.assertIsNone(js)                    # stdout 无 JSON（stderr 契约）
        self.assertIn("无法解析 docx", err)


# ────────────────────────── report：交付后同轮追加对账（条目22，门禁 G2' 裁决） ──────────────────────────

CHAIN_R1_R2 = """# 版本谱系 — paper-yu

- doctype：thesis

## r1（v1，2026-11-10）

- 版本文件：draft/draft.md（hash: abcd1234）
- 决议：Major Revision（映射评分 6）
- 发现：P0 2 / P1 2 / P2 0；撤回 0 条

## r2（v2，2026-11-11，核验式复审）

- 决议：Accept（映射评分 9）
"""

INDEX_MD = """# 论文审查索引

> 一行一篇（paper-review Step 6 追加；路径相对论文目录）。

| 稿件 | doctype | 当前轮次 | 决议 | 日期 | 报告路径 |
|------|---------|----------|------|------|----------|
| paper-yu | thesis | r1 | Major Revision | 2026-11-10 | reports/r1-审阅报告.md |
"""


class TestReport(Base):
    """report 子命令：rN-综合审阅意见.md + chain「专家对账」行（原决议不变）+ INDEX 同步。
    夹具态：match 后 E-1/E-2/E-4 吻合、E-6 冲突、E-3/E-5/E-7/E-8 隔离区；
    verify E-5 → confirmed P0（专家新增）、E-3 → rejected（多域客户端误判，he-paper 教训）。
    面板基线 P0 2 / P1 2 / P2 0（FINDINGS 统计行）→ 合并后 P0 3 / P1 2 / P2 0，总计 5。"""

    def setUp(self):
        super().setUp()
        self.paper_dir = os.path.join(self.dir, "paper-yu")
        os.makedirs(os.path.join(self.paper_dir, "reports"), exist_ok=True)
        os.makedirs(self.run_dir, exist_ok=True)
        self.chain = os.path.join(self.run_dir, "chain.md")
        with open(self.chain, "w", encoding="utf-8", newline="\n") as f:
            f.write(CHAIN_R1_R2)
        self.index = os.path.join(self.dir, "INDEX.md")
        with open(self.index, "w", encoding="utf-8", newline="\n") as f:
            f.write(INDEX_MD)

    def prepare(self):
        """init → match → verify（E-5 confirmed P0 / E-3 rejected）"""
        self.do_init()
        self.write_findings()
        self.do_match()
        code, js, err = self.do_verify("E-5", "confirmed",
                                       evidence="原文核对参考文献表，确无 [12] 条目",
                                       severity="P0")
        self.assertEqual(code, 0, err)
        code, js, err = self.do_verify("E-3", "rejected",
                                       evidence="全文不存在「多域客户端」一词，专家误判")
        self.assertEqual(code, 0, err)

    def do_report(self, round_no=1, paper_dir=None):
        args = ["--run-dir", self.run_dir, "report",
                "--paper-dir", paper_dir or self.paper_dir,
                "--round", str(round_no)]
        return run(args)

    def read_report(self, round_no=1):
        path = os.path.join(self.paper_dir, "reports",
                            "r%d-综合审阅意见.md" % round_no)
        with open(path, encoding="utf-8") as f:
            return f.read()

    # ── 产物内容 ──

    def test_report_artifact_content(self):
        self.prepare()
        code, js, err = self.do_report()
        self.assertEqual(code, 0, err)
        text = self.read_report()
        self.assertIn("# r1 综合审阅意见（交付后专家对账 · 同轮追加）", text)
        self.assertIn("## 三态对账表", text)
        self.assertIn("新增（来源=专家）", text)      # E-5 confirmed
        self.assertIn("排除（专家误判）", text)        # E-3 rejected
        self.assertIn("吻合", text)                    # E-1/E-2/E-4
        self.assertIn("冲突（未决分歧）", text)        # E-6
        self.assertIn("未核实遗漏（不计入）", text)    # E-7/E-8
        # 合并后分布：面板 P0 2 + 专家新增 1 = 3；总计 4 + 1 = 5
        self.assertIn("| P0 | 2 | 1 | 3 |", text)
        self.assertIn("| P1 | 2 | 0 | 2 |", text)
        self.assertIn("| 总计 | 4 | 1 | 5 |", text)
        self.assertIn("计数规则", text)

    def test_pending_disputes_section(self):
        self.prepare()
        self.do_report()
        text = self.read_report()
        dispute = text.split("## 未决分歧（交用户裁决）")[1].split("## 合并后")[0]
        self.assertIn("E-6", dispute)   # 冲突 → 未决
        self.assertIn("E-7", dispute)   # 未核实遗漏 → 未决
        self.assertIn("E-8", dispute)
        self.assertNotIn("E-5", dispute)   # confirmed 不属未决
        self.assertNotIn("E-3", dispute)   # rejected 不属未决

    def test_report_stdout_json(self):
        self.prepare()
        code, js, err = self.do_report()
        self.assertEqual(code, 0, err)
        self.assertTrue(js["success"])
        self.assertEqual(js["round"], 1)
        self.assertTrue(js["report"].endswith("reports/r1-综合审阅意见.md"))
        self.assertEqual(js["distribution"]["panel"]["P0"], 2)
        self.assertEqual(js["distribution"]["expert_added"], {"P0": 1})
        self.assertEqual(js["distribution"]["combined"]["P0"], 3)
        self.assertEqual(js["distribution"]["combined"]["total"], 5)
        self.assertEqual(js["counted_from_expert"], 1)
        self.assertTrue(js["chain_updated"])
        self.assertTrue(js["index_updated"])

    # ── chain.md：追加对账行、原决议不变、幂等 ──

    def test_chain_appended_and_decision_intact(self):
        self.prepare()
        code, js, err = self.do_report()
        self.assertEqual(code, 0, err)
        with open(self.chain, encoding="utf-8") as f:
            chain = f.read()
        self.assertIn("- 专家对账（", chain)
        self.assertIn("原决议不变", chain)
        # 原决议与 r2 节不受影响
        self.assertIn("- 决议：Major Revision（映射评分 6）", chain)
        self.assertIn("- 决议：Accept（映射评分 9）", chain)
        # 对账行落在 r1 节内（## r1 与 ## r2 之间）
        r1_sec = chain.split("## r1")[1].split("## r2")[0]
        self.assertIn("- 专家对账（", r1_sec)

    def test_chain_rerun_idempotent(self):
        self.prepare()
        self.do_report()
        self.do_report()
        with open(self.chain, encoding="utf-8") as f:
            chain = f.read()
        self.assertEqual(chain.count("- 专家对账（"), 1)

    # ── INDEX.md：路径同步且不重复追加 ──

    def test_index_synced_once(self):
        self.prepare()
        self.do_report()
        self.do_report()
        with open(self.index, encoding="utf-8") as f:
            index = f.read()
        row = [l for l in index.splitlines() if "paper-yu" in l][0]
        self.assertIn("reports/r1-审阅报告.md", row)          # 原路径保留
        self.assertIn("reports/r1-综合审阅意见.md", row)      # 新路径已加
        self.assertEqual(row.count("综合审阅意见"), 1)         # 幂等

    # ── 失败路径 ──

    def test_report_before_match_exit1(self):
        self.do_init()
        self.write_findings()
        code, js, err = self.do_report()
        self.assertEqual(code, 1)
        self.assertIn("match", err)

    def test_report_missing_merged_exit1(self):
        self.prepare()
        os.remove(os.path.join(self.run_dir, "merged_findings.md"))
        code, js, err = self.do_report()
        self.assertEqual(code, 1)
        self.assertIn("merged_findings.md", err)

    def test_report_merged_without_stats_line_exit1(self):
        self.prepare()
        self.write_findings("# 合并审查发现\n\n（统计行缺失）\n")
        code, js, err = self.do_report()
        self.assertEqual(code, 1)
        self.assertIn("统计行", err)

    def test_report_missing_chain_exit1(self):
        self.prepare()
        os.remove(self.chain)
        code, js, err = self.do_report()
        self.assertEqual(code, 1)
        self.assertIn("chain.md", err)

    def test_report_round_section_missing_exit1(self):
        self.prepare()
        with open(self.chain, "w", encoding="utf-8", newline="\n") as f:
            f.write(CHAIN_R1_R2.replace("## r1（", "## r9（"))
        code, js, err = self.do_report()
        self.assertEqual(code, 1)
        self.assertIn("r1", err)

    def test_report_paper_dir_missing_exit2(self):
        self.prepare()
        code, js, err = self.do_report(
            paper_dir=os.path.join(self.dir, "no-such-paper"))
        self.assertEqual(code, 2)

    # ── 真实布局：run_dir=.review/r1，chain 在 .review/ 根（上级目录回退） ──

    def test_nested_run_dir_chain_fallback(self):
        nested = os.path.join(self.dir, "paper2", ".review", "r1")
        os.makedirs(nested, exist_ok=True)
        chain = os.path.join(self.dir, "paper2", ".review", "chain.md")
        with open(chain, "w", encoding="utf-8", newline="\n") as f:
            f.write(CHAIN_R1_R2)
        paper2 = os.path.join(self.dir, "paper2")
        os.makedirs(os.path.join(paper2, "reports"), exist_ok=True)
        self.run_dir = nested
        self.prepare()
        code, js, err = run(["--run-dir", nested, "report",
                             "--paper-dir", paper2, "--round", "1",
                             "--index", self.index])
        self.assertEqual(code, 0, err)
        with open(chain, encoding="utf-8") as f:
            self.assertIn("- 专家对账（", f.read())
        self.assertTrue(os.path.isfile(os.path.join(
            paper2, "reports", "r1-综合审阅意见.md")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
