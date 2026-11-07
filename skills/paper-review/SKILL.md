---
name: paper-review
version: 2.0.0
description: |
  论文审查技能 v2.0：合并同行评审面板（七席含数值审计专席）→ 去AI审查
  （多智能体研讨）→ 合并报告 → 修改执行 → 收敛循环。支持稿件类型准则绑定
  （--doctype）、同目录多版本与核验式复审（--re-review）、专家意见对账
  （--expert-comments）、源位置三轨定位（--source）、RESUME 跨终端续跑。
  触发条件：用户说"审查论文"、"review paper"、"论文研讨"、
  "同行评审"、"去AI审查"、"paper review"、"论文审查"、"复审"等。
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

# paper-review — 论文审查技能（v2.0）

流水线：**Step 0 初始化 → 阶段1 合并面板（七席）→ 阶段2 去AI研讨 →
阶段3 合并报告 → 阶段4 修改执行 → 阶段5 收敛循环 → Step 6 最终报告**。

v2.0 架构（对比 v1.x）：原「多智能体研讨+同行评审」两阶段合并为七席单面板
（S7 数值审计专席新设）；去AI审查后置且改为多智能体研讨（audit-only，主上下文
零技能目录加载）；新增 doctype 准则绑定、同目录多版本/复审协议、RESUME 续跑、
转换审计前置、数值检查库、引文 lint、专家意见对账、成本预估。
阶段4/5 修改纪律与 v1.x 完全一致。

## 用法

```
/paper-review <文件路径> [--section X.Y] [--source <源文件|源目录>] [--format tex|docx|pdf]
              [--doctype TYPE] [--focus panel|de-ai] [--quick] [--rounds N] [--no-fix]
              [--re-review] [--response FILE] [--panel default|full] [--new-run]
              [--expert-comments FILE]
```

| 参数 | 说明 | 默认 |
|------|------|------|
| `<文件路径>` | 待审查论文 Markdown（draft.md=v1；draft-vN.md=vN） | — |
| `--section X.Y` | 仅审查指定小节（自动覆盖子小节） | 全文 |
| `--source PATH` | 源文件/目录（tex 目录 / .docx / pdf提取.txt），启用三轨定位 | 不启用 |
| `--format FMT` | 源格式 `tex`/`docx`/`pdf` | 自动推断 |
| `--doctype TYPE` | 稿件类型：full-paper/thesis/proposal/problem-collection/extended-abstract/technical-report/section-draft/review/other:<描述>（见 references/doctype-criteria.md） | 未声明则必须 AskUserQuestion 确认，**禁止臆测** |
| `--focus` | 只执行指定阶段：`panel`（阶段1）/ `de-ai`（阶段2），之后直达 Step 6 | 全流程 |
| `--quick` | 快速模式：**S1+S6 两席**单实例扮演，跳过讨论轮，不派 S7/去AI代理 | 正式模式 |
| `--rounds N` | 收敛循环最大轮数 | 3 |
| `--no-fix` | 只审查报告，不修改稿件（跳过阶段4/5） | 执行修改 |
| `--re-review` | 核验式复审（见 references/re-review-protocol.md） | 否 |
| `--response FILE` | 修订版随附作者回复信（复审 R&R 追溯用） | 无 |
| `--panel` | 复审面板范围：default=裁剪席位 / full=七席全开 | default |
| `--new-run` | 对同一版本强制开启新轮次 r<N+1>（全量重审） | 复用当前轮次 |
| `--expert-comments FILE` | 外部专家意见（md/提取文本），阶段1后启动对账 | 无 |

**路径占位符约定**：`{SKILL_DIR}` = 本 SKILL.md 所在目录；`{file_path}` `{review_dir}`
`{run_dir}` `{section_range}` `{rounds_max}` 等取自 Step 0 的 JSON 输出
（`review_dir`=`.review/`，跨轮共享 config/chain/RESUME；`run_dir`=`.review/r<N>/`，
本轮全部产物）。**步骤间数据一律通过文件传递，不依赖对话记忆**。

## 纪律规则（强制，任何阶段不得违反）

1. **所有 Skill 调用必须通过 Skill tool 实际执行**，不可口头描述
2. **只读铁律**：阶段1/2/3 全部代理只读被审稿件，绝不修改；修改只发生在阶段4/5
   且经用户确认
3. **P0/P1 修改必须经用户确认**（AskUserQuestion 逐项），P2 可打包；未同意不得 Edit
4. **收敛循环有最大轮数限制**（`--rounds`，默认3），达到即终止并输出未解决问题清单
5. **每阶段完成后向用户报告结果**（发现数/决议/评分/产物路径），再进入下一阶段
6. **RESUME.md 强制**：每阶段边界更新 `{review_dir}/RESUME.md`（resume.py），
   跨终端/跨会话续跑以此为恢复依据
7. **垄断规则**：结构要素核查仅 S1；数值复算仅 S7；引文格式仅 bib_lint.py——
   其余席位遇此类问题转交对应垄断方，不得重复上报
8. **撤回项不得复活**：config.json withdrawals 中的指控在任何后续轮次/来源
   不得重新列入（merge_findings.py 自动跳过，手工归并同样执行）
9. **子代理 API 错误 ≠ 阶段失败**：单个代理遇 API 错误（如 400 Arrearage/超时）
   只重试该代理（≤3次），**不得重跑整阶段**（全部阶段产物已落盘）
10. **doctype 禁止臆测**：未声明且无法继承时必须 AskUserQuestion 确认后才继续

## 数据流（.review/ 目录，v2.0）

```
<论文目录>/
├── draft.md / draft-vN.md       ← 工作稿（v1 无后缀在根目录）
├── response-vN.md               ← 作者回复信（可选输入）
├── sources/vN/                  ← v2+ 作者回包原样存放（复审出现时创建）
└── .review/
    ├── config.json              ← 跨轮状态唯一权威源（doctype/版本映射/轮次/
    │                               豁免清单/撤回记录/用户裁决）
    ├── chain.md                 ← 版本谱系（模板 templates/chain.md，每轮更新）
    ├── RESUME.md                ← 续跑快照（resume.py --run-dir {review_dir}）
    └── r<N>/                    ← 第 N 次审阅运行的全部产物
        ├── seat_config.md       ← 1a 席位配置卡
        ├── seat_reports/S1….md  ← 1b 七席独立报告
        ├── debate_summary.md    ← 1c 讨论与撤回记录
        ├── decision_letter.md   ← 1d Decision Letter
        ├── revision_roadmap.md  ← 1d 权威清单一（内容，R-#）
        ├── deai_audits/*.md     ← 2a 四技能审计清单
        ├── deai_cross.md        ← 2b 交叉质询矩阵
        ├── deai_confirmed.md    ← 2c 权威清单二（语言，D-#）
        ├── deai_exempt.md       ← 2c 豁免清单（误报拦截留痕）
        ├── expert_items.json / expert_reconcile.md ← 专家对账（如有）
        ├── merged_findings.md   ← 阶段3 合并（含 S-# 交叉引用）
        ├── anchor_requests.json / anchor_map.json  ← 三轨定位（--source 时）
        ├── conversion_audit.md / bib_lint.md       ← Step 0 前置审计
        ├── diff_scope.md / rr_matrix.md            ← 复审专用
        ├── revision_log.md / convergence.md        ← 阶段4/5
        └── final_report.md                         ← Step 6
```

v1.x 旧产物（扁平 agent_reports/、peer_reports.md 等）只读兼容，不迁移；
存量「另建目录」形态用 scripts/migrate_rounds.py 迁移。

---

## 执行流程

### Step 0 — 环境初始化 + 前置审计

0.1 执行：`Bash("python {SKILL_DIR}/scripts/setup_env.py --file <文件路径> [--section X.Y] [--rounds N] [--doctype TYPE] [--re-review] [--response FILE] [--expert-comments FILE] [--quick] [--panel P] [--new-run]")`

- 解析 stdout JSON：`file_path/section_range/review_dir/run_dir/rounds_max/version/round/doctype/applied_criteria/estimate` 及三个确认标志
- **验证**：`success == true`；否则报告 `problems` 并终止
- **doctype 确认（needs_doctype_confirmation=true 时，纪律10）**：
  执行：`AskUserQuestion(questions=[{"question": "未声明稿件类型。检测线索：{doctype_hints}。请确认本稿类型（决定结构检查准则，见 references/doctype-criteria.md）", "header": "稿件类型", "options": [{"label": "full-paper 完整论文"}, {"label": "thesis 学位论文"}, {"label": "proposal/problem-collection 申报/征集"}, {"label": "其它（extended-abstract/technical-report/section-draft/review/other:描述）"}]}])`
  → 用户选定后**重跑 0.1 带 --doctype**（同轮更新，不递增轮次）
- **覆盖护栏（needs_source_confirmation=true 时，§九规则2）**：
  执行：`AskUserQuestion(questions=[{"question": "根目录检测到未登记源文件 {untracked_sources}，且已有历史审阅轮次。这是新修订版吗？", "header": "版本确认", "options": [{"label": "是修订版：移入 sources/vN/ 并按 vN 审"}, {"label": "不是：忽略该文件继续"}, {"label": "替换 v1 源（我确认覆盖）"}]}])`
  → 修订版：手工移动文件（Bash mv）后带 `--new-run` 重跑 0.1
- **成本预估报告（§十⑪）**：向用户呈现 `estimate`（席位/代理数/预计墙钟/token 量级/
  建议）；若 recommendation 建议 --quick 而用户未指定，
  执行：`AskUserQuestion(questions=[{"question": "预估：{estimate摘要}。建议 {recommendation}，是否调整模式？", "header": "模式确认", "options": [{"label": "按建议执行"}, {"label": "维持正式模式（七席）"}, {"label": "改用 --quick（S1+S6）"}]}])`

0.2 RESUME 初始化：
执行：`Bash("python {SKILL_DIR}/scripts/resume.py --run-dir {review_dir} init --paper {file_path} --version {version} --round {round} --doctype {doctype}")`（已存在则跳过；此后**每阶段边界**执行 `resume.py --run-dir {review_dir} set --stage <阶段> --status <状态>` 与 `next --action …` 更新）

0.3 格式转换核对（被审文件是 pandoc/PDF 提取产物时）：
执行：`Read("{SKILL_DIR}/references/format-notes.md")`，按清单核对转换质量；
破损处记入报告，不计入 P0/P1/P2。**密码保护 PDF 回退链**（Read 拒读时）：
PyMuPDF 抽文本 → find_tables 抽表 → 渲染页为 PNG 后 Read 图像。

0.4 转换审计前置（§十⑥，有 --source 或明确转换产物时必做）：
执行：`Bash("python {SKILL_DIR}/scripts/conversion_audit.py --source <源路径> --draft {file_path} --output {run_dir}conversion_audit.md")`
- **验证**：success==true；`missing` 中丢失清单将注入 1a 配置卡共同豁免与各席 prompt

0.5 三轨定位（有 --source 时，见 references/anchor-locator.md）：
执行：`Bash("python {SKILL_DIR}/scripts/anchor_map.py --review-dir {run_dir} init --draft {file_path} --source <源路径> [--format FMT]")`
- 失败 → AskUserQuestion 修正或降级双轨（报告注明）

0.6 引文 lint（§十⑧，稿件含参考文献节或 .bib 时）：
执行：`Bash("python {SKILL_DIR}/scripts/bib_lint.py --input <参考文献节提取文件|.bib> --run-dir {run_dir}")`
- 产物 bib_lint.md 供 S3 复核（S3 不再手工查格式）

0.7 复审预处理（--re-review 时，见 references/re-review-protocol.md）：
执行：`Read("{SKILL_DIR}/references/re-review-protocol.md")`；
执行：`Bash("python {SKILL_DIR}/scripts/diff_scope.py --old <v(N-1)稿路径> --new {file_path} --output {run_dir}diff_scope.md")`
- 继承项（doctype/豁免/撤回/裁决）由 config.json 自动生效；席位按协议裁剪
  （--panel full 恢复七席）

0.8 `--focus` 路由：`panel`→仅阶段1后跳 Step 6；`de-ai`→仅阶段2后跳 Step 6；
缺省全流程。向用户报告 Step 0 结果（版本/轮次/doctype/预估/前置审计摘要）。

### 阶段1 — 合并同行评审面板（七席）

1a 领域分析与席位配置（沿用 ars-reviewer field_analyst 模式）：
执行：`Read("{SKILL_DIR}/references/panel-roles.md")` 与
`Read("{SKILL_DIR}/references/discussion-protocol.md")`；
由当前实例（或单代理）分析稿件领域/类型/规模，用 **Write** 产出 `{run_dir}seat_config.md`
（席位配置卡）：学科定位、doctype 准则（applied_criteria 原文）、**共同豁免清单**
（学位文体/期刊模板/转换伪影=conversion_audit 丢失清单/平行引用句式）、
复审时的 diff 分域（diff_scope.md 摘要）、bib_lint error 条目数。

#### 正式模式（默认）— Workflow 多代理

执行：`Workflow(script="<下方阶段1工作流脚本全文>", args={"file_path": "{file_path}", "section_range": {section_range}, "run_dir": "{run_dir}", "skill_dir": "{SKILL_DIR}", "seats": ["S1-EIC统筹", "S2-方法论", "S3-领域", "S4-写作编辑", "S5-跨学科视角", "S6-魔鬼代言人", "S7-数值审计"], "quick": false})`

> **args 传递纪律**：args 必须按 JSON 对象传递（不得字符串化）；即便如此 harness
> 仍可能字符串化送达（实测踩坑两次），**脚本侧必须 typeof 防御解析**。
> API 要点：`parallel()` 接受 **thunk 数组**（`() => Promise`）；`agent()` 签名为
> `agent(promptString, opts?)`，合法 opts 键 `label/phase/schema/model/effort/isolation/agentType`
> ——**对象式入参与 `tools` 键均无效**。

```javascript
// ── 阶段1 Workflow：合并同行评审面板（1b 独立审查 → 1c 讨论撤回 → 1d 编辑综合）──
const A = (typeof args === "string") ? JSON.parse(args) : (args || {});
const SEATS = A.seats || ["S1-EIC统筹", "S2-方法论", "S3-领域", "S4-写作编辑", "S5-跨学科视角", "S6-魔鬼代言人", "S7-数值审计"];
const SCOPE = A.section_range
  ? `（仅审查第 ${A.section_range[0]}–${A.section_range[1]} 行，Read 用 offset/limit）`
  : "（全文）";
const COMMON = [
  `先读席位配置卡 ${A.run_dir}seat_config.md（doctype 准则/共同豁免清单/转换审计丢失清单/分域），配置卡内豁免项不得上报。`,
  `席位章程见 ${A.skill_dir}/references/panel-roles.md，操作清单见 ${A.skill_dir}/references/review-checklist.md，`,
  `研讨协议（IRON RULE/撤回规则/输出格式）见 ${A.skill_dir}/references/discussion-protocol.md。`,
  `审查对象：${A.file_path}${SCOPE}。`,
  `只读审查：不得修改被审稿件；产物一律 Write 到指定路径（禁止 heredoc）。`,
  `每条发现：[P0]/[P1]/[P2] + 位置（§X.Y 第N段/行号）+ 问题 + 原句引文（≥15字）+ 建议；末尾四维评分。`,
].join("\n");

// 1b 七席独立审查 —— 并行、互盲（parallel 必须传 thunk 数组）
await parallel(SEATS.map(seat => () =>
  agent([
    `你是「${seat}」席。${COMMON}`,
    seat.startsWith("S7")
      ? `数值审计专用：先构造 checks.json 跑数值检查库 python ${A.skill_dir}/scripts/numeric_checks --input <checks.json路径> --output <复算表路径>（四检查器用法见脚本 --help），再手工扩展论文特有不变量；tex/docx 源用 PyMuPDF 对照 PDF 原表。每条数值发现必须附复算表。`
      : seat.startsWith("S3")
        ? `引文格式已脚本化：读 ${A.run_dir}bib_lint.md 复核 error 条目即可，你的重点是引用语义核对（描述与原文是否相符，可联网核实）。涉及外部事实的指控必须先完成文献级核验。`
        : seat.startsWith("S1")
          ? `结构要素核查由你垄断：按配置卡 doctype 准则出具「类型适配判定」（必备缺失按表定级；豁免缺失只在类型适配说明注明）。发现声明类型与内容实质不符时，只提单条「类型适配异议」。`
          : `发现结构缺失引用 S1 判定、数值疑点转交 S7（在报告中标注「转交S7」），不得自行重复上报或复算。`,
    `Write 报告到 ${A.run_dir}seat_reports/${seat}.md。不得读取其他席位的报告。`,
  ].join("\n"), { label: seat, phase: "独立审查" })
));

// 1c 聚焦讨论与撤回轮（假阳性防火墙）
await agent([
  `你是面板主持人。读取 ${A.run_dir}seat_reports/ 下全部席位报告。${COMMON}`,
  `按研讨协议 1c：提取争议点（结论冲突/严重度分歧/CRITICAL/类型适配异议），P0 优先；`,
  `相关席位各200字回应，最多2-3轮。数值类争议强制以 S7 复算表为裁定依据，你不自行裁数。`,
  `涉及外部事实的指控裁决前必须文献级核验；核验不成立即撤回，撤回记录写入纪要`,
  `（并注明需回填 config.json withdrawals）。Write ${A.run_dir}debate_summary.md。`,
].join("\n"), { label: "主持人-讨论撤回", phase: "讨论与撤回" });

// 1d 编辑综合（Decision Letter + Revision Roadmap）
await agent([
  `你是面板主持人（编辑综合）。汇总 ${A.run_dir}seat_reports/ 与 debate_summary.md。${COMMON}`,
  `按研讨协议 1d 产出两件：`,
  `1. ${A.run_dir}decision_letter.md：Editorial Decision（Accept/Minor/Major/Reject+口径）`,
  `   + 映射评分（9/8/6/4）+ 七席四维均值与主持人综合 + S6 每条 CRITICAL 逐条专节回应（铁律）`,
  `   + 分歧仲裁记录（未决分歧注明交用户裁决）。`,
  `2. ${A.run_dir}revision_roadmap.md：严格按列名`,
  `   | ID | 位置 | 问题 | 建议 | 来源席 | 工作量 | 验收标准 |，`,
  `   ID 前缀 R- 全局连续；分 ## P0 — 必须修改 / ## P1 — 重要修改 / ## P2 — 建议修改 三节；`,
  `   头部 ## 决议 行含 Decision；共识矩阵≥3席直接入，<3席经讨论裁定；`,
  `   数值类条目验收标准=对应 numeric_checks 检查器 pass；撤回项不得写入。`,
  `两份文件列名/小节标题不得更改（merge_findings.py 按此解析）。`,
].join("\n"), { label: "主持人-编辑综合", phase: "编辑综合" });
```

**验证**：`{run_dir}revision_roadmap.md` 与 `decision_letter.md` 存在，roadmap 含
P0/P1/P2 三节与 R-# ID；缺失则重跑「主持人-编辑综合」代理（≤3次，纪律9），
仍失败降级 --quick 流程并告知用户。
撤回项回填：读 debate_summary.md 撤回记录，用 **Edit** 更新
`{review_dir}config.json` 的 `withdrawals`（id/reason/round）。

#### 快速模式（--quick）— S1+S6 单实例扮演

不启动 Workflow：Read panel-roles.md/review-checklist.md 后，依次以 S1、S6 视角
独立审查并 Write `seat_reports/`；跳过 1c；按 1d 格式直接产出
decision_letter.md 与 revision_roadmap.md（数值疑问标注「未复算（quick 模式）」）。

#### 专家意见对账（--expert-comments 时，1d 之后）

执行：`Bash("python {SKILL_DIR}/scripts/expert_reconcile.py --run-dir {run_dir} init --comments <专家意见文件>")` →
阶段3 合并后执行 `match`，对每条「疑似遗漏」**读原文核实**后逐条
`verify --id E-N --result confirmed|rejected --evidence …`（confirmed 须 --severity）。
铁律：未核实的遗漏候选不得入报告（隔离区机制，脚本强制）。

阶段1 完成后：更新 RESUME（set --stage stage1-panel --status done）；
向用户报告：Decision、映射评分、P0/P1/P2 共识数、撤回数、CRITICAL 数。

### 阶段2 — 去AI审查（多智能体研讨，audit-only）

执行：`Read("{SKILL_DIR}/references/deai-discussion-protocol.md")`；然后
执行：`Workflow(script="<下方阶段2工作流脚本全文>", args={"file_path": "{file_path}", "section_range": {section_range}, "run_dir": "{run_dir}", "skill_dir": "{SKILL_DIR}", "skills": ["stop-slop", "academic-humanizer", "humanize-writing", "humanizer-zh"]})`

```javascript
// ── 阶段2 Workflow：去AI审查多智能体研讨（2a 并行审计 → 2b 交叉质询 → 2c 终裁）──
const A = (typeof args === "string") ? JSON.parse(args) : (args || {});
const SKILLS = A.skills || ["stop-slop", "academic-humanizer", "humanize-writing", "humanizer-zh"];
const SCOPE = A.section_range
  ? `（仅第 ${A.section_range[0]}–${A.section_range[1]} 行）`
  : "（全文）";
const COMMON = [
  `按 ${A.skill_dir}/references/deai-discussion-protocol.md 执行。`,
  `先读 ${A.run_dir}seat_config.md 的共同豁免清单与 doctype 准则——豁免项不得上报。`,
  `审查对象：${A.file_path}${SCOPE}。audit-only：不得修改稿件。`,
].join("\n");

// 2a 四技能代理并行独立审计（各自加载技能目录，主上下文零加载）
await parallel(SKILLS.map(sk => () =>
  agent([
    `你是「${sk}」审计代理。${COMMON}`,
    `Read 你的技能目录 ~/.claude/skills/${sk}/ 全部内容（SKILL.md 及模式目录/清单文件）作为审计标准；`,
    `目录不存在时按 ${A.skill_dir}/references/review-checklist.md 维度0 执行并在产物首行注明降级。`,
    `固定加审「英文摘要专检」四项（机译痕迹/中英术语一致/全半角标点/Tier1词汇）。`,
    `产出「模式→位置→证据（原句引文）→建议→初判严重度」表（语言级默认P2，声称级可P1；`,
    `与阶段1路线图 ${A.run_dir}revision_roadmap.md 同源的声称问题在备注标「疑似重叠 R-#」）。`,
    `Write 到 ${A.run_dir}deai_audits/${sk}.md。`,
  ].join("\n"), { label: sk + "-审计", phase: "独立审计" })
));

// 2b 交叉质询轮（1轮）+ 2c 主持人终裁
await agent([
  `你是去AI研讨主持人。读取 ${A.run_dir}deai_audits/ 全部清单与 revision_roadmap.md。${COMMON}`,
  `2b：四清单合并为「技能×发现」矩阵——模式堆叠合并（同短语多标记合并为一条，支持技能并列，`,
  `合并键=位置相同且引文重叠≥50%）；对每条候选自任其余三技能视角质询（豁免范畴/转换伪影/`,
  `内容问题误标），被质询方须引原文回应。Write 矩阵与质询记录到 ${A.run_dir}deai_cross.md。`,
  `2c 终裁，Write 两份清单：`,
  `1. ${A.run_dir}deai_confirmed.md，严格按列名`,
  `   | ID | 位置 | 问题 | 建议 | 支持技能 | 严重度 | 重叠标记 |，ID 前缀 D- 连续；`,
  `   与阶段1 P0/P1 同源的声称问题在「重叠标记」列填对应 R-#（合并时以阶段1为准，不重复计入）；`,
  `   表后一行「质量评分: N/50」（50−语言级×2−声称级×5−结构级×3，下限0，构成注明）。`,
  `2. ${A.run_dir}deai_exempt.md：被排除候选+排除理由+裁定依据（误报拦截留痕，复审继承）。`,
  `列名不得更改（merge_findings.py 按此解析）。`,
].join("\n"), { label: "主持人-终裁", phase: "交叉质询与终裁" });
```

**验证**：`deai_confirmed.md` 与 `deai_exempt.md` 存在且 confirmed 含 D-# ID 与
质量评分行；缺失则重跑终裁代理（≤3次），仍失败降级为主上下文单实例按协议执行并告知用户。
--quick 时：跳过阶段2（报告注明未做去AI审查）。
阶段2 完成后：更新 RESUME；向用户报告：确认清单条数（语言级/声称级/重叠）、
豁免拦截数、质量评分。**本阶段未修改稿件。**

### 阶段3 — 发现合并与最终清单

3.1 执行：`Bash("python {SKILL_DIR}/scripts/merge_findings.py --run-dir {run_dir} --output {run_dir}merged_findings.md")`

- 解析 stdout JSON（p0/p1/p2/total/cross_refs/withdrawn_skipped/decision/quality_score）
- **验证**：success==true；total=0 时报告用户"无待修改项"
- **手工语义归并（必做，脚本只做拼接与交叉引用）**：Read merged_findings.md 后：
  1. 同一问题被多来源命中 → 合并为一项，**严重度取最高**，来源并列保留
  2. 保留裁决轨迹：经 1c 辩论改判/降级的注明「（研讨裁决：…）」
  3. **撤回项不得复活**（纪律8；脚本已按 config 跳过，手工归并同样执行）
  4. 去AI与内容重叠项以阶段1为准（S-# 交叉引用只核对，不再拆分）

3.2 三轨定位填充（存在 anchor_map.json 时）：
- a. 从 merged_findings.md 逐条提取原句引文（≥15字且唯一），用 **Write** 写
  `{run_dir}anchor_requests.json`：`[{"id": "R-1", "quote": "…", "draft_line": N, "structural": "§X.Y 表N"}, …]`
- b. 执行：`Bash("python {SKILL_DIR}/scripts/anchor_map.py --review-dir {run_dir} fill --requests {run_dir}anchor_requests.json")`
- c. **验证**：success==true；ambiguous/not_found 不是错误——按 anchor-locator.md
  回退结构坐标，Step 6 报告如实标注

3.3 专家对账收尾（--expert-comments 时）：执行 expert_reconcile.py `match`，
逐条读原文核实后 `verify`；confirmed 项按严重度并入待修改清单（来源=专家）。

3.4 更新 RESUME；向用户报告：合并统计（内容/语言/交叉引用/撤回跳过）、
按严重度分布。

### 阶段4 — 修改执行（--no-fix 时跳过，直达 Step 6）

4.1 逐项确认与修改（顺序：P0 → P1 → P2）：

- a. 确认（纪律3）：
  - P0/P1 逐项执行：`AskUserQuestion(questions=[{"question": "【P0|来源席|位置】问题描述 —— 是否按建议修改？", "header": "修改确认", "options": [{"label": "按建议修改"}, {"label": "调整后修改（我给出意见）"}, {"label": "跳过此项"}]}])`
  - P2 可打包：列出全部 P2 项，选项「全部修改 / 逐项选择 / 全部跳过」
- b. 用户同意 → 执行：`Edit(file_path, old_string=原句片段, new_string=修改后片段)`
  - `--section` 时先确认目标在 section_range 内，越界项报用户裁决
  - **验证**：Edit 成功；失败（不唯一/不存在）Read 上下文修正后重试 ≤3次
- c. 每完成一处：`Bash("python {SKILL_DIR}/scripts/track_revisions.py --log \"原句|修改后|理由(含[P0]/[P1]/[P2]与R-#/D-#标记)|来源阶段\" --review-dir {run_dir}")`
  - 来源阶段 ∈：`阶段1-面板` / `阶段2-去AI` / `阶段3-专家对账` / `阶段5-收敛循环`；
    各段内不得含竖线 `|`
- d. 跳过项：merged_findings.md 对应行末追加「（用户决定：跳过）」；
  用户裁决结果记入 config.json `adjudications`

4.2 更新 RESUME；向用户报告：修改 N 项（P0/P1/P2 分布）、跳过 M 项。

### 阶段5 — 收敛循环（--no-fix 时跳过）

`round = 1`，循环执行：

5.1 去AI复查（轻量，只统计不修改）：
执行：`Skill(skill="stop-slop", args="快速扫描 {file_path}（范围 {section_range}），仅统计残留：Tier1/Tier2词汇残留数、结构问题数，输出计数，不做任何修改")`
- 去AI评分 = `max(1, min(10, 10 − 残留词数×0.5 − 结构问题数×0.5))`（convergence-criteria.md）

5.2 评审复查（READ-ONLY，单代理替代全面板）：
执行：`Skill(skill="academic-research-skills:ars-reviewer", args="复审 {file_path}（第{round}轮，对照 {run_dir}revision_roadmap.md 逐条检查改进情况）")`
- 报告 Write 到 `{run_dir}peer_recheck_r{round}.md`；Decision → 映射评分（同阶段1）

5.3 统计本轮 P0/P1/P2（5.1 残留 + 5.2 结构化发现）

5.4 执行：`Bash("python {SKILL_DIR}/scripts/convergence_check.py --round {round} --deai-score {x} --peer-score {y} --p0-count {a} --p1-count {b} --p2-count {c} --rounds-max {rounds_max} --review-dir {run_dir}")`

5.5 解析 `action`：
- `"stop"` → 退出循环，进入 Step 6
- `"escalate"` → `AskUserQuestion(questions=[{"question": "连续2轮评分无改善（去AI {x}/10，评审 {y}/10），如何处理？", "header": "停滞决策", "options": [{"label": "继续下一轮"}, {"label": "停止并定稿（输出未解决清单）"}, {"label": "调整策略（我给出方向）"}]}])`
- `"continue"` → 对本轮新增 P0/P1（及用户愿意处理的 P2）执行一轮修改（流程同 4.1，
  track_revisions 来源=`阶段5-收敛循环`）→ round += 1 → 回 5.1

### Step 6 — 最终报告与收尾

6.1 执行：`Bash("python {SKILL_DIR}/scripts/track_revisions.py --summary --review-dir {run_dir}")`

6.2 Read：`{run_dir}convergence.md`、merged_findings.md（跳过项）、anchor_map.json
（如有）、decision_letter.md、rr_matrix.md（复审时）、`{review_dir}chain.md`（如有）。

6.3 执行：`Read("{SKILL_DIR}/templates/final-report.md")`，按模板用 **Write** 产出
`{run_dir}final_report.md` 后向用户呈现。必含节：稿件类型与准则适配（含豁免缺席项
说明）/ 审查对象（含转换审计摘要行、密码 PDF 回退说明、docx 高亮观察——语义不明
高亮不计缺陷但提请作者清除）/ 定位坐标说明（三轨时）/ 阶段1 面板（Decision、
撤回记录、CRITICAL 专节）/ 数据完整性关切（触发时：「须解释的异常」定性+材料提交
程序）/ 专家意见对账表（如有）/ 阶段2 去AI（确认/豁免/质量评分）/ 合并发现与修改
（三轨问题表）/ R&R 追溯矩阵（复审时，不得橡皮图章）/ 收敛状态 / 产物路径。

6.4 chain.md 更新：按 `templates/chain.md` 在 `{review_dir}chain.md` 追加本轮一节
（决议/评分轨迹/发现状态流转/裁决项/Integrity 进展）。

6.5 RESUME 收尾：`resume.py --run-dir {review_dir} set --stage step6-report --status done`
+ `check` 通过。

---

## 参考文件（references/，可替换模板）

| 文件 | 用途 | 使用阶段 |
|------|------|---------|
| panel-roles.md | 七席章程（S1/S7 垄断规则、S6 CRITICAL、quick 映射） | 阶段1 |
| discussion-protocol.md | 1b/1c/1d 协议：撤回规则、数值争议交 S7、类型适配异议、专家对账铁律 | 阶段1 |
| deai-discussion-protocol.md | 2a–2c 流程、模式堆叠合并、豁免清单模板、英文摘要专检 | 阶段2 |
| doctype-criteria.md | 8 类型准则绑定表（必备/豁免/置换/合规；机器版在 setup_env.py） | Step 0/阶段1 |
| re-review-protocol.md | 核验式复审：diff 驱动、R&R 追溯矩阵、继承规则、存量迁移 | Step 0/阶段1/Step 6 |
| review-checklist.md | 七席操作级检查清单 + 共同豁免清单 + 维度0 去AI清单 | 阶段1/2/5 |
| convergence-criteria.md | 收敛条件、停滞处理、评分来源与映射 | 阶段5 |
| anchor-locator.md | 三轨定位说明、反查机制与诚实边界 | Step 0/阶段3/Step 6 |
| format-notes.md | pandoc/PDF 转换与提取注意事项（实测踩坑固化） | Step 0/Step 6 |

## 模板（templates/）

| 文件 | 用途 |
|------|------|
| final-report.md | 最终报告骨架（v2.0 全节：类型适配/完整性关切/对账表/三轨列） |
| chain.md | 版本谱系骨架（每轮追加） |

## 脚本清单（scripts/，均支持 --help，输出 JSON，UTF-8）

| 脚本 | 用途 | 调用时机 |
|------|------|---------|
| setup_env.py | 校验/章节定位/版本轮次路由/config.json/doctype 绑定/覆盖护栏/成本预估 | Step 0 |
| resume.py | RESUME.md 续跑快照 init/set/next/show/check | 各阶段边界 |
| conversion_audit.py | 源侧 vs draft 结构计数，转换丢失清单 | Step 0 |
| anchor_map.py | 三轨定位表 init/fill | Step 0 / 阶段3 |
| bib_lint.py | GB/T 7714 引文格式确定性检查 | Step 0 |
| diff_scope.py | v(N-1)→vN 变更区域定位 | Step 0（复审） |
| numeric_checks/ | S7 数值检查库（weighted_identity/table_sums/abstract_numbers/percent_basis） | 阶段1（S7） |
| expert_reconcile.py | 专家意见对账 init/match/verify/show（隔离区强制核实） | 阶段1后/阶段3 |
| merge_findings.py | v2 双权威清单合并（R-#/D-#/S-#，撤回不复活）；--review-dir 走 v1 兼容模式 | 阶段3 |
| track_revisions.py | 修改日志逐条 log / summary | 阶段4/5 |
| convergence_check.py | 收敛/停滞判定 | 阶段5 |
| migrate_rounds.py | 存量「另建目录」形态迁移（dry-run/--confirm） | 按需 |
| deai_audit.py | （v1 遗留）串行去AI日志；v2.0 流程不再使用，仅旧产物兼容 | — |

## 失败回退

- 脚本失败（退出码≠0）：读 stderr 与 problems，修正后重试 **≤3次**；仍失败暂停请用户介入
- **子代理 API 错误 ≠ 阶段失败**（纪律9）：重试该代理 ≤3次，不得重跑整阶段；
  恢复后凭 RESUME.md + 已落盘产物续跑
- Skill 调用失败：报告用户；经同意可降级（ars-reviewer 不可用→按 review-checklist.md
  自行评审），**降级必须在最终报告注明**
- Workflow 不可用或失败：阶段1 降级 --quick 单实例流程、阶段2 降级主上下文按协议
  单实例执行，并告知用户
- 三轨定位反查失败/歧义：回退结构坐标（不算错误）；--source 缺失/init 失败：全程双轨
- 密码保护 PDF：PyMuPDF 抽文本 → find_tables 抽表 → 渲染页 PNG 后 Read 图像
- 跨终端续跑：新会话读 `{review_dir}RESUME.md`（resume.py show）定位暂停点，
  从 next.action 继续，已完成阶段不重跑

### 写入与路径纪律（强制，实测踩坑固化）

1. **长 prose 一律用 Write 工具**（报告/清单/JSON 等含引号撇号文本），
   **禁止 Bash heredoc**——撇号/引号与定界符冲突导致 `unexpected EOF`（实测 `Cohen's dz`）
2. **脚本调用与 Edit/Read 一律绝对路径**：相对路径 Edit 实测报 File does not exist
3. **跨工具传文件禁用 `/tmp`**：Git Bash 的 /tmp 与 Windows 路径体系不同，
   Read 工具无法读取；中间文件一律放 `{run_dir}` 内
