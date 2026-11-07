#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_migrate_rounds.py — migrate_rounds.py 存量迁移单元测试（q10 原型树）

覆盖：
  - dry-run（缺省）：moves 计划（源→sources/v2、draft.md→draft-v2.md、
    response*.md→根、q10/.review 扁平产物→r1/、q10-1/.review→r2/）且文件系统零改动
  - --confirm：文件实际到位、config.json schema 2 完整（doctype/versions/rounds）、
    chain.md 骨架创建、q10-1 目录保留且 warnings 提示手工删除
  - 既有 config.json（含 exemptions）合并：exemptions/withdrawals/adjudications 保留
  - 参数错误 exit 2：--paper-dir / --new-dir 不存在、--new-version < 2
  - {new_dir} 无可迁移文件 → warnings 提示但仍 exit 0 且回填 config

运行：python tests/test_paper_review/test_migrate_rounds.py
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
    HERE, "..", "..", "skills", "paper-review", "scripts", "migrate_rounds.py"))


def run(args, cwd=None):
    """运行 migrate_rounds.py，返回 (exit_code, stdout_json, stderr)"""
    p = subprocess.run([sys.executable, SCRIPT] + args,
                       capture_output=True, cwd=cwd)
    out = p.stdout.decode("utf-8", errors="replace")
    err = p.stderr.decode("utf-8", errors="replace")
    try:
        return p.returncode, json.loads(out), err
    except json.JSONDecodeError:
        return p.returncode, None, out + err


def px(path):
    """绝对 posix 路径（与脚本输出的 from/to 同构）"""
    return os.path.abspath(path).replace("\\", "/")


def write(path, content="placeholder\n"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def build_q10_tree(base):
    """搭建 q10 原型树，返回 (q10, q10_1) 目录路径

    papers/q10/   paper.docx + draft.md + .review/{deai_log,merged_findings}.md
    papers/q10-1/ paper.docx + draft.md + response-v2.md + .review/{merged_findings,deai_log}.md
    """
    q10 = os.path.join(base, "papers", "q10")
    q10_1 = os.path.join(base, "papers", "q10-1")
    write(os.path.join(q10, "paper.docx"), "v1 source\n")
    write(os.path.join(q10, "draft.md"), "# v1 工作稿\n")
    write(os.path.join(q10, ".review", "deai_log.md"), "r1 deai\n")
    write(os.path.join(q10, ".review", "merged_findings.md"), "r1 findings\n")
    write(os.path.join(q10_1, "paper.docx"), "v2 source\n")
    write(os.path.join(q10_1, "draft.md"), "# v2 工作稿\n")
    write(os.path.join(q10_1, "response-v2.md"), "# 回复信\n")
    write(os.path.join(q10_1, ".review", "merged_findings.md"), "r2 findings\n")
    write(os.path.join(q10_1, ".review", "deai_log.md"), "r2 deai\n")
    return q10, q10_1


class TestDryRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.q10, self.q10_1 = build_q10_tree(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_dry_run_plan_and_no_fs_change(self):
        code, js, err = run(["--paper-dir", self.q10, "--new-dir", self.q10_1,
                             "--doctype", "problem-collection"])
        self.assertEqual(code, 0, err)
        self.assertTrue(js["success"])
        self.assertTrue(js["dry_run"])
        self.assertNotIn("moved", js)
        pairs = {(m["from"], m["to"]) for m in js["moves"]}
        expected = {
            # 步骤1：源文件 → sources/v2/
            (px(os.path.join(self.q10_1, "paper.docx")),
             px(os.path.join(self.q10, "sources", "v2", "paper.docx"))),
            # 步骤2：draft.md → draft-v2.md
            (px(os.path.join(self.q10_1, "draft.md")),
             px(os.path.join(self.q10, "draft-v2.md"))),
            # 步骤3：response*.md → 根目录（保留原名）
            (px(os.path.join(self.q10_1, "response-v2.md")),
             px(os.path.join(self.q10, "response-v2.md"))),
            # 步骤4：q10/.review 扁平旧产物 → r1/
            (px(os.path.join(self.q10, ".review", "deai_log.md")),
             px(os.path.join(self.q10, ".review", "r1", "deai_log.md"))),
            (px(os.path.join(self.q10, ".review", "merged_findings.md")),
             px(os.path.join(self.q10, ".review", "r1", "merged_findings.md"))),
            # 步骤5：q10-1/.review 全部产物 → r2/
            (px(os.path.join(self.q10_1, ".review", "merged_findings.md")),
             px(os.path.join(self.q10, ".review", "r2", "merged_findings.md"))),
            (px(os.path.join(self.q10_1, ".review", "deai_log.md")),
             px(os.path.join(self.q10, ".review", "r2", "deai_log.md"))),
        }
        self.assertTrue(expected.issubset(pairs),
                        "缺失计划: %s" % (expected - pairs))
        # dry-run 计划中的 config 已含 response 映射
        self.assertEqual(js["config"]["versions"]["v2"]["response"], "response-v2.md")
        # 文件系统零改动
        self.assertTrue(os.path.isfile(os.path.join(self.q10_1, "paper.docx")))
        self.assertTrue(os.path.isfile(os.path.join(self.q10_1, "draft.md")))
        self.assertTrue(os.path.isfile(os.path.join(self.q10_1, "response-v2.md")))
        self.assertTrue(os.path.isfile(os.path.join(self.q10, ".review", "deai_log.md")))
        self.assertFalse(os.path.exists(os.path.join(self.q10, "sources")))
        self.assertFalse(os.path.exists(os.path.join(self.q10, ".review", "r1")))
        self.assertFalse(os.path.exists(os.path.join(self.q10, ".review", "r2")))
        self.assertFalse(os.path.exists(os.path.join(self.q10, ".review", "config.json")))
        self.assertFalse(os.path.exists(os.path.join(self.q10, ".review", "chain.md")))

    def test_dry_run_empty_new_dir_warns_but_ok(self):
        empty = os.path.join(self.tmp.name, "papers", "q10-9")
        os.makedirs(empty)
        code, js, err = run(["--paper-dir", self.q10, "--new-dir", empty])
        self.assertEqual(code, 0, err)
        self.assertTrue(js["success"])
        self.assertTrue(any("未发现可迁移文件" in w for w in js["warnings"]))
        # config 回填计划仍存在
        self.assertEqual(js["config"]["schema"], 2)


class TestConfirm(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.q10, self.q10_1 = build_q10_tree(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_confirm_moves_config_chain(self):
        code, js, err = run(["--paper-dir", self.q10, "--new-dir", self.q10_1,
                             "--doctype", "problem-collection", "--confirm"])
        self.assertEqual(code, 0, err)
        self.assertTrue(js["success"])
        self.assertFalse(js["dry_run"])
        self.assertEqual(js["moved"], len(js["moves"]))
        # 文件实际到位
        for rel in [os.path.join("sources", "v2", "paper.docx"),
                    "draft-v2.md", "response-v2.md",
                    os.path.join(".review", "r1", "deai_log.md"),
                    os.path.join(".review", "r1", "merged_findings.md"),
                    os.path.join(".review", "r2", "merged_findings.md"),
                    os.path.join(".review", "r2", "deai_log.md")]:
            self.assertTrue(os.path.isfile(os.path.join(self.q10, rel)),
                            "缺文件: %s" % rel)
        # 旧扁平产物已移走
        self.assertFalse(os.path.exists(os.path.join(self.q10, ".review", "deai_log.md")))
        # config.json schema 完整
        cfg_path = os.path.join(self.q10, ".review", "config.json")
        self.assertTrue(os.path.isfile(cfg_path))
        with open(cfg_path, encoding="utf-8-sig") as f:
            cfg = json.load(f)
        self.assertEqual(cfg["schema"], 2)
        self.assertEqual(cfg["paper_dir"], px(self.q10))
        self.assertEqual(cfg["doctype"], "problem-collection")
        self.assertEqual(cfg["versions"]["v1"],
                         {"source_root": ".", "draft": "draft.md", "response": None})
        self.assertEqual(cfg["versions"]["v2"]["source_root"], "sources/v2")
        self.assertEqual(cfg["versions"]["v2"]["draft"], "draft-v2.md")
        self.assertEqual(cfg["versions"]["v2"]["response"], "response-v2.md")
        self.assertEqual(cfg["current_version"], "v2")
        self.assertEqual(cfg["rounds"], {"r1": {"version": "v1"},
                                         "r2": {"version": "v2"}})
        self.assertEqual(cfg["current_round"], "r2")
        self.assertEqual(cfg["exemptions"], [])
        self.assertEqual(cfg["withdrawals"], [])
        self.assertEqual(cfg["adjudications"], [])
        # chain.md 骨架
        chain_path = os.path.join(self.q10, ".review", "chain.md")
        self.assertTrue(os.path.isfile(chain_path))
        with open(chain_path, encoding="utf-8-sig") as f:
            chain = f.read()
        self.assertIn("# 版本谱系", chain)
        self.assertIn("## r1", chain)
        self.assertIn("## r2", chain)
        self.assertIn("决议：待回填", chain)
        self.assertIn("发现状态流转表：待回填", chain)
        # q10-1 绝不删除，warnings 提示手工处理
        self.assertTrue(os.path.isdir(self.q10_1))
        joined = "\n".join(js["warnings"])
        self.assertIn("已腾空", joined)
        self.assertIn("手工删除", joined)

    def test_confirm_merge_existing_config(self):
        cfg_path = os.path.join(self.q10, ".review", "config.json")
        old = {
            "schema": 1,
            "doctype": None,
            "exemptions": [{"id": "f3", "reason": "本次忽略：零参考文献"}],
            "withdrawals": [{"id": "f7"}],
            "adjudications": [{"id": "f5", "verdict": "保留"}],
            "rounds": {"r1": {"version": "v1", "note": "首轮"}},
        }
        write(cfg_path, json.dumps(old, ensure_ascii=False) + "\n")
        code, js, err = run(["--paper-dir", self.q10, "--new-dir", self.q10_1,
                             "--doctype", "problem-collection", "--confirm"])
        self.assertEqual(code, 0, err)
        with open(cfg_path, encoding="utf-8-sig") as f:
            cfg = json.load(f)
        # 既有清单/轮次记录保留
        self.assertEqual(cfg["exemptions"], old["exemptions"])
        self.assertEqual(cfg["withdrawals"], old["withdrawals"])
        self.assertEqual(cfg["adjudications"], old["adjudications"])
        self.assertEqual(cfg["rounds"]["r1"], {"version": "v1", "note": "首轮"})
        self.assertEqual(cfg["rounds"]["r2"], {"version": "v2"})
        # 新映射补齐
        self.assertEqual(cfg["schema"], 2)
        self.assertEqual(cfg["doctype"], "problem-collection")
        self.assertEqual(cfg["versions"]["v2"]["source_root"], "sources/v2")
        self.assertEqual(cfg["current_round"], "r2")
        # config.json 未被误移入 r1/
        self.assertFalse(os.path.exists(
            os.path.join(self.q10, ".review", "r1", "config.json")))

    def test_confirm_keeps_existing_chain(self):
        chain_path = os.path.join(self.q10, ".review", "chain.md")
        write(chain_path, "# 已有谱系\n")
        code, js, err = run(["--paper-dir", self.q10, "--new-dir", self.q10_1,
                             "--confirm"])
        self.assertEqual(code, 0, err)
        with open(chain_path, encoding="utf-8-sig") as f:
            self.assertEqual(f.read(), "# 已有谱系\n")   # 不被覆盖
        # chain.md 也未被误移入 r1/
        self.assertFalse(os.path.exists(
            os.path.join(self.q10, ".review", "r1", "chain.md")))


class TestArgErrors(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.q10, self.q10_1 = build_q10_tree(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_new_dir_exit2(self):
        code, js, err = run(["--paper-dir", self.q10,
                             "--new-dir", os.path.join(self.tmp.name, "nope")])
        self.assertEqual(code, 2)

    def test_missing_paper_dir_exit2(self):
        code, js, err = run(["--paper-dir", os.path.join(self.tmp.name, "nope"),
                             "--new-dir", self.q10_1])
        self.assertEqual(code, 2)

    def test_bad_new_version_exit2(self):
        code, js, err = run(["--paper-dir", self.q10, "--new-dir", self.q10_1,
                             "--new-version", "1"])
        self.assertEqual(code, 2)

    def test_same_dir_exit2(self):
        code, js, err = run(["--paper-dir", self.q10, "--new-dir", self.q10])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
