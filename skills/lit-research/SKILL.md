---
name: lit-research
version: 1.0.1
description: |
  文献调研技能：给定研究主题，通过 deep-research 检索文献，与本地文献库查重去重，
  下载原文并提取全文，按标准卡片格式建立资料卡片，进行质量评分和去AI化处理，
  最终集成到文献库。
  触发条件：用户说"调研文献"、"文献检索"、"查找相关研究"、"建卡"、
  "literature survey"、"lit review"、"文献调研"等。
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
  - WebSearch
  - WebFetch
  - Skill
  - AskUserQuestion
  - Workflow
---

# lit-research — 文献调研技能

给定研究主题，完成「检索 → 查重 → 决策 → 下载 → 建卡 → 去AI化 → 验证 → 入库」全流程，
产出符合标准格式的资料卡片并集成到本地文献库。

## 约定

- `{SKILL_DIR}`：本技能安装目录（即本 SKILL.md 所在目录），脚本调用一律写绝对路径
  `python {SKILL_DIR}/scripts/xxx.py`。
- `<库路径>`：文献库根目录，其下为 `NNN_XXX/` 文献子目录与 `文献库索引.tsv`。
  未由用户给出时，先用 AskUserQuestion 询问，不得猜测。
- **工作文件**：所有 `_step*.json` / `_step*.md` / `_step*.txt` 中间文件写入
  **当前项目工作目录**（非文献库目录）。步骤间数据只通过这些文件传递。
- **编号规则**：新文献编号从 `_step0_env.json` 的 `max_number + 1` 起连续分配，3 位数字。
- **目录/文件命名**：`NNN_XXX/` 目录内三件套 —— `NNN_card_XXX.md`（卡片）、
  `NNN_extract_XXX.txt`（文本提取）、`NNN_src_XXX.pdf`（源文件）；XXX 为英文描述名
  （下划线连接，如 `Wang_PromptInjection_LLM`）。
- **Route A（添加引用）**：本技能只负责建卡，并额外产出「拟引文文字 + GB/T 7714
  参考文献条目」交用户/主写作流程写入论文，不直接修改论文正文。
- 参考文件：`references/card-template.md`（卡片模板与占位符规则）、
  `references/quality-rubric.md`（评分细则）、`references/card-checklist.md`（V1–V6 清单）、
  `references/gbt7714-quickref.md`（著录格式速查）。

## 流程总览

```
Step 0 环境初始化与对齐（setup_env.py）
Step 1 锁定研究问题（_step1_query.md）
Step 2 深度文献调研（🔒 Skill: deep-research，full 级）
Step 3 与本地库交叉查重（lookup_lib.py，4 信号 + 🔒 二次人工复核）
Step 4 质量评分（quality-rubric.md）+ 用户决策（AskUserQuestion）
Step 5 下载原文与文本提取（extract_pdf.py，逐篇）
Step 6 建立资料卡片（create_card.py + card-template.md，逐篇）
Step 7 去AI化（🔒 Skill: stop-slop → academic-humanizer → humanize-writing，逐篇）
Step 8 入库集成与终验（rebuild_index.py + validate_card.py V1–V6 → 收尾报告）
```

---

## Step 0 — 环境初始化与对齐

- **执行**：`Bash("python {SKILL_DIR}/scripts/setup_env.py --init --lib-path <库路径> > _step0_env.json")`
  （若项目自带卡片模板，追加 `--template <模板路径>`）
- **输入**：用户提供的文献库根目录；可选的项目定制模板路径。
- **输出**：`_step0_env.json`（`max_number` / `lib_path` / `template_path` /
  `dependencies_ok` / `missing_deps` / `lib_problems` / `template_ok`）。
- **验证**：`dependencies_ok == true` 且 `lib_problems` 为空且 `template_ok == true`。
  - 依赖缺失 → `Bash("pip install <missing_deps>")` 后重跑本步骤；
  - 目录/模板问题 → 请用户修正路径后重跑。
  - 通过后记录：新文献起号 = `max_number + 1`。

## Step 1 — 锁定研究问题

- **执行**：`Write("_step1_query.md", ...)` —— 将研究问题、检索角度（背景知识/技术综述/
  发展态势/关键技术/对比分析/引用案例，至少覆盖「技术综述 + 引用案例」两类）、
  收录与排除标准写入文件。
- **输入**：用户的研究主题与用途说明；（论文项目场景下）对应章节的核心论证要点。
- **输出**：`_step1_query.md`。
- **验证**：文件存在且含明确、可直接检索的研究问题。主题过宽或含糊
  （如未限定领域/年代/用途）→ `AskUserQuestion` 提 2–3 个澄清问题后重写，不得带病进入 Step 2。

## Step 2 — 深度文献调研（🔒 强制调用 deep-research）

- **执行**：`Skill(skill="deep-research", args="<_step1_query.md 全文；明确要求 full 级深度>")`；
  技能完成后，从调研报告提取候选文献清单 →
  `Write("_step2_candidates.json", [{"title","doi","arxiv","authors","year","source","url","relevance"}, ...])`。
- **输入**：`_step1_query.md`。
- **输出**：deep-research 调研报告；`_step2_candidates.json`（完整著录 + 相关度评价）。
- **验证**：`_step2_candidates.json` 为合法 JSON 数组且每项含非空 `title`。
  🔒 不得降级为 quick/lit-review，不得以口头检索、WebSearch 罗列代替 deep-research 全流程。
  宁缺毋滥：候选不刻意凑数，但不得遗漏报告中的高质量文献。

## Step 3 — 与本地库交叉查重（4 信号 + 🔒 二次复核）

- **执行**：`Bash("python {SKILL_DIR}/scripts/lookup_lib.py --check _step2_candidates.json --lib-path <库路径> > _step3_lookup.json")`
- **输入**：`_step2_candidates.json`；`<库路径>/文献库索引.tsv`。
- **输出**：`_step3_lookup.json`（`new` / `duplicate` / `uncertain`，每项含
  `candidate` 原始数据 + `match_info.signals` + `match_info.matches` 库内条目）。
- **验证**：三列表长度之和 == 候选总数。🔒 二次人工复核：对 `duplicate` 与 `uncertain`
  逐项 `Read` 库内命中卡片（`<库路径>/NNN_XXX/NNN_card_*.md`）比对确认，
  用 `Edit` 把复核结论写回 `_step3_lookup.json`（误判 duplicate 的移入 new，
  确认重复的 uncertain 移入 duplicate）。只向用户报告净新候选；
  若发现「已在库、未引用且高度对口」的突兀项，单独列出提醒用户复查。
  严禁引入不必要的重复（重复一旦入库，后期极难处理）。

## Step 4 — 质量评分与用户决策

- **执行**：
  1. 对 `_step3_lookup.json["new"]` 每篇按 `references/quality-rubric.md` 五维打分 + 加减分 →
     `Write("_step4_scores.json", ...)`；
  2. `AskUserQuestion(questions=[...])` —— 呈报评分表，对每篇候选请用户三选一：
     ① 添加引用（Route A）/ ② 建卡备用（Route B）/ ③ 放弃；
  3. `Write("_step4_decisions.json", [{"number","name","title","route"}, ...])`，
     编号从 `max_number + 1` 起按决策顺序连续分配。
- **输入**：`_step3_lookup.json`、`references/quality-rubric.md`、`_step0_env.json`（起号）。
- **输出**：`_step4_scores.json`、`_step4_decisions.json`。
- **验证**：每个 `route ∈ {A, B, skip}` 的决策都有唯一 3 位编号且无冲突；
  10–14 分入选者已写明充分理由。仅 route A/B 进入 Step 5。
  用户未决策前不得进入 Step 5。

## Step 5 — 下载原文与文本提取（逐篇，route A/B）

- **执行**：先 `Bash("mkdir -p <库路径>/NNN_XXX")`，再
  `Bash("python {SKILL_DIR}/scripts/extract_pdf.py --url <下载URL> --number NNN --name XXX --output-dir <库路径>/NNN_XXX > _step5_download_NNN.json")`；
  已有本地 PDF 时以 `--file <路径>` 替换 `--url`。
- **输入**：`_step4_decisions.json`（编号/名称/URL）。
- **输出**：`<库路径>/NNN_XXX/NNN_src_XXX.pdf`、`NNN_extract_XXX.txt`、`_step5_download_NNN.json`。
  提取文本逐页植入页标记 `%% [PDF p.N]`（页级锚点标准格式，供 paper-review
  anchor_map.py 做 pdf 源定位）与 `--- Page N ---`（兼容旧格式）。
- **验证**：`success == true` 且 `chars > 0`。
  - 下载失败（付费墙/反爬）→ 给出 URL + 命名规则 `NNN_src_XXX.pdf` 请用户手工下载放入
    `NNN_XXX/`，**暂停等待用户确认后再继续**（确认后以 `--file` 重跑提取）；
  - `chars == 0`（扫描图片型 PDF）→ 卡片验证状态标 `⚠️ 部分验证（扫描版，未提取文字）`；
  - `pages > 30MB` 大文件提取失败同上处理。

## Step 6 — 建立资料卡片（逐篇，route A/B）

- **执行**：
  1. `Read("<库路径>/NNN_XXX/NNN_extract_XXX.txt")` 精读原文提取内容；
  2. 撰写卡片内容 → `Write("_step6_data_NNN.json", ...)`，格式遵循 create_card.py
     数据规范与 `references/card-template.md` 头部注释（9 字段基本信息、摘要=原文逐字+
     中文翻译+来源、内容概要 800–1000 字按「背景→方法→实验/结论→与主题关联」结构、
     引用方式按 `references/gbt7714-quickref.md` 著录）；
  3. `Bash("python {SKILL_DIR}/scripts/create_card.py --number NNN --name XXX --data _step6_data_NNN.json --template <_step0_env.json 的 template_path> --output <库路径>/NNN_XXX/NNN_card_XXX.md > _step6_card_NNN.json")`。
- **输入**：`NNN_extract_XXX.txt`、`card-template.md`、`gbt7714-quickref.md`。
- **输出**：`<库路径>/NNN_XXX/NNN_card_XXX.md`、`_step6_card_NNN.json`、`_step6_data_NNN.json`。
- **验证**：`success == true` 且 `missing_placeholders == []`；
  内容概要字数 800–1000、事实在前评价殿后（铁律）、忠于原文不臆造不过度延伸；
  route A 另需产出「拟引文文字 + 参考文献条目」附入卡片「引用情况」六字段，
  route B 卡片「引用情况」写单行「未被论文正文引用」。

## Step 7 — 去AI化（逐篇，🔒 三个技能依次实际调用）

- **执行**（顺序不可调换、不可省略）：
  1. `Skill(skill="stop-slop", args="<处理 NNN_card_XXX.md 的内容概要与全部自由文字段落>")`
  2. `Skill(skill="academic-humanizer", args="<同上，学术化改写>")`
  3. `Skill(skill="humanize-writing", args="<同上，最终人味润色>")`
  每调用完一个技能，立即 `Edit("_step7_deai_log.txt")` 追加一行：
  `<ISO时间> <技能名> <处理的卡片文件>`；技能产出的修改用 `Edit` 落回卡片文件。
- **输入**：`NNN_card_XXX.md`。
- **输出**：去AI化后的卡片；`_step7_deai_log.txt`（每篇 3 行日志）。
- **验证**：日志中该卡片对应 3 个技能名齐全；对照 `references/card-checklist.md` V5
  人工核对：无 Tier1 词汇（delve/landscape/tapestry/paradigm shift/leverage 等）、
  无过度对仗、无空洞总结句。注意：「文献[N] XXX」逐篇引用平行句式是学报综述标准
  风格，不属于 AI 痕迹，不得标记。🔒 不得用文字描述代替技能实际调用。

## Step 8 — 入库集成与终验（V1–V6）

- **执行**：
  1. `Bash("python {SKILL_DIR}/scripts/rebuild_index.py --lib-path <库路径> > _step8_index.json")`
  2. 逐篇 `Bash("python {SKILL_DIR}/scripts/validate_card.py --number NNN --lib-path <库路径> --extract-log _step7_deai_log.txt > _step8_validate_NNN.json")`
  3. 全部通过后收尾：清理本轮临时文件（`_step*.json` 等，正式产物三件套与索引保留；
     清理前 `AskUserQuestion` 确认）；如在 git 仓库且用户要求，提交本轮成果；
  4. 向用户报告：新增清单（编号/标题/route/评分）、查重拦截数、遗留问题
     （含「未发现需修改的问题」也要明说）。
- **输入**：全部新增 `NNN_XXX/` 目录（三件套齐全）、`_step7_deai_log.txt`。
- **输出**：重建的 `<库路径>/文献库索引.tsv`、`_step8_index.json`、`_step8_validate_NNN.json`。
- **验证**：`_step8_index.json` 的 `success == true` 且 `entries` 较上轮增加本次新增数；
  每篇 `all_pass == true`（V1–V6 逐项通过，机械项看 JSON、人工项对照
  `references/card-checklist.md` 声明核对结果）。任一 V 不通过 → 回退修复
  （V1/V2 → Step 2/3 补做；V3/V4 → Step 6 改卡；V5 → Step 7 重跑去AI化；
  V6 → 修正目录/文件命名后重跑 rebuild_index.py）→ 重跑验证，循环直至全部通过。

---

## 强制纪律

1. **每个步骤必须实际执行，不可口头描述代替**。凡标 🔒 者（deep-research 调用、
   二次复核、用户决策、去AI化技能调用）不得省略或降级；推进前自检「本步骤是否已
   实际执行」，未执行立即补做。
2. **步骤间数据通过文件传递（`_step*.json` 等），不依赖 Claude 记忆**。每步开工先
   `Read` 上一步产物文件，收工必写本步产物文件。
3. **Skill 调用必须通过 Skill tool 实际执行**（deep-research / stop-slop /
   academic-humanizer / humanize-writing），不得以「文字已较干净」「大致走一遍」为由
   简化为快速检查或直接改写。
4. **验证失败必须回退修复，不可跳过**：任一验证点不通过 → 回退到对应步骤修复 →
   重跑该验证，直至全部通过才进入下一步。
5. **同一检查点连续 3 次失败则暂停，请用户介入**：向用户报告失败详情与已尝试的修复，
   等待指示，不得静默绕过。
