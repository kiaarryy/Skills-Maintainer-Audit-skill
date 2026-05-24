from __future__ import annotations

import subprocess
from pathlib import Path

from skill_maintainer_audit.git_update import inspect_or_update
from skill_maintainer_audit.models import SkillRecord


def make_record(path: Path, name: str = "demo-skill") -> SkillRecord:
    return SkillRecord(
        name=name,
        folder_name=name,
        path=str(path),
        description="demo",
        category="agent-ops",
        summary="demo",
        is_git=(path / ".git").exists(),
    )


def test_non_git_needs_manual_review(tmp_path: Path) -> None:
    action = inspect_or_update(make_record(tmp_path), "safe")
    assert action.status == "needs_manual_review"


def test_clean_git_is_eligible_in_report_only(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    (repo / "SKILL.md").write_text("---\nname: demo-skill\ndescription: demo local skill for tests.\n---\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "SKILL.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(repo)], check=True)

    action = inspect_or_update(make_record(repo), "report-only")
    assert action.status == "eligible"

