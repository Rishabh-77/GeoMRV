"""
Tests for Report Generation (Task 3.2)
=========================================
Comprehensive tests covering:

**ReportVisualizations** (5 chart types):
- NDVI time-series (with/without trend, EVI overlay)
- Seasonal pattern (monthly bars with error bars)
- Verification summary (risk-level grouping, empty case)
- Confidence gauge (PASS / REVIEW / FAIL bands)
- Feature importance (horizontal bar chart, empty case)

**PDFReportGenerator**:
- Full report generation from evidence package
- Report with observation data (charts embedded)
- Report without optional data (graceful fallback)
- Individual section builders
- Table styling helpers
- Footer rendering
- Output directory creation

**Integration**:
- End-to-end: package → visualizations → PDF report
"""

from __future__ import annotations

import os
import tempfile
from io import BytesIO
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.evidence_generation.package_schema import (
    DataSource,
    EvidencePackage,
    Feature,
    ProcessingStep,
    VerificationResult,
)
from src.evidence_generation.visualizations import ReportVisualizations
from src.evidence_generation.report_generator import PDFReportGenerator


# ────────────────────────────────────────────────────────────
# Test Fixtures — reusable building blocks
# ────────────────────────────────────────────────────────────


def _make_data_source(**overrides) -> DataSource:
    defaults = dict(
        name="Sentinel-2",
        platform="ESA",
        collection="COPERNICUS/S2_SR_HARMONIZED",
        access_date="2026-02-15",
        url="https://earthengine.google.com",
        spatial_resolution_m=10.0,
        temporal_range_start="2025-01-01",
        temporal_range_end="2025-12-31",
    )
    defaults.update(overrides)
    return DataSource(**defaults)


def _make_processing_step(seq: int = 1, **overrides) -> ProcessingStep:
    defaults = dict(
        sequence=seq,
        operation="feature_extraction",
        timestamp="2026-03-01T10:00:00",
        script_version="1.0.0",
        parameters={"cloud_cover_threshold": 30.0},
        inputs={"project_id": "test-project", "observation_count": 48},
        outputs={"feature_count": 10},
        duration_ms=350,
        status="success",
        error_message="",
    )
    defaults.update(overrides)
    return ProcessingStep(**defaults)


def _make_verification_result(**overrides) -> VerificationResult:
    defaults = dict(
        rule_id="R1",
        rule_name="Insufficient Observations",
        status="pass",
        risk_level="medium",
        description="18 clear observations (threshold: 12)",
        recommendation="No action required",
    )
    defaults.update(overrides)
    return VerificationResult(**defaults)


def _make_feature(**overrides) -> Feature:
    defaults = dict(
        name="ndvi_mean",
        value=0.52,
        unit="index",
        uncertainty=0.03,
        source="satellite_data",
        description="Mean NDVI across analysis period",
    )
    defaults.update(overrides)
    return Feature(**defaults)


def _make_valid_package(**overrides) -> EvidencePackage:
    """Build a fully valid evidence package."""
    defaults = dict(
        package_id="pkg-00000000-0000-0000-0000-000000000001",
        project_id="proj-00000000-0000-0000-0000-000000000001",
        project_name="Western Ghats Restoration - Test",
        analysis_period_start="2025-01-01",
        analysis_period_end="2025-12-31",
        generated_date="2026-03-01T12:00:00",
        data_sources=[_make_data_source()],
        processing_chain=[
            _make_processing_step(1, operation="satellite_data_fetch"),
            _make_processing_step(2, operation="feature_extraction"),
            _make_processing_step(3, operation="ml_scoring"),
            _make_processing_step(4, operation="verification"),
        ],
        key_features=[
            _make_feature(name="ndvi_mean", value=0.52, unit="index"),
            _make_feature(
                name="trend_slope", value=0.005, unit="index/day", source="calculation"
            ),
            _make_feature(
                name="biomass_estimate", value=45.2, unit="t/ha", source="ml_model"
            ),
        ],
        growth_classification="growth",
        confidence_score=85.0,
        verification_results=[
            _make_verification_result(rule_id="R1", status="pass"),
            _make_verification_result(rule_id="R2", status="flag", risk_level="medium"),
            _make_verification_result(rule_id="R3", status="flag", risk_level="critical"),
        ],
        analyst="GeoMRV Automated Pipeline",
        methodology_version="1.0.0",
        data_quality_score=92.5,
        overall_status="PASS",
        summary="Healthy growth detected over 12-month period.",
    )
    defaults.update(overrides)
    return EvidencePackage(**defaults)


def _make_observations_df(n: int = 36) -> pd.DataFrame:
    """Create a synthetic observations DataFrame spanning ~1 year."""
    np.random.seed(42)
    dates = pd.date_range("2025-01-01", periods=n, freq="10D")
    ndvi_base = 0.3 + 0.25 * np.sin(np.linspace(0, 2 * np.pi, n))
    ndvi = ndvi_base + np.random.normal(0, 0.03, n)
    return pd.DataFrame({"date": dates, "ndvi": ndvi})


def _make_observations_with_evi(n: int = 24) -> pd.DataFrame:
    """Observations DataFrame with both NDVI and EVI columns."""
    np.random.seed(7)
    dates = pd.date_range("2025-01-01", periods=n, freq="15D")
    ndvi = 0.4 + 0.1 * np.sin(np.linspace(0, 2 * np.pi, n))
    evi = 0.35 + 0.08 * np.sin(np.linspace(0, 2 * np.pi, n))
    return pd.DataFrame({"date": dates, "ndvi": ndvi, "evi": evi})


# ════════════════════════════════════════════════════════════
# 1. ReportVisualizations tests
# ════════════════════════════════════════════════════════════


class TestVisualizationNDVITimeseries:
    """Test NDVI time-series chart generation."""

    def test_basic_output(self):
        viz = ReportVisualizations()
        df = _make_observations_df(20)
        buf = viz.create_ndvi_timeseries(df)
        assert isinstance(buf, BytesIO)
        data = buf.read()
        assert len(data) > 1000  # Non-trivial PNG
        assert data[:4] == b"\x89PNG"  # PNG magic bytes

    def test_with_evi(self):
        viz = ReportVisualizations()
        df = _make_observations_with_evi()
        buf = viz.create_ndvi_timeseries(df)
        assert isinstance(buf, BytesIO)
        assert buf.read()[:4] == b"\x89PNG"

    def test_without_trend(self):
        viz = ReportVisualizations()
        df = _make_observations_df(10)
        buf = viz.create_ndvi_timeseries(df, show_trend=False)
        assert isinstance(buf, BytesIO)
        assert buf.read()[:4] == b"\x89PNG"

    def test_without_smooth(self):
        viz = ReportVisualizations()
        df = _make_observations_df(10)
        buf = viz.create_ndvi_timeseries(df, show_smooth=False)
        assert isinstance(buf, BytesIO)

    def test_custom_title(self):
        viz = ReportVisualizations()
        df = _make_observations_df(10)
        buf = viz.create_ndvi_timeseries(df, title="Custom Title Here")
        assert isinstance(buf, BytesIO)

    def test_small_dataset(self):
        """Even 2 points should work (no smoothing)."""
        viz = ReportVisualizations()
        df = pd.DataFrame({
            "date": pd.date_range("2025-01-01", periods=2, freq="30D"),
            "ndvi": [0.3, 0.4],
        })
        buf = viz.create_ndvi_timeseries(df)
        assert isinstance(buf, BytesIO)
        assert buf.read()[:4] == b"\x89PNG"


class TestVisualizationSeasonalPattern:
    """Test seasonal pattern chart generation."""

    def test_basic_output(self):
        viz = ReportVisualizations()
        df = _make_observations_df(36)
        buf = viz.create_seasonal_pattern(df)
        assert isinstance(buf, BytesIO)
        assert buf.read()[:4] == b"\x89PNG"

    def test_single_month_data(self):
        """Should still render even if data covers only one month."""
        viz = ReportVisualizations()
        df = pd.DataFrame({
            "date": pd.date_range("2025-06-01", periods=5, freq="2D"),
            "ndvi": [0.5, 0.52, 0.48, 0.55, 0.51],
        })
        buf = viz.create_seasonal_pattern(df)
        assert isinstance(buf, BytesIO)

    def test_custom_title(self):
        viz = ReportVisualizations()
        df = _make_observations_df(12)
        buf = viz.create_seasonal_pattern(df, title="Test Seasonal")
        assert isinstance(buf, BytesIO)


class TestVisualizationVerificationSummary:
    """Test verification summary chart generation."""

    def test_with_flags(self):
        viz = ReportVisualizations()
        flags = [
            {"rule_id": "R1", "risk_level": "medium", "status": "flag"},
            {"rule_id": "R2", "risk_level": "critical", "status": "flag"},
            {"rule_id": "R3", "risk_level": "medium", "status": "flag"},
        ]
        buf = viz.create_verification_summary(flags)
        assert isinstance(buf, BytesIO)
        assert buf.read()[:4] == b"\x89PNG"

    def test_empty_list(self):
        """Empty list should render a 'no flags' message."""
        viz = ReportVisualizations()
        buf = viz.create_verification_summary([])
        assert isinstance(buf, BytesIO)
        assert buf.read()[:4] == b"\x89PNG"

    def test_single_risk_level(self):
        viz = ReportVisualizations()
        flags = [{"rule_id": "R1", "risk_level": "low", "status": "flag"}]
        buf = viz.create_verification_summary(flags)
        assert isinstance(buf, BytesIO)

    def test_all_risk_levels(self):
        viz = ReportVisualizations()
        flags = [
            {"rule_id": "R1", "risk_level": "critical", "status": "flag"},
            {"rule_id": "R2", "risk_level": "high", "status": "flag"},
            {"rule_id": "R3", "risk_level": "medium", "status": "flag"},
            {"rule_id": "R4", "risk_level": "low", "status": "flag"},
        ]
        buf = viz.create_verification_summary(flags)
        assert isinstance(buf, BytesIO)


class TestVisualizationConfidenceGauge:
    """Test confidence gauge chart generation."""

    def test_high_score(self):
        viz = ReportVisualizations()
        buf = viz.create_confidence_gauge(85.0)
        assert isinstance(buf, BytesIO)
        assert buf.read()[:4] == b"\x89PNG"

    def test_mid_score(self):
        viz = ReportVisualizations()
        buf = viz.create_confidence_gauge(55.0)
        assert isinstance(buf, BytesIO)

    def test_low_score(self):
        viz = ReportVisualizations()
        buf = viz.create_confidence_gauge(25.0)
        assert isinstance(buf, BytesIO)

    def test_boundary_zero(self):
        viz = ReportVisualizations()
        buf = viz.create_confidence_gauge(0.0)
        assert isinstance(buf, BytesIO)

    def test_boundary_hundred(self):
        viz = ReportVisualizations()
        buf = viz.create_confidence_gauge(100.0)
        assert isinstance(buf, BytesIO)

    def test_clamps_negative(self):
        viz = ReportVisualizations()
        buf = viz.create_confidence_gauge(-10.0)
        assert isinstance(buf, BytesIO)  # Should clamp to 0

    def test_clamps_above_hundred(self):
        viz = ReportVisualizations()
        buf = viz.create_confidence_gauge(110.0)
        assert isinstance(buf, BytesIO)  # Should clamp to 100

    def test_custom_title(self):
        viz = ReportVisualizations()
        buf = viz.create_confidence_gauge(75.0, title="My Gauge")
        assert isinstance(buf, BytesIO)


class TestVisualizationFeatureImportance:
    """Test feature importance chart generation."""

    def test_basic_output(self):
        viz = ReportVisualizations()
        features = [
            {"name": "ndvi_mean", "value": 0.52, "unit": "index"},
            {"name": "trend_slope", "value": 0.005, "unit": "index/day"},
            {"name": "biomass", "value": 45.2, "unit": "t/ha"},
        ]
        buf = viz.create_feature_importance(features)
        assert isinstance(buf, BytesIO)
        assert buf.read()[:4] == b"\x89PNG"

    def test_empty_features(self):
        viz = ReportVisualizations()
        buf = viz.create_feature_importance([])
        assert isinstance(buf, BytesIO)

    def test_negative_values(self):
        viz = ReportVisualizations()
        features = [
            {"name": "decline", "value": -0.05, "unit": "index/day"},
            {"name": "growth", "value": 0.03, "unit": "index/day"},
        ]
        buf = viz.create_feature_importance(features)
        assert isinstance(buf, BytesIO)

    def test_many_features_truncated(self):
        """More than max_features should be truncated."""
        viz = ReportVisualizations()
        features = [{"name": f"f{i}", "value": i * 0.1} for i in range(20)]
        buf = viz.create_feature_importance(features, max_features=5)
        assert isinstance(buf, BytesIO)


# ════════════════════════════════════════════════════════════
# 2. PDFReportGenerator tests
# ════════════════════════════════════════════════════════════


class TestPDFReportGeneratorInit:
    """Test generator initialization."""

    def test_default_init(self):
        gen = PDFReportGenerator()
        assert gen.page_size is not None
        assert gen.styles is not None
        assert gen._viz is not None

    def test_custom_styles_registered(self):
        gen = PDFReportGenerator()
        # Our custom styles should exist
        assert gen.styles["GeoTitle"] is not None
        assert gen.styles["GeoSubtitle"] is not None
        assert gen.styles["GeoHeading"] is not None
        assert gen.styles["GeoBody"] is not None
        assert gen.styles["GeoCaption"] is not None
        assert gen.styles["GeoFooter"] is not None


class TestPDFReportGeneratorSections:
    """Test individual section builders return valid ReportLab elements."""

    def setup_method(self):
        self.gen = PDFReportGenerator()
        self.pkg = _make_valid_package()

    def test_title_page(self):
        elements = self.gen._build_title_page(self.pkg)
        assert isinstance(elements, list)
        assert len(elements) >= 3  # Spacer + title + subtitle + spacer + table

    def test_executive_summary(self):
        elements = self.gen._build_executive_summary(self.pkg)
        assert isinstance(elements, list)
        assert len(elements) >= 3

    def test_data_sources(self):
        elements = self.gen._build_data_sources(self.pkg)
        assert isinstance(elements, list)
        assert len(elements) >= 2

    def test_data_sources_empty(self):
        pkg = _make_valid_package(data_sources=[])
        elements = self.gen._build_data_sources(pkg)
        assert isinstance(elements, list)
        assert len(elements) >= 2  # heading + "no data sources" text

    def test_analysis_results_with_features(self):
        elements = self.gen._build_analysis_results(self.pkg, None)
        assert isinstance(elements, list)
        assert len(elements) >= 2

    def test_analysis_results_with_observations(self):
        obs_df = _make_observations_df()
        elements = self.gen._build_analysis_results(self.pkg, obs_df)
        assert isinstance(elements, list)
        assert len(elements) >= 4  # heading + features table + charts

    def test_analysis_results_no_features(self):
        pkg = _make_valid_package(key_features=[])
        elements = self.gen._build_analysis_results(pkg, None)
        assert isinstance(elements, list)

    def test_verification_section(self):
        elements = self.gen._build_verification_section(self.pkg)
        assert isinstance(elements, list)
        assert len(elements) >= 3

    def test_verification_section_empty(self):
        pkg = _make_valid_package(verification_results=[])
        elements = self.gen._build_verification_section(pkg)
        assert isinstance(elements, list)
        assert len(elements) >= 2

    def test_lineage_section(self):
        elements = self.gen._build_lineage_section(self.pkg)
        assert isinstance(elements, list)
        assert len(elements) >= 3

    def test_lineage_section_empty(self):
        pkg = _make_valid_package(processing_chain=[])
        elements = self.gen._build_lineage_section(pkg)
        assert isinstance(elements, list)

    def test_appendix(self):
        elements = self.gen._build_appendix(self.pkg)
        assert isinstance(elements, list)
        assert len(elements) >= 2


class TestPDFReportGeneratorTableStyles:
    """Test table styling helpers."""

    def test_standard_style_commands(self):
        gen = PDFReportGenerator()
        cmds = gen._standard_table_style_commands(5)
        assert isinstance(cmds, list)
        assert len(cmds) > 0

    def test_standard_table_style(self):
        gen = PDFReportGenerator()
        style = gen._standard_table_style(3)
        assert style is not None

    def test_alternate_row_shading(self):
        gen = PDFReportGenerator()
        cmds = gen._standard_table_style_commands(6)
        # Should have BACKGROUND commands for even rows
        bg_cmds = [c for c in cmds if c[0] == "BACKGROUND" and c[1] != (0, 0)]
        assert len(bg_cmds) > 0  # At least one alt row


class TestPDFReportGeneratorFullReport:
    """Test full PDF report generation."""

    def test_generate_basic_report(self, tmp_path):
        gen = PDFReportGenerator()
        pkg = _make_valid_package()
        output = str(tmp_path / "test_report.pdf")
        result = gen.generate_report(pkg, output)
        assert os.path.exists(result)
        # Verify it's a real PDF
        with open(result, "rb") as f:
            header = f.read(5)
            assert header == b"%PDF-"
        assert os.path.getsize(result) > 5000  # Reasonable size

    def test_generate_report_with_observations(self, tmp_path):
        gen = PDFReportGenerator()
        pkg = _make_valid_package()
        obs_df = _make_observations_df()
        output = str(tmp_path / "report_with_obs.pdf")
        result = gen.generate_report(pkg, output, observations_df=obs_df)
        assert os.path.exists(result)
        size = os.path.getsize(result)
        # Report with charts should be larger than without
        assert size > 10000

    def test_generate_report_with_evi(self, tmp_path):
        gen = PDFReportGenerator()
        pkg = _make_valid_package()
        obs_df = _make_observations_with_evi()
        output = str(tmp_path / "report_with_evi.pdf")
        result = gen.generate_report(pkg, output, observations_df=obs_df)
        assert os.path.exists(result)

    def test_generate_report_creates_output_dir(self, tmp_path):
        gen = PDFReportGenerator()
        pkg = _make_valid_package()
        output = str(tmp_path / "subdir" / "deep" / "report.pdf")
        result = gen.generate_report(pkg, output)
        assert os.path.exists(result)

    def test_generate_minimal_package(self, tmp_path):
        """Report from a near-empty package should not crash."""
        gen = PDFReportGenerator()
        pkg = EvidencePackage(
            package_id="pkg-min",
            project_id="proj-min",
            project_name="Minimal Project",
            analysis_period_start="2025-01-01",
            analysis_period_end="2025-12-31",
            generated_date="2026-03-01T12:00:00",
            data_sources=[],
            processing_chain=[],
            key_features=[],
            growth_classification="unknown",
            confidence_score=0.0,
            verification_results=[],
            analyst="test",
            methodology_version="1.0.0",
            data_quality_score=0.0,
        )
        output = str(tmp_path / "minimal_report.pdf")
        result = gen.generate_report(pkg, output)
        assert os.path.exists(result)
        with open(result, "rb") as f:
            assert f.read(5) == b"%PDF-"

    def test_generate_report_with_flags(self, tmp_path):
        """Package with multiple flag types."""
        gen = PDFReportGenerator()
        pkg = _make_valid_package(
            verification_results=[
                _make_verification_result(
                    rule_id="R1", status="flag", risk_level="critical",
                    rule_name="Abrupt NDVI Drop",
                ),
                _make_verification_result(
                    rule_id="R2", status="flag", risk_level="high",
                    rule_name="Low Observations",
                ),
                _make_verification_result(
                    rule_id="R3", status="flag", risk_level="medium",
                    rule_name="Seasonal Anomaly",
                ),
                _make_verification_result(
                    rule_id="R4", status="pass", risk_level="low",
                    rule_name="Data Quality Check",
                ),
            ],
            overall_status="REVIEW_REQUIRED",
            confidence_score=55.0,
        )
        output = str(tmp_path / "flagged_report.pdf")
        result = gen.generate_report(pkg, output)
        assert os.path.exists(result)

    def test_generate_report_low_confidence(self, tmp_path):
        """Low confidence FAIL report."""
        gen = PDFReportGenerator()
        pkg = _make_valid_package(
            confidence_score=20.0,
            overall_status="FAIL",
            growth_classification="no_growth",
        )
        output = str(tmp_path / "fail_report.pdf")
        result = gen.generate_report(pkg, output)
        assert os.path.exists(result)

    def test_report_path_is_absolute(self, tmp_path):
        gen = PDFReportGenerator()
        pkg = _make_valid_package()
        output = str(tmp_path / "abs_test.pdf")
        result = gen.generate_report(pkg, output)
        assert os.path.isabs(result)

    def test_processing_step_with_error(self, tmp_path):
        """Steps with errors should render cleanly."""
        gen = PDFReportGenerator()
        pkg = _make_valid_package(
            processing_chain=[
                _make_processing_step(
                    1, operation="data_fetch", status="failed",
                    error_message="Timeout connecting to GEE",
                ),
                _make_processing_step(2, operation="retry_fetch", status="success"),
            ]
        )
        output = str(tmp_path / "error_step_report.pdf")
        result = gen.generate_report(pkg, output)
        assert os.path.exists(result)


# ════════════════════════════════════════════════════════════
# 3. Integration tests
# ════════════════════════════════════════════════════════════


class TestEndToEndIntegration:
    """Full pipeline: build package → generate charts → PDF report."""

    def test_full_pipeline(self, tmp_path):
        """End-to-end: evidence package → charts → PDF."""
        # 1. Build package
        pkg = _make_valid_package()

        # 2. Generate individual charts
        viz = ReportVisualizations()
        obs_df = _make_observations_df()
        ts_buf = viz.create_ndvi_timeseries(obs_df)
        seasonal_buf = viz.create_seasonal_pattern(obs_df)
        gauge_buf = viz.create_confidence_gauge(pkg.confidence_score)
        feat_buf = viz.create_feature_importance(
            [f.to_dict() for f in pkg.key_features]
        )

        # Charts are valid PNGs
        for buf in [ts_buf, seasonal_buf, gauge_buf, feat_buf]:
            buf.seek(0)
            assert buf.read(4) == b"\x89PNG"

        # 3. Generate PDF report
        gen = PDFReportGenerator()
        output = str(tmp_path / "integration_report.pdf")
        result = gen.generate_report(pkg, output, observations_df=obs_df)

        assert os.path.exists(result)
        size = os.path.getsize(result)
        assert size > 10000
        with open(result, "rb") as f:
            assert f.read(5) == b"%PDF-"

    def test_sealed_package_report(self, tmp_path):
        """Sealed package with checksum generates valid report."""
        pkg = _make_valid_package()
        pkg.seal()
        assert pkg.checksum is not None

        gen = PDFReportGenerator()
        output = str(tmp_path / "sealed_report.pdf")
        result = gen.generate_report(pkg, output)
        assert os.path.exists(result)

    def test_report_with_many_data_sources(self, tmp_path):
        """Multiple data sources render in a table."""
        sources = [
            _make_data_source(name="Sentinel-2", platform="ESA"),
            _make_data_source(
                name="Landsat 8", platform="USGS",
                collection="LANDSAT/LC08/C02/T1_L2",
                spatial_resolution_m=30.0,
            ),
            _make_data_source(
                name="MODIS", platform="NASA",
                collection="MODIS/006/MOD13Q1",
                spatial_resolution_m=250.0,
            ),
        ]
        pkg = _make_valid_package(data_sources=sources)
        gen = PDFReportGenerator()
        output = str(tmp_path / "multi_source_report.pdf")
        result = gen.generate_report(pkg, output)
        assert os.path.exists(result)

    def test_report_with_many_features(self, tmp_path):
        """Package with many features renders the feature chart."""
        features = [
            _make_feature(name=f"feature_{i}", value=i * 0.1, unit="unit")
            for i in range(15)
        ]
        pkg = _make_valid_package(key_features=features)
        gen = PDFReportGenerator()
        output = str(tmp_path / "many_features_report.pdf")
        result = gen.generate_report(pkg, output)
        assert os.path.exists(result)
