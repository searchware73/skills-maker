# convergence-criteria.md — 收敛条件与停滞处理

> **可替换模板**：paper-review 阶段5（收敛循环）判定依据。
> 机械判定由 `scripts/convergence_check.py` 执行（阈值改动需同步该脚本顶部常量）。

---

## 收敛条件（全部满足才算收敛）

1. 去AI评分 ≥ 8/10
2. 同行评审评分 ≥ 7/10
3. P0 问题数 = 0
4. P1 问题数 ≤ 3
5. 连续2轮无新增 P0/P1 问题
   （脚本近似判定：当前轮与上一轮均 P0=0 且当前 P1 不高于上一轮；首轮因历史不足恒不满足）

## 停滞检测

- **定义**：连续2轮各维度评分无改善（每轮的去AI评分与同行评审评分提升均 < 0.5 分）
- **处理**：暂停循环，向用户报告当前状态，请求决策（**继续 / 停止 / 调整策略**）
- 脚本输出 `action: "escalate"`，由 SKILL.md 通过 AskUserQuestion 交用户裁决

## 最大轮数

- **默认**：3轮（`--rounds` 可调）
- **达到最大轮数**：输出当前状态 + 未解决问题清单，不再循环（`action: "stop"`）

## 评分来源

- **去AI评分**：基于 Tier1/Tier2 词汇残留数、结构问题数计算，公式：

  ```
  去AI评分 = max(1, min(10, 10 − Tier1/Tier2残留词数 × 0.5 − 结构问题数 × 0.5))
  ```

  由阶段5复查（stop-slop 快速扫描）统计残留后算出，经 `--deai-score` 传入 convergence_check.py 判定。

- **同行评审评分**：ars-reviewer 的 Editorial Decision 映射：

  | Editorial Decision | 评分 |
  |--------------------|------|
  | Accept | 9 |
  | Minor Revision | 8 |
  | Major Revision | 6 |
  | Reject | 4 |

  介于两档之间时取中值 ±1，按意见条数微调后经 `--peer-score` 传入。

## 收敛记录格式（convergence.md）

```markdown
# 收敛记录

| 轮次 | 去AI评分 | 同行评审 | P0 | P1 | P2 | 状态 |
|------|---------|---------|----|----|----|----|
| 1    | 6.5     | 6.0     | 2  | 5  | 8  | continue |
| 2    | 8.0     | 7.5     | 0  | 3  | 5  | continue |
| 3    | 8.5     | 8.0     | 0  | 2  | 3  | converged |
```

> 状态列取值 = convergence_check.py 输出的 action 对应状态：
> `continue`（继续循环）/ `escalate`（停滞待用户决策）/ `stop`（达最大轮数终止）/ `converged`（已收敛）。
