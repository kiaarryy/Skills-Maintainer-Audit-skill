from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SourceCandidate:
    skill: str
    url: str
    source_type: str
    confidence: str
    detail: str = ""
    commit: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SkillRecord:
    name: str
    folder_name: str
    path: str
    description: str
    category: str
    summary: str
    is_git: bool
    source_url: str | None = None
    source_type: str | None = None
    source_confidence: str | None = None
    source_commit: str | None = None
    install_method: str | None = None
    tags: list[str] = field(default_factory=list)
    function_summary: str = ""
    similar_to: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    files: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class UpdateAction:
    skill: str
    path: str
    status: str
    reason: str
    before: str | None = None
    after: str | None = None
    remote: str | None = None
    source_type: str | None = None
    source_confidence: str | None = None
    manual_command: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class UsageRecord:
    skill: str
    count_7d: int = 0
    count_30d: int = 0
    evidence_files: list[str] = field(default_factory=list)
    evidence: list[dict[str, str]] = field(default_factory=list)
    excluded_counts: dict[str, int] = field(default_factory=dict)
    daily_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DuplicateGroup:
    category: str
    skills: list[str]
    reason: str
    overlap_score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def path_as_posix(path: Path) -> str:
    return path.resolve().as_posix()
