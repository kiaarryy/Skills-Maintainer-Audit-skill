---
name: skill-maintainer-audit
description: Maintain local AI agent skills by auditing installed Skill folders, safely updating Git-backed skills, analyzing 7-day and 30-day skill usage from local Codex logs, classifying capabilities, finding duplicate or overlapping skills, and generating visual maintenance reports.
---

# Skill Maintainer Audit

Use this skill when the user asks to maintain, update, audit, classify, deduplicate, or report on locally installed AI agent skills. Prefer the bundled CLI for repeated work and automation.

## Workflow

1. Identify scope.
   - Default Codex home: `$CODEX_HOME`, then `~/.codex`.
   - Default skills root: `<codex-home>/skills`.
   - Include `.system` skills only when explicitly requested.

2. Run the audit CLI.
   - Read-only report:
     `python scripts/run_audit.py --codex-home <codex-home> --output outputs/latest --update-policy report-only`
   - Safe maintenance:
     `python scripts/run_audit.py --codex-home <codex-home> --skills-root <skills-root> --output outputs/latest --update-policy safe`

3. Preserve safety boundaries.
   - Safe update only fast-forwards clean Git skill folders.
   - Dirty Git folders, non-Git folders, missing remotes, conflicts, unknown source folders, and local-only skills are reported for manual review.
   - Never delete skills, archives, logs, outputs, or generated reports.

4. Inspect results.
   - Open `outputs/latest/report.html` for the visual dashboard.
   - Use JSON files for automation: `skills_inventory.json`, `usage_7d_30d.json`, `update_actions.json`, and `duplicates.json`.

5. Act on findings.
   - For low-risk skill metadata issues, patch the relevant `SKILL.md` or `agents/openai.yaml`, then validate with the local skill validator.
   - For unknown-source skills, add source metadata using `references/source-manifest.example.json` as the template before expecting updates.
   - For duplicate skills, keep the one that is used more often, better maintained, or project-specific; archive only after explicit user approval.

6. Validate before completion.
   - Run `PYTHONUTF8=1 python C:\Users\pc\.codex\skills\.system\skill-creator\scripts\quick_validate.py <skill-folder>` on the changed skill.
   - Run `python -m pytest -q` when changing this project.
   - Run a report-only smoke test after CLI changes.

## Output Contract

The CLI writes a complete, timestamped maintenance snapshot to the selected output directory:

- `report.html`: visual dashboard for people.
- `skills_inventory.json`: installed skills, metadata, categories, sources, and structural issues.
- `source_candidates.json`: discovered GitHub or manifest-based source candidates with confidence.
- `usage_7d_30d.json`: parsed trigger evidence for 7-day and 30-day windows.
- `update_actions.json`: safe update results and manual-review reasons.
- `duplicates.json`: overlapping capability groups.
- `manual_update_commands.md`: advisory update notes for copied or vendored non-Git skills.

## References

- `references/source-manifest.example.json`: how to register source URLs for non-Git skills.
- `references/automation-prompt.md`: suggested recurring automation prompt.
