# -*- coding: utf-8 -*-
"""
StakeholderPdfGenerator — renders the stakeholder HTML to PDF via Playwright.

Uses the Chromium browser that already ships with Playwright (no new deps).
A fresh sync_playwright() context is spawned because the test-scoped browser
fixture is already torn down by the time reports are generated. Failures are
swallowed and reported via the return value so the test session never fails.
"""
from __future__ import annotations

from pathlib import Path


class StakeholderPdfGenerator:
    """Renders a local HTML file to PDF using headless Chromium."""

    def generate(self, html_path: Path, pdf_path: Path) -> bool:
        """Render *html_path* to *pdf_path*. Returns True on success, False on any failure."""
        html_path = Path(html_path)
        pdf_path  = Path(pdf_path)

        if not html_path.is_file():
            print(f"  [STAKEHOLDER] PDF skipped: HTML source not found -> {html_path}")
            return False

        pdf_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            print(f"  [STAKEHOLDER] PDF skipped: Playwright unavailable ({exc})")
            return False

        url = html_path.resolve().as_uri()

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    context = browser.new_context()
                    page    = context.new_page()
                    page.goto(url, wait_until="load")
                    page.emulate_media(media="print")
                    page.pdf(
                        path=str(pdf_path),
                        format="A4",
                        print_background=True,
                        margin={"top": "14mm", "bottom": "14mm", "left": "12mm", "right": "12mm"},
                    )
                finally:
                    browser.close()
        except Exception as exc:
            print(f"  [STAKEHOLDER] PDF skipped: {exc}")
            return False

        return True
