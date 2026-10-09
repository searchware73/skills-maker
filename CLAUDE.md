# CLAUDE.md — skills-maker 项目

## 项目说明

本项目是 Claude Code 自定义技能的开发、测试、发布工作空间。技能通过 `install.py` 安装到 `~/.claude/skills/` 后生效。

## 目录结构

```
skills/              ← 技能目录（每个技能一个子目录）
  lit-research/      ← 文献调研技能
  paper-review/      ← 论文审查技能
shared/scripts/      ← 跨技能共享的 Python 模块
tests/               ← 测试用例和样本数据
docs/                ← 文档
install.py           ← 安装/卸载/链接工具
```

## 技能结构规范

每个技能目录必须包含：
- `SKILL.md` — 技能定义（前置元数据 + 流程编排）
- `scripts/` — Python 脚本（执行机械性步骤）
- `references/` — 可替换模板文件（按项目定制）

## SKILL.md 编写规范

### 前置元数据（YAML）
```yaml
---
name: skill-name          # 必须，与目录名一致
version: 1.0.0            # 语义化版本
description: |            # 必须，含触发短语（harness据此自动匹配）
  技能描述...触发条件...
allowed-tools:            # 可选，限制工具范围
  - Read
  - Write
  - Bash
  - Skill
  - Workflow
---
```

### 流程编排原则

1. **显式调用**：所有步骤使用结构化指令格式，禁止自然语言描述
   - Python: `执行：Bash("python scripts/xxx.py --arg val")`
   - Skill: `执行：Skill(skill="name", args="...")`
   - Workflow: `执行：Workflow(script="...", args={...})`
   - AskUser: `执行：AskUserQuestion(questions=[...])`
2. **输入输出文件化**：步骤间数据通过文件传递（JSON），不依赖 Claude 记忆
3. **验证强制**：每个步骤有明确的验证条件，失败则回退修复
4. **循环保护**：验证循环最多3次，超出则暂停请用户介入

## Python 脚本规范

- 所有脚本接受 `--help` 参数输出用法
- 输出格式为 JSON（stdout），便于步骤间传递
- 错误输出到 stderr，退出码非零表示失败
- 编码统一 UTF-8，处理 Windows GBK 环境
- 依赖：PyMuPDF (fitz), requests（需在脚本中检查）

## 安装与发布

```bash
# 开发模式（符号链接，修改即时生效）
python install.py link <skill-name>

# 正式安装（复制到 ~/.claude/skills/）
python install.py install <skill-name>

# 列出已安装技能
python install.py list

# 卸载
python install.py uninstall <skill-name>
```

## Git 提交规范

- `feat(lit-research): 新增PDF提取脚本`
- `fix(paper-review): 修复收敛判定逻辑`
- `docs: 更新README安装说明`
- 版本标签：`v1.0.0`, `v1.1.0` 等
