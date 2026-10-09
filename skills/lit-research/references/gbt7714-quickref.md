# GB/T 7714 引用格式速查（gbt7714-quickref.md）

卡片「引用方式」字段必须按本速查表著录，且与论文参考文献表条目逐字一致。

## 一、文献类型标识与格式

| 类型 | 标识 | 格式 |
|------|------|------|
| 期刊论文 | [J] | 作者. 题名[J]. 刊名, 年, 卷(期): 页码. |
| 会议论文 | [C] | 作者. 题名[C]// 会议名. 出版地: 出版者, 年: 页码. |
| 专著 | [M] | 作者. 题名[M]. 版次. 出版地: 出版者, 年. |
| 报告 | [R] | 作者. 题名[R]. 出版地: 出版者, 年. |
| 学位论文 | [D] | 作者. 题名[D]. 保存地: 保存单位, 年. |
| 标准 | [S] | 标准编号. 标准名称[S]. 出版地: 出版者, 年. |
| 报纸 | [N] | 作者. 题名[N]. 报纸名, 出版日期(版次). |
| 网络资源 | [EB/OL] | 作者. 题名[EB/OL]. (发表日期)[引用日期]. URL. |

## 二、作者著录规则

- 英文：**姓 名首字母**（如 Smith J A）；姓全大写常见于学报（如 SMITH J A），跟随目标刊物惯例并全库统一
- 中文：**全名**（如 王飞跃）
- ≥3 人：第一作者 + "等"（中文）或 "et al."（英文）
- 机构作者：直接写机构名（如 NATO Standardization Office）

## 三、中文文献特殊规则

- 中文文献需附英文翻译，标注 (in Chinese)
- 页码用短横线 `-`（非 en-dash `–`）

## 四、预印本（arXiv 等）

- 未正式发表：按 [J/OL] 或 [EB/OL] 著录，给出 arXiv 号，如：
  `WANG P, LI X, XIANG C, et al. The landscape of prompt injection threats in LLM agents[J/OL]. arXiv: 2602.10453, 2026.`
- 已有正式发表版本：按正式版著录，卡片「其他」栏注明 arXiv 版差异

## 五、示例

```
[1] NATO. NATO Glossary of Terms and Definitions (AAP-06)[S]. Brussels: NATO Standardization Office, 2019.
[2] SHAHRIARI B, SWERSKY K, WANG Z, et al. Taking the human out of the loop: a review of Bayesian optimization[J]. Proceedings of the IEEE, 2016, 104(1): 148-175.
[3] 王飞跃. 平行系统方法与复杂系统的管理和控制[J]. 控制与决策, 2004, 19(5): 485-489 (in Chinese).
```

## 六、核对要点（写入卡片前）

1. 类型标识与实际文献类型匹配（期刊勿标 [C]，报告勿标 [M]）
2. 作者名缩写、大小写与目标刊物参考文献表逐字一致
3. 年、卷(期)、页码齐全且与原文核对无误
4. DOI/URL 可访问；DOI 优先给全称形式（10.xxxx/...）
5. 中文文献英文翻译准确、(in Chinese) 标注不缺
