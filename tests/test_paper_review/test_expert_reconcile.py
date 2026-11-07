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

运行：python tests/test_paper_review/test_expert_reconcile.py
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
