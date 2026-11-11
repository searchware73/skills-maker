# paper-review v2.1 实施账本

- 当前组：done（v2.1.0 已发版并安装；待补 push 后无遗留）
- 更新时间：2026-11-11
- 待补 push：本地 main 领先远端（G1–G4 全部提交 + 发版提交 28e18c8 + tag v2.1.0）；
  push 三连（首发 + 重试 2 次）均 Connection reset / 443 不可达，恢复网络后
  `git push --follow-tags origin main` 一次补齐

## 组进度

| 组 | 条目 | 状态 | 提交号 | 测试 | 备注 |
|---|---|---|---|---|---|
| G1 | 19,12,13,21,23,24 | done | f687cbd | 15 文件 212 用例全绿 | G1 验证命令通过：夹具 dry-run 输出 5 类待确认项（10 条）、26 moves、5 rewrites、零文件改动、无 .migrate-layout 残留 |
| G2 | 15,14,20,16,17 | done | 410881d | 17 文件 264 用例全绿 | 条目17 二选一取 validate_report.py（校验器而非生成器）；条目20 仅 merged 单源输入 |
| G3 | 11,18 | done | bbe578a | 18 文件 276 用例全绿 | 阶段1/2 各拆两段 Workflow，中间插 check_artifacts.py 门禁；防劫持条款进全部代理 prompt |
| G4 | 10,22,1,2,3 | done | 593248b | 20 文件 317 用例全绿 + lit-research 1 用例绿 | 门禁 G1'（独立新建）/G2'（同轮追加）/G4（条目1/2/3 全部延后 v2.2）已裁决；条目 9 维持冻结 |
| 发版 | Step 5 | done | 28e18c8 + tag v2.1.0 | 20 文件 317 + lit-research 1 = 318 全绿 | 门禁 G3 用户裁决执行三连；push 失败×3 记待补；install 校验：diff -rq 空 / 安装副本 version 2.1.0 / v21-migration-notes.md 已随装 |

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

### G4 明细（2026-11-11）

- 新增：`skills/paper-review/scripts/extract_pdf.py`（条目10，门禁 G1' 裁决独立新建；
  full-manuscript：全页无上限、`%% [PDF p.N]` 页标记、无书签按字号重建标题+被拆标题合并
  （有书签走 get_toc 匹配）、页眉页脚/独立页码/目录点引线过滤、图像按像素尺寸与长宽比
  过滤导出 figures/+markdown 引用+图/表题统计、参考文献按 [N] 切分 refs.txt（跨行归并、
  致谢/附录停止）、pdf_source_counts.json 源侧计数；加密/损坏 exit 1 指 Step 0.3 回退链；
  find_tables 的 PyMuPDF stdout 推广行重定向吞掉）+ test_extract_pdf.py（25，
  PyMuPDF 合成 3 页夹具：字号 24/16/13/10.5 分级、跨页页眉+页码、点引线、
  「2.1 实验」+「环境与数据集」被拆标题、200x150/10x10/300x4 三形态图像、线框表格、
  [1]–[3] 参考文献含跨行条目、加密 PDF、书签模式）
- 修改：`conversion_audit.py` +`--source-counts`（条目10 回填：JSON 覆盖非 null 键，
  缺失/非法 exit 1；stdout 增 source_counts_overlay/overlay_applied）→ test +6（21）
- 修改：`expert_reconcile.py` +`report` 子命令（条目22，门禁 G2' 裁决同轮追加：
  rN-综合审阅意见.md 三态对账表+未决分歧+合并后分布（新增标来源=专家）、
  chain.md r{N} 节追加「专家对账」行原决议不变且幂等替换（r1/r10 负向环视）、
  INDEX.md 报告路径列同步失败仅告警；pending/merged 缺统计行/chain 无该轮节 exit 1；
  chain.md 定位支持 run_dir 及其上级=.review/ 双布局）→ test +10（36）
- 修改：`skills/lit-research/scripts/extract_pdf.py` 仅 docstring 加「⚠ 节选提取，
  勿用于全文审阅」注记（铁律1 例外经技能 Step 4 明文授权；行为零改动，
  tests/test_lit_research/test_extract_pdf.py 1 用例保持绿）
- SKILL.md：Step 0.0 .pdf 分派改调 extract_pdf.py（产物清单+回退链）、0.4 增
  --source-counts 必带条件、0.6 注 refs.txt 直供 bib_lint、目录树补 draft/refs.txt +
  pdf_source_counts.json + reports/rN-综合审阅意见.md、新增「### 交付后追加对账」节
  （6.7 后：init/match/verify/AskUserQuestion 未决裁决/report 五步）、用法表
  --expert-comments 行注交付后路径、脚本清单 +extract_pdf 行并更新 conversion_audit/
  expert_reconcile 行
- 文档：format-notes.md 第 4 条实指 scripts/extract_pdf.py + 调用示例 + lit-research
  辨析；templates/chain.md r1 节增可选「专家对账」行示例；备忘条目 1/2/3（延后注记）、
  10、22 加「[v2.1 已实施（G4，门禁裁决…)]」注记；CHANGELOG G4 节 + 标题改「G1–G4 已交付」
- 守卫 meta：EXPECTED_MENTIONED_SCRIPTS +extract_pdf
- 条目 1/2/3 → **deferred → v2.2**（门禁 G4 用户裁决，已告知）；条目 9 维持冻结
  （实施顺序注5：17 已落地为 validate_report.py 校验器，模板定稿仍需 3–5 次实审摩擦点，
  不属 v2.1 范围）
- 已知问题（存量，非 G4 引入）：`python -m unittest discover` 汇总跑会因各测试文件
  重复包装 sys.stdout/stderr 在解释器收尾时「lost sys.stderr」崩溃——移除 G4 新文件后
  同样复现；本仓库惯例为逐文件运行（317 用例逐文件全绿）
- 测试合计：317 = G3 的 276 + extract_pdf 25 + conversion_audit 6 + expert_reconcile 10
  （20 文件全绿）+ test_lit_research/test_extract_pdf.py 1 绿

### 发版明细（Step 5，2026-11-11）

- 5.1 版本号：SKILL.md frontmatter `version: 2.1.0`；description 更新为 v2.1 能力口径
  （交付后同轮追加对账 / PDF 全文提取 / 产物完整性门禁 / 扁平结构；触发短语未动）
- 5.2 移交说明：新增 `skills/paper-review/references/v21-migration-notes.md`
  （落地目录树 / 与备忘偏差 10 条逐条含原因 / migrate_layout.py 全参数与 JSON 字段 /
  9 类 pending 人工判定与推荐处置 / 下游校验命令 7 条 / 新增与变更脚本参数一览）；
  SKILL.md 参考文件表收录（孤儿守卫要求）。守卫首跑抓到偏差表内写了备忘备选方案的
  字面路径 `shared/scripts/pdf_extract.py`（不存在于本技能 scripts/，check C 与
  存在性守卫同时 fail）→ 改写为不含路径的表述后两守卫全绿——守卫测试在发版阶段
  仍有效拦截，未放宽任何用例（无 G5）
- CHANGELOG：标题去「进行中」、增「### 发版（Step 5）」节
- 测试：守卫 10+5 绿；全套逐文件 318 绿（317 + lit-research 1）
- 5.3 门禁 G3 用户裁决「执行发版三连」→ commit 28e18c8 + tag v2.1.0；
  push 首发与重试 2 次均失败（Connection reset / 443 不可达）→ 记「待补 push」，
  按技能规则不阻塞，继续 install
- install：`python install.py install paper-review` 覆盖安装成功，list 显示已安装
- 5.4 安装校验：`diff -rq skills/paper-review ~/.claude/skills/paper-review` 无输出；
  安装副本 SKILL.md `version: 2.1.0`；references/v21-migration-notes.md 已随装（12923 B）
- 遗留给用户：重启 Claude Code 后在 paper-reviewer 工作空间执行 `/v21-adopt`；
  网络恢复后 `git push --follow-tags origin main` 补推

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
- 条目 1/2/3 / 条目 3 后加「[v2.1 处置（G4，门禁 G4 用户裁决：全部延后 v2.2）]」注记 /
  可选项处置须留痕，防止 v2.2 开工时误判为已实施（G4）
- 条目 10 / 加「[v2.1 已实施（G4，门禁 G1' 用户裁决：paper-review 内独立新建）]」注记块：
  未走 shared/ 双模式的依据（install.py 不携带 shared 模块，安装副本 import 必失败）、
  合成夹具替代「于小岚 186 页前 10 页切片」建议的原因（仓库内无真稿）、
  PyMuPDF find_tables stdout 推广行需重定向（实测发现，否则污染脚本 JSON stdout）（G4）
- 条目 22 / 加「[v2.1 已实施（G4，门禁 G2' 用户裁决：同轮追加）]」注记块：report 子命令
  行为、chain 幂等替换与 r1/r10 负向环视、INDEX 失败仅告警、三类 exit 1 前置校验（G4）

## 回流缺陷（来自 paper-reviewer /v21-adopt）
（编号 / 现象 / 归属组 / 状态 / 提交号）

## 门禁裁决记录
（门禁号 / 选项 / 用户裁决 / 日期）

- G2 / 条目21 专家意见 docx：「仅文本+先转换」vs「脚本原生支持 docx」/ **用户裁决：脚本原生支持 docx**（实现采用 conversion_audit.py 既有的 zipfile+ElementTree 零依赖模式，不引入 python-docx/pandoc 运行时依赖）/ 2026-11-11
- G1' / 条目10 PDF 全文提取脚本位置：「shared 双模式 --mode excerpt|full-manuscript」vs「paper-review 内独立新建」/ **用户裁决：paper-review 内独立新建**（依据：install.py 无 shared/ 处理逻辑，共享模块不会随技能安装到 ~/.claude/skills/，安装副本上必然 import 失败；lit-research 侧仅在其 extract_pdf.py docstring 加「节选提取，勿用于全文审阅」注记，行为不变）/ 2026-11-11
- G2' / 条目22 交付后专家对账：「同轮追加」vs「强制 --new-run」/ **用户裁决：同轮追加**（对已交付轮补跑 expert_reconcile，产出 `<paper>/reports/rN-综合审阅意见.md`，chain.md 追加「专家对账」行不改原决议，INDEX.md 同步；吻合不重复计、专家新增按面板规则定级、冲突入未决分歧）/ 2026-11-11
- G4 / 条目1/2/3 可选增强（图表审计专趟 / Response Letter 骨架 / severity-precedents.md 判例库）/ **用户裁决：全部延后 v2.2**（账本记 deferred → v2.2，G4 报告明确告知）/ 2026-11-11
- G3 / 发版三连：「执行三连」vs「只 tag+install 不 push」vs「暂不发版」/ **用户裁决：执行发版三连**（测试全绿 318 为前提；push 实际失败×3 → 按规则记待补并继续 install，install 校验通过）/ 2026-11-11
