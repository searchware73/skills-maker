# paper-review 技能加固交接规格（2026-10-13，来自 paper-reviewer 工作空间）

> 来源会话：D:\WS\paper-reviewer（4 篇论文全流程审阅：li-paper-v13 / xue-paper-latex / he-paper / zhang-paper 继承产物）。
> 本文档为**变更规格草稿**，供 skills-maker 会话实施；实施时请遵循本仓库 CLAUDE.md 的约定与 tests/ 校验。
> 证据材料均在 paper-reviewer 工作空间：`output/*-审阅报告.md`、`papers/*/.review/`、
> 加固版工作流脚本 `C:\Users\X1\.claude\projects\D--WS-paper-reviewer-papers-li-paper-v13\...\paper-review-stage2-wf_48fc53d3-828.js`（含 args 防御解析，可直接参考）。

---

## A. 功能增强：源位置三轨定位（anchor 表 + 报告「源位置」列）

### 背景

现行流水线以 `draft.md` 行号为唯一工作坐标；源文件（.tex/.docx/.pdf）定位仅由评审员随手附注，未系统化。
用户需求：审阅意见应能追溯到**源文件**位置，便于作者直接在原稿修改。

### 规格

1. **三轨定位器**（每条发现同时给出）：
   - 工作坐标：`draft.md` 行号（现有，保留）
   - 源坐标：tex = `文件:行号`；docx = 段落序号（python-docx paragraph index）；pdf = `页码`（利用提取时植入的 `%% [PDF p.N]` 标记）
   - 结构坐标：章/节/表/公式编号（跨格式最稳、不随编辑漂移）+ 原句引文（≥15字唯一片段）
2. **新增脚本 `scripts/anchor_map.py`**：
   - 输入：`--draft <draft.md> --source <源文件或源目录> --format tex|docx|pdf`
   - 机制：逐条发现的原句引文在源中做文本反查（tex 直接 grep 行号；docx 按段落序匹配；pdf 按页标记+页内文本匹配）
   - 输出：`{review_dir}/anchor_map.json`（md行 ↔ 源定位 ↔ 结构定位）；反查失败/歧义（全文多处命中）时回退结构坐标并标 `ambiguous:true`
   - 调用时机：Step 0 之后生成空表，阶段4 合并时填充；Step 6 报告渲染时引用
3. **SKILL.md Step 6 最终报告模板**：问题表增加「源位置」列（三轨并列）；报告头部注明各轨含义与漂移特性
4. **LaTeX 加成**：若存在 `.synctex.gz`，源坐标可直接用 synctex 做 pdf页↔tex行 精确映射（可选增强，非必须）
5. **Word 交付加成（可选）**：需要回源交付时优先用 word-revision 的 Track Changes 锚定字符区间，强于任何行号

### 诚实边界（写入 references）

文本反查会失败于：同句多次出现、转换改标点（全半角/断词连字符）、宏展开改变表面文字。
失败回退结构坐标；**结构坐标+引文永远是兜底锚点**。

---

## B. 缺陷修复与注意事项固化（本会话实测踩坑）

### B1. SKILL.md 内嵌阶段2 Workflow 脚本与真实 Workflow API 不符（必修）

现脚本写法（SKILL.md「阶段2 正式模式」代码块）：
- `parallel(ROLES.map(role => agent({name, prompt, tools})))` —— 两处错误：
  1. `parallel()` 需要 **thunk 数组**（`() => Promise`），传 Promise 会并发失控/报错
  2. `agent()` 真实签名为 `agent(promptString, opts?: {label, phase, schema, model, effort, ...})`，**对象式入参无效**；`tools` 不是合法 opts 键
- `args.roles` 直接解构 —— **args 可能被 harness 字符串化**（本会话与前终端各踩一次，报错 `undefined is not an object (evaluating 'ROLES.map')`）

修复模板（已在本会话验证可用）：
```javascript
const A = (typeof args === 'string') ? JSON.parse(args) : (args || {});
const ROLES = A.roles || [/*默认5角色*/];
const reports = await parallel(ROLES.map(role => () =>
  agent(promptString, { label: role, phase: '独立审查' })));
```
并在 SKILL.md 加注：「args 必须按 JSON 对象传递；脚本侧仍须做 typeof 防御」。

### B2. 长文本写入纪律（写入 SKILL.md「失败回退」节）

- 含引号/撇号的长 prose（报告、结构化发现清单）**用 Write 工具**，不用 Bash heredoc（本会话 `Cohen's dz` 撇号与 heredoc 引号冲突致 `unexpected EOF`）
- Bash 的 cwd 跨调用持久化 → 技能脚本与 Edit/Read 一律**绝对路径**（本会话相对路径 Edit 报 File does not exist 一次）
- Git Bash 的 `/tmp` 与 Windows 路径体系不同，跨工具传文件用工作空间内路径（本会话 Read /tmp 失败一次）

### B3. 转换环节注意事项（写入 SKILL.md 或 references/format-notes.md）

- pandoc 转 LaTeX：标准 `abstract` 环境会被吸收为元数据而**从正文消失**（he-paper 未遇、xue-paper 实测），转换后必须核对中英文摘要在位，缺失则从源 tex 补插
- pandoc 转 LaTeX：`table*`/tikz/algorithmic 可能丢失或变形 → 报告须声明「数值核验以编译 PDF 为准」（he-paper 已用此纪律，4/5 评审共识）
- pandoc 转 DOCX：公式/文本框/批注可能破损；转换后抽查（li-paper 实测 `$pos_{a}ll$` 类破损）
- PDF 提取：植入 `%% [PDF p.N]` 页标记作为页级锚点（he-paper 实践，建议固化为标准动作）

### B4. 合并脚本已知噪声（merge_findings.py）

- 源文件中的**叙述性段落**（研讨纪要的「参与角色」「分歧记录」、决议信散文段）若含 P0/P1/P2 字样或表格行会被误解析为发现（li-paper 6 条、xue 首版 7 条噪声）
- 缓解：纪要/决议信的散文段避免 `- ` 项目符号 + 严重度词同现；或在 merge_findings.py 增加来源小节白名单（只解析约定表头）
- 跨来源去重能力弱（duplicates_removed 常为 0）→ SKILL.md Step 6 已要求手工语义归并，建议在 SKILL.md 明示归并规则（同问题多源取最高严重度、保留裁决轨迹、撤回项不得复活）

---

## C. 建议实施顺序

1. B1（脚本 API 修复）——影响每次正式模式运行，优先级最高
2. B2/B3（纪律与转换注意）——纯文档，零风险
3. B4（merge 噪声）——脚本小改+文档
4. A（anchor 表+源位置列）——新功能，含新脚本 anchor_map.py 与 tests
5. 更新 CHANGELOG/版本号，跑 tests/，commit + push，`python install.py` 同步到 ~/.claude/skills
