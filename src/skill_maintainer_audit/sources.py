from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .models import SourceCandidate

GITHUB_RE = re.compile(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?", re.I)

_GITHUB_API_BASE = "https://api.github.com"
_github_search_cache: dict[str, SourceCandidate | None] = {}
_last_github_request_time: float = 0.0


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


def github_search(skill_name: str, description: str = "", enable: bool = False) -> SourceCandidate | None:
    """Search GitHub for a repository matching the skill name.

    Requires enable=True (passed via CLI flag) or GITHUB_SEARCH=1 env var.
    Respects rate limits with a 1-second minimum gap between requests.
    Uses GITHUB_TOKEN if set for higher rate limits.
    """
    if not enable and not os.environ.get("GITHUB_SEARCH"):
        return None
    if skill_name in _github_search_cache:
        return _github_search_cache[skill_name]

    global _last_github_request_time
    elapsed = time.time() - _last_github_request_time
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)

    token = os.environ.get("GITHUB_TOKEN", "")
    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "skill-maintainer-audit/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    query = urllib.parse.quote(skill_name)
    url = f"{_GITHUB_API_BASE}/search/repositories?q={query}+in:name&per_page=5&sort=stars"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        _last_github_request_time = time.time()
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        _last_github_request_time = time.time()
        _github_search_cache[skill_name] = None
        return None

    items = data.get("items", [])
    candidate = None
    for item in items:
        repo_name = item.get("name", "").lower()
        repo_desc = (item.get("description") or "").lower()
        repo_topics = [t.lower() for t in (item.get("topics") or [])]
        is_skill_related = _is_skill_related(repo_desc, repo_topics)
        exact = repo_name == skill_name.lower()
        fuzzy = not exact and _name_fuzzy_match(skill_name, repo_name)

        if exact and is_skill_related:
            # Exact name match AND the repo is clearly AI/skill related
            candidate = SourceCandidate(
                skill=skill_name,
                url=normalize_github_url(item["clone_url"]),
                source_type="github_search_exact",
                confidence="medium",
                detail=f"GitHub search exact name + skill-related: {item['full_name']}",
            )
            break
        if exact and not is_skill_related and not candidate:
            # Exact name match but no skill signal — mark as "unverified"
            # Do NOT immediately accept; keep looking for skill-related match
            candidate = SourceCandidate(
                skill=skill_name,
                url=normalize_github_url(item["clone_url"]),
                source_type="github_search_name_only",
                confidence="unverified",
                detail=f"Name match only, no AI/skill signal — verify before using: {item['full_name']}",
            )
        if fuzzy and is_skill_related and not candidate:
            # Fuzzy match with skill signal
            candidate = SourceCandidate(
                skill=skill_name,
                url=normalize_github_url(item["clone_url"]),
                source_type="github_search_fuzzy",
                confidence="low",
                detail=f"GitHub search fuzzy + skill-related: {item['full_name']}",
            )

    _github_search_cache[skill_name] = candidate
    return candidate


def github_search_family(prefix: str, skill_name: str, enable: bool = False) -> SourceCandidate | None:
    """Search GitHub for a family/parent repo using a skill name prefix.

    Used for skill families like cheat-bump, cheat-init → searches for 'cheat'.
    """
    if not enable and not os.environ.get("GITHUB_SEARCH"):
        return None

    cache_key = f"__family__{prefix}"
    if cache_key in _github_search_cache:
        cached = _github_search_cache[cache_key]
        if cached is None:
            return None
        return SourceCandidate(
            skill=skill_name,
            url=cached.url,
            source_type="github_search_family",
            confidence="low",
            detail=f"Parent/family repo search for prefix '{prefix}': {cached.detail}",
        )

    global _last_github_request_time
    elapsed = time.time() - _last_github_request_time
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)

    token = os.environ.get("GITHUB_TOKEN", "")
    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "skill-maintainer-audit/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    query = urllib.parse.quote(prefix)
    url = f"{_GITHUB_API_BASE}/search/repositories?q={query}+in:name&per_page=5&sort=stars"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        _last_github_request_time = time.time()
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        _last_github_request_time = time.time()
        _github_search_cache[cache_key] = None
        return None

    items = data.get("items", [])
    for item in items:
        repo_name = item.get("name", "").lower()
        repo_desc = (item.get("description") or "").lower()
        repo_topics = [t.lower() for t in (item.get("topics") or [])]
        if repo_name == prefix.lower() and _is_skill_related(repo_desc, repo_topics):
            sentinel = SourceCandidate(prefix, normalize_github_url(item["clone_url"]),
                                       "github_search_family", "low", item["full_name"])
            _github_search_cache[cache_key] = sentinel
            return SourceCandidate(
                skill=skill_name,
                url=sentinel.url,
                source_type="github_search_family",
                confidence="low",
                detail=f"Family repo '{item['full_name']}' matched prefix '{prefix}'",
            )

    _github_search_cache[cache_key] = None
    return None


def _extract_prefix(skill_name: str) -> str | None:
    """Extract the prefix from a hyphenated skill name, e.g. 'cheat-bump' -> 'cheat'."""
    parts = skill_name.split("-")
    if len(parts) >= 2:
        return parts[0]
    return None


def _name_fuzzy_match(skill_name: str, repo_name: str) -> bool:
    clean_skill = re.sub(r"[-_]", "", skill_name.lower())
    clean_repo = re.sub(r"[-_]", "", repo_name.lower())
    return clean_skill == clean_repo or clean_skill in clean_repo or clean_repo in clean_skill


_SKILL_RELATED_SIGNALS = (
    "claude", "anthropic", "codex", "openai", "skill", "agent", "llm", "ai agent",
    "prompt", "mcp", "tool use", "assistant", "copilot", "gpt", "claude-code",
    "ai", "automation", "workflow",
)


def _is_skill_related(repo_desc: str, repo_topics: list[str]) -> bool:
    haystack = repo_desc + " " + " ".join(repo_topics)
    return any(signal in haystack for signal in _SKILL_RELATED_SIGNALS)


def discover_source(
    skill_dir: Path,
    skill_name: str,
    source_manifest: dict[str, dict[str, Any]],
    enable_github_search: bool = False,
    description: str = "",
) -> SourceCandidate | None:
    # Priority 1: explicit source manifest (user-provided, highest trust)
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

    # Priority 2: persisted install info file written by a previous audit run
    from .install_info import source_from_install_info
    install_info = source_from_install_info(skill_name, skill_dir)
    if install_info:
        url, stype, conf, commit = install_info
        return SourceCandidate(skill_name, normalize_github_url(url), stype, conf, "From persisted install info.", commit)

    # Priority 3: local git remote
    if (skill_dir / ".git").exists():
        remote = git_remote(skill_dir)
        if remote:
            return SourceCandidate(skill_name, normalize_github_url(remote), "git_remote", "high", "Git origin remote.")

    # Priority 4: manifest.json / package.json in the skill folder
    manifest_candidate = from_manifest_json(skill_dir, skill_name)
    if manifest_candidate:
        return manifest_candidate

    package_candidate = from_package_json(skill_dir, skill_name)
    if package_candidate:
        return package_candidate

    # Priority 5: GitHub URLs embedded in text files
    text_candidate = from_text_files(skill_dir, skill_name)
    if text_candidate:
        return text_candidate

    # Priority 6: GitHub API search (opt-in, network required)
    if enable_github_search:
        search_candidate = github_search(skill_name, description=description, enable=True)
        # For unverified-only results, try family search before giving up
        if search_candidate and search_candidate.confidence != "unverified":
            return search_candidate

        prefix = _extract_prefix(skill_name)
        if prefix:
            family_candidate = github_search_family(prefix, skill_name, enable=True)
            if family_candidate:
                return family_candidate

        # Return the unverified exact match as last resort (user must verify)
        if search_candidate:
            return search_candidate

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

