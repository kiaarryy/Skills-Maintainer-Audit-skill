from __future__ import annotations

import json
import re
from collections import defaultdict
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


def relevant_texts(obj: dict[str, Any]) -> list[str]:
    payload = obj.get("payload", {})
    texts: list[str] = []
    payload_type = payload.get("type")
    role = payload.get("role")
    if role in {"system", "developer"}:
        return []
    if obj.get("type") == "turn_context":
        return []
    if payload_type in {"message", "user_message", "agent_message"}:
        collect_strings(payload.get("content"), texts)
        collect_strings(payload.get("message"), texts)
    elif payload_type in {"function_call", "function_call_output"}:
        collect_strings(payload.get("name"), texts)
        collect_strings(payload.get("arguments"), texts)
        collect_strings(payload.get("output"), texts)
    else:
        collect_strings(payload.get("message"), texts)
    return [text for text in texts if text and not any(marker in text for marker in SKIP_MARKERS)]


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
        evidence = count_file(path, patterns)
        if not evidence:
            continue
        day = timestamp.date().isoformat()
        for name, count in evidence.items():
            usage[name].count_30d += count
            if timestamp >= cutoff_7:
                usage[name].count_7d += count
            usage[name].daily_counts[day] = usage[name].daily_counts.get(day, 0) + count
            path_text = str(path.resolve())
            if path_text not in usage[name].evidence_files:
                usage[name].evidence_files.append(path_text)

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


def count_file(path: Path, patterns: dict[str, re.Pattern[str]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    try:
        if path.suffix.lower() == ".jsonl":
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    text = "\n".join(relevant_texts(obj))
                    if not text:
                        continue
                    for name, pattern in patterns.items():
                        matches = pattern.findall(text)
                        if matches:
                            counts[name] += min(len(matches), 5)
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
            for name, pattern in patterns.items():
                matches = pattern.findall(text)
                if matches:
                    counts[name] += min(len(matches), 20)
    except OSError:
        return {}
    return dict(counts)
