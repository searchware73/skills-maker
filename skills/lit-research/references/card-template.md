<!--
================================================================================
 资料卡片模板 card-template.md
================================================================================
 用途：create_card.py 读取本模板，将 {PLACEHOLDER} 占位符替换为 --data JSON 内容。
 规则：占位符一律为「大写 + 下划线」并整体包裹花括号，如 {AUTHOR}；缺失数据时
       create_card.py 会保留占位符原样并在 JSON 输出的 missing_placeholders 中列出。

 占位符清单与填写规则：
   {NUMBER}          3 位数字编号（不含方括号；模板中已写作 [{NUMBER}]）
   {AUTHOR}          GB/T 7714 作者格式——英文「姓 名首字母」（如 Smith J A），
                     中文写全名（如 王飞跃）；≥3 人取第一作者 + 等/et al.
   {TITLE}           文献原始标题（保留原语种，不翻译）
   {YEAR}            4 位年份
   {TYPE}            文献类型标识：[J]期刊 [M]专著 [C]会议 [R]报告 [D]学位论文
                     [S]标准 [N]报纸 [EB/OL]网络资源
   {SOURCE}          出版源（刊名/出版社/会议名 + 卷期页等）
   {DOI_URL}         DOI 或可访问 URL（前缀 DOI: 或 URL:）
   {CITATION}        引用方式，必须与论文参考文献表条目逐字一致（GB/T 7714）
   {VERIFICATION}    验证状态：✅ 已验证 / ⚠️ 部分验证 / ❌ 未验证（附验证方式）
   {ABSTRACT}        摘要——原文逐字摘录 + 中文翻译（可传 {original, translation}）
   {ABSTRACT_SOURCE} 摘要来源标注（如「PDF原文（Abstract）· 第 1 页」）
   {SUMMARY}         内容概要——800–1000 字，事实在前、评价殿后（铁律），忠于原文
                     不臆造、不过度延伸；结构：背景/问题→方法→实验→结论→与主题关联
   {SUMMARY_SOURCE}  概要来源标注
   {SUMMARY_BASIS}   概要依据标注（如「arXiv 全文（22 页，2602.10453）」）
   {SRC_FILENAME}    已下载源文件名 NNN_src_XXX.pdf
   {SRC_FORMAT}      源文件格式（默认 PDF）
   {SRC_SIZE}        源文件大小（如 1.2MB）
   {SRC_PAGES}       源文件页数
   {EXTRACT_FILENAME} 文本提取文件名 NNN_extract_XXX.txt
   {CITATION_STATUS} 引用情况——被引用者填 6 字段（引用状态/论文引用文字/原文对应
                     段落/引用用途/是否合适/评价说明）；未被引用者填单行
                     「未被论文正文引用」
   {OTHER}           其他补充信息（版本、预印本状态、关键定义等）
================================================================================
-->

# 资料卡片 [{NUMBER}]

## 基本信息

- **编号**：[{NUMBER}]
- **作者**：{AUTHOR}
- **标题**：{TITLE}
- **年份**：{YEAR}
- **类型**：{TYPE}
- **出版源**：{SOURCE}
- **DOI/URL**：{DOI_URL}
- **引用方式（GB/T 7714）**：{CITATION}
- **验证状态**：{VERIFICATION}

## 摘要

{ABSTRACT}

来源：{ABSTRACT_SOURCE}

## 内容概要

{SUMMARY}

来源：{SUMMARY_SOURCE}
依据：{SUMMARY_BASIS}

## 资料下载

- **已下载**：`{SRC_FILENAME}`（{SRC_FORMAT}，{SRC_SIZE}，{SRC_PAGES}页）
- **文本提取**：`{EXTRACT_FILENAME}`

## 引用情况

{CITATION_STATUS}

## 其他

{OTHER}
