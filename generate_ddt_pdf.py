"""Generate DDT_Reference_Guide.pdf from DDT_Reference_Guide.md using Playwright."""

from pathlib import Path
from playwright.sync_api import sync_playwright

_ROOT = Path(__file__).resolve().parent
_MD   = _ROOT / "DDT_Reference_Guide.md"
_PDF  = _ROOT / "DDT_Reference_Guide.pdf"

CSS = """
  @page { margin: 16mm 18mm; size: A4; }
  * { box-sizing: border-box; }
  body {
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 10.5px;
    color: #1a1a1a;
    line-height: 1.55;
    max-width: 960px;
    margin: 0 auto;
  }

  /* ── Headings ── */
  h1 {
    font-size: 20px;
    color: #0d2d52;
    border-bottom: 3px solid #0d2d52;
    padding-bottom: 8px;
    margin-top: 0;
    margin-bottom: 6px;
  }
  h2 {
    font-size: 13.5px;
    color: #ffffff;
    background: #0d2d52;
    padding: 5px 12px;
    border-radius: 4px;
    margin-top: 26px;
    margin-bottom: 8px;
    page-break-after: avoid;
  }
  h3 {
    font-size: 10.5px;
    color: #0d2d52;
    font-weight: 700;
    margin-top: 16px;
    margin-bottom: 4px;
    border-left: 3px solid #4a90c4;
    padding-left: 8px;
    page-break-after: avoid;
  }

  /* ── Tables ── */
  table {
    border-collapse: collapse;
    width: 100%;
    margin: 6px 0 14px 0;
    font-size: 10px;
    page-break-inside: avoid;
  }
  thead tr {
    background: #1a5276;
    color: #ffffff;
  }
  th {
    padding: 6px 12px;
    text-align: left;
    font-weight: 600;
    letter-spacing: 0.3px;
  }
  td {
    padding: 5px 12px;
    border-bottom: 1px solid #d5e2f0;
    vertical-align: top;
    line-height: 1.6;
  }
  tr:nth-child(even) td { background: #f0f6fc; }
  tr:last-child td { border-bottom: 2px solid #1a5276; }

  /* ── Inline code (values) ── */
  code {
    background: #e8f4fd;
    border: 1px solid #b0d0ea;
    border-radius: 3px;
    padding: 1px 5px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 9.5px;
    color: #1a5276;
    white-space: nowrap;
  }

  /* ── Blockquote (notes) ── */
  blockquote {
    background: #fff8e1;
    border-left: 4px solid #f39c12;
    margin: 8px 0 14px 0;
    padding: 7px 14px;
    border-radius: 0 4px 4px 0;
    font-size: 10px;
    color: #5d4037;
  }
  blockquote p { margin: 0; }
  blockquote strong { color: #e65100; }

  /* ── HR ── */
  hr {
    border: none;
    border-top: 1px solid #ccd9e8;
    margin: 18px 0 10px 0;
  }

  /* ── Paragraph ── */
  p { margin: 4px 0 8px 0; }

  /* ── Footer ── */
  .footer {
    margin-top: 28px;
    padding-top: 8px;
    border-top: 1px solid #ccd9e8;
    font-size: 8.5px;
    color: #999;
    text-align: center;
  }
"""


def escape(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(t: str) -> str:
    import re
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"`([^`]+)`", lambda m: f"<code>{escape(m.group(1))}</code>", t)
    t = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", t)
    # non-breaking spaces
    t = t.replace("&nbsp;", "&nbsp;")
    return t


def md_to_html(md_text: str) -> str:
    import re
    lines = md_text.split("\n")
    out = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Heading
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            lvl = len(m.group(1))
            txt = inline(escape(m.group(2)))
            out.append(f"<h{lvl}>{txt}</h{lvl}>")
            i += 1
            continue

        # Table
        if "|" in line and i + 1 < len(lines) and re.match(r"^\|[-| :]+\|", lines[i + 1]):
            raw_headers = [c.strip() for c in line.strip().strip("|").split("|")]
            headers = [inline(escape(h)) for h in raw_headers]
            i += 2  # skip separator row
            rows = []
            while i < len(lines) and "|" in lines[i] and not re.match(r"^\|[-| :]+\|", lines[i]):
                cells = [inline(escape(c.strip())) for c in lines[i].strip().strip("|").split("|")]
                while len(cells) < len(headers):
                    cells.append("")
                rows.append(cells)
                i += 1
            th = "".join(f"<th>{h}</th>" for h in headers)
            tbody = ""
            for row in rows:
                tbody += "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"
            out.append(f'<table><thead><tr>{th}</tr></thead><tbody>{tbody}</tbody></table>')
            continue

        # HR
        if re.match(r"^---+$", line.strip()):
            out.append("<hr>")
            i += 1
            continue

        # Blockquote
        if line.startswith(">"):
            bq = []
            while i < len(lines) and lines[i].startswith(">"):
                bq.append(inline(escape(lines[i][1:].strip())))
                i += 1
            out.append(f'<blockquote><p>{"<br>".join(bq)}</p></blockquote>')
            continue

        # Blank
        if not line.strip():
            i += 1
            continue

        # Paragraph
        out.append(f"<p>{inline(escape(line))}</p>")
        i += 1

    return "\n".join(out)


def build_html(md_text: str) -> str:
    body = md_to_html(md_text)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>{CSS}</style>
</head>
<body>
{body}
<div class="footer">DDT Keys &amp; Allowable Values Reference &mdash; Specigo Lab Automation &mdash; 2026-03-25</div>
</body>
</html>"""


def generate_pdf() -> None:
    md_text  = _MD.read_text(encoding="utf-8")
    html     = build_html(md_text)
    tmp_html = _ROOT / "_ddt_tmp.html"
    tmp_html.write_text(html, encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page    = browser.new_page()
        page.goto(tmp_html.as_uri())
        page.wait_for_load_state("networkidle")
        page.pdf(
            path=str(_PDF),
            format="A4",
            margin={"top": "16mm", "bottom": "16mm", "left": "18mm", "right": "18mm"},
            print_background=True,
        )
        browser.close()

    tmp_html.unlink(missing_ok=True)
    print(f"PDF saved: {_PDF}")


if __name__ == "__main__":
    generate_pdf()
