# Skill Maintainer Audit Skill · 本地 Skill 维护 / 更新 / 使用统计 / 可视化

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Skill](https://img.shields.io/badge/AI%20Agent-Skill-blue.svg)](SKILL.md)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](pyproject.toml)

> English version: [README.en.md](README.en.md)

一个面向 Codex / Claude Code / Cursor 等本地 Agent 环境的 Skill 维护工具。它用于管理大量安装在本地的 AI agent skills：安全更新、结构审计、7 天和 30 天使用统计、功能分类、重复能力识别，并生成单文件 HTML 仪表盘。

## 30 秒开始

```bash
git clone https://github.com/kiaarryy/Skills-Maintainer-Audit-skill.git ~/.codex/skills/skill-maintainer-audit
cd ~/.codex/skills/skill-maintainer-audit
python scripts/run_audit.py --codex-home ~/.codex --output outputs/latest --update-policy report-only
```

已经安装过的话，用这段命令更新：

```bash
cd ~/.codex/skills/skill-maintainer-audit
git pull --ff-only
```

安装后可以直接对 Agent 说：

```text
Use $skill-maintainer-audit to audit my local skills, show 7-day and 30-day usage, find duplicates, and generate a dashboard.
```

## 效果

- 安全更新：只对干净 Git skill 执行 fast-forward；复制安装的非 Git skill 只做来源识别、上游检测和旁路 review 克隆建议。
- 使用统计：从本地 Codex sessions、session index、automation memory 中提取 7 天和 30 天触发证据。
- 来源识别：从 `.git`、`manifest.json`、`package.json`、README / AGENTS / SKILL 中识别 GitHub 来源和置信度。
- 分类整理：按研究、文档、前端设计、浏览器 QA、开发、自动化运维、agent 运维等类别整理全部 skill。
- 重复识别：按类别、名称和描述关键词找出功能类似或重复的 skill 组。
- 可视化报告：生成 `report.html`，包含 KPI、柱状图、使用榜单、未使用 skill、重复组和风险列表。
- 自动化友好：CLI 输出 JSON 和 HTML，适合每日或每周自动运行。

## 适合 / 不适合

合适：

- 本地安装了大量来源不同的 Skill，需要周期性维护。
- 想知道哪些 skill 真正在用，哪些 7 天或 30 天完全没用。
- 需要整理 skill 分类、发现重复功能、为清理或合并做证据。
- 希望自动化生成可浏览的维护仪表盘。

不适合：

- 需要强制覆盖或删除本地 skill。
- 希望在没有来源信息的情况下自动更新所有非 Git skill。
- 希望统计结果等同于平台内部真实触发计数。这里统计的是本地日志中的可解析触发证据。

## 安装

### 方式一：Git clone

```bash
git clone https://github.com/kiaarryy/Skills-Maintainer-Audit-skill.git ~/.codex/skills/skill-maintainer-audit
```

### 方式二：让 Agent 安装

把下面这段话发给有 shell 权限的 AI Agent：

```text
请帮我安装 skill-maintainer-audit。把 https://github.com/kiaarryy/Skills-Maintainer-Audit-skill.git 克隆到 ~/.codex/skills/skill-maintainer-audit，然后检查 SKILL.md、scripts/、references/ 是否存在。
```

## 使用流程

1. Inventory：扫描 `<codex-home>/skills` 下的 `SKILL.md`、`agents/openai.yaml`、脚本和资源目录。
2. Update：按安全策略检查 Git skill；只有干净工作树会被 fast-forward。
3. Usage：解析最近 7 天和 30 天本地日志，统计 `$skill-name` 和 `SKILL.md` 路径触发证据。
4. Classify：按描述和关键词生成类别、功能摘要和结构问题。
5. Deduplicate：生成相似 skill 组，辅助判断保留、合并或停用。
6. Report：输出 HTML 仪表盘和 JSON 数据。

## 常用命令

只读审计：

```bash
python scripts/run_audit.py --codex-home ~/.codex --output outputs/latest --update-policy report-only
```

安全更新：

```bash
python scripts/run_audit.py --codex-home ~/.codex --skills-root ~/.codex/skills --output outputs/latest --update-policy safe
```

Windows Codex 默认路径示例：

```powershell
python scripts/run_audit.py --codex-home C:\Users\pc\.codex --output outputs\latest --update-policy safe
```

## 输出文件

- `outputs/latest/report.html`：可视化仪表盘。
- `outputs/latest/skills_inventory.json`：skill 清单、分类、结构问题、来源信息。
- `outputs/latest/source_candidates.json`：自动发现的 GitHub 来源、来源类型和置信度。
- `outputs/latest/usage_7d_30d.json`：7 天和 30 天使用统计。
- `outputs/latest/update_actions.json`：更新状态和手动检查原因。
- `outputs/latest/duplicates.json`：功能重复或近似重复分组。
- `outputs/latest/manual_update_commands.md`：registry 更新命令，以及非 Git 安装 skill 的非破坏性 review 克隆建议。

## 自动化

建议把现有 Daily Skill Maintainer Audit 的 prompt 替换为：

```text
Use $skill-maintainer-audit from E:\VISUAL_code\Skill-Maintainer to run the local skill maintenance CLI against C:\Users\pc\.codex. Use safe update mode. Generate outputs/latest/report.html plus JSON outputs, summarize updated skills, manual-review items, 7-day and 30-day usage, duplicate groups, validation results, and any logs that could not be parsed.
```

## 来源清单

很多本地 skill 不是 Git clone 安装的，无法安全 `git pull`。可以参考 `references/source-manifest.example.json` 为它们补充来源 URL。默认策略不会自动覆盖这些 skill；发现上游后只会生成 `git clone --depth 1 ... _review_<skill>` 命令，便于人工比对后再决定是否合并。

## 开发验证

```bash
python -m pytest -q
PYTHONUTF8=1 python C:\Users\pc\.codex\skills\.system\skill-creator\scripts\quick_validate.py E:\VISUAL_code\Skill-Maintainer
python scripts/run_audit.py --codex-home C:\Users\pc\.codex --output outputs\smoke --update-policy report-only
```

## License

MIT
