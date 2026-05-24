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
  /* Typography */
  --ink:   #111827;
  --soft:  #374151;
  --muted: #6b7280;

  /* Surfaces */
  --paper: #f3f4f6;
  --white: #ffffff;
  --line:  #e5e7eb;
  --wash:  #f9fafb;

  /* Accent — teal */
  --accent:      #0b7a75;
  --accent-bg:   #e6f4f3;
  --accent-line: #5fbfbb;

  /* Green — registry / success */
  --green:      #166534;
  --green-bg:   #f0fdf4;
  --green-line: #86efac;
  /* Dark green for code blocks — harmonises with the green registry cards */
  --green-shell:      #0d2818;
  --green-shell-text: #a7f3d0;
  --green-shell-ps1:  #6ee7b7;

  /* Amber — warnings */
  --amber:      #92400e;
  --amber-bg:   #fffbeb;
  --amber-line: #fcd34d;

  /* Red — errors */
  --red:      #991b1b;
  --red-bg:   #fef2f2;
  --red-line: #fca5a5;

  /* Blue — info */
  --blue:      #1e40af;
  --blue-bg:   #eff6ff;
  --blue-line: #93c5fd;
}

/* ── Reset ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  font-size: 14px;
  line-height: 1.6;
  background: var(--paper);
  color: var(--ink);
  -webkit-font-smoothing: antialiased;
}

/* ── Hero ── */
.hero {
  background: var(--white);
  border-bottom: 1px solid var(--line);
  padding: 32px 56px 28px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}
.eyebrow {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .13em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 10px;
}
h1 {
  font-size: 40px;
  font-weight: 800;
  line-height: 1.05;
  letter-spacing: -.5px;
  color: var(--ink);
}
.lede { margin-top: 16px; display: flex; flex-wrap: wrap; gap: 8px; }
.pill {
  display: inline-flex; align-items: center; gap: 6px;
  border-radius: 999px; padding: 5px 14px;
  font-size: 13px; font-weight: 600; border: 1.5px solid;
}
.pill.green { background: var(--green-bg); color: var(--green); border-color: var(--green-line); }
.pill.amber { background: var(--amber-bg); color: var(--amber); border-color: var(--amber-line); }
.pill.blue  { background: var(--blue-bg);  color: var(--blue);  border-color: var(--blue-line); }
.pill.muted { background: var(--wash); color: var(--muted); border-color: var(--line); }
.stamp {
  font-size: 12px; color: var(--muted);
  text-align: right; white-space: nowrap;
  background: var(--wash); border: 1px solid var(--line);
  border-radius: 8px; padding: 7px 12px;
  margin-top: 4px; align-self: flex-start;
}

/* ── Layout ── */
main { padding: 24px 56px 72px; display: flex; flex-direction: column; gap: 18px; }

/* ── KPI strip ── */
.kpis { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; }
.kpi {
  background: var(--white);
  border: 1px solid var(--line);
  border-top: 3px solid var(--line);
  border-radius: 10px;
  padding: 16px 18px;
}
.kpi.green { border-top-color: var(--green);  background: var(--green-bg); border-color: var(--green-line); border-top-color: var(--green); }
.kpi.amber { border-top-color: var(--amber);  background: var(--amber-bg); border-color: var(--amber-line); border-top-color: var(--amber); }
.kpi.red   { border-top-color: var(--red);    background: var(--red-bg);   border-color: var(--red-line);   border-top-color: var(--red); }
.kpi strong { display: block; font-size: 30px; font-weight: 800; line-height: 1; letter-spacing: -1px; }
.kpi .label { font-size: 13px; font-weight: 600; margin-top: 7px; }
.kpi .sub   { font-size: 11px; color: var(--muted); margin-top: 2px; }

/* ── Panels ── */
.panel {
  background: var(--white);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 22px 24px;
  overflow: hidden;
}
.panel-head {
  display: flex; align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
  flex-wrap: wrap; gap: 8px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--line);
}
.panel-head h2 { font-size: 15px; font-weight: 700; }
.panel-head span { font-size: 12px; color: var(--muted); }
.badge {
  border-radius: 999px; padding: 3px 10px;
  font-size: 11px; font-weight: 700; border: 1.5px solid;
}
.badge.green { background: var(--green-bg); color: var(--green); border-color: var(--green-line); }
.badge.amber { background: var(--amber-bg); color: var(--amber); border-color: var(--amber-line); }
.badge.red   { background: var(--red-bg);   color: var(--red);   border-color: var(--red-line); }
.layout-two { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }

/* ── Registry update cards ── */
.update-source {
  border: 1px solid var(--green-line);
  border-radius: 10px;
  margin-bottom: 10px;
  overflow: hidden;
}
.update-source-head {
  background: var(--green-bg);
  border-bottom: 1px solid var(--green-line);
  display: flex; align-items: center; gap: 8px;
  padding: 9px 14px;
}
.source-name {
  font-family: "Cascadia Code", "Fira Code", "Consolas", monospace;
  font-weight: 700; font-size: 13px; color: var(--green);
}
.source-count {
  font-size: 11px; font-weight: 700;
  background: var(--green); color: white;
  border-radius: 999px; padding: 1px 8px;
}
.source-installs { font-size: 11px; color: var(--muted); margin-left: auto; }
.update-source-body { padding: 12px 14px; background: var(--white); }
.skill-tags { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 10px; }
.stag {
  background: var(--green-bg);
  border: 1px solid var(--green-line);
  border-radius: 6px;
  padding: 2px 8px;
  font-size: 11.5px; font-weight: 500; color: var(--green);
}

/* ── Command / shell box ── */
/* Dark forest green — intentionally harmonises with the green registry cards  */
.cmd-box {
  background: var(--green-shell);
  color: var(--green-shell-text);
  border-radius: 8px;
  padding: 10px 14px;
  font-family: "Cascadia Code", "Fira Code", "Consolas", monospace;
  font-size: 12.5px;
  overflow-x: auto;
  display: flex; align-items: center; gap: 8px;
  line-height: 1.5;
}
.cmd-box::before {
  content: '$';
  color: var(--green-shell-ps1);
  font-weight: 700;
  flex-shrink: 0;
  user-select: none;
}

/* ── Usage table ── */
table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead { border-bottom: 2px solid var(--line); }
th {
  font-size: 10px; text-transform: uppercase;
  letter-spacing: .08em; color: var(--muted);
  font-weight: 700; padding: 8px 10px;
  text-align: left; white-space: nowrap;
}
td {
  border-bottom: 1px solid var(--line);
  padding: 9px 10px;
  text-align: left; vertical-align: middle;
}
tr:last-child td { border-bottom: none; }
tr:hover td { background: var(--wash); }
.n { font-weight: 700; }
.bar-wrap { background: var(--line); border-radius: 999px; height: 6px; min-width: 56px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 999px; background: var(--accent); }

/* ── Unused panel ── */
.unused-list { display: flex; flex-direction: column; max-height: 400px; overflow-y: auto; }
.unused-row {
  display: flex; align-items: center;
  justify-content: space-between; gap: 8px;
  padding: 7px 0;
  border-bottom: 1px solid var(--line);
  font-size: 13px;
}
.unused-row:last-child { border-bottom: none; }
.unused-name { font-weight: 600; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.unused-src { font-size: 11px; color: var(--accent); flex-shrink: 0; max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* ── Duplicate cards ── */
.dup-card {
  border-left: 3px solid var(--amber);
  background: var(--amber-bg);
  border-radius: 0 8px 8px 0;
  padding: 10px 14px;
  margin-bottom: 8px;
}
.dup-head {
  font-size: 11px; font-weight: 700; color: var(--amber);
  text-transform: uppercase; letter-spacing: .05em;
  margin-bottom: 6px;
}
.dup-skills { display: flex; flex-wrap: wrap; gap: 5px; }
.dup-skill {
  background: var(--white);
  border: 1px solid var(--amber-line);
  border-radius: 6px;
  padding: 2px 8px; font-size: 12px; font-weight: 500;
}

/* ── Category grid ── */
.cat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 8px; }
.cat-tile {
  background: var(--wash); border: 1px solid var(--line);
  border-radius: 8px; padding: 12px 14px;
  transition: border-color .12s, background .12s;
}
.cat-tile:hover { border-color: var(--accent-line); background: var(--accent-bg); }
.cat-tile strong { display: block; font-size: 22px; font-weight: 800; line-height: 1; color: var(--ink); }
.cat-tile div { font-size: 11px; color: var(--soft); margin-top: 5px; }

/* ── Evidence ── */
details summary {
  cursor: pointer; font-size: 11.5px;
  color: var(--accent); margin-top: 4px;
  user-select: none;
}
details summary:hover { text-decoration: underline; }
.ev-box {
  margin-top: 8px; padding: 8px 10px;
  background: var(--wash); border-radius: 6px;
  border-left: 2px solid var(--accent-line);
}
.ev-row { font-size: 11.5px; margin-bottom: 5px; }
.ev-row:last-child { margin-bottom: 0; }
.ev-file { font-weight: 700; color: var(--soft); }
.ev-snip { display: block; margin-top: 1px; padding-left: 8px; color: var(--muted); font-style: italic; }

/* ── Unknown source ── */
.unknown-grid { display: flex; flex-wrap: wrap; gap: 6px; }
.unknown-chip {
  border: 1px solid var(--line); background: var(--white);
  border-radius: 6px; padding: 4px 10px;
  font-family: "Cascadia Code", "Fira Code", "Consolas", monospace;
  font-size: 12px; color: var(--soft);
}

/* ── Full inventory ── */
.status-registry_updateable   { color: var(--green); font-weight: 700; }
.status-non_git_updateable    { color: var(--amber); font-weight: 700; }
.status-outdated_source_detected { color: var(--amber); font-weight: 700; }
.status-up_to_date            { color: var(--green); font-weight: 600; }
.status-unknown_source        { color: var(--muted); }
.status-non_git_no_baseline   { color: var(--muted); }
.status-dirty_git             { color: var(--red); font-weight: 700; }
.status-failed                { color: var(--red); font-weight: 700; }
.inv-name { font-weight: 700; font-size: 13px; }
.inv-desc { font-size: 11.5px; color: var(--muted); max-width: 340px; line-height: 1.4; margin-top: 2px; }
code {
  font-family: "Cascadia Code", "Fira Code", "Consolas", monospace;
  font-size: 12px; background: var(--wash);
  padding: 1px 5px; border-radius: 4px;
  color: var(--soft);
}
#q {
  border: 1.5px solid var(--line); border-radius: 8px;
  padding: 7px 12px; font: inherit; font-size: 13px;
  width: min(300px, 100%); outline: none;
  transition: border-color .15s;
  background: var(--wash);
}
#q:focus { border-color: var(--accent); background: var(--white); }

/* ── Responsive ── */
@media (max-width: 1024px) {
  .kpis { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 768px) {
  .hero, main { padding-left: 20px; padding-right: 20px; }
  .layout-two { grid-template-columns: 1fr; }
  h1 { font-size: 32px; }
  .hero { flex-direction: column; }
  .stamp { align-self: flex-start; }
}
@media (max-width: 480px) {
  .kpis { grid-template-columns: 1fr 1fr; }
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
        installs = max(
            (by_name.get(i.skill, SkillRecord.__new__(SkillRecord)).registry_installs or 0)
            for i in source_items
        ) if by_name else 0
        installs_html = (
            f'<span class="source-installs">{installs:,} installs</span>'
            if installs > 0 else ""
        )
        n = len(source_items)
        parts.append(
            f'<div class="update-source">'
            # ── card header: repo name + pill + install count
            f'<div class="update-source-head">'
            f'<span class="source-name">{escape(source)}</span>'
            f'<span class="source-count">{n} skill{"s" if n != 1 else ""}</span>'
            f'{installs_html}'
            f'</div>'
            # ── card body: skill pills + command
            f'<div class="update-source-body">'
            f'<div class="skill-tags">{tags}</div>'
            f'<div class="cmd-box">npx skills add {escape(source)} -g</div>'
            f'</div>'
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
