"""Action-first HTML report and update commands for the skill audit."""
from __future__ import annotations

import html
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from .models import DuplicateGroup, SkillRecord, UpdateAction, UsageRecord


# ── Utilities ─────────────────────────────────────────────────────────────


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _source_label(record: SkillRecord) -> str:
    if record.registry_source:
        return "skills.sh"
    if record.is_git:
        return "git-backed"
    if record.source_url:
        return f"source-{record.source_confidence or 'unknown'}"
    return "unknown"


# ── Update commands (Markdown) ────────────────────────────────────────────


def render_manual_update_commands(path: Path, updates: list[UpdateAction]) -> None:
    """Write a grouped, action-first update commands file."""
    lines = [
        "# Skill Update Commands",
        "",
        "> Copy-paste these commands to update your skills.",
        "> All commands are safe — they install over existing files without deleting anything.",
        "",
    ]

    # Section 1: skills.sh registry
    registry_items = [u for u in updates if u.status == "registry_updateable" and u.registry_command]
    if registry_items:
        by_source: dict[str, list[UpdateAction]] = {}
        for item in registry_items:
            by_source.setdefault(item.remote or "unknown", []).append(item)

        lines += ["## From skills.sh Registry (Recommended)", "",
                  "Update via the official registry:", ""]
        for source, items in sorted(by_source.items()):
            skill_names = ", ".join(i.skill for i in items)
            lines += [
                f"### `{source}` ({len(items)} skill{'s' if len(items) > 1 else ''})",
                f"Skills: {skill_names}", "",
                "```bash",
                f"npx skills add {source} -g",
                "```", "",
                "_Or update one at a time:_", "", "```bash",
            ]
            for item in items:
                lines.append(item.registry_command or "")
            lines += ["```", ""]

    # Section 2: git clone fallback
    git_items = [u for u in updates if u.status in {"non_git_updateable", "outdated_source_detected"} and u.manual_command]
    if git_items:
        lines += ["## Git Clone Fallback", "",
                  "Skills with a discovered source but not on skills.sh:", ""]
        for item in git_items:
            conf_note = f" (confidence={item.source_confidence})" if item.source_confidence else ""
            lines += [
                f"### {item.skill}",
                f"Source: `{item.remote or 'unknown'}`{conf_note}", "",
                "```bash",
                item.manual_command,
                "```", "",
            ]

    if not registry_items and not git_items:
        lines += ["No update commands available yet.",
                  "", "Run with `--registry-search` to discover skills on skills.sh."]

    path.write_text("\n".join(lines), encoding="utf-8")


# ── HTML report ────────────────────────────────────────────────────────────


def render_report(
    output_path: Path,
    records: list[SkillRecord],
    usage: list[UsageRecord],
    updates: list[UpdateAction],
    duplicates: list[DuplicateGroup],
    generated_at: datetime,
) -> None:
    usage_by_skill = {u.skill: u for u in usage}
    update_by_skill = {a.skill: a for a in updates}
    category_counts = Counter(r.category for r in records)
    used_30 = sum(1 for u in usage if u.count_30d > 0)
    unused = sorted((u for u in usage if u.count_30d == 0), key=lambda u: u.skill)
    registry_items = [a for a in updates if a.status == "registry_updateable"]
    non_git_items = [a for a in updates if a.status == "non_git_updateable"]
    unknown_items = [a for a in updates if a.status == "unknown_source"]
    top_used = sorted((u for u in usage if u.count_30d > 0), key=lambda u: (-u.count_30d, u.skill))[:24]
    registry_by_name = {r.name: r for r in records if r.registry_source}

    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Skill Audit — {escape(generated_at.strftime("%Y-%m-%d"))}</title>
  <style>{CSS}</style>
</head>
<body>
<header class="hero">
  <div>
    <p class="eyebrow">Skill Maintainer Audit</p>
    <h1>{len(records)} Skills</h1>
    <p class="lede">
      <span class="pill green">{len(registry_items)} updatable via skills.sh</span>
      <span class="pill amber">{len(unused)} unused 30d</span>
      <span class="pill blue">{len(duplicates)} duplicate groups</span>
      <span class="pill muted">{len(unknown_items)} unknown source</span>
    </p>
  </div>
  <div class="stamp">{escape(generated_at.strftime("%Y-%m-%d %H:%M UTC"))}</div>
</header>

<main>
  <!-- 1. KPIs -->
  <div class="kpis">
    {kpi("Total", len(records), "installed")}
    {kpi("On skills.sh", len(registry_items), "updatable", "green" if registry_items else "")}
    {kpi("Active 30d", used_30, "used")}
    {kpi("Unused 30d", len(unused), "dormant", "amber" if len(unused) > 10 else "")}
    {kpi("Duplicates", len(duplicates), "groups", "amber" if duplicates else "")}
    {kpi("Unknown src", len(unknown_items), "untracked", "red" if len(unknown_items) > 50 else "amber")}
  </div>

  <!-- 2. Update actions — most important section -->
  <section class="panel">
    <div class="panel-head">
      <h2>Update via skills.sh Registry</h2>
      <span class="badge green">{len(registry_items)} skills · official registry</span>
    </div>
    {registry_update_panel(registry_items, registry_by_name)}
  </section>

  <!-- 3. Usage: most used + unused side by side -->
  <div class="layout-two">
    <section class="panel">
      <div class="panel-head"><h2>Most Used (30 days)</h2><span>{used_30} of {len(records)} active</span></div>
      {top_used_table(top_used)}
    </section>
    <section class="panel">
      <div class="panel-head">
        <h2>Never Used (30 days)</h2>
        <span class="badge amber">{len(unused)}</span>
      </div>
      {unused_panel(unused, registry_by_name)}
    </section>
  </div>

  <!-- 4. Duplicates + Categories -->
  <div class="layout-two">
    <section class="panel">
      <div class="panel-head"><h2>Duplicate Capabilities</h2><span>{len(duplicates)} groups</span></div>
      {duplicates_panel(duplicates, usage_by_skill)}
    </section>
    <section class="panel">
      <div class="panel-head"><h2>Skill Categories</h2><span>by capability</span></div>
      {category_grid(category_counts)}
    </section>
  </div>

  <!-- 5. Non-registry updateable -->
  {non_registry_panel(non_git_items) if non_git_items else ""}

  <!-- 6. Not found on registry -->
  <section class="panel">
    <div class="panel-head">
      <h2>Not Found on skills.sh</h2>
      <span>{len(unknown_items)} skills · run <code>--registry-search</code> to resolve</span>
    </div>
    {unknown_panel(unknown_items)}
  </section>

  <!-- 7. Full inventory -->
  <section class="panel">
    <div class="panel-head">
      <h2>Full Inventory</h2>
      <input id="q" type="search" placeholder="Filter by name, category, source…">
    </div>
    {full_inventory(records, usage_by_skill, update_by_skill)}
  </section>
</main>
<script>{SCRIPT}</script>
</body></html>"""
    output_path.write_text(html_text, encoding="utf-8")


# ── CSS ────────────────────────────────────────────────────────────────────

CSS = """
:root {
  --ink: #1a2433; --soft: #4a5568; --muted: #718096;
  --paper: #f8faf9; --white: #ffffff;
  --line: #e2e8f0; --wash: #edf2f0;
  --green: #276749; --green-bg: #f0fff4; --green-line: #9ae6b4;
  --amber: #975a16; --amber-bg: #fffaf0; --amber-line: #fbd38d;
  --red: #c53030; --red-bg: #fff5f5; --red-line: #feb2b2;
  --blue: #2b6cb0; --blue-bg: #ebf8ff; --blue-line: #90cdf4;
  --accent: #0b7a75;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, "Segoe UI", sans-serif;
  font-size: 15px; line-height: 1.6;
  background: var(--paper); color: var(--ink);
}
.hero {
  padding: 36px 52px 28px;
  border-bottom: 1px solid var(--line);
  display: flex; align-items: flex-start; justify-content: space-between; gap: 24px;
}
.eyebrow { font-size: 11px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--accent); margin-bottom: 8px; }
h1 { font-size: 48px; line-height: 1; color: var(--ink); }
.lede { margin-top: 14px; display: flex; flex-wrap: wrap; gap: 8px; }
.pill { border-radius: 999px; padding: 4px 12px; font-size: 14px; font-weight: 600; border: 1.5px solid; }
.pill.green { background: var(--green-bg); color: var(--green); border-color: var(--green-line); }
.pill.amber { background: var(--amber-bg); color: var(--amber); border-color: var(--amber-line); }
.pill.blue  { background: var(--blue-bg); color: var(--blue); border-color: var(--blue-line); }
.pill.muted { background: var(--wash); color: var(--muted); border-color: var(--line); }
.stamp { font-size: 13px; color: var(--muted); text-align: right; white-space: nowrap; margin-top: 4px; }
main { padding: 28px 52px 60px; display: flex; flex-direction: column; gap: 20px; }
.kpis { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; }
.kpi { background: var(--white); border: 1px solid var(--line); border-radius: 10px; padding: 18px 16px; }
.kpi.green { border-color: var(--green-line); background: var(--green-bg); }
.kpi.amber { border-color: var(--amber-line); background: var(--amber-bg); }
.kpi.red   { border-color: var(--red-line); background: var(--red-bg); }
.kpi strong { display: block; font-size: 34px; line-height: 1; }
.kpi .label { font-weight: 700; margin-top: 6px; }
.kpi .sub { font-size: 12px; color: var(--muted); margin-top: 2px; }
.panel { background: var(--white); border: 1px solid var(--line); border-radius: 10px; padding: 22px; overflow: hidden; }
.panel-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; flex-wrap: wrap; gap: 8px; }
.panel-head h2 { font-size: 18px; }
.panel-head span { font-size: 13px; color: var(--muted); }
.badge { border-radius: 999px; padding: 3px 10px; font-size: 13px; font-weight: 600; border: 1.5px solid; }
.badge.green { background: var(--green-bg); color: var(--green); border-color: var(--green-line); }
.badge.amber { background: var(--amber-bg); color: var(--amber); border-color: var(--amber-line); }
.badge.red   { background: var(--red-bg); color: var(--red); border-color: var(--red-line); }
.layout-two { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
/* Registry update panel */
.update-source { background: var(--green-bg); border: 1px solid var(--green-line); border-radius: 8px; padding: 14px 16px; margin-bottom: 12px; }
.update-source-head { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.source-name { font-weight: 700; font-size: 15px; color: var(--green); }
.source-count { font-size: 12px; background: var(--green); color: white; border-radius: 999px; padding: 1px 8px; }
.cmd-box { background: #1a2433; color: #e2e8f0; border-radius: 6px; padding: 10px 14px; font-family: monospace; font-size: 13px; overflow-x: auto; margin-top: 8px; }
.skill-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.stag { background: white; border: 1px solid var(--green-line); border-radius: 999px; padding: 2px 9px; font-size: 12px; color: var(--green); }
.stag.unknown { border-color: var(--line); color: var(--muted); background: var(--wash); }
/* Usage tables */
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { border-bottom: 1px solid var(--line); padding: 9px 10px; text-align: left; vertical-align: top; }
th { font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); font-weight: 700; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: var(--wash); }
.n { font-weight: 700; }
.bar-wrap { background: var(--line); border-radius: 999px; height: 8px; min-width: 60px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 999px; background: var(--accent); }
/* Unused panel */
.unused-list { display: flex; flex-direction: column; gap: 4px; max-height: 360px; overflow-y: auto; }
.unused-row { display: flex; align-items: center; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--line); font-size: 13px; }
.unused-row:last-child { border-bottom: none; }
.unused-name { font-weight: 600; }
.unused-src { font-size: 12px; color: var(--accent); }
/* Duplicate cards */
.dup-card { border: 1px solid var(--amber-line); background: var(--amber-bg); border-radius: 8px; padding: 12px 14px; margin-bottom: 10px; }
.dup-head { font-weight: 700; color: var(--amber); margin-bottom: 6px; font-size: 13px; }
.dup-skills { display: flex; flex-wrap: wrap; gap: 6px; }
.dup-skill { background: white; border: 1px solid var(--amber-line); border-radius: 999px; padding: 3px 10px; font-size: 12px; }
/* Category grid */
.cat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 8px; }
.cat-tile { background: var(--wash); border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; }
.cat-tile strong { display: block; font-size: 26px; }
/* Evidence */
details summary { cursor: pointer; font-size: 12px; color: var(--accent); margin-top: 4px; }
.ev-box { margin-top: 6px; padding: 8px; background: var(--wash); border-radius: 6px; }
.ev-row { font-size: 12px; margin-bottom: 4px; }
.ev-file { font-weight: 700; color: var(--soft); margin-right: 6px; }
.ev-snip { color: var(--muted); font-style: italic; }
/* Unknown source */
.unknown-grid { display: flex; flex-wrap: wrap; gap: 6px; }
.unknown-chip { border: 1px solid var(--line); background: var(--wash); border-radius: 999px; padding: 4px 12px; font-size: 13px; color: var(--soft); }
/* Full inventory */
.status-registry_updateable { color: var(--green); font-weight: 700; }
.status-non_git_updateable  { color: var(--amber); font-weight: 700; }
.status-outdated_source_detected { color: var(--amber); font-weight: 700; }
.status-up_to_date { color: var(--green); font-weight: 700; }
.status-unknown_source { color: var(--muted); }
.status-dirty_git { color: var(--red); font-weight: 700; }
.status-failed { color: var(--red); font-weight: 700; }
.inv-name { font-weight: 700; }
.inv-desc { font-size: 12px; color: var(--muted); max-width: 360px; }
code { font-family: monospace; font-size: 12px; background: var(--wash); padding: 1px 5px; border-radius: 3px; }
#q { border: 1px solid var(--line); border-radius: 8px; padding: 8px 12px; font: inherit; width: min(340px, 100%); }
@media (max-width: 900px) {
  .hero, main { padding-left: 18px; padding-right: 18px; }
  .kpis, .layout-two { grid-template-columns: 1fr 1fr; }
  h1 { font-size: 36px; }
}
"""


# ── JS ─────────────────────────────────────────────────────────────────────

SCRIPT = """
const q = document.getElementById('q');
if (q) q.addEventListener('input', () => {
  const v = q.value.toLowerCase();
  document.querySelectorAll('[data-row]').forEach(r => {
    r.style.display = r.textContent.toLowerCase().includes(v) ? '' : 'none';
  });
});
"""


# ── Component functions ────────────────────────────────────────────────────


def kpi(label: str, value: int, sub: str, color: str = "") -> str:
    cls = f' class="kpi {color}"' if color else ' class="kpi"'
    return f'<div{cls}><strong>{value}</strong><div class="label">{escape(label)}</div><div class="sub">{escape(sub)}</div></div>'


def registry_update_panel(items: list[UpdateAction], by_name: dict[str, SkillRecord]) -> str:
    if not items:
        return '<p style="color:var(--muted);font-size:14px">No skills found on skills.sh registry yet. Run with <code>--registry-search</code> to discover.</p>'

    by_source: dict[str, list[UpdateAction]] = {}
    for item in items:
        by_source.setdefault(item.remote or "unknown", []).append(item)

    parts = []
    for source, source_items in sorted(by_source.items(), key=lambda x: -len(x[1])):
        tags = "".join(
            f'<span class="stag">{escape(i.skill)}</span>' for i in source_items
        )
        installs = max((by_name.get(i.skill, SkillRecord.__new__(SkillRecord)).registry_installs or 0) for i in source_items) if by_name else 0
        install_txt = f" · {installs:,} installs" if installs > 0 else ""
        parts.append(
            f'<div class="update-source">'
            f'<div class="update-source-head">'
            f'<span class="source-name">{escape(source)}</span>'
            f'<span class="source-count">{len(source_items)} skill{"s" if len(source_items) > 1 else ""}{install_txt}</span>'
            f'</div>'
            f'<div class="skill-tags">{tags}</div>'
            f'<div class="cmd-box">npx skills add {escape(source)} -g</div>'
            f'</div>'
        )
    return "".join(parts)


def top_used_table(items: list[UsageRecord]) -> str:
    if not items:
        return '<p style="color:var(--muted);font-size:14px">No usage data found.</p>'
    max_count = max(u.count_30d for u in items) or 1
    rows = []
    for u in items:
        pct = int(u.count_30d / max_count * 100)
        evidence_html = ""
        if u.evidence:
            def _fname(path: str) -> str:
                return path.replace("\\", "/").split("/")[-1]
            snippets = "".join(
                f'<div class="ev-row"><span class="ev-file">{escape(_fname(e.get("file", "")))}</span>'
                f' <span class="ev-snip">{escape(e.get("snippet", "")[:120])}</span></div>'
                for e in u.evidence[:5]
            )
            evidence_html = f'<details><summary>Show evidence</summary><div class="ev-box">{snippets}</div></details>'
        rows.append(
            f'<tr><td class="n">{escape(u.skill)}{evidence_html}</td>'
            f'<td>{u.count_7d}</td><td>{u.count_30d}</td>'
            f'<td><div class="bar-wrap"><div class="bar-fill" style="width:{pct}%"></div></div></td></tr>'
        )
    return (
        '<table><thead><tr><th>Skill</th><th>7d</th><th>30d</th><th></th></tr></thead><tbody>'
        + "".join(rows) + "</tbody></table>"
    )


def unused_panel(items: list[UsageRecord], by_name: dict[str, SkillRecord]) -> str:
    if not items:
        return '<p style="color:var(--green);font-size:14px">All skills used in the last 30 days.</p>'
    rows = []
    for u in items[:60]:
        record = by_name.get(u.skill)
        src = ""
        if record:
            src = f'<span class="unused-src">{escape(record.registry_source or record.source_url or "")}</span>'
        rows.append(
            f'<div class="unused-row">'
            f'<span class="unused-name">{escape(u.skill)}</span>'
            f'{src}</div>'
        )
    extra = f'<p style="color:var(--muted);font-size:12px;margin-top:8px">+{len(items)-60} more</p>' if len(items) > 60 else ""
    return f'<div class="unused-list">{"".join(rows)}</div>{extra}'


def duplicates_panel(groups: list[DuplicateGroup], usage_by_skill: dict[str, UsageRecord]) -> str:
    if not groups:
        return '<p style="color:var(--muted);font-size:14px">No overlapping skill groups detected.</p>'
    parts = []
    for g in groups[:12]:
        skills_html = "".join(
            f'<span class="dup-skill">{escape(s)} ({usage_by_skill.get(s, UsageRecord(s)).count_30d})</span>'
            for s in g.skills
        )
        parts.append(
            f'<div class="dup-card">'
            f'<div class="dup-head">{escape(g.category)} — {escape(g.reason)}</div>'
            f'<div class="dup-skills">{skills_html}</div>'
            f'</div>'
        )
    return "".join(parts)


def category_grid(counts: Counter) -> str:
    tiles = "".join(
        f'<div class="cat-tile"><strong>{n}</strong><div>{escape(c)}</div></div>'
        for c, n in counts.most_common()
    )
    return f'<div class="cat-grid">{tiles}</div>'


def non_registry_panel(items: list[UpdateAction]) -> str:
    if not items:
        return ""
    rows = []
    for item in items[:30]:
        conf = item.source_confidence or "?"
        rows.append(
            f'<tr data-row>'
            f'<td class="n">{escape(item.skill)}</td>'
            f'<td><code>{escape(item.remote or "")}</code></td>'
            f'<td>{escape(conf)}</td>'
            f'<td><details><summary>Command</summary>'
            f'<div class="cmd-box" style="margin-top:8px">{escape(item.manual_command or "")}</div>'
            f'</details></td></tr>'
        )
    return (
        '<section class="panel">'
        '<div class="panel-head"><h2>Git Clone Fallback Updates</h2>'
        f'<span>{len(items)} skills with git source but not on registry</span></div>'
        '<table><thead><tr><th>Skill</th><th>Source</th><th>Confidence</th><th>Command</th></tr></thead>'
        '<tbody>' + "".join(rows) + '</tbody></table></section>'
    )


def unknown_panel(items: list[UpdateAction]) -> str:
    if not items:
        return '<p style="color:var(--green);font-size:14px">All skills have a known source.</p>'
    chips = "".join(f'<span class="unknown-chip">{escape(i.skill)}</span>' for i in items)
    return (
        f'<p style="font-size:13px;color:var(--muted);margin-bottom:12px">'
        f'These skills were not found on skills.sh. Re-run with '
        f'<code>--registry-search</code> or add them to a source manifest.</p>'
        f'<div class="unknown-grid">{chips}</div>'
    )


def full_inventory(
    records: list[SkillRecord],
    usage_by_skill: dict[str, UsageRecord],
    update_by_skill: dict[str, UpdateAction],
) -> str:
    rows = []
    for r in sorted(records, key=lambda x: x.category + x.name):
        u = usage_by_skill.get(r.name)
        a = update_by_skill.get(r.name)
        status = a.status if a else "unknown"
        src = r.registry_source or r.source_url or "—"
        rows.append(
            f'<tr data-row>'
            f'<td><div class="inv-name">{escape(r.name)}</div>'
            f'<div class="inv-desc">{escape(r.summary[:120] if r.summary else "")}</div></td>'
            f'<td>{escape(r.category)}</td>'
            f'<td>{u.count_7d if u else 0} / {u.count_30d if u else 0}</td>'
            f'<td class="status-{escape(status)}">{escape(status.replace("_", " "))}</td>'
            f'<td style="font-size:12px;color:var(--accent)">{escape(src)}</td>'
            f'</tr>'
        )
    return (
        '<table><thead><tr>'
        '<th>Skill</th><th>Category</th><th>7d/30d</th><th>Status</th><th>Source</th>'
        '</tr></thead><tbody>' + "".join(rows) + '</tbody></table>'
    )
