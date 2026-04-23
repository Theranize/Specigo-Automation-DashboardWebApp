# -*- coding: utf-8 -*-
"""
Module-level singleton instances shared across the reporting package.

Imported by conftest.py and by any code that needs to interact with the
live report registry or generators without constructing new instances.
"""
from __future__ import annotations

from utils.reporting.registry import ArtifactManager, ReportRegistry
from utils.reporting.generators.summary_html     import HtmlReportGenerator
from utils.reporting.generators.summary_json     import JsonReportGenerator
from utils.reporting.generators.summary_csv      import CsvReportGenerator
from utils.reporting.generators.phase_html       import PatientPhaseHtmlGenerator
from utils.reporting.generators.phase_json       import PatientPhaseJsonGenerator
from utils.reporting.generators.stakeholder_html import StakeholderHtmlGenerator
from utils.reporting.generators.stakeholder_pdf  import StakeholderPdfGenerator

artifact_manager           = ArtifactManager()
report_registry            = ReportRegistry()
html_generator             = HtmlReportGenerator()
json_generator             = JsonReportGenerator()
csv_generator              = CsvReportGenerator()
phase_html_generator       = PatientPhaseHtmlGenerator()
phase_json_generator       = PatientPhaseJsonGenerator()
stakeholder_html_generator = StakeholderHtmlGenerator()
stakeholder_pdf_generator  = StakeholderPdfGenerator()
