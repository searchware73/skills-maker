#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_numeric_checks.py — S7 数值审计复算检查库单元测试

覆盖（含规格给定的三个真实案例数值）：
  - weighted_identity：薛 表3.1（复算 66.54 vs 稿件 69.11 → fail，|Δ|≈2.57）；
    权重和≠1 → warning + normalized；自洽 → pass
  - table_sums：仿真稿 表6-9（Ex 行 Σcells=72.9 vs stated_sum=77.6 → fail，其余行 pass）
  - abstract_numbers：李 表3.4/3.5（摘要 91.33 正文仅 83.28 → fail + 正文相近值提示）；
    年份/纯序号跳过；摘要零数字 → warn
  - percent_basis：before=60→after=75 声称 15%（percent → fail 口径混淆；point → pass）；
    before=0 → error
  - CLI：--output 复算表（表头/fail 行/ID 行标签后缀/判定列）、未知 type → error、
    JSON 非法 → exit 1、缺 --input → exit 2、stdout 汇总计数、任意 cwd 可运行

运行：python tests/test_paper_review/test_numeric_checks.py
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
    HERE, "..", "..", "skills", "paper-review", "scripts", "numeric_checks"))


def run(args, cwd=None):
    """运行 numeric_checks 包目录，返回 (exit_code, stdout_json, stderr)"""
    p = subprocess.run([sys.executable, SCRIPT] + args,
                       capture_output=True, cwd=cwd)
    out = p.stdout.decode("utf-8", errors="replace")
    err = p.stderr.decode("utf-8", errors="replace")
    try:
        return p.returncode, json.loads(out), err
    except json.JSONDecodeError:
        return p.returncode, None, out + err


# ────────────────────────── 真实案例夹具 ──────────────────────────

# 案例1 薛 表3.1：0.40×72.30 + 0.35×64.10 + 0.25×60.74 = 66.54，稿件 69.11
XUE_CHECK = {
    "id": "xue31", "type": "weighted_identity",
    "label": "薛 表3.1 综合指数加权自洽",
    "components": [
        {"name": "作战效能", "weight": 0.40, "value": 72.30},
        {"name": "保障效能", "weight": 0.35, "value": 64.10},
        {"name": "训练效益", "weight": 0.25, "value": 60.74},
    ],
    "stated_total": 69.11,
}

# 案例2 仿真稿 表6-9：Ex 行 24.5+25.2+23.2 = 72.9，稿件行和 77.6
SIM_CHECK = {
    "id": "sim69", "type": "table_sums",
    "label": "仿真稿 表6-9 行和勾稽",
    "rows": [
        {"label": "Fx", "cells": [21.3, 22.4, 23.1], "stated_sum": 66.8},
        {"label": "Ex", "cells": [24.5, 25.2, 23.2], "stated_sum": 77.6},
        {"label": "Gx", "cells": [18.9, 19.6, 20.1], "stated_sum": 58.6},
    ],
}

# 案例3 李 表3.4/3.5：摘要声称 91.33，正文只有 83.28（另含年份/纯序号干扰项）
LI_ABSTRACT = ("针对2023年演训任务提出综合评估改进方法：1. 重构指标体系；"
               "2. 优化组合权重。改进后某型装备综合得分达 91.33，较基线提升明显。")
LI_CHECK = {
    "id": "li34", "type": "abstract_numbers",
    "label": "李 表3.4/3.5 摘要数字交叉",
    "abstract": LI_ABSTRACT,
    "body_values": [{"value": 83.28, "label": "表3.4 组合赋权综合得分"}],
    # 真实案例 91.33↔83.28 相对差≈8.8%，提示阈值放宽到 10%（实现默认 5%）
    "near_threshold": 0.10,
}

# 案例4 摘要零数字 → warn
ZERO_CHECK = {
    "id": "zero", "type": "abstract_numbers", "label": "摘要零数字",
    "abstract": "本文提出一种面向综合评估的改进方法，并通过实验验证了所提方法的有效性与优越性。",
    "body_values": [],
}

# 案例5 百分比 vs 百分点：60→75，relative=25%，points=15，稿件声称 15
PB_PERCENT = {
    "id": "pb1", "type": "percent_basis", "label": "4.2节 命中率提升",
    "before": 60.0, "after": 75.0, "stated_change": 15.0, "stated_kind": "percent",
}
PB_POINT = dict(PB_PERCENT, id="pb2", stated_kind="point")

# 案例7a 未知 type
UNKNOWN_CHECK = {"id": "u1", "type": "quantum_check", "label": "未知类型"}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def run_checks(self, checks, extra_args=(), cwd=None):
        path = os.path.join(self.dir, "checks.json")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"checks": checks}, f, ensure_ascii=False)
        code, js, err = run(["--input", path] + list(extra_args), cwd=cwd)
        self.assertEqual(code, 0, err)
        self.assertIsNotNone(js, err)
        return js

    def result_by_id(self, js, cid):
        for r in js["results"]:
            if r.get("id") == cid:
                return r
        self.fail("result %s not found" % cid)


class TestWeightedIdentity(Base):
    def test_xue_table31_fail(self):
        """案例1：复算 66.54 vs 稿件 69.11 → fail，|Δ|≈2.5–2.6"""
        js = self.run_checks([XUE_CHECK])
        self.assertTrue(js["success"])
        r = self.result_by_id(js, "xue31")
        self.assertEqual(r["type"], "weighted_identity")
        self.assertEqual(r["status"], "fail")
        self.assertAlmostEqual(r["computed"], 66.54, places=3)
        self.assertEqual(r["stated_total"], 69.11)
        self.assertTrue(2.5 <= abs(r["delta"]) <= 2.6, r["delta"])
        self.assertAlmostEqual(r["weight_sum"], 1.0, places=6)
        self.assertNotIn("warning", r)          # 权重和=1，无附加警告
        self.assertEqual(js["fail"], 1)

    def test_weight_sum_warning(self):
        """权重和≠1 → warning + normalized，判定仍用 computed vs stated_total"""
        check = {
            "id": "w2", "type": "weighted_identity", "label": "权重和不足",
            "components": [{"name": "A", "weight": 0.5, "value": 70.0},
                           {"name": "B", "weight": 0.4, "value": 62.0}],
            "stated_total": 59.8,
        }
        js = self.run_checks([check])
        r = self.result_by_id(js, "w2")
        self.assertEqual(r["status"], "pass")   # computed=59.8 与稿件一致
        self.assertEqual(r["warning"], "权重和≠1")
        self.assertAlmostEqual(r["weight_sum"], 0.9, places=6)
        self.assertAlmostEqual(r["normalized"], 59.8 / 0.9, places=3)

    def test_consistent_pass(self):
        js = self.run_checks([dict(XUE_CHECK, id="xue31p", stated_total=66.54)])
        r = self.result_by_id(js, "xue31p")
        self.assertEqual(r["status"], "pass")
        self.assertAlmostEqual(r["delta"], 0.0, places=2)


class TestTableSums(Base):
    def test_sim_table69_row_fail(self):
        """案例2：Ex 行 Σ=72.9 vs stated_sum=77.6 → fail，其余行 pass"""
        js = self.run_checks([SIM_CHECK])
        r = self.result_by_id(js, "sim69")
        self.assertEqual(r["type"], "table_sums")
        self.assertEqual(r["status"], "fail")   # 非全 pass → 整体 fail
        self.assertEqual(r["failed_rows"], 1)
        by_label = {d["label"]: d for d in r["rows"]}
        self.assertEqual(by_label["Ex"]["status"], "fail")
        self.assertAlmostEqual(by_label["Ex"]["computed"], 72.9, places=3)
        self.assertEqual(by_label["Ex"]["stated_sum"], 77.6)
        self.assertEqual(by_label["Fx"]["status"], "pass")
        self.assertEqual(by_label["Gx"]["status"], "pass")
        self.assertIn("72.9", r["detail"])

    def test_all_rows_pass(self):
        rows = [dict(r) for r in SIM_CHECK["rows"]]
        rows[1]["stated_sum"] = 72.9            # 修正 Ex 行稿件值
        js = self.run_checks([dict(SIM_CHECK, id="sim69p", rows=rows)])
        r = self.result_by_id(js, "sim69p")
        self.assertEqual(r["status"], "pass")
        self.assertEqual(r["failed_rows"], 0)


class TestAbstractNumbers(Base):
    def test_li_unmatched_with_hint(self):
        """案例3：摘要 91.33 正文仅 83.28 → fail，detail 提示正文相近值；
        年份 2023 与纯序号 1./2. 应被跳过"""
        js = self.run_checks([LI_CHECK])
        r = self.result_by_id(js, "li34")
        self.assertEqual(r["type"], "abstract_numbers")
        self.assertEqual(r["status"], "fail")
        self.assertEqual(r["numbers"], ["91.33"])   # 年份/序号已跳过
        self.assertEqual(len(r["unmatched"]), 1)
        self.assertAlmostEqual(r["unmatched"][0]["nearest_value"], 83.28, places=6)
        self.assertIn("91.33", r["detail"])
        self.assertIn("正文无对应", r["detail"])
        self.assertIn("正文相近值", r["detail"])
        self.assertIn("83.28", r["detail"])

    def test_all_matched_pass(self):
        check = {
            "id": "ab2", "type": "abstract_numbers",
            "abstract": "组合权重 0.4 与 0.35 下综合得分为 66.54。",
            "body_values": [{"value": 0.4, "label": "表3.1 权重A"},
                            {"value": 0.35, "label": "表3.1 权重B"},
                            {"value": 66.54, "label": "表3.1 合计"}],
        }
        js = self.run_checks([check])
        r = self.result_by_id(js, "ab2")
        self.assertEqual(r["status"], "pass")
        self.assertEqual(r["numbers"], ["0.4", "0.35", "66.54"])
        self.assertEqual(r["unmatched"], [])

    def test_zero_numbers_warn(self):
        """案例4：require_numbers 缺省 true 且摘要无数字 → warn"""
        js = self.run_checks([ZERO_CHECK])
        r = self.result_by_id(js, "zero")
        self.assertEqual(r["status"], "warn")
        self.assertIn("摘要零数字", r["detail"])
        self.assertEqual(r["numbers"], [])
        self.assertEqual(js["warn"], 1)


class TestPercentBasis(Base):
    def test_percent_kind_confusion(self):
        """案例5a：60→75 声称 percent 变化 15，实际 relative=25 → fail 口径混淆"""
        js = self.run_checks([PB_PERCENT])
        r = self.result_by_id(js, "pb1")
        self.assertEqual(r["type"], "percent_basis")
        self.assertEqual(r["status"], "fail")
        self.assertAlmostEqual(r["relative"], 25.0, places=6)
        self.assertAlmostEqual(r["points"], 15.0, places=6)
        self.assertIn("口径混淆", r["detail"])
        self.assertIn("15", r["detail"])

    def test_point_kind_pass(self):
        """案例5b：同一数据按 point 口径 → pass"""
        js = self.run_checks([PB_POINT])
        r = self.result_by_id(js, "pb2")
        self.assertEqual(r["status"], "pass")
        self.assertAlmostEqual(r["expected"], 15.0, places=6)

    def test_before_zero_error(self):
        check = dict(PB_PERCENT, id="pb0", before=0.0, after=5.0)
        js = self.run_checks([check])
        r = self.result_by_id(js, "pb0")
        self.assertEqual(r["status"], "error")
        self.assertIn("before=0", r["detail"])


class TestCLI(Base):
    MIX = [XUE_CHECK, SIM_CHECK, LI_CHECK, ZERO_CHECK,
           PB_PERCENT, PB_POINT, UNKNOWN_CHECK]

    def test_summary_counts_and_output_md(self):
        """案例6：--output 复算表写出；stdout 汇总计数"""
        out = os.path.join(self.dir, "recalc.md")
        js = self.run_checks(self.MIX, ["--output", out])
        self.assertTrue(js["success"])
        self.assertEqual(js["total"], 7)
        self.assertEqual(js["pass"], 1)     # pb2
        self.assertEqual(js["fail"], 4)     # xue31 / sim69 / li34 / pb1
        self.assertEqual(js["warn"], 1)     # zero
        self.assertEqual(js["error"], 1)    # u1
        self.assertEqual(js["output"], out.replace("\\", "/"))
        self.assertTrue(os.path.isfile(out))
        with open(out, encoding="utf-8") as f:
            md = f.read()
        self.assertIn("# S7 复算表", md)
        self.assertIn("| ID | 检查 | 标签 | 复算值 | 稿件值 | Δ | 判定 |", md)
        self.assertIn("sim69/Ex", md)       # table_sums 失败行 ID 加行标签后缀
        self.assertIn("| fail |", md)
        self.assertIn("| warn |", md)
        self.assertIn("| error |", md)
        self.assertIn("| pass |", md)

    def test_no_output_by_default(self):
        js = self.run_checks([XUE_CHECK])
        self.assertIsNone(js["output"])

    def test_unknown_type_error(self):
        """案例7a：未知 type → 该条 status=error，整体仍 exit 0"""
        js = self.run_checks([UNKNOWN_CHECK])
        self.assertTrue(js["success"])
        r = self.result_by_id(js, "u1")
        self.assertEqual(r["status"], "error")
        self.assertIn("未知检查类型", r["detail"])
        self.assertIn("quantum_check", r["detail"])
        self.assertEqual(js["error"], 1)

    def test_invalid_json_exit1(self):
        """案例7b：输入 JSON 非法 / 文件不存在 → exit 1"""
        bad = os.path.join(self.dir, "bad.json")
        with open(bad, "w", encoding="utf-8", newline="\n") as f:
            f.write("{{{ 这不是 JSON")
        code, js, err = run(["--input", bad])
        self.assertEqual(code, 1)
        self.assertIsNone(js)
        code, js, err = run(["--input", os.path.join(self.dir, "nope.json")])
        self.assertEqual(code, 1)

    def test_missing_input_exit2_and_help(self):
        code, js, err = run([])             # 缺 --input → 参数错误
        self.assertEqual(code, 2)
        code, js, err = run(["--help"])     # --help 正常输出用法
        self.assertEqual(code, 0)
        self.assertIn("--input", err + (js or ""))

    def test_runs_from_any_cwd(self):
        """sys.path 插入自身目录 → 任意 cwd（含包目录本身）可运行"""
        js = self.run_checks([XUE_CHECK], cwd=self.dir)
        self.assertEqual(self.result_by_id(js, "xue31")["status"], "fail")
        js = self.run_checks([XUE_CHECK], cwd=SCRIPT)
        self.assertEqual(js["total"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
