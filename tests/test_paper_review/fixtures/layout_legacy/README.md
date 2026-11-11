# layout_legacy 夹具

migrate_layout.py 的验收夹具：按备忘 §十一 第12条「存量实测清单」构造的最小样例，
覆盖 5 类人工判定（非标准报告名 / 完整 LaTeX 工程 / pandoc media/ / PyMuPDF figures/ /
output 内非报告 docx）+ 1 篇可全自动迁移的干净论文（simple，双版本 + sources/v2 + 根草稿）。

**仅供测试复制使用，任何测试不得就地修改本目录**（test_migrate_layout.py 一律先
copytree 到 tmpdir 再操作）。所有 docx/pdf/png 均为文本占位（迁移不解析内容）。
