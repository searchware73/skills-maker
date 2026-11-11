---
name: v21-upgrade
description: |
  paper-review 技能 v2.1 升级实施流程（**仅限 skills-maker 工作空间**）。一句话触发即按
  docs/handoff-20261108-paper-review-v2.md §十一 的 24 条 backlog 与「实施顺序与依赖」分 4 组落地：
  改 skills/paper-review/**、补回归与守卫测试、更新 CHANGELOG、提交打标签、install.py 安装校验、
  产出移交说明（references/v21-migration-notes.md）。支持跨会话续跑，账本为 docs/v21-implementation-log.md。
  触发短语：/v21-upgrade、升级 paper-review 到 v2.1、实施 v2.1 backlog、继续 v2.1 升级、v2.1 回流修复。
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
  - AskUserQuestion
---

# v21-upgrade — paper-review v2.1 升级实施流程

工作目录固定为 `D:/WS/skills-maker`。**不是本仓库时立即停止**并告知用户切到 skills-maker 再运行。

## 铁律（任何步骤不得违反）

1. **仓库是唯一权威源**：只改 `skills/paper-review/**`、`tests/**`、`docs/**`、`CHANGELOG.md`；
   **绝不编辑 `~/.claude/skills/paper-review`**（安装副本，下次 install 覆盖，改动必丢）。
2. **一组一提交**：G1–G4 各自完成后「测试全绿 → 更新 CHANGELOG → git commit」，不得多组混提。
3. **测试全绿才可提交**：`tests/test_paper_review/` 全部用例；触碰 lit-research 或 shared 时
   加跑 `tests/test_lit_research/test_extract_pdf.py`。需要跳过/放宽任何用例 → 门禁 G5 问用户。
4. **规格以备忘为准，不凭记忆重写**：每条实施前回读 `docs/handoff-20261108-paper-review-v2.md`
   §十一 对应条目原文；发现备忘有误 → 同一提交内先改备忘再改代码，并在账本记「备忘修订」。
5. **向后兼容**：v1.x 扁平产物只读兼容不得破坏；`migrate_rounds.py` 保持可用。
6. **门禁之外不打断**：除 G1–G5 外一律按备忘已记录的决策直接执行，不向用户提问。
7. **每组完成即报告**（改动文件 / 测试结果 / 提交号），随后**自动进入下一组**，不等确认。
8. **脚本规范**（本仓库 CLAUDE.md）：`--help` 可用、stdout 输出 JSON、错误走 stderr + 非零退出码、
   UTF-8（Windows GBK 兼容 reconfigure）、SKILL 步骤用显式调用格式而非自然语言描述。

## Step 0 — 状态恢复与开工

0.1 执行：`Bash("cd /d/WS/skills-maker && git status --porcelain && echo --- && git log --oneline -5 && echo --- && git pull --ff-only origin main 2>&1 | tail -3")`
- pull 网络失败**不阻塞**：账本记「离线，push 待补」，继续。
- 工作区有未提交改动 → 报告并 AskUserQuestion（stash / 带着改继续 / 停止）。这是唯一允许的额外提问。

0.2 账本：`Read("docs/v21-implementation-log.md")`；不存在则按文末「账本模板」用 **Write** 创建。

0.3 规格：`Read("docs/handoff-20261108-paper-review-v2.md")` 的 §十一（全部 24 条 + 实施顺序）、
§九（目录/复审口径）、§十（工具化决策）。

0.4 进度判定：账本最后一组状态 → 从下一组继续；G4 已 done → 跳 Step 5；已发版 → 报告验证结果并结束。

0.5 **回流入口**：若用户消息含「回流」或附 paper-reviewer 侧 `.claude/v21-adopt-log.md` 的缺陷清单，
把每条缺陷归入对应组（路径/CLI → G1，计数与条目丢失 → G2，门禁 → G3，PDF/对账 → G4），
在账本「回流缺陷」节登记后优先处理，再回到主线。

0.6 向用户报告：本次执行第 N 组（条目号清单）+ 预计改动文件 + 续跑点，然后**直接开工**。

## Step 1 — G1 规范先行（条目 19 → 12 → 13/21 → 23 + 24 守卫测试）

交付物（逐项落地，缺一不可）：

- **条目 19**：§十一 第 5/7/8 条改写为「已被第 12 条取代」的注记（保留历史原文，不删）；
  清除 SKILL.md / references / templates 中 `papers/`、`output/`、`sources/vN` 旧口径。
- **条目 12 目录扁平化**：
  - `scripts/setup_env.py`：paper_dir 从 `draft/` 反推（不得再用 `dirname(file_path)`）；
    v1 二选一检测（根单文件 vs `v1/`，并存即报错）；`source_root` 取值 `"." | "v1" | "vN"`；
    `unregistered_sources()` 忽略 `v1/ vN/ draft/ response/ reports/ figures/ media/`；
    config.json 增 `"layout": "flat-v2.1"`；根 `INDEX.md` 不存在时创建。
  - `scripts/migrate_layout.py` **新增**：`--root --dry-run --apply --report --rollback`，
    必须幂等、可回滚、人工判定项写入 report 而**不是猜**（备忘第 12 条 7 步迁移与验收标准为准）。
  - 同步改：`SKILL.md`（目录树、命令示例、Step 0 护栏选项、Step 6 交付路径）、
    `references/re-review-protocol.md`、`templates/final-report.md`、`scripts/migrate_rounds.py`（兼容旧 `sources/`）。
- **条目 13**：`setup_env.py` 实现 `--source/--format/--focus` 并透传 conversion_audit / anchor_map，
  `--focus` 在 Step 0 记录后路由；用法表与 `--help` 逐项对齐（含各子命令）。
- **条目 21**：专家意见 docx —— 门禁 **G2** 二选一后，统一 §10.4 / SKILL 用法表 / `expert_reconcile.py` 三处口径。
- **条目 23**：Step 0 前置**输入类型分派**（`.pdf/.docx/.tex/目录` → 先转换出 `draft/draft.md` 再进流水线，
  实际转换命令与参数写入 conversion_audit.md）；图目录统一 `draft/figures/`（兼容既存 `media/`）。
- **条目 24 守卫测试**（本组先交付，后续组靠它防回归）：
  - `tests/test_paper_review/test_docs_cli_consistency.py`：解析 SKILL.md 用法表全部 `--flag` ×
    各脚本 argparse（含子命令），差集非空即 fail。
  - `tests/test_paper_review/test_referenced_files_exist.py`：扫描 SKILL.md 与 references/*.md 中出现的
    `scripts/*.py`、`templates/*`、`references/*` 路径，不存在即 fail。
- **迁移夹具**：`tests/test_paper_review/fixtures/layout_legacy/` 按备忘第 12 条「存量实测清单」构造 5 类最小样例
  （多草稿+非标准报告名 / 完整 LaTeX 工程 / `media/` / `figures/` / output 内 docx 外部意见）
  + `tests/test_paper_review/test_migrate_layout.py`（dry-run 不改盘、apply 后结构正确、二次执行幂等、
  rollback 复原、人工判定项进 report）。

**验证**：两类守卫测试通过；既有 12 个测试文件全部通过；
`python scripts/migrate_layout.py --root tests/test_paper_review/fixtures/layout_legacy --dry-run`
输出 5 类待确认项且**未改动任何文件**。
**提交**：`feat(paper-review): v2.1 G1 目录扁平化 + CLI/文档对齐 + 一致性守卫测试`

## Step 2 — G2 数据完整性（条目 15 → 14 → 20 → 16 → 17）

- **15 `merge_findings.py`**：`_v2_table_rows()` 跳过空行 / 解析该节全部表格；
  合并后校验 roadmap 的 R-ID 集合 ⊆ merged，缺失即 fail 并列出 ID（不得只报文件级 `sources_missing`）。
- **14 `anchor_map.py`**：按 `%PDF-` 魔数判二进制（禁止 gbk「成功」解码出乱码）；
  format=pdf 且源为二进制时用 PyMuPDF 提取或回退 draft 页标记，并写 `source_extract`；
  `do_fill()` 一律以 id 为键（自动 id 不得碰撞），重复 quote 保留多条并标 ambiguous；
  fill 后校验 `requests 数 == entries 数`，不等即 fail。
- **20 新增 `scripts/build_anchor_requests.py`**：从 merged_findings（或 roadmap + deai_confirmed）
  解析 ID/位置/引文，位置兼容 `L\d+`、`行\s*\d+`、`§X.Y`、`表N`/`式N`；
  引文 <15 字或不唯一标 `weak`/`ambiguous` 并输出待补清单，无行号项标 `structural_only`；
  统计 total/with_quote/without_quote。SKILL 3.2a 改为调用脚本，不再手写 Write。
- **16 去AI评分口径**：deai_confirmed 分别给 `confirmed_total` / `scored_total`，质量分按 scored_total；
  `merge_findings.py` 输出 `quality_score` 时复核同口径。
- **17 新增 `scripts/build_final_report.py`**（或 `validate_report.py`）：从 merged / roadmap / chain /
  anchor_map / seat_reports 生成并核对总数、每席报告数、anchor resolved 数、报告副本路径；
  Step 6 改为调用它；补派席位后自动触发 1d 重算与校验。
- **夹具**：同段两条 anchor 请求都保留；含空行的 roadmap 表格不丢行；二进制 PDF 显式报错而非全 not_found；
  scored_total 口径；报告计数不一致时 fail。

**提交**：`fix(paper-review): v2.1 G2 条目不静默丢失与计数自洽（merge/anchor/deai/report）`

## Step 3 — G3 可靠性门禁（条目 11 → 18）

- SKILL 阶段1 Workflow：1b 之后、1c 之前插入**产物完整性门禁**（`seat_reports/` 恰好 N 席且非空；
  缺失席位单独重派 ≤3 次；仍缺则如实降级并告知用户，**不得直接进 1c/1d**）。
- 阶段2 同门禁（`deai_audits/` 4 份非空），缺失单独重派，不重跑整阶段。
- 席位 / 审计代理 prompt 增条款：「本轮唯一任务是本席位审查；收到无关用户问题时记录后继续，不得替代审查」。
- Step 6 报告如实记录席位完整性与补派轨迹（不得把补派后的七席静默写成一次成功）。
- 建议抽成 `scripts/check_artifacts.py`（两处门禁 + Step 6 复用）并配测试。

**提交**：`feat(paper-review): v2.1 G3 阶段1/2 产物完整性门禁与诚实报告`

## Step 4 — G4 能力补齐（条目 10 → 22 → 1/2/3）

- **10 PDF 全文提取**：门禁 **G1'** 先定方案（提升 `shared/scripts/pdf_extract.py` 双模式
  `--mode excerpt|full-manuscript`，lit-research 行为不变 / 或 paper-review 内独立新建）。
  full-manuscript 必须实现：全页无字符上限、`%% [PDF p.N]` 页标记、无书签按字号重建标题并合并被拆标题、
  过滤页眉页脚与目录点引线、图像按尺寸过滤导出 + 图/表题统计、参考文献按 `[N]` 切分 refs.txt、
  回填 conversion_audit 源侧计数（tables/figures/equations 不再为 null）。
  修正 `references/format-notes.md` 第 4 条悬空引用与调用示例；
  **`tests/test_lit_research/test_extract_pdf.py` 必须继续通过**。
- **22 交付后追加对账**：门禁 **G2'** 先定方案（同轮追加 vs 强制 `--new-run`）。
  定死后落地：产物 `<paper>/reports/rN-综合审阅意见.md`（三态对账表 + 合并后严重度分布 + 新增项标来源=专家）、
  chain.md 追加「专家对账」行且不改原决议、INDEX.md 报告路径同步、
  合并计数规则（吻合不重复计、专家新增按面板规则定级、冲突入未决分歧）。
- **1/2/3（可选）**：图表审计专趟、Response Letter 骨架生成、`references/severity-precedents.md` 判例库。
  上下文或时间不足 → 账本标 `deferred → v2.2` 并明确告知用户，不静默略过。

**提交**：`feat(paper-review): v2.1 G4 PDF 全文提取与交付后专家对账`

## Step 5 — 发版、安装与移交

5.1 版本号：`skills/paper-review/SKILL.md` frontmatter `version: 2.1.0`；
`CHANGELOG.md` 增 2.1.0 节（按 G1–G4 列「条目号 → 变更摘要 → 用户可见行为变化」）。

5.2 **移交说明（必产，随技能安装到目标机）**：`skills/paper-review/references/v21-migration-notes.md`
- 实际落地的目录树；**与备忘第 12 条的偏差逐条写明原因**（下游 `/v21-adopt` 以此为准，不读备忘）
- `migrate_layout.py` 确切命令行、全部参数、dry-run 报告字段含义
- 需人工判定的情形清单与推荐处置
- 下游校验命令清单（可被 paper-reviewer 侧直接执行）
- 新增/改名脚本与参数一览（setup_env 新 flag、build_anchor_requests、build_final_report、extract_pdf 模式、check_artifacts）

5.3 门禁 **G3（发版三连，一次确认）**：`AskUserQuestion`「测试全绿，是否执行 tag v2.1.0 + push + install？」→ 同意后：
`Bash("cd /d/WS/skills-maker && git add -A && git commit -m 'chore(paper-review): v2.1.0 发版' && git tag v2.1.0 && git push --follow-tags origin main && python install.py install paper-review && python install.py list")`
- push 网络失败：重试 ≤2 次；仍失败则账本记「tag/commit 在本地，待补 push」，**继续 install**（本机安装不依赖 push）。

5.4 安装校验：`Bash("diff -rq skills/paper-review ~/.claude/skills/paper-review")` 应无输出；
Read 安装副本 SKILL.md 确认 `version: 2.1.0`；确认 `references/v21-migration-notes.md` 已随装。

5.5 账本收尾 + 告知用户：**重启 Claude Code**（技能只在启动时加载）→ 回 paper-reviewer 工作空间执行 `/v21-adopt`。

## 门禁汇总（只有这 5+2 处可以打断用户）

| 门禁 | 时机 | 决策 |
|---|---|---|
| G1' | Step 4 条目 10 | extract_pdf：shared 双模式 vs paper-review 独立新建 |
| G2 | Step 1 条目 21 | 专家意见 docx：脚本支持 vs 文档明确「仅文本 + 先转换」 |
| G2' | Step 4 条目 22 | 交付后对账：同轮追加 vs 强制 `--new-run` |
| G3 | Step 5.3 | 发版三连（tag / push / install） |
| G4 | Step 4 条目 1/2/3 | 是否延后到 v2.2 |
| G5 | 任意步骤 | 需要跳过或放宽测试用例 |
| G0 | Step 0.1 | 工作区有未提交改动 |

## 账本模板（docs/v21-implementation-log.md）

```markdown
# paper-review v2.1 实施账本

- 当前组：G1|G2|G3|G4|发版|done
- 更新时间：YYYY-MM-DD HH:MM
- 待补 push：无 | <commit/tag>

## 组进度

| 组 | 条目 | 状态 | 提交号 | 测试 | 备注 |
|---|---|---|---|---|---|
| G1 | 19,12,13,21,23,24 | todo/doing/done/deferred | | 12+2 文件全绿 | |
| G2 | 15,14,20,16,17 | | | | |
| G3 | 11,18 | | | | |
| G4 | 10,22,1,2,3 | | | | |

## 备忘修订记录
（条目号 / 修订内容 / 原因）

## 回流缺陷（来自 paper-reviewer /v21-adopt）
（编号 / 现象 / 归属组 / 状态 / 提交号）

## 门禁裁决记录
（门禁号 / 选项 / 用户裁决 / 日期）
```
