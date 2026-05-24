from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .models import SkillRecord, UsageRecord

SKIP_MARKERS = (
    "<skills_instructions>",
    "### Available skills",
    "Skill roots",
    "base_instructions",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def file_time_utc(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def relevant_texts(obj: dict[str, Any]) -> tuple[str, list[str], str]:
    payload = obj.get("payload", {})
    texts: list[str] = []
    payload_type = payload.get("type")
    role = payload.get("role")
    top_type = obj.get("type")
    if role in {"system", "developer"}:
        return "excluded_role", [], "system_or_developer"
    if top_type == "turn_context":
        return "excluded_context", [], "turn_context"
    if payload_type == "message" and role in {"user", "assistant"}:
        collect_strings(payload.get("content"), texts)
        collect_strings(payload.get("message"), texts)
        evidence_type = f"{role}_message"
    elif payload_type in {"user_message", "agent_message"}:
        collect_strings(payload.get("message"), texts)
        evidence_type = payload_type
    elif payload_type in {"function_call", "function_call_output"} or "call" in str(payload_type):
        return "excluded_tool", [], str(payload_type)
    else:
        return "excluded_other", [], str(payload_type)
    clean = [text for text in texts if text and not any(marker in text for marker in SKIP_MARKERS)]
    if not clean:
        return "excluded_marker", [], evidence_type
    return evidence_type, clean, ""


def collect_strings(value: Any, result: list[str]) -> None:
    if isinstance(value, str):
        if len(value) <= 20000:
            result.append(value)
        else:
            result.append(value[:20000])
        return
    if isinstance(value, list):
        for item in value:
            collect_strings(item, result)
        return
    if isinstance(value, dict):
        for key in ("text", "input_text", "output_text", "name", "arguments", "output", "message", "content"):
            if key in value:
                collect_strings(value[key], result)


def skill_patterns(skill_names: list[str]) -> dict[str, re.Pattern[str]]:
    patterns: dict[str, re.Pattern[str]] = {}
    for name in skill_names:
        escaped = re.escape(name)
        patterns[name] = re.compile(
            rf"(\${escaped}\b|skills[\\/]+{escaped}[\\/]+SKILL\.md|{escaped}[\\/]+SKILL\.md)",
            re.IGNORECASE,
        )
    return patterns


def analyze_usage(codex_home: Path, records: list[SkillRecord], now: datetime | None = None) -> list[UsageRecord]:
    now = now or utc_now()
    cutoff_30 = now - timedelta(days=30)
    cutoff_7 = now - timedelta(days=7)
    names = [record.name for record in records]
    patterns = skill_patterns(names)
    usage = {name: UsageRecord(skill=name) for name in names}

    for path in candidate_files(codex_home, cutoff_30):
        timestamp = file_time_utc(path)
        if timestamp < cutoff_30:
            continue
        counts, evidence_items, excluded = count_file(path, patterns)
        if not counts and not excluded:
            continue
        day = timestamp.date().isoformat()
        for name, count in counts.items():
            usage[name].count_30d += count
            if timestamp >= cutoff_7:
                usage[name].count_7d += count
            usage[name].daily_counts[day] = usage[name].daily_counts.get(day, 0) + count
            path_text = str(path.resolve())
            if path_text not in usage[name].evidence_files:
                usage[name].evidence_files.append(path_text)
        for name, items in evidence_items.items():
            usage[name].evidence.extend(items[: max(0, 20 - len(usage[name].evidence))])
        for name in usage:
            if excluded:
                for reason, count in excluded.items():
                    usage[name].excluded_counts[reason] = usage[name].excluded_counts.get(reason, 0) + count

    return sorted(usage.values(), key=lambda item: (-item.count_30d, item.skill))


def candidate_files(codex_home: Path, cutoff: datetime) -> list[Path]:
    candidates: list[Path] = []
    sessions = codex_home / "sessions"
    if sessions.exists():
        candidates.extend(path for path in sessions.rglob("*") if path.is_file() and file_time_utc(path) >= cutoff)
    for path in (codex_home / "session_index.jsonl",):
        if path.exists() and file_time_utc(path) >= cutoff:
            candidates.append(path)
    automations = codex_home / "automations"
    if automations.exists():
        candidates.extend(path for path in automations.rglob("memory.md") if path.is_file() and file_time_utc(path) >= cutoff)
    return candidates


def count_file(path: Path, patterns: dict[str, re.Pattern[str]]) -> tuple[dict[str, int], dict[str, list[dict[str, str]]], dict[str, int]]:
    counts: dict[str, int] = defaultdict(int)
    evidence: dict[str, list[dict[str, str]]] = defaultdict(list)
    excluded: Counter[str] = Counter()
    try:
        if path.suffix.lower() == ".jsonl":
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        excluded["invalid_json"] += 1
                        continue
                    evidence_type, texts, reason = relevant_texts(obj)
                    if not texts:
                        excluded[reason or evidence_type] += 1
                        continue
                    add_matches(path, patterns, texts, evidence_type, counts, evidence)
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
            add_matches(path, patterns, [text], "automation_memory", counts, evidence, limit=20)
    except OSError:
        return {}, {}, {"read_error": 1}
    return dict(counts), dict(evidence), dict(excluded)


def add_matches(
    path: Path,
    patterns: dict[str, re.Pattern[str]],
    texts: list[str],
    evidence_type: str,
    counts: dict[str, int],
    evidence: dict[str, list[dict[str, str]]],
    limit: int = 5,
) -> None:
    for text in texts:
        for name, pattern in patterns.items():
            matches = list(pattern.finditer(text))
            if not matches:
                continue
            counts[name] += min(len(matches), limit)
            for match in matches[:3]:
                if len(evidence[name]) >= 20:
                    break
                evidence[name].append(
                    {
                        "evidence_type": evidence_type,
                        "file": str(path.resolve()),
                        "snippet": snippet(text, match.start(), match.end()),
                    }
                )


def snippet(text: str, start: int, end: int, radius: int = 80) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return re.sub(r"\s+", " ", text[left:right]).strip()
