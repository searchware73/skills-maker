# paper-review 技能 v2.0 升级交接规格（2026-11-08）

> 定位：**v1.1 → v2.0 的架构级重构交接**。v1.1 交接（docs/handoff-20261013-paper-review-hardening.md）已实施完毕
> （锚点表/源位置列、Workflow 脚本 API 修复、写入纪律、转换注意、merge 噪声缓解），本文档不重复其内容，仅在其基础上重构流水线。
> 证据基础：本规格所有设计决策来自 5 篇真实审阅的复盘——li-paper-v13（学位论文/Minor）、xue-paper-latex（LaTeX/Major）、
> he-paper（跨终端续跑/Major）、zhang-paper 与 q10（前终端产物继承）、仿真稿件-20261105（期刊稿/Major 附 Reject 触发+数据完整性专节）。
> 用户已确认的三项架构决策：①阶段2+阶段3 合并为单面板（复盘分析方案1）；②去AI审查移至同行评审之后；③去AI审查改为多智能体研讨模式。
> 后续补充决策：④doctype 准则绑定（§八）、⑤同目录多版本与复审协议（§九）、⑥–⑪ 工具化与对账机制（§十）；v2.1 backlog 见§十一。

---

## 一、v2.0 流水线总览

```
Step 0  环境初始化 + 格式转换（v1.1 转换注意）+ anchor_map 生成（v1.1）
        + --doctype 稿件类型声明（见§八；未声明时 AskUserQuestion 确认，禁止臆测）
阶段1   合并同行评审面板（原阶段2+阶段3）
        1a 领域分析与席位配置（7席，含数值审计专席）
        1b 七席独立审查（并行，互盲）
        1c 聚焦讨论与撤回轮（主持人；假阳性防火墙）
        1d 编辑综合（共识矩阵/仲裁/Decision Letter/Revision Roadmap+验收标准）
阶段2   去AI审查（多智能体研讨模式，审计-only 默认）
        2a 四技能代理独立审计（stop-slop / academic-humanizer / humanize-writing / humanizer-zh）
        2b 交叉质询轮（模式堆叠合并、豁免裁定）
        2c 主持人终裁（确认AI问题清单 + 豁免清单附理由；与阶段1重叠项打标签）
阶段3   发现合并与最终报告（两份权威清单拼接+重叠交叉引用；源位置三轨列）
阶段4/5 修改执行/收敛循环（仅 fix 模式；--no-fix 跳过，纪律不变）
```

顺序调整理由（用户决策）：内容审查（数值/逻辑/证据）决定稿件生死，优先执行；去AI属语言层，
后置不影响任何下游判断，且去AI主持人可拿阶段1路线图做重叠打标（见 2c）。

---

## 二、阶段1：合并同行评审面板（核心重构）

### 2.1 为什么合并（复盘数据）

- 角色 4/5 同构（A1↔R1、A2↔R2、A4↔DA、A5↔EIC），P0 互命中率近 100%（li-paper 阶段2 的 5 条 P0 全部被阶段3 再命中）
- 跨来源重复率 25–53%/篇，下游每次被迫手工语义归并（83→33、70→33、49→32）
- 但两阶段各有独占高价值产出，**合并时必须保留两侧机制**：
  - 原阶段2 独占：辩论-撤回机制（5 篇拦下 3 次错误指控：孙昱东、SynthDigits、基线计数 5→6）；写作编辑席的术语/符号细粒度发现
  - 原阶段3 独占：编辑决议信+Decision 映射+验收标准；跨学科视角席（伦理/完整性/部署可行性）；联网文献核实

### 2.2 七席配置（panel-roles.md 替换 agent-roles.md）

| 席 | 来源 | 职责边界（互不重叠） |
|---|---|---|
| S1 EIC/统筹 | 原A5+原EIC | 选题/贡献清晰度/结构闭环/规范完整性/决议档位建议；不深入公式与统计 |
| S2 方法论 | 原A1+原R1 | 研究设计/统计有效性/可复现性/实验公平性；**不做**逐表复算（交 S7） |
| S3 领域 | 原A2+原R2 | 文献谱系/溯源核实（可联网）/术语共识/增量定位 |
| S4 写作编辑 | 原A3 | 句式/图表体例/标点/誊录级数字串核对/术语统一；**唯一**承接原阶段2独占产出 |
| S5 跨学科视角 | 原R3 | 部署可行性/伦理与人在回路/动机-验证断层/相邻领域对话/数据完整性疑点初筛 |
| S6 魔鬼代言人 | 原A4+原DA | 最强反论证/选择性报告/过度声明/CRITICAL 标注；专属报告格式保留 |
| **S7 数值审计（新专席）** | 制度化原主持人复算+R1/DA 自发复算 | **逐数复算**：加权恒等式/跨表一致性/Monte-Carlo 核对/对照 PDF 原表（PyMuPDF 抽表或渲染页图）；产出「复算表」附于每条数值类发现；不做定性批评 |

S7 设立依据：xue-paper 表3.1（69.11 vs 66.54）、仿真稿件 Ex=77.6（vs 72.9）两案均为多路独立复算交叉证实后才升级为决议级事实；
he-paper 主持人复算亦为共识依据。复算值得专职而非依附于方法论席。

### 2.3 阶段1 内部流程

- **1b 独立审查**：七席并行、互盲；IRON RULE 保留（只读/独立/批评到行号/优缺点平衡/评分有据）；
  席位配置卡由 1a 领域分析生成（沿用 ars-reviewer field_analyst 模式，含共同豁免清单：学位文体/期刊模板/转换伪影/平行引用句式）
- **1c 讨论与撤回轮**（原阶段2 机制保留并强化）：
  - 主持人提取争议点（结论冲突/严重度分歧），P0 优先，相关席位各 200 字回应 ≤2-3 轮
  - **撤回规则制度化**（he-paper/SynthDigits 教训）：涉及外部事实的指控（文献内容/数据集规模/他文结论）裁决前必须完成文献级核验（联网或原文对照）；核验不成立即撤回并留「撤回记录」防复活
  - **数值类争议强制交 S7 复算裁定**，主持人不自行裁数
- **1d 编辑综合**：共识矩阵（≥3席）/分歧仲裁记录/Decision Letter（Accept/Minor/Major/Reject + 盲审或期刊口径判断）/
  Revision Roadmap（P0/P1/P2，位置/问题/建议/来源席/工作量/验收标准）/DA-CRITICAL 逐条专节铁律保留

### 2.4 决议与评分

- Decision 映射评分保留（Accept=9/Minor=8/Major=6/Reject=4）
- 评分汇总取七席四维均值 + 主持人综合；严重度分歧仲裁记录保留（v1.x 的「未决分歧交用户裁决」机制保留）

---

## 三、阶段2：去AI审查多智能体研讨模式

### 3.1 现状问题（v1.x）

- 4 技能在主上下文串行执行：每技能目录全文（stop-slop/academic-humanizer/humanize-writing/humanizer-zh 各数十 KB）加载进主对话，5 篇累计主上下文消耗巨大
- 4 技能模式目录重叠约 80%（同一条 AI 痕迹常被 2-3 技能重复标记），靠 deai_log 手工避免重复计数
- 无交叉质询：豁免判断（学位文体/期刊模板/转换伪影）靠调用参数口头传达，各技能执行尺度不一

### 3.2 v2.0 设计

- **2a 四技能代理并行独立审计**（audit-only）：每代理加载自己的技能目录+审查清单，产出「模式→位置→证据→建议初判严重度」清单；
  共同豁免清单由 1a 配置卡统一下发（不再靠调用参数口头传达）
- **2b 交叉质询轮（1 轮）**：四清单合并为「技能×发现」矩阵；按 humanize-writing 的模式堆叠规则合并同短语多标记；
  对每条候选发现，其余三代理可质询（是否豁免范畴/是否转换伪影/是否内容问题误标为AI痕迹）；被质询方须引原文回应
- **2c 主持人终裁**：产出两份清单——①**确认AI问题清单**（位置/问题/建议/支持技能数/严重度，语言级默认 P2，声称级可升 P1）；
  ②**豁免清单**（被排除候选+排除理由，如「中文破折号为标准标点」「算法关键字粗体为 LaTeX 排版」——xue/li 两篇均有此类误报拦截记录）；
  并接收阶段1路线图做**重叠打标**：与阶段1 P0/P1 同源的声称问题（如摘要过度声明）标「内容问题，阶段1 已辖」，不重复计入去AI清单
- 质量评分（/50）保留，由主持人按终裁后清单给出

### 3.3 收益

- 主上下文零技能目录加载（全部下沉子代理）
- 豁免尺度统一、误报有拦截记录（与 1c 撤回机制同构，构成第二道假阳性防火墙）
- 四技能并行，墙钟时间从串行 4 次降为 1 次+质询轮

---

## 四、阶段3：合并与报告

- 输入变为**两份权威清单**：阶段1 Revision Roadmap（内容）+ 阶段2 确认AI问题清单（语言），取代 v1.x 三来源自由文本解析
- merge_findings.py 改造：接收两个结构化输入（稳定 ID：R-#/S-#/D-#），仅对重叠打标项做交叉引用，不再做跨源模糊去重
  （v1.x 的叙述段误解析噪声问题随之消失，B4 条款退役）
- 手工语义归并规则写入 SKILL.md（本复盘固化）：同问题多源取最高严重度；保留裁决轨迹；**撤回项不得复活**；去AI与内容重叠项以阶段1为准
- 最终报告模板保留 v1.x 六节结构 + 源位置三轨列（v1.1 A）+「数据完整性关切」可选专节（仿真稿件案确立：合成指纹类指控定性为
  「须解释的异常」而非造假认定，触发材料提交程序，表述模板见仿真稿件决议包）

---

## 五、可靠性与续跑机制（v1.1 之后新增教训）

1. **RESUME.md 制度化**：每阶段边界写 `.review/RESUME.md`（已完成/暂停点/恢复命令/环境备忘），he-paper 跨终端续跑已验证其价值；
   v2.0 将其列为技能强制产物
2. **代理级 API 故障重试**：仿真稿件阶段3 综合代理曾遇 400 Arrearage（账户欠费）中断；因全部阶段产物落盘，恢复后单代理重试即续跑。
   SKILL.md「失败回退」节增补：子代理 API 错误 ≠ 阶段失败，重试该代理（≤3 次），不得重跑整阶段
3. **密码保护 PDF 回退**：Read 工具拒读密码 PDF（he-paper 案）；回退链：PyMuPDF 抽文本 → 抽表（find_tables）→ 渲染页为 PNG 后 Read 图像（图1.3 核验即用此法）；写入格式注意（v1.1 B3 扩展）
4. **Word 高亮观察**：docx 源高亮（pandoc 转 `{.mark}`）语义不明时不计缺陷，但须在报告「源稿特征声明」节提请作者清除（仿真稿件案）

---

## 六、成本模型对照

| | v1.x | v2.0 |
|---|---|---|
| 内容审查代理 | 10（5+5） | 7（含 S7） |
| 主持/综合代理 | 3（讨论+纪要+综合） | 2（讨论撤回+综合） |
| 去AI | 4 次主上下文技能调用 | 5 子代理（4 审计+1 终裁） |
| 主上下文技能目录加载 | 4 份全文 | 0 |
| 下游手工归并 | 每篇 30-50 条跨源去重 | 仅重叠打标核对 |
| 预计墙钟 | 阶段2 35-40min + 阶段3 30-50min 串行 | 阶段1 ≈40min + 阶段2 ≈15min 串行（内部均并行） |

---

## 七、实施清单（skills-maker 会话用）

1. SKILL.md 重写：阶段重编号（1 面板/2 去AI/3 合并报告/4-5 不变）；--quick 映射为「S1+S6 两席+跳过讨论轮」；--focus 取值更新（panel/de-ai）
2. references/：agent-roles.md → panel-roles.md（七席含 S7 章程）；discussion-protocol.md 增「撤回规则」「数值争议交 S7」条款；
   新增 deai-discussion-protocol.md（2a-2c 流程+模式堆叠合并规则+豁免清单模板）；review-checklist.md 按七席重切
3. scripts/：merge_findings.py 改双权威清单输入（保留旧参数兼容一个版本）；新增 resume.py（RESUME.md 读写与校验）
4. templates/：最终报告模板加「数据完整性关切」可选专节与源位置列说明
5. tests/：双清单合并用例；RESUME 续跑用例；S7 复算表格式用例
6. CHANGELOG：2.0（架构重构：面板合并/去AI后置多智能体化/数值审计专席/续跑制度化）
7. 兼容：v1.x 的 .review/ 旧产物（agent_reports/、peer_reports.md）在新版只读兼容，不迁移

> 交接方式同 v1.1：在 skills-maker 工作空间开新会话，首句「读 docs/handoff-20261108-paper-review-v2.md，按规格实施 v2.0 并更新
> SKILL.md/references/scripts/tests，跑校验后 commit + push + install」。

---

## 八、稿件类型声明与准则绑定（v2.0 补充决策④，用户 2026-11-08 提出）

### 8.1 问题（q10 案实证）

q10 原稿为**问题征集/立项申报体例**（各题「问题摘要」、立项口吻、无实验），但流水线按完整论文基准审：
「零参考文献」被多席重复报为 P0 阻断项；q10-1 复审时为阻止重复报告，只能在报告头**手工声明「本次忽略」清单**
（题文不符/零参考文献/无源断言均不计入）——人工忽略清单正是类型缺失的症状。同类风险：proposal、extended abstract、
技术报告、章节草稿、综述提纲等非完整论文稿件，都会触发「缺摘要/缺参考文献/缺数据支撑」的批量伪 P0。

### 8.2 设计：--doctype 声明 + 准则绑定表

1. **Step 0 新增参数 `--doctype`**，枚举：`full-paper | thesis | proposal | problem-collection | extended-abstract |
   technical-report | section-draft | review | other:<描述>`。未提供时技能**必须** AskUserQuestion 确认（可附自动检测线索：
   无摘要/无参考文献/无实验节 → 提示疑似非完整论文），禁止按默认 full-paper 臆测跑完全流程。
2. **新增 `references/doctype-criteria.md`**，每类型定义三组规则：
   - **必备结构要素**：缺失即发现，严重度按类型表（如 thesis 缺致谢=P2 程序项；full-paper 缺参考文献=P0；
     problem-collection 缺参考文献=**不报**，缺「定量断言出处」=P1）
   - **豁免结构要素**：缺失一律不作为发现上报；报告头部「类型适配说明」一节每缺席项一句话注明（不计入 P0/P1/P2 统计）
   - **检查语义置换**（关键：不是放松，而是换成该类型正确的检查）：
     proposal/problem-collection 型：「数据支撑证明」置换为「声称↔依据」（ preliminary data / 权威出处（白皮书·标准·官方口径）/
     可行性论证，参照 academic-humanizer Layer 6 的 claim↔feasibility 纪律）；「可复现性」「统计审查」不适用；
     引用检查置换为「支柱性定量断言须注明数据来源，叙述性背景可无引用」
3. **结构完整性检查垄断**：结构要素核查仅由 **S1（EIC）** 执行并出具类型适配判定；其余各席遇结构缺失引用 S1 判定、
   不得重复上报（与 S7 数值垄断同构）。此条直接消除「五席各报一次缺摘要」的重复源。
4. **类型适配异议机制**：任席发现声明类型与内容实质不符的证据（如声明 full-paper 却无实验无数据，或声明 proposal
   却含完整实验节），提**单条**「类型适配异议」争议点；主持人仲裁：换类型（重绑准则、补跑受影响检查）或维持+报告注明。
   防噪声与防漏检兼顾，不允许各席自行按另一套基准散报。
5. **报告与复审继承**：最终报告头部新增「稿件类型与准则适配」节（声明类型/适用与豁免的检查类别/豁免缺席项说明）；
   re-review 模式自动继承上一轮的 doctype 与豁免清单（q10-1 的手工「本次忽略」制度化为自动继承）。
6. **合规清单组**（每类型绑定，S1 核查、缺项按类型定级）：保密审查/地名脱敏声明（军事·边防类，仿真稿件 P0-9 案）、
   人类被试/数据伦理声明（医疗·用户数据类）、AI 使用披露（he-paper 正例：5 项用途逐一披露获正面认定）、
   数据/代码可得性声明。类型未要求的合规项缺失不报。

### 8.3 q10 案在 v2.0 下的预期行为

声明 `--doctype problem-collection` → 零参考文献不入报告（头部一句类型说明）；「定量指标无源」以置换后的
「定量断言出处」检查报 P1；「题文不符/缺遴选方法」作为内容发现正常保留（类型绑定只豁免结构类检查，不豁免内容质量）。
复审轮自动继承，无需手工忽略清单。

### 8.4 §七实施清单增补

- setup_env.py 增 `--doctype` 参数、写入 review 配置 json、缺失时触发确认流程
- 新增 references/doctype-criteria.md（首版覆盖 8 类型；q10 problem-collection 与仿真稿件 full-paper 为对照示例）
- panel-roles.md S1 职责增「结构检查垄断+类型适配判定」；discussion-protocol.md 增「类型适配异议」争议类型与仲裁规则
- 报告模板增「稿件类型与准则适配」节；re-review 协议增类型与豁免清单继承
- tests/ 增 doctype 绑定用例：同一稿件在 full-paper 与 problem-collection 两类型下的报告差异断言（豁免项不出现/检查置换生效）

---

## 九、同目录多版本与复审协议（v2.0 补充决策⑤，用户 2026-11-08 提出）

### 9.1 问题（q10/q10-1 案实证）

q10 按意见修改后产生新版本，用户为新版本**另建目录** papers/q10-1/：操作多一步、版本间延续性不可见、
首轮审阅信息（发现清单/裁决/撤回记录/豁免清单）与第二轮物理隔离——q10-1 复审不得不手工声明「本次忽略」清单，
且无法自动对照首轮 P0/P1 逐条核销。多轮 R&R（期刊复审、答辩修改稿）场景下该问题会持续放大。

### 9.2 目录约定：v1 源留根目录（多数case零仪式），v2+ 入 sources/v<N>/（用户 2026-11-08 二次修订）

```
papers/<name>/
├── paper.docx / 主tex+chapters/ …   ← v1 源原位存放（单文件或多文件 LaTeX 工程整包；与现状一致）
├── draft.md                    ← v1 工作副本（draft-v1 别名，setup_env 自动解析）
├── draft-v2.md …               ← 各修订版工作副本（所有 draft-vN 均在根，便于查找）
├── response-v2.md …            ← 随 v<N> 提交的作者回复信（可选输入）
├── sources/v2/ …               ← 仅当复审出现时创建：v<N≥2> 作者回包原样存放（保留原名与内部结构）
└── .review/
    ├── config.json    ← doctype、source_root 映射、轮次↔版本映射、豁免清单、撤回记录、裁决记录（跨轮继承源）
    ├── chain.md       ← 版本谱系与发现状态流转（见 9.5）
    ├── r1/ … rN/      ← 每次审阅运行的全部产物（r<N>=第N次审阅运行）
    └── RESUME.md
```

**规则**：
1. **源根映射**：config.json 按版本记录 `source_root`（v1="."，vN="sources/vN/"）；格式转换（pandoc 以主文件目录为基准）、
   anchor_map、diff_scope、S7 对照原表均据此取路径。多文件 LaTeX 工程相对路径包内自洽，故 v2+ 整包置于任何目录均可转换
2. **覆盖护栏**：Step 0 检测到「根目录出现新源文件且已有 r≥1 轮记录」时，必须 AskUserQuestion 确认
   （「这是修订版吗？是否移入 sources/v<N>/？」），禁止默默混入或覆盖根目录 v1 源
3. **不可变性**：根目录 v1 源与 sources/v<N>/ 自对应轮次开审起不可变（防复审中途污染）；再修订产生 v<N+1>
4. **命名序列语义**：v<N> = 第 N 个收到的稿件版本（作者修订即递增，同一版本重复审查不递增）；
   r<N> = 第 N 次审阅运行（每次 /paper-review 执行递增，含对同一版本的全量重审）；config.json 记录 r↔v 映射
5. **存量兼容**：既有五篇（li/xue/he/仿真/zhang）已为「v1 在根」形态，零迁移；无 draft-v<N> 时 draft.md 视为 v1、
   既有 .review/ 扁平产物视为 r1/（兼容读取，不强制迁移）
6. config.json 为跨轮状态的**唯一权威源**：doctype（§八继承）、source_root、豁免清单、撤回记录、用户裁决项及其结果

### 9.3 调用方式

```
/paper-review papers/<name>/draft-v2.md --no-fix --re-review [--response response-letter.md]
```

- 轮次自动判定：文件名 v<N> / config.json 当前轮次；对 v2+ 文件未带 --re-review 时 AskUserQuestion 确认意图
  （「核验式复审」vs「从头全量重审」），不默认
- --re-review 语义 = 核验式复审（下方 9.4）；全量重审 = 普通流程但产物入 r<N>/ 并更新 chain.md

### 9.4 核验式复审的面板范围（diff 驱动，延续性与成本兼得）

1. **R&R 追溯矩阵**（复用 ars-reviewer re-review 模式 Schema 11）：上轮 P0/P1/P2 逐条 × 作者声称（response-letter
   或 diff 推断）× 席位核验（数值类强制 S7 复算）× 结论（已解决/部分解决/未解决/新证据推翻）；铁律：不得橡皮图章
   「全部已改」，每条独立核验
2. **diff 范围全扫**：v(N-1)→vN 变更区域（markdown/tex diff 定位）接受全面板扫查，捕捉「改A坏B」与夹带新缺陷
3. **未变更区域**：仅回归检查上轮发现是否被间接破坏，不做全新扫查（成本关键）
4. **新增章节/表格**：视同变更区域全扫
5. **席位裁剪**：默认 S1+S2+S7+S6 + 与未决项相关的席位（--panel full 恢复七席）；讨论轮仅开未决/争议项
6. **继承项**（零配置）：doctype 与豁免清单、撤回记录（不复活）、上轮用户裁决结果、Integrity 程序状态

### 9.5 chain.md（版本谱系，延续性的载体）

每轮一节：版本文件/hash、日期、决议与映射评分、评分轨迹（与上轮对比）、发现状态流转表
（上轮# → 本轮状态：resolved/residual/new/withdrawn/reopened）、用户裁决项记录、Integrity 程序进展。
最终报告头部引用 chain.md 摘要，使单份报告自带版本上下文。

### 9.6 产物命名

- 轮报告：output/<name>-r<N>-re-review-report.md（追溯矩阵 + diff 范围新发现 + 评分对比）；首轮仍为 <name>-审阅报告.md
- chain.md 每轮更新；r<N>/ 内保留该轮完整中间产物供追溯

### 9.7 存量迁移（q10 案）

提供 scripts/migrate_rounds.py 或手工清单：papers/q10-1/paper.docx → papers/q10/sources/v2/paper.docx；
q10-1/draft.md → papers/q10/draft-v2.md；q10/.review/* → q10/.review/r1/；q10-1/.review/* → r2/；回填 config.json
（doctype=problem-collection 依§八、source_root={"v1":".","v2":"sources/v2/"}）与 chain.md（r1 决议/发现清单、
r2 忽略清单转为豁免记录）；删除 q10-1 目录前须用户确认。

### 9.8 §七实施清单增补

- setup_env.py 支持版本文件名解析与 r<N>/ 产物路由；config.json schema（doctype/轮次/豁免/撤回/裁决）
- 新增 scripts/diff_scope.py（v(N-1)→vN 变更区域定位，输出行范围清单供面板分域）
- references/re-review-protocol.md（9.4 流程+追溯矩阵模板+继承规则）；chain.md 模板入 templates/
- re-review 模式与 §八 doctype 继承、§五 RESUME 机制联调测试；migrate_rounds.py + q10 迁移用例

---

## 十、v2.0 补充决策⑥–⑪：工具化与对账机制（用户 2026-11-08 确认）

### 10.1 ⑥ 转换审计前置（scripts/conversion_audit.py）

- 问题：pandoc 对 table*/tikz/algorithmic 的丢失在评审中途才被发现（xue 案），「PDF 为数值基准」纪律系事后补救
- 设计：Step 0 转换后运行：源侧计数（docx 用 python-docx 数表/图；tex 数 \begin{table}/\begin{figure}/algorithm 环境；
  pdf 记页数）vs draft.md 计数（markdown 表格/图引用/公式块）；产出 `.review/conversion_audit.md`
  （丢失清单+源页码/章节指针+建议核验基准），注入 1a 配置卡共同豁免与各席 prompt
- 验收：xue 案为测试夹具（丢失清单应与人工核查一致）

### 10.2 ⑦ 数值检查库（scripts/numeric_checks/）

- 将 S7 复算沉淀为可复用检查器：`weighted_identity`（混合口径加权自洽）、`table_sums`（行列和/勾稽）、
  `abstract_numbers`（摘要数字↔正文表格交叉，含「摘要零数字」警示）、`percent_basis`（百分比 vs 百分点/分母口径）
- S7 章程修改：先跑库产出机器核查表，再手工扩展论文特有不变量（如 Monte-Carlo 复现）；
  每条数值类发现必须附库输出或手写复算片段
- 夹具：xue 表3.1（69.11 vs 66.54）、仿真稿表6-9（Ex=77.6 vs 72.9）、li 表3.4/3.5（91.33 vs 83.28）

### 10.3 ⑧ 引文 lint 脚本化（scripts/bib_lint.py）

- 确定性检查：GB/T 7714 姓名序启发式、`[C]//` 空会议名、arXiv vs 正式发表（CrossRef 联网可选、离线回退=年份/venue 字段完整性）、
  键名-年份相符、双语著录配对、标点（双句点/逗号后空格/页码空格）
- 产出逐条判定表入 r<N>/bib_lint.md；**S3 席职责改为仅语义核对**（引用描述与原文是否相符，联网核实），不再手工查格式
- 证据：li/xue/he 三篇各约 20 处格式问题，全部为可脚本化重复劳动

### 10.4 ⑨ 专家意见对账（--expert-comments <md|docx>）

- 时机：阶段1 面板完成后启动对账代理：专家意见逐条 × 面板发现 → 三态（吻合/面板遗漏/冲突）；
  **遗漏项必须读原文核实后才可入报告**（防误收专家误判——he-paper 核验中「多域客户端」全文不存在即为反例）
- 报告增「专家意见对账表」节；核实成立的遗漏项按严重度规则入 P0/P1/P2 并标来源=专家
- 证据：he-paper 用户 8 条意见中 4 条为面板遗漏（图1.3 图文对齐、算法3.1 浮动漂移、异步/异构因子分离、概念定义节）

### 10.5 ⑩ 英文摘要专检（去AI章程固定项）

- 2a 审计代理增固定检查项（不新增席位）：机译痕迹（悬垂/句式杂糅，如「Aiming The…」）、中英摘要术语一致性
  （标题关键词↔Key words）、全半角标点、Tier1 AI 词汇
- 证据：仿真稿「Aiming The」、xue「leverages/paradigms」、li 英文摘要 Tier1 词——三篇命中，此前均靠顺带发现

### 10.6 ⑪ Step 0 成本与模式预估

- Step 0 输出本次运行预估：席位数/代理数、预计墙钟、token 量级（引用历史按阶段记账均值），并按 doctype 与稿件行数
  给出 --quick vs 正式模式建议；用户可当场改判
- 证据：CLAUDE.md 成本提示为静态文字，而单篇实际开销差异大（892 行期刊稿 vs 4507 行学位论文）

### 10.7 实施清单增补

- 新增脚本：conversion_audit.py、numeric_checks/（四检查器）、bib_lint.py；setup_env.py 增 --expert-comments 参数与对账代理模板；
  Step 0 预估输出
- panel-roles.md：S7 章程引用数值检查库；S3 章程拆分为「格式→脚本 / 语义→席」
- deai-discussion-protocol.md 增英文摘要专检项；报告模板增「专家意见对账表」可选节与转换审计摘要行
- tests/：conversion_audit 用 xue 夹具；numeric_checks 三夹具；bib_lint 用 li/xue 夹具；
  专家对账用 he-paper 8 条意见夹具（含「多域客户端」不存在回归用例，验证「遗漏须核实」生效）

---

## 十一、v2.1 backlog（记录在案，v2.0 不实施）

1. **图表审计专趟**：逐图渲染 PDF 核轴标签/图例/图题与正文对位（he 图1.3、li 图 alt 误标、xue 图4.2 缺轴标签）；
   v2.0 先作为 S4/S7 清单条目存在，不建独立工具
2. **Response Letter 骨架**：从路线图自动生成 R→A→C 三栏骨架，随最终报告产出（仿真稿决议曾手写 Instructions，应固化）
3. **严重度判例库** references/severity-precedents.md：跨篇累积边界裁决（he DPA trade-off P2→P1、姓名倒置 P0/P1 之争、
   表8 定性措辞仲裁），新仲裁先查判例
4. **一篇一会话纪律 + 阶段记账**：正式模式单篇单会话；RESUME.md/config 记各阶段墙钟与 token（亦为 10.6 预估的数据源）
5. **跨篇 INDEX**：Step 6 向 papers/INDEX.md 追加一行状态（稿件名/doctype/当前轮次/决议/日期/报告路径），
   新会话一眼全貌（现状须 ls + 逐篇读 RESUME）；属工作空间级约定，随 v2.0 落地时与 CLAUDE.md 更新一并讨论
   > **[v2.1 注记：路径口径已被第 12/19 条取代]** `papers/INDEX.md` → 工程根 `INDEX.md`（一行一篇，
   > 路径相对论文目录）；文件不存在时由 setup_env.py 创建骨架、Step 6 追加行，而非仅追加。
6. **prev_findings 脚本化抽取**（r5 回归发现①）：复审基线 prev_findings.md 不得手工摘要回填——r5 中压缩表述
   （「全文统一」）与 r4 原文口径（「5 处必改+2 处请作者裁决」）偏差，差点导致 PR-3 误判 partial（被 1c 三轮仲裁救回）。
   改为脚本从 r(N-1) 报告原表逐行抽取（保留建议列全文），主持人/席位引用不得转述缩水
7. **覆盖护栏 v1 跟踪修正**（r5 回归发现②）：source_root="." 时根目录 v1 源文件未被登记为已跟踪，
   导致 r5 对根目录 paper.docx（v1 原件，mtime 早于任何新拷贝）误报 needs_source_confirmation。
   setup_env.py 的 untracked 判定应排除「v1 source_root 内、mtime 早于 r1 开跑时间或哈希匹配 r1 转换输入」的文件
   > **[v2.1 注记：口径已被第 12/19 条扩展]** `source_root` 取值扩展为 `"." | "v1" | "vN"` 两种 v1 形态
   > （根单文件 vs v1/ 目录，并存报错）；护栏判定同步：rounds.r1 记 `started_at`，根目录源文件
   > mtime 早于 r1 开跑时间或已登记为 versions.v1.source_file 时不报 untracked。
8. **版本草稿与报告归档目录约定**（用户 2026-11-08 提出）：
   - 草稿：draft-vN.md（N≥2）改放各自源目录 `sources/vN/`（与源同目录便于对照查找）；draft.md（v1）仍留根目录；
     config.json versions 映射、diff_scope、命令示例、CLAUDE.md 目录树同步改
   - 报告：单轮稿件维持 `output/<name>-审阅报告.md` 平铺（多数case零仪式）；**出现复审（r≥2）时**建
     `output/<name>/` 子目录，各轮报告归集为 `<name>-r1-审阅报告.md`、`<name>-rN-re-review-report.md`…，
     chain.md 同步记录各轮报告路径（移动后旧路径留转发注记）；备选方案「所有稿件一律 per-paper 子目录」记录在案，
     推荐沿用§九非对称原则（不为多数单轮稿件增加复杂性）
   > **[v2.1 注记：本条目录约定已被第 12 条扁平化结构取代，实施以第 12 条为准]**
   > draft 入 `<paper>/draft/`（draft.md / draft-vN.md）、版本源入 `<paper>/vN/`（取消 sources/）、
   > 回复信入 `<paper>/response/`、交付报告入 `<paper>/reports/`（r1-审阅报告.md / rN-复审报告.md，
   > 取代 output/ 平铺与 per-paper 子目录两案）；图片产物落 `draft/figures/`（第 19/23 条）。
9. **审查报告格式统一化**（用户 2026-11-08 提出）：templates/final-report.md 暂冻结；再执行 3–5 次审阅后
   汇总模板摩擦点（可选节空载率、三轨列在无 anchor 时的呈现、复审/首审差异节、去AI节与合并节的信息重复度），
   修订为定稿格式并回填本交接文档；期间各轮报告允许在模板外加「轮次特注」但不得改模板节名与列名
10. **PDF 提取脚本缺失补齐**（2026-11-10 用户提出，于小岚稿实测）：`references/format-notes.md` 第 4 条声明
   「extract_pdf.py 已固化」，但 `scripts/` 目录中并无此文件，仅 anchor_map.py / conversion_audit.py 注释引用；
   实际每次 PDF 审阅都要临时重写 PyMuPDF 脚本，且转换审计的 source_counts（tables/figures/equations）全为 null。
   v2.1 应新增 `scripts/extract_pdf.py` 并纳入 SKILL Step 0.3/0.4：
   - 逐页植入 `%% [PDF p.N]` 页标记（anchor_map 三轨定位的唯一切分依据）
   - 无书签 PDF 按字号重建标题（章/节/小节），合并被 PDF 换行拆开的标题
   - 过滤页眉页脚（如「XX大学博士学位论文+页码」）与目录点引线
   - 图像按尺寸过滤导出（剔除表格线、字形碎片、背景条），生成图占位符并统计图/表题
   - 参考文献按 `[N]` 切分为 refs.txt，供 bib_lint 直接消费
   - 回填 conversion_audit 的源侧计数，表格线性化/公式文本化列入共同豁免
   同时修正 format-notes.md 的脚本路径与调用示例，避免下次再临时造轮子。
   **⚠ 名称撞车提醒（2026-11-11 复核发现）**：`skills/lit-research/scripts/extract_pdf.py` **已存在**，
   但它是文献卡场景的**节选提取器**（前 8 页 + 后 3 页、每页 ≤3000 字符、可从 URL 下载、
   产物名 `NNN_src_*.pdf` / `NNN_extract_*.txt`），**不能直接用于全文稿件审阅**（学位论文 186 页会被截断）。
   format-notes.md 的「已固化」很可能就是把它误当成本技能脚本。v2.1 二选一：
   - 提升为 `shared/scripts/pdf_extract.py`，加 `--mode excerpt|full-manuscript` 双模式（excerpt 保持
     lit-research 现行为不变，full-manuscript 实现上述全部要求），两技能各自调用；
   - 或在 `skills/paper-review/scripts/` 下新建独立 `extract_pdf.py`（full-manuscript 专用），
     并在 lit-research 那份的 docstring 注明「节选提取，勿用于全文审阅」。
   无论哪种，`tests/test_lit_research/test_extract_pdf.py`（页标记用例）须继续通过，
   并为 full-manuscript 模式新增夹具（建议用于小岚 186 页 PDF 的前 10 页切片）。
11. **Workflow 席位被用户消息劫持导致漏派**（2026-11-10 用户提出，连续两篇实测）：
   现象：全昌寿稿 S4、于小岚稿 S3 在阶段1 七席并行时未产出报告，但 Workflow 统计为
   `agents_done=9, agents_error=0`，无自动重试；1c 主持人只能标注缺口或按六席计算。
   根因（已核对 workflow journal 与 agent transcript）：
   - Workflow harness 会把**启动该 Workflow 时的最新用户消息**作为「triggering user request」
     注入每个子代理的首条消息，并声明「this request wins」高于脚本计算的席位任务；
   - 两次启动时最新消息分别是无关的「临时文件命令是否自动执行」与「PDF 转换为何要写 Python」，
     被劫持的 S4/S3 转去回答该问题、未写席位报告；S4 的输出还因含 permissions/settings-json
     被 harness 安全规则拦截；
   - Workflow 只按「代理是否正常结束」计数，不校验约定产物是否存在；1b 后也没有七席完整性门禁。
   修复建议：
   - 阶段1 的 1b 之后、1c 之前增加**产物完整性门禁**：校验 `seat_reports/` 恰好 N 席且文件非空
     （或每个 agent 返回 `report_path` 并由脚本核验存在），缺失席位单独重派（≤3 次），
     不得直接进入 1c/1d；
   - 启动 Workflow 前确认当前用户消息就是审阅请求；若刚回答过无关问题，先结束该回合或重新锚定，
     再启动流程（运行中也不要向会话发送无关提问）；
   - 席位 prompt 增加一句：「本轮唯一任务是本席位审查；如收到与本任务无关的用户问题，
     记录后继续审查，不得以其替代审查」——可降低误从概率，但不能替代产物门禁；
   - Step 6 报告在「阶段1」节如实记录席位完整性（含补派），不得把补派后的七席静默写成一次成功。
12. **目录结构扁平化：每篇论文一目录，取消 papers/ 与 output/**（2026-11-10 用户提出，拟 v2.1 统一实施）：
   目标：论文原文、各版本、审阅过程与交付报告全部收在论文目录内，便于对应查阅、多版本比对与外部意见对账。
   推荐结构：
   ```
   <project-root>/
   ├── CLAUDE.md
   ├── INDEX.md
   └── <paper-name>/
       ├── v1/                  # 可选；多文件 LaTeX 必须放这里
       ├── <v1 单文件>          # 与 v1/ 二选一，不得并存
       ├── draft/               # 各版本提取生成的 md
       │   ├── draft.md         # 当前轮工作副本
       │   └── draft-v2.md      # 版本快照
       ├── v2/                  # 作者回包原样（替代 sources/v2）
       ├── response/            # 作者回复信与外部反馈
       │   └── response-v2.md
       ├── reports/             # 交付报告（替代 output/）
       │   ├── r1-审阅报告.md
       │   └── r2-复审报告.md
       └── .review/             # 过程状态（config/chain/RESUME/rN）
   ```
   规则（必须定死，否则会比现状更乱）：
   - **v1 二选一**：单文件源可直接放 `paper-name/` 根（`source_root="."`）；多文件 LaTeX 必须放
     `paper-name/v1/`（`source_root="v1"`）。两者不得并存；`setup_env.py` 检测到并存时报错并要求选择。
   - **v2+ 一律 `vN/`**：取消 `sources/`；`source_root="v2"`、`"v3"`…；作者回包原样保存，开审后不可变。
   - **draft 统一入 `draft/`**：`draft/draft.md` 为当前工作副本，`draft/draft-vN.md` 为版本快照；
     源目录只放原文，不混入转换稿。`draft/` 内文件均为可重建产物，**不是源**，不得作为唯一存档。
     文件名保留 `draft.md` / `draft-vN.md` 以兼容现有版本识别逻辑，不改成 `v1.md`。
   - **response 统一入 `response/`**：作者回复信 `response/response-vN.md`；外部专家/导师意见可放
     `response/expert-*.md`，便于与回复信逐条对账。不再放论文根。
   - **报告分两层**：`.review/rN/final_report.md` 为过程记录；`reports/rN-审阅报告.md` 为交付副本
     （Step 6 生成，二者内容一致，**采用复制而非软链接**，避免 Windows 兼容问题）。
   - **`.review/` 保持隐藏**：过程状态不改为可见的 `review/`，避免与阅读材料混排。
   - **INDEX.md 留在工程根**：一行一篇，路径相对论文目录；不再维护 `papers/INDEX.md`。
   影响清单（v2.1 实施时逐项改）：
   - `scripts/setup_env.py`：v2 默认 `source_root` 由 `sources/vN` 改为 `vN`；增加 v1 根目录/v1 目录
     二选一检测；**paper_dir 解析必须从 `draft/` 子目录回到论文根**（不能再用 `dirname(file_path)`）；
     `unregistered_sources()` 需忽略 `v1/`、`vN/`、`draft/`、`response/`、`reports/`、`figures/`，避免误报。
   - `config.json`：`versions.vN.source_root` 取值改为 `"." | "v1" | "v2"…`；`draft` 路径改为
     `draft/draft.md` / `draft/draft-vN.md`；建议加 `"layout": "flat-v2.1"` 供迁移脚本识别。
   - `SKILL.md`：目录树、命令示例（`<paper>/draft/draft-v2.md`、`--response response/response-v2.md`）、
     Step 0 覆盖护栏选项、Step 6 交付路径。
   - `references/re-review-protocol.md`：`sources/vN` 全部改 `vN`；draft/response 路径示例；报告路径改 `reports/`。
   - `templates/final-report.md`：产物路径与报告路径。
   - 工作空间 `CLAUDE.md`：目录树与“新稿件放入根目录/<paper-name>/”的说明。
   - `scripts/migrate_rounds.py`：兼容旧 `sources/`；新增 `scripts/migrate_layout.py`。
   迁移方案（`migrate_layout.py`，必须支持 dry-run/备份/回滚/幂等）：
   1. 扫描 `papers/*` 与 `output/*`，按稿名生成映射表并输出 dry-run 报告；
   2. 将 `papers/<name>` 移至根目录 `<name>`；`sources/vN` 重命名为 `vN`；
   3. 根目录 `draft*.md` 移入 `<name>/draft/`，`response*.md` 移入 `<name>/response/`；
   4. 将 `output/<name>-rN-*.md` 移入 `<name>/reports/rN-审阅报告.md`，其余历史报告按稿名归位；
   5. 更新每篇 `config.json` 的 `source_root` 与 `draft` 路径、`chain.md`/`RESUME.md` 中的路径、根 `INDEX.md`；
   6. 校验：`setup_env.py` 能从 `draft/` 反推论文根、`resume.py check` 通过、`--re-review` 能从 `vN/` 找到源；
   7. 保留 `papers.bak/`、`output.bak/` 直至用户确认后再删。
   验收标准：根目录不再存在 `papers/`、`output/`；每篇论文目录自包含源/草稿/版本/反馈/过程/报告；
   v1 根与 v1/ 两种形态均可运行且混用被拒绝；从 `draft/draft-vN.md` 启动时 paper_dir 解析正确；
   迁移脚本重复执行不产生二次移动。
   已定决策（2026-11-10 用户确认）：`.review` 保持隐藏；报告交付副本采用复制，不用软链接。
   **存量实测清单（2026-11-11 核对 paper-reviewer 工作空间，可直接当 migrate_layout 的验收夹具）**：
   8 篇稿件 + 根 `papers/INDEX.md` + `output/` 17 个文件，其中 5 类需人工判定、脚本须能列出待确认项而非猜测：
   - `q10/`：根目录并存 draft.md 与 draft-v2…v5.md + `sources/`，报告名非标准
     （`q10-1-复审报告.md`/`q10-2-审阅报告.md`/`q10-3-审阅报告.md`/`q10-r5-re-review-report.md`/
     `q10-去AI替换对照清单-全量.md`）→ 轮次号需从文件名或 chain.md 反推；
   - `xue-paper-latex/`：完整 LaTeX 工程（`chapters/`、`figure/`、latexmkrc、编译产物 .lof/.lot/.toc/.pdf、
     以及 LICENSE/README.md/_config.yml 等无关文件）→ 必须整体入 `v1/`，且 v1 二选一检测不得被
     根目录 README/LICENSE 干扰；
   - `li-paper-v13/`、`zhang-paper/`、`仿真稿件-20261105/`：docx + pandoc `media/` 图目录；
   - `于小岚…/`、`全昌寿…/`：PDF + PyMuPDF `figures/` 图目录；
   - `output/` 内的**非报告文件**须归入对应论文 `response/`：
     `仿真稿件-20261105-审阅报告（张审查第一轮）.20261109.docx`（外部专家意见）、
     `何论文意见.20261011.docx`（he-paper 外部意见）；
     `仿真稿件-20261105-综合审阅意见.md/.docx` 属交付报告 → `reports/`。
   注意：paper-reviewer 工作空间**不是 git 仓库**，迁移无版本回退，只能依赖 `papers.bak/`、`output.bak/`。
13. **setup_env CLI 与 SKILL 用法不一致**（2026-11-10 两篇实测）：
   `SKILL.md` 用法表示例带 `--source` / `--format` / `--focus`，但 `setup_env.py` 的 argparse 不接受，
   直接报 `unrecognized arguments`（实测两次都只能去掉这些参数再跑）。v2.1 二选一：
   - 实现 `--source` / `--format` 并透传给 conversion_audit / anchor_map；`--focus` 在 Step 0 记录后路由；
   - 或从 SKILL 用法表移除这些参数，改在 Step 0.3/0.5 单独调用。
   同时逐项核对用法表与 `--help` 的所有参数，避免“文档教一套、脚本收另一套”。
14. **anchor_map 的 PDF fill 与 quote 键冲突**：
   - `init` 接受 `--format pdf`，但 `fill` 的 `pdf_units()` 只读带 `%% [PDF p.N]` 页标记的**提取文本**；
     对二进制 PDF 无法读取。实测需临时把 `anchor_map.json.source` 改为 `draft.md`、fill 后再恢复。
     v2.1 应在 format=pdf 且源为二进制时用 PyMuPDF 提取，或自动回退 draft 页标记，并把
     `source_extract` 写入 anchor_map.json。
   - `do_fill()` 以 `id` 或 `quote` 为键；新 id 的条目用 quote 作键，同一段落的多条发现会互相覆盖
     （实测 78 条请求只落 70 条）。应始终以 `id` 为键；重复 quote 保留多条并标 ambiguous；
     fill 后校验 `requests 数 == entries 数`，不等即报错。
15. **merge_findings 的表格空行截断导致条目静默丢失**：
   `_v2_table_rows()` 从标题后找第一个表格，遇到空行即停止。若在表格中间插入空行（手工补条目时极易发生），
   后续行会被静默丢弃；实测 R-40～R-45 未进入 merged（P0 7→9、内容 41→47 未反映），
   而 `sources_missing` 仍为空。应跳过空行直到下一个标题，或解析该节全部表格；合并后校验
   roadmap 的 R-ID 集合 ⊆ merged，缺失即 fail 并列出 ID，不得只报文件级 `sources_missing`。
16. **去AI质量评分与重叠项口径不一致**：
   `deai_confirmed.md` 的「质量评分」把与阶段1 重叠的语言项也计入扣分（实测 31 条，合并实际保留 26 条），
   与协议「重叠不重复计入」矛盾。2c 应分别报告 `confirmed_total` 与 `scored_total`，按 `scored_total`
   计算质量分；`merge_findings.py` 输出 `quality_score` 时复核同一口径。
17. **Step 6 报告与计数一致性校验**：
   `final_report.md` 目前手工生成，P0/P1/P2、交叉引用、席位完整性、anchor resolved 数需人工同步；
   于小岚稿实测出现 7→9 P0、39→47 项、75→81 项的中间态，均靠人工发现。v2.1 增加
   `scripts/build_final_report.py` 或 `validate_report.py`：从 merged/roadmap/chain 读取并核对
   总数、每席报告数、anchor resolved 数、报告副本路径；不一致即 fail。补派席位后自动触发 1d 重算与校验。
18. **Workflow 劫持防护扩展到阶段2**（第 11 条补充）：
   harness 的 triggering request 注入对所有 Workflow 生效，阶段2 四技能审计同样可能被无关提问劫持。
   完整性门禁应同时覆盖 `seat_reports/`（N 席）与 `deai_audits/`（4 份），均校验非空与预期路径；
   缺失时单独重派，不得只重跑整个阶段。
19. **条目 5/7/8 与第 12 条的冲突修订**（实施时以第 12 条为准）：
   - 第 5 条 `papers/INDEX.md` → 工程根 `INDEX.md`；文件不存在时由 Step 6 创建，而非仅追加；
   - 第 7 条 `source_root="."` 需扩展为 `"." | "v1"` 两种 v1 形态，护栏判定同步；
   - 第 8 条的 `sources/vN`、根目录 `draft-vN.md`、`output/` 报告约定已被第 12 条取代：
     draft 入 `draft/`、版本源入 `vN/`、报告入 `reports/`；实施时删除/改写旧约定，避免两套并存。
   - 第 12 条目录树缺图片产物位置：extract 出的图应落 `draft/figures/`（见第 23 条）。
20. **anchor_requests.json 仍靠手工构建**（2026-11-10 两篇实测）：
   SKILL 3.2a 要求用 Write 手写请求表；两篇都只能临时写 Python 从 merged_findings 抽行，
   且位置列格式不统一（`L123` / `行123` / `§5.2 第3段` / `表5-6`），首次抽取 0 条请求。
   v2.1 新增 `scripts/build_anchor_requests.py`：
   - 从 merged_findings.md（或 roadmap + deai_confirmed）逐条解析 ID/位置/原句引文，
     位置解析兼容 `L\d+`、`行\s*\d+`、`§X.Y`、`表N`/`式N`；
   - 引文不足 15 字或在 draft 中不唯一时标 `weak`/`ambiguous` 并输出「待人工补引文」清单，
     不得静默丢弃；无行号项（跨节/文末）显式标 `structural_only`；
   - 输出 `{run_dir}anchor_requests.json` + 统计（total/with_quote/without_quote），
     与第 14 条的 fill 校验（requests 数 == entries 数）串成闭环。
21. **专家意见 docx 支持：规格与实现不一致**（仿真稿 2026-11-09 实测）：
   §10.4 标题写 `--expert-comments <md|docx>`，但 `expert_reconcile.py` 用 `read_text_file()`
   只按 utf-8-sig/utf-8/gbk 读文本，docx 直接失败；SKILL 用法表则写「md/提取文本」。
   实测外部意见（张审查第一轮）以 `.docx` 到达，须先手工转换才能对账。v2.1 二选一并统一三处口径
   （§10.4 / SKILL 用法表 / 脚本实现）：
   - 实现 docx 读取（pandoc 或 python-docx，复用第 10 条转换链），`setup_env.py` 按扩展名校验并给明确错误；
   - 或明确「仅接受文本」，在 SKILL Step 0 增「docx 先转换」前置指令。
   > **[v2.1 已实施（G1，门禁 G2 用户裁决：脚本原生支持 docx）]**：选「实现 docx 读取」，
   > 但既未用 pandoc 也未用 python-docx——`expert_reconcile.py` 以 zipfile+ElementTree
   > 原生解析 `word/document.xml`（零第三方依赖，与 conversion_audit.py 同一模式；
   > Word 自动列表段落按 w:numPr 转 `- ` 条目行，多行续接规则不变）；损坏/伪 docx
   > exit 1 明确报错；`setup_env.py` 对 .docx 专家意见做 zip 魔数校验（exit 2）。
   > §10.4 标题 / SKILL 用法表 / 脚本实现三处口径已统一为 `<md|docx>`。
22. **报告交付后收到外部意见的追加对账流程未定义**（仿真稿实测）：
   现协议假定 `--expert-comments` 在 Step 0 声明、阶段3 收尾对账；实际外部意见常在 r1 报告交付后才到。
   本次靠手工综合（面板 32 条 × 专家 17 条 → 13 吻合 / 1 部分吻合 / 3 新增，合并计数 P0 10 / P1 14 / P2 12 = 36），
   产物命名、计数口径、是否递增轮次均无规范。v2.1 应定死：
   - 同轮追加：允许对已交付轮次补跑 `expert_reconcile init/match/verify`，产出
     `<paper>/reports/rN-综合审阅意见.md`（三态对账表 + 合并后严重度分布 + 新增项标注来源=专家），
     并同步更新 chain.md 该轮记录（追加「专家对账」行，不改原决议）与 INDEX.md 报告路径；
   - 或强制 `--new-run` 开 r<N+1>；二者择一，避免「综合意见」游离于版本谱系之外；
   - 合并计数规则：吻合项不重复计数；专家新增项按面板严重度规则定级；冲突项记入未决分歧交用户裁决。
23. **Step 0 缺输入类型分派**（与第 10、12 条配套）：
   SKILL 只接受 Markdown 路径，PDF/DOCX/TeX → md 的转换步骤只写在工作空间 CLAUDE.md 里，
   技能本身无入口（两篇实测均由会话临时决定转换方式，故有第 10 条）。v2.1 在 Step 0.1 前增加分派：
   入参为 `.pdf` / `.docx` / `.tex` / 目录时，先调 `extract_pdf.py`（或 pandoc）产出 `draft/draft.md`
   再进流水线，并把实际转换命令与参数写入 conversion_audit.md 以便复现；
   图片产物落 `draft/figures/`（与 draft.md 相对引用），同时加入 `unregistered_sources()` 忽略清单
   与 `migrate_layout.py`，否则图目录会被覆盖护栏误报为未登记源。
   **图目录有两种既存形态**（实测 8 篇稿件）：pandoc 转 docx 产出 `media/`，PyMuPDF 提取产出 `figures/`；
   忽略清单与迁移脚本须同时覆盖两者（建议统一收敛到 `draft/figures/`，迁移时把 `media/` 一并移入并
   改写 draft.md 内的图片相对路径）。
24. **每条修复必须配回归用例 + 两类一致性守卫测试**（tests/test_paper_review 已有 12 个测试文件，
   但第 14/15 条缺陷均未被现有用例覆盖）：
   - 修复夹具：anchor 同段两条发现不得互相覆盖；二进制 PDF fill 应显式报错而非静默全 not_found
     （`_read_text()` 对二进制可能按 gbk「成功」解码出乱码，需按 `%PDF-` 魔数判二进制）；
     merge_findings 表格含空行；去AI `scored_total` 口径；`migrate_layout` dry-run/幂等/回滚；
   - 守卫测试①**文档-脚本一致性**：解析 SKILL.md 用法表全部 `--flag`，与各脚本 argparse（含子命令）比对，
     差集非空即 fail（可直接拦住第 13、21 条）；
   - 守卫测试②**引用文件存在性**：扫描 SKILL.md 与 references/*.md 中出现的 `scripts/*.py`、
     `templates/*`、`references/*` 路径，文件不存在即 fail（可直接拦住第 10 条的 extract_pdf.py 悬空引用）。

### 实施顺序与依赖（建议，2026-11-11 复核后补）

1. **规范先行**：19（消除 5/7/8 与 12 的冲突）→ 12（扁平化 + `migrate_layout.py`）→ 13/21（文档与 CLI 对齐）
   → 23（输入分派）。这组决定路径与参数口径，后续脚本修复须按新路径写，先做可避免返工。
2. **数据完整性**：15 → 14 → 20 → 16 → 17，一组做完（共同保证「条目不静默丢失、计数自洽」），
   并按 24 补回归用例。
3. **可靠性**：11 → 18（产物完整性门禁），改动集中在 Workflow 脚本与 SKILL 验证段，可与第 2 组并行。
4. **能力补齐**：10（`extract_pdf.py`）→ 22（追加对账）→ 1/2/3（图表审计专趟、Response Letter 骨架、判例库）。
5. **9（报告格式统一化）继续冻结**：等 17 的 `build_final_report.py` 落地后再定稿模板，避免改两次模板。
