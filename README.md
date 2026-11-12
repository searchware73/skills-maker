# skills-maker

Claude Code 自定义技能开发与发布工作空间。

## 技能列表

| 技能 | 版本 | 说明 |
|------|------|------|
| **lit-research** | 1.0.1 | 文献调研：deep-research 检索 → 查新 → 下载提取 → 建卡 → 去AI化 → 验证入库 |
| **paper-review** | 2.1.1 | 论文审查：七席合并面板（含数值审计专席）→ 去AI多智能体研讨 → 合并报告 → 修改执行 → 收敛循环；v2.1 扁平目录（每篇论文一目录 + 工程根 INDEX.md）、PDF 全文提取、阶段产物完整性门禁、交付后同轮追加对账；支持稿件类型准则绑定、多版本复审、专家意见对账、三轨定位、RESUME 续跑 |

## 安装

### 方法一：从 GitHub 安装（推荐）

```bash
git clone https://github.com/<your-username>/skills-maker.git
cd skills-maker
python install.py install lit-research
python install.py install paper-review
```

### 方法二：开发模式（符号链接）

```bash
python install.py link lit-research   # 修改即时生效
python install.py list                 # 查看状态
```

安装后重启 Claude Code，技能即可通过 `/lit-research` 或 `/paper-review` 调用。

> 在新机器上同步工作空间与安装技能，见 [docs/SYNC-GUIDE.md](docs/SYNC-GUIDE.md)。

## 使用方法

### lit-research（文献调研）

```
/lit-research 数字孪生在军事训练中的应用 --max-papers 8
```

流程：deep-research 检索 → 本地查新 → 用户选择 → 下载提取 → 质量评分 → 建卡 → 去AI化 → 验证 → 入库

### paper-review（论文审查）

```
/paper-review 论文.md --doctype full-paper        # 完整论文（类型必声明，缺失会询问）
/paper-review 论文.pdf --doctype thesis           # PDF 稿：extract_pdf.py 全文提取（页标记/图表题/参考文献）
/paper-review 论文.md --quick                     # 快速模式（S1+S6 两席）
/paper-review 论文.md --focus de-ai               # 仅去AI审查（panel=仅面板）
/paper-review 论文.md --no-fix                    # 仅报告不修改
/paper-review 论文.md --source tex目录            # 源位置三轨定位（tex/docx/pdf）
/paper-review draft-v2.md --re-review --response response-v2.md   # 核验式复审
/paper-review 论文.md --expert-comments 专家意见.md               # 专家意见对账（md/docx；交付后可同轮追加，产出 reports/rN-综合审阅意见.md）
```

流程：Step 0（doctype 绑定/转换审计/引文 lint/成本预估）→ 七席面板（独立审查→讨论撤回→编辑综合）→ 去AI研讨（四代理审计→交叉质询→终裁）→ 合并报告 → 修改执行 → 收敛循环

工作空间采用 v2.1 扁平结构（工程根 `INDEX.md` + 每篇论文一目录，论文目录内自带 `draft/`、`reports/`、`.review/`）。存量 `papers/`+`output/` 工作空间用迁移脚本升级（缺省 dry-run，人工判定项只列不猜）：

```bash
python ~/.claude/skills/paper-review/scripts/migrate_layout.py --root <工作空间根>   # 预演
python ~/.claude/skills/paper-review/scripts/migrate_layout.py --root <工作空间根> --apply
```

迁移参数、待确认项处置与下游校验清单详见 [skills/paper-review/references/v21-migration-notes.md](skills/paper-review/references/v21-migration-notes.md)。

## 测试

```bash
# paper-review（19 文件 317 用例，逐文件运行；一次性 unittest discover 汇总跑会因
# 测试模块重复包装 sys.stdout 在解释器收尾崩溃，属存量问题）
python tests/test_paper_review/test_setup_env_v2.py           # doctype/轮次/护栏/预估/扁平结构（31）
python tests/test_paper_review/test_merge_findings_v2.py      # 合并完整性/双口径（15）
python tests/test_paper_review/test_merge_findings.py         # v1 兼容回归（7）
python tests/test_paper_review/test_anchor_map.py             # 三轨定位/二进制 PDF/fill 完整性（21）
python tests/test_paper_review/test_build_anchor_requests.py  # merged → 锚点请求（14）
python tests/test_paper_review/test_resume.py                 # RESUME 续跑（20）
python tests/test_paper_review/test_diff_scope.py             # 版本 diff 分域（13）
python tests/test_paper_review/test_conversion_audit.py       # 转换审计 + 源侧计数回填（21）
python tests/test_paper_review/test_numeric_checks.py         # S7 数值检查库（17）
python tests/test_paper_review/test_bib_lint.py               # 引文 lint（10）
python tests/test_paper_review/test_expert_reconcile.py       # 专家对账 + 交付后同轮追加（36）
python tests/test_paper_review/test_validate_report.py        # 交付前机器校验（21）
python tests/test_paper_review/test_check_artifacts.py        # 产物完整性门禁（12）
python tests/test_paper_review/test_extract_pdf.py            # PDF 全文提取（25，需 PyMuPDF）
python tests/test_paper_review/test_migrate_layout.py         # 存量迁移 dry-run/apply/幂等/回滚（24）
python tests/test_paper_review/test_migrate_rounds.py         # 轮次迁移（11）
python tests/test_paper_review/test_docs_cli_consistency.py   # 守卫：SKILL/CLI 一致性（10）
python tests/test_paper_review/test_referenced_files_exist.py # 守卫：引用路径存在性（5）
python tests/test_paper_review/test_skill_invocation.py       # 阶段5 技能调用名（4）
python tests/test_lit_research/test_extract_pdf.py            # PDF 页标记（需 PyMuPDF）
```

## 依赖

- Python 3.8+
- PyMuPDF (`pip install pymupdf`)
- requests (`pip install requests`)
- Claude Code（含 ARS 插件用于同行评审）

## 项目结构

```
skills/                  技能目录
  lit-research/          文献调研技能
    SKILL.md             流程编排
    scripts/             Python 脚本（6个）
    references/          可替换模板（4个）
  paper-review/          论文审查技能
    SKILL.md             流程编排
    scripts/             Python 脚本（17个 + numeric_checks/ 检查库）
    references/          可替换模板（10个：七席章程/研讨协议/doctype准则/复审协议/v2.1 移交说明等）
    templates/           报告与谱系模板（final-report.md / chain.md）
shared/scripts/          共享模块
install.py               安装工具
tests/                   测试用例
docs/                    文档
CHANGELOG.md             变更日志
```

## 自定义

每个技能的 `references/` 目录包含可替换模板：
- **card-template.md** — 卡片格式模板，按项目需求定制
- **quality-rubric.md** — 评分标准，可调整维度和权重
- **panel-roles.md** — 七席面板章程，可增减席位或调整检查清单
- **doctype-criteria.md** — 稿件类型准则（机器版在 setup_env.py，两处需同步）

替换这些文件即可适配不同项目，无需修改核心流程。

## 许可证

MIT
