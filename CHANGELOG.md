# CHANGELOG

## 2026-11-09 — paper-review v2.0.1（阶段5 评审复查调用修正）

- **修复**：阶段5.2 的
  `Skill(skill="academic-research-skills:ars-reviewer")` 改为
  `Skill(skill="academic-research-skills:academic-paper-reviewer", args="re-review 模式：…")`。
  `ars-reviewer` 是 ARS 插件的斜杠命令（`commands/ars-reviewer.md`，且
  `disable-model-invocation: true`），不是技能，原调用必然失败并静默降级；
  改为直接调用技能并显式指定 `re-review` 模式（Revision verification checklist），
  与「对照 revision_roadmap 逐条核验改进情况」的语义一致。
- 同步更新：失败回退措辞（`SKILL.md`）、`references/convergence-criteria.md`、
  `README.md`、`docs/SYNC-GUIDE.md`（ARS 插件依赖名）。
- 新增静态回归测试 `tests/test_paper_review/test_skill_invocation.py`，
  锁定阶段5 必须调用 `academic-paper-reviewer` 技能且不得把命令名当技能调用。
- 依赖版本核对：stop-slop `8da1f03`、humanize-writing 2.0.0、
  academic-humanizer 0.3.3、ARS 插件 3.24.2 均为上游最新；
  humanizer-zh 本地落后上游 1 个提交（`f4518a8`，中文改写保义性修复），
  由用户在 `~/.claude/skills/humanizer-zh` 执行 `git pull` 更新，不随本仓库发布。

## 2026-11-08 — paper-review v2.0.0（架构级重构）

按 `docs/handoff-20261108-paper-review-v2.md` 规格实施
（证据基础：li/xue/he/zhang/q10/仿真稿件 5+ 篇真实审阅复盘；
用户确认决策①–⑪）。lit-research 不变（v1.0.1）。

### 架构重构（决策①②③）

- **阶段2+阶段3 合并为单面板**：七席（S1 EIC/S2 方法论/S3 领域/S4 写作编辑/
  S5 跨学科/S6 魔鬼代言人/**S7 数值审计新专席**），职责边界互不重叠；
  保留原阶段2 辩论-撤回机制与原阶段3 编辑决议信/验收标准两侧独占产出
  （`references/panel-roles.md` 取代 agent-roles.md）
- **去AI审查后置**（内容审查决定稿件生死，优先执行）且改为**多智能体研讨模式**：
  2a 四技能代理并行 audit-only → 2b 交叉质询（模式堆叠合并）→ 2c 主持人终裁
  （确认清单 D-# + 豁免清单留痕 + 与阶段1 重叠打标）；主上下文零技能目录加载
  （`references/deai-discussion-protocol.md`）
- 垄断规则：结构核查仅 S1、数值复算仅 S7、引文格式仅 bib_lint.py——消除重复上报源

### 新决策④–⑪

- **④ doctype 准则绑定**：`--doctype` 8 类型（full-paper/thesis/proposal/
  problem-collection/extended-abstract/technical-report/section-draft/review/other:），
  必备/豁免/置换/合规四组规则（`references/doctype-criteria.md` + setup_env.py
  机器版）；未声明必须 AskUserQuestion，禁止臆测；类型适配异议单条仲裁；
  q10「零参考文献误报 P0」案根治
- **⑤ 同目录多版本与复审协议**：v1 源留根、v2+ 入 `sources/v<N>/`、产物按
  `.review/r<N>/` 轮次路由；config.json 为跨轮唯一权威源（doctype/豁免/撤回/裁决
  继承）；核验式复审=diff 驱动分域 + R&R 追溯矩阵（不得橡皮图章）+ 席位裁剪；
  chain.md 版本谱系；`migrate_rounds.py` 存量迁移（`references/re-review-protocol.md`）
- **⑥ 转换审计前置**：`conversion_audit.py` 源侧 vs draft 结构计数（tex 环境/
  docx zipfile+ET/pdf 页标记），丢失清单注入配置卡（xue 案制度化）
- **⑦ 数值检查库**：`numeric_checks/`（weighted_identity/table_sums/
  abstract_numbers/percent_basis 四检查器 + S7 复算表输出；xue 表3.1、
  仿真稿 Ex、li 表3.4 三案为测试夹具）
- **⑧ 引文 lint 脚本化**：`bib_lint.py`（GB/T 7714 空会议名/双句点/逗号空格/
  页码格式/键名-年份/arXiv-正式发表（CrossRef 可选联网）/姓名倒置/双语配对）；
  S3 改为仅语义核对
- **⑨ 专家意见对账**：`--expert-comments` + `expert_reconcile.py`
  init/match/verify/show；隔离区机制强制「遗漏项读原文核实后才可入报告」
  （he-paper「多域客户端」误判回归用例）
- **⑩ 英文摘要专检**：2a 审计代理固定四项（机译痕迹/中英术语一致/全半角/Tier1）
- **⑪ Step 0 成本预估**：席位/代理数/墙钟/token 量级/--quick 建议，用户可当场改判

### 可靠性（§五）

- **RESUME.md 制度化**：`resume.py`（init/set/next/show/check），每阶段边界强制更新，
  跨终端续跑凭此恢复
- **代理级 API 故障重试**：子代理 API 错误 ≠ 阶段失败，重试该代理 ≤3 次，
  不得重跑整阶段（仿真稿 400 Arrearage 案）
- 密码保护 PDF 回退链（PyMuPDF 抽文本→抽表→渲染页图）；docx 高亮观察不计缺陷
  但提请清除（均入 SKILL.md 失败回退与报告模板）

### 脚本变更

- `setup_env.py` v2：版本/轮次解析与 r<N>/ 路由、config.json 维护（合并保留）、
  --doctype 绑定与检测线索、覆盖护栏、--re-review/--response/--expert-comments/
  --panel/--new-run、estimate 输出（v1 旧键全保留）
- `merge_findings.py` v2：`--run-dir` 双权威清单模式（revision_roadmap.md R-# +
  deai_confirmed.md D-#，重叠→S-# 交叉引用不重复计入，撤回记录自动跳过，
  Decision/质量评分提取）；`--review-dir` v1 三来源模式保留一个版本
- 新增：resume.py / diff_scope.py / conversion_audit.py / numeric_checks/（4检查器）/
  bib_lint.py / expert_reconcile.py / migrate_rounds.py；deai_audit.py 降为 v1 遗留
- 新增 `templates/`：final-report.md（类型适配/数据完整性关切/专家对账表/三轨列/
  CRITICAL 专节）、chain.md

### 测试（新增 8 个测试文件，全部通过）

test_setup_env_v2（15）/ test_merge_findings_v2（8）/ test_resume（20）/
test_diff_scope（13）/ test_conversion_audit（15）/ test_numeric_checks /
test_bib_lint / test_expert_reconcile（22）/ test_migrate_rounds（9）；
v1 回归（test_anchor_map 11、test_merge_findings 7、test_extract_pdf）保持全绿；
SKILL.md 两段 Workflow 脚本经 node --check 验证

### 版本

- paper-review 1.1.0 → **2.0.0**（--quick 映射 S1+S6 两席；--focus 取值改为
  panel/de-ai；--roles 参数由席位体系取代）

## 2026-10-15 — paper-review v1.1.0 / lit-research v1.0.1

按 `docs/handoff-20261013-paper-review-hardening.md` 规格实施加固
（来源：paper-reviewer 工作空间 4 篇论文全流程审阅实测）。

### A. 新功能：源位置三轨定位（paper-review）

- 新增 `scripts/anchor_map.py`：`init`（Step 0 生成空表）/ `fill`（阶段4 填充），
  维护 `{review_dir}/anchor_map.json`（md行 ↔ 源定位 ↔ 结构坐标）
  - tex=文件:行号（源可为目录，遍历 *.tex）；docx=段落序号（zipfile+XML 解析，无新依赖）；
    pdf=页码（按 `%% [PDF p.N]` / 旧式 `--- Page N ---` 标记切分）
  - 归一化反查（NFKC 全半角统一、大小写折叠、tex 去注释/命令/花括号）+ 压缩匹配兜底；
    多处命中 → `ambiguous:true`、0 命中 → `not_found`，均回退结构坐标
- SKILL.md：新增 `--source` / `--format` 参数；Step 0 init、阶段4 fill、
  Step 6 问题表增加「源位置」列（三轨并列）与坐标漂移说明
- 新增 `references/anchor-locator.md`：三轨定义、反查机制、诚实边界
  （同句多处/转换改标点/宏展开必失败，结构坐标+引文永远兜底）、
  synctex 与 word-revision Track Changes 可选增强
- lit-research `extract_pdf.py`：提取时逐页植入标准页标记 `%% [PDF p.N]`
  （保留 `--- Page N ---` 兼容旧格式），固化为标准动作

### B. 缺陷修复与纪律固化（paper-review）

- **B1（必修）**：重写 SKILL.md 内嵌阶段2 Workflow 脚本，对齐真实 Workflow API——
  `parallel()` 改传 thunk 数组；`agent()` 改为 `(promptString, {label, phase})` 签名，
  删除无效的对象式入参与 `tools` 键；增加 `typeof args === "string"` 防御解析
  （harness 可能字符串化 args，实测踩坑两次）
- **B2**：SKILL.md 新增「写入与路径纪律」节——长 prose 用 Write 禁 heredoc
  （撇号冲突致 unexpected EOF）、脚本/Edit/Read 一律绝对路径、跨工具传文件禁用 /tmp
- **B3**：新增 `references/format-notes.md`——pandoc 转 LaTeX 摘要被吸收/table*·tikz 丢失
  （数值核验以编译 PDF 为准）、pandoc 转 DOCX 公式破损抽查、PDF 页标记标准动作；
  Step 0 增加转换质量核对入口，Step 6 报告注明转换链路
- **B4**：`merge_findings.py` 对 discussion_minutes.md 启用小节白名单——只解析
  「共识发现/结构化发现/P0/P1/P2」小节，叙述性小节（参与角色/分歧记录/评分汇总/决议信）
  中含严重度字样的散文与表格行不再误解析为发现（li-paper 6 条/xue 7 条噪声回归）；
  SKILL.md 阶段4 明示手工语义归并规则（同问题多源取最高严重度、保留裁决轨迹、撤回项不得复活）

### 测试

- 新增 `tests/test_paper_review/test_anchor_map.py`（11 用例：tex/docx/pdf 三格式、
  resolved/ambiguous/not_found、归一化容差、draft 行号反查、新旧页标记）
- 新增 `tests/test_paper_review/test_merge_findings.py`（7 用例：白名单防噪声回归、
  三来源解析、计数、缺失来源忽略）
- 新增 `tests/test_lit_research/test_extract_pdf.py`（页标记植入，需 PyMuPDF）
- 全部通过；阶段2 Workflow 脚本经 node --check 语法验证

### 版本

- paper-review 1.0.0 → **1.1.0**；lit-research 1.0.0 → **1.0.1**
