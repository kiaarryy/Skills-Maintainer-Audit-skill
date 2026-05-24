from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from .models import SourceCandidate

GITHUB_RE = re.compile(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?", re.I)


def normalize_github_url(url: str) -> str:
    clean = url.strip().rstrip("/).,;'\"")
    clean = clean.split("/tree/")[0].split("/blob/")[0]
    if clean.lower().startswith("https://github.com/") and not clean.lower().endswith(".git"):
        clean += ".git"
    return clean


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


def discover_source(skill_dir: Path, skill_name: str, source_manifest: dict[str, dict[str, Any]]) -> SourceCandidate | None:
    manifest_record = source_manifest.get(skill_name) or source_manifest.get(skill_dir.name)
    if manifest_record and manifest_record.get("source_url"):
        return SourceCandidate(
            skill=skill_name,
            url=normalize_github_url(str(manifest_record["source_url"])),
            source_type="source_manifest",
            confidence="high",
            detail="Configured in source manifest.",
            commit=as_optional_str(manifest_record.get("commit")),
        )

    if (skill_dir / ".git").exists():
        remote = git_remote(skill_dir)
        if remote:
            return SourceCandidate(skill_name, normalize_github_url(remote), "git_remote", "high", "Git origin remote.")

    manifest_candidate = from_manifest_json(skill_dir, skill_name)
    if manifest_candidate:
        return manifest_candidate

    package_candidate = from_package_json(skill_dir, skill_name)
    if package_candidate:
        return package_candidate

    text_candidate = from_text_files(skill_dir, skill_name)
    if text_candidate:
        return text_candidate

    return None


def git_remote(skill_dir: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(skill_dir), "remote", "get-url", "origin"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def from_manifest_json(skill_dir: Path, skill_name: str) -> SourceCandidate | None:
    path = skill_dir / "manifest.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None
    repos = data.get("source_repositories")
    if isinstance(repos, list) and repos:
        first = next((repo for repo in repos if isinstance(repo, dict) and repo.get("url")), None)
        if first:
            return SourceCandidate(
                skill=skill_name,
                url=normalize_github_url(str(first["url"])),
                source_type="manifest_json",
                confidence="high",
                detail="Found in manifest.json source_repositories.",
                commit=as_optional_str(first.get("commit")),
            )
    for key in ("source_url", "repository", "repo", "url"):
        if data.get(key):
            return SourceCandidate(skill_name, normalize_github_url(str(data[key])), "manifest_json", "medium", f"Found manifest.json {key}.")
    return None


def from_package_json(skill_dir: Path, skill_name: str) -> SourceCandidate | None:
    path = skill_dir / "package.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None
    repo = data.get("repository")
    url = None
    if isinstance(repo, dict):
        url = repo.get("url")
    elif isinstance(repo, str):
        url = repo
    if not url:
        return None
    url = str(url).replace("git+", "")
    if url.startswith("git@github.com:"):
        url = "https://github.com/" + url.split(":", 1)[1]
    return SourceCandidate(skill_name, normalize_github_url(url), "package_json", "medium", "Found in package.json repository.")


def from_text_files(skill_dir: Path, skill_name: str) -> SourceCandidate | None:
    for name in ("README.md", "AGENTS.md", "SKILL.md"):
        path = skill_dir / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")[:50000]
        matches = [normalize_github_url(match.group(0)) for match in GITHUB_RE.finditer(text)]
        if matches:
            return SourceCandidate(skill_name, matches[0], f"{name.lower()}_url", "low", f"Found GitHub URL in {name}.")
    return None


def as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

