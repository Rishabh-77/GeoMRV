# Phase 3: Evidence & Audit Packaging (Weeks 10–11)

**Duration:** 2 weeks  
**Goal:** Generate audit-ready evidence packages with visualizations and processing lineage  
**Deliverable:** PDF reports, metadata packages, and downloadable evidence

---

## 📊 Phase Overview

Phase 3 is critical for MVP success—it transforms raw data and models into audit-ready evidence. The system generates:
- Professional PDF reports with charts
- Complete processing lineage (data provenance)
- Confidence scores and risk assessments
- Verification rule outcomes
- Structured metadata for audit compliance

### Success Metrics
- PDF reports generated successfully
- All processing steps documented with timestamps
- Evidence packages stored in Azure Blob Storage
- Checksum integrity verification working
- Reports accepted by auditors (validation step)

---

## 🎯 Tasks Breakdown

### Task 3.1: Evidence Package Structure (Days 1–3)

**Objective:** Define audit-ready evidence package schema

**Steps:**

1. **Create Evidence Package Model**
   ```python
   # src/evidence_generation/package_schema.py
   from dataclasses import dataclass, asdict
   from datetime import datetime
   from typing import List, Dict
   import json
   
   @dataclass
   class DataSource:
       name: str  # Sentinel-2, Landsat, etc.
       platform: str  # ESA, USGS, GEE
       collection: str  # e.g., COPERNICUS/S2
       access_date: str  # ISO date
       url: str  # Reference to original data
   
   @dataclass
   class ProcessingStep:
       sequence: int
       operation: str  # feature_extraction, ml_scoring, etc.
       timestamp: str  # ISO timestamp
       script_version: str
       parameters: Dict
       inputs: Dict
       outputs: Dict
       duration_ms: int
       status: str  # success, failed
   
   @dataclass
   class VerificationResult:
       rule_id: str
       rule_name: str
       status: str  # pass, flag, critical
       risk_level: str
       description: str
       recommendation: str
   
   @dataclass
   class Feature:
       name: str
       value: float
       unit: str
       uncertainty: float
       source: str  # satellite data, ml model, calculation
   
   @dataclass
   class EvidencePackage:
       package_id: str  # UUID
       project_id: str
       project_name: str
       analysis_period_start: str  # ISO date
       analysis_period_end: str  # ISO date
       generated_date: str
       
       # Data sources
       data_sources: List[DataSource]
       
       # Processing lineage
       processing_chain: List[ProcessingStep]
       
       # Key findings
       key_features: List[Feature]
       growth_classification: str  # growth, stable, loss
       confidence_score: float  # 0-100
       
       # Verification outcomes
       verification_results: List[VerificationResult]
       
       # Metadata
       analyst: str
       methodology_version: str
       data_quality_score: float
       
       def to_dict(self):
           return asdict(self)
       
       def to_json(self):
           return json.dumps(self.to_dict(), indent=2)
   ```

2. **Create Package Validator**
   ```python
   # src/evidence_generation/package_validator.py
   from typing import List
   import logging
   
   logger = logging.getLogger(__name__)
   
   class EvidencePackageValidator:
       """Validate evidence package completeness"""
       
       def validate(self, package) -> List[str]:
           """
           Check package completeness
           
           Returns:
               List of validation errors (empty if valid)
           """
           errors = []
           
           # Check required fields
           if not package.project_id:
               errors.append("Missing project_id")
           if not package.analysis_period_start or not package.analysis_period_end:
               errors.append("Missing analysis period")
           if not package.data_sources or len(package.data_sources) == 0:
               errors.append("No data sources documented")
           if not package.processing_chain or len(package.processing_chain) == 0:
               errors.append("No processing steps logged")
           
           # Check confidence score
           if package.confidence_score is None or package.confidence_score < 0:
               errors.append("Invalid confidence score")
           
           # Check verification results
           if not package.verification_results:
               errors.append("No verification results")
           
           # Critical flags
           critical_flags = [
               v for v in package.verification_results 
               if v.risk_level == "critical"
           ]
           if critical_flags:
               logger.warning(f"Package has {len(critical_flags)} critical flags")
           
           return errors
   ```

**Deliverables:**
- [x] EvidencePackage dataclass defined
    - Verified `EvidencePackage` in `src/evidence_generation/package_schema.py`.
    - 5 supporting dataclasses: `DataSource`, `ProcessingStep`, `VerificationResult`, `Feature`, plus the main `EvidencePackage`.
    - All dataclasses support `to_dict()` / `from_dict()` and `to_json()` / `from_json()` round-trip serialisation.
    - Convenience properties: `flag_count`, `critical_flag_count`, `processing_step_count`, `has_ml_scoring`, `has_verification`, `get_feature_by_name()`.
    - Class-level validation constants: `VALID_CLASSIFICATIONS`, `VALID_STATUSES`, `VALID_SOURCES`, `VALID_RISK_LEVELS`.
- [x] Package validator implemented
    - Verified `EvidencePackageValidator` in `src/evidence_generation/package_validator.py`.
    - 8 discrete check methods: `_check_required_identifiers`, `_check_analysis_period`, `_check_data_sources`, `_check_processing_chain`, `_check_findings`, `_check_verification_results`, `_check_metadata`, `_check_data_quality`.
    - Returns structured `ValidationReport` with `errors` (blocking) and `warnings` (non-blocking).
    - `validate_and_raise()` raises `ValueError` on invalid packages.
    - Analysis period date ordering enforced; short-period warning (< 30 days).
- [x] Schema matches audit requirements
    - Full processing lineage via `processing_chain` (ordered steps with params/inputs/outputs/duration/status).
    - Data provenance via `data_sources` (satellite collection, access date, spatial resolution, temporal range).
    - Verification traceability via `verification_results` (rule_id, risk_level, recommendation).
    - Methodology versioning and analyst identification in metadata fields.
- [x] JSON serialization working
    - Verified: `to_json()` → `from_json()` round-trip preserves all fields including nested objects.
    - Compact and pretty-print modes supported.
    - Extra keys in input dicts are safely ignored during deserialisation.
- [x] Checksum integrity verification
    - SHA-256 checksum computed over canonical JSON (sorted keys, checksum field excluded).
    - `seal()` sets checksum; `verify_integrity()` detects tampering.
    - Verified: round-trip through JSON preserves checksum validity.
- [x] Documentation of required fields
    - All dataclasses fully documented with docstrings and attribute descriptions.
    - Module-level docstring with usage example.
    - 77 unit tests covering all schema and validator functionality.

**Files Created:**
- [x] `src/evidence_generation/__init__.py`
- [x] `src/evidence_generation/package_schema.py`
- [x] `src/evidence_generation/package_validator.py`
- [x] `tests/test_package_schema.py`

---

### Task 3.2: Report Generation (Days 3–6)

**Objective:** Create professional PDF reports with visualizations

**Steps:**

1. **Create Visualization Service**
   ```python
   # src/evidence_generation/visualizations.py
   import matplotlib.pyplot as plt
   import matplotlib.dates as mdates
   import seaborn as sns
   import pandas as pd
   import numpy as np
   from io import BytesIO
   import logging
   
   logger = logging.getLogger(__name__)
   
   class ReportVisualizations:
       """Generate charts for evidence reports"""
       
       def __init__(self):
           sns.set_style("whitegrid")
           plt.rcParams['figure.figsize'] = (12, 6)
       
       def create_ndvi_timeseries(self, observations_df: pd.DataFrame) -> BytesIO:
           """Plot NDVI time series with trend"""
           fig, ax = plt.subplots(figsize=(12, 5))
           
           # Sort by date
           obs_df = observations_df.sort_values('date')
           
           # Plot raw observations
           ax.scatter(obs_df['date'], obs_df['ndvi'], alpha=0.6, s=50, label='Raw observations')
           
           # Add smoothed trend
           if len(obs_df) > 3:
               obs_df['ndvi_smooth'] = obs_df['ndvi'].rolling(window=3, center=True).mean()
               ax.plot(obs_df['date'], obs_df['ndvi_smooth'], 'r-', linewidth=2, label='Smoothed trend')
           
           # Linear trend line
           x = np.arange(len(obs_df))
           y = obs_df['ndvi'].values
           mask = ~np.isnan(y)
           if len(x[mask]) >= 2:
               coeffs = np.polyfit(x[mask], y[mask], 1)
               trend_line = np.polyval(coeffs, x)
               ax.plot(obs_df['date'], trend_line, 'g--', linewidth=2, label='Linear trend', alpha=0.7)
           
           ax.set_xlabel('Date', fontsize=12)
           ax.set_ylabel('NDVI', fontsize=12)
           ax.set_title('Vegetation Index Time Series (NDVI)', fontsize=14, fontweight='bold')
           ax.legend(loc='best')
           ax.grid(True, alpha=0.3)
           ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
           plt.xticks(rotation=45)
           plt.tight_layout()
           
           # Save to bytes
           buf = BytesIO()
           plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
           buf.seek(0)
           plt.close()
           
           return buf
       
       def create_seasonal_pattern(self, observations_df: pd.DataFrame) -> BytesIO:
           """Plot seasonal NDVI pattern"""
           fig, ax = plt.subplots(figsize=(10, 5))
           
           obs_df = observations_df.copy()
           obs_df['month'] = pd.to_datetime(obs_df['date']).dt.month
           
           # Group by month
           monthly_stats = obs_df.groupby('month')['ndvi'].agg(['mean', 'std'])
           
           months = monthly_stats.index
           means = monthly_stats['mean'].values
           stds = monthly_stats['std'].values
           
           ax.bar(months, means, yerr=stds, capsize=5, alpha=0.7, color='steelblue', edgecolor='black')
           ax.set_xlabel('Month', fontsize=12)
           ax.set_ylabel('Mean NDVI', fontsize=12)
           ax.set_title('Seasonal NDVI Pattern', fontsize=14, fontweight='bold')
           ax.set_xticks(range(1, 13))
           ax.set_xticklabels(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])
           ax.grid(True, alpha=0.3, axis='y')
           
           plt.tight_layout()
           buf = BytesIO()
           plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
           buf.seek(0)
           plt.close()
           
           return buf
       
       def create_verification_summary(self, verification_results: list) -> BytesIO:
           """Plot verification rule outcomes"""
           fig, ax = plt.subplots(figsize=(10, 6))
           
           # Count by risk level
           risk_levels = {}
           for result in verification_results:
               level = result.get('risk_level', 'unknown')
               risk_levels[level] = risk_levels.get(level, 0) + 1
           
           if not risk_levels:
               # Empty plot
               ax.text(0.5, 0.5, 'No verification issues detected', 
                      ha='center', va='center', fontsize=14)
               ax.set_xlim(0, 1)
               ax.set_ylim(0, 1)
               ax.axis('off')
           else:
               colors = {
                   'critical': '#d62728',  # red
                   'high': '#ff7f0e',      # orange
                   'medium': '#ffbb78',    # light orange
                   'low': '#90ee90'        # light green
               }
               
               levels = list(risk_levels.keys())
               counts = list(risk_levels.values())
               bar_colors = [colors.get(l, 'gray') for l in levels]
               
               ax.bar(levels, counts, color=bar_colors, edgecolor='black', alpha=0.8)
               ax.set_ylabel('Number of Flags', fontsize=12)
               ax.set_title('Verification Rule Outcomes', fontsize=14, fontweight='bold')
               ax.grid(True, alpha=0.3, axis='y')
           
           plt.tight_layout()
           buf = BytesIO()
           plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
           buf.seek(0)
           plt.close()
           
           return buf
       
       def create_confidence_gauge(self, confidence_score: float) -> BytesIO:
           """Create confidence score gauge (0-100)"""
           fig, ax = plt.subplots(figsize=(8, 4), subplot_kw=dict(projection='polar'))
           
           # Create gauge
           theta = np.linspace(0, np.pi, 100)
           r = np.ones(100)
           
           # Color gradient: red (0) -> yellow (50) -> green (100)
           colors_range = [plt.cm.RdYlGn(i/100.0) for i in range(101)]
           
           # Normalize score to 0-1
           score_normalized = min(max(confidence_score / 100.0, 0), 1)
           needle_angle = score_normalized * np.pi
           
           # Plot gauge
           ax.plot(theta, r, color='black', linewidth=2)
           ax.barh(theta, r, width=0.01, alpha=0.0)
           
           # Plot needle
           ax.plot([needle_angle, needle_angle], [0, 1], 'k-', linewidth=3)
           ax.plot(needle_angle, 1.05, 'ko', markersize=10)
           
           # Labels
           ax.set_ylim(0, 1.2)
           ax.set_theta_zero_location('W')
           ax.set_theta_direction(-1)
           ax.set_xticks([0, np.pi/4, np.pi/2, 3*np.pi/4, np.pi])
           ax.set_xticklabels(['100', '75', '50', '25', '0'], fontsize=10)
           ax.set_yticks([])
           ax.set_title(f'Confidence Score: {confidence_score:.1f}%', 
                       fontsize=14, fontweight='bold', pad=20)
           
           plt.tight_layout()
           buf = BytesIO()
           plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
           buf.seek(0)
           plt.close()
           
           return buf
   ```

2. **Create PDF Report Generator**
   ```python
   # src/evidence_generation/report_generator.py
   from reportlab.lib.pagesizes import letter, A4
   from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
   from reportlab.lib.units import inch
   from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak, KeepTogether
   from reportlab.lib import colors
   from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
   from datetime import datetime
   import io
   import logging
   
   logger = logging.getLogger(__name__)
   
   class PDFReportGenerator:
       """Generate audit-ready PDF reports"""
       
       def __init__(self):
           self.styles = getSampleStyleSheet()
           self._setup_custom_styles()
       
       def _setup_custom_styles(self):
           """Create custom paragraph styles"""
           self.styles.add(ParagraphStyle(
               name='CustomTitle',
               parent=self.styles['Heading1'],
               fontSize=24,
               textColor=colors.HexColor('#1f4e78'),
               spaceAfter=30,
               alignment=TA_CENTER,
               fontName='Helvetica-Bold'
           ))
           
           self.styles.add(ParagraphStyle(
               name='CustomHeading',
               parent=self.styles['Heading2'],
               fontSize=14,
               textColor=colors.HexColor('#2e75b6'),
               spaceAfter=12,
               spaceBefore=12,
               fontName='Helvetica-Bold'
           ))
       
       def generate_report(self, evidence_package, output_path: str):
           """Generate complete PDF report"""
           doc = SimpleDocTemplate(
               output_path,
               pagesize=letter,
               rightMargin=0.5*inch,
               leftMargin=0.5*inch,
               topMargin=0.75*inch,
               bottomMargin=0.75*inch
           )
           
           story = []
           
           # Title page
           story.append(self._create_title_page(evidence_package))
           story.append(PageBreak())
           
           # Executive summary
           story.append(self._create_executive_summary(evidence_package))
           story.append(PageBreak())
           
           # Data sources
           story.append(self._create_data_sources_section(evidence_package))
           
           # Analysis results
           story.append(self._create_analysis_results(evidence_package))
           story.append(PageBreak())
           
           # Verification outcomes
           story.append(self._create_verification_section(evidence_package))
           story.append(PageBreak())
           
           # Processing lineage
           story.append(self._create_lineage_section(evidence_package))
           
           # Build PDF
           doc.build(story)
           logger.info(f"Report generated: {output_path}")
       
       def _create_title_page(self, package):
           """Create report title page"""
           story = []
           story.append(Spacer(1, 1.5*inch))
           
           story.append(Paragraph(
               "GeoMRV Evidence Package",
               self.styles['CustomTitle']
           ))
           
           story.append(Spacer(1, 0.3*inch))
           
           story.append(Paragraph(
               f"Project: {package.project_name}",
               self.styles['Heading2']
           ))
           
           story.append(Spacer(1, 0.5*inch))
           
           data = [
               ['Period:', f"{package.analysis_period_start} to {package.analysis_period_end}"],
               ['Generated:', package.generated_date],
               ['Package ID:', package.package_id[:16] + '...'],
               ['Growth Status:', package.growth_classification.upper()],
               ['Confidence:', f"{package.confidence_score:.1f}%"]
           ]
           
           t = Table(data, colWidths=[2*inch, 4*inch])
           t.setStyle(TableStyle([
               ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e7e6e6')),
               ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
               ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
               ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
               ('FONTSIZE', (0, 0), (-1, -1), 11),
               ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
               ('GRID', (0, 0), (-1, -1), 1, colors.black)
           ]))
           
           story.append(t)
           return story[0] if len(story) == 1 else KeepTogether(story)
       
       def _create_executive_summary(self, package):
           """Create executive summary section"""
           story = []
           
           story.append(Paragraph("Executive Summary", self.styles['CustomHeading']))
           
           summary_text = f"""
           <b>Growth Status:</b> {package.growth_classification.upper()}<br/>
           <b>Confidence Score:</b> {package.confidence_score:.1f}/100<br/>
           <b>Data Quality:</b> {package.data_quality_score:.1f}/100<br/>
           <b>Analysis Period:</b> {package.analysis_period_start} to {package.analysis_period_end}<br/>
           <br/>
           This evidence package documents the monitoring and verification results for {package.project_name}.
           The analysis is based on satellite imagery from {len(package.data_sources)} source(s) and includes
           {len(package.key_features)} key features extracted using standardized methodology (Version {package.methodology_version}).
           """
           
           story.append(Paragraph(summary_text, self.styles['BodyText']))
           return KeepTogether(story)
       
       def _create_data_sources_section(self, package):
           """Document data sources"""
           story = []
           
           story.append(Paragraph("Data Sources", self.styles['CustomHeading']))
           
           data = [['Source', 'Platform', 'Access Date', 'URL']]
           for source in package.data_sources:
               data.append([
                   source.name,
                   source.platform,
                   source.access_date,
                   source.url[:30] + '...' if len(source.url) > 30 else source.url
               ])
           
           t = Table(data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 2*inch])
           t.setStyle(TableStyle([
               ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
               ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
               ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
               ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
               ('FONTSIZE', (0, 0), (-1, 0), 10),
               ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
               ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
               ('GRID', (0, 0), (-1, -1), 1, colors.black),
               ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
           ]))
           
           story.append(t)
           return KeepTogether(story)
       
       def _create_analysis_results(self, package):
           """Analysis results with visualizations"""
           story = []
           
           story.append(Paragraph("Analysis Results", self.styles['CustomHeading']))
           
           # Key features table
           data = [['Feature', 'Value', 'Unit']]
           for feature in package.key_features:
               data.append([
                   feature.name,
                   f"{feature.value:.2f}",
                   feature.unit
               ])
           
           t = Table(data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
           t.setStyle(TableStyle([
               ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
               ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
               ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
               ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
               ('GRID', (0, 0), (-1, -1), 1, colors.black)
           ]))
           
           story.append(t)
           story.append(Spacer(1, 0.3*inch))
           
           return KeepTogether(story)
       
       def _create_verification_section(self, package):
           """Verification outcomes"""
           story = []
           
           story.append(Paragraph("Verification Results", self.styles['CustomHeading']))
           
           if not package.verification_results:
               story.append(Paragraph("No issues detected.", self.styles['BodyText']))
           else:
               data = [['Rule', 'Status', 'Risk Level', 'Recommendation']]
               for result in package.verification_results:
                   data.append([
                       result.rule_name[:25],
                       result.status,
                       result.risk_level,
                       result.recommendation[:30]
                   ])
               
               t = Table(data, colWidths=[1.5*inch, 1*inch, 1*inch, 2.5*inch])
               t.setStyle(TableStyle([
                   ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                   ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                   ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                   ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                   ('FONTSIZE', (0, 0), (-1, 0), 10),
                   ('GRID', (0, 0), (-1, -1), 1, colors.black),
                   ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
               ]))
               
               story.append(t)
           
           return KeepTogether(story)
       
       def _create_lineage_section(self, package):
           """Processing lineage for audit trail"""
           story = []
           
           story.append(Paragraph("Processing Lineage", self.styles['CustomHeading']))
           
           story.append(Paragraph(
               "All processing steps are logged below for full transparency and reproducibility:",
               self.styles['BodyText']
           ))
           story.append(Spacer(1, 0.2*inch))
           
           for step in package.processing_chain:
               text = f"""
               <b>Step {step.sequence}: {step.operation.replace('_', ' ').title()}</b><br/>
               Time: {step.timestamp}<br/>
               Status: {step.status}<br/>
               Duration: {step.duration_ms}ms
               """
               story.append(Paragraph(text, self.styles['Normal']))
               story.append(Spacer(1, 0.15*inch))
           
           return story
   ```

**Deliverables:**
- [x] ReportVisualizations class with 4+ chart types
    - Verified `ReportVisualizations` in `src/evidence_generation/visualizations.py`.
    - 5 chart types: `create_ndvi_timeseries()`, `create_seasonal_pattern()`, `create_verification_summary()`, `create_confidence_gauge()`, `create_feature_importance()`.
    - All methods return `BytesIO` PNG buffers at 150 DPI, ready for PDF embedding.
    - Matplotlib "Agg" backend for headless/CI safety. Seaborn "whitegrid" styling.
    - Custom GeoMRV brand colours; risk-level colour mapping (`critical` red → `low` green).
    - NDVI time-series supports optional smoothed trend, linear regression, and secondary EVI axis.
    - Seasonal pattern highlights peak (green) and trough (red) months with std-dev error bars.
    - Confidence gauge uses RdYlGn colormap wedges with needle and PASS/REVIEW/FAIL labels.
- [x] PDFReportGenerator implemented
    - Verified `PDFReportGenerator` in `src/evidence_generation/report_generator.py`.
    - 7 section builders: title page, executive summary, data sources, analysis results, verification outcomes, processing lineage, appendix.
    - Brand-consistent styles: `GeoTitle`, `GeoSubtitle`, `GeoHeading`, `GeoBody`, `GeoCaption`, `GeoFooter`.
    - Alternate-row shading, risk-level colour-coding in verification table, header/footer on every page.
    - Accepts optional `observations_df` for embedding NDVI time-series and seasonal charts.
    - Output directory auto-created; returns absolute path to generated PDF.
- [x] Sample PDF report generated
    - Verified via 55 automated tests (9 full-report generation tests producing valid `%PDF-` files).
    - Reports generated for: basic, with observations, with EVI, minimal package, flagged, low-confidence, sealed, multi-source, many-features scenarios.
- [x] All visualizations rendering correctly
    - 24 visualization-specific tests: all 5 chart types with edge cases (empty data, small datasets, boundary scores, negative values, truncated features).
    - All charts produce valid PNG files (verified via `\x89PNG` magic bytes and non-trivial file sizes).
- [x] Report structure audit-ready
    - Complete processing lineage section with per-step parameter tables.
    - Appendix with package ID, SHA-256 checksum, analyst, methodology version.
    - Branded footer with page numbers, "Confidential" label, and UTC generation timestamp.
- [x] Lineage tracking complete
    - Processing chain rendered as ordered step tables with timestamp, status, duration, parameters, and error messages.
    - Full traceability from data sources through processing to verification outcomes.

**Files Created:**
- [x] `src/evidence_generation/visualizations.py`
- [x] `src/evidence_generation/report_generator.py`
- [x] `tests/test_report_generation.py`

**Manual Verification Steps:**
1. Run `python -m pytest tests/test_report_generation.py -v` → 55 tests should pass.
2. Generate a sample report:
   ```python
   from src.evidence_generation.report_generator import PDFReportGenerator
   from src.evidence_generation.package_schema import *
   import pandas as pd, numpy as np

   # Build sample package (use test fixtures from test_report_generation.py)
   pkg = EvidencePackage(
       package_id="manual-test-001", project_id="proj-001",
       project_name="Manual Verification Test",
       analysis_period_start="2025-01-01", analysis_period_end="2025-12-31",
       generated_date="2026-03-01T12:00:00",
       data_sources=[DataSource("Sentinel-2","ESA","COPERNICUS/S2_SR_HARMONIZED",
                     "2026-02-15","https://earthengine.google.com",10.0,"2025-01-01","2025-12-31")],
       processing_chain=[ProcessingStep(1,"data_fetch","2026-03-01T10:00:00","1.0.0",{},{},{},350,"success","")],
       key_features=[Feature("ndvi_mean",0.52,"index",0.03,"satellite_data","Mean NDVI")],
       growth_classification="growth", confidence_score=85.0,
       verification_results=[VerificationResult("R1","Obs Check","pass","low","OK","None")],
       analyst="Test", methodology_version="1.0.0", data_quality_score=92.5,
   )

   obs_df = pd.DataFrame({
       "date": pd.date_range("2025-01-01", periods=36, freq="10D"),
       "ndvi": 0.3 + 0.25 * np.sin(np.linspace(0, 2*np.pi, 36)) + np.random.normal(0, 0.03, 36),
   })

   gen = PDFReportGenerator()
   path = gen.generate_report(pkg, "output/manual_test_report.pdf", observations_df=obs_df)
   print(f"Report at: {path}")
   ```
3. Open the generated PDF and verify: title page, executive summary with gauge, data sources table, NDVI charts, verification table, processing lineage, appendix with checksum.

---

### Task 3.3: Evidence Package Assembly & Storage (Days 6–9)

**Objective:** Assemble packages and store in Azure Blob Storage

**Steps:**

1. **Create Assembly Service**
   ```python
   # src/evidence_generation/package_assembly.py
   from src.evidence_generation.package_schema import EvidencePackage, DataSource, ProcessingStep, VerificationResult, Feature
   from src.api.models import Observation, ProcessingLog, Project
   from sqlalchemy.orm import Session
   import json
   from datetime import datetime
   
   class PackageAssemblyService:
       """Assemble evidence packages from raw data and results"""
       
       def __init__(self, db: Session):
           self.db = db
       
       def assemble_package(self, project_id: str, start_date: str, end_date: str) -> EvidencePackage:
           """
           Assemble complete evidence package
           """
           # Load project
           project = self.db.query(Project).filter(Project.id == project_id).first()
           
           # Load all processing logs
           logs = self.db.query(ProcessingLog).filter(
               (ProcessingLog.project_id == project_id) &
               (ProcessingLog.created_at >= start_date) &
               (ProcessingLog.created_at <= end_date)
           ).order_by(ProcessingLog.created_at).all()
           
           # Build processing chain
           processing_steps = []
           for idx, log in enumerate(logs, 1):
               processing_steps.append(ProcessingStep(
                   sequence=idx,
                   operation=log.operation_type,
                   timestamp=log.created_at.isoformat(),
                   script_version="0.1.0",
                   parameters=log.input_data or {},
                   inputs={},
                   outputs=log.output_data or {},
                   duration_ms=log.execution_time_ms or 0,
                   status=log.status
               ))
           
           # Extract features from latest feature extraction log
           features_log = next((l for l in logs if l.operation_type == 'feature_extraction'), None)
           key_features = []
           if features_log and features_log.output_data:
               features_dict = features_log.output_data
               key_features = [
                   Feature(
                       name='NDVI Mean',
                       value=features_dict.get('ndvi_stats', {}).get('mean', 0),
                       unit='Index',
                       uncertainty=features_dict.get('ndvi_stats', {}).get('std', 0),
                       source='Sentinel-2'
                   ),
                   Feature(
                       name='Growth Trend',
                       value=features_dict.get('trend', {}).get('trend_slope', 0),
                       unit='Index/day',
                       uncertainty=0.0001,
                       source='Satellite time-series'
                   )
               ]
           
           # Extract verification results
           verification_log = next((l for l in logs if l.operation_type == 'verification'), None)
           verification_results = []
           if verification_log and verification_log.output_data:
               for flag in verification_log.output_data.get('flags', []):
                   verification_results.append(VerificationResult(
                       rule_id=flag.get('rule_id'),
                       rule_name=flag.get('name'),
                       status='flag' if flag.get('risk_level') != 'low' else 'pass',
                       risk_level=flag.get('risk_level'),
                       description=flag.get('description'),
                       recommendation='Review flag'
                   ))
           
           # Get confidence and classification from ML log
           ml_log = next((l for l in logs if l.operation_type == 'ml_scoring'), None)
           confidence = 50.0
           classification = 'stable'
           if ml_log and ml_log.output_data:
               confidence = ml_log.output_data.get('confidence', 50) * 100
               classification = ml_log.output_data.get('prediction', 'stable')
           
           # Data sources
           data_sources = [
               DataSource(
                   name='Sentinel-2',
                   platform='ESA Copernicus',
                   collection='COPERNICUS/S2',
                   access_date=datetime.now().isoformat(),
                   url='https://earthengine.google.com'
               )
           ]
           
           # Create package
           package = EvidencePackage(
               package_id=f"pkg_{project_id}_{start_date}_{end_date}",
               project_id=str(project_id),
               project_name=project.name,
               analysis_period_start=start_date,
               analysis_period_end=end_date,
               generated_date=datetime.now().isoformat(),
               data_sources=data_sources,
               processing_chain=processing_steps,
               key_features=key_features,
               growth_classification=classification,
               confidence_score=confidence,
               verification_results=verification_results,
               analyst='GeoMRV System',
               methodology_version='0.1.0',
               data_quality_score=confidence
           )
           
           return package
   ```

2. **Create Storage Service**
   ```python
   # src/evidence_generation/storage_service.py
   from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
   from azure.core.exceptions import AzureError
   import hashlib
   import logging
   import os
   
   logger = logging.getLogger(__name__)
   
   class EvidenceStorageService:
       """Store evidence packages in Azure Blob Storage"""
       
       def __init__(self, connection_string: str, container_name: str = 'evidence-packages'):
           self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
           self.container_name = container_name
       
       def upload_package(self, file_path: str, package_id: str) -> dict:
           """
           Upload evidence package to Azure Blob Storage
           
           Returns:
               {
                   'blob_path': path in storage,
                   'url': public URL,
                   'checksum': SHA-256 hash,
                   'size_bytes': file size
               }
           """
           try:
               # Read file
               with open(file_path, 'rb') as f:
                   blob_data = f.read()
               
               # Calculate checksum
               checksum = hashlib.sha256(blob_data).hexdigest()
               
               # Upload blob
               blob_name = f"packages/{package_id}.pdf"
               blob_client = self.blob_service_client.get_blob_client(
                   container=self.container_name,
                   blob=blob_name
               )
               
               blob_client.upload_blob(blob_data, overwrite=True)
               
               # Get file size
               file_size = os.path.getsize(file_path)
               
               logger.info(f"Uploaded {blob_name}: {file_size} bytes, checksum={checksum[:16]}...")
               
               return {
                   'blob_path': blob_name,
                   'checksum': checksum,
                   'size_bytes': file_size,
                   'url': blob_client.url
               }
           
           except AzureError as e:
               logger.error(f"Azure storage error: {e}")
               raise
       
       def download_package(self, blob_name: str, local_path: str):
           """Download evidence package from storage"""
           try:
               blob_client = self.blob_service_client.get_blob_client(
                   container=self.container_name,
                   blob=blob_name
               )
               
               with open(local_path, 'wb') as f:
                   f.write(blob_client.download_blob().readall())
               
               logger.info(f"Downloaded {blob_name} to {local_path}")
           except AzureError as e:
               logger.error(f"Download error: {e}")
               raise
   ```

3. **Create Evidence Endpoint**
   ```python
   # src/api/routers/evidence.py
   from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
   from fastapi.responses import FileResponse
   from src.api.database import get_db
   from src.evidence_generation.package_assembly import PackageAssemblyService
   from src.evidence_generation.report_generator import PDFReportGenerator
   from src.evidence_generation.storage_service import EvidenceStorageService
   import os
   
   router = APIRouter()
   
   @router.post("/{project_id}/generate")
   def generate_evidence_package(
       project_id: str,
       start_date: str,
       end_date: str,
       background_tasks: BackgroundTasks,
       db = Depends(get_db)
   ):
       """Generate and store evidence package"""
       try:
           # Assemble package
           assembly_service = PackageAssemblyService(db)
           package = assembly_service.assemble_package(project_id, start_date, end_date)
           
           # Generate PDF
           report_gen = PDFReportGenerator()
           temp_path = f"/tmp/report_{package.package_id}.pdf"
           report_gen.generate_report(package, temp_path)
           
           # Upload to Azure (background)
           background_tasks.add_task(
               _upload_to_storage,
               temp_path,
               package.package_id
           )
           
           # Save package metadata
           from src.api.models import EvidencePackage as EvidencePackageModel
           pkg = EvidencePackageModel(
               id=package.package_id,
               project_id=project_id,
               package_date=start_date,
               period_start=start_date,
               period_end=end_date,
               status='generated',
               s3_path=f"packages/{package.package_id}.pdf",
               checksum=''
           )
           db.add(pkg)
           db.commit()
           
           return {
               'package_id': package.package_id,
               'status': 'generating',
               'growth_classification': package.growth_classification,
               'confidence_score': package.confidence_score
           }
       except Exception as e:
           raise HTTPException(status_code=500, detail=str(e))
   
   @router.get("/{package_id}/download")
   def download_evidence(package_id: str, db = Depends(get_db)):
       """Download evidence package PDF"""
       pkg = db.query(EvidencePackageModel).filter(
           EvidencePackageModel.id == package_id
       ).first()
       
       if not pkg:
           raise HTTPException(status_code=404, detail="Package not found")
       
       # Download from Azure
       storage = EvidenceStorageService(os.getenv('AZURE_STORAGE_CONNECTION_STRING'))
       local_path = f"/tmp/{package_id}.pdf"
       storage.download_package(pkg.s3_path, local_path)
       
       return FileResponse(local_path, filename=f"{package_id}.pdf")
   
   def _upload_to_storage(file_path: str, package_id: str):
       """Background task to upload to Azure"""
       storage = EvidenceStorageService(os.getenv('AZURE_STORAGE_CONNECTION_STRING'))
       storage.upload_package(file_path, package_id)
       os.remove(file_path)  # Clean up temp file
   ```

**Deliverables:**
- [ ] PackageAssemblyService assembles complete packages
- [ ] Azure Blob Storage integration working
- [ ] PDF reports generated and uploaded
- [ ] Checksum integrity verification
- [ ] Download endpoint operational
- [ ] Evidence packages stored with metadata

**Files to Create:**
- `src/evidence_generation/package_assembly.py`
- `src/evidence_generation/storage_service.py`
- `tests/test_storage_service.py`

---

### Task 3.4: Integration & Testing (Days 9–11)

**Objective:** Test end-to-end evidence generation pipeline

**Steps:**

1. **Create Integration Tests**
   ```python
   # tests/test_evidence_pipeline.py
   import pytest
   from src.evidence_generation.package_assembly import PackageAssemblyService
   from src.evidence_generation.report_generator import PDFReportGenerator
   from src.evidence_generation.package_schema import EvidencePackage, Feature
   
   def test_package_assembly(db):
       """Test assembling evidence package from logs"""
       service = PackageAssemblyService(db)
       package = service.assemble_package('test_project', '2023-01-01', '2023-12-31')
       
       assert package.project_id == 'test_project'
       assert package.analysis_period_start == '2023-01-01'
       assert len(package.processing_chain) > 0
   
   def test_report_generation():
       """Test PDF report generation"""
       # Create mock package
       package = EvidencePackage(
           package_id='test_pkg',
           project_id='proj1',
           project_name='Test Project',
           analysis_period_start='2023-01-01',
           analysis_period_end='2023-12-31',
           generated_date='2024-01-15',
           data_sources=[],
           processing_chain=[],
           key_features=[Feature('Test', 0.5, 'unit', 0.1, 'source')],
           growth_classification='growth',
           confidence_score=85,
           verification_results=[],
           analyst='test',
           methodology_version='0.1.0',
           data_quality_score=85
       )
       
       # Generate report
       gen = PDFReportGenerator()
       gen.generate_report(package, '/tmp/test_report.pdf')
       
       # Verify file created
       import os
       assert os.path.exists('/tmp/test_report.pdf')
       os.remove('/tmp/test_report.pdf')
   ```

2. **Create Sample Data Test**
   ```bash
   # Run end-to-end test with sample project
   python -m pytest tests/test_evidence_pipeline.py -v
   ```

**Deliverables:**
- [ ] Integration tests passing
- [ ] Sample evidence package generated
- [ ] PDF report readable and complete
- [ ] Azure storage upload verified
- [ ] Checksum validation working
- [ ] Pipeline end-to-end functional

---

## ✅ Phase 3 Checklist

- [ ] Evidence package schema defined
- [ ] Package validator implemented
- [ ] Report visualizations complete
- [ ] PDF report generator working
- [ ] Azure Blob Storage integration
- [ ] Package assembly service functional
- [ ] Evidence endpoint operational
- [ ] Download endpoint working
- [ ] Checksum verification working
- [ ] Integration tests passing
- [ ] Sample report generated and validated
- [ ] Ready for frontend integration (Phase 4)

---

## 📊 Phase 3 Deliverables

| Component | Status | Notes |
|-----------|--------|-------|
| Package Schema | ✅ | Complete structure |
| Visualizations | ✅ | 4+ chart types |
| PDF Report | ✅ | Professional format |
| Azure Storage | ✅ | Upload/download working |
| Package Assembly | ✅ | Full lineage tracking |
| Evidence Download | ✅ | Checksum verification |

---

**Next Phase:** [Phase 4: Frontend & Integration](phase4_frontend_integration.md)  
**Timeline:** Weeks 12–13
