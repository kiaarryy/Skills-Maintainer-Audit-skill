from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

INSTALL_INFO_FILE = ".skill-install-info.json"


def read_install_info(skill_dir: Path) -> dict[str, Any] | None:
    path = skill_dir / INSTALL_INFO_FILE
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def write_install_info(
    skill_dir: Path,
    source_url: str,
    confidence: str,
    method: str,
    commit: str | None = None,
) -> None:
    existing = read_install_info(skill_dir) or {}
    existing.update(
        {
            "source_url": source_url,
            "confidence": confidence,
            "discovery_method": method,
            "discovered_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    if commit:
        existing["commit"] = commit
    path = skill_dir / INSTALL_INFO_FILE
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def source_from_install_info(skill_name: str, skill_dir: Path) -> tuple[str, str, str, str | None] | None:
    """Return (url, source_type, confidence, commit) or None."""
    info = read_install_info(skill_dir)
    if not info or not info.get("source_url"):
        return None
    return (
        info["source_url"],
        "install_info_file",
        info.get("confidence", "medium"),
        info.get("commit"),
    )


def generate_review_command(skill_dir: Path, source_url: str) -> str:
    """Generate a non-destructive command that stages upstream content for review."""
    review_dir = skill_dir.resolve().parent / f"_review_{skill_dir.name}"
    return f'git clone --depth 1 "{source_url}" "{review_dir}"'


def generate_reinstall_command(skill_dir: Path, source_url: str) -> str:
    """Backward-compatible name for the safer review command."""
    return generate_review_command(skill_dir, source_url)
