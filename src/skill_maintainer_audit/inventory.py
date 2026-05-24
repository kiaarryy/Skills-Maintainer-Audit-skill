from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import SkillRecord

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
VALID_NAME_RE = re.compile(r"^[a-z0-9-]+$")

CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("research", ("research", "paper", "academic", "nature", "figure", "manuscript", "literature")),
    ("documents", ("pdf", "docx", "pptx", "xlsx", "document", "slides", "spreadsheet")),
    ("frontend-design", ("frontend", "design", "html", "ui", "css", "visual", "canvas", "image", "art")),
    ("browser-qa", ("browser", "playwright", "qa", "test", "scrape", "webapp")),
    ("development", ("code", "git", "github", "review", "debug", "test-driven", "worktree", "ship")),
    ("automation-ops", ("automation", "monitor", "canary", "deploy", "netlify", "health", "benchmark")),
    ("agent-ops", ("agent", "skill", "codex", "context", "plan", "memory", "instructions")),
    ("safety-maintenance", ("guard", "careful", "cleanup", "security", "audit", "safe")),
    ("communication", ("gmail", "slack", "comms", "email", "inbox")),
]


def parse_frontmatter(text: str) -> dict[str, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    data: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip("\"'")
    return data


def load_source_manifest(path: Path | None) -> dict[str, dict[str, Any]]:
    if not path or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    records = data.get("skills", [])
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        name = str(record.get("name", "")).strip()
        if name:
            result[name] = record
    return result


def iter_skill_dirs(root: Path, include_system: bool = False) -> list[Path]:
    if (root / "SKILL.md").exists():
        return [root]
    if not root.exists():
        return []
    skill_dirs: list[Path] = []
    for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir():
            continue
        if child.name == ".system":
            if include_system:
                skill_dirs.extend(iter_skill_dirs(child, include_system=True))
            continue
        if (child / "SKILL.md").exists():
            skill_dirs.append(child)
    return skill_dirs


def categorize(name: str, description: str, body: str) -> str:
    haystack = f"{name} {description} {body[:2000]}".lower()
    for category, keywords in CATEGORY_KEYWORDS:
        if any(keyword in haystack for keyword in keywords):
            return category
    return "other"


def summarize(description: str, body: str) -> str:
    if description:
        return description.strip()
    for line in body.splitlines():
        stripped = line.strip(" #")
        if len(stripped) > 24:
            return stripped[:220]
    return "No summary available."


def audit_skill(skill_dir: Path, source_manifest: dict[str, dict[str, Any]] | None = None) -> SkillRecord:
    source_manifest = source_manifest or {}
    skill_file = skill_dir / "SKILL.md"
    issues: list[str] = []
    text = ""
    frontmatter: dict[str, str] = {}
    if skill_file.exists():
        text = skill_file.read_text(encoding="utf-8", errors="replace")
        frontmatter = parse_frontmatter(text)
    else:
        issues.append("missing SKILL.md")

    name = frontmatter.get("name") or skill_dir.name
    description = frontmatter.get("description", "")
    body = FRONTMATTER_RE.sub("", text, count=1)
    extra_keys = sorted(set(frontmatter) - {"name", "description"})

    if skill_file.exists() and not frontmatter:
        issues.append("missing or invalid YAML frontmatter")
    if extra_keys:
        issues.append(f"frontmatter has extra keys: {', '.join(extra_keys)}")
    if not frontmatter.get("name"):
        issues.append("missing frontmatter name")
    elif frontmatter["name"] != skill_dir.name:
        issues.append(f"name '{frontmatter['name']}' does not match folder '{skill_dir.name}'")
    if name and not VALID_NAME_RE.match(name):
        issues.append("name is not lowercase hyphen-case")
    if not description:
        issues.append("missing frontmatter description")
    elif len(description.split()) < 12:
        issues.append("description may be too vague for reliable triggering")
    if "TODO" in text or "[TODO" in text:
        issues.append("contains TODO placeholder text")
    if text.count("\n") > 500:
        issues.append("SKILL.md is over 500 lines; consider moving details to references")

    openai_yaml = skill_dir / "agents" / "openai.yaml"
    scripts_dir = skill_dir / "scripts"
    references_dir = skill_dir / "references"
    assets_dir = skill_dir / "assets"
    if openai_yaml.exists():
        yaml_text = openai_yaml.read_text(encoding="utf-8", errors="replace")
        if "$" + skill_dir.name not in yaml_text:
            issues.append("agents/openai.yaml default_prompt may not mention the skill")

    source = source_manifest.get(name) or source_manifest.get(skill_dir.name) or {}
    remote = source.get("source_url")
    if not remote and (skill_dir / ".git").exists():
        remote = None

    return SkillRecord(
        name=name,
        folder_name=skill_dir.name,
        path=str(skill_dir.resolve()),
        description=description,
        category=categorize(name, description, body),
        summary=summarize(description, body),
        is_git=(skill_dir / ".git").exists(),
        source_url=remote,
        install_method=source.get("install_method"),
        issues=issues,
        files={
            "SKILL.md": skill_file.exists(),
            "agents/openai.yaml": openai_yaml.exists(),
            "scripts": scripts_dir.exists(),
            "references": references_dir.exists(),
            "assets": assets_dir.exists(),
        },
    )


def inventory_skills(skills_root: Path, include_system: bool = False, source_manifest_path: Path | None = None) -> list[SkillRecord]:
    manifest = load_source_manifest(source_manifest_path)
    return [audit_skill(path, manifest) for path in iter_skill_dirs(skills_root, include_system=include_system)]

