# Skill Maintainer Audit Skill

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Skill](https://img.shields.io/badge/AI%20Agent-Skill-blue.svg)](SKILL.md)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](pyproject.toml)

> 中文版本: [README.md](README.md)

Skill Maintainer Audit is an AI-agent skill for maintaining large local skill collections. It audits installed skills, safely updates Git-backed skills, analyzes 7-day and 30-day usage evidence, classifies capabilities, detects overlapping skills, and generates a single-file HTML dashboard.

## Quick Start

```bash
git clone https://github.com/kiaarryy/Skills-Maintainer-Audit-skill.git ~/.codex/skills/skill-maintainer-audit
cd ~/.codex/skills/skill-maintainer-audit
python scripts/run_audit.py --codex-home ~/.codex --output outputs/latest --update-policy report-only
```

To update the installed skill:

```bash
cd ~/.codex/skills/skill-maintainer-audit
git pull --ff-only
```

After installation, ask your agent:

```text
Use $skill-maintainer-audit to audit my local skills, show 7-day and 30-day usage, find duplicates, and generate a dashboard.
```

## Features

- Safe updates: only clean Git skill folders are eligible for fast-forward updates.
- Usage analytics: extracts 7-day and 30-day trigger evidence from local Codex sessions, session index files, and automation memories.
- Skill inventory: records metadata, file structure, categories, and structural issues.
- Duplicate detection: groups skills with similar names, descriptions, and capability keywords.
- Visual reporting: writes `report.html` with KPI cards, charts, usage tables, unused skills, duplicate groups, and manual-review lists.
- Automation-ready outputs: writes JSON files alongside the HTML dashboard.

## Good Fit / Poor Fit

Good fit:

- You have many locally installed skills from different sources.
- You want to know which skills are actually used.
- You need evidence before cleaning up or consolidating overlapping skills.
- You want a recurring maintenance dashboard.

Poor fit:

- You want to forcibly overwrite or delete local skills.
- You expect non-Git skills with unknown sources to be automatically updated.
- You need exact internal platform trigger counts. This tool reports locally parseable evidence only.

## Commands

Read-only audit:

```bash
python scripts/run_audit.py --codex-home ~/.codex --output outputs/latest --update-policy report-only
```

Safe update:

```bash
python scripts/run_audit.py --codex-home ~/.codex --skills-root ~/.codex/skills --output outputs/latest --update-policy safe
```

Windows Codex example:

```powershell
python scripts/run_audit.py --codex-home C:\Users\pc\.codex --output outputs\latest --update-policy safe
```

## Outputs

- `outputs/latest/report.html`: visual dashboard.
- `outputs/latest/skills_inventory.json`: inventory, categories, structural issues, and source metadata.
- `outputs/latest/usage_7d_30d.json`: usage evidence for 7-day and 30-day windows.
- `outputs/latest/update_actions.json`: update statuses and manual-review reasons.
- `outputs/latest/duplicates.json`: similar or overlapping skill groups.

## Automation

Suggested recurring automation prompt:

```text
Use $skill-maintainer-audit from E:\VISUAL_code\Skill-Maintainer to run the local skill maintenance CLI against C:\Users\pc\.codex. Use safe update mode. Generate outputs/latest/report.html plus JSON outputs, summarize updated skills, manual-review items, 7-day and 30-day usage, duplicate groups, validation results, and any logs that could not be parsed.
```

## Source Manifest

Many installed skills are copied rather than Git-cloned. They cannot be safely updated with `git pull`. Use `references/source-manifest.example.json` to document source URLs for manual review or future reinstall workflows.

## Development Checks

```bash
python -m pytest -q
PYTHONUTF8=1 python C:\Users\pc\.codex\skills\.system\skill-creator\scripts\quick_validate.py E:\VISUAL_code\Skill-Maintainer
python scripts/run_audit.py --codex-home C:\Users\pc\.codex --output outputs\smoke --update-policy report-only
```

## License

MIT

