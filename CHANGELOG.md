# CHANGELOG

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
