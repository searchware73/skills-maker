# re-review-protocol.md — 核验式复审协议（v2.0 §九）

> **可替换模板**：paper-review `--re-review` 模式（核验式复审）依据本协议执行。
> 目录约定：v1 源留根目录，v2+ 入 `sources/v<N>/`；`.review/r<N>/` 按轮次路由产物；
> `config.json` 为跨轮状态唯一权威源；`chain.md` 为版本谱系载体。
> 实证来源：q10/q10-1 案（另建目录导致首轮信息物理隔离、手工「本次忽略」清单、
> 无法自动核销上轮 P0/P1）。

---

## 1. 调用与轮次判定

```
/paper-review papers/<name>/draft-v2.md --no-fix --re-review [--response response-v2.md]
```

- 轮次自动判定：文件名 v<N> / config.json 当前轮次；每次运行产物入 `.review/r<N>/`
- 对 v2+ 文件**未带** `--re-review` 时必须 AskUserQuestion 确认意图
  （「核验式复审」vs「从头全量重审」），**不默认**
- `--re-review` = 核验式复审（本协议）；全量重审 = 普通流程 + `--new-run`
  （产物入新 r<N>/，chain.md 照常更新）

## 2. 继承项（零配置，来自 config.json）

| 继承项 | 规则 |
|--------|------|
| doctype 与豁免清单 | 自动继承；本轮不得重新按 full-paper 基准散报 |
| 撤回记录 | **不复活**：上轮撤回的指控本轮不得重新上报（merge_findings.py 自动跳过） |
| 用户裁决结果 | 上轮 adjudications 中用户已拍板的项，本轮直接沿用 |
| Integrity 程序状态 | 「数据完整性关切」程序进展随 chain.md 延续 |
| 去AI豁免清单 | deai_exempt.md 留痕项不重复上报 |

## 3. diff 驱动的面板范围（延续性与成本兼得）

Step 0 后执行：`Bash("python {SKILL_DIR}/scripts/diff_scope.py --old <v(N-1)稿> --new <vN稿> --output {run_dir}/diff_scope.md")`

| 区域 | 审查策略 |
|------|---------|
| **变更区域**（diff hunks） | 全面板扫查：捕捉「改A坏B」与夹带新缺陷 |
| **新增章节/表格**（new_headings） | 视同变更区域全扫 |
| **未变更区域** | 仅回归检查上轮发现是否被间接破坏，**不做全新扫查**（成本关键） |

## 4. R&R 追溯矩阵（复用 academic-paper-reviewer re-review 模式 Schema 11）

上轮 P0/P1/P2 **逐条**核验，写入 `{run_dir}/rr_matrix.md`：

```markdown
| 上轮ID | 严重度 | 问题摘要 | 作者声称（response/diff推断） | 核验席位 | 核验证据 | 结论 |
|--------|--------|----------|------------------------------|----------|----------|------|
| R-1 | P0 | 表3.1 加权和不一致 | 「已按复算表更正」 | S7 | numeric_checks pass | resolved |
| R-3 | P1 | 术语混用 | response 称已统一 | S4 | §2.1 仍有 2 处混用 | partial |
```

- 结论枚举：`resolved / partial / unresolved / reopened（新证据推翻）`
- **数值类强制 S7 复算**（不得凭作者声称通过）
- **铁律：不得橡皮图章「全部已改」**——每条独立核验，核验证据列不得为空；
  无 --response 时作者声称从 diff 推断（推断须注明）

## 5. 席位裁剪

- 默认：**S1 + S2 + S7 + S6** + 与未决项（partial/unresolved）相关的席位
- `--panel full` 恢复七席
- 讨论轮（1c）仅开未决/争议项，不重开已 resolved 项

## 6. chain.md 更新（每轮必做）

每轮结束后按 templates/chain.md 模板追加一节：
版本文件/hash、日期、决议与映射评分、评分轨迹（与上轮对比）、
**发现状态流转表**（上轮# → 本轮状态：resolved/residual/new/withdrawn/reopened）、
用户裁决项记录、Integrity 程序进展。

最终报告头部引用 chain.md 摘要，使单份报告自带版本上下文。

## 7. 产物命名

- 轮报告：`output/<name>-r<N>-re-review-report.md`
  （追溯矩阵 + diff 范围新发现 + 评分对比）；首轮仍为 `<name>-审阅报告.md`
- `r<N>/` 内保留该轮完整中间产物供追溯；chain.md 每轮更新

## 8. 覆盖护栏与不可变性（§九规则2/3）

- Step 0 检测到「根目录出现新源文件且已有 r≥1 轮记录」→ setup_env.py 输出
  `needs_source_confirmation=true`，必须 AskUserQuestion（「这是修订版吗？
  是否移入 sources/v<N>/？」），禁止默默混入或覆盖根目录 v1 源
- 根目录 v1 源与 sources/v<N>/ 自对应轮次开审起**不可变**；再修订产生 v<N+1>

## 9. 存量迁移（旧「另建目录」形态 → 新形态）

`Bash("python {SKILL_DIR}/scripts/migrate_rounds.py --paper-dir papers/q10 --new-dir papers/q10-1 --doctype problem-collection")`
（先 dry-run 看计划，加 `--confirm` 执行；脚本只移动不删除，
腾空后的旧目录经用户确认再手工删除。）
