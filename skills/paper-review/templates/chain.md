# chain.md — 版本谱系模板（v2.0 §9.5）

> 用法：首轮 Step 6 创建 `{review_dir}/chain.md`（注意：在 .review/ 根，不在 r<N>/ 内，
> 跨轮共享）；此后**每轮结束追加一节**。最终报告头部引用本文件摘要。
> migrate_rounds.py 会为迁移的存量稿件生成骨架（占位「待回填」）。

---

# 版本谱系 — {name}

- doctype：{problem-collection}（{r1 声明 / r2 仲裁改判}）
- 源根映射：v1="."（根单文件）或 "v1"（多文件工程），v2="v2"

## r1（v1，{YYYY-MM-DD}）

- 版本文件：draft/draft.md（hash: {前8位}）
- 决议：{Major Revision}（映射评分 {6}）
- 评分：方法论 {N}/10 | 写作 {N}/10 | 创新性 {N}/10 | 总体 {N}/10
- 发现：P0 {a} / P1 {b} / P2 {c}；撤回 {w} 条
- 用户裁决项：{R-5 维持 P1（用户）/ …}
- Integrity 程序：{无 / 已触发：异常清单见 r1/final_report.md §3.1}
- 专家对账（{YYYY-MM-DD}，交付后追加）：条目 {n} → 吻合 {m} / 新增 {c}（来源=专家）/ 冲突 {x} / 排除 {r}；合并后 P0 {a} / P1 {b} / P2 {c}；原决议不变
  ← 可选行：仅交付后追加对账时存在，由 expert_reconcile.py report 自动追加（v2.1 条目22，同轮追加、不改原决议）

## r2（v2，{YYYY-MM-DD}，核验式复审）

- 版本文件：draft/draft-v2.md（hash: {前8位}）；response：response/response-v2.md
- 评分轨迹（vs r1）：总体 {6.2 → 7.5}（{+1.3}）
- 决议：{Minor Revision}（映射评分 {8}）
- **发现状态流转表**：

| 上轮ID | r1 严重度 | r2 状态 | 说明 |
|--------|-----------|---------|------|
| R-1 | P0 | resolved | S7 复算 pass |
| R-3 | P1 | residual | §2.1 仍有 2 处混用 |
| R-9 | P0 | withdrawn | r1 文献核验不成立，不复活 |
| （新）D-4 | — | new | diff 范围扫查新发现 |

- 用户裁决项：{…}
- Integrity 程序进展：{已解释关闭 / 待材料}

## rN（…）

{同构追加}
