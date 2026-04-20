# -*- coding: utf-8 -*-
"""
HtmlReportGenerator — produces summary_report.html.

Self-contained interactive dashboard with:
  • Current Run tab  : stat cards, doughnut chart, pass-rate trend, filterable result table
  • Run History tab  : history cards, trend bar chart, expandable run-detail rows

MNC standard: type hints, docstrings, section comments.
"""
from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path
from typing import List

from utils.reporting.constants import patient_label
from utils.reporting.models import TestResult
from utils.reporting.session import _load_run_history


# =============================================================================
# EMBEDDED CSS
# =============================================================================
_CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --navy:#0d2137;--blue:#1677ff;--green:#389e0d;--red:#cf1322;
  --orange:#d46b08;--purple:#722ed1;--teal:#08979c;--grey:#8c8c8c;
  --bg:#f0f2f5;--surface:#fff;--border:#e8e8e8;
  --text:#1a1a1a;--text2:#595959;--text3:#8c8c8c;
  --r:8px;--sh:0 2px 8px rgba(0,0,0,.08);--sh2:0 4px 16px rgba(0,0,0,.14);
}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;
     background:var(--bg);color:var(--text);font-size:14px;line-height:1.6;padding-bottom:64px}
/* ===== STICKY HEADER ===== */
.hdr{background:var(--navy);color:#fff;height:56px;padding:0 32px;
     display:flex;align-items:center;justify-content:space-between;
     position:sticky;top:0;z-index:500;box-shadow:0 2px 10px rgba(0,0,0,.4)}
.hdr-brand{display:flex;flex-direction:column;gap:1px}
.hdr-brand .logo{font-size:1rem;font-weight:800;letter-spacing:.02em}
.hdr-brand .logo span{color:#4096ff}
.hdr-brand .sub{font-size:.68rem;color:rgba(255,255,255,.42)}
.hdr-right{display:flex;align-items:center;gap:16px}
.hdr-pill{display:flex;align-items:center;gap:6px;background:rgba(255,255,255,.09);
          border-radius:20px;padding:4px 14px}
.hp-num{font-size:1.15rem;font-weight:800;line-height:1}
.hp-lbl{font-size:.65rem;color:rgba(255,255,255,.5);text-transform:uppercase;letter-spacing:.07em}
.hp-green{color:#73d13d}.hp-yellow{color:#ffd666}.hp-red{color:#ff7875}
.hdr-nav{display:flex;gap:4px}
.hnav-btn{padding:5px 14px;border:none;border-radius:16px;background:transparent;
          color:rgba(255,255,255,.65);cursor:pointer;font-size:.8rem;
          font-family:inherit;transition:all .15s}
.hnav-btn:hover{background:rgba(255,255,255,.1);color:#fff}
.hnav-btn.active{background:rgba(255,255,255,.16);color:#fff;font-weight:600}
/* ===== LAYOUT ===== */
.wrap{max-width:1480px;margin:0 auto;padding:24px 32px}
/* ===== MAIN TABS ===== */
.main-tabs{display:flex;gap:0;border-bottom:2px solid var(--border);margin-bottom:24px}
.main-tab{padding:10px 22px;border:none;background:transparent;cursor:pointer;
          font-size:.86rem;color:var(--text2);font-family:inherit;
          border-bottom:3px solid transparent;margin-bottom:-2px;
          transition:all .15s;display:flex;align-items:center;gap:8px;font-weight:500}
.main-tab:hover{color:var(--blue);background:#f0f5ff}
.main-tab.active{color:var(--blue);border-bottom-color:var(--blue);font-weight:700}
.main-tab .tc{background:#e6f0ff;color:var(--blue);border-radius:10px;
              padding:1px 7px;font-size:.7rem;font-weight:700}
.main-tab.active .tc{background:var(--blue);color:#fff}
.tab-panel{display:none}.tab-panel.active{display:block}
/* ===== RUN META BAR ===== */
.run-meta{background:var(--surface);border-radius:var(--r);box-shadow:var(--sh);
          padding:11px 20px;margin-bottom:18px;display:flex;align-items:center;
          gap:28px;flex-wrap:wrap;border-left:4px solid var(--blue)}
.rm-item{display:flex;flex-direction:column;gap:0}
.rm-lbl{font-size:.65rem;text-transform:uppercase;letter-spacing:.08em;color:var(--text3)}
.rm-val{font-size:.88rem;font-weight:600;color:var(--text)}
/* ===== STAT CARDS ===== */
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(128px,1fr));
       gap:12px;margin-bottom:18px}
.card{background:var(--surface);border-radius:var(--r);box-shadow:var(--sh);
      padding:16px 14px;display:flex;flex-direction:column;align-items:center;
      gap:4px;border-top:3px solid var(--border);
      transition:transform .15s,box-shadow .15s;cursor:default}
.card:hover{transform:translateY(-2px);box-shadow:var(--sh2)}
.card.c-all{border-color:#1677ff}.card.c-pass{border-color:#52c41a}
.card.c-fail{border-color:#ff4d4f}.card.c-err{border-color:#fa8c16}
.card.c-skip{border-color:#d9d9d9}.card.c-pat{border-color:#722ed1}
.card.c-flow{border-color:#13c2c2}
.card .num{font-size:2rem;font-weight:800;line-height:1.1}
.card .lbl{font-size:.66rem;color:var(--text3);text-transform:uppercase;
           letter-spacing:.07em;text-align:center}
.n-blue{color:#1677ff}.n-green{color:#389e0d}.n-red{color:#cf1322}
.n-orange{color:#d46b08}.n-grey{color:#8c8c8c}.n-purple{color:#722ed1}
.n-teal{color:#08979c}
/* ===== CHARTS ROW ===== */
.charts-row{display:grid;grid-template-columns:280px 1fr;gap:16px;margin-bottom:18px}
@media(max-width:820px){.charts-row{grid-template-columns:1fr}}
.chart-card{background:var(--surface);border-radius:var(--r);box-shadow:var(--sh);
            padding:20px;display:flex;flex-direction:column;gap:10px}
.chart-title{font-size:.72rem;font-weight:700;text-transform:uppercase;
             letter-spacing:.07em;color:var(--text2)}
.chart-wrap{position:relative;width:100%;display:flex;align-items:center;
            justify-content:center;min-height:200px}
/* ===== PHASE LINK BAR ===== */
.phase-link-bar{background:#f0f5ff;border:1px solid #adc6ff;border-radius:var(--r);
                padding:10px 20px;margin-bottom:16px;display:flex;align-items:center;
                justify-content:space-between;font-size:.85rem}
.phase-link-bar a{color:var(--blue);font-weight:600;text-decoration:none;
                  display:inline-flex;align-items:center;gap:5px}
.phase-link-bar a:hover{text-decoration:underline}
/* ===== TOOLBAR ===== */
.toolbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:12px}
.fbtn{padding:5px 14px;border:1px solid var(--border);border-radius:20px;
      background:var(--surface);cursor:pointer;font-size:.79rem;
      color:var(--text2);transition:all .12s;white-space:nowrap;font-family:inherit}
.fbtn:hover{border-color:var(--blue);color:var(--blue)}
.fbtn.active{background:var(--blue);border-color:var(--blue);color:#fff;font-weight:600}
.fbtn.fa-pass.active{background:#52c41a;border-color:#52c41a}
.fbtn.fa-fail.active{background:#ff4d4f;border-color:#ff4d4f}
.fbtn.fa-error.active{background:#fa8c16;border-color:#fa8c16}
.fbtn.fa-skip.active{background:#8c8c8c;border-color:#8c8c8c}
.search-box{margin-left:auto;padding:6px 14px;border:1px solid var(--border);
            border-radius:20px;font-size:.82rem;outline:none;
            transition:border-color .12s;min-width:200px;font-family:inherit}
.search-box:focus{border-color:var(--blue);box-shadow:0 0 0 2px rgba(22,119,255,.1)}
/* ===== RESULT TABLE ===== */
.tbl-wrap{background:var(--surface);border-radius:var(--r);box-shadow:var(--sh);overflow:hidden}
table{width:100%;border-collapse:collapse}
thead th{background:var(--navy);color:rgba(255,255,255,.85);
         padding:10px 14px;text-align:left;font-size:.7rem;
         text-transform:uppercase;letter-spacing:.07em;
         white-space:nowrap;cursor:pointer;user-select:none}
thead th:hover{background:#1a3550}
thead th .si{margin-left:4px;opacity:.4;font-size:.68rem}
thead th.sorted .si{opacity:1}
tbody td{padding:9px 14px;border-bottom:1px solid #f5f5f5;vertical-align:middle;font-size:.84rem}
tbody tr:last-child td{border-bottom:none}
tbody tr.row-pass:hover{background:#f6ffed}
tbody tr.row-fail{background:#fff2f0}
tbody tr.row-fail:hover{background:#ffe8e6}
tbody tr.row-error{background:#fff7e6}
tbody tr.row-error:hover{background:#fff1d6}
tbody tr.row-skip{background:#fafafa}
tbody tr.row-skip:hover{background:#f5f5f5}
/* ===== BADGES ===== */
.badge{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;
       border-radius:10px;font-size:.74rem;font-weight:700;white-space:nowrap}
.badge::before{content:'';width:6px;height:6px;border-radius:50%;display:inline-block;flex-shrink:0}
.b-pass{background:#f6ffed;color:#389e0d;border:1px solid #b7eb8f}
.b-pass::before{background:#52c41a}
.b-fail{background:#fff2f0;color:#cf1322;border:1px solid #ffa39e}
.b-fail::before{background:#ff4d4f}
.b-error{background:#fff7e6;color:#d46b08;border:1px solid #ffd591}
.b-error::before{background:#fa8c16}
.b-skip{background:#fafafa;color:#8c8c8c;border:1px solid #d9d9d9}
.b-skip::before{background:#d9d9d9}
/* ===== TABLE CELLS ===== */
.test-cell{font-family:'Consolas','Courier New',monospace;font-size:.8rem;
           color:#262626;max-width:200px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mod-cell{color:var(--text2)}.pid-cell{font-weight:600;color:var(--blue);white-space:nowrap}
.err-cell{color:#cf1322;font-size:.8rem;max-width:220px}
.err-short{cursor:pointer}.err-short:hover{text-decoration:underline dashed}
.err-full{display:none;white-space:pre-wrap;word-break:break-all;font-size:.76rem}
.err-expanded .err-short{display:none}.err-expanded .err-full{display:block}
a.shot-link{color:var(--blue);font-size:.8rem;text-decoration:none;
            display:inline-flex;align-items:center;gap:3px}
a.shot-link:hover{text-decoration:underline}
a.shot-link::before{content:'\\1F4F8';font-size:.75rem}
.dur-cell{white-space:nowrap;color:var(--text2);font-size:.82rem}
.no-data{text-align:center;padding:48px!important;color:var(--text3);font-size:.92rem}
/* ===== RUN HISTORY ===== */
.hist-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));
            gap:12px;margin-bottom:18px}
.hcard{background:var(--surface);border-radius:var(--r);box-shadow:var(--sh);
       padding:16px 20px;border-left:4px solid var(--border)}
.hcard.hc-total{border-left-color:#1677ff}.hcard.hc-best{border-left-color:#52c41a}
.hcard.hc-last{border-left-color:#722ed1}.hcard.hc-avg{border-left-color:#13c2c2}
.hcard .hnum{font-size:1.7rem;font-weight:800;line-height:1.1}
.hcard .hlbl{font-size:.68rem;text-transform:uppercase;letter-spacing:.07em;color:var(--text3)}
.hcard .hsub{font-size:.78rem;color:var(--text2);margin-top:2px}
.run-id-cell{font-family:'Consolas','Courier New',monospace;font-size:.8rem;color:#262626}
.open-btn{padding:4px 12px;background:var(--blue);color:#fff;border:none;
          border-radius:12px;cursor:pointer;font-size:.75rem;font-family:inherit;
          text-decoration:none;display:inline-block;transition:background .12s}
.open-btn:hover{background:#0958d9}
.run-detail-row{display:none;background:#f8faff}
.run-detail-row td{padding:0!important}
.run-detail-inner{padding:14px 20px;font-size:.82rem}
.run-detail-inner table{margin-top:8px;font-size:.8rem}
.run-detail-inner thead th{background:#1a3550;font-size:.68rem}
.run-detail-inner tbody td{padding:7px 12px}
.run-detail-row.open{display:table-row}
/* ===== FOOTER ===== */
.footer{margin-top:28px;text-align:center;font-size:.74rem;color:var(--text3)}
.footer a{color:var(--blue);text-decoration:none}
.footer a:hover{text-decoration:underline}
"""


# =============================================================================
# EMBEDDED JAVASCRIPT
# =============================================================================
_JS = """
/* ---- Main tab switching ---- */
function switchMainTab(id) {
  document.querySelectorAll('.main-tab').forEach(function(t) { t.classList.remove('active'); });
  document.querySelectorAll('.tab-panel').forEach(function(p) { p.classList.remove('active'); });
  document.getElementById('mtab-' + id).classList.add('active');
  document.getElementById('mpanel-' + id).classList.add('active');
}

/* ---- Current-run table filter ---- */
var _sf = 'ALL', _sq = '';
function applyFilters() {
  var rows = document.querySelectorAll('#rtbody tr');
  rows.forEach(function(r) {
    var b = r.querySelector('.badge');
    var sm = (_sf === 'ALL') || (b && b.getAttribute('data-status') === _sf);
    var qm = !_sq || r.textContent.toLowerCase().indexOf(_sq.toLowerCase()) >= 0;
    r.style.display = (sm && qm) ? '' : 'none';
  });
}
function filterStatus(s) {
  _sf = s;
  document.querySelectorAll('.fbtn').forEach(function(b) { b.classList.remove('active'); });
  var btn = document.getElementById('fb-' + s);
  if (btn) btn.classList.add('active');
  applyFilters();
}
function onSearch(q) { _sq = q; applyFilters(); }

/* ---- Sort current-run table ---- */
var _sc = -1, _sa = true;
function sortCol(c) {
  if (_sc === c) { _sa = !_sa; } else { _sc = c; _sa = true; }
  var tbody = document.getElementById('rtbody');
  var rows = Array.from(tbody.querySelectorAll('tr'));
  rows.sort(function(a, b) {
    var av = a.cells[c] ? a.cells[c].textContent.trim() : '';
    var bv = b.cells[c] ? b.cells[c].textContent.trim() : '';
    var an = parseFloat(av), bn = parseFloat(bv);
    if (!isNaN(an) && !isNaN(bn)) return _sa ? an - bn : bn - an;
    return _sa ? av.localeCompare(bv, undefined, {sensitivity:'base'})
               : bv.localeCompare(av, undefined, {sensitivity:'base'});
  });
  rows.forEach(function(r) { tbody.appendChild(r); });
  document.querySelectorAll('thead th .si').forEach(function(si, i) {
    si.innerHTML = i === c ? (_sa ? '&#9650;' : '&#9660;') : '&#8597;';
    si.parentElement.classList.toggle('sorted', i === c);
  });
  applyFilters();
}
function toggleErr(el) { el.closest('.err-cell').classList.toggle('err-expanded'); }

/* ---- History search & session filter ---- */
var _histSess = 0;
var _histQ    = '';
function filterHistSession(snum) {
  _histSess = snum;
  document.querySelectorAll('[id^="hsf-"]').forEach(function(b) { b.classList.remove('active'); });
  var btn = document.getElementById('hsf-' + snum);
  if (btn) btn.classList.add('active');
  _refreshHistTable();
}
function onHistSearch(q) {
  _histQ = q.toLowerCase();
  _refreshHistTable();
}
function _refreshHistTable() {
  document.querySelectorAll('#rhtbody > tr.run-row').forEach(function(r) {
    var matchSess = (_histSess === 0 || parseInt(r.dataset.session || 0) === _histSess);
    var matchQ    = (!_histQ || r.textContent.toLowerCase().indexOf(_histQ) >= 0);
    r.style.display = (matchSess && matchQ) ? '' : 'none';
    var next = r.nextElementSibling;
    if (next && next.classList.contains('run-detail-row')) next.style.display = 'none';
  });
}
/* ---- Run history row expand ---- */
function toggleRun(btn, runIdx) {
  var detailRow = document.getElementById('rdr-' + runIdx);
  if (!detailRow) return;
  var isOpen = detailRow.classList.contains('open');
  document.querySelectorAll('.run-detail-row.open').forEach(function(r) { r.classList.remove('open'); });
  if (!isOpen) {
    detailRow.classList.add('open');
    btn.textContent = 'Close';
  } else {
    btn.textContent = 'Open';
  }
  document.querySelectorAll('.run-row .open-btn').forEach(function(b) {
    if (b !== btn) b.textContent = 'Open';
  });
}

/* ---- Charts (Chart.js) ---- */
document.addEventListener('DOMContentLoaded', function() {
  var donutEl = document.getElementById('donutChart');
  if (donutEl && window.Chart) {
    new Chart(donutEl.getContext('2d'), {
      type: 'doughnut',
      data: {
        labels: ['Passed','Failed','Errors','Skipped'],
        datasets: [{
          data: [_DPASSED, _DFAILED, _DERRORS, _DSKIPPED],
          backgroundColor: ['#52c41a','#ff4d4f','#fa8c16','#d9d9d9'],
          borderWidth: 2, borderColor: '#fff'
        }]
      },
      options: {
        cutout: '68%',
        plugins: {
          legend: { position: 'bottom', labels: { padding: 10, font: { size: 11 } } }
        }
      }
    });
  }
  var trendEl = document.getElementById('trendChart');
  if (trendEl && window.Chart && _RUN_HISTORY.length > 0) {
    var labels = _RUN_HISTORY.map(function(r) {
      return r.session_num ? 'Session ' + r.session_num : (r.run_id || '').replace('run_','').replace(/_/g,' ');
    });
    var rates = _RUN_HISTORY.map(function(r) { return r.summary ? r.summary.pass_rate : 0; });
    var colors = rates.map(function(v) {
      return v >= 90 ? '#52c41a' : (v >= 70 ? '#fa8c16' : '#ff4d4f');
    });
    new Chart(trendEl.getContext('2d'), {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{ label: 'Pass Rate %', data: rates,
          backgroundColor: colors, borderRadius: 4, borderSkipped: false }]
      },
      options: {
        scales: {
          y: { min: 0, max: 100, ticks: { callback: function(v) { return v + '%'; } } },
          x: { ticks: { font: { size: 10 } } }
        },
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: {
            title: function(items) {
              var r = _RUN_HISTORY[items[0].dataIndex];
              var tests = (r.tests_executed || []).join(', ') || '(none)';
              return (r.session_num ? 'Session ' + r.session_num : items[0].label) + ' \u2014 ' + tests;
            },
            label: function(c) { return c.raw + '%'; }
          }}
        }
      }
    });
  }
});
"""


# =============================================================================
# GENERATOR
# =============================================================================
class HtmlReportGenerator:
    """Generates a self-contained HTML dashboard report (summary_report.html)."""

    def generate(
        self,
        results:     List[TestResult],
        summary:     dict,
        output_path: Path,
    ) -> None:
        """Write the HTML report to *output_path*."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self._build(results, summary), encoding="utf-8")

    def _build(self, results: List[TestResult], summary: dict) -> str:
        pr      = summary["pass_rate"]
        pr_cls  = "hp-green" if pr >= 90 else ("hp-yellow" if pr >= 70 else "hp-red")
        total   = summary["total"]
        passed  = summary["passed"]
        failed  = summary["failed"]
        errors  = summary["errors"]
        skipped = summary["skipped"]
        dur     = summary["duration_seconds"]
        gen_at  = summary["generated_at"]

        # Compute run_id from generated_at
        try:
            dt_obj = datetime.fromisoformat(gen_at)
            run_id = dt_obj.strftime("run_%Y%m%d_%H%M%S")
        except Exception:
            run_id = "run_unknown"

        unique_patients = len({r.patient_id for r in results if r.patient_id})
        unique_modules  = len({r.module for r in results if r.module})

        runs     = _load_run_history()
        num_runs = len(runs)

        rows_html = "\n".join(self._row(r) for r in results)
        empty_row = (
            '<tr><td colspan="7" class="no-data">No test results recorded.</td></tr>'
            if not results else ""
        )

        js_vars = (
            f"var _DPASSED = {passed};\n"
            f"var _DFAILED = {failed};\n"
            f"var _DERRORS = {errors};\n"
            f"var _DSKIPPED = {skipped};\n"
            f"var _RUN_HISTORY = {json.dumps(runs)};\n"
        )

        _session_nums = sorted({r.get("session_num", 0) for r in runs if r.get("session_num", 0)})
        if _session_nums:
            _sf_all  = '<button class="fbtn active" id="hsf-0" onclick="filterHistSession(0)">All Sessions</button>'
            _sf_btns = "".join(
                f'<button class="fbtn" id="hsf-{sn}" onclick="filterHistSession({sn})">Session {sn}</button>'
                for sn in _session_nums
            )
            sess_filter_html = _sf_all + _sf_btns
        else:
            sess_filter_html = ""

        hist_cards_html = self._run_hist_cards(runs)
        hist_table_html = self._run_hist_table(runs, run_id)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Summary Report &mdash; {escape(gen_at[:10])}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>{_CSS}</style>
</head>
<body>

<!-- ===== STICKY HEADER ===== -->
<header class="hdr">
  <div class="hdr-brand">
    <div class="logo">Summary <span>Report</span></div>
    <div class="sub">Test Run Summary &mdash; {escape(gen_at)}</div>
  </div>
  <div class="hdr-right">
    <div class="hdr-pill">
      <div>
        <div class="hp-num {pr_cls}">{pr}%</div>
        <div class="hp-lbl">Pass Rate</div>
      </div>
    </div>
    <nav class="hdr-nav">
      <button class="hnav-btn active" id="mtab-current"
              onclick="switchMainTab('current')">Current Run</button>
      <button class="hnav-btn" id="mtab-history"
              onclick="switchMainTab('history')">Run History ({num_runs})</button>
    </nav>
  </div>
</header>

<div class="wrap">

  <!-- ===== MAIN TABS ===== -->
  <div class="main-tabs">
    <button class="main-tab active" id="mtab-current"
            onclick="switchMainTab('current')">
      Current Run
      <span class="tc">{total}</span>
    </button>
    <button class="main-tab" id="mtab-history"
            onclick="switchMainTab('history')">
      Run History
      <span class="tc">{num_runs}</span>
    </button>
  </div>

  <!-- ===== CURRENT RUN PANEL ===== -->
  <div class="tab-panel active" id="mpanel-current">

    <!-- Run meta bar -->
    <div class="run-meta">
      <div class="rm-item">
        <div class="rm-lbl">Run ID</div>
        <div class="rm-val">{escape(run_id)}</div>
      </div>
      <div class="rm-item">
        <div class="rm-lbl">Date</div>
        <div class="rm-val">{escape(gen_at[:10])}</div>
      </div>
      <div class="rm-item">
        <div class="rm-lbl">Duration</div>
        <div class="rm-val">{dur}s</div>
      </div>
      <div class="rm-item">
        <div class="rm-lbl">Total Tests</div>
        <div class="rm-val">{total}</div>
      </div>
      <div class="rm-item">
        <div class="rm-lbl">Pass Rate</div>
        <div class="rm-val">{pr}%</div>
      </div>
    </div>

    <!-- Stat cards -->
    <div class="cards">
      <div class="card c-all">
        <div class="num n-blue">{total}</div>
        <div class="lbl">Total</div>
      </div>
      <div class="card c-pass">
        <div class="num n-green">{passed}</div>
        <div class="lbl">Passed</div>
      </div>
      <div class="card c-fail">
        <div class="num n-red">{failed}</div>
        <div class="lbl">Failed</div>
      </div>
      <div class="card c-err">
        <div class="num n-orange">{errors}</div>
        <div class="lbl">Errors</div>
      </div>
      <div class="card c-skip">
        <div class="num n-grey">{skipped}</div>
        <div class="lbl">Skipped</div>
      </div>
      <div class="card c-pat">
        <div class="num n-purple">{unique_patients}</div>
        <div class="lbl">Patients</div>
      </div>
      <div class="card c-flow">
        <div class="num n-teal">{unique_modules}</div>
        <div class="lbl">Flows</div>
      </div>
    </div>

    <!-- Charts row -->
    <div class="charts-row">
      <div class="chart-card">
        <div class="chart-title">Result Distribution</div>
        <div class="chart-wrap">
          <canvas id="donutChart" width="220" height="220"></canvas>
        </div>
      </div>
      <div class="chart-card">
        <div class="chart-title">Pass Rate Trend &mdash; By Session</div>
        <div class="chart-wrap">
          <canvas id="trendChart"></canvas>
        </div>
      </div>
    </div>

    <!-- Phase report link bar -->
    <div class="phase-link-bar">
      <span>E2E phase-level breakdown available in the Phase Report</span>
      <a href="patient_phase_report.html" target="_blank">
        Open Phase Breakdown Report &rarr;
      </a>
    </div>

    <!-- Toolbar -->
    <div class="toolbar">
      <button id="fb-ALL"   class="fbtn active"   onclick="filterStatus('ALL')">
        All ({total})
      </button>
      <button id="fb-PASS"  class="fbtn fa-pass"  onclick="filterStatus('PASS')">
        Pass ({passed})
      </button>
      <button id="fb-FAIL"  class="fbtn fa-fail"  onclick="filterStatus('FAIL')">
        Fail ({failed})
      </button>
      <button id="fb-ERROR" class="fbtn fa-error" onclick="filterStatus('ERROR')">
        Error ({errors})
      </button>
      <button id="fb-SKIP"  class="fbtn fa-skip"  onclick="filterStatus('SKIP')">
        Skip ({skipped})
      </button>
      <input class="search-box" type="text"
             placeholder="Search tests, modules, patients..."
             oninput="onSearch(this.value)">
    </div>

    <!-- Result table -->
    <div class="tbl-wrap">
      <table>
        <thead>
          <tr>
            <th onclick="sortCol(0)">Test<span class="si">&#8597;</span></th>
            <th onclick="sortCol(1)">Module<span class="si">&#8597;</span></th>
            <th onclick="sortCol(2)">Patient<span class="si">&#8597;</span></th>
            <th onclick="sortCol(3)">Status<span class="si">&#8597;</span></th>
            <th onclick="sortCol(4)">Error<span class="si">&#8597;</span></th>
            <th>Screenshot</th>
            <th onclick="sortCol(6)">Time<span class="si">&#8597;</span></th>
          </tr>
        </thead>
        <tbody id="rtbody">
          {rows_html or empty_row}
        </tbody>
      </table>
    </div>

  </div><!-- #mpanel-current -->

  <!-- ===== RUN HISTORY PANEL ===== -->
  <div class="tab-panel" id="mpanel-history">

    {hist_cards_html}

    <!-- Trend chart in history panel -->
    <div class="charts-row" style="grid-template-columns:1fr">
      <div class="chart-card">
        <div class="chart-title">Pass Rate Trend &mdash; All Sessions</div>
        <div class="chart-wrap" style="min-height:180px">
          <canvas id="trendChartHist"></canvas>
        </div>
      </div>
    </div>

    <!-- History toolbar -->
    <div class="toolbar" style="margin-bottom:14px">
      {sess_filter_html}
      <input class="search-box" type="text"
             placeholder="Search run ID, date..."
             oninput="onHistSearch(this.value)">
    </div>

    <!-- Run history table -->
    <div class="tbl-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Run ID</th>
            <th>Date</th>
            <th>Total</th>
            <th>Passed</th>
            <th>Failed</th>
            <th>Pass %</th>
            <th>Duration</th>
            <th>Open</th>
          </tr>
        </thead>
        <tbody id="rhtbody">
          {hist_table_html}
        </tbody>
      </table>
    </div>

  </div><!-- #mpanel-history -->

</div><!-- .wrap -->

<div class="footer">
  Summary Report &bull; {escape(gen_at)}
  &nbsp;&bull;&nbsp;
  <a href="patient_phase_report.html" target="_blank">Phase Breakdown Report</a>
</div>

<script>
{js_vars}
{_JS}
/* Second trend chart for history panel */
document.addEventListener('DOMContentLoaded', function() {{
  var el2 = document.getElementById('trendChartHist');
  if (el2 && window.Chart && _RUN_HISTORY.length > 0) {{
    var labels = _RUN_HISTORY.map(function(r) {{
      return r.session_num ? 'Session ' + r.session_num : (r.run_id || '').replace('run_','').replace(/_/g,' ');
    }});
    var rates = _RUN_HISTORY.map(function(r) {{ return r.summary ? r.summary.pass_rate : 0; }});
    var colors = rates.map(function(v) {{
      return v >= 90 ? '#52c41a' : (v >= 70 ? '#fa8c16' : '#ff4d4f');
    }});
    new Chart(el2.getContext('2d'), {{
      type: 'bar',
      data: {{
        labels: labels,
        datasets: [{{ label: 'Pass Rate %', data: rates,
          backgroundColor: colors, borderRadius: 4, borderSkipped: false }}]
      }},
      options: {{
        scales: {{
          y: {{ min: 0, max: 100, ticks: {{ callback: function(v) {{ return v + '%'; }} }} }},
          x: {{ ticks: {{ font: {{ size: 10 }} }} }}
        }},
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{ callbacks: {{
            title: function(items) {{
              var r = _RUN_HISTORY[items[0].dataIndex];
              var tests = (r.tests_executed || []).join(', ') || '(none)';
              return (r.session_num ? 'Session ' + r.session_num : items[0].label) + ' \u2014 ' + tests;
            }},
            label: function(c) {{ return c.raw + '%'; }}
          }} }}
        }}
      }}
    }});
  }}
}});
/* Fix duplicate tab IDs by wiring header nav buttons manually */
document.querySelectorAll('.hdr-nav .hnav-btn').forEach(function(btn) {{
  btn.addEventListener('click', function() {{
    document.querySelectorAll('.hdr-nav .hnav-btn').forEach(function(b) {{ b.classList.remove('active'); }});
    btn.classList.add('active');
  }});
}});
</script>
</body>
</html>"""

    @staticmethod
    def _row(r: TestResult) -> str:
        """Render one table row for a TestResult."""
        cls_map = {"PASS": "row-pass", "FAIL": "row-fail",
                   "ERROR": "row-error", "SKIP": "row-skip"}
        row_cls = cls_map.get(r.status, "")
        b_map   = {"PASS": "b-pass", "FAIL": "b-fail",
                   "ERROR": "b-error", "SKIP": "b-skip"}
        b_cls   = b_map.get(r.status, "b-skip")
        badge   = (
            f'<span class="badge {b_cls}" data-status="{escape(r.status)}">'
            f'{escape(r.status)}</span>'
        )
        if r.error:
            short  = escape(r.error[:90])
            suffix = "..." if len(r.error) > 90 else ""
            full   = escape(r.error)
            err_td = (
                f'<div class="err-cell">'
                f'<span class="err-short" onclick="toggleErr(this)"'
                f' title="Click to expand">{short}{suffix}</span>'
                f'<span class="err-full">{full}</span>'
                f'</div>'
            )
        else:
            err_td = "<span style=\"color:#8c8c8c\">&mdash;</span>"
        if r.screenshot_path:
            rel  = Path(r.screenshot_path).as_posix()
            shot = f'<a class="shot-link" href="../{rel}" target="_blank">View</a>'
        else:
            shot = "<span style=\"color:#8c8c8c\">&mdash;</span>"
        display_name = escape(patient_label(r.patient_id))
        pid_raw      = escape(str(r.patient_id))
        return (
            f'<tr class="{row_cls}">'
            f'<td class="test-cell">{escape(r.test_name)}</td>'
            f'<td class="mod-cell">{escape(r.module)}</td>'
            f'<td class="pid-cell" data-pid="{pid_raw}" title="{pid_raw}">{display_name}</td>'
            f'<td>{badge}</td>'
            f'<td>{err_td}</td>'
            f'<td>{shot}</td>'
            f'<td class="dur-cell">{r.duration}s</td>'
            f'</tr>'
        )

    def _run_hist_cards(self, runs: List[dict]) -> str:
        """Render 4 summary stat cards for the run history tab."""
        total_runs = len(runs)
        if total_runs == 0:
            return (
                '<div class="hist-cards">'
                '<div class="hcard hc-total">'
                '<div class="hnum">0</div>'
                '<div class="hlbl">Total Runs</div>'
                '<div class="hsub">No history yet</div>'
                '</div>'
                '</div>'
            )
        rates     = [r.get("summary", {}).get("pass_rate", 0) for r in runs]
        best      = max(rates)
        avg       = round(sum(rates) / len(rates), 1)
        last      = runs[-1]
        last_rate = last.get("summary", {}).get("pass_rate", 0)
        last_color = "#389e0d" if last_rate >= 90 else ("#d46b08" if last_rate >= 70 else "#cf1322")
        last_rid  = escape(last.get("run_id", ""))
        return f"""
<div class="hist-cards">
  <div class="hcard hc-total">
    <div class="hnum" style="color:#1677ff">{total_runs}</div>
    <div class="hlbl">Total Runs</div>
    <div class="hsub">All recorded runs</div>
  </div>
  <div class="hcard hc-best">
    <div class="hnum" style="color:#389e0d">{best}%</div>
    <div class="hlbl">Best Pass Rate</div>
    <div class="hsub">Peak performance</div>
  </div>
  <div class="hcard hc-last">
    <div class="hnum" style="color:{last_color}">{last_rate}%</div>
    <div class="hlbl">Last Run</div>
    <div class="hsub">{last_rid}</div>
  </div>
  <div class="hcard hc-avg">
    <div class="hnum" style="color:#08979c">{avg}%</div>
    <div class="hlbl">Avg Pass Rate</div>
    <div class="hsub">Across all runs</div>
  </div>
</div>"""

    def _run_hist_table(self, runs: List[dict], current_run_id: str) -> str:
        """Render run history table rows with expandable detail sub-rows."""
        if not runs:
            return (
                '<tr class="run-row">'
                '<td colspan="9" class="no-data">No run history found.</td>'
                '</tr>'
            )
        rows = []
        for idx, run in enumerate(runs):
            s      = run.get("summary", {})
            rid    = run.get("run_id", "")
            snum   = run.get("session_num", 0)
            date   = s.get("generated_at", "")[:10]
            ttl    = s.get("total", 0)
            psd    = s.get("passed", 0)
            fld    = s.get("failed", 0) + s.get("errors", 0)
            rate   = s.get("pass_rate", 0)
            dur    = s.get("duration_seconds", 0)
            is_cur = " (current)" if rid == current_run_id else ""
            sess_badge = (
                f'<span style="background:#e6f0ff;color:#1677ff;border-radius:8px;'
                f'padding:1px 8px;font-size:.72rem;font-weight:700;margin-left:6px">'
                f'Session {snum}</span>' if snum else ""
            )
            rate_color = "#389e0d" if rate >= 90 else ("#d46b08" if rate >= 70 else "#cf1322")
            rows.append(
                f'<tr class="run-row" data-session="{snum}">'
                f'<td>{idx + 1}</td>'
                f'<td class="run-id-cell">{escape(rid)}{escape(is_cur)}{sess_badge}</td>'
                f'<td>{escape(date)}</td>'
                f'<td>{ttl}</td>'
                f'<td style="color:#389e0d;font-weight:600">{psd}</td>'
                f'<td style="color:#cf1322;font-weight:600">{fld}</td>'
                f'<td style="color:{rate_color};font-weight:700">{rate}%</td>'
                f'<td>{dur}s</td>'
                f'<td><button class="open-btn" onclick="toggleRun(this, {idx})">Open</button></td>'
                f'</tr>'
                f'{self._run_detail_sub_table(run, idx)}'
            )
        return "\n".join(rows)

    def _run_detail_sub_table(self, run_data: dict, idx: int) -> str:
        """Render expandable detail sub-table for a historical run."""
        results = run_data.get("results", [])
        if not results:
            inner = '<p style="color:#8c8c8c;font-size:.82rem">No result details stored.</p>'
        else:
            trows = []
            for r in results:
                st    = r.get("status", "")
                b_map = {"PASS": "b-pass", "FAIL": "b-fail", "ERROR": "b-error", "SKIP": "b-skip"}
                b_cls = b_map.get(st, "b-skip")
                badge = f'<span class="badge {b_cls}">{escape(st)}</span>'
                pid   = str(r.get("patient_id", ""))
                disp  = escape(patient_label(pid))
                trows.append(
                    f'<tr>'
                    f'<td>{escape(r.get("test_name", ""))}</td>'
                    f'<td>{escape(r.get("module", ""))}</td>'
                    f'<td title="{escape(pid)}">{disp}</td>'
                    f'<td>{badge}</td>'
                    f'<td>{r.get("duration", 0)}s</td>'
                    f'</tr>'
                )
            inner = f"""
<table>
  <thead>
    <tr>
      <th>Test</th><th>Module</th><th>Patient</th><th>Status</th><th>Time</th>
    </tr>
  </thead>
  <tbody>{"".join(trows)}</tbody>
</table>"""
        return (
            f'<tr class="run-detail-row" id="rdr-{idx}">'
            f'<td colspan="9">'
            f'<div class="run-detail-inner">{inner}</div>'
            f'</td>'
            f'</tr>'
        )
