---
name: paper-review
version: 1.0.0
description: |
  论文审查技能：对论文或章节进行去AI化审查、多智能体研讨、同行评审，
  组织修改并循环验证至质量收敛。支持正式模式（Workflow多代理）和
  快速模式（单实例角色扮演）。
  触发条件：用户说"审查论文"、"review paper"、"论文研讨"、
  "同行评审"、"去AI审查"、"paper review"、"论文审查"等。
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
  - Skill
  - Workflow
  - AskUserQuestion
---

# paper-review — 论文审查技能

五阶段流水线：**去AI审查 → 多智能体研讨 → 同行评审 → 修改执行 → 收敛循环**。

## 用法

```
/paper-review <文件路径> [--section X.Y] [--focus de-ai|discussion|peer] [--quick] [--rounds N] [--roles R1,R2..] [--no-fix]
```

| 参数 | 说明 | 默认 |
|------|------|------|
| `<文件路径>` | 待审查论文 Markdown 文件（必填） | — |
| `--section X.Y` | 仅审查指定小节（如 1.1，自动覆盖其子小节） | 全文 |
| `--focus` | 只执行指定阶段：`de-ai` / `discussion` / `peer`，之后直达 Step 6 | 全流程 |
| `--quick` | 快速模式：单实例角色扮演代替 Workflow 多代理 | 正式模式 |
| `--rounds N` | 收敛循环最大轮数 | 3 |
| `--roles R1,R2..` | 自定义研讨角色（名称见 references/agent-roles.md，至少2个） | A1–A5 |
| `--no-fix` | 只审查报告，不修改稿件（跳过阶段4/5的修改动作） | 执行修改 |

**路径占位符约定**：`{SKILL_DIR}` = 本 SKILL.md 所在目录（安装后通常为
`~/.claude/skills/paper-review`）；`{file_path}` `{review_dir}` `{section_range}`
`{rounds_max}` 等取自 Step 0 的 JSON 输出。**步骤间数据一律通过 `.review/` 下的文件传递，
不依赖对话记忆**（每阶段开始时重新读取所需文件）。

## 纪律规则（强制，任何阶段不得违反）

1. **所有 Skill 调用必须通过 Skill tool 实际执行**，不可口头描述（禁止"已调用/假设已完成"）
2. **ars-reviewer 为 READ-ONLY**：阶段3（及阶段5复查）只保存评审报告，绝不修改稿件
3. **P0/P1 修改必须经用户确认**（AskUserQuestion 逐项），P2 可打包确认；用户未同意不得 Edit
4. **收敛循环有最大轮数限制**（`--rounds`，默认3），达到即终止并输出未解决问题清单
5. **每阶段完成后向用户报告结果**（发现数/修改数/评分/产物路径），再进入下一阶段

## 数据流（.review/ 目录）

```
.review/
├── deai_log.md            ← 阶段1：4技能去AI审查日志（deai_audit.py 维护）
├── agent_reports/         ← 阶段2：各角色独立评审报告（每角色一个 .md）
├── discussion_minutes.md  ← 阶段2：研讨纪要（merge_findings.py 的来源之一）
├── peer_reports.md        ← 阶段3：ars-reviewer 评审报告（+结构化发现）
├── merged_findings.md     ← 阶段4：合并发现清单 P0/P1/P2
├── revision_log.md        ← 阶段4/5：修改日志（track_revisions.py 维护）
└── convergence.md         ← 阶段5：收敛记录（convergence_check.py 维护）
```

---

## 执行流程

### Step 0 — 环境初始化

执行：`Bash("python {SKILL_DIR}/scripts/setup_env.py --file <文件路径> [--section X.Y] [--rounds N]")`

- 解析 stdout JSON，记住 `file_path` / `section_range` / `review_dir` / `rounds_max`
- **验证**：`success == true`；否则向用户报告 `problems` 并终止
- 若指定 `--section`：后续所有阶段只读取/修改 `section_range` 行范围内的内容
  （Read 用 offset/limit，Edit 前确认目标行在范围内）
- `--focus` 路由：`de-ai`→阶段1后跳 Step 6；`discussion`→从阶段2开始；`peer`→从阶段3开始；
  缺省全流程。被跳过阶段的缺失来源文件由 merge_findings.py 自动忽略

### 阶段1 — 去AI审查（4技能串行，全部实际调用）

1.0 初始化日志：
执行：`Bash("python {SKILL_DIR}/scripts/deai_audit.py --phase start --review-dir {review_dir}")`

1.1 对下列 4 个技能**依次**执行（顺序固定，`{SKILL_NAME}` ∈
`stop-slop` → `academic-humanizer` → `humanize-writing` → `humanizer-zh`）：

- a. 执行：`Skill(skill="{SKILL_NAME}", args="审查并修改 {file_path}（范围：{section_range} 行 / 全文）。这是学术论文（学报风格），注意：「文献[N] XXX」逐篇引用平行句式是学报标准风格，不要当作AI模式处理")`
  - 等待技能**实际执行完毕**，从其结果中统计：发现数 N（识别出的AI模式处数）、修改数 M（实际编辑处数）
- b. 执行：`Bash("python {SKILL_DIR}/scripts/deai_audit.py --log {SKILL_NAME} --findings-count N --edits-count M --review-dir {review_dir}")`
- c. 若该技能报告了**未修复的残留问题**，以列表条目追加到 `{review_dir}/deai_log.md` 末尾
  （格式：`- [P1] 位置：§X.Y 第N段`／`问题：…`／`建议：…`，供阶段4合并）

1.2 完整性验证：
执行：`Bash("python {SKILL_DIR}/scripts/deai_audit.py --verify --review-dir {review_dir}")`

- **验证**：`all_logged == true`；否则对 `missing` 中的技能回补 1.1（最多重试3次，仍缺则报告用户）

1.3 向用户报告：4技能各自发现数/修改数、残留问题数。

### 阶段2 — 多智能体研讨

准备：执行 `Read("{SKILL_DIR}/references/agent-roles.md")` 与
`Read("{SKILL_DIR}/references/discussion-protocol.md")`；角色默认 A1–A5，`--roles` 指定时以其为准（至少2个）。

#### 正式模式（默认）— Workflow 多代理

执行：`Workflow(script="<下方工作流脚本全文>", args={"file_path": "{file_path}", "section_range": {section_range}, "review_dir": "{review_dir}", "roles": ["A1-方法论批评家", "A2-领域专家", "A3-写作编辑", "A4-魔鬼代言人", "A5-审稿人视角"], "skill_dir": "{SKILL_DIR}"})`

```javascript
// ── 阶段2 Workflow 脚本：多智能体研讨（3阶段协议见 discussion-protocol.md）──
// args: file_path, section_range, review_dir, roles, skill_dir
const ROLES = args.roles;
const SCOPE = args.section_range
  ? `（仅审查第 ${args.section_range[0]}–${args.section_range[1]} 行，用 Read 的 offset/limit 读取）`
  : "（全文）";
const COMMON = [
  `角色定义与检查清单见 ${args.skill_dir}/references/agent-roles.md，`,
  `研讨协议与输出格式见 ${args.skill_dir}/references/discussion-protocol.md，`,
  `审查清单见 ${args.skill_dir}/references/review-checklist.md。`,
  `审查对象：${args.file_path}${SCOPE}。这是学报综述论文，`,
  `注意「文献[N] XXX」逐篇引用平行句式是学报标准风格，不属于AI写作问题。`,
].join("\n");

// 阶段1：独立审查 —— 5个角色并行，互相隔离（禁止交叉沟通）
const reports = await parallel(ROLES.map(role => agent({
  name: role,
  prompt: [
    `你是「${role}」。${COMMON}`,
    `按研讨协议「阶段1：独立审查」输出格式，产出500-800字结构化评审报告：`,
    `每条发现标注严重度 [P0]/[P1]/[P2] + 位置（§X.Y 第N段/行号）+ 问题 + 建议，`,
    `末尾附四维评分（方法论/写作/创新性/总体，各N/10）。`,
    `写入 ${args.review_dir}/agent_reports/${role}.md。不得读取其他角色的报告。`,
  ].join("\n"),
  tools: ["Read", "Grep", "Glob", "Write"],
})));

// 阶段2：聚焦讨论 —— 主持人提取争议点，组织相关角色最多2-3轮回应
await agent({
  name: "主持人-讨论",
  prompt: [
    `读取 ${args.review_dir}/agent_reports/ 下全部评审报告（共${ROLES.length}份）。${COMMON}`,
    `按研讨协议「阶段2：聚焦讨论」：提取争议点（角色间结论冲突、严重度分歧大者），`,
    `按 P0 优先排序；每个争议点组织相关角色各200字回应（必须引用具体段落、提出可操作修改），`,
    `最多2-3轮；总结共识与分歧，写入 ${args.review_dir}/debate_summary.md。`,
  ].join("\n"),
  tools: ["Read", "Grep", "Glob", "Write", "Agent"],
});

// 阶段3：共识决议 —— 产出研讨纪要（merge_findings.py 的解析来源）
await agent({
  name: "主持人-纪要",
  prompt: [
    `汇总 ${args.review_dir}/agent_reports/ 与 debate_summary.md。${COMMON}`,
    `严格按研讨协议「纪要模板」产出：共识发现（### P0 — 必须修改 / ### P1 — 重要修改 /`,
    `### P2 — 建议修改 三个小节，表格列名固定为 | # | 位置 | 问题 | 建议 | 支持角色 |）、`,
    `分歧记录、评分汇总。写入 ${args.review_dir}/discussion_minutes.md。`,
    `不得更改小节标题与表格列名（下游脚本按此解析）。`,
  ].join("\n"),
  tools: ["Read", "Write"],
});
```

**验证**：`{review_dir}/discussion_minutes.md` 存在，且含 P0/P1/P2 三个小节与评分汇总；
缺失则重跑「主持人-纪要」步骤（最多3次），仍失败降级为快速模式并告知用户。

#### 快速模式（--quick）— 单实例角色扮演

不启动 Workflow，由当前实例按协议顺序完成：

1. Read agent-roles.md、discussion-protocol.md、review-checklist.md
2. 依次以 A1→A5（或 --roles 列表）视角独立审查（Read 论文后逐角色撰写，每份500–800字），
   分别 Write 到 `{review_dir}/agent_reports/{角色}.md`
3. 自任主持人做聚焦讨论：仅对 P0/P1 争议做 1 轮正反方模拟回应，Write `{review_dir}/debate_summary.md`
4. 按纪要模板 Write `{review_dir}/discussion_minutes.md`（小节标题与表格列名不得更改）

阶段2完成后向用户报告：参与角色数、P0/P1/P2 共识发现数、主要分歧点。

### 阶段3 — 同行评审（READ-ONLY，不修改稿件）

3.1 执行：`Skill(skill="academic-research-skills:ars-reviewer", args="full 评审 {file_path}（目标期刊：论文所属学报；如指定 --section {section_range}，重点关注该章节，但决策基于全文）")`

3.2 将 ars-reviewer 完整报告 Write 到 `{review_dir}/peer_reports.md`（追加模式：阶段5复审报告依次追加，各加 `# 第N轮复审` 标题）

3.3 若报告中无逐条 P0/P1/P2 标注，则在 `peer_reports.md` 末尾追加「## 结构化发现」小节，
将每条评审意见转写为条目式（供 merge_findings.py 解析）：

```
- [P0] 位置：§X.Y 第N段
  问题：…
  建议：…
```

3.4 提取 Editorial Decision → 同行评审评分（Accept=9，Minor Revision=8，Major Revision=6，
Reject=4；介于两档取中值±1按意见条数微调，见 convergence-criteria.md）

3.5 向用户报告：Decision、映射评分、主要意见摘要。**本阶段未对稿件做任何修改。**

### 阶段4 — 修改执行（--no-fix 时跳过，直达 Step 6）

4.1 合并发现：
执行：`Bash("python {SKILL_DIR}/scripts/merge_findings.py --review-dir {review_dir} --output {review_dir}/merged_findings.md")`

- 解析 stdout JSON（p0/p1/p2/total），Read merged_findings.md 获取逐项内容
- **验证**：输出文件存在；total=0 时报告用户"无待修改项"，跳到阶段5

4.2 逐项确认与修改（顺序：P0 → P1 → P2）：

- a. 确认（纪律规则3）：
  - P0/P1 逐项执行：`AskUserQuestion(questions=[{"question": "【P0|来源|位置】问题描述 —— 是否按建议修改？", "header": "修改确认", "options": [{"label": "按建议修改"}, {"label": "调整后修改（我给出意见）"}, {"label": "跳过此项"}]}])`
  - P2 可打包：列出全部 P2 项，选项为「全部修改 / 逐项选择 / 全部跳过」
- b. 用户同意 → 执行：`Edit(file_path, old_string=原句片段, new_string=修改后片段)`
  - 指定 `--section` 时，先确认目标位置在 section_range 内，越界项报用户裁决
  - **验证**：Edit 成功；失败（old_string 不唯一/不存在）时 Read 上下文修正后重试，最多3次
- c. 每完成一处修改，执行：`Bash("python {SKILL_DIR}/scripts/track_revisions.py --log \"原句|修改后|理由(含[P0]/[P1]/[P2]标记)|来源阶段\" --review-dir {review_dir}")`
  - 来源阶段 ∈：`阶段1-去AI` / `阶段2-研讨` / `阶段3-同行评审` / `阶段5-收敛循环`
  - 各段内不得含竖线 `|`（脚本会报错）
- d. 跳过项：在 merged_findings.md 对应行末追加「（用户决定：跳过）」

4.3 向用户报告：修改 N 项（P0 x / P1 y / P2 z）、跳过 M 项。

### 阶段5 — 收敛循环（--no-fix 时跳过）

`round = 1`，循环执行：

5.1 去AI复查（轻量，只统计不修改）：
执行：`Skill(skill="stop-slop", args="快速扫描 {file_path}（范围 {section_range}），仅统计残留：Tier1/Tier2词汇残留数、结构问题数，输出计数，不做任何修改")`

- 去AI评分 = `max(1, min(10, 10 − 残留词数 × 0.5 − 结构问题数 × 0.5))`（见 convergence-criteria.md）

5.2 同行评审复查（READ-ONLY）：
执行：`Skill(skill="academic-research-skills:ars-reviewer", args="复审 {file_path}（第{round}轮，对照上轮意见检查改进情况）")`

- 报告追加到 `{review_dir}/peer_reports.md`（`# 第{round}轮复审` 标题下），同 3.3 追加结构化发现
- Decision → 同行评审评分（映射同阶段3）

5.3 统计本轮 P0/P1/P2 数（来自 5.1 残留 + 5.2 结构化发现）

5.4 执行：`Bash("python {SKILL_DIR}/scripts/convergence_check.py --round {round} --deai-score {x} --peer-score {y} --p0-count {a} --p1-count {b} --p2-count {c} --rounds-max {rounds_max} --review-dir {review_dir}")`

5.5 解析 JSON 的 `action`：

- `"stop"` → 退出循环（converged=true 为已收敛；否则为达最大轮数），进入 Step 6
- `"escalate"`（停滞）→ 执行：`AskUserQuestion(questions=[{"question": "连续2轮评分无改善（去AI {x}/10，评审 {y}/10），如何处理？", "header": "停滞决策", "options": [{"label": "继续下一轮"}, {"label": "停止并定稿（输出未解决清单）"}, {"label": "调整策略（我给出方向）"}]}])`
  → 继续：`round += 1` 回 5.1；停止：进入 Step 6；调整策略：按用户方向执行一轮修改（记入
  revision_log，来源=阶段5-收敛循环）后 `round += 1` 回 5.1
- `"continue"` → 对本轮新增 P0/P1（及用户愿意处理的 P2）执行一轮修改（流程同 4.2，
  track_revisions 来源=`阶段5-收敛循环`）→ `round += 1` → 回 5.1

### Step 6 — 最终报告

6.1 执行：`Bash("python {SKILL_DIR}/scripts/track_revisions.py --summary --review-dir {review_dir}")`

6.2 Read `{review_dir}/convergence.md`（评分轨迹）与 merged_findings.md 中标记跳过的条目。

6.3 向用户输出最终报告（Markdown）：

- **审查对象**：文件、范围（全文/§X.Y）、模式（正式/快速、--no-fix 与否）
- **阶段1 去AI**：4技能发现数/修改数（deai_log.md 表格）
- **阶段2 研讨**：参与角色、共识发现 P0/P1/P2 数、未解决分歧
- **阶段3 同行评审**：Editorial Decision、映射评分
- **阶段4/5 修改**：total 及 by_source、by_severity 分布；跳过项清单
- **收敛状态**：轮数、convergence.md 评分轨迹表、是否收敛；未收敛时列出未解决问题清单
- **产物路径**：.review/ 下全部文件

---

## 参考文件（references/，可替换模板）

| 文件 | 用途 | 使用阶段 |
|------|------|---------|
| agent-roles.md | 5核心+10扩展研讨角色定义与检查清单 | 阶段2 |
| discussion-protocol.md | 3阶段研讨协议与纪要模板 | 阶段2 |
| review-checklist.md | 4维度审查清单（去AI/学术规范/写作质量/结构完整性） | 阶段1/2/5 |
| convergence-criteria.md | 收敛条件、停滞处理、评分来源与映射 | 阶段5 |

## 脚本清单（scripts/，均支持 --help，输出 JSON，UTF-8）

| 脚本 | 用途 | 调用时机 |
|------|------|---------|
| setup_env.py | 校验文件、定位章节行号、建 .review/ | Step 0 |
| deai_audit.py | 去AI日志：start/log/verify | 阶段1 |
| merge_findings.py | 三来源发现合并、去重、P0/P1/P2 分级 | 阶段4 |
| track_revisions.py | 修改日志：逐条 log / summary 统计 | 阶段4/5 |
| convergence_check.py | 收敛/停滞判定，维护 convergence.md | 阶段5 |

## 失败回退

- 脚本失败（退出码≠0）：读 stderr 与 JSON 中 problems，修正参数/文件后重试，**最多3次**；
  仍失败则暂停并向用户报告，请求介入
- Skill 调用失败：向用户报告；经用户同意可降级（如 ars-reviewer 不可用时，按
  review-checklist.md 维度2/4 自行评审），**降级必须在最终报告中注明**
- Workflow 不可用或失败：自动降级为快速模式（--quick 流程），并告知用户
