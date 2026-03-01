"""
Tests for Evidence Package Schema & Validator (Task 3.1)
=========================================================
Comprehensive tests covering:
- DataSource, ProcessingStep, VerificationResult, Feature dataclasses
- EvidencePackage creation, serialisation, and round-trip
- Checksum computation and integrity verification
- Package validation (errors + warnings)
- Edge cases: empty packages, invalid values, critical flags
"""

from __future__ import annotations

import json
from copy import deepcopy

import pytest

from src.evidence_generation.package_schema import (
    DataSource,
    EvidencePackage,
    Feature,
    ProcessingStep,
    VerificationResult,
)
from src.evidence_generation.package_validator import (
    EvidencePackageValidator,
    ValidationReport,
)


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
            _make_feature(name="trend_slope", value=0.005, unit="index/day", source="calculation"),
            _make_feature(name="biomass_estimate", value=45.2, unit="t/ha", source="ml_model"),
        ],
        growth_classification="growth",
        confidence_score=85.0,
        verification_results=[
            _make_verification_result(rule_id="R1", status="pass"),
            _make_verification_result(rule_id="R2", status="pass"),
            _make_verification_result(rule_id="R3", status="pass"),
        ],
        analyst="GeoMRV Automated Pipeline",
        methodology_version="1.0.0",
        data_quality_score=92.5,
        overall_status="PASS",
        summary="Healthy growth detected over 12-month period.",
    )
    defaults.update(overrides)
    return EvidencePackage(**defaults)


# ════════════════════════════════════════════════════════════
# 1. DataSource tests
# ════════════════════════════════════════════════════════════


class TestDataSource:
    def test_create(self):
        ds = _make_data_source()
        assert ds.name == "Sentinel-2"
        assert ds.platform == "ESA"
        assert ds.spatial_resolution_m == 10.0

    def test_to_dict(self):
        ds = _make_data_source()
        d = ds.to_dict()
        assert isinstance(d, dict)
        assert d["name"] == "Sentinel-2"
        assert d["collection"] == "COPERNICUS/S2_SR_HARMONIZED"

    def test_from_dict(self):
        original = _make_data_source()
        restored = DataSource.from_dict(original.to_dict())
        assert restored.name == original.name
        assert restored.platform == original.platform

    def test_from_dict_extra_keys_ignored(self):
        data = _make_data_source().to_dict()
        data["extra_field"] = "should be ignored"
        ds = DataSource.from_dict(data)
        assert ds.name == "Sentinel-2"


# ════════════════════════════════════════════════════════════
# 2. ProcessingStep tests
# ════════════════════════════════════════════════════════════


class TestProcessingStep:
    def test_create(self):
        step = _make_processing_step(1)
        assert step.sequence == 1
        assert step.operation == "feature_extraction"
        assert step.status == "success"

    def test_to_dict(self):
        step = _make_processing_step(2, operation="ml_scoring")
        d = step.to_dict()
        assert d["sequence"] == 2
        assert d["operation"] == "ml_scoring"

    def test_from_dict_round_trip(self):
        original = _make_processing_step(3, operation="verification", duration_ms=120)
        restored = ProcessingStep.from_dict(original.to_dict())
        assert restored.sequence == original.sequence
        assert restored.duration_ms == 120

    def test_failed_step(self):
        step = _make_processing_step(
            1, status="failed", error_message="Timeout connecting to GEE"
        )
        assert step.status == "failed"
        assert "Timeout" in step.error_message


# ════════════════════════════════════════════════════════════
# 3. VerificationResult tests
# ════════════════════════════════════════════════════════════


class TestVerificationResult:
    def test_create(self):
        vr = _make_verification_result()
        assert vr.rule_id == "R1"
        assert vr.status == "pass"

    def test_to_dict(self):
        vr = _make_verification_result(status="flag", risk_level="high")
        d = vr.to_dict()
        assert d["status"] == "flag"
        assert d["risk_level"] == "high"

    def test_from_dict_round_trip(self):
        original = _make_verification_result(
            rule_id="R5", rule_name="Vegetation Loss",
            status="critical", risk_level="critical",
        )
        restored = VerificationResult.from_dict(original.to_dict())
        assert restored.rule_id == "R5"
        assert restored.status == "critical"

    def test_valid_statuses(self):
        assert "pass" in VerificationResult.VALID_STATUSES
        assert "flag" in VerificationResult.VALID_STATUSES
        assert "critical" in VerificationResult.VALID_STATUSES


# ════════════════════════════════════════════════════════════
# 4. Feature tests
# ════════════════════════════════════════════════════════════


class TestFeature:
    def test_create(self):
        f = _make_feature()
        assert f.name == "ndvi_mean"
        assert f.value == 0.52

    def test_to_dict(self):
        f = _make_feature(name="trend_slope", value=0.005, unit="index/day")
        d = f.to_dict()
        assert d["name"] == "trend_slope"
        assert d["unit"] == "index/day"

    def test_from_dict(self):
        original = _make_feature(source="ml_model")
        restored = Feature.from_dict(original.to_dict())
        assert restored.source == "ml_model"

    def test_valid_sources(self):
        assert "satellite_data" in Feature.VALID_SOURCES
        assert "ml_model" in Feature.VALID_SOURCES
        assert "calculation" in Feature.VALID_SOURCES
        assert "derived" in Feature.VALID_SOURCES


# ════════════════════════════════════════════════════════════
# 5. EvidencePackage — creation & properties
# ════════════════════════════════════════════════════════════


class TestEvidencePackageCreation:
    def test_create_valid_package(self):
        pkg = _make_valid_package()
        assert pkg.project_name == "Western Ghats Restoration - Test"
        assert pkg.confidence_score == 85.0
        assert pkg.growth_classification == "growth"

    def test_flag_count(self):
        pkg = _make_valid_package()
        assert pkg.flag_count == 0  # all pass

        pkg.verification_results.append(
            _make_verification_result(status="flag")
        )
        assert pkg.flag_count == 1

    def test_critical_flag_count(self):
        pkg = _make_valid_package()
        assert pkg.critical_flag_count == 0

        pkg.verification_results.append(
            _make_verification_result(status="critical", risk_level="critical")
        )
        assert pkg.critical_flag_count == 1

    def test_processing_step_count(self):
        pkg = _make_valid_package()
        assert pkg.processing_step_count == 4

    def test_has_ml_scoring(self):
        pkg = _make_valid_package()
        assert pkg.has_ml_scoring is True

        pkg2 = _make_valid_package(
            processing_chain=[_make_processing_step(1, operation="feature_extraction")]
        )
        assert pkg2.has_ml_scoring is False

    def test_has_verification(self):
        pkg = _make_valid_package()
        assert pkg.has_verification is True

        pkg2 = _make_valid_package(verification_results=[])
        assert pkg2.has_verification is False

    def test_get_feature_by_name(self):
        pkg = _make_valid_package()
        feat = pkg.get_feature_by_name("ndvi_mean")
        assert feat is not None
        assert feat.value == 0.52

        assert pkg.get_feature_by_name("nonexistent") is None

    def test_generate_id(self):
        id1 = EvidencePackage.generate_id()
        id2 = EvidencePackage.generate_id()
        assert id1 != id2
        assert len(id1) == 36  # UUID format

    def test_timestamp_now(self):
        ts = EvidencePackage.timestamp_now()
        assert "T" in ts  # ISO format

    def test_repr(self):
        pkg = _make_valid_package()
        r = repr(pkg)
        assert "Western Ghats" in r
        assert "PASS" in r


# ════════════════════════════════════════════════════════════
# 6. EvidencePackage — serialisation round-trip
# ════════════════════════════════════════════════════════════


class TestEvidencePackageSerialization:
    def test_to_dict(self):
        pkg = _make_valid_package()
        d = pkg.to_dict()
        assert isinstance(d, dict)
        assert d["project_name"] == "Western Ghats Restoration - Test"
        assert isinstance(d["data_sources"], list)
        assert isinstance(d["data_sources"][0], dict)

    def test_to_json(self):
        pkg = _make_valid_package()
        j = pkg.to_json()
        assert isinstance(j, str)
        parsed = json.loads(j)
        assert parsed["confidence_score"] == 85.0

    def test_to_json_compact(self):
        pkg = _make_valid_package()
        j_pretty = pkg.to_json(pretty=True)
        j_compact = pkg.to_json(pretty=False)
        assert len(j_compact) < len(j_pretty)

    def test_from_dict_round_trip(self):
        original = _make_valid_package()
        d = original.to_dict()
        restored = EvidencePackage.from_dict(d)
        assert restored.package_id == original.package_id
        assert restored.project_name == original.project_name
        assert restored.confidence_score == original.confidence_score
        assert len(restored.data_sources) == len(original.data_sources)
        assert restored.data_sources[0].name == original.data_sources[0].name
        assert len(restored.processing_chain) == len(original.processing_chain)
        assert len(restored.key_features) == len(original.key_features)
        assert len(restored.verification_results) == len(original.verification_results)

    def test_from_json_round_trip(self):
        original = _make_valid_package()
        json_str = original.to_json()
        restored = EvidencePackage.from_json(json_str)
        assert restored.package_id == original.package_id
        assert restored.growth_classification == original.growth_classification

    def test_from_dict_with_extra_keys(self):
        d = _make_valid_package().to_dict()
        d["unknown_extra_field"] = "should be ignored"
        pkg = EvidencePackage.from_dict(d)
        assert pkg.project_name == "Western Ghats Restoration - Test"


# ════════════════════════════════════════════════════════════
# 7. EvidencePackage — checksum & integrity
# ════════════════════════════════════════════════════════════


class TestEvidencePackageChecksum:
    def test_compute_checksum(self):
        pkg = _make_valid_package()
        checksum = pkg.compute_checksum()
        assert isinstance(checksum, str)
        assert len(checksum) == 64  # SHA-256 hex

    def test_seal_sets_checksum(self):
        pkg = _make_valid_package()
        assert pkg.checksum == ""
        pkg.seal()
        assert pkg.checksum != ""
        assert len(pkg.checksum) == 64

    def test_seal_returns_self(self):
        pkg = _make_valid_package()
        result = pkg.seal()
        assert result is pkg

    def test_verify_integrity_after_seal(self):
        pkg = _make_valid_package()
        pkg.seal()
        assert pkg.verify_integrity() is True

    def test_verify_integrity_fails_on_tamper(self):
        pkg = _make_valid_package()
        pkg.seal()
        pkg.confidence_score = 99.9  # tamper
        assert pkg.verify_integrity() is False

    def test_verify_integrity_false_when_no_checksum(self):
        pkg = _make_valid_package()
        assert pkg.verify_integrity() is False

    def test_checksum_deterministic(self):
        pkg1 = _make_valid_package()
        pkg2 = _make_valid_package()
        assert pkg1.compute_checksum() == pkg2.compute_checksum()

    def test_checksum_changes_with_content(self):
        pkg1 = _make_valid_package(confidence_score=85.0)
        pkg2 = _make_valid_package(confidence_score=90.0)
        assert pkg1.compute_checksum() != pkg2.compute_checksum()

    def test_round_trip_preserves_checksum(self):
        pkg = _make_valid_package()
        pkg.seal()
        json_str = pkg.to_json()
        restored = EvidencePackage.from_json(json_str)
        assert restored.checksum == pkg.checksum
        assert restored.verify_integrity() is True


# ════════════════════════════════════════════════════════════
# 8. ValidationReport tests
# ════════════════════════════════════════════════════════════


class TestValidationReport:
    def test_empty_report_is_valid(self):
        report = ValidationReport()
        assert report.is_valid is True
        assert report.total_issues == 0

    def test_report_with_errors_is_invalid(self):
        report = ValidationReport(errors=["Something wrong"])
        assert report.is_valid is False

    def test_report_with_only_warnings_is_valid(self):
        report = ValidationReport(warnings=["Minor issue"])
        assert report.is_valid is True

    def test_to_dict(self):
        report = ValidationReport(
            errors=["err1"], warnings=["warn1"],
            checked_at="2026-03-01T12:00:00",
            package_id="test-pkg",
        )
        d = report.to_dict()
        assert d["is_valid"] is False
        assert d["error_count"] == 1
        assert d["warning_count"] == 1


# ════════════════════════════════════════════════════════════
# 9. EvidencePackageValidator — valid package
# ════════════════════════════════════════════════════════════


class TestValidatorValidPackage:
    def setup_method(self):
        self.validator = EvidencePackageValidator()

    def test_valid_package_passes(self):
        pkg = _make_valid_package()
        report = self.validator.validate(pkg)
        assert report.is_valid is True
        assert len(report.errors) == 0

    def test_valid_package_report_has_package_id(self):
        pkg = _make_valid_package()
        report = self.validator.validate(pkg)
        assert report.package_id == pkg.package_id

    def test_valid_package_report_has_timestamp(self):
        pkg = _make_valid_package()
        report = self.validator.validate(pkg)
        assert report.checked_at != ""


# ════════════════════════════════════════════════════════════
# 10. EvidencePackageValidator — missing required fields
# ════════════════════════════════════════════════════════════


class TestValidatorMissingFields:
    def setup_method(self):
        self.validator = EvidencePackageValidator()

    def test_missing_package_id(self):
        pkg = _make_valid_package(package_id="")
        report = self.validator.validate(pkg)
        assert not report.is_valid
        assert any("package_id" in e for e in report.errors)

    def test_missing_project_id(self):
        pkg = _make_valid_package(project_id="")
        report = self.validator.validate(pkg)
        assert not report.is_valid
        assert any("project_id" in e for e in report.errors)

    def test_missing_project_name(self):
        pkg = _make_valid_package(project_name="")
        report = self.validator.validate(pkg)
        assert not report.is_valid
        assert any("project_name" in e for e in report.errors)

    def test_missing_analysis_period_start(self):
        pkg = _make_valid_package(analysis_period_start="")
        report = self.validator.validate(pkg)
        assert not report.is_valid
        assert any("analysis_period_start" in e for e in report.errors)

    def test_missing_analysis_period_end(self):
        pkg = _make_valid_package(analysis_period_end="")
        report = self.validator.validate(pkg)
        assert not report.is_valid
        assert any("analysis_period_end" in e for e in report.errors)


# ════════════════════════════════════════════════════════════
# 11. EvidencePackageValidator — data lineage
# ════════════════════════════════════════════════════════════


class TestValidatorDataLineage:
    def setup_method(self):
        self.validator = EvidencePackageValidator()

    def test_no_data_sources(self):
        pkg = _make_valid_package(data_sources=[])
        report = self.validator.validate(pkg)
        assert not report.is_valid
        assert any("data sources" in e.lower() for e in report.errors)

    def test_no_processing_chain(self):
        pkg = _make_valid_package(processing_chain=[])
        report = self.validator.validate(pkg)
        assert not report.is_valid
        assert any("processing" in e.lower() for e in report.errors)

    def test_data_source_missing_name(self):
        ds = _make_data_source(name="")
        pkg = _make_valid_package(data_sources=[ds])
        report = self.validator.validate(pkg)
        assert not report.is_valid
        assert any("missing name" in e for e in report.errors)

    def test_processing_step_missing_operation(self):
        step = _make_processing_step(1, operation="")
        pkg = _make_valid_package(processing_chain=[step])
        report = self.validator.validate(pkg)
        assert not report.is_valid
        assert any("missing operation" in e for e in report.errors)

    def test_out_of_order_sequence_warns(self):
        steps = [
            _make_processing_step(3, operation="verification"),
            _make_processing_step(1, operation="fetch"),
        ]
        pkg = _make_valid_package(processing_chain=steps)
        report = self.validator.validate(pkg)
        # Still valid (warning, not error)
        assert any("sequence order" in w for w in report.warnings)

    def test_failed_step_warns(self):
        steps = [_make_processing_step(1, status="failed", error_message="GEE timeout")]
        pkg = _make_valid_package(processing_chain=steps)
        report = self.validator.validate(pkg)
        assert any("failed" in w for w in report.warnings)


# ════════════════════════════════════════════════════════════
# 12. EvidencePackageValidator — findings
# ════════════════════════════════════════════════════════════


class TestValidatorFindings:
    def setup_method(self):
        self.validator = EvidencePackageValidator()

    def test_invalid_growth_classification(self):
        pkg = _make_valid_package(growth_classification="unknown")
        report = self.validator.validate(pkg)
        assert not report.is_valid
        assert any("growth_classification" in e for e in report.errors)

    def test_negative_confidence_score(self):
        pkg = _make_valid_package(confidence_score=-5.0)
        report = self.validator.validate(pkg)
        assert not report.is_valid
        assert any("confidence_score" in e for e in report.errors)

    def test_confidence_score_over_100(self):
        pkg = _make_valid_package(confidence_score=105.0)
        report = self.validator.validate(pkg)
        assert not report.is_valid

    def test_no_features_warns(self):
        pkg = _make_valid_package(key_features=[])
        report = self.validator.validate(pkg)
        # Valid but warns
        assert report.is_valid
        assert any("features" in w.lower() for w in report.warnings)

    def test_feature_missing_name_errors(self):
        feat = _make_feature(name="")
        pkg = _make_valid_package(key_features=[feat])
        report = self.validator.validate(pkg)
        assert not report.is_valid


# ════════════════════════════════════════════════════════════
# 13. EvidencePackageValidator — verification
# ════════════════════════════════════════════════════════════


class TestValidatorVerification:
    def setup_method(self):
        self.validator = EvidencePackageValidator()

    def test_no_verification_results_errors(self):
        pkg = _make_valid_package(verification_results=[])
        report = self.validator.validate(pkg)
        assert not report.is_valid
        assert any("verification" in e.lower() for e in report.errors)

    def test_critical_flags_warn(self):
        vrs = [
            _make_verification_result(rule_id="R5", status="critical", risk_level="critical"),
        ]
        pkg = _make_valid_package(verification_results=vrs)
        report = self.validator.validate(pkg)
        # Still valid (warning, not error)
        assert any("critical" in w.lower() for w in report.warnings)

    def test_missing_rule_id_errors(self):
        vr = _make_verification_result(rule_id="")
        pkg = _make_valid_package(verification_results=[vr])
        report = self.validator.validate(pkg)
        assert not report.is_valid


# ════════════════════════════════════════════════════════════
# 14. EvidencePackageValidator — metadata & quality
# ════════════════════════════════════════════════════════════


class TestValidatorMetadata:
    def setup_method(self):
        self.validator = EvidencePackageValidator()

    def test_invalid_overall_status(self):
        pkg = _make_valid_package(overall_status="UNKNOWN")
        report = self.validator.validate(pkg)
        assert not report.is_valid
        assert any("overall_status" in e for e in report.errors)

    def test_valid_statuses(self):
        for status in ["PASS", "REVIEW_REQUIRED", "FAIL"]:
            pkg = _make_valid_package(overall_status=status)
            report = self.validator.validate(pkg)
            assert report.is_valid, f"Status {status} should be valid"

    def test_negative_data_quality_score(self):
        pkg = _make_valid_package(data_quality_score=-1.0)
        report = self.validator.validate(pkg)
        assert not report.is_valid

    def test_data_quality_score_over_100(self):
        pkg = _make_valid_package(data_quality_score=101.0)
        report = self.validator.validate(pkg)
        assert not report.is_valid

    def test_zero_data_quality_warns(self):
        pkg = _make_valid_package(data_quality_score=0.0)
        report = self.validator.validate(pkg)
        assert report.is_valid  # warning only
        assert any("data_quality_score" in w for w in report.warnings)

    def test_short_analysis_period_warns(self):
        pkg = _make_valid_package(
            analysis_period_start="2025-01-01",
            analysis_period_end="2025-01-20",
        )
        report = self.validator.validate(pkg)
        assert report.is_valid
        assert any("days" in w for w in report.warnings)

    def test_end_before_start_errors(self):
        pkg = _make_valid_package(
            analysis_period_start="2025-12-31",
            analysis_period_end="2025-01-01",
        )
        report = self.validator.validate(pkg)
        assert not report.is_valid
        assert any("after" in e for e in report.errors)


# ════════════════════════════════════════════════════════════
# 15. EvidencePackageValidator — validate_and_raise
# ════════════════════════════════════════════════════════════


class TestValidateAndRaise:
    def setup_method(self):
        self.validator = EvidencePackageValidator()

    def test_valid_package_no_exception(self):
        pkg = _make_valid_package()
        report = self.validator.validate_and_raise(pkg)
        assert report.is_valid

    def test_invalid_package_raises(self):
        pkg = _make_valid_package(project_id="", package_id="")
        with pytest.raises(ValueError, match="validation failed"):
            self.validator.validate_and_raise(pkg)


# ════════════════════════════════════════════════════════════
# 16. Integration — full workflow
# ════════════════════════════════════════════════════════════


class TestFullWorkflow:
    """Simulate the complete evidence package lifecycle."""

    def test_create_validate_seal_verify(self):
        """Create → Validate → Seal → Serialise → Restore → Verify integrity."""
        # 1. Create
        pkg = EvidencePackage(
            package_id=EvidencePackage.generate_id(),
            project_id="proj-test-001",
            project_name="Integration Test Project",
            analysis_period_start="2025-01-01",
            analysis_period_end="2025-12-31",
            generated_date=EvidencePackage.timestamp_now(),
            data_sources=[
                DataSource(
                    name="Sentinel-2",
                    platform="ESA",
                    collection="COPERNICUS/S2_SR_HARMONIZED",
                    access_date="2026-02-15",
                    url="https://earthengine.google.com",
                ),
            ],
            processing_chain=[
                ProcessingStep(
                    sequence=1,
                    operation="satellite_data_fetch",
                    timestamp=EvidencePackage.timestamp_now(),
                    script_version="1.0.0",
                    parameters={"start_date": "2025-01-01", "end_date": "2025-12-31"},
                    inputs={"project_id": "proj-test-001"},
                    outputs={"observation_count": 48},
                    duration_ms=2500,
                    status="success",
                ),
                ProcessingStep(
                    sequence=2,
                    operation="feature_extraction",
                    timestamp=EvidencePackage.timestamp_now(),
                    script_version="1.0.0",
                    duration_ms=350,
                    status="success",
                ),
            ],
            key_features=[
                Feature(name="ndvi_mean", value=0.55, unit="index", source="satellite_data"),
                Feature(name="trend_slope", value=0.004, unit="index/day", source="calculation"),
            ],
            growth_classification="growth",
            confidence_score=82.0,
            verification_results=[
                VerificationResult(
                    rule_id="R1", rule_name="Insufficient Observations",
                    status="pass", risk_level="medium",
                    description="48 observations (threshold: 12)",
                    recommendation="No action required",
                ),
            ],
            data_quality_score=88.0,
            overall_status="PASS",
            summary="Positive growth trend detected.",
        )

        # 2. Validate
        validator = EvidencePackageValidator()
        report = validator.validate(pkg)
        assert report.is_valid, f"Validation errors: {report.errors}"

        # 3. Seal
        pkg.seal()
        assert pkg.checksum != ""

        # 4. Serialise
        json_str = pkg.to_json()
        assert len(json_str) > 100

        # 5. Restore
        restored = EvidencePackage.from_json(json_str)
        assert restored.project_name == "Integration Test Project"
        assert restored.confidence_score == 82.0

        # 6. Verify integrity
        assert restored.verify_integrity() is True

        # 7. Tampering detection
        restored.confidence_score = 99.0
        assert restored.verify_integrity() is False
