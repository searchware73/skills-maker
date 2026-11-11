# paper-review v2.1 实施账本

- 当前组：G2
- 更新时间：2026-11-11
- 待补 push：git pull/push 网络失败（Connection reset），离线开工，push 待补

## 组进度

| 组 | 条目 | 状态 | 提交号 | 测试 | 备注 |
|---|---|---|---|---|---|
| G1 | 19,12,13,21,23,24 | done | （待补，见下条 docs 提交） | 15 文件 212 用例全绿 | G1 验证命令通过：夹具 dry-run 输出 5 类待确认项（10 条）、26 moves、5 rewrites、零文件改动、无 .migrate-layout 残留 |
| G2 | 15,14,20,16,17 | doing | | | |
| G3 | 11,18 | todo | | | |
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

## 备忘修订记录
（条目号 / 修订内容 / 原因）

- 条目 5/7/8（§十一）/ 各加「[v2.1 注记：…已被第 12 条取代]」引导块，保留历史原文不删 /
  条目 19 要求清除旧口径且备忘自身需标明被取代，防止后续实施回读旧文（G1）
- 条目 21 / 在二选一选项后追加「[v2.1 已实施（G1，门禁 G2 用户裁决：脚本原生支持 docx）]」记录：
  采用 expert_reconcile.py zipfile+ElementTree 原生解析 word/document.xml（零第三方依赖，
  与 conversion_audit.py 同一模式），未用 pandoc/python-docx；§10.4 标题、SKILL 用法表、脚本实现
  三处口径统一为 `<md|docx>` / 备忘只列了选项，实施后须记录实际选择与实现方式（G1）

## 回流缺陷（来自 paper-reviewer /v21-adopt）
（编号 / 现象 / 归属组 / 状态 / 提交号）

## 门禁裁决记录
（门禁号 / 选项 / 用户裁决 / 日期）

- G2 / 条目21 专家意见 docx：「仅文本+先转换」vs「脚本原生支持 docx」/ **用户裁决：脚本原生支持 docx**（实现采用 conversion_audit.py 既有的 zipfile+ElementTree 零依赖模式，不引入 python-docx/pandoc 运行时依赖）/ 2026-11-11
