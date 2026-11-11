# format-notes.md — 格式转换与提取注意事项（实测踩坑固化）

> 来源：4 篇论文全流程审阅实测（li-paper-v13 / xue-paper-latex / he-paper / zhang-paper，
> 见 docs/handoff-20261013-paper-review-hardening.md §B3）。
> 凡涉及 pandoc 转换或 PDF 提取的环节，执行前后必须按本清单核对。

## pandoc → LaTeX

1. **abstract 环境会被吸收为元数据而从正文消失**（xue-paper 实测）。
   转换后必须核对中英文摘要是否仍在正文中；缺失则从源 tex 手工补插
   `\begin{abstract}...\end{abstract}`，再继续流水线。
2. **`table*` / tikz / algorithmic 可能丢失或变形**（he-paper 实测，4/5 评审共识）。
   凡审查对象经过 pandoc 转换，最终报告必须声明：
   **「数值核验以编译 PDF 为准」**——表格数字、公式编号的核对不得只依赖转换后的 md/tex。

## pandoc → DOCX

3. **公式 / 文本框 / 批注可能破损**（li-paper 实测 `$pos_{a}ll$` 类破损）。
   转换后抽查：随机打开 3–5 处含公式/特殊格式的段落与源对照；
   发现破损即在报告中注明破损位置清单，破损区域不参与去AI自动修改（防止 Edit 误伤）。

## PDF → 文本提取

4. **页标记是标准动作，提取一律走脚本**：SKILL Step 0.0 调用
   `scripts/extract_pdf.py`（如 `python scripts/extract_pdf.py --input <src.pdf> --draft draft/draft.md`，
   full-manuscript 专用：全页无字符上限、标题重建、页眉页脚/点引线过滤、图像导出、
   refs.txt、pdf_source_counts.json），自动逐页植入 `%% [PDF p.N]` 标记；
   临时用 PyMuPDF 自行提取时也必须逐页植入。
   ⚠ 勿与 `skills/lit-research/scripts/extract_pdf.py` 混淆——那是**节选提取器**
   （前 8 页 + 后 3 页、每页 ≤3000 字符），用于全文稿件会把长文截断。
   该标记是 anchor_map.py 三轨定位中 pdf 源坐标（页码）的唯一切分依据，
   缺失则 pdf 源定位全部退化为结构坐标。

## 通用纪律

5. 任何转换后，**先抽查再进入审查阶段**；转换引入的破损不属于论文本身的问题，
   不得计入 P0/P1/P2 发现，但必须在最终报告「审查对象」节注明转换链路与抽查结果。
6. **转换命令留痕**：Step 0.0 输入类型分派（.pdf/.docx/.tex/目录 → draft/draft.md）
   的实际转换命令与参数，在 conversion_audit.md 生成后追加「## 转换链路」节写入，
   保证 draft 可复现；图片产物统一落 `draft/figures/`（pandoc 的 `media/` 与
   PyMuPDF 的 `figures/` 双形态均收敛于此）。
