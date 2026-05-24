from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .duplicates import find_duplicates
from .git_update import update_skills
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
    records = inventory_skills(skills_root, include_system=args.include_system, source_manifest_path=args.source_manifest)
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

    write_json(output / "skills_inventory.json", [record.to_dict() for record in records])
    write_json(output / "source_candidates.json", source_candidates)
    write_json(output / "usage_7d_30d.json", [item.to_dict() for item in usage])
    write_json(output / "update_actions.json", [item.to_dict() for item in updates])
    write_json(output / "duplicates.json", [item.to_dict() for item in duplicates])
    render_manual_update_commands(output / "manual_update_commands.md", updates)
    write_json(
        output / "run_summary.json",
        {
            "generated_at": generated_at.isoformat(),
            "codex_home": str(codex_home),
            "skills_root": str(skills_root),
            "update_policy": args.update_policy,
            "skill_count": len(records),
            "issue_count": sum(len(record.issues) for record in records),
            "duplicate_group_count": len(duplicates),
            "output_files": [
                "report.html",
                "skills_inventory.json",
                "source_candidates.json",
                "usage_7d_30d.json",
                "update_actions.json",
                "duplicates.json",
                "manual_update_commands.md",
            ],
        },
    )
    render_report(output / "report.html", records, usage, updates, duplicates, generated_at)

    print(json.dumps({"status": "ok", "skills": len(records), "output": str(output)}, ensure_ascii=False))
    return 0


def annotate_similarities(records, duplicates) -> None:
    by_name = {record.name: record for record in records}
    for group in duplicates:
        for name in group.skills:
            record = by_name.get(name)
            if record:
                record.similar_to = [other for other in group.skills if other != name]
