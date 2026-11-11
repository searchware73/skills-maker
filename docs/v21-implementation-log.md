# paper-review v2.1 实施账本

- 当前组：G4
- 更新时间：2026-11-11
- 待补 push：git pull/push 网络失败（Connection reset），离线开工，push 待补

## 组进度

| 组 | 条目 | 状态 | 提交号 | 测试 | 备注 |
|---|---|---|---|---|---|
| G1 | 19,12,13,21,23,24 | done | f687cbd | 15 文件 212 用例全绿 | G1 验证命令通过：夹具 dry-run 输出 5 类待确认项（10 条）、26 moves、5 rewrites、零文件改动、无 .migrate-layout 残留 |
| G2 | 15,14,20,16,17 | done | 410881d | 17 文件 264 用例全绿 | 条目17 二选一取 validate_report.py（校验器而非生成器）；条目20 仅 merged 单源输入 |
| G3 | 11,18 | done | （待回填） | 18 文件 276 用例全绿 | 阶段1/2 各拆两段 Workflow，中间插 check_artifacts.py 门禁；防劫持条款进全部代理 prompt |
| G4 | 10,22,1,2,3 | todo | | | |

### G1 明细（2026-11-11）

- 新增：`skills/paper-review/scripts/migrate_layout.py`（--root/--dry-run/--apply/--rollback/--report，
  幂等、字节级回滚、5 类人工判定项只列不猜）；`tests/test_paper_review/fixtures/layout_legacy/`（50 文件）；
  `tests/test_paper_review/test_migrate_layout.py`（24）；`test_docs_cli_consistency.py`（10）；
  `test_referenced_files_exist.py`（5）
- 改写：`setup_env.py`（paper_dir 从 draft/ 反推、v1 二选一、source_root "."|"v1"|"vN"、
  layout=flat-v2.1、根 INDEX.md、--source/--format/--focus/--no-fix、非 md 分派指引 exit 1、docx 魔数校验 exit 2）→ 31 用例
- 修改：`migrate_rounds.py`（就地规范化为扁平口径）→ 11；`expert_reconcile.py`（docx 原生解析，
  zipfile+ElementTree 零依赖）→ 26
- 文档：SKILL.md（用法表/目录树/Step 0.0/0.1/6.4/脚本清单）、re-review-protocol.md、templates/chain.md、
  templates/final-report.md、format-notes.md、备忘（条目 5/7/8/21 注记）
- 测试合计：212 = anchor_map 11 + bib_lint 10 + conversion_audit 15 + diff_scope 13 + docs_cli 10 +
  expert_reconcile 26 + merge_findings 7 + merge_findings_v2 8 + migrate_layout 24 + migrate_rounds 11 +
  numeric_checks 17 + referenced_files 5 + resume 20 + setup_env_v2 31 + skill_invocation 4

### G2 明细（2026-11-11）

- 修改：`merge_findings.py`（条目15：`_v2_table_rows` 空行/散文不截断、收集本节全部表格、
  重复表头跳过；声明 R-ID ⊆ 合并∪撤回 校验，缺失 exit 1 不写输出。条目16：confirmed_total/
  scored_total 双口径 + quality_score_basis + quality_basis_warnings）→ test_merge_findings_v2 扩至 15
- 修改：`anchor_map.py`（条目14：%PDF- 魔数 → PyMuPDF → draft 页标记 → 显式报错级联，
  source_extract 留痕；fill 以 id 为键 + 自动 id 防碰撞 + 重复 id exit 1 + dup_quote 标 ambiguous +
  structural_only 保留 + requests==entries 强制校验）→ test_anchor_map 扩至 21
- 新增：`build_anchor_requests.py`（条目20：merged → anchor_requests.json；引文抽取/位置四形态/
  weak/ambiguous/not_in_draft/structural_only/needs_manual_quote；含省略号示意性引文跳过
  draft 存在性核查防系统性误报）+ test_build_anchor_requests.py（14，含 build→fill 闭环用例）
- 新增：`validate_report.py`（条目17：合并统计8数/决议三方/质量评分/反查统计↔anchor_map/
  席位份数与非空/交付副本字节一致+INDEX 行/chain 本轮节；problems 全收集 exit 1）
  + test_validate_report.py（21，merged 夹具由 merge_findings.py 真跑生成）
- 文档：SKILL.md（2c 三行固定格式提示词、阶段2 报告口径、3.2a 改调脚本+人工补引文、
  Step 6 增 6.6 校验步/RESUME 顺延 6.7、脚本清单 +2 行）；templates/final-report.md §2 反查统计行；
  references/anchor-locator.md 调用时机表；deai-discussion-protocol.md 2c 模板（条目16）；
  备忘条目 14/15/16/17/20 加「[v2.1 已实施（G2）]」注记
- 守卫测试 meta 集合同步：EXPECTED_MENTIONED_SCRIPTS +build_anchor_requests/validate_report
- 测试合计：264 = G1 的 212 + build_anchor_requests 14 + validate_report 21 +
  merge_findings_v2 新增 7 + anchor_map 新增 10（17 文件全绿）

### G3 明细（2026-11-11）

- 新增：`check_artifacts.py`（--run-dir/--subdir/--expect/--ext；恰好 N 份非空、
  前缀匹配 S1→S1-EIC统筹.md、多余文件 unexpected 判不完整、redispatch=missing+empty、
  不完整 exit 1）+ test_check_artifacts.py（12）
- SKILL.md：阶段1 拆 1b Workflow（七席∥）→ 1b-gate → 1c/1d Workflow（主持人用
  MOD_COMMON，防劫持条款）；阶段2 拆 2a Workflow（四技能∥）→ 2a-gate → 2b/2c
  Workflow；「触发请求锚定」提示（harness 注入最新用户消息且声明优先）；quick 模式
  写完 seat_reports 同样过门禁（--expect S1,S6）；Step 6.3 必含「席位完整性与补派
  轨迹」；阶段报告行如实记录补派/降级；脚本清单 +1 行
- 防劫持条款进 4 处 prompt COMMON：席位（1b）、审计（2a）、面板主持（1c/1d）、去AI主持（2b/2c）
- 文档：templates/final-report.md §3 席位完整性行 + §4 审计完整性；
  deai-discussion-protocol.md 2a 节增门禁说明；备忘条目 11/18 加实施注记；CHANGELOG G3 节
- 守卫 meta：EXPECTED_MENTIONED_SCRIPTS +check_artifacts
- 测试合计：276 = G2 的 264 + check_artifacts 12（18 文件全绿）

## 备忘修订记录
（条目号 / 修订内容 / 原因）

- 条目 5/7/8（§十一）/ 各加「[v2.1 注记：…已被第 12 条取代]」引导块，保留历史原文不删 /
  条目 19 要求清除旧口径且备忘自身需标明被取代，防止后续实施回读旧文（G1）
- 条目 21 / 在二选一选项后追加「[v2.1 已实施（G1，门禁 G2 用户裁决：脚本原生支持 docx）]」记录：
  采用 expert_reconcile.py zipfile+ElementTree 原生解析 word/document.xml（零第三方依赖，
  与 conversion_audit.py 同一模式），未用 pandoc/python-docx；§10.4 标题、SKILL 用法表、脚本实现
  三处口径统一为 `<md|docx>` / 备忘只列了选项，实施后须记录实际选择与实现方式（G1）
- 条目 14/15/16/17/20 / 各加「[v2.1 已实施（G2）]」注记块，保留历史原文 /
  实施事实与备忘有出入处需就地固化：条目17 二选一取 **validate_report.py**（报告生成仍走
  模板+人工语义归并——生成器无法替代语义归并，校验器即可锁死数字一致）；条目20 仅实现
  merged_findings.md 单源输入（merged 即合并后唯一权威清单，备选双源无独立价值）；
  含省略号引文标 weak 并跳过 draft 存在性核查（NFKC 把 … 展开为 ...，示意性片段核查
  必然误报 not_in_draft——实测夹具触发）（G2）

## 回流缺陷（来自 paper-reviewer /v21-adopt）
（编号 / 现象 / 归属组 / 状态 / 提交号）

## 门禁裁决记录
（门禁号 / 选项 / 用户裁决 / 日期）

- G2 / 条目21 专家意见 docx：「仅文本+先转换」vs「脚本原生支持 docx」/ **用户裁决：脚本原生支持 docx**（实现采用 conversion_audit.py 既有的 zipfile+ElementTree 零依赖模式，不引入 python-docx/pandoc 运行时依赖）/ 2026-11-11
