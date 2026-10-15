# anchor-locator.md — 源位置三轨定位说明与诚实边界

> 配套脚本：`scripts/anchor_map.py`；数据文件：`{review_dir}/anchor_map.json`。
> 目的：审阅意见可追溯到**源文件**位置，便于作者直接在原稿（tex/docx/pdf）上修改，
> 而不是只对着 draft.md 行号找。

## 三轨定义

| 轨道 | 形式 | 特性 |
|------|------|------|
| 工作坐标 | draft.md 行号 | 流水线内部使用；每次编辑后**会漂移** |
| 源坐标 | tex=`文件:行号`；docx=`段落N`（python-docx paragraph index）；pdf=`p.N` 页码 | 指向作者原稿；tex/docx 行段号在源文件被编辑后同样漂移 |
| 结构坐标 | 章/节/表/公式编号（如 §2.1 表3 / 式(5)）+ 原句引文（≥15字唯一片段） | **跨格式最稳、不随编辑漂移**；永远是兜底锚点 |

每条发现应同时给出三轨；任何一轨缺失不影响其余两轨生效。

## 反查机制（anchor_map.py）

1. 引文与源文本先做归一化：NFKC（全半角统一）、去 markdown 强调符、空白折叠；
   tex 额外去注释、去命令、去花括号/数学定界符。
2. 归一化精确子串匹配；失败则退化为「压缩匹配」（再剔除全部空白与标点后比较）。
3. 命中统计：**恰 1 处 → resolved；多处 → ambiguous；0 处 → not_found**。
   ambiguous / not_found 时 `source_loc=null`，回退结构坐标（`structural` + `quote` 保留）。
4. pdf 源按提取文本中的页标记（`%% [PDF p.N]`，兼容 `--- Page N ---`）切分页单元后页内匹配。

## 诚实边界（反查何时会失败）

文本反查**不是**可靠保证，已知失败场景：

- **同句多处出现**：套话、模板句、重复的图表标题 → 多处命中 → ambiguous；
- **转换改标点**：pandoc/Word 往返会把全角改半角、断词加连字符、引号变体替换
  → 压缩匹配可救回一部分，但仍可能 not_found；
- **宏展开改变表面文字**：tex 中 `\newcommand{\method}{XYZ-Net}` 使源文件里
  根本没有 draft 中出现的字面文字 → 必然 not_found；
- **数学公式**：`$...$` 内的符号序列在 draft 与源中表面形式差异大 → 低命中。

失败不是错误：**结构坐标 + 引文永远是兜底锚点**，报告照常可交付，
只是「源位置」列显示 `—（回退结构坐标）`。

## 调用时机

| 时机 | 动作 |
|------|------|
| Step 0 之后 | 用户提供 `--source` 时：`anchor_map.py init` 生成空表；未提供则跳过（报告双轨） |
| 阶段4 合并时 | 从 merged_findings.md 逐条提取原句引文（≥15字、draft 内唯一），写 `anchor_requests.json`，执行 `anchor_map.py fill` 填充 |
| Step 6 报告 | 问题表增加「源位置」列（三轨并列），报告头部注明各轨含义与漂移特性 |

## 可选增强（非必须）

- **LaTeX + synctex**：若源目录存在 `.synctex.gz`，可用 synctex 做 pdf页 ↔ tex行
  精确映射，源坐标质量高于文本反查（实施时优先）。
- **Word 回源交付**：需要把修改落回 .docx 时，优先用 `word-revision` 技能的
  Track Changes 锚定字符区间——字符级锚定强于任何行号/段落号，且作者可见修订轨迹。
