# -*- coding: utf-8 -*-
"""
PatientPhaseHtmlGenerator — produces patient_phase_report[N].html.

Layout
------
Header  : batch-wide phase stats (pass rate, counts)
Filter  : shared status filter + search (above tabs)
Tabs    : Session 1 | Session 2 | ...  (latest = default active)
Panel   : session meta bar + stat cards + flow bars + flow cards
          Each flow card → pipeline stepper + 4-column phase table
                           (Patient | Executed Flow | Section | Status)

Batch rotation: after SESSIONS_PER_BATCH sessions the caller writes to a
new file (patient_phase_report2.html, etc.) so each file stays ≤ 10 sessions.

MNC standard: type hints, docstrings, section comments.
"""
from __future__ import annotations

import math
import re
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Dict, List

from utils.reporting.constants import flow_label, flow_phase_order, patient_label
from utils.reporting.embed import embed_image, load_highlights
from utils.reporting.format import fmt_duration
from utils.reporting.session import load_batch_sessions


# =============================================================================
# EMBEDDED CSS
# =============================================================================
_PHASE_CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --navy:#0d2137;--blue:#1677ff;--green:#52c41a;--dkgreen:#389e0d;
  --red:#ff4d4f;--dkred:#cf1322;--orange:#fa8c16;--dkorange:#d46b08;
  --purple:#722ed1;--teal:#08979c;
  --grey:#8c8c8c;--ltgrey:#bfbfbf;--bg:#f0f2f5;--surface:#fff;
  --border:#e8e8e8;--text:#1a1a1a;--text2:#595959;--text3:#8c8c8c;
  --r:8px;--sh:0 1px 6px rgba(0,0,0,.09);--sh2:0 4px 16px rgba(0,0,0,.14);
}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,
     'Helvetica Neue',Arial,sans-serif;background:var(--bg);
     color:var(--text);font-size:14px;line-height:1.6;padding-bottom:56px}

/* ===== HEADER ===== */
.hdr{background:var(--navy);color:#fff;height:64px;padding:0 32px;
     display:flex;align-items:center;justify-content:space-between;
     position:sticky;top:0;z-index:500;box-shadow:0 2px 10px rgba(0,0,0,.4)}
.hdr-left h1{font-size:1.05rem;font-weight:700;letter-spacing:.02em}
.hdr-left .sub{font-size:.77rem;color:rgba(255,255,255,.52);margin-top:2px}

/* ===== WRAP ===== */
.wrap{max-width:1500px;margin:0 auto;padding:24px 32px}

/* ===== PATIENT TABS ===== */
.ptab-wrap{display:flex;gap:0;border-bottom:2px solid var(--border);
           margin-bottom:20px;overflow-x:auto;white-space:nowrap}
.ptab{display:inline-flex;align-items:center;gap:6px;
      padding:9px 20px;border:none;background:transparent;
      cursor:pointer;font-size:.83rem;color:var(--text2);
      border-bottom:3px solid transparent;margin-bottom:-2px;
      transition:all .15s;white-space:nowrap;font-family:inherit;font-weight:500}
.ptab:hover{color:var(--blue);background:#f0f5ff}
.ptab.active{color:var(--blue);border-bottom-color:var(--blue);font-weight:700}
.ptab-panel{display:none}
.ptab-panel.active{display:block}
.pat-info-card{background:var(--surface);border-radius:var(--r);box-shadow:var(--sh);
               padding:14px 20px;margin-bottom:16px;
               border-left:4px solid var(--purple);display:flex;flex-direction:column;gap:3px}
.pic-name{font-size:1rem;font-weight:700;color:var(--navy)}
.pic-id{font-size:.8rem;color:var(--text3);font-family:'Consolas','Courier New',monospace}

/* ===== OVERVIEW ROW ===== */
.overview{display:grid;grid-template-columns:1fr 260px;gap:20px;margin-bottom:24px}
@media(max-width:860px){.overview{grid-template-columns:1fr}}

/* Stat cards */
.stat-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));
            gap:12px;margin-bottom:16px}
.scard{background:var(--surface);border-radius:var(--r);box-shadow:var(--sh);
       padding:14px 16px;display:flex;flex-direction:column;align-items:center;
       gap:2px;border-top:3px solid var(--border);
       transition:transform .15s,box-shadow .15s}
.scard:hover{transform:translateY(-2px);box-shadow:var(--sh2)}
.scard.sc-total{border-color:#1677ff}.scard.sc-pass{border-color:var(--green)}
.scard.sc-fail{border-color:var(--red)}.scard.sc-notexec{border-color:#d9d9d9}
.scard.sc-flows{border-color:var(--purple)}.scard.sc-partial{border-color:var(--orange)}
.scard .sn{font-size:1.8rem;font-weight:700;line-height:1.1}
.scard .sl{font-size:.7rem;color:var(--text3);text-transform:uppercase;letter-spacing:.08em}
.sn-blue{color:#1677ff}.sn-green{color:var(--dkgreen)}.sn-red{color:var(--dkred)}
.sn-grey{color:var(--grey)}.sn-purple{color:var(--purple)}.sn-orange{color:var(--dkorange)}

/* Flow bars */
.bars-card{background:var(--surface);border-radius:var(--r);
           box-shadow:var(--sh);padding:16px 20px}
.bars-title{font-size:.75rem;font-weight:700;text-transform:uppercase;
            letter-spacing:.08em;color:var(--text2);margin-bottom:12px}
.fbar-row{display:flex;align-items:center;gap:10px;margin-bottom:9px}
.fbar-row:last-child{margin-bottom:0}
.fbar-label{font-size:.76rem;color:var(--text2);flex-shrink:0;
            width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.fbar-track{flex:1;height:8px;background:#f0f0f0;border-radius:4px;overflow:hidden}
.fbar-fill{height:100%;border-radius:4px;transition:width .6s ease}
.fb-green{background:linear-gradient(90deg,#52c41a,#95de64)}
.fb-orange{background:linear-gradient(90deg,#fa8c16,#ffd591)}
.fb-red{background:linear-gradient(90deg,#ff4d4f,#ff7875)}
.fbar-pct{font-size:.74rem;font-weight:700;color:var(--text2);
           white-space:nowrap;width:52px;text-align:right}

/* Donut chart (Chart.js canvas) */
.donut-card{background:var(--surface);border-radius:var(--r);
            box-shadow:var(--sh);padding:20px;
            display:flex;flex-direction:column;align-items:center;gap:14px}
.donut-title{font-size:.75rem;font-weight:700;text-transform:uppercase;
             letter-spacing:.08em;color:var(--text2);align-self:flex-start}
.donut-svg-wrap{position:relative;display:flex;align-items:center;
                justify-content:center}
.donut-legend{display:flex;flex-direction:column;gap:7px;width:100%}
.leg-row{display:flex;align-items:center;gap:8px;font-size:.78rem;color:var(--text2)}
.leg-dot{width:11px;height:11px;border-radius:50%;flex-shrink:0}
.ld-pass{background:var(--green)}.ld-fail{background:var(--red)}
.ld-notexec{background:#d9d9d9}
.leg-val{margin-left:auto;font-weight:600;color:var(--text)}

/* ===== FLOW TABS ===== */
.flow-tabs-wrap{margin-bottom:16px;border-bottom:2px solid #e4e4e4;
                overflow-x:auto;white-space:nowrap}
.flow-tabs{display:inline-flex;gap:0}
.ftab{display:inline-flex;align-items:center;gap:6px;
      padding:8px 18px;border:none;background:transparent;
      cursor:pointer;font-size:.82rem;color:var(--text2);
      border-bottom:3px solid transparent;margin-bottom:-2px;
      transition:all .15s;white-space:nowrap;font-family:inherit}
.ftab:hover{color:var(--blue);background:#f0f5ff}
.ftab.active{color:var(--blue);font-weight:600;border-bottom-color:var(--blue)}
.ftab .tc{display:inline-flex;align-items:center;justify-content:center;
           width:18px;height:18px;border-radius:9px;font-size:.65rem;
           font-weight:700;margin-left:4px}
.tc-pass{background:#f6ffed;color:var(--dkgreen)}
.tc-fail{background:#fff2f0;color:var(--dkred)}
.tc-partial{background:#fff7e6;color:var(--dkorange)}
.tc-all{background:#e6f0ff;color:var(--blue)}

/* ===== STATUS FILTER + SEARCH ===== */
.sfilter-bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;
             margin-bottom:14px}
.sfbtn{padding:3px 13px;border:1px solid #d9d9d9;border-radius:14px;
       background:var(--surface);cursor:pointer;font-size:.78rem;
       color:var(--text2);transition:all .12s;font-family:inherit}
.sfbtn:hover{border-color:var(--blue);color:var(--blue)}
.sfbtn.active{background:var(--blue);border-color:var(--blue);color:#fff;font-weight:600}
.sfbtn.sf-pass.active{background:var(--green);border-color:var(--green)}
.sfbtn.sf-fail.active{background:var(--red);border-color:var(--red)}
.sfbtn.sf-notexec.active{background:#8c8c8c;border-color:#8c8c8c}

/* ===== FLOW CARD ===== */
.flow-card{background:var(--surface);border-radius:var(--r);
           box-shadow:var(--sh);margin-bottom:24px;overflow:hidden;
           border:1px solid var(--border)}
.flow-header{display:flex;align-items:flex-start;justify-content:space-between;
             padding:14px 20px 12px;border-bottom:1px solid #f0f0f0;background:#fafafa}
.fh-left{display:flex;flex-direction:column;gap:3px}
.flow-title{font-size:.95rem;font-weight:700;color:var(--navy)}
.flow-meta{font-size:.74rem;color:var(--text3)}
.fh-right{display:flex;flex-direction:column;align-items:flex-end;gap:5px}
.flow-badge{padding:3px 12px;border-radius:12px;font-size:.76rem;
            font-weight:700;white-space:nowrap}
.fb-all-pass{background:#f6ffed;color:#237804;border:1px solid #b7eb8f}
.fb-partial{background:#fff7e6;color:#ad4e00;border:1px solid #ffd591}
.fb-all-fail{background:#fff2f0;color:#a8071a;border:1px solid #ffa39e}
.fb-notexec{background:#fafafa;color:var(--grey);border:1px solid #d9d9d9}
.flow-phase-stat{font-size:.74rem;color:var(--text3)}
.flow-phase-stat strong{color:var(--text2)}

/* ===== PIPELINE STEPPER ===== */
.pipeline-wrap{padding:16px 20px;border-bottom:1px solid #f5f5f5;
               overflow-x:auto;-webkit-overflow-scrolling:touch}
.pipeline-label{font-size:.7rem;font-weight:700;text-transform:uppercase;
                letter-spacing:.08em;color:var(--text3);margin-bottom:10px}
.pipeline{display:flex;align-items:stretch;gap:0;min-width:max-content}
.pnode{display:flex;flex-direction:column;align-items:center;justify-content:center;
       gap:5px;padding:10px 14px;border-radius:8px;min-width:88px;
       text-align:center;border:2px solid transparent;cursor:default;
       transition:transform .12s,box-shadow .12s}
.pnode:hover{transform:translateY(-2px);box-shadow:var(--sh2)}
.pn-pass{background:#f6ffed;border-color:#95de64}
.pn-fail{background:#fff2f0;border-color:#ffa39e}
.pn-notexec{background:#fafafa;border-color:#e8e8e8}
.pn-icon{font-size:1.2rem;line-height:1;font-weight:700}
.pn-pass .pn-icon{color:var(--green)}
.pn-fail .pn-icon{color:var(--red)}
.pn-notexec .pn-icon{color:#d9d9d9}
.pn-name{font-size:.65rem;color:var(--text2);line-height:1.3;
         max-width:82px;word-wrap:break-word}
.p-arrow{display:flex;align-items:center;padding:0 6px;
         color:var(--ltgrey);font-size:1.1rem;flex-shrink:0;align-self:center}

/* ===== 4-COLUMN PHASE TABLE ===== */
.tbl-outer{overflow-x:auto}
.phase-tbl{width:100%;border-collapse:collapse}
/* Table column header — non-sticky.
   Sticky thead was tried (top:64px to clear .hdr) but was unreliable:
   .flow-card{overflow:hidden} and .tbl-outer{overflow-x:auto} both create
   scroll/containing-block contexts, so sticky resolved against the wrong
   ancestor and the thead drifted below the first data row at certain
   scroll positions. Tables here are short (≤16 rows per flow), so the
   thead being in normal flow is fine and always reads correctly.
   Color: #1a3550 (lighter than var(--navy)=#0d2137 used by .hdr) keeps
   thead visually distinct from the page header even on first paint. */
.phase-tbl thead th{
  background:#1a3550;color:rgba(255,255,255,.92);
  padding:10px 16px;text-align:left;font-size:.7rem;
  text-transform:uppercase;letter-spacing:.07em;
  white-space:nowrap;cursor:pointer;user-select:none;
  border-top:1px solid rgba(255,255,255,.10)}
.phase-tbl thead th:hover{background:#244568}
.phase-tbl thead th .si{margin-left:4px;opacity:.4;font-size:.68rem}
.phase-tbl thead th.sorted .si{opacity:1}
.phase-tbl tbody td{
  padding:9px 16px;border-bottom:1px solid #f5f5f5;
  font-size:.84rem;vertical-align:middle}
.phase-tbl tbody tr:last-child td{border-bottom:none}
.tr-pass{background:#fff}
.tr-pass:hover{background:#f6ffed}
.tr-fail{background:#fffafa}
.tr-fail:hover{background:#fff2f0}
.tr-notexec{background:#fafafa}
.tr-notexec:hover{background:#f5f5f5}
.td-pid{font-weight:700;color:var(--blue);white-space:nowrap;min-width:60px}
.td-flow{color:var(--text2);font-size:.81rem;max-width:220px}
.td-phase{color:#262626;font-weight:500}
/* Status column intentionally narrow — only holds the badge + error text.
   The screenshot lives in .td-artifact, so we redirect width budget there. */
.td-status{white-space:nowrap;min-width:120px;max-width:240px}
.td-artifact{min-width:280px;max-width:520px;vertical-align:middle}
.td-artifact .td-empty{color:var(--text3)}
.th-artifact{cursor:default !important}
.th-artifact:hover{background:#1a3550 !important}  /* no sort hover */

/* Status badges in table */
.pbadge{display:inline-flex;align-items:center;gap:5px;
        padding:3px 10px;border-radius:10px;
        font-size:.76rem;font-weight:700;white-space:nowrap}
.pb-pass{background:#f6ffed;color:#237804;border:1px solid #b7eb8f}
.pb-fail{background:#fff2f0;color:#a8071a;border:1px solid #ffa39e}
.pb-notexec{background:#fafafa;color:var(--grey);border:1px solid #d9d9d9}

/* Error detail inside fail cell — width matches narrower .td-status (240px) */
.err-detail{margin-top:5px;font-size:.74rem;color:var(--dkred);
            line-height:1.4;max-width:220px;white-space:normal;
            word-break:break-word}
.err-toggle{font-size:.72rem;color:var(--blue);cursor:pointer;
            text-decoration:underline dotted;display:inline-block;margin-top:2px}
.err-full-text{display:none;font-size:.72rem;color:var(--dkred);
               margin-top:3px;white-space:pre-wrap;word-break:break-word}
.err-expanded .err-full-text{display:block}
.err-expanded .err-toggle{display:none}
a.pshot{font-size:.73rem;color:var(--blue);text-decoration:none;
        display:inline-flex;align-items:center;gap:3px;margin-top:3px}
a.pshot:hover{text-decoration:underline}

/* Inline failure screenshot + highlight overlay
   Visual language: matches existing .pshot / .pbadge tone — 1–2px borders,
   pastel surfaces, no motion. The red overlay alone stands out against
   the grayscale screenshot.
   Layout: lives inside .td-artifact (its own column, max-width:520px).
   shot-canvas is capped at 500px so it fills the artifact column without
   forcing it past the configured max. */
.shot-embed{margin-top:0;white-space:normal;max-width:500px}
.shot-details{display:block;max-width:100%}
.shot-details>summary{cursor:pointer;color:var(--blue);font-size:.73rem;
                      display:inline-flex;align-items:center;gap:4px;
                      list-style:none;user-select:none;margin-top:3px;
                      white-space:nowrap}
.shot-details>summary::-webkit-details-marker{display:none}
.shot-details>summary:hover{text-decoration:underline}
.shot-details>summary::before{content:"\\25B8";display:inline-block;
                              transition:transform .15s;font-size:.65rem;
                              color:var(--text3)}
.shot-details[open]>summary::before{transform:rotate(90deg)}
.shot-canvas{position:relative;display:block;max-width:500px;width:100%;
             margin-top:6px;border:1px solid var(--border);
             border-radius:var(--r);overflow:hidden;
             box-shadow:var(--sh);background:#fafafa}
.shot-canvas img{display:block;width:100%;height:auto}
.shot-canvas .hl-box{position:absolute;border:2px solid var(--red);
                     border-radius:2px;background:rgba(255,77,79,.06);
                     pointer-events:auto;cursor:help;
                     transition:background .15s,border-color .15s}
.shot-canvas .hl-box:hover{border-color:var(--dkred);
                           background:rgba(255,77,79,.12)}
.shot-nocap{font-size:.73rem;color:var(--text3);font-style:italic;
            margin-top:4px}

/* Cropped failure screenshot — used in the artifact column.
   The frame size is set inline (computed from the highlight + ~50px pad)
   and the image inside is sized + offset so the crop window fills the
   frame exactly. The .hl-box sits in the cropped frame's pixel space. */
.shot-crop{position:relative;display:block;margin-top:6px;
           border:1px solid var(--border);border-radius:var(--r);
           overflow:hidden;box-shadow:var(--sh);background:#fafafa}
.shot-crop img{position:absolute;display:block;max-width:none}
.shot-crop .hl-box{position:absolute;border:2px solid var(--red);
                   border-radius:2px;background:rgba(255,77,79,.06);
                   pointer-events:auto;cursor:help;
                   transition:background .15s,border-color .15s}
.shot-crop .hl-box:hover{border-color:var(--dkred);
                         background:rgba(255,77,79,.12)}

/* ===== SESSION SUB-TABS  (Phases | Errors) ===== */
.sub-tabs{display:flex;gap:0;border-bottom:1px solid var(--border);
          margin-bottom:16px}
.sub-tab{display:inline-flex;align-items:center;gap:6px;
         padding:7px 18px;border:none;background:transparent;cursor:pointer;
         font-size:.79rem;color:var(--text2);font-family:inherit;font-weight:500;
         border-bottom:2px solid transparent;margin-bottom:-1px;
         transition:color .15s,border-color .15s}
.sub-tab:hover{color:var(--blue)}
.sub-tab.active{color:var(--blue);border-bottom-color:var(--blue);font-weight:700}
.sub-tab-cnt{display:inline-flex;align-items:center;justify-content:center;
             min-width:18px;height:16px;padding:0 5px;border-radius:8px;
             background:#fff2f0;color:#a8071a;border:1px solid #ffa39e;
             font-size:.66rem;font-weight:700;line-height:1;margin-left:4px}
.sub-pane{display:none}
.sub-pane.active{display:block}

/* ===== ERRORS GALLERY ===== */
.err-list{display:flex;flex-direction:column;gap:18px}
.err-card{background:var(--surface);border-radius:var(--r);box-shadow:var(--sh);
          border:1px solid var(--border);padding:14px 18px;
          border-left:4px solid var(--red)}
.err-hdr{display:flex;flex-wrap:wrap;align-items:center;gap:8px;
         margin-bottom:8px;font-size:.78rem}
.err-pid{display:inline-flex;align-items:center;padding:2px 8px;border-radius:10px;
         background:#e6f4ff;color:#0958d9;border:1px solid #91caff;
         font-weight:700;font-size:.72rem;letter-spacing:.04em}
.err-pname{color:var(--text);font-weight:600}
.err-flow{color:var(--text2);font-size:.76rem}
.err-flow::before{content:"\\2022";margin-right:6px;color:var(--text3)}
.err-phase{color:var(--dkred);font-weight:700;font-size:.76rem}
.err-phase::before{content:"\\2022";margin-right:6px;color:var(--text3);font-weight:400}
.err-text{font-family:'Consolas','Courier New',monospace;font-size:.74rem;
          color:var(--dkred);background:#fffafa;border:1px solid #ffd6d6;
          border-radius:4px;padding:8px 10px;margin:6px 0 10px;
          white-space:pre-wrap;word-break:break-word;line-height:1.45;
          max-height:140px;overflow:auto}
.err-card .shot-canvas{max-width:880px}
.err-empty{text-align:center;padding:60px 24px;background:var(--surface);
           border-radius:var(--r);box-shadow:var(--sh);
           border:1px solid var(--border);color:var(--text2)}
.err-empty-icon{font-size:2.4rem;color:var(--green);margin-bottom:8px}
.err-empty-text{font-size:.88rem;color:var(--text2)}

/* No data */
.no-phase-data{text-align:center;padding:48px;color:var(--text3);font-size:.92rem}

/* Legend */
.legend-row{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:16px}
.leg-item{display:flex;align-items:center;gap:7px;font-size:.78rem;color:var(--text2)}
.leg-swatch{width:13px;height:13px;border-radius:3px;flex-shrink:0}
.ls-pass{background:#d9f7be;border:1px solid #95de64}
.ls-fail{background:#ffccc7;border:1px solid #ff7875}
.ls-notexec{background:#f0f0f0;border:1px solid #d9d9d9}

/* Footer */
.footer{margin-top:24px;text-align:center;font-size:.74rem;color:var(--text3)}
.footer a{color:var(--blue);text-decoration:none}
.footer a:hover{text-decoration:underline}

/* ===== SESSION META BAR ===== */
.session-meta-bar{
  background:var(--surface);border-radius:var(--r);box-shadow:var(--sh);
  padding:13px 20px;margin-bottom:16px;display:flex;align-items:flex-start;
  gap:28px;flex-wrap:wrap;border-left:4px solid var(--blue)
}
.sm-item{display:flex;flex-direction:column;gap:2px}
.sm-item.sm-wide{flex:1;min-width:220px}
.sm-lbl{font-size:.62rem;text-transform:uppercase;letter-spacing:.09em;color:var(--text3)}
.sm-val{font-size:.88rem;font-weight:600;color:var(--text)}
.sm-tests-val{font-size:.82rem;font-weight:400;color:var(--text2);line-height:1.5;white-space:normal}
/* Session tab count badge */
.stab-cnt{background:#e6f0ff;color:var(--blue);border-radius:10px;
          padding:1px 7px;font-size:.7rem;font-weight:700;margin-left:6px}
.ptab.active .stab-cnt{background:var(--blue);color:#fff}
/* global filter bar (above session tabs) */
.global-filter-bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px}
"""


# =============================================================================
# EMBEDDED JAVASCRIPT
# =============================================================================
_PHASE_JS = """
/* ---- Session tab switching ---- */
function showSessionTab(snum) {
  document.querySelectorAll('.ptab').forEach(function(t) { t.classList.remove('active'); });
  document.querySelectorAll('.ptab-panel').forEach(function(p) { p.classList.remove('active'); });
  var btn = document.getElementById('ptab-btn-s' + snum);
  var pnl = document.getElementById('ptab-panel-s' + snum);
  if (btn) btn.classList.add('active');
  if (pnl) pnl.classList.add('active');
  /* reset filters when switching sessions */
  _status = 'ALL';
  document.querySelectorAll('.sfbtn').forEach(function(b) { b.classList.remove('active'); });
  var allBtn = document.getElementById('psf-ALL');
  if (allBtn) allBtn.classList.add('active');
  applyPhaseFilters();
}

/* ---- Status filter (applies to active session panel only) ---- */
var _status = 'ALL';
function filterStatus(s) {
  _status = s;
  document.querySelectorAll('.sfbtn').forEach(function(b) { b.classList.remove('active'); });
  var btn = document.getElementById('psf-' + s);
  if (btn) btn.classList.add('active');
  applyPhaseFilters();
}

function applyPhaseFilters() {
  var activePanel = document.querySelector('.ptab-panel.active');
  var scope = activePanel ? activePanel : document;
  scope.querySelectorAll('.phase-tbl tbody tr').forEach(function(tr) {
    var ok = true;
    if (_status !== 'ALL') {
      var b = tr.querySelector('.pbadge');
      if (!b || b.getAttribute('data-ps') !== _status) ok = false;
    }
    tr.style.display = ok ? '' : 'none';
  });
}

/* ---- Session sub-tab switcher (Phases | Errors) ---- */
function showSessionSubTab(snum, sub) {
  var panel = document.getElementById('ptab-panel-s' + snum);
  if (!panel) return;
  panel.querySelectorAll('.sub-tab').forEach(function(b) {
    b.classList.toggle('active', b.getAttribute('data-sub') === sub);
  });
  panel.querySelectorAll('.sub-pane').forEach(function(p) {
    p.classList.toggle('active', p.id === 'sub-s' + snum + '-' + sub);
  });
}

/* ---- Sort phase table ---- */
function toggleErrFull(el) { el.closest('.td-status').classList.toggle('err-expanded'); }
var _sortIdx = {};
function sortPhaseCol(tblId, col) {
  var key = tblId + ':' + col;
  _sortIdx[key] = !_sortIdx[key];
  var asc = _sortIdx[key];
  var tbody = document.querySelector('#' + tblId + ' tbody');
  if (!tbody) return;
  var rows = Array.from(tbody.querySelectorAll('tr'));
  rows.sort(function(a, b) {
    var av = a.cells[col] ? a.cells[col].textContent.trim() : '';
    var bv = b.cells[col] ? b.cells[col].textContent.trim() : '';
    return asc ? av.localeCompare(bv) : bv.localeCompare(av);
  });
  rows.forEach(function(r) { tbody.appendChild(r); });
  var ths = document.querySelectorAll('#' + tblId + ' thead th');
  ths.forEach(function(th, i) {
    var si = th.querySelector('.si');
    if (si) si.innerHTML = i === col ? (asc ? '&#9650;' : '&#9660;') : '&#8597;';
    th.classList.toggle('sorted', i === col);
  });
  applyPhaseFilters();
}
"""


# =============================================================================
# DICT ENTRY WRAPPER
# =============================================================================
class _DictEntry:
    """
    Thin wrapper that lets plain dicts (from saved JSON snapshots) behave
    like PhaseEntry dataclass instances in renderer methods.
    """
    __slots__ = ("patient_id", "phase_name", "status", "error", "screenshot_path", "timestamp")

    def __init__(self, d: dict) -> None:
        self.patient_id      = d.get("patient_id",      "")
        self.phase_name      = d.get("phase_name",      "")
        self.status          = d.get("status",          "NOT EXECUTED")
        self.error           = d.get("error",           "")
        self.screenshot_path = d.get("screenshot_path", "")
        self.timestamp       = d.get("timestamp",       "")


# =============================================================================
# GENERATOR
# =============================================================================
class PatientPhaseHtmlGenerator:
    """
    Generates the patient-phase HTML report with session-based tabs.

    Reads batch session snapshots via load_batch_sessions(); falls back to the
    live phase_tracker when no persisted snapshots exist yet (first run edge case).
    """

    # ------------------------------------------------------------------ entry
    def generate(
        self,
        phase_tracker,
        output_path:         Path,
        current_session_num: int = 1,
        batch:               int = 1,
    ) -> None:
        """
        Write the phase breakdown HTML report to *output_path*.

        Parameters
        ----------
        phase_tracker        : live PhaseTracker (fallback source when no snapshots)
        output_path          : destination file path
        current_session_num  : session number just completed
        batch                : report-file batch number (1 → default file names)
        """
        batch_sessions = load_batch_sessions(batch)

        # Fallback: synthesise from live tracker on very first run
        if not batch_sessions and phase_tracker.has_data():
            from dataclasses import asdict as _asdict
            raw_data   = phase_tracker.get_report_data()
            phase_data = {
                tn: {
                    pid: [_asdict(e) for e in entries]
                    for pid, entries in patient_map.items()
                }
                for tn, patient_map in raw_data.items()
            }
            batch_sessions = [{
                "session_num":      current_session_num,
                "run_id":           "",
                "start_time":       "",
                "end_time":         datetime.now().isoformat(timespec="seconds"),
                "duration_seconds": 0,
                "tests_executed":   list(phase_data.keys()),
                "summary":          {},
                "phase_data":       phase_data,
            }]

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            self._build(batch_sessions, current_session_num),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------ build
    def _build(
        self,
        batch_sessions:      List[dict],
        current_session_num: int,
    ) -> str:
        now = datetime.now().isoformat(timespec="seconds")

        if not batch_sessions:
            return self._empty_html(now)

        # --- Active tab selection ---
        snums_present = {s.get("session_num", 0) for s in batch_sessions}
        default_active = (
            current_session_num if current_session_num in snums_present
            else batch_sessions[-1].get("session_num", 1)
        )

        # --- Build session tab strip + panels ---
        tabs_html   = ""
        panels_html = ""
        for sess in batch_sessions:
            snum      = sess.get("session_num", 1)
            is_active = (snum == default_active)
            n_flows   = len(sess.get("phase_data", {}))
            active_c  = "active" if is_active else ""
            tabs_html += (
                f'<button class="ptab {active_c}" id="ptab-btn-s{snum}"'
                f' onclick="showSessionTab({snum})">'
                f'Session {snum}'
                f'<span class="stab-cnt">{n_flows}</span>'
                f'</button>\n'
            )
            panels_html += self._session_panel(sess, snum, is_active)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Phase Breakdown Report &mdash; {escape(now[:10])}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>{_PHASE_CSS}</style>
</head>
<body>

<!-- ===== HEADER ===== -->
<header class="hdr">
  <div class="hdr-left">
    <h1>E2E Phase Breakdown Report</h1>
    <div class="sub">
      Session &bull; Flow &bull; Patient &bull; Phase &bull; Status
      &nbsp;&mdash;&nbsp; Generated: {escape(now)}
    </div>
  </div>
</header>

<!-- ===== CONTENT ===== -->
<div class="wrap">

  <!-- Global status filter (above tabs, filters active session) -->
  <div class="global-filter-bar">
    <button id="psf-ALL"          class="sfbtn active"     onclick="filterStatus('ALL')">All</button>
    <button id="psf-PASSED"       class="sfbtn sf-pass"    onclick="filterStatus('PASSED')">&#10003; Passed</button>
    <button id="psf-FAILED"       class="sfbtn sf-fail"    onclick="filterStatus('FAILED')">&#10007; Failed</button>
    <button id="psf-NOT EXECUTED" class="sfbtn sf-notexec" onclick="filterStatus('NOT EXECUTED')">&#9711; Not Executed</button>
  </div>

  <!-- Session tabs -->
  <div class="ptab-wrap">
    {tabs_html}
  </div>

  <!-- Session panels -->
  {panels_html}

</div><!-- .wrap -->

<div class="footer">
  Phase Breakdown Report &bull; {escape(now)}
</div>

<script>
{_PHASE_JS}
</script>
</body>
</html>"""

    # ---------------------------------------------------------------- session panel

    def _session_panel(self, sess: dict, snum: int, is_active: bool) -> str:
        """Render the full content panel for one session tab."""
        phase_data     = sess.get("phase_data", {})
        summary        = sess.get("summary", {})
        start_time     = sess.get("start_time", "")
        end_time       = sess.get("end_time", summary.get("generated_at", ""))
        duration       = sess.get("duration_seconds", summary.get("duration_seconds", 0))
        tests_executed = sess.get("tests_executed", list(phase_data.keys()))

        # --- Session-level phase stats ---
        # Same reconciliation as batch totals: pads NOT EXECUTED for phases
        # that flow_phase_order expected but the run never reached.
        s_total = s_pass = s_fail = s_notexec = 0
        flow_stats: List[dict] = []
        for tn, patient_map in phase_data.items():
            f_pass, f_fail, f_notexec, f_total = self._count_phases(tn, patient_map)
            s_pass    += f_pass
            s_fail    += f_fail
            s_notexec += f_notexec
            s_total   += f_total
            flow_stats.append({
                "test_name": tn,
                "label":     flow_label(tn),
                "total":     f_total,
                "passed":    f_pass,
                "failed":    f_fail,
            })

        # --- Meta bar values ---
        date_str  = (start_time or end_time)[:10]
        start_str = start_time[11:19] if len(start_time) > 10 else ""
        end_str   = end_time[11:19]   if len(end_time)   > 10 else ""
        tests_str = ", ".join(flow_label(t) for t in tests_executed) or "\u2014"

        start_item = (
            f'<div class="sm-item">'
            f'<div class="sm-lbl">Start</div>'
            f'<div class="sm-val">{escape(start_str)}</div>'
            f'</div>' if start_str else ""
        )
        end_item = (
            f'<div class="sm-item">'
            f'<div class="sm-lbl">End</div>'
            f'<div class="sm-val">{escape(end_str)}</div>'
            f'</div>' if end_str else ""
        )

        meta_bar = f"""
<div class="session-meta-bar">
  <div class="sm-item">
    <div class="sm-lbl">Session</div>
    <div class="sm-val">#{snum}</div>
  </div>
  <div class="sm-item">
    <div class="sm-lbl">Date</div>
    <div class="sm-val">{escape(date_str)}</div>
  </div>
  {start_item}
  {end_item}
  <div class="sm-item">
    <div class="sm-lbl">Duration</div>
    <div class="sm-val">{fmt_duration(duration)}</div>
  </div>
  <div class="sm-item sm-wide">
    <div class="sm-lbl">Tests Executed</div>
    <div class="sm-val sm-tests-val">{escape(tests_str)}</div>
  </div>
</div>"""

        stat_cards = f"""
<div class="stat-cards">
  <div class="scard sc-total">
    <div class="sn sn-blue">{s_total}</div>
    <div class="sl">Total Phases</div>
  </div>
  <div class="scard sc-pass">
    <div class="sn sn-green">{s_pass}</div>
    <div class="sl">Passed</div>
  </div>
  <div class="scard sc-fail">
    <div class="sn sn-red">{s_fail}</div>
    <div class="sl">Failed</div>
  </div>
  <div class="scard sc-notexec">
    <div class="sn sn-grey">{s_notexec}</div>
    <div class="sl">Not Executed</div>
  </div>
  <div class="scard sc-flows">
    <div class="sn sn-purple">{len(flow_stats)}</div>
    <div class="sl">Flows</div>
  </div>
</div>"""

        bars_html = self._flow_bars(flow_stats)

        legend = """
<div class="legend-row" style="margin-top:12px;margin-bottom:14px">
  <div class="leg-item"><div class="leg-swatch ls-pass"></div> <span>Phase Passed</span></div>
  <div class="leg-item"><div class="leg-swatch ls-fail"></div>
    <span>Phase Failed &mdash; subsequent sections not executed</span></div>
  <div class="leg-item"><div class="leg-swatch ls-notexec"></div>
    <span>Not Executed &mdash; skipped due to earlier failure</span></div>
</div>"""

        # --- Flow cards ---
        flow_cards_html = ""
        for tn, patient_map in phase_data.items():
            phases   = flow_phase_order(tn) or self._phases_from_data(patient_map)
            patients = list(patient_map.keys())
            wrapped: Dict[str, list] = {
                pid: [_DictEntry(e) if isinstance(e, dict) else e for e in entries]
                for pid, entries in patient_map.items()
            }
            flow_cards_html += self._flow_card(tn, phases, patients, wrapped)

        if not flow_cards_html:
            flow_cards_html = (
                '<div class="no-phase-data">No phase data recorded in this session.</div>'
            )

        # Errors-tab gallery — full-page screenshots of every FAILED phase
        # in this session, reconciled against flow_phase_order so we never
        # show stale entries (uses the same `phase_data` shape).
        errors_gallery_html = self._render_errors_gallery(phase_data)

        active_cls = "active" if is_active else ""
        # Sub-tab badge for the Errors tab — only shown when count > 0.
        err_badge = (
            f'<span class="sub-tab-cnt">{s_fail}</span>' if s_fail > 0 else ""
        )
        return f"""
<div id="ptab-panel-s{snum}" class="ptab-panel {active_cls}">
  <!-- Phases | Errors sub-tab strip -->
  <div class="sub-tabs" role="tablist">
    <button class="sub-tab active" data-sub="phases"
            onclick="showSessionSubTab({snum},'phases')">Phases</button>
    <button class="sub-tab" data-sub="errors"
            onclick="showSessionSubTab({snum},'errors')">Errors{err_badge}</button>
  </div>

  <!-- Phases pane (existing content) -->
  <div id="sub-s{snum}-phases" class="sub-pane active">
    {meta_bar}
    <div class="overview">
      <div>
        {stat_cards}
        <div class="bars-card">
          <div class="bars-title">Flow Completion Rate</div>
          {bars_html}
        </div>
      </div>
      <!-- Donut chart for this session -->
      <div class="donut-card">
        <div class="donut-title">Phase Distribution</div>
        <div class="donut-svg-wrap">
          {self._svg_donut(s_pass, s_fail, s_notexec, s_total)}
        </div>
        <div class="donut-legend">
          <div class="leg-row">
            <div class="leg-dot ld-pass"></div><span>Passed</span>
            <span class="leg-val">{s_pass}</span>
          </div>
          <div class="leg-row">
            <div class="leg-dot ld-fail"></div><span>Failed</span>
            <span class="leg-val">{s_fail}</span>
          </div>
          <div class="leg-row">
            <div class="leg-dot ld-notexec"></div><span>Not Executed</span>
            <span class="leg-val">{s_notexec}</span>
          </div>
        </div>
      </div>
    </div>
    {legend}
    {flow_cards_html}
  </div>

  <!-- Errors pane (full-page screenshots gallery) -->
  <div id="sub-s{snum}-errors" class="sub-pane">
    {errors_gallery_html}
  </div>
</div>"""

    @staticmethod
    def _phases_from_data(patient_map: dict) -> List[str]:
        """Derive phase order from data when FLOW_REGISTRY has no entry for this test."""
        seen: Dict[str, int] = {}
        for entries in patient_map.values():
            for i, e in enumerate(entries):
                ph = (e.get("phase_name") if isinstance(e, dict) else e.phase_name) or ""
                if ph and ph not in seen:
                    seen[ph] = i
        return sorted(seen, key=lambda p: seen[p])

    @staticmethod
    def _count_phases(test_name: str, patient_map: dict) -> tuple:
        """Return (passed, failed, notexec, total) for one test's phase data.

        Reconciles recorded entries against ``flow_phase_order(test_name)``
        (the canonical expected pipeline) so phases that never executed —
        because the test aborted early — are counted as NOT EXECUTED rather
        than silently absent. Falls back to phases derived from the data
        itself when the test has no FLOW_REGISTRY entry.
        """
        expected = flow_phase_order(test_name) or \
            PatientPhaseHtmlGenerator._phases_from_data(patient_map)
        n_pass = n_fail = n_notexec = 0
        for _pid, entries in patient_map.items():
            recorded: Dict[str, str] = {}
            for e in entries:
                if isinstance(e, dict):
                    name = e.get("phase_name") or ""
                    st   = e.get("status", "NOT EXECUTED")
                else:
                    name = e.phase_name
                    st   = e.status
                if name:
                    recorded[name] = st
            for phase in expected:
                st = recorded.get(phase, "NOT EXECUTED")
                if   st == "PASSED": n_pass    += 1
                elif st == "FAILED": n_fail    += 1
                else:                n_notexec += 1
        return n_pass, n_fail, n_notexec, (n_pass + n_fail + n_notexec)

    # ---------------------------------------------------- errors gallery

    @classmethod
    def _render_errors_gallery(cls, phase_data: dict) -> str:
        """Render the Errors-tab gallery for one session.

        Walks every test/patient/phase in *phase_data*, collects the FAILED
        entries (in the order they ran), and renders one ``<article>`` per
        failure with header (PID / patient name / flow / phase), error
        text, and the full-page screenshot via ``_render_failure_full``.

        Returns the empty-state markup when no failures are present, so
        the Errors pane never renders blank.
        """
        cards: List[str] = []
        for tn, patient_map in phase_data.items():
            flow_lbl = flow_label(tn)
            for pid, entries in patient_map.items():
                for e in entries:
                    if isinstance(e, dict):
                        status     = e.get("status", "")
                        phase_name = e.get("phase_name", "")
                        err_text   = e.get("error", "") or ""
                        shot_path  = e.get("screenshot_path", "") or ""
                    else:
                        status     = e.status
                        phase_name = e.phase_name
                        err_text   = e.error or ""
                        shot_path  = e.screenshot_path or ""
                    if status != "FAILED":
                        continue
                    cards.append(cls._render_error_card(
                        pid=str(pid),
                        flow_lbl=flow_lbl,
                        phase_name=phase_name,
                        err_text=err_text,
                        shot_path=shot_path,
                    ))

        if not cards:
            return (
                '<div class="err-empty">'
                '<div class="err-empty-icon">&#10003;</div>'
                '<div class="err-empty-text">No failures in this session.</div>'
                '</div>'
            )
        return f'<div class="err-list">{"".join(cards)}</div>'

    @staticmethod
    def _render_error_card(
        pid: str,
        flow_lbl: str,
        phase_name: str,
        err_text: str,
        shot_path: str,
    ) -> str:
        """One <article> in the errors gallery: header + error text + full screenshot."""
        display_pid = patient_label(pid)
        # Header chips show: <PID / Display Name> · Flow · Phase
        pid_chip = (
            f'<span class="err-pid">{escape(pid)}</span>'
            f'<span class="err-pname">{escape(display_pid)}</span>'
            if display_pid and display_pid != pid
            else f'<span class="err-pid">{escape(pid)}</span>'
        )
        flow_chip  = f'<span class="err-flow">{escape(flow_lbl)}</span>'
        phase_chip = f'<span class="err-phase">{escape(phase_name)}</span>'
        err_block  = (
            f'<pre class="err-text">{escape(err_text)}</pre>' if err_text else ""
        )
        shot_block = PatientPhaseHtmlGenerator._render_failure_full(shot_path)
        return (
            '<article class="err-card">'
            f'<header class="err-hdr">{pid_chip}{flow_chip}{phase_chip}</header>'
            f'{err_block}'
            f'{shot_block}'
            '</article>'
        )

    @staticmethod
    def _empty_html(now: str) -> str:
        return (
            f'<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">'
            f'<title>Phase Report</title></head><body>'
            f'<p style="padding:40px;font-family:sans-serif;color:#8c8c8c">'
            f'No phase data recorded yet. Generated: {escape(now)}</p>'
            f'</body></html>'
        )

    # ---------------------------------------------------------------- helpers

    def _flow_bars(self, flow_stats: List[dict]) -> str:
        if not flow_stats:
            return "<p style=\"color:#8c8c8c;font-size:.82rem\">No flow data.</p>"
        rows = []
        for fs in flow_stats:
            pct     = round(fs["passed"] / fs["total"] * 100, 1) if fs["total"] else 0.0
            bar_cls = "fb-green" if pct == 100 else ("fb-orange" if pct > 50 else "fb-red")
            rows.append(
                f'<div class="fbar-row">'
                f'<div class="fbar-label" title="{escape(fs["label"])}">'
                f'{escape(fs["label"])}</div>'
                f'<div class="fbar-track">'
                f'<div class="fbar-fill {bar_cls}" style="width:{pct}%"></div>'
                f'</div>'
                f'<div class="fbar-pct">{fs["passed"]}/{fs["total"]}</div>'
                f'</div>'
            )
        return "\n".join(rows)

    # ---------------------------------------------------------------- flow card

    def _flow_card(
        self,
        test_name:   str,
        phases:      List[str],
        patients:    List[str],
        patient_map: dict,
    ) -> str:
        """Render one flow card with pipeline stepper + 4-column phase table."""
        label = flow_label(test_name)

        # Convert wrapped/dataclass entries back to a uniform dict for
        # _count_phases, which is the single source of truth for the
        # passed/failed/not-executed reconciliation against flow_phase_order.
        plain_map = {
            pid: [
                e if isinstance(e, dict) else {
                    "phase_name": getattr(e, "phase_name", ""),
                    "status":     getattr(e, "status",     "NOT EXECUTED"),
                }
                for e in patient_map.get(pid, [])
            ]
            for pid in patients
        }
        f_pass, f_fail, f_notexec, f_total = self._count_phases(test_name, plain_map)

        if f_fail == 0 and f_pass > 0:
            badge_cls, badge_txt = "fb-all-pass", "&#10003; All Phases Passed"
        elif f_fail > 0 and f_pass > 0:
            badge_cls, badge_txt = "fb-partial", "&#9888; Partially Passed"
        elif f_fail > 0 and f_pass == 0:
            badge_cls, badge_txt = "fb-all-fail", "&#10007; Flow Failed"
        else:
            badge_cls, badge_txt = "fb-notexec", "&#9711; Not Executed"

        meta = f"{len(patients)} patient(s) &bull; {f_total} phase executions"
        stat = (
            f'<strong>{f_pass}</strong>/{f_total} phases passed'
            f'{f", &nbsp;<strong style=\"color:#cf1322\">" + str(f_fail) + "</strong> failed" if f_fail else ""}'
        )

        agg_statuses = self._aggregate_pipeline(phases, patients, patient_map)
        pipeline     = self._pipeline_html(phases, agg_statuses)

        tbl_id   = re.sub(r"[^\w]", "_", test_name)
        tbl_html = self._phase_table(tbl_id, label, phases, patients, patient_map)

        return f"""
<div class="flow-card" data-flow="{escape(test_name)}">
  <div class="flow-header">
    <div class="fh-left">
      <div class="flow-title">{escape(label)}</div>
      <div class="flow-meta">{meta}</div>
    </div>
    <div class="fh-right">
      <span class="flow-badge {badge_cls}">{badge_txt}</span>
      <div class="flow-phase-stat">{stat}</div>
    </div>
  </div>

  <!-- Pipeline -->
  <div class="pipeline-wrap">
    <div class="pipeline-label">Execution Pipeline</div>
    {pipeline}
  </div>

  <!-- 5-column table (Patient | Flow | Section | Status | Artifact) -->
  <div class="tbl-outer">
    <table class="phase-tbl" id="{tbl_id}">
      <thead>
        <tr>
          <th onclick="sortPhaseCol('{tbl_id}',0)">Patient<span class="si">&#8597;</span></th>
          <th onclick="sortPhaseCol('{tbl_id}',1)">Executed Flow<span class="si">&#8597;</span></th>
          <th onclick="sortPhaseCol('{tbl_id}',2)">Executed Section<span class="si">&#8597;</span></th>
          <th onclick="sortPhaseCol('{tbl_id}',3)">Status<span class="si">&#8597;</span></th>
          <th class="th-artifact">Artifact</th>
        </tr>
      </thead>
      <tbody>
        {tbl_html}
      </tbody>
    </table>
  </div>
</div>"""

    # ---------------------------------------------------------------- pipeline

    @staticmethod
    def _aggregate_pipeline(
        phases:      List[str],
        patients:    List[str],
        patient_map: dict,
    ) -> Dict[str, str]:
        """Return worst-case status per phase across all patients."""
        agg: Dict[str, str] = {}
        for phase in phases:
            statuses = []
            for pid in patients:
                for e in patient_map.get(pid, []):
                    if e.phase_name == phase:
                        statuses.append(e.status)
            if "FAILED" in statuses:
                agg[phase] = "FAILED"
            elif statuses and all(s == "PASSED" for s in statuses):
                agg[phase] = "PASSED"
            else:
                agg[phase] = "NOT EXECUTED"
        return agg

    @staticmethod
    def _pipeline_html(
        phases:   List[str],
        statuses: Dict[str, str],
    ) -> str:
        nodes = []
        for i, phase in enumerate(phases):
            s = statuses.get(phase, "NOT EXECUTED")
            if s == "PASSED":
                cls, icon = "pn-pass", "&#10003;"
            elif s == "FAILED":
                cls, icon = "pn-fail", "&#10007;"
            else:
                cls, icon = "pn-notexec", "&#9711;"
            nodes.append(
                f'<div class="pnode {cls}" title="{escape(phase)}: {escape(s)}">'
                f'<div class="pn-icon">{icon}</div>'
                f'<div class="pn-name">{escape(phase)}</div>'
                f'</div>'
            )
            if i < len(phases) - 1:
                nodes.append('<div class="p-arrow">&rarr;</div>')
        return f'<div class="pipeline">{"".join(nodes)}</div>'

    # -------------------------------------------------- failure-screenshot embed

    # Crop window — controls the in-cell view of the failure region.
    _CROP_PAD_PX     = 50    # padding (in source-image pixels) on each side of the highlight
    _CROP_FRAME_W_PX = 360   # rendered frame width inside the artifact column

    @staticmethod
    def _render_failure_shot(shot_path: str) -> str:
        """Render the **cropped** failure screenshot for one FAILED phase row.

        Used by ``_phase_table`` for the artifact column. Shows only the
        region around the highlighted error (highlight + ~50 px padding),
        scaled up to fit a 360-px frame so the actual failing UI is
        readable without expanding anything.

        Fallback chain:
        * No ``shot_path`` or unreadable PNG    → ``""`` (table cell shows
          its em-dash placeholder via the surrounding cell template).
        * No sidecar / no highlights            → full-image render so
          the cell isn't empty (we know there's a screenshot, just no
          known region to crop to).
        * Sidecar has a usable highlight        → cropped frame + scaled
          ``<img>`` + ``.hl-box`` overlay drawn in the cropped frame's
          pixel space.
        """
        if not shot_path:
            return ""

        data_url = embed_image(shot_path)
        if not data_url:
            return '<div class="shot-nocap">&#128247; Screenshot unavailable</div>'

        meta = load_highlights(shot_path)
        page_w = meta["page_size"]["width"]
        page_h = meta["page_size"]["height"]
        highlights = meta["highlights"]

        # Pick the first usable highlight; if none, fall back to the full image.
        h = next(
            (x for x in highlights if x["width"] > 0 and x["height"] > 0),
            None,
        )
        if h is None or page_w <= 0 or page_h <= 0:
            return PatientPhaseHtmlGenerator._wrap_details(
                PatientPhaseHtmlGenerator._render_full_canvas(data_url, meta),
                summary_label="&#128247; Screenshot",
            )

        # Crop window in source-image coordinates, padded and clamped.
        pad = PatientPhaseHtmlGenerator._CROP_PAD_PX
        cx = max(0.0, h["x"] - pad)
        cy = max(0.0, h["y"] - pad)
        cw = min(page_w - cx, h["width"]  + 2 * pad)
        ch = min(page_h - cy, h["height"] + 2 * pad)
        if cw <= 0 or ch <= 0:
            return PatientPhaseHtmlGenerator._wrap_details(
                PatientPhaseHtmlGenerator._render_full_canvas(data_url, meta),
                summary_label="&#128247; Screenshot",
            )

        # Frame: fixed width; height derived so the crop window's aspect
        # ratio is preserved. Image scaled so the crop region fills the frame.
        frame_w = PatientPhaseHtmlGenerator._CROP_FRAME_W_PX
        scale   = frame_w / cw
        frame_h = ch * scale
        img_w   = page_w * scale
        img_h   = page_h * scale
        img_x   = -cx * scale
        img_y   = -cy * scale

        # Highlight rectangle in cropped-frame pixel space.
        hl_left   = (h["x"] - cx) * scale
        hl_top    = (h["y"] - cy) * scale
        hl_width  = h["width"]  * scale
        hl_height = h["height"] * scale
        tip = escape(h["text"][:240]) if h["text"] else "Failure region"

        crop_html = (
            f'<div class="shot-crop" '
            f'style="width:{frame_w}px;height:{frame_h:.0f}px">'
            f'<img src="{data_url}" alt="Failure region (cropped)" loading="lazy" '
            f'style="width:{img_w:.0f}px;height:{img_h:.0f}px;'
            f'left:{img_x:.0f}px;top:{img_y:.0f}px">'
            f'<div class="hl-box" '
            f'style="left:{hl_left:.0f}px;top:{hl_top:.0f}px;'
            f'width:{hl_width:.0f}px;height:{hl_height:.0f}px" '
            f'title="{tip}"></div>'
            f'</div>'
        )

        return PatientPhaseHtmlGenerator._wrap_details(
            crop_html,
            summary_label="&#128247; Error region",
        )

    @staticmethod
    def _render_failure_full(shot_path: str) -> str:
        """Render the **full-page** failure screenshot for the errors gallery.

        Same image and overlay logic as the original mid-flow render, but
        WITHOUT the ``<details>`` wrapper — the gallery layout shows
        screenshots inline by default. Returns the bare ``.shot-canvas``
        block (or a "no screenshot" note when the file is missing).
        """
        if not shot_path:
            return '<div class="shot-nocap">&#128247; No screenshot captured.</div>'
        data_url = embed_image(shot_path)
        if not data_url:
            return '<div class="shot-nocap">&#128247; Screenshot unavailable</div>'
        return PatientPhaseHtmlGenerator._render_full_canvas(
            data_url, load_highlights(shot_path)
        )

    @staticmethod
    def _render_full_canvas(data_url: str, meta: dict) -> str:
        """Build the ``.shot-canvas`` block (full-page img + percent-positioned
        overlays) for either the cropped fallback or the errors gallery."""
        page_w = meta["page_size"]["width"]
        page_h = meta["page_size"]["height"]
        boxes: List[str] = []
        if page_w > 0 and page_h > 0:
            for h in meta["highlights"]:
                if h["width"] <= 0 or h["height"] <= 0:
                    continue
                left   = max(0.0, min(100.0, h["x"] / page_w * 100.0))
                top    = max(0.0, min(100.0, h["y"] / page_h * 100.0))
                width  = max(0.0, min(100.0 - left, h["width"]  / page_w * 100.0))
                height = max(0.0, min(100.0 - top,  h["height"] / page_h * 100.0))
                tip = escape(h["text"][:240]) if h["text"] else "Failure region"
                boxes.append(
                    f'<div class="hl-box" '
                    f'style="left:{left:.2f}%;top:{top:.2f}%;'
                    f'width:{width:.2f}%;height:{height:.2f}%" '
                    f'title="{tip}"></div>'
                )
        return (
            '<div class="shot-canvas">'
            f'<img src="{data_url}" alt="Failure screenshot" loading="lazy">'
            f'{"".join(boxes)}'
            '</div>'
        )

    @staticmethod
    def _wrap_details(inner_html: str, summary_label: str) -> str:
        """Wrap an inner block in the standard ``<details>`` toggle used in
        the artifact column."""
        return (
            '<div class="shot-embed">'
            '<details class="shot-details">'
            f'<summary>{summary_label}</summary>'
            f'{inner_html}'
            '</details>'
            '</div>'
        )

    # ---------------------------------------------------------------- table

    def _phase_table(
        self,
        tbl_id:      str,
        flow_lbl:    str,
        phases:      List[str],
        patients:    List[str],
        patient_map: dict,
    ) -> str:
        rows: List[str] = []
        for pid in patients:
            entry_map = {e.phase_name: e for e in patient_map.get(pid, [])}
            for phase in phases:
                entry     = entry_map.get(phase)
                status    = "NOT EXECUTED" if entry is None else entry.status
                error_str = "" if entry is None else (entry.error or "")
                shot_path = "" if entry is None else (entry.screenshot_path or "")

                # Status column: badge + (for FAILED) error text only.
                # Artifact column: the screenshot link / embed lives here in
                # its own column, separated from any error text.
                artifact_inner = '<span class="td-empty">&mdash;</span>'

                if status == "PASSED":
                    row_cls = "tr-pass"
                    status_inner = (
                        f'<span class="pbadge pb-pass" data-ps="{escape(status)}">'
                        f'&#10003; Passed</span>'
                    )
                    if shot_path:
                        rel = Path(shot_path).as_posix()
                        artifact_inner = (
                            f'<a class="pshot" href="../{rel}" target="_blank"'
                            f' title="View success screenshot">'
                            f'&#128247; <span class="pshot-lbl">View</span></a>'
                        )

                elif status == "FAILED":
                    row_cls   = "tr-fail"
                    err_short = escape(error_str[:110]) + ("..." if len(error_str) > 110 else "")
                    err_full  = escape(error_str)
                    err_html  = (
                        f'<div class="err-detail">{err_short}'
                        f'{"<span class=\"err-toggle\" onclick=\"toggleErrFull(this)\"> show more</span>" if len(error_str) > 110 else ""}'
                        f'<div class="err-full-text">{err_full}</div>'
                        f'</div>'
                    ) if error_str else ""
                    status_inner = (
                        f'<span class="pbadge pb-fail" data-ps="{escape(status)}">&#10007; Failed</span>'
                        f'{err_html}'
                    )
                    shot_html = self._render_failure_shot(shot_path)
                    if shot_html:
                        artifact_inner = shot_html

                else:  # NOT EXECUTED
                    row_cls      = "tr-notexec"
                    status_inner = (
                        f'<span class="pbadge pb-notexec" data-ps="{escape(status)}">'
                        f'&#9711; Not Executed</span>'
                    )

                display_pid = escape(patient_label(str(pid)))
                pid_raw     = escape(str(pid))
                rows.append(
                    f'<tr class="{row_cls}">'
                    f'<td class="td-pid" title="{pid_raw}">{display_pid}</td>'
                    f'<td class="td-flow">{escape(flow_lbl)}</td>'
                    f'<td class="td-phase">{escape(phase)}</td>'
                    f'<td class="td-status">{status_inner}</td>'
                    f'<td class="td-artifact">{artifact_inner}</td>'
                    f'</tr>'
                )

        if not rows:
            return f'<tr><td colspan="5" class="no-phase-data">No phase data for this flow.</td></tr>'
        return "\n".join(rows)

    # ---------------------------------------------------------------- svg donut

    def _svg_donut(
        self,
        passed:   int,
        failed:   int,
        not_exec: int,
        total:    int,
    ) -> str:
        if total == 0:
            return (
                '<svg viewBox="0 0 200 200" width="180" height="180">'
                '<circle cx="100" cy="100" r="70" fill="none" stroke="#f0f0f0" stroke-width="28"/>'
                '<text x="100" y="100" text-anchor="middle" dominant-baseline="middle" '
                'font-size="13" fill="#8c8c8c">No data</text>'
                '</svg>'
            )

        C = 2 * math.pi * 70  # circumference using midpoint radius

        def seg(color: str, length: float, offset: float) -> str:
            if length <= 0:
                return ""
            return (
                f'<circle cx="100" cy="100" r="70" fill="none" '
                f'stroke="{color}" stroke-width="28" '
                f'stroke-linecap="butt" '
                f'stroke-dasharray="{length:.3f} {C:.3f}" '
                f'stroke-dashoffset="{-offset:.3f}" '
                f'transform="rotate(-90 100 100)"/>'
            )

        p_len = (passed   / total) * C
        f_len = (failed   / total) * C
        n_len = (not_exec / total) * C

        pct       = round(passed / total * 100, 1)
        pct_color = "#52c41a" if pct >= 90 else ("#fa8c16" if pct >= 60 else "#ff4d4f")

        segments = ""
        acc = 0.0
        if p_len > 0:
            segments += seg("#52c41a", p_len, acc); acc += p_len
        if f_len > 0:
            segments += seg("#ff4d4f", f_len, acc); acc += f_len
        if n_len > 0:
            segments += seg("#d9d9d9", n_len, acc)

        return (
            f'<svg viewBox="0 0 200 200" width="180" height="180">'
            f'<circle cx="100" cy="100" r="70" fill="none" stroke="#f5f5f5" stroke-width="28"/>'
            f'{segments}'
            f'<text x="100" y="92" text-anchor="middle" font-size="24" '
            f'font-weight="800" fill="{pct_color}">{pct}%</text>'
            f'<text x="100" y="114" text-anchor="middle" font-size="10" fill="#8c8c8c">Phase Pass Rate</text>'
            f'</svg>'
        )
