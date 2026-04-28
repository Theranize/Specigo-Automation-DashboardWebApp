# -*- coding: utf-8 -*-
"""
StakeholderHtmlGenerator — produces the slim, stakeholder-facing HTML report.

One/two page self-contained HTML for managers and non-engineers:
  * Cover   : run date, duration, pass rate, pass/fail/skip counts
  * Table   : one row per test (name, scenario, patient, status, duration)
  * Failures: error line + base64-embedded screenshot thumbnail per failure

No external assets. Safe to email or drop into Slack.
"""
from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime
from html import escape
from math import cos, pi, sin
from pathlib import Path
from typing import Dict, List, Optional

from utils.reporting.constants import flow_label, patient_label
from utils.reporting.embed import embed_image as _embed_image
from utils.reporting.format import fmt_duration as _fmt_duration
from utils.reporting.models import TestResult
from utils.reporting.session_context import marker_for, scenario_for


_PATIENT_TYPE_CACHE: Dict[str, str] = {}
_PATIENT_TYPE_LOADED: bool = False


def _patient_types() -> Dict[str, str]:
    """Lazy-load {patient_id_ref: patient_type} from test_data/front_desk/patient_data.json."""
    global _PATIENT_TYPE_CACHE, _PATIENT_TYPE_LOADED
    if _PATIENT_TYPE_LOADED:
        return _PATIENT_TYPE_CACHE
    try:
        raw = Path("test_data/front_desk/patient_data.json").read_text(encoding="utf-8")
        data = json.loads(raw)
        _PATIENT_TYPE_CACHE = {
            (p.get("patient_id_ref") or "").strip(): (p.get("patient_intent", {}) or {}).get("patient_type", "")
            for p in data.get("patients", [])
        }
    except (IOError, OSError, json.JSONDecodeError):
        _PATIENT_TYPE_CACHE = {}
    _PATIENT_TYPE_LOADED = True
    return _PATIENT_TYPE_CACHE


def _pretty(label: str) -> str:
    """Humanise a snake_case label (e.g. 'existing_primary' -> 'Existing Primary')."""
    return (label or "").replace("_", " ").strip().title() or "—"


_CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --navy:#0d2137;--blue:#1677ff;--green:#389e0d;--red:#cf1322;
  --orange:#d46b08;--grey:#8c8c8c;
  --bg:#f7f8fa;--surface:#fff;--border:#e4e7eb;
  --text:#1a1a1a;--text2:#4a5568;--text3:#8c8c8c;
  --r:10px;--sh:0 1px 3px rgba(0,0,0,.06);
}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;
     background:var(--bg);color:var(--text);font-size:13.5px;line-height:1.55}
.wrap{max-width:920px;margin:0 auto;padding:28px 32px 48px}
/* Cover */
.cover{background:var(--navy);color:#fff;border-radius:var(--r);padding:28px 32px;margin-bottom:22px}
.cover h1{font-size:1.35rem;font-weight:700;letter-spacing:.01em;margin-bottom:4px}
.cover .sub{font-size:.78rem;color:rgba(255,255,255,.62);margin-bottom:18px}
.stat-row{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:12px}
.stat{background:rgba(255,255,255,.08);border-radius:8px;padding:12px 14px}
.stat .n{font-size:1.55rem;font-weight:700;line-height:1.05}
.stat .l{font-size:.68rem;color:rgba(255,255,255,.58);text-transform:uppercase;letter-spacing:.08em;margin-top:3px}
.stat.pr .n.green{color:#95de64}
.stat.pr .n.yellow{color:#ffd666}
.stat.pr .n.red{color:#ff7875}
/* Cover layout with chart */
.cover-grid{display:grid;grid-template-columns:1fr 160px;gap:24px;align-items:center}
.cover-grid .stats-col{min-width:0}
.chart-wrap{display:flex;flex-direction:column;align-items:center;gap:6px}
.chart-wrap svg{display:block}
.chart-wrap .lbl{font-size:.64rem;color:rgba(255,255,255,.58);text-transform:uppercase;letter-spacing:.08em}
.chart-legend{display:flex;gap:10px;font-size:.68rem;margin-top:6px;flex-wrap:wrap;justify-content:center}
.chart-legend .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:4px;vertical-align:middle}
.meta-bar{display:flex;flex-wrap:wrap;gap:22px;margin-top:18px;padding-top:16px;border-top:1px solid rgba(255,255,255,.12);font-size:.8rem;color:rgba(255,255,255,.72)}
.meta-bar span strong{color:#fff;font-weight:600}
/* Section */
h2{font-size:.92rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--text2);margin:22px 0 10px}
/* Breakdown grid */
.bd-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;margin-bottom:4px}
.bd-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);box-shadow:var(--sh);overflow:hidden}
.bd-card h3{font-size:.76rem;font-weight:700;color:var(--text2);padding:10px 14px;background:#fafbfc;
            border-bottom:1px solid var(--border);text-transform:uppercase;letter-spacing:.06em}
.bd-card table{width:100%}
.bd-card th{background:#fcfcfd;font-size:.66rem;padding:8px 14px}
.bd-card td{padding:8px 14px;font-size:.78rem}
.bd-card td.num{text-align:right;font-variant-numeric:tabular-nums}
.bd-card td.label{font-weight:600;color:var(--text)}
.pr-cell{display:inline-flex;align-items:center;gap:6px}
.pr-bar{width:60px;height:6px;background:#eef1f4;border-radius:3px;overflow:hidden;display:inline-block}
.pr-bar span{display:block;height:100%;border-radius:3px}
.pr-bar span.green{background:#52c41a}
.pr-bar span.yellow{background:#faad14}
.pr-bar span.red{background:#f5222d}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);box-shadow:var(--sh);overflow:hidden}
table{width:100%;border-collapse:collapse}
th{background:#fafbfc;text-align:left;font-size:.7rem;text-transform:uppercase;letter-spacing:.06em;
   color:var(--text3);font-weight:700;padding:10px 14px;border-bottom:1px solid var(--border)}
td{padding:11px 14px;border-bottom:1px solid var(--border);font-size:.82rem;vertical-align:top}
tr:last-child td{border-bottom:none}
tr.pass td{background:#fff}
tr.fail td{background:#fff5f5}
tr.skip td{background:#fafafa;color:var(--text2)}
.badge{display:inline-block;padding:2px 10px;border-radius:12px;font-size:.7rem;font-weight:700;letter-spacing:.04em}
.badge.pass{background:#d4edda;color:#155724}
.badge.fail{background:#f8d7da;color:#721c24}
.badge.err {background:#fde2cf;color:#7a3300}
.badge.skip{background:#e2e6ea;color:#3a3f44}
.tname{font-weight:600;color:var(--text)}
.scenario{color:var(--text2);font-size:.78rem;margin-top:2px}
.pid{color:var(--text3);font-size:.72rem;font-family:'SF Mono',Menlo,Consolas,monospace}
.dur{color:var(--text3);font-size:.78rem;font-variant-numeric:tabular-nums;white-space:nowrap}
/* Failures */
.fail-block{background:var(--surface);border:1px solid var(--border);border-left:4px solid var(--red);
            border-radius:var(--r);padding:16px 18px;margin-bottom:14px;box-shadow:var(--sh)}
.fail-block h3{font-size:.88rem;font-weight:700;color:var(--red);margin-bottom:4px}
.fail-block .sc{font-size:.78rem;color:var(--text2);margin-bottom:10px}
.fail-block pre{background:#fafbfc;border:1px solid var(--border);border-radius:6px;
                padding:10px 12px;font-family:'SF Mono',Menlo,Consolas,monospace;font-size:.74rem;
                color:#111;white-space:pre-wrap;word-break:break-word;margin-bottom:10px;max-height:180px;overflow:hidden}
.fail-block img{max-width:100%;max-height:380px;border-radius:6px;border:1px solid var(--border);display:block}
.fail-block .nocap{font-size:.74rem;color:var(--text3);font-style:italic;padding:8px 0}
.empty{padding:24px;text-align:center;color:var(--text3);font-size:.8rem}
/* Footer */
.footer{margin-top:28px;padding-top:14px;border-top:1px solid var(--border);color:var(--text3);font-size:.72rem;text-align:center}
/* Print */
@media print{
  body{background:#fff}
  .wrap{padding:0 10mm}
  .cover{break-after:avoid}
  .fail-block{break-inside:avoid}
  .card{break-inside:auto}
  tr{break-inside:avoid}
}
"""


def _fmt_dt(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d %b %Y, %H:%M")
    except Exception:
        return iso or "-"


def _pr_class(pr: float) -> str:
    if pr >= 90: return "green"
    if pr >= 70: return "yellow"
    return "red"


def _status_badge(status: str) -> str:
    s = (status or "").lower()
    if s == "passed":  return '<span class="badge pass">PASS</span>'
    if s == "failed":  return '<span class="badge fail">FAIL</span>'
    if s == "error":   return '<span class="badge err">ERROR</span>'
    if s == "skipped": return '<span class="badge skip">SKIP</span>'
    return f'<span class="badge skip">{escape(status.upper() or "-")}</span>'


def _row_class(status: str) -> str:
    s = (status or "").lower()
    if s == "passed":  return "pass"
    if s in ("failed", "error"): return "fail"
    return "skip"


def _donut_svg(passed: int, failed: int, skipped: int, size: int = 140) -> str:
    """Return an inline SVG donut chart for pass/fail/skip counts."""
    total = max(passed + failed + skipped, 0)
    cx = cy = size / 2
    r_outer = size / 2 - 4
    r_inner = r_outer - 18

    if total == 0:
        return (
            f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
            f'<circle cx="{cx}" cy="{cy}" r="{r_outer}" fill="rgba(255,255,255,.06)"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r_inner}" fill="#0d2137"/>'
            f'<text x="{cx}" y="{cy+4}" text-anchor="middle" font-size="14" '
            f'fill="rgba(255,255,255,.55)">no data</text></svg>'
        )

    segments = [
        ("#52c41a", passed),
        ("#ff4d4f", failed),
        ("#bfbfbf", skipped),
    ]
    paths = []
    start = -pi / 2
    for color, count in segments:
        if count <= 0:
            continue
        angle = (count / total) * 2 * pi
        end = start + angle
        large = 1 if angle > pi else 0
        x1 = cx + r_outer * cos(start); y1 = cy + r_outer * sin(start)
        x2 = cx + r_outer * cos(end);   y2 = cy + r_outer * sin(end)
        x3 = cx + r_inner * cos(end);   y3 = cy + r_inner * sin(end)
        x4 = cx + r_inner * cos(start); y4 = cy + r_inner * sin(start)
        # Single-segment full circle would need two arcs; draw as two halves if only one type present.
        if count == total:
            paths.append(
                f'<circle cx="{cx}" cy="{cy}" r="{(r_outer + r_inner) / 2}" '
                f'fill="none" stroke="{color}" stroke-width="{r_outer - r_inner}"/>'
            )
        else:
            d = (
                f"M{x1:.2f},{y1:.2f} "
                f"A{r_outer:.2f},{r_outer:.2f} 0 {large} 1 {x2:.2f},{y2:.2f} "
                f"L{x3:.2f},{y3:.2f} "
                f"A{r_inner:.2f},{r_inner:.2f} 0 {large} 0 {x4:.2f},{y4:.2f} Z"
            )
            paths.append(f'<path d="{d}" fill="{color}"/>')
        start = end

    pr = round(passed * 100 / total) if total else 0
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
        + "".join(paths)
        + f'<text x="{cx}" y="{cy-2}" text-anchor="middle" font-size="22" font-weight="700" '
          f'fill="#fff">{pr}%</text>'
        + f'<text x="{cx}" y="{cy+14}" text-anchor="middle" font-size="9" '
          f'fill="rgba(255,255,255,.6)" letter-spacing="1.5">PASS RATE</text>'
        + '</svg>'
    )


def _pr_bar_class(pr: float) -> str:
    if pr >= 90: return "green"
    if pr >= 70: return "yellow"
    return "red"


def _group_results(results: List[TestResult], keyfn) -> "OrderedDict[str, Dict[str, int]]":
    """Group results by keyfn(r); returns OrderedDict of key -> {total, passed, failed, skipped}."""
    grouped: "OrderedDict[str, Dict[str, int]]" = OrderedDict()
    for r in results:
        k = keyfn(r) or "—"
        bucket = grouped.setdefault(k, {"total": 0, "passed": 0, "failed": 0, "skipped": 0})
        bucket["total"] += 1
        status = (r.status or "").lower()
        if status == "passed":
            bucket["passed"] += 1
        elif status in ("failed", "error"):
            bucket["failed"] += 1
        elif status == "skipped":
            bucket["skipped"] += 1
    return grouped


def _render_breakdown_table(title: str, grouped: "OrderedDict[str, Dict[str, int]]") -> str:
    """Render a small breakdown card with a count+pass-rate table."""
    if not grouped:
        return (
            f'<div class="bd-card"><h3>{escape(title)}</h3>'
            f'<div class="empty">No data available.</div></div>'
        )
    rows = []
    for key, b in grouped.items():
        total  = b["total"]
        passed = b["passed"]
        failed = b["failed"]
        pr     = round(passed * 100 / total) if total else 0
        cls    = _pr_bar_class(pr)
        rows.append(
            f'<tr>'
            f'<td class="label">{escape(_pretty(key))}</td>'
            f'<td class="num">{total}</td>'
            f'<td class="num">{passed}</td>'
            f'<td class="num">{failed}</td>'
            f'<td class="num"><span class="pr-cell">'
            f'<span class="pr-bar"><span class="{cls}" style="width:{pr}%"></span></span>'
            f'{pr}%</span></td>'
            f'</tr>'
        )
    return f"""
    <div class="bd-card">
      <h3>{escape(title)}</h3>
      <table>
        <thead>
          <tr>
            <th style="text-align:left">Category</th>
            <th style="text-align:right">Total</th>
            <th style="text-align:right">Pass</th>
            <th style="text-align:right">Fail</th>
            <th style="text-align:right">Pass Rate</th>
          </tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    """


def _render_phase_breakdown(phase_data: Optional[dict]) -> str:
    """Aggregate phase_tracker data into a per-phase pass/fail/not-executed table."""
    if not phase_data:
        return (
            '<div class="bd-card"><h3>By Phase</h3>'
            '<div class="empty" style="padding:18px;text-align:center;color:var(--text3);font-size:.78rem">'
            'No phase data recorded.</div></div>'
        )

    agg: "OrderedDict[str, Dict[str, int]]" = OrderedDict()
    for _test, patients in phase_data.items():
        for _pid, entries in patients.items():
            for e in entries:
                phase  = getattr(e, "phase_name", None) or (e.get("phase_name") if isinstance(e, dict) else "—")
                status = getattr(e, "status", None) or (e.get("status") if isinstance(e, dict) else "")
                bucket = agg.setdefault(phase, {"passed": 0, "failed": 0, "not_exec": 0})
                s = (status or "").upper()
                if s == "PASSED":
                    bucket["passed"] += 1
                elif s == "FAILED":
                    bucket["failed"] += 1
                else:
                    bucket["not_exec"] += 1

    if not agg:
        return (
            '<div class="bd-card"><h3>By Phase</h3>'
            '<div class="empty" style="padding:18px;text-align:center;color:var(--text3);font-size:.78rem">'
            'No phase entries recorded.</div></div>'
        )

    rows = []
    for phase, b in agg.items():
        total  = b["passed"] + b["failed"] + b["not_exec"]
        passed = b["passed"]
        pr     = round(passed * 100 / total) if total else 0
        cls    = _pr_bar_class(pr)
        rows.append(
            f'<tr>'
            f'<td class="label">{escape(phase)}</td>'
            f'<td class="num">{passed}</td>'
            f'<td class="num">{b["failed"]}</td>'
            f'<td class="num">{b["not_exec"]}</td>'
            f'<td class="num"><span class="pr-cell">'
            f'<span class="pr-bar"><span class="{cls}" style="width:{pr}%"></span></span>'
            f'{pr}%</span></td>'
            f'</tr>'
        )
    return f"""
    <div class="bd-card">
      <h3>By Phase</h3>
      <table>
        <thead>
          <tr>
            <th style="text-align:left">Phase</th>
            <th style="text-align:right">Pass</th>
            <th style="text-align:right">Fail</th>
            <th style="text-align:right">Not&nbsp;Exec</th>
            <th style="text-align:right">Pass Rate</th>
          </tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    """


class StakeholderHtmlGenerator:
    """Generates the manager-facing self-contained HTML report."""

    def generate(
        self,
        results:     List[TestResult],
        summary:     dict,
        output_path: Path,
        phase_data:  Optional[dict] = None,
    ) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self._build(results, summary, phase_data), encoding="utf-8")

    def _build(self, results: List[TestResult], summary: dict, phase_data: Optional[dict] = None) -> str:
        total    = summary.get("total", 0)
        passed   = summary.get("passed", 0)
        failed   = summary.get("failed", 0)
        errors   = summary.get("errors", 0)
        skipped  = summary.get("skipped", 0)
        pr       = summary.get("pass_rate", 0)
        dur_s    = summary.get("duration_seconds", 0)
        gen_at   = summary.get("generated_at", "")

        donut = _donut_svg(passed, failed + errors, skipped, size=140)
        legend = (
            '<div class="chart-legend">'
            f'<span><span class="dot" style="background:#52c41a"></span>Pass</span>'
            f'<span><span class="dot" style="background:#ff4d4f"></span>Fail</span>'
            f'<span><span class="dot" style="background:#bfbfbf"></span>Skip</span>'
            '</div>'
        )
        cover = f"""
        <div class="cover">
          <h1>Specigo Automation — Test Report</h1>
          <div class="sub">Generated {escape(_fmt_dt(gen_at))}</div>
          <div class="cover-grid">
            <div class="stats-col">
              <div class="stat-row">
                <div class="stat pr">
                  <div class="n {_pr_class(pr)}">{pr}%</div>
                  <div class="l">Pass Rate</div>
                </div>
                <div class="stat">
                  <div class="n">{passed}<span style="font-size:.75rem;opacity:.6;font-weight:500"> / {total}</span></div>
                  <div class="l">Passed</div>
                </div>
                <div class="stat">
                  <div class="n">{failed + errors}</div>
                  <div class="l">Failed</div>
                </div>
                <div class="stat">
                  <div class="n">{skipped}</div>
                  <div class="l">Skipped</div>
                </div>
              </div>
              <div class="meta-bar">
                <span>Duration <strong>{_fmt_duration(dur_s)}</strong></span>
                <span>Total Scenarios <strong>{total}</strong></span>
                <span>Environment <strong>frontenddevh1.specigo.com</strong></span>
              </div>
            </div>
            <div class="chart-wrap">
              {donut}
              {legend}
            </div>
          </div>
        </div>
        """

        pt_map = _patient_types()
        by_marker = _group_results(results, lambda r: marker_for(r.test_name))
        by_type   = _group_results(results, lambda r: pt_map.get(r.patient_id, ""))
        breakdowns_html = f"""
        <h2>Breakdown</h2>
        <div class="bd-grid">
          {_render_breakdown_table('By Marker', by_marker)}
          {_render_breakdown_table('By Patient Type', by_type)}
          {_render_phase_breakdown(phase_data)}
        </div>
        """

        rows_html = "\n".join(self._row(r) for r in results) if results else \
            '<tr><td colspan="4" class="empty">No tests were executed.</td></tr>'

        table = f"""
        <h2>Scenario Results</h2>
        <div class="card">
          <table>
            <thead>
              <tr>
                <th style="width:42%">Test / Scenario</th>
                <th style="width:18%">Patient</th>
                <th style="width:12%">Status</th>
                <th style="width:12%;text-align:right">Duration</th>
              </tr>
            </thead>
            <tbody>
              {rows_html}
            </tbody>
          </table>
        </div>
        """

        failure_results = [r for r in results if (r.status or "").lower() in ("failed", "error")]
        failures_html = ""
        if failure_results:
            blocks = "\n".join(self._failure_block(r) for r in failure_results)
            failures_html = f"""
            <h2>Failure Details</h2>
            {blocks}
            """

        footer = f"""
        <div class="footer">
          Specigo Automation Dashboard &middot; Stakeholder Report &middot; {escape(_fmt_dt(gen_at))}
        </div>
        """

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Specigo Automation — Test Report</title>
<style>{_CSS}</style>
</head>
<body>
<div class="wrap">
  {cover}
  {breakdowns_html}
  {table}
  {failures_html}
  {footer}
</div>
</body>
</html>
"""

    def _row(self, r: TestResult) -> str:
        scenario = scenario_for(r.test_name) or flow_label(r.test_name)
        pname    = patient_label(r.patient_id) if r.patient_id else "—"
        pid_tag  = f'<div class="pid">{escape(r.patient_id)}</div>' if r.patient_id else ""
        return f"""
        <tr class="{_row_class(r.status)}">
          <td>
            <div class="tname">{escape(r.test_name)}</div>
            <div class="scenario">{escape(scenario)}</div>
          </td>
          <td>
            <div>{escape(pname)}</div>
            {pid_tag}
          </td>
          <td>{_status_badge(r.status)}</td>
          <td class="dur" style="text-align:right">{_fmt_duration(r.duration)}</td>
        </tr>
        """

    def _failure_block(self, r: TestResult) -> str:
        scenario = scenario_for(r.test_name) or flow_label(r.test_name)
        err      = (r.error or "").strip() or "(no error message captured)"
        img_src  = _embed_image(r.screenshot_path)
        img_html = (
            f'<img src="{img_src}" alt="Failure screenshot">'
            if img_src else
            '<div class="nocap">No screenshot captured for this failure.</div>'
        )
        return f"""
        <div class="fail-block">
          <h3>{escape(r.test_name)}</h3>
          <div class="sc">{escape(scenario)}</div>
          <pre>{escape(err)}</pre>
          {img_html}
        </div>
        """
