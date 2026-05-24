from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .duplicates import find_duplicates
from .git_update import update_skills
from .install_info import write_install_info
from .inventory import inventory_skills
from .report import render_manual_update_commands, render_report, write_json
from .usage import analyze_usage


def default_codex_home() -> Path:
    env_home = os.environ.get("CODEX_HOME")
    if env_home:
        return Path(env_home).expanduser()
    return Path.home() / ".codex"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit, update, classify, and visualize local AI agent skills.")
    subparsers = parser.add_subparsers(dest="command")

    audit = subparsers.add_parser("audit", help="Run a full skill maintenance audit")
    audit.add_argument("--codex-home", type=Path, default=default_codex_home(), help="Codex home directory")
    audit.add_argument("--skills-root", type=Path, default=None, help="Installed skills root")
    audit.add_argument("--output", type=Path, default=Path("outputs/latest"), help="Output directory")
    audit.add_argument("--update-policy", choices=["report-only", "dry-run", "safe"], default="report-only")
    audit.add_argument("--include-system", action="store_true", help="Include .system skills")
    audit.add_argument("--source-manifest", type=Path, default=None, help="Optional source manifest JSON")
    audit.add_argument(
        "--registry-search",
        action="store_true",
        default=False,
        help="Search skills.sh registry for each skill — authoritative source for npx skills add commands",
    )
    audit.add_argument(
        "--github-search",
        action="store_true",
        default=False,
        help="Search GitHub API for source URLs of skills not found on skills.sh registry",
    )
    audit.add_argument(
        "--write-install-info",
        action="store_true",
        default=False,
        help="Persist discovered source URLs into each skill directory as .skill-install-info.json",
    )

    parser.set_defaults(command="audit")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command != "audit":
        parser.error("unknown command")

    codex_home = args.codex_home.expanduser().resolve()
    skills_root = (args.skills_root or codex_home / "skills").expanduser().resolve()
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    if not skills_root.exists():
        parser.error(f"skills root does not exist: {skills_root}")

    generated_at = datetime.now(timezone.utc)
    records = inventory_skills(
        skills_root,
        include_system=args.include_system,
        source_manifest_path=args.source_manifest,
        enable_github_search=args.github_search,
        enable_registry_search=args.registry_search,
    )
    usage = analyze_usage(codex_home, records, now=generated_at)
    updates = update_skills(records, args.update_policy)
    duplicates = find_duplicates(records)
    annotate_similarities(records, duplicates)
    source_candidates = [
        {
            "skill": record.name,
            "url": record.source_url,
            "source_type": record.source_type,
            "confidence": record.source_confidence,
            "commit": record.source_commit,
        }
        for record in records
        if record.source_url
    ]

    # Persist discovered sources into each skill dir so future runs skip the search step
    if args.write_install_info:
        _write_install_info_files(records)

    # Auto-draft source manifest for all skills with discovered sources
    _write_source_manifest_draft(output, records)

    write_json(output / "skills_inventory.json", [record.to_dict() for record in records])
    write_json(output / "source_candidates.json", source_candidates)
    write_json(output / "usage_7d_30d.json", [item.to_dict() for item in usage])
    write_json(output / "update_actions.json", [item.to_dict() for item in updates])
    write_json(output / "duplicates.json", [item.to_dict() for item in duplicates])
    render_manual_update_commands(output / "manual_update_commands.md", updates)
    from collections import Counter as _Counter
    status_summary = dict(_Counter(a.status for a in updates))
    output_files = [
        "report.html",
        "skills_inventory.json",
        "source_candidates.json",
        "usage_7d_30d.json",
        "update_actions.json",
        "duplicates.json",
        "manual_update_commands.md",
    ]
    if (output / "source_manifest_draft.json").exists():
        output_files.append("source_manifest_draft.json")

    registry_count = sum(1 for r in records if r.registry_source)
    registry_updateable = [a for a in updates if a.status == "registry_updateable"]

    write_json(
        output / "run_summary.json",
        {
            "generated_at": generated_at.isoformat(),
            "codex_home": str(codex_home),
            "skills_root": str(skills_root),
            "update_policy": args.update_policy,
            "registry_search_enabled": args.registry_search,
            "github_search_enabled": args.github_search,
            "write_install_info": args.write_install_info,
            "skill_count": len(records),
            "registry_count": registry_count,
            "source_discovered_count": sum(1 for r in records if r.source_url),
            "issue_count": sum(len(record.issues) for record in records),
            "duplicate_group_count": len(duplicates),
            "status_summary": status_summary,
            "output_files": output_files,
        },
    )
    render_report(output / "report.html", records, usage, updates, duplicates, generated_at)

    # Print a clean, readable summary (not just JSON)
    _print_action_summary(records, usage, updates, duplicates, output)
    return 0


def _print_action_summary(records, usage, updates, duplicates, output) -> None:
    from collections import Counter as _Counter
    registry_updateable = [a for a in updates if a.status == "registry_updateable"]
    non_git_updateable = [a for a in updates if a.status == "non_git_updateable"]
    unknown = [a for a in updates if a.status == "unknown_source"]
    unused_30d = [u for u in usage if u.count_30d == 0]

    lines = [
        "",
        f"  Skill Audit Complete — {len(records)} skills",
        "  " + "─" * 48,
    ]
    if registry_updateable:
        lines.append(f"  [{len(registry_updateable):3}] on skills.sh registry  → npx skills add  (see manual_update_commands.md)")
    if non_git_updateable:
        lines.append(f"  [{len(non_git_updateable):3}] non-git source known   → git clone review (see manual_update_commands.md)")
    if unknown:
        lines.append(f"  [{len(unknown):3}] source unknown          → run with --registry-search to discover")
    if unused_30d:
        lines.append(f"  [{len(unused_30d):3}] unused in 30 days       → review candidates")
    if duplicates:
        lines.append(f"  [{len(duplicates):3}] duplicate groups         → overlapping capabilities")
    lines += [
        "  " + "─" * 48,
        f"  Report: {output / 'report.html'}",
        f"  Actions: {output / 'manual_update_commands.md'}",
        "",
    ]
    print("\n".join(lines))


def annotate_similarities(records, duplicates) -> None:
    by_name = {record.name: record for record in records}
    for group in duplicates:
        for name in group.skills:
            record = by_name.get(name)
            if record:
                record.similar_to = [other for other in group.skills if other != name]


def _write_install_info_files(records) -> None:
    from pathlib import Path

    for record in records:
        if not record.source_url:
            continue
        # Never write install info into git-backed skills — they already have
        # a .git directory that tracks provenance. Writing here would dirty the tree.
        if record.is_git:
            continue
        skill_dir = Path(record.path)
        try:
            write_install_info(
                skill_dir,
                source_url=record.source_url,
                confidence=record.source_confidence or "low",
                method=record.source_type or "unknown",
                commit=record.source_commit,
            )
        except OSError:
            pass


def _write_source_manifest_draft(output, records) -> None:
    from pathlib import Path

    draft_skills = []
    for record in records:
        if not record.source_url:
            continue
        entry: dict = {
            "name": record.name,
            "path": record.path,
            "source_url": record.source_url,
            "confidence": record.source_confidence,
            "discovery_method": record.source_type,
        }
        if record.source_commit:
            entry["commit"] = record.source_commit
        draft_skills.append(entry)

    if draft_skills:
        write_json(
            output / "source_manifest_draft.json",
            {
                "version": 1,
                "_note": "Auto-generated draft. Review and rename to source_manifest.json to use with --source-manifest.",
                "skills": draft_skills,
            },
        )
