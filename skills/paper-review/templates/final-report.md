# {name}{-rN-re-review-report | -审阅报告}.md — 最终报告模板（v2.0）

> 用法：Step 6 以本模板为骨架 Write `{run_dir}/final_report.md`（勿用 heredoc），
> 再向用户呈现。`{…}` 为占位符；标注（可选）的节按条件出现。
> v1.x 六节结构保留 + v2.0 新增：稿件类型与准则适配节、数据完整性关切专节、
> 专家意见对账表、转换审计摘要行、源位置三轨列。

---

## 0. 稿件类型与准则适配（v2.0 必含）

- 声明类型：{doctype}（来源：用户声明 / 上轮继承 / 主持人仲裁改判）
- 适用检查：{applied_criteria.required 摘要}
- 类型适配说明（豁免缺席项，每项一句话，不计入 P0/P1/P2 统计）：
  - {如：「参考文献」为 problem-collection 类型豁免要素，本稿未设该节，不作为发现}
- 类型适配异议（如有）：{异议内容 / 仲裁结果：换类型（重绑准则）或维持+理由}

## 0.1 版本谱系摘要（re-review 时必含，引 chain.md）

{上一轮决议/评分 → 本轮决议/评分；发现状态流转统计：resolved X / residual Y / new Z / withdrawn W}

## 1. 审查对象

- 文件：{file_path}（{version}，轮次 {round}）；范围：{全文/§X.Y}
- 模式：{正式七席 / --quick 两席 / --no-fix / --re-review 裁剪席位}
- 转换链路与抽查结果：{pandoc/PDF 提取说明；按 format-notes.md 核对结论}
- **转换审计摘要**：源侧 vs draft 计数 {表 X→Y / 图 X→Y / 公式 X→Y}，
  疑似丢失 {N} 处（详见 conversion_audit.md）；适用时声明
  **「数值核验以编译 PDF 为准」**
- 源稿特征声明（如有）：{docx 高亮等语义不明标记——不计缺陷，提请作者清除}

## 2. 定位坐标说明（启用三轨定位时必含）

工作坐标=draft 行号（编辑后漂移）；源坐标=tex 文件:行 / docx 段落序 / pdf 页码
（源文件被编辑后同样漂移）；结构坐标=章节/表/公式编号+原句引文
（**不随编辑漂移，为兜底锚点**）。反查失败/歧义项源位置显示 `—（回退结构坐标）`。

## 3. 阶段1 合并面板

- 参与席位：{S1–S7 / quick: S1+S6}；配置卡要点：{doctype/豁免清单/分域}
- Editorial Decision：**{Accept/Minor/Major/Reject}**（{盲审/期刊}口径；映射评分 {N}）
- 评分汇总：七席四维均值 {…} + 主持人综合 {…}
- 撤回记录：{N 条（原指控/核验方式/结论），不复活}
- 未决分歧：{各方观点并列，交用户裁决项}
- CRITICAL 逐条专节（S6 标注时铁律）：
  - [CRITICAL-1] {问题} → 编辑裁定：{采纳入 P0 / 驳回+理由}

## 3.1 数据完整性关切（可选专节，触发时必含）

> 定性纪律：合成指纹类指控定性为**「须解释的异常」**而非造假认定；
> 触发材料提交程序（要求作者提供原始数据/日志/生成脚本）。

- 异常清单：{S5 初筛 → S7 复算结果，附复算表}
- 程序状态：{已请求材料 / 待作者解释 / 已解释关闭}

## 3.2 专家意见对账表（--expert-comments 时必含）

| 专家意见ID | 摘要 | 对账结果 | 核实证据 | 处置 |
|-----------|------|----------|----------|------|
| E-1 | … | 吻合 R-2 / 遗漏（核实成立）/ 冲突 / 专家误判 | … | 入 P1（来源=专家）/ 不入清单留痕 |

## 4. 阶段2 去AI审查（多智能体研讨）

- 四技能审计：发现数 {…}；交叉质询：合并 {N} 条、质询改判 {M} 条
- 确认AI问题清单：语言级 {a} 条 / 声称级 {b} 条；重叠打标（阶段1已辖）{c} 条
- 豁免清单（误报拦截留痕）：{N 条，摘 2-3 例}
- 质量评分：**{N}/50**

## 5. 合并发现与修改执行

- 合并统计：P0 {a} / P1 {b} / P2 {c}，总计 {N}（内容 {X} + 语言 {Y}；
  交叉引用 {Z} 不重复计入；撤回跳过 {W}）
- 问题表（三轨并列）：

| # | 严重度 | 工作坐标 | 源位置 | 结构坐标 | 问题 | 处理 |
|---|--------|----------|--------|----------|------|------|
| R-1 | P0 | L142 | main.tex:88 | §3.2 表3.1 | … | 已修改（用户确认）/ 跳过（用户决定） |

- 修改统计：{total 及 by_source、by_severity}；跳过项清单：{…}

## 5.1 R&R 追溯矩阵（re-review 时必含，引 rr_matrix.md）

{上轮逐条状态：resolved/partial/unresolved/reopened + 核验证据摘要；不得橡皮图章}

## 6. 收敛状态

- 轮数：{N}/{rounds_max}；评分轨迹：{convergence.md 表}
- 是否收敛：{是/否}；未收敛时**未解决问题清单**：{逐条}

## 产物路径

{run_dir 下全部文件清单：config.json / RESUME.md / seat_config.md / seat_reports/ /
debate_summary.md / decision_letter.md / revision_roadmap.md / deai_audits/ /
deai_cross.md / deai_confirmed.md / deai_exempt.md / merged_findings.md /
anchor_map.json / conversion_audit.md / bib_lint.md / diff_scope.md（复审）/
rr_matrix.md（复审）/ expert_reconcile.md（如有）/ revision_log.md /
convergence.md / chain.md / final_report.md}
