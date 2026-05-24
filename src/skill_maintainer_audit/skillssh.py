"""skills.sh registry integration.

Queries https://skills.sh/api/search to look up skills in the official
open-agent-skills registry and map them to their source repo.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

# Valid GitHub owner/repo pattern: two non-empty segments separated by exactly one /
# Each segment can contain alphanumeric chars, hyphens, underscores and dots.
_VALID_SOURCE_RE = re.compile(r"^[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+$")

_REGISTRY_BASE = "https://skills.sh/api"
_SEARCH_CACHE: dict[str, "RegistryMatch | None"] = {}
_last_request_time: float = 0.0
_MIN_REQUEST_GAP = 0.35  # seconds between requests (well under rate limit)


@dataclass
class RegistryMatch:
    """A skill found in the skills.sh registry."""

    skill: str  # local skill name
    source: str  # owner/repo (e.g. 'anthropics/skills')
    skill_id: str  # canonical skill name in registry
    installs: int  # total install count
    exact: bool  # True if skill_id == local name (case-insensitive)

    @property
    def add_command(self) -> str:
        """Return the `npx skills add` command to install/update this skill."""
        if self.exact and self.skill_id.lower() == self.skill.lower():
            return f"npx skills add {self.source} -g -s {self.skill_id}"
        return f"npx skills add {self.source} -g -s {self.skill_id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill": self.skill,
            "source": self.source,
            "skill_id": self.skill_id,
            "installs": self.installs,
            "exact": self.exact,
            "add_command": self.add_command,
        }


def search_registry(skill_name: str, enable: bool = False) -> RegistryMatch | None:
    """Search skills.sh registry for a skill by name.

    Returns None when the registry is unreachable or no match is found.
    Set enable=True or SKILLSSH_SEARCH=1 to activate (opt-in, requires network).
    """
    if not enable and not os.environ.get("SKILLSSH_SEARCH"):
        return None

    cache_key = skill_name.lower()
    if cache_key in _SEARCH_CACHE:
        return _SEARCH_CACHE[cache_key]

    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < _MIN_REQUEST_GAP:
        time.sleep(_MIN_REQUEST_GAP - elapsed)

    url = f"{_REGISTRY_BASE}/search?q={urllib.parse.quote(skill_name)}"
    headers = {"User-Agent": "skill-maintainer-audit/1.0", "Accept": "application/json"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        _last_request_time = time.time()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError):
        _last_request_time = time.time()
        _SEARCH_CACHE[cache_key] = None
        return None

    # skills.sh may return results under 'skills' or 'results'
    items: list[dict] = data.get("skills", data.get("results", []))
    match = _best_match(skill_name, items)
    _SEARCH_CACHE[cache_key] = match
    return match


def batch_search_registry(
    skill_names: list[str],
    enable: bool = False,
    on_progress: Any = None,
) -> dict[str, RegistryMatch | None]:
    """Search skills.sh registry for multiple skills.

    Returns a dict mapping each skill name to its best RegistryMatch (or None).
    on_progress(done, total) is called after each search if provided.
    """
    results: dict[str, RegistryMatch | None] = {}
    total = len(skill_names)
    for i, name in enumerate(skill_names):
        results[name] = search_registry(name, enable=enable)
        if on_progress:
            on_progress(i + 1, total)
    return results


def _best_match(skill_name: str, items: list[dict]) -> RegistryMatch | None:
    """Select the best matching registry entry for a skill name."""
    if not items:
        return None
    name_lower = skill_name.lower()

    # Priority 1: exact skillId match
    for item in items:
        sid = str(item.get("skillId") or item.get("name") or "").lower()
        if sid == name_lower:
            m = _make_match(skill_name, item, exact=True)
            if m is not None:
                return m

    # Priority 2: exact name match (display name may differ)
    for item in items:
        n = str(item.get("name") or "").lower()
        if n == name_lower:
            m = _make_match(skill_name, item, exact=True)
            if m is not None:
                return m

    return None  # no fuzzy matches — caller can use GitHub search as fallback


def _make_match(skill_name: str, item: dict, exact: bool) -> RegistryMatch | None:
    source = str(item.get("source") or "")
    # Reject entries without a valid owner/repo source (e.g. bare domain names)
    if not _VALID_SOURCE_RE.match(source):
        return None
    skill_id = str(item.get("skillId") or item.get("name") or skill_name)
    installs = int(item.get("installs") or 0)
    return RegistryMatch(skill=skill_name, source=source, skill_id=skill_id,
                         installs=installs, exact=exact)


def group_by_source(matches: dict[str, RegistryMatch | None]) -> dict[str, list[RegistryMatch]]:
    """Group registry matches by their source repo.

    Returns a dict: source_repo → list[RegistryMatch].
    Useful for generating one `npx skills add <source>` command per repo.
    """
    groups: dict[str, list[RegistryMatch]] = {}
    for match in matches.values():
        if match is None:
            continue
        groups.setdefault(match.source, []).append(match)
    return groups
