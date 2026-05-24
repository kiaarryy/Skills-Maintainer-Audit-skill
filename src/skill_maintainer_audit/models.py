from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


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
    install_method: str | None = None
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class UsageRecord:
    skill: str
    count_7d: int = 0
    count_30d: int = 0
    evidence_files: list[str] = field(default_factory=list)
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

