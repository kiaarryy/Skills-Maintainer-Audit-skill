from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from skill_maintainer_audit.models import SkillRecord
from skill_maintainer_audit.usage import analyze_usage


def record(name: str) -> SkillRecord:
    return SkillRecord(
        name=name,
        folder_name=name,
        path=f"/tmp/{name}",
        description="demo",
        category="agent-ops",
        summary="demo",
        is_git=False,
    )


def test_usage_counts_skill_mentions(tmp_path: Path) -> None:
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    line = {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "Please use $demo-skill now."}],
        },
    }
    (sessions / "session.jsonl").write_text(json.dumps(line), encoding="utf-8")

    usage = analyze_usage(tmp_path, [record("demo-skill")], now=datetime.now(timezone.utc))
    assert usage[0].count_7d == 1
    assert usage[0].count_30d == 1


def test_usage_ignores_tool_output_skill_lists(tmp_path: Path) -> None:
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    lines = [
        {
            "type": "response_item",
            "payload": {
                "type": "function_call_output",
                "role": "tool",
                "output": "Available skills include $demo-skill and C:/Users/pc/.codex/skills/demo-skill/SKILL.md",
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "developer",
                "content": [{"type": "input_text", "text": "Use $demo-skill in system instructions."}],
            },
        },
    ]
    (sessions / "session.jsonl").write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")

    usage = analyze_usage(tmp_path, [record("demo-skill")], now=datetime.now(timezone.utc))
    assert usage[0].count_7d == 0
    assert usage[0].count_30d == 0
    assert usage[0].evidence == []
