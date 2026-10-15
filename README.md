# skills-maker

Claude Code 自定义技能开发与发布工作空间。

## 技能列表

| 技能 | 版本 | 说明 |
|------|------|------|
| **lit-research** | 1.0.1 | 文献调研：deep-research 检索 → 查新 → 下载提取 → 建卡 → 去AI化 → 验证入库 |
| **paper-review** | 1.1.0 | 论文审查：去AI审查 → 多智能体研讨 → 同行评审 → 修改执行 → 收敛循环（支持源位置三轨定位） |

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

## 使用方法

### lit-research（文献调研）

```
/lit-research 数字孪生在军事训练中的应用 --max-papers 8
```

流程：deep-research 检索 → 本地查新 → 用户选择 → 下载提取 → 质量评分 → 建卡 → 去AI化 → 验证 → 入库

### paper-review（论文审查）

```
/paper-review 论文.md --section 2.1
/paper-review 论文.md --quick          # 快速模式（单实例）
/paper-review 论文.md --focus de-ai    # 仅去AI审查
/paper-review 论文.md --no-fix         # 仅报告不修改
/paper-review 论文.md --source tex目录 # 源位置三轨定位（tex/docx/pdf）
```

流程：去AI审查(4技能) → 多智能体研讨(5角色) → 同行评审(ars-reviewer) → 修改执行 → 收敛循环

## 测试

```bash
python tests/test_paper_review/test_anchor_map.py       # 三轨定位（11 用例）
python tests/test_paper_review/test_merge_findings.py   # 合并+白名单防噪声（7 用例）
python tests/test_lit_research/test_extract_pdf.py      # PDF 页标记（需 PyMuPDF）
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
    scripts/             Python 脚本（6个，含 anchor_map.py 三轨定位）
    references/          可替换模板（6个，含 anchor-locator.md / format-notes.md）
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
- **agent-roles.md** — 讨论角色，可增减或替换

替换这些文件即可适配不同项目，无需修改核心流程。

## 许可证

MIT
