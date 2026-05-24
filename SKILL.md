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
   - Safe maintenance with Git fast-forward:
     `python scripts/run_audit.py --codex-home <codex-home> --output outputs/latest --update-policy safe`
   - Full discovery (network): add `--github-search` to search GitHub for skills without a known source URL.
   - Persist discovered sources: add `--write-install-info` to write `.skill-install-info.json` into each skill folder so future runs skip the search step.

3. Preserve safety boundaries.
   - Safe update only fast-forwards clean Git skill folders.
   - Non-Git skills are never overwritten automatically. `manual_update_commands.md` contains registry install commands when available and Git clone review commands for source-known non-Git skills.
   - Never delete skills, archives, logs, outputs, or generated reports.

4. Understand update statuses.
   | Status | Meaning | Action |
   |---|---|---|
   | `updated` | Git skill fast-forwarded | ✅ Done |
   | `up_to_date` | Git skill already at latest | ✅ Done |
   | `non_git_updateable` | Source URL confirmed + upstream HEAD fetched | Clone upstream to `_review_*`, compare, then apply manually |
   | `outdated_source_detected` | Vendored commit differs from upstream | Clone upstream to `_review_*`, compare, then apply manually |
   | `non_git_no_baseline` | Source URL found but upstream unreachable | Check network / URL validity |
   | `unknown_source` | No source URL discovered | Run with `--github-search` or add to source manifest |
   | `dirty_git` | Git skill has local changes | Review and commit or stash changes first |

5. Inspect results.
   - Open `outputs/latest/report.html` for the visual dashboard.
   - Check the registry and Git clone review sections for non-Git skills that need human-controlled updates.
   - Use JSON files for automation: `skills_inventory.json`, `usage_7d_30d.json`, `update_actions.json`, and `duplicates.json`.
   - `source_manifest_draft.json` is auto-generated with all discovered sources; rename to `source_manifest.json` and pass with `--source-manifest` to make sources permanent.

6. Act on findings.
   - For low-risk skill metadata issues, patch the relevant `SKILL.md` or `agents/openai.yaml`, then validate with the local skill validator.
   - For `unknown_source` skills: run `--github-search --write-install-info` once to discover and persist sources. Review `source_manifest_draft.json` before committing.
   - For `non_git_updateable` skills: run the Git clone review command from `manual_update_commands.md`, compare the `_review_*` copy with the installed skill, then apply selected changes manually.
   - For duplicate skills, keep the one that is used more often, better maintained, or project-specific; archive only after explicit user approval.

7. Validate before completion.
   - Run `PYTHONUTF8=1 python C:\Users\pc\.codex\skills\.system\skill-creator\scripts\quick_validate.py <skill-folder>` on the changed skill.
   - Run `python -m pytest -q` when changing this project.
   - Run a report-only smoke test after CLI changes.

## Output Contract

The CLI writes a complete, timestamped maintenance snapshot to the selected output directory:

- `report.html`: visual dashboard — includes registry actions and Git clone review fallback sections.
- `skills_inventory.json`: installed skills, metadata, categories, sources, and structural issues.
- `source_candidates.json`: discovered GitHub or manifest-based source candidates with confidence.
- `usage_7d_30d.json`: parsed trigger evidence for 7-day and 30-day windows.
- `update_actions.json`: safe update results and manual-review reasons.
- `duplicates.json`: overlapping capability groups.
- `manual_update_commands.md`: registry update commands plus non-destructive Git clone review commands for source-known non-Git skills.
- `source_manifest_draft.json`: auto-generated; all discovered sources ready for review and reuse.

## Source Discovery Priority

The audit discovers source URLs in this priority order:
1. `--source-manifest` file (user-provided, highest trust)
2. `.skill-install-info.json` in the skill folder (persisted from a previous `--write-install-info` run)
3. Local `.git/config` origin remote (git-backed skills)
4. `manifest.json` `source_repositories` field
5. `package.json` `repository` field
6. GitHub URLs embedded in `README.md`, `AGENTS.md`, or `SKILL.md`
7. GitHub API search (opt-in with `--github-search`)

## References

- `references/source-manifest.example.json`: how to register source URLs for non-Git skills.
- `references/automation-prompt.md`: suggested recurring automation prompt.
