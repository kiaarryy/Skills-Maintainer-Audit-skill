from __future__ import annotations

import html
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from .models import DuplicateGroup, SkillRecord, UpdateAction, UsageRecord


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def render_report(
    output_path: Path,
    records: list[SkillRecord],
    usage: list[UsageRecord],
    updates: list[UpdateAction],
    duplicates: list[DuplicateGroup],
    generated_at: datetime,
) -> None:
    category_counts = Counter(record.category for record in records)
    status_counts = Counter(action.status for action in updates)
    used_7 = sum(1 for item in usage if item.count_7d > 0)
    used_30 = sum(1 for item in usage if item.count_30d > 0)
    issue_count = sum(len(record.issues) for record in records)
    top_usage = sorted(usage, key=lambda item: (-item.count_30d, item.skill))[:20]
    unused = [item for item in usage if item.count_30d == 0]
    risky = [record for record in records if record.issues][:30]

    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Skill Maintainer Audit</title>
  <style>{CSS}</style>
</head>
<body>
  <header>
    <p class="eyebrow">Skill Maintainer Audit</p>
    <h1>Local Skill Maintenance Dashboard</h1>
    <p>Generated at {escape(generated_at.isoformat())}</p>
  </header>
  <main>
    <section class="kpis">
      {kpi("Installed skills", len(records))}
      {kpi("Used in 7 days", used_7)}
      {kpi("Used in 30 days", used_30)}
      {kpi("Structural issues", issue_count)}
      {kpi("Duplicate groups", len(duplicates))}
      {kpi("Manual review", status_counts.get("needs_manual_review", 0))}
    </section>
    <section class="grid">
      <article>
        <h2>Category Distribution</h2>
        {bar_chart(category_counts)}
      </article>
      <article>
        <h2>Update Status</h2>
        {bar_chart(status_counts)}
      </article>
    </section>
    <section>
      <h2>7/30 Day Usage</h2>
      {usage_table(top_usage)}
    </section>
    <section>
      <h2>Unused In 30 Days</h2>
      <p>{len(unused)} skills had no parsed trigger evidence in the last 30 days.</p>
      {pill_list([item.skill for item in unused[:80]])}
    </section>
    <section>
      <h2>Duplicate Or Similar Capabilities</h2>
      {duplicate_table(duplicates)}
    </section>
    <section>
      <h2>Risks And Manual Review</h2>
      {risk_table(risky, updates)}
    </section>
  </main>
</body>
</html>
"""
    output_path.write_text(html_text, encoding="utf-8")


CSS = """
:root {
  color-scheme: light;
  --ink: #182026;
  --muted: #65717b;
  --line: #d7dde2;
  --panel: #f7f9fb;
  --accent: #007c89;
  --accent-2: #c23b22;
  --good: #1f8a5b;
}
* { box-sizing: border-box; }
body { margin: 0; font-family: Inter, Segoe UI, Arial, sans-serif; color: var(--ink); background: #fff; }
header { padding: 42px 48px 28px; border-bottom: 1px solid var(--line); }
h1 { margin: 0 0 8px; font-size: 40px; letter-spacing: 0; }
h2 { margin: 0 0 18px; font-size: 22px; letter-spacing: 0; }
p { color: var(--muted); }
main { padding: 28px 48px 60px; }
section { margin: 0 0 28px; }
article, section:not(.kpis):not(.grid) { border: 1px solid var(--line); border-radius: 8px; padding: 22px; background: #fff; }
.eyebrow { margin: 0 0 8px; color: var(--accent); font-weight: 700; text-transform: uppercase; font-size: 12px; }
.kpis { display: grid; grid-template-columns: repeat(6, minmax(120px, 1fr)); gap: 12px; }
.kpi { border: 1px solid var(--line); border-radius: 8px; padding: 18px; background: var(--panel); }
.kpi strong { display: block; font-size: 30px; line-height: 1.1; }
.kpi span { color: var(--muted); font-size: 13px; }
.grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.bar { display: grid; grid-template-columns: 180px 1fr 52px; gap: 10px; align-items: center; margin: 10px 0; }
.track { height: 12px; background: #e9eef2; border-radius: 999px; overflow: hidden; }
.fill { height: 100%; background: var(--accent); }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { text-align: left; border-bottom: 1px solid var(--line); padding: 10px 8px; vertical-align: top; }
th { color: var(--muted); font-weight: 700; }
.pill-list { display: flex; flex-wrap: wrap; gap: 8px; }
.pill { padding: 6px 10px; border: 1px solid var(--line); border-radius: 999px; background: var(--panel); font-size: 13px; }
.status-needs_manual_review, .status-failed { color: var(--accent-2); font-weight: 700; }
.status-updated, .status-up_to_date, .status-eligible { color: var(--good); font-weight: 700; }
@media (max-width: 980px) {
  header, main { padding-left: 20px; padding-right: 20px; }
  .kpis, .grid { grid-template-columns: 1fr; }
  .bar { grid-template-columns: 120px 1fr 42px; }
}
"""


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def kpi(label: str, value: int) -> str:
    return f'<div class="kpi"><strong>{value}</strong><span>{escape(label)}</span></div>'


def bar_chart(counts: Counter[str]) -> str:
    if not counts:
        return "<p>No data.</p>"
    total = max(counts.values())
    rows = []
    for label, count in counts.most_common():
        width = int((count / total) * 100) if total else 0
        rows.append(
            f'<div class="bar"><span>{escape(label)}</span><div class="track"><div class="fill" style="width:{width}%"></div></div><b>{count}</b></div>'
        )
    return "\n".join(rows)


def usage_table(items: list[UsageRecord]) -> str:
    rows = [
        f"<tr><td>{escape(item.skill)}</td><td>{item.count_7d}</td><td>{item.count_30d}</td><td>{escape(', '.join(item.evidence_files[:3]))}</td></tr>"
        for item in items
    ]
    return "<table><thead><tr><th>Skill</th><th>7d</th><th>30d</th><th>Evidence</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def pill_list(items: list[str]) -> str:
    if not items:
        return "<p>None.</p>"
    return '<div class="pill-list">' + "".join(f'<span class="pill">{escape(item)}</span>' for item in items) + "</div>"


def duplicate_table(groups: list[DuplicateGroup]) -> str:
    if not groups:
        return "<p>No duplicate groups detected.</p>"
    rows = [
        f"<tr><td>{escape(group.category)}</td><td>{escape(', '.join(group.skills))}</td><td>{group.overlap_score:.3f}</td><td>{escape(group.reason)}</td></tr>"
        for group in groups
    ]
    return "<table><thead><tr><th>Category</th><th>Skills</th><th>Score</th><th>Reason</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def risk_table(records: list[SkillRecord], updates: list[UpdateAction]) -> str:
    update_by_skill = {item.skill: item for item in updates}
    rows = []
    for record in records:
        action = update_by_skill.get(record.name)
        status = action.status if action else "n/a"
        rows.append(
            f'<tr><td>{escape(record.name)}</td><td>{escape(record.category)}</td><td>{escape("; ".join(record.issues))}</td><td class="status-{escape(status)}">{escape(status)}</td></tr>'
        )
    if not rows:
        return "<p>No structural issues found.</p>"
    return "<table><thead><tr><th>Skill</th><th>Category</th><th>Issues</th><th>Update</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"

