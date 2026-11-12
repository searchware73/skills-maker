# v21-migration-notes.md — paper-review v2.1 移交说明（随技能安装到目标机）

> **读者**：在 paper-reviewer 等工作空间执行 `/v21-adopt` 的会话与用户。
> 本文件是 v2.1 落地的**唯一权威移交口径**——与 `docs/handoff-20261108-paper-review-v2.md`
> 备忘有出入处以本文件为准，不必回读备忘。
> 版本：paper-review v2.1.0（G1–G4，2026-11-11）。技能安装副本路径以
> `~/.claude/skills/paper-review/` 为准（下文简写 `{SKILL}`）。

---

## 1. 实际落地的目录树（v2.1 扁平结构）

```
<工程根>/                          ← 工作空间根
├── INDEX.md                       ← 审查索引（一行一篇；setup_env 缺则创建，Step 6 追加行）
└── <paper-name>/                  ← 论文目录（{paper_dir}，自包含）
    ├── <v1单文件源> 或 v1/         ← v1 源二选一：单文件留根（source_root="."）
    │                                 或多文件 LaTeX 整体入 v1/（source_root="v1"），不得并存
    ├── vN/                        ← v2+ 作者回包原样存放（开审后不可变）
    ├── draft/                     ← 工作稿（转换可重建产物，不是源）
    │   ├── draft.md / draft-vN.md ← 当前工作副本 / 版本快照
    │   ├── figures/               ← 稿件图片（media/ 与 figures/ 双形态均收敛于此）
    │   └── refs.txt / pdf_source_counts.json
    │                              ← PDF 稿 Step 0.0 产物（extract_pdf.py）：
    │                                 参考文献 [N] 切分（供 bib_lint）/ 源侧计数（供 conversion_audit）
    ├── response/                  ← 作者回复信 response-vN.md；外部专家意见 expert-*.md
    ├── reports/                   ← 交付副本：rN-审阅报告.md / rN-复审报告.md（复制而非软链接）；
    │                                 rN-综合审阅意见.md（交付后追加对账，expert_reconcile.py report）
    └── .review/                   ← 过程状态（隐藏目录）
        ├── config.json            ← 跨轮状态唯一权威源；含 "layout": "flat-v2.1"
        ├── chain.md               ← 版本谱系（每轮一节；交付后对账追加「专家对账」行）
        ├── RESUME.md              ← 续跑快照（resume.py --run-dir {review_dir}）
        └── r<N>/                  ← 第 N 次审阅运行的全部过程产物
            （seat_config.md / seat_reports/ / debate_summary.md / decision_letter.md /
             revision_roadmap.md / deai_audits/ / deai_cross.md / deai_confirmed.md /
             deai_exempt.md / expert_items.json / expert_reconcile.md /
             merged_findings.md / anchor_requests.json / anchor_map.json /
             conversion_audit.md / bib_lint.md / final_report.md …）
```

向后兼容：v1.x 扁平产物只读兼容不破坏；`migrate_rounds.py`（轮次形态迁移）保持可用。

## 2. 与备忘的偏差（逐条，含原因）

| # | 备忘条目 | 备忘口径 | 实际落地 | 原因 |
|---|---------|---------|---------|------|
| 1 | 条目10 extract_pdf 位置 | 二选一：提升为 shared 共享模块双模式（excerpt/full-manuscript） vs paper-review 内独立新建 | **paper-review 内独立新建**（门禁 G1' 用户裁决）；lit-research 版仅加 docstring 警示，行为不变 | install.py 不携带 shared/ 模块，安装副本上 import 必然失败 |
| 2 | 条目10 测试夹具 | 建议用于小岚 186 页 PDF 前 10 页切片 | PyMuPDF **合成 3 页夹具**（字号分级标题/页眉页脚/点引线/被拆标题/三形态图像/线框表格/[N] 参考文献/加密 PDF/书签模式） | 仓库内无真稿；合成夹具可精确断言且无版权/体积问题 |
| 3 | 条目17 二选一 | build_final_report.py 或 validate_report.py | **validate_report.py（校验器）** | 报告生成含语义归并，无法脚本化；校验器锁死数字一致（合并统计/决议三方/质量评分/反查统计/席位/交付副本/INDEX/chain） |
| 4 | 条目20 输入源 | merged_findings（或 roadmap+deai 双源） | **仅 merged_findings.md 单源** | merged 即合并后唯一权威清单，双源无独立价值 |
| 5 | 条目22 二选一 | 同轮追加 vs 强制 --new-run | **同轮追加**（门禁 G2' 用户裁决）：report 子命令产出 rN-综合审阅意见.md，chain 追加「专家对账」行不改原决议，INDEX 同步 | 交付后补开 r(N+1) 会让「综合意见」游离于版本谱系 |
| 6 | 条目1/2/3 | 图表审计专趟 / Response Letter 骨架 / severity-precedents.md 判例库 | **deferred → v2.2**（门禁 G4 用户裁决） | 可选增强，上下文预算优先给 10/22 |
| 7 | 条目9 | 报告格式统一化 | **维持冻结**；templates/final-report.md 仅增行（§2 反查统计、§3 席位完整性、§4 审计完整性），未改节名列名 | 需再实审 3–5 次汇总摩擦点后定稿 |
| 8 | §12 目录树 | draft/ 只列 draft.md/draft-vN.md | 增列 figures/、refs.txt、pdf_source_counts.json；reports/ 增 rN-综合审阅意见.md | 条目10/22 的 G4 产物，备忘 §12 早于其定稿 |
| 9 | 条目20 引文核查 | 引文 <15 字标 weak | 增补：**含省略号（…/...）的示意性引文一律标 weak 并跳过 draft 存在性核查**，进 needs_manual_quote | NFKC 把 … 展开为 ...，示意片段核查必然误报 not_in_draft（实测触发） |
| 10 | 条目16 双口径 | confirmed_total/scored_total | 落地为 deai_confirmed.md 表后**固定三行**（confirmed_total / scored_total / 质量评分），merge_findings.py 机器复核，不符告警 quality_basis_warnings（不中断） | 固定行格式才能被脚本锁定 |

## 3. migrate_layout.py（存量工作空间迁移）

```bash
python {SKILL}/scripts/migrate_layout.py --root <工作空间根>            # 缺省 dry-run
python {SKILL}/scripts/migrate_layout.py --root <root> --dry-run [--report FILE]
python {SKILL}/scripts/migrate_layout.py --root <root> --apply   [--report FILE]
python {SKILL}/scripts/migrate_layout.py --root <root> --rollback
```

| 参数 | 含义 |
|------|------|
| `--root` | 工作空间根（含 papers/ 与 output/；或已迁移后的扁平根） |
| `--dry-run` | 缺省模式：只输出迁移计划与待确认清单，**零文件系统改动** |
| `--apply` | 实际执行；每步记入 `<root>/.migrate-layout/manifest.json`（改写文件先备份） |
| `--rollback` | 按 manifest 逆序字节级复原（应在开始新审阅之前执行） |
| `--report FILE` | markdown 报告写盘（计划/待确认项/校验命令/备份说明） |

stdout JSON 字段：`success` / `mode` / `root` / `scanned{papers,output_files}` /
`moves[{from,to}]` / `rewrites[path]`（config/chain/RESUME 路径口径改写）/
`pending[{category,paper,item,recommendation}]`（人工判定项，**只列不猜**）/
`notes` / `report` / `manifest`；`--apply` 另有 `moved`/`rewritten`，`--rollback` 另有 `restored`。

纪律：幂等（二次 apply 零改动）；**只移动不删除**（papers/ → papers.bak/、
output/ → output.bak/，用户确认后再手工删）；退出码 0 成功 / 1 运行时失败
（manifest 已记录，可 rollback 或重跑）/ 2 参数错误。

**改写范围仅限机器字段**（回流 R-4 实测确认）：config.json / chain.md / RESUME.md
与 anchor_map*.json 的路径字段会重写为 v2.1 口径；`.review/` 内叙述性文本
（报告正文、「审计对象」行、历史命令记录）中的旧路径**保留原样**——属历史记录，
不改写。照抄旧命令会失败，重放前按新布局人工核对。

## 4. 人工判定情形清单（pending.category）与推荐处置

| category | 情形 | 推荐处置 |
|----------|------|---------|
| nonstandard_report | output 报告名非标准（轮次号需反推） | 对照 chain.md/文件内轮次标注重命名后再 apply |
| latex_project | 完整 LaTeX 工程 | 整体移入 `<paper>/v1/`，无关文件不入检测视野 |
| media_dir | pandoc 产出 media/ 图目录 | 收敛到 draft/figures/ 并改写 draft 内相对路径 |
| figures_dir | PyMuPDF 产出 figures/ 图目录 | 同上收敛到 draft/figures/ |
| output_non_report | output 内非报告文件（外部意见/过程产物） | 确认归属：专家意见→response/，报告→reports/，过程→.review/ |
| v1_dual_form | 根单文件源与 v1/ 目录并存 | 二选一（多文件工程以 v1/ 为准），另一形态移走 |
| paper_dir_conflict | 工程根已存在同名目录 | 该篇自动跳过，人工合并两个目录 |
| index_conflict | 工程根已有 INDEX.md | 保留根版，papers/INDEX.md 行人工并入 |
| config_broken | config.json 解析失败 | 人工修复 JSON 后重跑 dry-run |

## 5. 下游校验命令清单（paper-reviewer 侧可直接执行）

```bash
# ① 迁移预演（零改动；确认 pending 清单后再 --apply）
python ~/.claude/skills/paper-review/scripts/migrate_layout.py --root <工作空间根> --dry-run --report migrate-report.md

# ② 迁移后抽查一篇：结构完整性 + config 口径
python -c "import json;print(json.load(open(r'<root>/<paper>/.review/config.json',encoding='utf-8'))['layout'])"   # 应输出 flat-v2.1

# ③ PDF 稿全流程冒烟：提取 → 源侧计数回填审计
python ~/.claude/skills/paper-review/scripts/extract_pdf.py --input <src.pdf> --draft <root>/<paper>/draft/draft.md
python ~/.claude/skills/paper-review/scripts/conversion_audit.py --source <src.pdf> --draft <root>/<paper>/draft/draft.md --source-counts <root>/<paper>/draft/pdf_source_counts.json --output audit.md

# ④ 交付前机器校验（Step 6.6 同款）
python ~/.claude/skills/paper-review/scripts/validate_report.py --run-dir <root>/<paper>/.review/r<N>/ --paper-dir <root>/<paper> --round <N> --seats 7

# ⑤ 阶段产物门禁（1b/2a 后同款）
python ~/.claude/skills/paper-review/scripts/check_artifacts.py --run-dir <root>/<paper>/.review/r<N>/ --subdir seat_reports --expect S1,S2,S3,S4,S5,S6,S7

# ⑥ 交付后专家对账（同轮追加）
python ~/.claude/skills/paper-review/scripts/expert_reconcile.py --run-dir <root>/<paper>/.review/r<N>/ report --paper-dir <root>/<paper> --round <N>

# ⑦ 本仓库测试套件（skills-maker 侧，逐文件跑；unittest discover 汇总跑会因
#    测试文件重复包装 sys.stdout 在收尾崩溃，属存量问题）
for f in tests/test_paper_review/test_*.py; do python "$f" || break; done   # 20 文件 317 用例
```

## 6. 新增/变更脚本与参数一览

**新增脚本**：

| 脚本 | 参数 | 用途 |
|------|------|------|
| `extract_pdf.py` | `--input --draft [--figures-dir --refs-out --counts-out --min-image-size]` | PDF 全文提取（full-manuscript 专用；⚠ 勿与 lit-research 同名节选提取器混用） |
| `build_anchor_requests.py` | `--run-dir --merged [--draft --output]` | merged → anchor_requests.json（引文抽取/weak/ambiguous/not_in_draft/structural_only/needs_manual_quote） |
| `validate_report.py` | `--run-dir [--paper-dir --round --re-review --seats --report --merged --index]` | 交付前机器校验（备忘条目17 的落地形态，取代 build_final_report 方案） |
| `check_artifacts.py` | `--run-dir --subdir --expect LIST [--ext]` | 阶段产物完整性门禁（恰好 N 份非空；redispatch 清单） |
| `migrate_layout.py` | `--root [--dry-run --apply --rollback --report]` | 存量工作空间 → v2.1 扁平结构迁移 |

**变更脚本**：

| 脚本 | 变更 |
|------|------|
| `setup_env.py` | 新增 `--source --format --focus --no-fix`（全参数：`--file --section --rounds --doctype --source --format --focus --quick --no-fix --re-review --response --expert-comments --panel --new-run`）；paper_dir 从 draft/ 反推；v1 二选一检测；config 增 layout=flat-v2.1；根 INDEX.md 缺则创建；非 md 输入 exit 1 给分派指引；docx 魔数校验 exit 2 |
| `conversion_audit.py` | 新增 `--source-counts FILE`（extract_pdf.py 计数 JSON 回填，pdf 源侧不再 null） |
| `expert_reconcile.py` | 新增 `report` 子命令（`--paper-dir --round [--merged --output --index]`，交付后同轮追加对账）；`--comments` 支持 .docx 原生解析（零第三方依赖） |
| `merge_findings.py` | `_v2_table_rows` 空行/散文容错；声明 R-ID ⊆ 合并∪撤回校验（缺失 exit 1 不写输出）；confirmed_total/scored_total 双口径复核 |
| `anchor_map.py` | `%PDF-` 魔数判二进制；PyMuPDF→draft 页标记→显式报错级联并留痕 source_extract；fill 以 id 为键、重复 id exit 1、requests==entries 强制校验 |
| `migrate_rounds.py` | 就地规范化为扁平口径（`sources/vK`→`vK`、draft/response 归位、config 补 layout），保持可用 |

**SKILL 流程变更**（用户可见）：Step 0.0 输入类型分派（.pdf 走 extract_pdf.py）；
阶段1 拆 1b→门禁→1c/1d，阶段2 拆 2a→门禁→2b/2c（Workflow 代理数≠产物存在）；
3.2a 改调 build_anchor_requests.py；Step 6 增 6.6 validate_report 机器校验；
新增「交付后追加对账」节；全部代理 prompt 增防劫持条款。
