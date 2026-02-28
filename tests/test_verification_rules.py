"""
Tests for Verification Rules Engine (Task 1.5)
===============================================
Unit tests for the rules engine, rule store, and verification API
endpoints.
"""

from __future__ import annotations

import json
from copy import deepcopy
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.verification_rules.rules_engine import (
    RiskLevel,
    VerificationFlag,
    VerificationRulesEngine,
)

client = TestClient(app)

# ────────────────────────────────────────────────────────────
# Sample Feature Sets
# ────────────────────────────────────────────────────────────

HEALTHY_FEATURES = {
    "project_id": "00000000-0000-0000-0000-000000000001",
    "period_start": "2025-01-01",
    "period_end": "2025-12-31",
    "total_observations": 20,
    "clear_observations": 18,
    "cloud_cover_threshold": 30.0,
    "max_observation_gap_days": 30,
    "extracted_at": "2026-02-28T12:00:00",
    "trend": {
        "trend_slope": 0.005,
        "slope_per_year": 0.06,
        "r_squared": 0.85,
    },
    "seasonality": {
        "peak_month": 9,
        "trough_month": 3,
        "peak_ndvi": 0.72,
        "trough_ndvi": 0.35,
        "seasonal_amplitude": 0.37,
    },
    "growth_period": {
        "growth_start": "2025-04-15",
        "growth_end": "2025-10-15",
        "growth_days": 183,
        "ndvi_threshold": 0.45,
    },
    "anomalies": [],
    "ndvi_stats": {
        "mean": 0.52,
        "std": 0.10,
        "min": 0.30,
        "max": 0.72,
        "median": 0.51,
        "count": 18,
    },
    "biomass_stats": {
        "mean": 32.5,
        "std": 8.0,
        "min": 16.0,
        "max": 45.0,
    },
}

PROBLEMATIC_FEATURES = {
    "project_id": "00000000-0000-0000-0000-000000000002",
    "period_start": "2025-01-01",
    "period_end": "2025-12-31",
    "total_observations": 20,
    "clear_observations": 5,  # triggers R1
    "cloud_cover_threshold": 30.0,
    "max_observation_gap_days": 90,  # triggers R6
    "extracted_at": "2026-02-28T12:00:00",
    "trend": {
        "trend_slope": -0.003,  # triggers R3
        "slope_per_year": -0.036,
        "r_squared": 0.15,  # triggers R7
    },
    "seasonality": {
        "peak_month": 8,
        "trough_month": 2,
        "peak_ndvi": 0.75,
        "trough_ndvi": 0.10,
        "seasonal_amplitude": 0.65,
    },
    "growth_period": {
        "growth_start": "2025-05-01",
        "growth_end": "2025-09-01",
        "growth_days": 123,
        "ndvi_threshold": 0.40,
    },
    "anomalies": [
        "2025-03-15",
        "2025-06-20",
        "2025-08-10",
        "2025-11-05",
    ],  # triggers R4
    "ndvi_stats": {
        "mean": 0.38,
        "std": 0.22,
        "min": 0.10,  # < 0.2  \
        "max": 0.75,  # > 0.7   }  swing > 0.5 → triggers R5
        "median": 0.35,
        "count": 5,
    },
    "biomass_stats": {
        "mean": 20.0,
        "std": 12.0,
        "min": 5.0,
        "max": 40.0,
    },
}

SAMPLE_PROJECT = {
    "name": "Verification Test Project",
    "description": "Project for verification testing",
    "location_name": "Goa",
    "country": "India",
    "region": "Western Ghats",
    "total_area_ha": 100.0,
    "project_type": "forest",
    "start_date": "2025-01-01",
}


def _create_project(**overrides) -> dict:
    payload = {**SAMPLE_PROJECT, **overrides}
    resp = client.post("/api/v1/projects", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ────────────────────────────────────────────────────────────
# Tests — VerificationRulesEngine (unit)
# ────────────────────────────────────────────────────────────


class TestRulesEngine:
    """Unit tests for the VerificationRulesEngine class."""

    def setup_method(self):
        self.engine = VerificationRulesEngine()

    # ── Healthy features should produce no flags ──

    def test_healthy_features_no_flags(self):
        flags = self.engine.verify(HEALTHY_FEATURES)
        assert flags == [], f"Expected no flags, got {[f.rule_id for f in flags]}"

    def test_healthy_confidence_high(self):
        flags = self.engine.verify(HEALTHY_FEATURES)
        score = self.engine.get_confidence_score(HEALTHY_FEATURES, flags)
        assert score >= 70, f"Expected score ≥ 70, got {score}"

    def test_healthy_status_pass(self):
        flags = self.engine.verify(HEALTHY_FEATURES)
        score = self.engine.get_confidence_score(HEALTHY_FEATURES, flags)
        assert self.engine.get_overall_status(score) == "PASS"

    # ── R1: Insufficient observations ──

    def test_r1_insufficient_observations(self):
        features = deepcopy(HEALTHY_FEATURES)
        features["clear_observations"] = 5
        flags = self.engine.verify(features)
        rule_ids = [f.rule_id for f in flags]
        assert "R1_insufficient_data" in rule_ids

    def test_r1_not_triggered_at_threshold(self):
        features = deepcopy(HEALTHY_FEATURES)
        features["clear_observations"] = 12
        flags = self.engine.verify(features)
        rule_ids = [f.rule_id for f in flags]
        assert "R1_insufficient_data" not in rule_ids

    # ── R2: High cloud cover ──

    def test_r2_high_cloud_cover(self):
        features = deepcopy(HEALTHY_FEATURES)
        features["total_observations"] = 20
        features["clear_observations"] = 10  # 50% rejected
        flags = self.engine.verify(features)
        rule_ids = [f.rule_id for f in flags]
        assert "R2_high_cloud_cover" in rule_ids

    def test_r2_not_triggered_low_cloud(self):
        features = deepcopy(HEALTHY_FEATURES)
        features["total_observations"] = 20
        features["clear_observations"] = 18  # only 10% rejected
        flags = self.engine.verify(features)
        rule_ids = [f.rule_id for f in flags]
        assert "R2_high_cloud_cover" not in rule_ids

    # ── R3: No growth detected ──

    def test_r3_negative_trend(self):
        features = deepcopy(HEALTHY_FEATURES)
        features["trend"]["trend_slope"] = -0.002
        flags = self.engine.verify(features)
        rule_ids = [f.rule_id for f in flags]
        assert "R3_no_growth_detected" in rule_ids

    def test_r3_zero_trend(self):
        features = deepcopy(HEALTHY_FEATURES)
        features["trend"]["trend_slope"] = 0.0
        flags = self.engine.verify(features)
        rule_ids = [f.rule_id for f in flags]
        assert "R3_no_growth_detected" in rule_ids

    def test_r3_not_triggered_positive(self):
        flags = self.engine.verify(HEALTHY_FEATURES)
        rule_ids = [f.rule_id for f in flags]
        assert "R3_no_growth_detected" not in rule_ids

    # ── R4: Anomalous values ──

    def test_r4_anomalies_present(self):
        features = deepcopy(HEALTHY_FEATURES)
        features["anomalies"] = ["2025-07-15"]
        flags = self.engine.verify(features)
        rule_ids = [f.rule_id for f in flags]
        assert "R4_anomalous_spike" in rule_ids

    def test_r4_not_triggered_empty(self):
        flags = self.engine.verify(HEALTHY_FEATURES)
        rule_ids = [f.rule_id for f in flags]
        assert "R4_anomalous_spike" not in rule_ids

    # ── R5: Vegetation loss ──

    def test_r5_large_ndvi_swing(self):
        features = deepcopy(HEALTHY_FEATURES)
        features["ndvi_stats"]["min"] = 0.10
        features["ndvi_stats"]["max"] = 0.80
        flags = self.engine.verify(features)
        rule_ids = [f.rule_id for f in flags]
        assert "R5_forest_loss" in rule_ids

    def test_r5_not_triggered_normal_range(self):
        flags = self.engine.verify(HEALTHY_FEATURES)
        rule_ids = [f.rule_id for f in flags]
        assert "R5_forest_loss" not in rule_ids

    # ── R6: Data gap ──

    def test_r6_large_gap(self):
        features = deepcopy(HEALTHY_FEATURES)
        features["max_observation_gap_days"] = 90
        flags = self.engine.verify(features)
        rule_ids = [f.rule_id for f in flags]
        assert "R6_data_gap" in rule_ids

    def test_r6_not_triggered_small_gap(self):
        flags = self.engine.verify(HEALTHY_FEATURES)
        rule_ids = [f.rule_id for f in flags]
        assert "R6_data_gap" not in rule_ids

    # ── R7: Low trend confidence ──

    def test_r7_low_r_squared(self):
        features = deepcopy(HEALTHY_FEATURES)
        features["trend"]["r_squared"] = 0.15
        flags = self.engine.verify(features)
        rule_ids = [f.rule_id for f in flags]
        assert "R7_low_trend_confidence" in rule_ids

    def test_r7_not_triggered_good_r_squared(self):
        flags = self.engine.verify(HEALTHY_FEATURES)
        rule_ids = [f.rule_id for f in flags]
        assert "R7_low_trend_confidence" not in rule_ids

    # ── Problematic features trigger multiple rules ──

    def test_problematic_triggers_all_rules(self):
        flags = self.engine.verify(PROBLEMATIC_FEATURES)
        rule_ids = {f.rule_id for f in flags}
        expected = {
            "R1_insufficient_data",
            "R2_high_cloud_cover",
            "R3_no_growth_detected",
            "R4_anomalous_spike",
            "R5_forest_loss",
            "R6_data_gap",
            "R7_low_trend_confidence",
        }
        assert expected.issubset(rule_ids), f"Missing: {expected - rule_ids}"


class TestConfidenceScoring:
    """Unit tests for the confidence scoring algorithm."""

    def setup_method(self):
        self.engine = VerificationRulesEngine()

    def test_perfect_score(self):
        flags = self.engine.verify(HEALTHY_FEATURES)
        score = self.engine.get_confidence_score(HEALTHY_FEATURES, flags)
        assert score == 100.0

    def test_score_never_negative(self):
        flags = self.engine.verify(PROBLEMATIC_FEATURES)
        score = self.engine.get_confidence_score(PROBLEMATIC_FEATURES, flags)
        assert 0.0 <= score <= 100.0

    def test_critical_flag_heavy_penalty(self):
        features = deepcopy(HEALTHY_FEATURES)
        features["ndvi_stats"]["min"] = 0.05
        features["ndvi_stats"]["max"] = 0.80
        flags = self.engine.verify(features)
        score = self.engine.get_confidence_score(features, flags)
        assert score < 70  # should drop below PASS threshold

    def test_score_decreases_with_fewer_observations(self):
        features = deepcopy(HEALTHY_FEATURES)
        flags_full = self.engine.verify(features)
        score_full = self.engine.get_confidence_score(features, flags_full)

        features["clear_observations"] = 5
        flags_low = self.engine.verify(features)
        score_low = self.engine.get_confidence_score(features, flags_low)

        assert score_low < score_full


class TestOverallStatus:
    """Unit tests for status classification."""

    def setup_method(self):
        self.engine = VerificationRulesEngine()

    def test_pass_threshold(self):
        assert self.engine.get_overall_status(70.0) == "PASS"
        assert self.engine.get_overall_status(100.0) == "PASS"

    def test_review_threshold(self):
        assert self.engine.get_overall_status(69.9) == "REVIEW_REQUIRED"
        assert self.engine.get_overall_status(40.0) == "REVIEW_REQUIRED"

    def test_fail_threshold(self):
        assert self.engine.get_overall_status(39.9) == "FAIL"
        assert self.engine.get_overall_status(0.0) == "FAIL"


class TestVerificationFlagSerialization:
    """Test VerificationFlag.to_dict()."""

    def test_to_dict(self):
        flag = VerificationFlag(
            rule_id="R1_insufficient_data",
            rule_name="Insufficient Observations",
            risk_level=RiskLevel.MEDIUM,
            description="Only 5 observations",
            affected_period="2025-01-01 to 2025-12-31",
            recommended_action="Extend period",
        )
        d = flag.to_dict()
        assert d["risk_level"] == "medium"
        assert d["rule_id"] == "R1_insufficient_data"
        assert isinstance(d, dict)


# ────────────────────────────────────────────────────────────
# Tests — Verification API Endpoints
# ────────────────────────────────────────────────────────────


class TestVerifyEndpoint:
    """POST /api/v1/verification/{project_id}/verify"""

    @patch("src.api.routers.verification.PipelineFeatureExtractor")
    def test_verify_returns_pass(self, mock_extractor_class):
        """Verify endpoint returns PASS for healthy features."""
        project = _create_project(name="Verify Pass Test")

        mock_instance = MagicMock()
        mock_instance.extract_features.return_value = deepcopy(HEALTHY_FEATURES)
        mock_extractor_class.return_value = mock_instance

        resp = client.post(
            f"/api/v1/verification/{project['id']}/verify"
            "?start_date=2025-01-01&end_date=2025-12-31"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_status"] == "PASS"
        assert data["confidence_score"] >= 70
        assert data["flag_count"] == 0
        assert data["project_id"] == project["id"]

    @patch("src.api.routers.verification.PipelineFeatureExtractor")
    def test_verify_returns_flags(self, mock_extractor_class):
        """Verify endpoint returns flags for problematic features."""
        project = _create_project(name="Verify Flags Test")

        mock_instance = MagicMock()
        mock_instance.extract_features.return_value = deepcopy(PROBLEMATIC_FEATURES)
        mock_extractor_class.return_value = mock_instance

        resp = client.post(
            f"/api/v1/verification/{project['id']}/verify"
            "?start_date=2025-01-01&end_date=2025-12-31"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["flag_count"] > 0
        assert data["overall_status"] in ("REVIEW_REQUIRED", "FAIL")
        rule_ids = [f["rule_id"] for f in data["verification_flags"]]
        assert "R3_no_growth_detected" in rule_ids

    @patch("src.api.routers.verification.PipelineFeatureExtractor")
    def test_verify_error_no_observations(self, mock_extractor_class):
        """Verify returns 422 when extractor signals no data."""
        project = _create_project(name="Verify No Data")

        mock_instance = MagicMock()
        mock_instance.extract_features.return_value = {
            "project_id": project["id"],
            "error": "no_observations",
        }
        mock_extractor_class.return_value = mock_instance

        resp = client.post(
            f"/api/v1/verification/{project['id']}/verify"
            "?start_date=2025-01-01&end_date=2025-12-31"
        )
        assert resp.status_code == 422

    def test_verify_nonexistent_project_returns_404(self):
        resp = client.post(
            "/api/v1/verification/00000000-0000-0000-0000-000000000099/verify"
            "?start_date=2025-01-01&end_date=2025-12-31"
        )
        assert resp.status_code == 404


class TestLatestVerificationEndpoint:
    """GET /api/v1/verification/{project_id}/latest"""

    @patch("src.api.routers.verification.PipelineFeatureExtractor")
    def test_latest_returns_result(self, mock_extractor_class):
        """After running verify, latest should return the result."""
        project = _create_project(name="Latest Verification")

        mock_instance = MagicMock()
        mock_instance.extract_features.return_value = deepcopy(HEALTHY_FEATURES)
        mock_extractor_class.return_value = mock_instance

        # Run verification first
        client.post(
            f"/api/v1/verification/{project['id']}/verify"
            "?start_date=2025-01-01&end_date=2025-12-31"
        )

        resp = client.get(f"/api/v1/verification/{project['id']}/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == project["id"]
        assert "verification" in data
        assert "confidence_score" in data["verification"]

    def test_latest_no_results_returns_404(self):
        project = _create_project(name="No Verification Yet")
        resp = client.get(f"/api/v1/verification/{project['id']}/latest")
        assert resp.status_code == 404


class TestVerificationHistoryEndpoint:
    """GET /api/v1/verification/{project_id}/history"""

    @patch("src.api.routers.verification.PipelineFeatureExtractor")
    def test_history_lists_runs(self, mock_extractor_class):
        """History should list all verification runs."""
        project = _create_project(name="Verification History")

        mock_instance = MagicMock()
        mock_instance.extract_features.return_value = deepcopy(HEALTHY_FEATURES)
        mock_extractor_class.return_value = mock_instance

        # Run verification twice
        client.post(
            f"/api/v1/verification/{project['id']}/verify"
            "?start_date=2025-01-01&end_date=2025-06-30"
        )
        client.post(
            f"/api/v1/verification/{project['id']}/verify"
            "?start_date=2025-07-01&end_date=2025-12-31"
        )

        resp = client.get(f"/api/v1/verification/{project['id']}/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 2

    def test_history_nonexistent_project(self):
        resp = client.get(
            "/api/v1/verification/00000000-0000-0000-0000-000000000099/history"
        )
        assert resp.status_code == 404
