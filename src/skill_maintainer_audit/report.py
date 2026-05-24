from __future__ import annotations

import html
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from .models import DuplicateGroup, SkillRecord, UpdateAction, UsageRecord


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def render_manual_update_commands(path: Path, updates: list[UpdateAction]) -> None:
    lines = [
        "# Manual Skill Update Notes",
        "",
        "The audit does not overwrite non-Git skill folders automatically.",
        "Commands below are ready to run after reviewing what will change.",
        "",
    ]

    actionable = [item for item in updates if item.manual_command and item.status in {"non_git_updateable", "outdated_source_detected"}]
    advisory = [item for item in updates if item.manual_command and item.status not in {"non_git_updateable", "outdated_source_detected"}]

    if actionable:
        lines += ["## Actionable Reinstalls", "", "Source found and upstream HEAD confirmed — run to update:", ""]
        for item in actionable:
            lines += [
                f"### {item.skill}",
                "",
                f"- Source: `{item.remote or 'unknown'}` ({item.source_type}, confidence={item.source_confidence})",
                f"- Upstream HEAD: `{item.after or 'unknown'}`",
                "```",
                item.manual_command,
                "```",
                "",
            ]

    if advisory:
        lines += ["## Advisory (no upstream confirmation)", ""]
        for item in advisory:
            lines += [
                f"### {item.skill}",
                "",
                f"- Status: `{item.status}`",
                f"- Source: {item.remote or 'unknown'} ({item.source_type})",
                f"- Reason: {item.reason}",
                "```",
                item.manual_command,
                "```",
                "",
            ]

    if not actionable and not advisory:
        lines.append("No manual update commands were generated.")
    path.write_text("\n".join(lines), encoding="utf-8")


def render_report(
    output_path: Path,
    records: list[SkillRecord],
    usage: list[UsageRecord],
    updates: list[UpdateAction],
    duplicates: list[DuplicateGroup],
    generated_at: datetime,
) -> None:
    usage_by_skill = {item.skill: item for item in usage}
    update_by_skill = {item.skill: item for item in updates}
    category_counts = Counter(record.category for record in records)
    status_counts = Counter(action.status for action in updates)
    source_counts = Counter(source_label(record) for record in records)
    used_7 = sum(1 for item in usage if item.count_7d > 0)
    used_30 = sum(1 for item in usage if item.count_30d > 0)
    unused = sorted((item for item in usage if item.count_30d == 0), key=lambda item: item.skill)
    issue_count = sum(len(record.issues) for record in records)
    top_usage = sorted(usage, key=lambda item: (-item.count_30d, item.skill))[:16]
    last_30_days = [(generated_at - timedelta(days=offset)).date().isoformat() for offset in range(29, -1, -1)]

    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Skill Maintainer Audit</title>
  <style>{CSS}</style>
</head>
<body>
  <header class="hero">
    <div>
      <p class="eyebrow">Skill Maintainer Audit</p>
      <h1>Local Skill Operations Dashboard</h1>
      <p class="lede">Safe updates, real usage evidence, capability taxonomy, and duplicate detection for local AI agent skills.</p>
    </div>
    <div class="stamp">
      <span>Generated</span>
      <strong>{escape(generated_at.strftime("%Y-%m-%d %H:%M UTC"))}</strong>
    </div>
  </header>
  <main>
    <section class="kpis" aria-label="Audit summary">
      {kpi("Installed", len(records), "skills scanned")}
      {kpi("Used 7d", used_7, "with parsed evidence")}
      {kpi("Used 30d", used_30, "with parsed evidence")}
      {kpi("Unused 30d", len(unused), "no evidence")}
      {kpi("Sources", sum(1 for record in records if record.source_url), "discovered")}
      {kpi("Issues", issue_count, "structural warnings")}
    </section>

    <section class="layout-two">
      <article class="panel">
        <div class="panel-head"><h2>Update Funnel</h2><span>Safe mode</span></div>
        {funnel(status_counts)}
      </article>
      <article class="panel">
        <div class="panel-head"><h2>Source Coverage</h2><span>How updates are decided</span></div>
        {bar_chart(source_counts)}
      </article>
    </section>

    <section class="layout-two">
      <article class="panel">
        <div class="panel-head"><h2>Category Distribution</h2><span>Capability taxonomy</span></div>
        {category_tiles(category_counts)}
      </article>
      <article class="panel">
        <div class="panel-head"><h2>30 Day Usage Heatmap</h2><span>Evidence by day</span></div>
        {heatmap(usage, last_30_days)}
      </article>
    </section>

    <section class="panel">
      <div class="panel-head"><h2>Top Usage Evidence</h2><span>Evidence is shortened; expand rows for details</span></div>
      {usage_table(top_usage)}
    </section>

    <section class="layout-two wide-left">
      <article class="panel">
        <div class="panel-head"><h2>Duplicate Capability Matrix</h2><span>{len(duplicates)} groups</span></div>
        {duplicate_matrix(duplicates)}
      </article>
      <article class="panel">
        <div class="panel-head"><h2>Unused In 30 Days</h2><span>{len(unused)} skills</span></div>
        {pill_list([item.skill for item in unused[:80]])}
      </article>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>Actionable Reinstall Commands</h2>
        <span>Non-Git skills with confirmed upstream source</span>
      </div>
      {actionable_reinstalls(updates)}
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>Skill Inventory</h2>
        <input id="skillSearch" type="search" placeholder="Filter skills, categories, status, source">
      </div>
      {inventory_table(records, usage_by_skill, update_by_skill)}
    </section>
  </main>
  <script>{SCRIPT}</script>
</body>
</html>
"""
    output_path.write_text(html_text, encoding="utf-8")


CSS = """
:root {
  color-scheme: light;
  --ink: #17212b;
  --soft-ink: #3d4a57;
  --muted: #697887;
  --paper: #fbfcf8;
  --panel: #ffffff;
  --line: #d9e0df;
  --wash: #eef4f2;
  --accent: #0b7a75;
  --accent-dark: #095b58;
  --amber: #b76b00;
  --red: #b63d2b;
  --green: #277a4d;
  --blue: #256f9c;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background:
    linear-gradient(135deg, rgba(11,122,117,.08), transparent 34%),
    linear-gradient(315deg, rgba(183,107,0,.08), transparent 28%),
    var(--paper);
  color: var(--ink);
  font-family: Aptos, "Segoe UI Variable", "Trebuchet MS", sans-serif;
  font-size: 16px;
  line-height: 1.5;
}
.hero {
  min-height: 230px;
  padding: 46px 56px 34px;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 28px;
  align-items: end;
  border-bottom: 1px solid var(--line);
}
.eyebrow {
  margin: 0 0 10px;
  color: var(--accent-dark);
  font-size: 13px;
  font-weight: 800;
  letter-spacing: .08em;
  text-transform: uppercase;
}
h1 { margin: 0; max-width: 900px; font-size: 54px; line-height: .98; letter-spacing: 0; }
h2 { margin: 0; font-size: 24px; letter-spacing: 0; }
.lede { margin: 18px 0 0; max-width: 780px; color: var(--soft-ink); font-size: 20px; }
.stamp { border: 1px solid var(--line); background: rgba(255,255,255,.72); border-radius: 8px; padding: 16px 18px; min-width: 230px; }
.stamp span { display: block; color: var(--muted); font-size: 13px; }
.stamp strong { font-size: 17px; }
main { padding: 30px 56px 68px; }
.kpis { display: grid; grid-template-columns: repeat(6, minmax(132px, 1fr)); gap: 14px; margin-bottom: 20px; }
.kpi { border: 1px solid var(--line); border-radius: 8px; padding: 18px; background: rgba(255,255,255,.86); }
.kpi strong { display: block; font-size: 36px; line-height: 1; }
.kpi span { display: block; margin-top: 8px; color: var(--ink); font-weight: 700; }
.kpi em { display: block; margin-top: 2px; color: var(--muted); font-style: normal; font-size: 13px; }
.panel { border: 1px solid var(--line); border-radius: 8px; padding: 22px; background: rgba(255,255,255,.92); box-shadow: 0 18px 50px rgba(23,33,43,.07); overflow: hidden; }
.panel-head { display: flex; justify-content: space-between; gap: 18px; align-items: center; margin-bottom: 18px; }
.panel-head span { color: var(--muted); font-size: 14px; white-space: nowrap; }
.layout-two { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; margin-bottom: 20px; }
.wide-left { grid-template-columns: minmax(0, 1.35fr) minmax(300px, .65fr); }
.funnel-row, .bar-row { display: grid; grid-template-columns: 190px 1fr 64px; gap: 12px; align-items: center; margin: 12px 0; }
.track { height: 16px; background: var(--wash); border-radius: 999px; overflow: hidden; border: 1px solid #dce6e4; }
.fill { height: 100%; background: var(--accent); }
.status-updated, .status-up_to_date { color: var(--green); font-weight: 800; }
.status-outdated_source_detected, .status-non_git_updateable { color: var(--amber); font-weight: 800; }
.status-unknown_source, .status-dirty_git, .status-non_git_no_baseline, .status-failed { color: var(--red); font-weight: 800; }
.category-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
.category-tile { background: var(--wash); border: 1px solid var(--line); border-radius: 8px; padding: 12px; }
.category-tile strong { display: block; font-size: 26px; }
.heatmap { display: grid; grid-template-columns: 170px repeat(30, minmax(9px, 1fr)); gap: 4px; align-items: center; overflow-x: auto; padding-bottom: 4px; }
.heat-label { font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.heat-cell { height: 18px; border-radius: 3px; background: #e9eeee; border: 1px solid rgba(0,0,0,.04); }
.heat-1 { background: #b9d8cf; }
.heat-2 { background: #73b8aa; }
.heat-3 { background: #258f83; }
.heat-4 { background: #075f5a; }
table { width: 100%; border-collapse: collapse; font-size: 15px; }
th, td { border-bottom: 1px solid var(--line); padding: 12px 10px; vertical-align: top; text-align: left; }
th { color: var(--muted); font-size: 13px; text-transform: uppercase; letter-spacing: .04em; }
tr:hover td { background: #f7fbfa; }
.skill-name { font-weight: 800; }
.summary { color: var(--soft-ink); max-width: 440px; }
.mono { font-family: Consolas, "Cascadia Mono", monospace; font-size: 13px; }
.chip-list { display: flex; flex-wrap: wrap; gap: 7px; }
.chip { max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; border: 1px solid var(--line); border-radius: 999px; padding: 5px 9px; background: var(--wash); font-size: 13px; }
.evidence-chip { max-width: 360px; }
details { margin-top: 8px; }
summary { cursor: pointer; color: var(--accent-dark); font-weight: 800; }
.detail-box { margin-top: 8px; padding: 10px; background: #f4f7f6; border: 1px solid var(--line); border-radius: 8px; max-height: 260px; overflow: auto; }
.pill-list { display: flex; flex-wrap: wrap; gap: 8px; }
.pill { border: 1px solid var(--line); border-radius: 999px; padding: 7px 10px; background: var(--wash); font-weight: 700; font-size: 14px; }
#skillSearch { width: min(420px, 100%); border: 1px solid var(--line); border-radius: 8px; padding: 11px 12px; font: inherit; background: #fff; }
@media (max-width: 1100px) {
  .hero, main { padding-left: 22px; padding-right: 22px; }
  .hero, .layout-two, .wide-left, .kpis { grid-template-columns: 1fr; }
  h1 { font-size: 40px; }
  .heatmap { grid-template-columns: 130px repeat(30, 14px); }
}
"""

SCRIPT = """
const search = document.getElementById('skillSearch');
if (search) {
  search.addEventListener('input', () => {
    const q = search.value.toLowerCase();
    document.querySelectorAll('[data-skill-row]').forEach(row => {
      row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  });
}
"""


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def source_label(record: SkillRecord) -> str:
    if record.is_git:
        return "git-backed"
    if record.source_url:
        return f"source:{record.source_confidence or 'unknown'}"
    return "unknown"


def kpi(label: str, value: int, note: str) -> str:
    return f'<div class="kpi"><strong>{value}</strong><span>{escape(label)}</span><em>{escape(note)}</em></div>'


def funnel(counts: Counter[str]) -> str:
    order = ["updated", "up_to_date", "outdated_source_detected", "non_git_updateable", "non_git_no_baseline", "unknown_source", "dirty_git", "failed"]
    total = max(counts.values(), default=1)
    rows = []
    for status in order:
        count = counts.get(status, 0)
        width = int((count / total) * 100) if total else 0
        rows.append(f'<div class="funnel-row"><span class="status-{status}">{escape(status)}</span><div class="track"><div class="fill" style="width:{width}%"></div></div><b>{count}</b></div>')
    return "\n".join(rows)


def bar_chart(counts: Counter[str]) -> str:
    if not counts:
        return "<p>No data.</p>"
    total = max(counts.values())
    return "\n".join(
        f'<div class="bar-row"><span>{escape(label)}</span><div class="track"><div class="fill" style="width:{int((count / total) * 100)}%"></div></div><b>{count}</b></div>'
        for label, count in counts.most_common()
    )


def category_tiles(counts: Counter[str]) -> str:
    return '<div class="category-grid">' + "".join(
        f'<div class="category-tile"><strong>{count}</strong><span>{escape(category)}</span></div>' for category, count in counts.most_common()
    ) + "</div>"


def heatmap(usage: list[UsageRecord], days: list[str]) -> str:
    rows = []
    for item in sorted(usage, key=lambda u: (-u.count_30d, u.skill))[:12]:
        rows.append(f'<div class="heat-label" title="{escape(item.skill)}">{escape(item.skill)}</div>')
        max_count = max(item.daily_counts.values() or [1])
        for day in days:
            count = item.daily_counts.get(day, 0)
            level = 0 if count == 0 else min(4, max(1, int((count / max_count) * 4)))
            rows.append(f'<div class="heat-cell heat-{level}" title="{escape(item.skill)} {day}: {count}"></div>')
    return '<div class="heatmap">' + "".join(rows) + "</div>"


def usage_table(items: list[UsageRecord]) -> str:
    rows = []
    for item in items:
        rows.append(
            "<tr>"
            f"<td class=\"skill-name\">{escape(item.skill)}</td>"
            f"<td>{item.count_7d}</td>"
            f"<td>{item.count_30d}</td>"
            f"<td>{evidence_block(item)}</td>"
            "</tr>"
        )
    return "<table><thead><tr><th>Skill</th><th>7d</th><th>30d</th><th>Evidence</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def evidence_block(item: UsageRecord) -> str:
    if not item.evidence:
        return '<span class="chip">No detailed evidence</span>'
    chips = "".join(f'<span class="chip evidence-chip">{escape(e.get("snippet", ""))}</span>' for e in item.evidence[:2])
    details = "".join(
        f'<p><b>{escape(e.get("evidence_type", ""))}</b>: {escape(e.get("snippet", ""))}<br><span class="mono">{escape(short_path(e.get("file", "")))}</span></p>'
        for e in item.evidence[:12]
    )
    return f'<div class="chip-list">{chips}</div><details><summary>Show evidence</summary><div class="detail-box">{details}</div></details>'


def actionable_reinstalls(updates: list[UpdateAction]) -> str:
    items = [u for u in updates if u.manual_command and u.status in {"non_git_updateable", "outdated_source_detected"}]
    if not items:
        advisory = [u for u in updates if u.manual_command]
        if not advisory:
            return "<p>No actionable reinstalls. All non-Git skills either have no discovered source or are already tracked. Run with <code>--github-search</code> to discover more sources.</p>"
        return f"<p>No upstream-confirmed reinstalls yet. {len(advisory)} advisory items in <code>manual_update_commands.md</code>. Run with <code>--github-search</code> to confirm upstream sources.</p>"

    rows = []
    for item in items:
        cmd = escape(item.manual_command or "")
        rows.append(
            "<tr>"
            f"<td class=\"skill-name\">{escape(item.skill)}</td>"
            f"<td class=\"status-{escape(item.status)}\">{escape(item.status)}</td>"
            f"<td><span class=\"chip\">{escape(item.source_confidence or '?')}</span> {escape(item.source_type or '')}</td>"
            f"<td class=\"mono\">{escape(item.remote or '')}</td>"
            f"<td>{escape(item.after or '—')}</td>"
            f"<td><details><summary>Show command</summary><div class=\"detail-box mono\">{cmd}</div></details></td>"
            "</tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>Skill</th><th>Status</th><th>Confidence</th><th>Source URL</th><th>Upstream HEAD</th><th>Reinstall</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def duplicate_matrix(groups: list[DuplicateGroup]) -> str:
    if not groups:
        return "<p>No duplicate groups detected.</p>"
    rows = []
    for group in groups[:24]:
        rows.append(
            "<tr>"
            f"<td>{escape(group.category)}</td>"
            f"<td>{pill_list(group.skills)}</td>"
            f"<td>{group.overlap_score:.3f}</td>"
            f"<td>{escape(group.reason)}</td>"
            "</tr>"
        )
    return "<table><thead><tr><th>Category</th><th>Skills</th><th>Score</th><th>Reason</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def pill_list(items: list[str]) -> str:
    if not items:
        return "<p>None.</p>"
    return '<div class="pill-list">' + "".join(f'<span class="pill">{escape(item)}</span>' for item in items) + "</div>"


def inventory_table(records: list[SkillRecord], usage_by_skill: dict[str, UsageRecord], update_by_skill: dict[str, UpdateAction]) -> str:
    rows = []
    for record in sorted(records, key=lambda item: (item.category, item.name)):
        usage = usage_by_skill.get(record.name)
        update = update_by_skill.get(record.name)
        status = update.status if update else "unknown"
        source = record.source_url or "not detected"
        rows.append(
            f'<tr data-skill-row><td><div class="skill-name">{escape(record.name)}</div><div class="summary">{escape(record.function_summary or record.summary)}</div></td>'
            f'<td>{escape(record.category)}<div class="chip-list">{tags(record.tags)}</div></td>'
            f'<td>{usage.count_7d if usage else 0} / {usage.count_30d if usage else 0}</td>'
            f'<td class="status-{escape(status)}">{escape(status)}</td>'
            f'<td><span class="chip">{escape(record.source_confidence or "no-source")}</span><details><summary>Source</summary><div class="detail-box mono">{escape(source)}</div></details></td>'
            f'<td>{escape("; ".join(record.issues[:3]) or "OK")}</td></tr>'
        )
    return "<table><thead><tr><th>Skill</th><th>Category</th><th>7d / 30d</th><th>Status</th><th>Source</th><th>Issues</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def tags(items: list[str]) -> str:
    return "".join(f'<span class="chip">{escape(item)}</span>' for item in items[:5])


def short_path(path: str) -> str:
    if len(path) <= 90:
        return path
    return "..." + path[-87:]
