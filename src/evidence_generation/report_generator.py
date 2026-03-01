"""
GeoMRV PDF Report Generator
==============================
Generate audit-ready PDF evidence reports using ReportLab.

Each report contains:
- Title page with project metadata
- Executive summary with key findings
- Data sources table
- Analysis results with embedded charts
- Verification outcomes table
- Processing lineage (audit trail)
- Appendix with full package metadata

Usage
-----
    from src.evidence_generation.report_generator import PDFReportGenerator
    from src.evidence_generation.visualizations import ReportVisualizations

    gen = PDFReportGenerator()
    gen.generate_report(evidence_package, "output/report.pdf")

    # Or with observation data for charts:
    gen.generate_report(
        evidence_package,
        "output/report.pdf",
        observations_df=obs_df,  # pandas DataFrame with date/ndvi columns
    )
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.evidence_generation.package_schema import EvidencePackage
from src.evidence_generation.visualizations import ReportVisualizations

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Brand colours
# ──────────────────────────────────────────────────────────────

_BRAND_BLUE = colors.HexColor("#1f4e78")
_BRAND_LIGHT_BLUE = colors.HexColor("#2e75b6")
_HEADER_BG = colors.HexColor("#1f4e78")
_HEADER_FG = colors.whitesmoke
_ROW_ALT = colors.HexColor("#f2f7fb")
_STATUS_COLORS = {
    "PASS": colors.HexColor("#2ca02c"),
    "REVIEW_REQUIRED": colors.HexColor("#ff7f0e"),
    "FAIL": colors.HexColor("#d62728"),
}
_RISK_COLORS = {
    "critical": colors.HexColor("#d62728"),
    "high": colors.HexColor("#ff7f0e"),
    "medium": colors.HexColor("#ffbb78"),
    "low": colors.HexColor("#2ca02c"),
}


# ──────────────────────────────────────────────────────────────
# PDF Report Generator
# ──────────────────────────────────────────────────────────────


class PDFReportGenerator:
    """Generate professional, audit-ready PDF reports from evidence packages.

    The generator produces multi-page PDF documents containing:

    - Branded title page
    - Executive summary
    - Data sources documentation
    - Analysis results (with optional embedded charts)
    - Verification rule outcomes
    - Processing lineage (complete audit trail)
    - Package metadata appendix

    Parameters
    ----------
    page_size : tuple
        ReportLab page size (default: US Letter).
    """

    def __init__(self, page_size: tuple = letter) -> None:
        self.page_size = page_size
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        self._viz = ReportVisualizations()

    # ── custom styles ─────────────────────────────────────────

    def _setup_custom_styles(self) -> None:
        """Register custom paragraph styles for the GeoMRV brand."""
        self.styles.add(
            ParagraphStyle(
                name="GeoTitle",
                parent=self.styles["Heading1"],
                fontSize=26,
                textColor=_BRAND_BLUE,
                spaceAfter=30,
                alignment=TA_CENTER,
                fontName="Helvetica-Bold",
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="GeoSubtitle",
                parent=self.styles["Heading2"],
                fontSize=16,
                textColor=_BRAND_LIGHT_BLUE,
                spaceAfter=20,
                alignment=TA_CENTER,
                fontName="Helvetica",
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="GeoHeading",
                parent=self.styles["Heading2"],
                fontSize=14,
                textColor=_BRAND_BLUE,
                spaceAfter=10,
                spaceBefore=16,
                fontName="Helvetica-Bold",
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="GeoBody",
                parent=self.styles["BodyText"],
                fontSize=10,
                leading=14,
                alignment=TA_JUSTIFY,
                spaceAfter=8,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="GeoCaption",
                parent=self.styles["Normal"],
                fontSize=8,
                textColor=colors.grey,
                alignment=TA_CENTER,
                spaceAfter=12,
                spaceBefore=4,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="GeoFooter",
                parent=self.styles["Normal"],
                fontSize=8,
                textColor=colors.grey,
                alignment=TA_CENTER,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="GeoTableHeader",
                parent=self.styles["Normal"],
                fontSize=9,
                leading=11,
                fontName="Helvetica-Bold",
                textColor=_HEADER_FG,
                alignment=TA_LEFT,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="GeoTableCell",
                parent=self.styles["Normal"],
                fontSize=9,
                leading=11,
                alignment=TA_LEFT,
                wordWrap="CJK",
            )
        )

    # ── public API ────────────────────────────────────────────

    def generate_report(
        self,
        package: EvidencePackage,
        output_path: str,
        *,
        observations_df: Optional[pd.DataFrame] = None,
    ) -> str:
        """Generate a complete PDF report from an evidence package.

        Parameters
        ----------
        package : EvidencePackage
            The evidence package to render.
        output_path : str
            File path for the output PDF.
        observations_df : pd.DataFrame, optional
            Raw observations with ``date`` and ``ndvi`` columns.
            If provided, NDVI time-series and seasonal charts are
            embedded.

        Returns
        -------
        str
            Absolute path to the generated PDF.
        """
        # Ensure output directory exists
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=self.page_size,
            rightMargin=0.6 * inch,
            leftMargin=0.6 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        story: list = []

        # ── Sections ──
        story.extend(self._build_title_page(package))
        story.append(PageBreak())

        story.extend(self._build_executive_summary(package))
        story.append(PageBreak())

        story.extend(self._build_data_sources(package))
        story.append(Spacer(1, 0.3 * inch))

        story.extend(self._build_analysis_results(package, observations_df))
        story.append(PageBreak())

        story.extend(self._build_verification_section(package))
        story.append(PageBreak())

        story.extend(self._build_lineage_section(package))
        story.append(PageBreak())

        story.extend(self._build_appendix(package))

        # Build
        doc.build(story, onFirstPage=self._add_footer, onLaterPages=self._add_footer)

        abs_path = os.path.abspath(output_path)
        logger.info("PDF report generated: %s", abs_path)
        return abs_path

    # ── footer ────────────────────────────────────────────────

    @staticmethod
    def _add_footer(canvas, doc) -> None:
        """Add page number and branding to every page."""
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        page_num = f"Page {canvas.getPageNumber()}"
        canvas.drawCentredString(doc.pagesize[0] / 2, 0.4 * inch, page_num)
        canvas.drawString(
            0.6 * inch,
            0.4 * inch,
            "GeoMRV Evidence Report — Confidential",
        )
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        canvas.drawRightString(
            doc.pagesize[0] - 0.6 * inch,
            0.4 * inch,
            f"Generated: {ts}",
        )
        canvas.restoreState()

    # ── sections ──────────────────────────────────────────────

    def _header_cell(self, value: Any) -> Paragraph:
        text = "" if value is None else str(value)
        return Paragraph(escape(text), self.styles["GeoTableHeader"])

    def _cell(self, value: Any) -> Paragraph:
        text = "—" if value in (None, "") else str(value)
        return Paragraph(escape(text), self.styles["GeoTableCell"])

    def _build_title_page(self, pkg: EvidencePackage) -> list:
        """Title page with project metadata."""
        elements: list = []
        elements.append(Spacer(1, 1.5 * inch))
        elements.append(Paragraph("GeoMRV", self.styles["GeoTitle"]))
        elements.append(
            Paragraph("Evidence &amp; Verification Report", self.styles["GeoSubtitle"])
        )
        elements.append(Spacer(1, 0.4 * inch))
        elements.append(
            Paragraph(pkg.project_name, self.styles["GeoSubtitle"])
        )
        elements.append(Spacer(1, 0.6 * inch))

        # Metadata table
        status_colour = _STATUS_COLORS.get(pkg.overall_status, colors.black)
        data = [
            [self._cell("Analysis Period"), self._cell(f"{pkg.analysis_period_start}  to  {pkg.analysis_period_end}")],
            [self._cell("Generated"), self._cell(pkg.generated_date)],
            [self._cell("Package ID"), self._cell(pkg.package_id)],
            [self._cell("Growth Status"), self._cell(pkg.growth_classification.upper())],
            [self._cell("Confidence Score"), self._cell(f"{pkg.confidence_score:.1f} / 100")],
            [self._cell("Overall Status"), self._cell(pkg.overall_status)],
            [self._cell("Methodology"), self._cell(f"v{pkg.methodology_version}")],
        ]
        t = Table(data, colWidths=[2.2 * inch, 4.2 * inch])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e7e6e6")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        elements.append(t)

        return elements

    def _build_executive_summary(self, pkg: EvidencePackage) -> list:
        """Executive summary section."""
        elements: list = []
        elements.append(Paragraph("1. Executive Summary", self.styles["GeoHeading"]))

        summary_text = (
            f"This evidence package documents the monitoring and verification results for "
            f"<b>{pkg.project_name}</b> covering the period "
            f"<b>{pkg.analysis_period_start}</b> to <b>{pkg.analysis_period_end}</b>."
        )
        elements.append(Paragraph(summary_text, self.styles["GeoBody"]))
        elements.append(Spacer(1, 0.15 * inch))

        # Key findings
        elements.append(Paragraph("Key Findings", self.styles["GeoHeading"]))

        findings = [
            [self._header_cell("Metric"), self._header_cell("Value")],
            [self._cell("Growth Classification"), self._cell(pkg.growth_classification.upper())],
            [self._cell("Confidence Score"), self._cell(f"{pkg.confidence_score:.1f} / 100")],
            [self._cell("Overall Status"), self._cell(pkg.overall_status)],
            [self._cell("Data Quality Score"), self._cell(f"{pkg.data_quality_score:.1f} / 100")],
            [self._cell("Data Sources"), self._cell(str(len(pkg.data_sources)))],
            [self._cell("Processing Steps"), self._cell(str(pkg.processing_step_count))],
            [self._cell("Verification Flags"), self._cell(str(pkg.flag_count))],
            [self._cell("Critical Flags"), self._cell(str(pkg.critical_flag_count))],
        ]
        t = Table(findings, colWidths=[3 * inch, 3.4 * inch])
        t.setStyle(self._standard_table_style(len(findings)))
        elements.append(t)
        elements.append(Spacer(1, 0.2 * inch))

        # Confidence gauge
        try:
            gauge_buf = self._viz.create_confidence_gauge(pkg.confidence_score)
            elements.append(Image(gauge_buf, width=4 * inch, height=2.5 * inch))
            elements.append(Paragraph("Figure 1: Confidence Score Gauge", self.styles["GeoCaption"]))
        except Exception as exc:
            logger.warning("Could not render confidence gauge: %s", exc)

        # Summary text
        if pkg.summary:
            elements.append(Spacer(1, 0.15 * inch))
            elements.append(Paragraph(pkg.summary, self.styles["GeoBody"]))

        return elements

    def _build_data_sources(self, pkg: EvidencePackage) -> list:
        """Data sources documentation."""
        elements: list = []
        elements.append(Paragraph("2. Data Sources", self.styles["GeoHeading"]))

        if not pkg.data_sources:
            elements.append(
                Paragraph("No data sources documented.", self.styles["GeoBody"])
            )
            return elements

        header = [
            self._header_cell("Source"),
            self._header_cell("Platform"),
            self._header_cell("Collection"),
            self._header_cell("Resolution"),
            self._header_cell("Access Date"),
        ]
        data = [header]
        for ds in pkg.data_sources:
            data.append(
                [
                    self._cell(ds.name),
                    self._cell(ds.platform),
                    self._cell(ds.collection),
                    self._cell(f"{ds.spatial_resolution_m}m"),
                    self._cell(ds.access_date[:10] if ds.access_date else "—"),
                ]
            )

        col_widths = [1.1 * inch, 0.9 * inch, 2.4 * inch, 0.8 * inch, 1.1 * inch]
        t = Table(data, colWidths=col_widths)
        t.setStyle(self._standard_table_style(len(data)))
        elements.append(t)

        return elements

    def _build_analysis_results(
        self,
        pkg: EvidencePackage,
        observations_df: Optional[pd.DataFrame],
    ) -> list:
        """Analysis results with optional embedded charts."""
        elements: list = []
        elements.append(Paragraph("3. Analysis Results", self.styles["GeoHeading"]))

        # Key features table
        if pkg.key_features:
            elements.append(
                Paragraph("3.1 Extracted Features", self.styles["GeoHeading"])
            )
            header = [
                self._header_cell("Feature"),
                self._header_cell("Value"),
                self._header_cell("Unit"),
                self._header_cell("Uncertainty"),
                self._header_cell("Source"),
            ]
            data = [header]
            for f in pkg.key_features:
                data.append(
                    [
                        self._cell(f.name),
                        self._cell(f"{f.value:.4f}"),
                        self._cell(f.unit),
                        self._cell(f"{f.uncertainty:.4f}" if f.uncertainty else "—"),
                        self._cell(f.source),
                    ]
                )
            col_widths = [1.6 * inch, 1.1 * inch, 0.9 * inch, 1.1 * inch, 1.4 * inch]
            t = Table(data, colWidths=col_widths)
            t.setStyle(self._standard_table_style(len(data)))
            elements.append(t)
            elements.append(Spacer(1, 0.3 * inch))

        # Feature importance chart
        if pkg.key_features:
            try:
                feat_dicts = [f.to_dict() for f in pkg.key_features]
                feat_buf = self._viz.create_feature_importance(feat_dicts)
                elements.append(
                    Image(feat_buf, width=5.5 * inch, height=3 * inch)
                )
                elements.append(
                    Paragraph(
                        "Figure 2: Key Feature Values", self.styles["GeoCaption"]
                    )
                )
                elements.append(Spacer(1, 0.2 * inch))
            except Exception as exc:
                logger.warning("Could not render feature chart: %s", exc)

        # Observation-based charts (if data provided)
        if observations_df is not None and len(observations_df) > 0:
            figure_num = 3
            # NDVI time-series
            try:
                ts_buf = self._viz.create_ndvi_timeseries(observations_df)
                elements.append(
                    Paragraph("3.2 NDVI Time Series", self.styles["GeoHeading"])
                )
                elements.append(
                    Image(ts_buf, width=6 * inch, height=3 * inch)
                )
                elements.append(
                    Paragraph(
                        f"Figure {figure_num}: NDVI Time Series with Trend",
                        self.styles["GeoCaption"],
                    )
                )
                figure_num += 1
                elements.append(Spacer(1, 0.2 * inch))
            except Exception as exc:
                logger.warning("Could not render NDVI time-series: %s", exc)

            # Seasonal pattern
            try:
                seasonal_buf = self._viz.create_seasonal_pattern(observations_df)
                elements.append(
                    Paragraph("3.3 Seasonal Pattern", self.styles["GeoHeading"])
                )
                elements.append(
                    Image(seasonal_buf, width=5.5 * inch, height=3 * inch)
                )
                elements.append(
                    Paragraph(
                        f"Figure {figure_num}: Monthly Seasonal NDVI Pattern",
                        self.styles["GeoCaption"],
                    )
                )
                elements.append(Spacer(1, 0.2 * inch))
            except Exception as exc:
                logger.warning("Could not render seasonal pattern: %s", exc)

        return elements

    def _build_verification_section(self, pkg: EvidencePackage) -> list:
        """Verification rule outcomes."""
        elements: list = []
        elements.append(
            Paragraph("4. Verification Results", self.styles["GeoHeading"])
        )

        if not pkg.verification_results:
            elements.append(
                Paragraph(
                    "No verification results available.", self.styles["GeoBody"]
                )
            )
            return elements

        # Summary text
        elements.append(
            Paragraph(
                f"{len(pkg.verification_results)} verification rule(s) evaluated. "
                f"<b>{pkg.flag_count}</b> flag(s) raised, including "
                f"<b>{pkg.critical_flag_count}</b> critical.",
                self.styles["GeoBody"],
            )
        )
        elements.append(Spacer(1, 0.15 * inch))

        # Table
        header = [
            self._header_cell("Rule ID"),
            self._header_cell("Rule Name"),
            self._header_cell("Status"),
            self._header_cell("Risk Level"),
            self._header_cell("Recommendation"),
        ]
        data = [header]
        for vr in pkg.verification_results:
            data.append(
                [
                    self._cell(vr.rule_id),
                    self._cell(vr.rule_name),
                    vr.status.upper(),
                    vr.risk_level.upper(),
                    self._cell(vr.recommendation),
                ]
            )
        col_widths = [0.7 * inch, 1.7 * inch, 0.8 * inch, 0.9 * inch, 2.2 * inch]
        t = Table(data, colWidths=col_widths)

        # Custom style: colour-code risk levels
        style_commands = self._standard_table_style_commands(len(data))
        for row_idx in range(1, len(data)):
            risk = pkg.verification_results[row_idx - 1].risk_level
            if risk in _RISK_COLORS:
                style_commands.append(
                    ("TEXTCOLOR", (3, row_idx), (3, row_idx), _RISK_COLORS[risk])
                )
            status = pkg.verification_results[row_idx - 1].status
            if status != "pass":
                style_commands.append(
                    ("FONTNAME", (2, row_idx), (2, row_idx), "Helvetica-Bold")
                )

        t.setStyle(TableStyle(style_commands))
        elements.append(t)
        elements.append(Spacer(1, 0.3 * inch))

        # Verification summary chart
        try:
            # Only show flagged results in chart
            flagged = [
                vr.to_dict()
                for vr in pkg.verification_results
                if vr.status != "pass"
            ]
            vr_buf = self._viz.create_verification_summary(flagged)
            elements.append(
                Image(vr_buf, width=5 * inch, height=2.8 * inch)
            )
            elements.append(
                Paragraph(
                    "Figure: Verification Flag Distribution",
                    self.styles["GeoCaption"],
                )
            )
        except Exception as exc:
            logger.warning("Could not render verification chart: %s", exc)

        return elements

    def _build_lineage_section(self, pkg: EvidencePackage) -> list:
        """Processing lineage / audit trail."""
        elements: list = []
        elements.append(
            Paragraph("5. Processing Lineage", self.styles["GeoHeading"])
        )
        elements.append(
            Paragraph(
                "Complete processing chain for full transparency and reproducibility. "
                "Each step is logged with timestamps, parameters, and status.",
                self.styles["GeoBody"],
            )
        )
        elements.append(Spacer(1, 0.15 * inch))

        if not pkg.processing_chain:
            elements.append(
                Paragraph("No processing steps recorded.", self.styles["GeoBody"])
            )
            return elements

        for step in pkg.processing_chain:
            step_title = (
                f"<b>Step {step.sequence}: "
                f"{step.operation.replace('_', ' ').title()}</b>"
            )
            elements.append(Paragraph(step_title, self.styles["GeoBody"]))

            details = [
                [self._cell("Timestamp"), self._cell(step.timestamp[:19] if step.timestamp else "—")],
                [self._cell("Status"), self._cell(step.status.upper())],
                [self._cell("Duration"), self._cell(f"{step.duration_ms} ms")],
                [self._cell("Script Version"), self._cell(step.script_version)],
            ]

            if step.parameters:
                params_str = ", ".join(
                    f"{k}={v}" for k, v in list(step.parameters.items())[:5]
                )
                details.append([self._cell("Parameters"), self._cell(params_str)])

            if step.error_message:
                details.append([self._cell("Error"), self._cell(step.error_message)])

            t = Table(details, colWidths=[1.5 * inch, 4.8 * inch])
            t.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.lightgrey),
                    ]
                )
            )
            elements.append(t)
            elements.append(Spacer(1, 0.15 * inch))

        return elements

    def _build_appendix(self, pkg: EvidencePackage) -> list:
        """Appendix with package metadata and checksum."""
        elements: list = []
        elements.append(Paragraph("Appendix: Package Metadata", self.styles["GeoHeading"]))

        meta_data = [
            [self._header_cell("Field"), self._header_cell("Value")],
            [self._cell("Package ID"), self._cell(pkg.package_id)],
            [self._cell("Project ID"), self._cell(pkg.project_id)],
            [self._cell("Analyst"), self._cell(pkg.analyst)],
            [self._cell("Methodology Version"), self._cell(pkg.methodology_version)],
            [self._cell("Data Quality Score"), self._cell(f"{pkg.data_quality_score:.1f}")],
            [self._cell("Checksum (SHA-256)"), self._cell(pkg.checksum if pkg.checksum else "Not sealed")],
            [self._cell("Overall Status"), self._cell(pkg.overall_status)],
            [self._cell("Generated Date"), self._cell(pkg.generated_date)],
        ]
        t = Table(meta_data, colWidths=[2.2 * inch, 4.2 * inch])
        t.setStyle(self._standard_table_style(len(meta_data)))
        elements.append(t)
        elements.append(Spacer(1, 0.3 * inch))

        elements.append(
            Paragraph(
                "This report was generated automatically by the GeoMRV pipeline. "
                "All data, processing steps, and verification results are fully traceable. "
                "The SHA-256 checksum can be used to verify package integrity.",
                self.styles["GeoBody"],
            )
        )

        return elements

    # ── table style helpers ───────────────────────────────────

    def _standard_table_style_commands(self, n_rows: int) -> list:
        """Build standard table style commands for n_rows (incl. header)."""
        cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), _HEADER_FG),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
        # Alternate row shading
        for i in range(1, n_rows):
            if i % 2 == 0:
                cmds.append(("BACKGROUND", (0, i), (-1, i), _ROW_ALT))
        return cmds

    def _standard_table_style(self, n_rows: int) -> TableStyle:
        """Return a ``TableStyle`` for a standard data table."""
        return TableStyle(self._standard_table_style_commands(n_rows))


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────


def _truncate(text: str, max_len: int) -> str:
    """Truncate text, adding '…' if it exceeds *max_len*."""
    if not text:
        return "—"
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"
