from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from skill_maintainer_audit.models import DuplicateGroup, SkillRecord, UpdateAction, UsageRecord
from skill_maintainer_audit.report import render_report


def test_report_contains_dashboard_sections_and_details(tmp_path: Path) -> None:
    report = tmp_path / "report.html"
    records = [
        SkillRecord(
            name="demo-skill",
            folder_name="demo-skill",
            path=str(tmp_path / "demo-skill"),
            description="Use when testing report rendering for local skills.",
            category="agent-ops",
            summary="Demo summary",
            function_summary="Demo summary",
            is_git=False,
            source_url="https://github.com/example/demo.git",
            source_confidence="low",
            tags=["agent-ops", "review"],
        )
    ]
    usage = [
        UsageRecord(
            skill="demo-skill",
            count_7d=1,
            count_30d=2,
            daily_counts={"2026-05-24": 2},
            evidence=[{"evidence_type": "user_message", "file": "C:/long/path/session.jsonl", "snippet": "Use $demo-skill now"}],
        )
    ]
    updates = [UpdateAction("demo-skill", str(tmp_path), "non_git_no_baseline", "source but no baseline")]
    duplicates = [DuplicateGroup("agent-ops", ["demo-skill", "demo-skill-2"], "similar names", 0.5)]

    render_report(report, records, usage, updates, duplicates, datetime(2026, 5, 24, tzinfo=timezone.utc))
    html = report.read_text(encoding="utf-8")
    assert "Update Funnel" in html
    assert "30 Day Usage Heatmap" in html
    assert "Category Distribution" in html
    assert "Duplicate Capability Matrix" in html
    assert "<details>" in html
    assert "Show evidence" in html

