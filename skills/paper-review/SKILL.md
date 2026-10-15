---
name: paper-review
version: 1.1.0
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
/paper-review <文件路径> [--section X.Y] [--source <源文件|源目录>] [--format tex|docx|pdf] [--focus de-ai|discussion|peer] [--quick] [--rounds N] [--roles R1,R2..] [--no-fix]
```

| 参数 | 说明 | 默认 |
|------|------|------|
| `<文件路径>` | 待审查论文 Markdown 文件（必填） | — |
| `--section X.Y` | 仅审查指定小节（如 1.1，自动覆盖其子小节） | 全文 |
| `--source PATH` | 源文件或源目录（.tex 目录 / .docx / pdf提取.txt），启用源位置三轨定位 | 不启用 |
| `--format FMT` | 源格式 `tex`/`docx`/`pdf`（缺省按扩展名推断，目录→tex） | 自动推断 |
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
├── anchor_requests.json   ← 阶段4：源定位请求（--source 时；每条发现的引文+坐标）
├── anchor_map.json        ← Step 0 init / 阶段4 fill：三轨定位表（anchor_map.py 维护）
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
- 若提供 `--source`（三轨定位，见 references/anchor-locator.md）：
  执行：`Bash("python {SKILL_DIR}/scripts/anchor_map.py --review-dir {review_dir} init --draft {file_path} --source <源路径> [--format tex|docx|pdf]")`
  - **验证**：`success == true`，生成空 `{review_dir}/anchor_map.json`；
    失败（源不存在/格式无法推断）→ AskUserQuestion 请用户修正或放弃三轨定位（降级双轨，报告注明）
- `--focus` 路由：`de-ai`→阶段1后跳 Step 6；`discussion`→从阶段2开始；`peer`→从阶段3开始；
  缺省全流程。被跳过阶段的缺失来源文件由 merge_findings.py 自动忽略
- 若被审文件是 pandoc/PDF 提取的转换产物：执行 `Read("{SKILL_DIR}/references/format-notes.md")`，
  按其清单**先核对转换质量**（摘要在位/公式与表格未破损/页标记存在）再进入阶段1；
  破损处记入报告，不计入 P0/P1/P2

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

> **args 传递纪律**：args 必须按 **JSON 对象**传递（不得字符串化）；即便如此，
> harness 仍可能将其字符串化送达脚本（实测踩坑两次），**脚本侧必须做 typeof 防御解析**。
> API 要点：`parallel()` 接受 **thunk 数组**（`() => Promise`，传 Promise 会并发失控）；
> `agent()` 签名为 `agent(promptString, opts?)`，合法 opts 键为
> `label/phase/schema/model/effort/isolation/agentType`——**对象式入参与 `tools` 键均无效**。

```javascript
// ── 阶段2 Workflow 脚本：多智能体研讨（3阶段协议见 discussion-protocol.md）──
// args: file_path, section_range, review_dir, roles, skill_dir
// 防御解析：args 可能被 harness 字符串化（实测踩坑），必须 typeof 检查
const A = (typeof args === "string") ? JSON.parse(args) : (args || {});
const ROLES = A.roles || ["A1-方法论批评家", "A2-领域专家", "A3-写作编辑", "A4-魔鬼代言人", "A5-审稿人视角"];
const SCOPE = A.section_range
  ? `（仅审查第 ${A.section_range[0]}–${A.section_range[1]} 行，用 Read 的 offset/limit 读取）`
  : "（全文）";
const COMMON = [
  `角色定义与检查清单见 ${A.skill_dir}/references/agent-roles.md，`,
  `研讨协议与输出格式见 ${A.skill_dir}/references/discussion-protocol.md，`,
  `审查清单见 ${A.skill_dir}/references/review-checklist.md。`,
  `审查对象：${A.file_path}${SCOPE}。这是学报综述论文，`,
  `注意「文献[N] XXX」逐篇引用平行句式是学报标准风格，不属于AI写作问题。`,
  `只读审查：不得修改被审论文，产物一律 Write 到指定路径。`,
].join("\n");

// 阶段1：独立审查 —— 各角色并行，互相隔离（禁止交叉沟通）
// parallel() 必须传 thunk 数组；agent() 第一参数是 prompt 字符串
const reports = await parallel(ROLES.map(role => () =>
  agent([
    `你是「${role}」。${COMMON}`,
    `按研讨协议「阶段1：独立审查」输出格式，产出500-800字结构化评审报告：`,
    `每条发现标注严重度 [P0]/[P1]/[P2] + 位置（§X.Y 第N段/行号）+ 问题 + 建议，`,
    `末尾附四维评分（方法论/写作/创新性/总体，各N/10）。`,
    `用 Write 写入 ${A.review_dir}/agent_reports/${role}.md。不得读取其他角色的报告。`,
  ].join("\n"), { label: role, phase: "独立审查" })
));

// 阶段2：聚焦讨论 —— 主持人提取争议点，组织相关角色最多2-3轮回应
await agent([
  `你是研讨主持人。读取 ${A.review_dir}/agent_reports/ 下全部评审报告（共${ROLES.length}份）。${COMMON}`,
  `按研讨协议「阶段2：聚焦讨论」：提取争议点（角色间结论冲突、严重度分歧大者），`,
  `按 P0 优先排序；每个争议点组织相关角色各200字回应（必须引用具体段落、提出可操作修改），`,
  `最多2-3轮；总结共识与分歧，用 Write 写入 ${A.review_dir}/debate_summary.md。`,
].join("\n"), { label: "主持人-讨论", phase: "聚焦讨论" });

// 阶段3：共识决议 —— 产出研讨纪要（merge_findings.py 的解析来源）
await agent([
  `你是研讨主持人。汇总 ${A.review_dir}/agent_reports/ 与 debate_summary.md。${COMMON}`,
  `严格按研讨协议「纪要模板」产出：共识发现（### P0 — 必须修改 / ### P1 — 重要修改 /`,
  `### P2 — 建议修改 三个小节，表格列名固定为 | # | 位置 | 问题 | 建议 | 支持角色 |）、`,
  `分歧记录、评分汇总。用 Write 写入 ${A.review_dir}/discussion_minutes.md。`,
  `不得更改小节标题与表格列名（下游脚本按此解析，且对叙述性小节启用白名单跳过）。`,
].join("\n"), { label: "主持人-纪要", phase: "共识决议" });
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
- **手工语义归并（必做）**：脚本按「位置+类型」机械去重，跨来源去重能力弱
  （`duplicates_removed` 常为 0）。Read merged_findings.md 后按下述规则人工归并：
  1. 同一问题被多来源命中 → 合并为一项，**严重度取最高**，来源字段并列保留
  2. 归并时**保留裁决轨迹**：研讨中经辩论改判/降级的，在条目后注明「（研讨裁决：…）」
  3. **撤回项不得复活**：研讨纪要或用户已明确否决/撤回的意见，即使再次出现在
     其他来源，也不得重新列入待修改清单（注明「已撤回」后跳过）
- 若存在 anchor_map.json（Step 0 已 init），填充三轨定位：
  - a. 从 merged_findings.md 逐条提取**原句引文**（在 {file_path} 中 ≥15字且唯一的片段），
    用 **Write**（勿用 heredoc）写 `{review_dir}/anchor_requests.json`：
    `[{"id": "f1", "quote": "…", "draft_line": N, "structural": "§X.Y 表N/式(N)"}, …]`
    （structural 为结构坐标：章/节/表/公式编号，跨格式最稳，反查失败时的兜底）
  - b. 执行：`Bash("python {SKILL_DIR}/scripts/anchor_map.py --review-dir {review_dir} fill --requests {review_dir}/anchor_requests.json")`
  - c. **验证**：`success == true`；`ambiguous`/`not_found` 不是错误——按
    references/anchor-locator.md 回退结构坐标，Step 6 报告中如实标注即可

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

6.2 Read `{review_dir}/convergence.md`（评分轨迹）与 merged_findings.md 中标记跳过的条目；
若存在 `{review_dir}/anchor_map.json`，一并 Read（供问题表「源位置」列取值）。

6.3 向用户输出最终报告（Markdown，用 **Write** 写入 `{review_dir}/final_report.md` 后再呈现）：

- **审查对象**：文件、范围（全文/§X.Y）、模式（正式/快速、--no-fix 与否）；
  经过 pandoc/PDF 转换的稿件须注明转换链路与抽查结果（references/format-notes.md），
  并声明「数值核验以编译 PDF 为准」（适用时）
- **定位坐标说明**（启用三轨定位时，报告头部注明）：
  工作坐标=draft 行号（编辑后漂移）；源坐标=tex 文件:行 / docx 段落序 / pdf 页码
  （源文件被编辑后同样漂移）；结构坐标=章节/表/公式编号+原句引文（**不随编辑漂移，
  为兜底锚点**）。反查失败/歧义项源位置显示 `—（回退结构坐标）`
- **阶段1 去AI**：4技能发现数/修改数（deai_log.md 表格）
- **阶段2 研讨**：参与角色、共识发现 P0/P1/P2 数、未解决分歧
- **阶段3 同行评审**：Editorial Decision、映射评分
- **阶段4/5 修改**：total 及 by_source、by_severity 分布；跳过项清单。
  问题表在「位置」列基础上增加**「源位置」列**（三轨并列），如：
  `| # | 严重度 | 工作坐标 | 源位置 | 结构坐标 | 问题 | 处理 |`
  （源位置取自 anchor_map.json 的 source_loc；ambiguous/not_found 项回退结构坐标）
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
| anchor-locator.md | 源位置三轨定位说明、反查机制与诚实边界 | Step 0/阶段4/Step 6 |
| format-notes.md | pandoc/PDF 转换与提取注意事项（实测踩坑固化） | Step 0/Step 6 |

## 脚本清单（scripts/，均支持 --help，输出 JSON，UTF-8）

| 脚本 | 用途 | 调用时机 |
|------|------|---------|
| setup_env.py | 校验文件、定位章节行号、建 .review/ | Step 0 |
| anchor_map.py | 三轨定位表 init/fill（md行↔源定位↔结构坐标） | Step 0 init / 阶段4 fill |
| deai_audit.py | 去AI日志：start/log/verify | 阶段1 |
| merge_findings.py | 三来源发现合并、去重、P0/P1/P2 分级（纪要启用小节白名单防噪声） | 阶段4 |
| track_revisions.py | 修改日志：逐条 log / summary 统计 | 阶段4/5 |
| convergence_check.py | 收敛/停滞判定，维护 convergence.md | 阶段5 |

## 失败回退

- 脚本失败（退出码≠0）：读 stderr 与 JSON 中 problems，修正参数/文件后重试，**最多3次**；
  仍失败则暂停并向用户报告，请求介入
- Skill 调用失败：向用户报告；经用户同意可降级（如 ars-reviewer 不可用时，按
  review-checklist.md 维度2/4 自行评审），**降级必须在最终报告中注明**
- Workflow 不可用或失败：自动降级为快速模式（--quick 流程），并告知用户
- 三轨定位反查失败/歧义：按 references/anchor-locator.md 回退结构坐标（不算错误，报告如实标注）；
  `--source` 未提供或 init 失败：全程双轨（工作坐标+结构坐标），报告注明

### 写入与路径纪律（强制，实测踩坑固化）

1. **长 prose 一律用 Write 工具**（报告、结构化发现清单、anchor_requests.json 等
   含引号/撇号文本），**禁止 Bash heredoc**——撇号/引号与 heredoc 定界符冲突
   会导致 `unexpected EOF`（实测：`Cohen's dz` 触发）
2. **脚本调用与 Edit/Read 一律绝对路径**：Bash 的 cwd 跨调用持久化但不可依赖，
   相对路径 Edit 实测报 File does not exist
3. **跨工具传文件禁用 `/tmp`**：Git Bash 的 `/tmp` 与 Windows 路径体系不同，
   Read 工具无法读取；中间文件一律放 `{review_dir}` 或项目工作目录内
