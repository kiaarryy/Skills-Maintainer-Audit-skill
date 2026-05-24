from __future__ import annotations

from pathlib import Path

from skill_maintainer_audit.inventory import inventory_skills, parse_frontmatter


def test_parse_frontmatter() -> None:
    data = parse_frontmatter("---\nname: demo\ndescription: Use for testing local skills.\n---\n# Demo\n")
    assert data["name"] == "demo"
    assert data["description"].startswith("Use for")


def test_inventory_detects_skill(tmp_path: Path) -> None:
    skill = tmp_path / "demo-skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: Use when auditing demo local skills with enough trigger detail for realistic maintenance workflows.\n---\n# Demo\n",
        encoding="utf-8",
    )
    records = inventory_skills(tmp_path)
    assert len(records) == 1
    assert records[0].name == "demo-skill"
    assert records[0].issues == []
