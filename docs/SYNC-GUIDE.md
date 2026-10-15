# 新机器同步与安装指南

> 适用场景：在另一台笔记本（或重装系统后的机器）上同步 skills-maker 工作空间，
> 并安装/更新 `lit-research` 与 `paper-review` 两个技能。
> 最后核对：2026-10-15（对应 paper-review v1.1.0 / lit-research v1.0.1，标签 `v1.1.0`）。

---

## 1. 前置条件

新机器上需具备：

| 项目 | 要求 | 检查命令 |
|------|------|---------|
| Git | 任意较新版本 | `git --version` |
| Python | 3.8+ | `python --version` |
| Python 依赖 | PyMuPDF、requests | `pip install pymupdf requests` |
| Claude Code | 可正常启动 | — |
| GitHub 凭证 | 能访问 `searchware73/skills-maker` | `git ls-remote https://github.com/searchware73/skills-maker.git` |

## 2. 同步工作空间

**首次（新机器无仓库）：**

```bash
git clone https://github.com/searchware73/skills-maker.git
cd skills-maker
```

**更新（已有旧克隆）：**

```bash
cd skills-maker
git checkout main
git pull origin main        # 拉取最新提交
git describe --tags         # 可选：确认版本标签，如 v1.1.0
```

## 3. 安装两个技能

```bash
python install.py install lit-research
python install.py install paper-review
python install.py list      # 验证：两个都应显示 [已安装]
```

- 安装目标目录：`~/.claude/skills/`（Windows 为 `C:\Users\<用户名>\.claude\skills\`）
- 已存在旧版本时会提示覆盖，直接覆盖即可

**开发模式（可选）**——若在新机器上继续开发技能，改用符号链接，仓库改动即时生效：

```bash
python install.py link lit-research
python install.py link paper-review
```

> 注意：Windows 符号链接需开启「开发者模式」或以管理员运行；失败则退回 `install` 模式。

## 4. 安装外部依赖技能（⚠️ 容易漏，必查）

以下依赖**不在本仓库中**，需单独安装到 `~/.claude/skills/`（或按插件方式安装）：

| 依赖 | 被谁使用 | 必需性 |
|------|---------|--------|
| `stop-slop` | 两者去AI化阶段 | 必需 |
| `academic-humanizer` | 两者去AI化阶段 | 必需 |
| `humanize-writing` | 两者去AI化阶段 | 必需 |
| `humanizer-zh` | paper-review 阶段1 | 必需 |
| `deep-research` | lit-research Step 2 | 必需 |
| ARS 插件（含 `ars-reviewer`） | paper-review 阶段3/5 同行评审 | 必需 |
| `word-revision` | docx 回源交付（Track Changes） | 可选 |

最简办法：从旧机器整体拷贝 `~/.claude/skills/` 下对应目录 + ARS 插件配置。

## 5. 验证

1. **重启 Claude Code**（技能列表仅在启动时加载）
2. 输入 `/`，确认能看到 `lit-research`、`paper-review`
3. 跑仓库自带测试确认脚本环境正常（应全部 OK）：

```bash
python tests/test_paper_review/test_anchor_map.py        # 三轨定位，11 用例
python tests/test_paper_review/test_merge_findings.py    # 合并+白名单，7 用例
python tests/test_lit_research/test_extract_pdf.py       # PDF 页标记，需 PyMuPDF
```

4. 抽查安装副本与仓库一致：

```bash
diff -rq skills/paper-review ~/.claude/skills/paper-review
diff -rq skills/lit-research ~/.claude/skills/lit-research
```

## 6. 日常双向同步习惯

- **开发机改完**：更新版本号（SKILL.md frontmatter）与 CHANGELOG.md →
  `git commit` → `git push` → 本机 `python install.py install <skill>`
- **其他机器更新**：`git pull` → `python install.py install <skill>` → 重启 Claude Code

**铁律：仓库是唯一权威源。** 两台机器的 `~/.claude/skills/` 只通过 `install.py`
从仓库同步；不要直接编辑安装目录里的副本（下次 install 会被覆盖，改动丢失）。

## 7. 常见问题

| 症状 | 原因与处理 |
|------|-----------|
| `/` 里看不到技能 | 未重启 Claude Code；或 SKILL.md frontmatter 损坏（`name` 须与目录名一致） |
| 脚本输出中文乱码 | Windows GBK 环境；脚本已内置 UTF-8 reconfigure，若仍乱码检查终端编码 |
| `extract_pdf.py` 报缺少依赖 | `pip install pymupdf requests` |
| `link` 模式报权限错误 | Windows 开启开发者模式或用管理员终端；或改用 `install` |
| paper-review 阶段3 失败 | ARS 插件未装；技能会提示降级（自行按 checklist 评审），最终报告注明 |
| pull 后技能行为没变 | 忘了重新 `install`（复制模式下安装副本不会自动更新） |
