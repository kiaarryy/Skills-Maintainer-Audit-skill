from __future__ import annotations

import json
import subprocess
from pathlib import Path

from skill_maintainer_audit.sources import discover_source


def test_discover_git_remote(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", "https://github.com/example/demo.git"], check=True)

    source = discover_source(repo, "demo", {})
    assert source
    assert source.url == "https://github.com/example/demo.git"
    assert source.source_type == "git_remote"


def test_discover_manifest_source_repositories(tmp_path: Path) -> None:
    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "manifest.json").write_text(
        json.dumps({"source_repositories": [{"url": "https://github.com/example/ars.git", "commit": "abc123"}]}),
        encoding="utf-8",
    )

    source = discover_source(skill, "skill", {})
    assert source
    assert source.url == "https://github.com/example/ars.git"
    assert source.commit == "abc123"
    assert source.confidence == "high"


def test_discover_package_repository(tmp_path: Path) -> None:
    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "package.json").write_text(
        json.dumps({"repository": {"url": "git+https://github.com/example/pkg.git"}}),
        encoding="utf-8",
    )

    source = discover_source(skill, "skill", {})
    assert source
    assert source.url == "https://github.com/example/pkg.git"
    assert source.source_type == "package_json"


def test_discover_readme_url(tmp_path: Path) -> None:
    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "README.md").write_text("Installed from https://github.com/example/readme-skill", encoding="utf-8")

    source = discover_source(skill, "skill", {})
    assert source
    assert source.url == "https://github.com/example/readme-skill.git"
    assert source.confidence == "low"


def test_no_source(tmp_path: Path) -> None:
    assert discover_source(tmp_path, "missing", {}) is None

