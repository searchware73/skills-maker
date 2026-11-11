# CHANGELOG

## 2026-11-11 — paper-review v2.1.0（进行中 · G1–G2 已交付）

> v2.1 按 `docs/handoff-20261108-paper-review-v2.md` §十一 分 G1–G4 四组实施，
> 本节随各组追加；SKILL.md frontmatter 版本号在 Step 5 发版时升为 2.1.0。

### G1 目录扁平化 + CLI/文档对齐 + 一致性守卫（条目 19/12/13/21/23/24）

- **目录扁平化（条目 12，用户可见）**：改为「每篇论文一目录」的 v2.1 扁平结构——
  工程根 `INDEX.md`（一行一篇）；`<paper-name>/` 内：v1 源（根单文件 **或** `v1/` 目录，
  二选一，并存报错）、`vN/`（v2+ 源包，开审后不可变）、`draft/`（draft.md/draft-vN.md/figures/）、
  `response/`（response-vN.md、expert-*.md）、`reports/`（rN-审阅报告.md/rN-复审报告.md 交付副本，
  **复制而非软链接**）、`.review/`（config.json/chain.md/RESUME.md/rN/ 过程产物）。
  `config.json` 增 `"layout": "flat-v2.1"`；v1.x 与 v2.0 存量产物保持只读兼容。
- **setup_env.py 重写（条目 12/13，用户可见）**：`paper_dir` 从 `draft/` 反推（不再 `dirname(file_path)`）；
  v1 二选一检测；`source_root` ∈ `"." | "v1" | "vN"`（旧 `sources/vN` 只读兼容）；
  `unregistered_sources()` 忽略 v1/ vN/ draft/ response/ reports/ figures/ media/，并按 r1 开审时间截断；
  根 `INDEX.md` 不存在时创建；新增 `--source/--format/--focus/--no-fix` 并透传 conversion_audit/anchor_map；
  非 md 输入给 Step 0.0 分派指引后 exit 1；`.docx` 专家意见做 zip 魔数校验（exit 2）。
- **新增 scripts/migrate_layout.py（条目 12，用户可见）**：存量 `papers/`+`output/` 工作空间 →
  v2.1 扁平结构迁移；`--root` + `--dry-run`（默认）/`--apply`/`--rollback` + `--report`；
  幂等（二次 apply 零改动）、可回滚（manifest + backups/ 字节级复原，`papers.bak/`/`output.bak/`
  只移动不删除）；5 类人工判定项（非标准报告名/LaTeX 工程/media/figures/output 非报告）**只列 report 不猜**。
- **migrate_rounds.py 同步（条目 12/19）**：「另建目录」轮次形态就地规范化为扁平口径
  （`sources/vK`→`vK`、根 draft/response 归位、config 补 `layout` 戳），保持可用。
- **专家意见 docx 原生支持（条目 21，门禁 G2 用户裁决，用户可见）**：`expert_reconcile.py --comments`
  接受 `.docx`，zipfile+ElementTree 原生解析 word/document.xml（零第三方依赖，与 conversion_audit.py
  同一模式）；Word 自动列表段落（w:numPr）转 `- ` 条目行，多行续接规则不变；损坏/伪 docx exit 1 明确报错。
  §10.4 / SKILL 用法表 / 脚本实现三处口径统一为 `<md|docx>`。
- **Step 0.0 输入类型分派（条目 23，用户可见）**：`.docx/.tex/目录` → pandoc 转 `draft/draft.md`
  （docx 图落 media/ 后归位 figures/ 并改写引用）；`.pdf` → PyMuPDF 提取（逐页 `%% [PDF p.N]` 标记，
  anchor_map pdf 源坐标依据）；实际转换命令与参数写入 conversion_audit.md「## 转换链路」节；
  图片产物统一收敛 `draft/figures/`。
- **文档同步（条目 19）**：SKILL.md（用法表/数据流目录树/Step 0.0/0.1 输出键/护栏 vN/ 选项/
  Step 6.4 交付副本+INDEX 行/脚本清单）、re-review-protocol.md（v2.1 口径 + §9 双迁移脚本入口）、
  templates/chain.md、templates/final-report.md、format-notes.md（第 4 条悬空引用改写 + 第 6 条转换留痕）；
  备忘条目 5/7/8/21 加 v2.1 注记（保留历史原文）。
- **新增守卫测试（条目 24）**：`test_docs_cli_consistency.py`（SKILL 用法块/用法表/调用行 flag ×
  各脚本 argparse AST 双向对账 + 全脚本 `--help` 实测，10 例）；`test_referenced_files_exist.py`
  （文档引用的 scripts/templates/references 路径存在性 + 孤儿文件反向收录守卫，5 例）。
- **新增迁移夹具**：`tests/test_paper_review/fixtures/layout_legacy/`（按备忘「存量实测清单」构造
  5 类最小样例，50 文件）+ `test_migrate_layout.py`（dry-run 不改盘/apply 结构/幂等/回滚字节级复原/
  判定项进 report/合成冲突场景，24 例）。
- 测试：`tests/test_paper_review/` 15 文件 212 用例全绿；G1 验证命令通过
  （夹具 dry-run：5 类待确认项、26 moves、5 rewrites、零文件改动）。

### G2 条目不静默丢失与计数自洽（条目 15/14/20/16/17）

- **merge_findings.py 完整性（条目 15，用户可见）**：`_v2_table_rows()` 表格中间的手工空行/
  散文行不再截断解析，收集同节全部表格（重复表头行自动跳过）；合并后校验「roadmap 声明的
  R-ID 集合 ⊆ 合并清单∪撤回记录」，缺失即 exit 1 列出 ID 且**不写半成品输出**
  （回归实测缺陷：空行曾致 R-40~R-45 静默丢失而 sources_missing 仍为空）。
- **去AI双口径计分（条目 16，用户可见）**：deai_confirmed.md 表后固定三行
  `确认总数 confirmed_total: N（…）` / `计分总数 scored_total: M（重叠 k 项不重复计入）` /
  `质量评分: N/50`；质量分只按 scored_total 口径计（与阶段1 重叠项不得二次扣分）；
  merge_findings.py 复核双口径并输出 `deai_confirmed_total`/`deai_scored_total`/
  `quality_score_basis`，声明与表格不符 stderr 告警 + `quality_basis_warnings`（不中断）；
  deai-discussion-protocol.md 2c 模板与 SKILL 2c 提示词同步。
- **anchor_map.py 二进制 PDF 与 fill 完整性（条目 14，用户可见）**：按 `%PDF-` 魔数判定
  二进制 PDF → PyMuPDF 提取（lazy import fitz/pymupdf）→ 回退 draft `%% [PDF p.N]` 页标记 →
  均失败**显式报错**，绝不再 gbk 解码乱码假装成功；`source_extract`（method/pages）留痕于
  anchor_map.json 与 fill 输出。fill 一律以 id 为键（自动 id 防碰撞），重复请求 id exit 1；
  同段重复 quote 多条保留标 `ambiguous`+`dup_quote`；无引文请求保留为 `structural_only`
  条目；fill 后强制校验 `requests 数 == entries 数`，条目静默丢失即 exit 1。
- **新增 scripts/build_anchor_requests.py（条目 20，用户可见）**：从 merged_findings.md
  自动构建 anchor_requests.json，取代 3.2a 手写 Write——引文抽取（「」/『』/“”/"" 最长片段）、
  位置四形态解析（`L\d+`/`行N`→draft_line；`§X.Y`/`表N`/`式N`→structural）；引文 <15 字或
  含省略号（示意性片段）标 `weak`、draft 多处命中标 `ambiguous`、未命中标 `not_in_draft`、
  无行号标 `structural_only`，全部进 `needs_manual_quote` 待人工补引文清单（**不静默丢弃**）；
  draft 唯一命中自动回填 draft_line；S-# 交叉引用行不重复生成、跨表 id 去重；与条目 14 的
  fill 校验串成闭环。
- **新增 scripts/validate_report.py（条目 17，用户可见；备忘二选一取校验器方案）**：
  final_report.md 交付前机器校验——合并统计 8 数/决议（报告↔merged↔roadmap 三方）/质量评分
  ↔ merged_findings.md；反查统计 ↔ anchor_map.json entries 计数；seat_reports/ 份数与非空
  （`--seats`）；交付副本字节一致 + INDEX.md 行；chain.md 本轮节。收集全部 problems 后
  exit 1，**不得带着不一致交付**（回归实测缺陷：7→9 P0、39→47 项中间态靠人工发现）。
  SKILL Step 6 增 6.6 校验步（RESUME 收尾顺延 6.7），补派席位后先重跑 1d+merge_findings
  再校验；templates/final-report.md §2 增「反查统计」行；anchor-locator.md 调用时机表同步。
- 测试：新增 test_build_anchor_requests.py（14）、test_validate_report.py（21），
  test_anchor_map.py 扩至 21、test_merge_findings_v2.py 扩至 15；
  `tests/test_paper_review/` 17 文件 264 用例全绿。

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
