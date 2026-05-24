from __future__ import annotations

import re
from collections import defaultdict

from .models import DuplicateGroup, SkillRecord

STOPWORDS = {
    "skill",
    "skills",
    "use",
    "when",
    "user",
    "asks",
    "with",
    "from",
    "this",
    "that",
    "and",
    "for",
    "the",
    "local",
    "codex",
    "agent",
}


def tokens(record: SkillRecord) -> set[str]:
    text = f"{record.name} {record.description} {record.summary}".lower()
    parts = set(re.findall(r"[a-z0-9][a-z0-9-]{2,}", text))
    expanded = set()
    for part in parts:
        expanded.update(p for p in part.split("-") if len(p) > 2)
        expanded.add(part)
    return {part for part in expanded if part not in STOPWORDS}


def find_duplicates(records: list[SkillRecord]) -> list[DuplicateGroup]:
    by_category: dict[str, list[SkillRecord]] = defaultdict(list)
    for record in records:
        by_category[record.category].append(record)

    groups: list[DuplicateGroup] = []
    used: set[str] = set()
    for category, items in by_category.items():
        token_map = {item.name: tokens(item) for item in items}
        for item in items:
            if item.name in used:
                continue
            cluster = [item.name]
            for other in items:
                if other.name == item.name or other.name in used:
                    continue
                score = jaccard(token_map[item.name], token_map[other.name])
                name_overlap = item.name in other.name or other.name in item.name
                if score >= 0.28 or name_overlap:
                    cluster.append(other.name)
            if len(cluster) >= 2:
                used.update(cluster)
                score = max_pair_score(cluster, token_map)
                groups.append(
                    DuplicateGroup(
                        category=category,
                        skills=sorted(cluster),
                        reason="similar category, names, or description keywords",
                        overlap_score=round(score, 3),
                    )
                )
    return sorted(groups, key=lambda group: (-group.overlap_score, group.category, group.skills))


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def max_pair_score(names: list[str], token_map: dict[str, set[str]]) -> float:
    score = 0.0
    for index, name in enumerate(names):
        for other in names[index + 1 :]:
            score = max(score, jaccard(token_map[name], token_map[other]))
    return score

