from __future__ import annotations

from pathlib import Path

from skill_maintainer_audit.install_info import (
    generate_reinstall_command,
    generate_review_command,
    read_install_info,
    source_from_install_info,
    write_install_info,
)


def test_write_and_read_install_info(tmp_path: Path) -> None:
    write_install_info(tmp_path, "https://github.com/example/skill.git", "medium", "github_search_exact")
    info = read_install_info(tmp_path)
    assert info is not None
    assert info["source_url"] == "https://github.com/example/skill.git"
    assert info["confidence"] == "medium"
    assert info["discovery_method"] == "github_search_exact"
    assert "discovered_at" in info


def test_write_install_info_with_commit(tmp_path: Path) -> None:
    write_install_info(tmp_path, "https://github.com/example/skill.git", "high", "git_remote", commit="abc123")
    info = read_install_info(tmp_path)
    assert info is not None
    assert info["commit"] == "abc123"


def test_write_install_info_preserves_existing_fields(tmp_path: Path) -> None:
    (tmp_path / ".skill-install-info.json").write_text('{"custom_field": "keep_me"}', encoding="utf-8")
    write_install_info(tmp_path, "https://github.com/example/skill.git", "low", "text_scan")
    info = read_install_info(tmp_path)
    assert info is not None
    assert info.get("custom_field") == "keep_me"


def test_read_install_info_missing(tmp_path: Path) -> None:
    assert read_install_info(tmp_path) is None


def test_source_from_install_info(tmp_path: Path) -> None:
    write_install_info(tmp_path, "https://github.com/example/skill.git", "medium", "github_search_exact", commit="deadbeef")
    result = source_from_install_info("my-skill", tmp_path)
    assert result is not None
    url, stype, conf, commit = result
    assert url == "https://github.com/example/skill.git"
    assert stype == "install_info_file"
    assert conf == "medium"
    assert commit == "deadbeef"


def test_source_from_install_info_missing(tmp_path: Path) -> None:
    assert source_from_install_info("my-skill", tmp_path) is None


def test_generate_review_command_is_non_destructive(tmp_path: Path) -> None:
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    cmd = generate_review_command(skill_dir, "https://github.com/example/skill.git")
    assert "git clone --depth 1" in cmd
    assert "https://github.com/example/skill.git" in cmd
    assert "_review_my-skill" in cmd
    blocked_tokens = ("robocopy", "rsync", "rm -rf", "rd /s", "Remove-Item", "rmdir /s")
    assert not any(token in cmd for token in blocked_tokens)


def test_generate_reinstall_command_legacy_name_is_safe(tmp_path: Path) -> None:
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    cmd = generate_reinstall_command(skill_dir, "https://github.com/example/skill.git")
    assert cmd == generate_review_command(skill_dir, "https://github.com/example/skill.git")
