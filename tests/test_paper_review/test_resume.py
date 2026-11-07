#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_resume.py — resume.py 跨终端续跑快照单元测试

覆盖：
  - init：创建 RESUME.md（7 阶段全量 pending）；元信息往返；已存在时不覆盖
    （existed=true）；--force 覆盖重建
  - set ：多阶段 状态/产物/备注 更新；未提供的列保留原值；刷新「更新时间」；
          备注含竖线时的表格转义
  - next：恢复点往返（动作/命令/多行环境备忘）；未提供字段保留原值
  - show：解析与写入自产自得一致
  - check：新鲜文件通过（exit 0）；in_progress 缺「下一步动作」失败（exit 1）；
           补动作后恢复通过；文件缺失；缺阶段行；非法状态
  - 非法 stage/status 枚举 → exit 2；未 init 即 set/next/show → exit 1

运行：python tests/test_paper_review/test_resume.py
"""
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(os.path.join(
    HERE, "..", "..", "skills", "paper-review", "scripts", "resume.py"))

STAGES = ["step0-env", "stage1-panel", "stage2-deai", "stage3-merge",
          "stage4-fix", "stage5-converge", "step6-report"]
TS_RE = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$"


def run(args, cwd=None):
    """运行 resume.py，返回 (exit_code, stdout_json, stderr)"""
    p = subprocess.run([sys.executable, SCRIPT] + args,
                       capture_output=True, cwd=cwd)
    out = p.stdout.decode("utf-8", errors="replace")
    err = p.stderr.decode("utf-8", errors="replace")
    try:
        return p.returncode, json.loads(out), err
    except json.JSONDecodeError:
        return p.returncode, None, out + err


def to_posix(p):
    return p.replace("\\", "/")


class ResumeTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.run_dir = os.path.join(self.dir, "run1")
        self.resume = os.path.join(self.run_dir, "RESUME.md")

    def tearDown(self):
        self.tmp.cleanup()

    def init(self, extra=()):
        code, js, err = run(["--run-dir", self.run_dir, "init"] + list(extra))
        self.assertEqual(code, 0, err)
        return js

    def set_stage(self, stage, status, extra=()):
        code, js, err = run(["--run-dir", self.run_dir, "set",
                             "--stage", stage, "--status", status] + list(extra))
        self.assertEqual(code, 0, err)
        return js

    def show(self):
        code, js, err = run(["--run-dir", self.run_dir, "show"])
        self.assertEqual(code, 0, err)
        return js

    def check(self):
        return run(["--run-dir", self.run_dir, "check"])

    def read_md(self):
        with open(self.resume, encoding="utf-8") as f:
            return f.read()

    def write_md(self, text):
        with open(self.resume, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)


class TestInit(ResumeTestCase):
    def test_init_creates_resume(self):
        js = self.init()
        self.assertTrue(js["success"])
        self.assertFalse(js["existed"])
        self.assertTrue(os.path.isfile(self.resume))
        self.assertEqual(js["resume_file"], to_posix(os.path.abspath(self.resume)))
        # md 结构：头部 + 阶段状态表 + 恢复点节
        md = self.read_md()
        self.assertIn("## 阶段状态", md)
        self.assertIn("## 恢复点", md)
        self.assertIn("| 阶段 | 状态 | 产物 | 备注 |", md)
        # show：7 阶段按固定顺序全量 pending，产物/恢复点为空
        snap = self.show()
        self.assertTrue(snap["success"])
        self.assertEqual(list(snap["stage_status"].keys()), STAGES)
        self.assertTrue(all(v == "pending" for v in snap["stage_status"].values()))
        self.assertEqual(snap["artifacts"], {})
        self.assertEqual(snap["next"], {"action": "", "cmd": "", "env": []})
        self.assertRegex(snap["meta"]["updated"], TS_RE)
        self.assertIsNone(snap["meta"]["paper"])

    def test_init_meta_roundtrip(self):
        self.init(["--paper", "Digital Twin Survey", "--version", "v2",
                   "--round", "r1", "--doctype", "journal"])
        meta = self.show()["meta"]
        self.assertEqual(meta["paper"], "Digital Twin Survey")
        self.assertEqual(meta["version"], "v2")
        self.assertEqual(meta["round"], "r1")
        self.assertEqual(meta["doctype"], "journal")
        self.assertRegex(meta["updated"], TS_RE)

    def test_init_existing_not_overwritten(self):
        self.init(["--paper", "A"])
        code, js, err = run(["--run-dir", self.run_dir, "init", "--paper", "B"])
        self.assertEqual(code, 0, err)
        self.assertTrue(js["success"])
        self.assertTrue(js["existed"])
        self.assertEqual(self.show()["meta"]["paper"], "A")   # 未被覆盖

    def test_init_force_overwrites(self):
        self.init(["--paper", "A"])
        code, js, err = run(["--run-dir", self.run_dir, "init",
                             "--paper", "B", "--force"])
        self.assertEqual(code, 0, err)
        self.assertFalse(js["existed"])
        self.assertEqual(self.show()["meta"]["paper"], "B")


class TestSetNextShow(ResumeTestCase):
    def test_set_multiple_stages_and_show(self):
        self.init()
        art = os.path.join(self.dir, "stage0_env.json")
        js = self.set_stage("step0-env", "done",
                            ["--artifact", art, "--note", "环境就绪"])
        self.assertTrue(js["success"])
        self.assertEqual(js["stage"], "step0-env")
        self.assertEqual(js["status"], "done")
        self.set_stage("stage1-panel", "in_progress", ["--note", "专家组构建中"])
        snap = self.show()
        self.assertEqual(snap["stage_status"]["step0-env"], "done")
        self.assertEqual(snap["stage_status"]["stage1-panel"], "in_progress")
        self.assertEqual(snap["stage_status"]["stage2-deai"], "pending")
        self.assertEqual(snap["artifacts"], {"step0-env": to_posix(art)})
        self.assertEqual(list(snap["stage_status"].keys()), STAGES)   # 顺序不变

    def test_set_keeps_artifact_and_note_when_omitted(self):
        self.init()
        art = os.path.join(self.dir, "a.json")
        self.set_stage("step0-env", "done", ["--artifact", art, "--note", "N1"])
        self.set_stage("step0-env", "failed")     # 未提供 artifact/note
        snap = self.show()
        self.assertEqual(snap["stage_status"]["step0-env"], "failed")
        self.assertEqual(snap["artifacts"], {"step0-env": to_posix(art)})
        self.assertIn("N1", self.read_md())        # 备注保留

    def test_set_refreshes_updated(self):
        self.init()
        md = re.sub(r"(?m)^- 更新时间:.*$", "- 更新时间: 2000-01-01 00:00",
                    self.read_md())
        self.assertIn("2000-01-01 00:00", md)
        self.write_md(md)
        self.set_stage("step0-env", "done")
        updated = self.show()["meta"]["updated"]
        self.assertNotEqual(updated, "2000-01-01 00:00")
        self.assertRegex(updated, TS_RE)

    def test_set_note_with_pipe_stays_parseable(self):
        self.init()
        self.set_stage("stage3-merge", "done", ["--note", "含 | 竖线"])
        snap = self.show()
        self.assertEqual(snap["stage_status"]["stage3-merge"], "done")
        self.assertEqual(list(snap["stage_status"].keys()), STAGES)
        self.assertIn("含 \\| 竖线", self.read_md())   # 表格内已转义

    def test_next_roundtrip(self):
        self.init()
        code, js, err = run(["--run-dir", self.run_dir, "next",
                             "--action", "继续执行 stage2-deai",
                             "--cmd", "python scripts/deai.py --run-dir run1",
                             "--env", "PYTHONIOENCODING=utf-8",
                             "--env", "需先激活 venv"])
        self.assertEqual(code, 0, err)
        self.assertTrue(js["success"])
        self.assertEqual(js["next_action"], "继续执行 stage2-deai")
        snap = self.show()
        self.assertEqual(snap["next"], {
            "action": "继续执行 stage2-deai",
            "cmd": "python scripts/deai.py --run-dir run1",
            "env": ["PYTHONIOENCODING=utf-8", "需先激活 venv"],
        })
        # md 人类可读性：恢复点节含对应行
        md = self.read_md()
        self.assertIn("- 下一步动作: 继续执行 stage2-deai", md)
        self.assertIn("- 恢复命令: python scripts/deai.py --run-dir run1", md)
        self.assertEqual(md.count("- 环境备忘: "), 2)

    def test_next_keeps_cmd_env_when_omitted(self):
        self.init()
        run(["--run-dir", self.run_dir, "next", "--action", "旧动作",
             "--cmd", "old-cmd", "--env", "E1"])
        code, js, err = run(["--run-dir", self.run_dir, "next",
                             "--action", "新动作"])
        self.assertEqual(code, 0, err)
        snap = self.show()
        self.assertEqual(snap["next"], {"action": "新动作", "cmd": "old-cmd",
                                        "env": ["E1"]})


class TestCheck(ResumeTestCase):
    def test_check_fresh_valid(self):
        self.init()
        code, js, err = self.check()
        self.assertEqual(code, 0, err)
        self.assertTrue(js["valid"])
        self.assertEqual(js["problems"], [])

    def test_check_in_progress_requires_next_action(self):
        self.init()
        self.set_stage("stage2-deai", "in_progress")
        code, js, err = self.check()
        self.assertEqual(code, 1)
        self.assertFalse(js["valid"])
        self.assertTrue(any("stage2-deai" in p for p in js["problems"]))
        # 补充「下一步动作」后恢复通过
        code, js, err = run(["--run-dir", self.run_dir, "next",
                             "--action", "继续去AI味"])
        self.assertEqual(code, 0, err)
        code, js, err = self.check()
        self.assertEqual(code, 0, err)
        self.assertTrue(js["valid"])

    def test_check_missing_file(self):
        code, js, err = run(["--run-dir", os.path.join(self.dir, "nope"),
                             "check"])
        self.assertEqual(code, 1)
        self.assertFalse(js["valid"])
        self.assertTrue(js["problems"])

    def test_check_missing_stage_row(self):
        self.init()
        lines = [ln for ln in self.read_md().splitlines()
                 if not ln.startswith("| stage3-merge ")]
        self.write_md("\n".join(lines) + "\n")
        code, js, err = self.check()
        self.assertEqual(code, 1)
        self.assertFalse(js["valid"])
        self.assertTrue(any("stage3-merge" in p for p in js["problems"]))

    def test_check_invalid_status(self):
        self.init()
        md = self.read_md().replace("| step0-env | pending |",
                                    "| step0-env | bogus |")
        self.assertIn("bogus", md)
        self.write_md(md)
        code, js, err = self.check()
        self.assertEqual(code, 1)
        self.assertFalse(js["valid"])
        self.assertTrue(any("step0-env" in p for p in js["problems"]))


class TestArgErrors(ResumeTestCase):
    def test_set_invalid_stage_exit2(self):
        self.init()
        code, js, err = run(["--run-dir", self.run_dir, "set",
                             "--stage", "stage9-nope", "--status", "done"])
        self.assertEqual(code, 2)

    def test_set_invalid_status_exit2(self):
        self.init()
        code, js, err = run(["--run-dir", self.run_dir, "set",
                             "--stage", "step0-env", "--status", "doing"])
        self.assertEqual(code, 2)

    def test_set_before_init_exit1(self):
        code, js, err = run(["--run-dir", self.run_dir, "set",
                             "--stage", "step0-env", "--status", "done"])
        self.assertEqual(code, 1)

    def test_next_before_init_exit1(self):
        code, js, err = run(["--run-dir", self.run_dir, "next",
                             "--action", "x"])
        self.assertEqual(code, 1)

    def test_show_before_init_exit1(self):
        code, js, err = run(["--run-dir", self.run_dir, "show"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
