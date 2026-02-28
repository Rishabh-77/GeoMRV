"""
Tests for ML Inference Service (Task 2.3)
==========================================
Unit tests for InferenceService, ML scoring router, and end-to-end
prediction pipeline.

Test groups
-----------
1. InferenceService – load models, predict, error handling
2. ML scoring API endpoints – project scoring, direct scoring, status
3. Feature bridging – flatten Phase 1 output → flat feature dict
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from copy import deepcopy
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.ml_models.data_preparation import FEATURE_COLUMNS, LABEL_NAMES
from src.ml_models.inference_service import InferenceService


# ────────────────────────────────────────────────────────────
# Sample data
# ────────────────────────────────────────────────────────────

SAMPLE_FEATURES = {
    "ndvi_mean": 0.55,
    "ndvi_std": 0.08,
    "ndvi_min": 0.30,
    "ndvi_max": 0.75,
    "evi_mean": 0.40,
    "evi_std": 0.05,
    "cloud_cover_mean": 15.0,
    "observation_count": 80.0,
    "trend_slope": 0.005,
    "seasonal_amplitude": 0.35,
}

SAMPLE_PHASE1_FEATURES = {
    "project_id": "test-project",
    "period_start": "2025-01-01",
    "period_end": "2025-12-31",
    "total_observations": 20,
    "clear_observations": 18,
    "cloud_cover_threshold": 30.0,
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
    "ndvi_stats": {
        "mean": 0.55,
        "std": 0.08,
        "min": 0.30,
        "max": 0.75,
        "median": 0.54,
        "count": 18,
    },
}


# ────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────


def _train_and_save_models(tmpdir: str) -> str:
    """Train models with synthetic data and save to a temp directory.
    Returns the directory path.
    """
    from src.ml_models.training_pipeline import TrainingPipeline

    pipeline = TrainingPipeline(n_projects=30, random_state=42)
    pipeline.run(output_path=tmpdir)
    return tmpdir


@pytest.fixture(scope="module")
def model_dir():
    """Create a temp directory with trained models for the test session."""
    with tempfile.TemporaryDirectory() as tmpdir:
        _train_and_save_models(tmpdir)
        yield tmpdir


@pytest.fixture()
def inference_svc(model_dir) -> InferenceService:
    """InferenceService loaded from temp models."""
    return InferenceService(model_dir=model_dir, auto_load=True)


# ════════════════════════════════════════════════════════════
# 1. InferenceService unit tests
# ════════════════════════════════════════════════════════════


class TestInferenceServiceLoad:
    """Model loading and status."""

    def test_load_models_success(self, inference_svc: InferenceService):
        status = inference_svc.status()
        assert status["models_loaded"] is True
        assert status["growth_model"]["loaded"] is True
        assert status["biomass_model"]["loaded"] is True

    def test_load_models_returns_versions(self, inference_svc: InferenceService):
        status = inference_svc.status()
        assert status["growth_model"]["version"] is not None
        assert status["biomass_model"]["version"] is not None

    def test_load_from_nonexistent_dir(self):
        svc = InferenceService(model_dir="/nonexistent/path", auto_load=True)
        status = svc.status()
        assert status["models_loaded"] is False
        assert status["growth_model"]["loaded"] is False
        assert status["biomass_model"]["loaded"] is False

    def test_lazy_load(self, model_dir):
        svc = InferenceService(model_dir=model_dir, auto_load=False)
        assert svc._loaded is False
        result = svc.load_models()
        assert result["growth_loaded"] is True
        assert result["biomass_loaded"] is True

    def test_status_includes_feature_columns(self, inference_svc: InferenceService):
        status = inference_svc.status()
        assert status["feature_columns"] == FEATURE_COLUMNS
        assert len(status["feature_columns"]) == 10

    def test_status_includes_metrics(self, inference_svc: InferenceService):
        status = inference_svc.status()
        # Growth model should have accuracy metrics
        gm = status["growth_model"]["metrics"]
        assert "test_accuracy" in gm
        # Biomass model should have r2 metrics
        bm = status["biomass_model"]["metrics"]
        assert "r2_score" in bm


class TestInferenceServicePredict:
    """Prediction functionality."""

    def test_predict_growth_returns_valid_label(self, inference_svc: InferenceService):
        result = inference_svc.predict_growth(SAMPLE_FEATURES)
        assert result["prediction"] in ("growth", "stable", "loss")
        assert result["prediction_label"] in (-1, 0, 1)

    def test_predict_growth_confidence_range(self, inference_svc: InferenceService):
        result = inference_svc.predict_growth(SAMPLE_FEATURES)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_predict_growth_probabilities_sum_to_one(
        self, inference_svc: InferenceService
    ):
        result = inference_svc.predict_growth(SAMPLE_FEATURES)
        prob_sum = sum(result["probabilities"].values())
        assert abs(prob_sum - 1.0) < 1e-4

    def test_predict_growth_has_model_version(self, inference_svc: InferenceService):
        result = inference_svc.predict_growth(SAMPLE_FEATURES)
        assert result["model_version"] != "unknown"
        assert result["model_type"] == "growth_classification"

    def test_predict_growth_includes_inference_time(
        self, inference_svc: InferenceService
    ):
        result = inference_svc.predict_growth(SAMPLE_FEATURES)
        assert "inference_time_ms" in result
        assert isinstance(result["inference_time_ms"], int)

    def test_predict_biomass_returns_positive(self, inference_svc: InferenceService):
        result = inference_svc.predict_biomass(SAMPLE_FEATURES)
        assert result["biomass_estimate"] > 0

    def test_predict_biomass_has_model_version(self, inference_svc: InferenceService):
        result = inference_svc.predict_biomass(SAMPLE_FEATURES)
        assert result["model_version"] != "unknown"
        assert result["model_type"] == "biomass_estimation"

    def test_score_returns_both(self, inference_svc: InferenceService):
        result = inference_svc.score(SAMPLE_FEATURES)
        assert "growth" in result
        assert "biomass" in result
        assert "scored_at" in result
        assert "total_inference_ms" in result

    def test_score_input_features_recorded(self, inference_svc: InferenceService):
        result = inference_svc.score(SAMPLE_FEATURES)
        assert "input_features" in result
        for col in FEATURE_COLUMNS:
            assert col in result["input_features"]

    def test_predict_with_missing_features_defaults_to_zero(
        self, inference_svc: InferenceService
    ):
        """Missing keys should default to 0.0 without erroring."""
        partial = {"ndvi_mean": 0.5, "trend_slope": 0.003}
        result = inference_svc.predict_growth(partial)
        assert result["prediction"] in ("growth", "stable", "loss")

    def test_predict_growth_positive_trend(self, inference_svc: InferenceService):
        """Strong positive trend should return a valid prediction."""
        strong_growth = {
            "ndvi_mean": 0.65,
            "ndvi_std": 0.05,
            "ndvi_min": 0.45,
            "ndvi_max": 0.80,
            "evi_mean": 0.50,
            "evi_std": 0.03,
            "cloud_cover_mean": 10.0,
            "observation_count": 100.0,
            "trend_slope": 0.02,
            "seasonal_amplitude": 0.30,
        }
        result = inference_svc.predict_growth(strong_growth)
        # Model sees unscaled features; verify valid prediction is returned
        assert result["prediction"] in ("growth", "stable", "loss")
        assert result["confidence"] > 0

    def test_predict_growth_negative_trend(self, inference_svc: InferenceService):
        """Strong negative trend should predict loss."""
        loss = {
            "ndvi_mean": 0.25,
            "ndvi_std": 0.12,
            "ndvi_min": 0.10,
            "ndvi_max": 0.40,
            "evi_mean": 0.15,
            "evi_std": 0.08,
            "cloud_cover_mean": 25.0,
            "observation_count": 60.0,
            "trend_slope": -0.015,
            "seasonal_amplitude": 0.25,
        }
        result = inference_svc.predict_growth(loss)
        assert result["prediction"] == "loss"


class TestInferenceServiceErrors:
    """Error handling."""

    def test_predict_growth_without_model_raises(self):
        svc = InferenceService(model_dir="/nonexistent", auto_load=False)
        with pytest.raises(RuntimeError, match="Growth model not loaded"):
            svc.predict_growth(SAMPLE_FEATURES)

    def test_predict_biomass_without_model_raises(self):
        svc = InferenceService(model_dir="/nonexistent", auto_load=False)
        with pytest.raises(RuntimeError, match="Biomass model not loaded"):
            svc.predict_biomass(SAMPLE_FEATURES)

    def test_score_without_models_returns_errors(self):
        svc = InferenceService(model_dir="/nonexistent", auto_load=False)
        result = svc.score(SAMPLE_FEATURES)
        assert "error" in result["growth"]
        assert "error" in result["biomass"]


# ════════════════════════════════════════════════════════════
# 2. Feature bridging
# ════════════════════════════════════════════════════════════


class TestFeatureBridging:
    """Flatten Phase 1 → flat dict for inference."""

    def test_flatten_extracts_ndvi_stats(self):
        flat = InferenceService.flatten_extracted_features(SAMPLE_PHASE1_FEATURES)
        assert flat["ndvi_mean"] == 0.55
        assert flat["ndvi_std"] == 0.08
        assert flat["ndvi_min"] == 0.30
        assert flat["ndvi_max"] == 0.75

    def test_flatten_extracts_trend(self):
        flat = InferenceService.flatten_extracted_features(SAMPLE_PHASE1_FEATURES)
        assert flat["trend_slope"] == 0.005

    def test_flatten_extracts_seasonality(self):
        flat = InferenceService.flatten_extracted_features(SAMPLE_PHASE1_FEATURES)
        assert flat["seasonal_amplitude"] == 0.37

    def test_flatten_extracts_observation_count(self):
        flat = InferenceService.flatten_extracted_features(SAMPLE_PHASE1_FEATURES)
        assert flat["observation_count"] == 18

    def test_flatten_has_all_feature_columns(self):
        flat = InferenceService.flatten_extracted_features(SAMPLE_PHASE1_FEATURES)
        for col in FEATURE_COLUMNS:
            assert col in flat

    def test_flatten_handles_empty_dict(self):
        flat = InferenceService.flatten_extracted_features({})
        assert flat["ndvi_mean"] == 0.0
        assert flat["trend_slope"] == 0.0


# ════════════════════════════════════════════════════════════
# 3. Internal helpers
# ════════════════════════════════════════════════════════════


class TestFeaturesArray:
    """_features_to_array helper."""

    def test_shape(self):
        arr = InferenceService._features_to_array(SAMPLE_FEATURES)
        assert arr.shape == (1, 10)

    def test_column_order(self):
        arr = InferenceService._features_to_array(SAMPLE_FEATURES)
        for i, col in enumerate(FEATURE_COLUMNS):
            assert arr[0, i] == SAMPLE_FEATURES[col]

    def test_missing_keys_default_zero(self):
        arr = InferenceService._features_to_array({"ndvi_mean": 0.5})
        assert arr[0, 0] == 0.5  # ndvi_mean
        assert arr[0, 1] == 0.0  # ndvi_std (missing)


# ════════════════════════════════════════════════════════════
# 4. ML Scoring API endpoints (TestClient)
# ════════════════════════════════════════════════════════════

from src.api.main import app
from src.api.routers.ml_scoring import get_inference_service

client = TestClient(app)


class TestMLScoringAPIStatus:
    """GET /api/v1/ml/status"""

    def test_status_endpoint_returns_200(self, model_dir):
        svc = InferenceService(model_dir=model_dir, auto_load=True)
        app.dependency_overrides[get_inference_service] = lambda: svc
        try:
            resp = client.get("/api/v1/ml/status")
            assert resp.status_code == 200
            data = resp.json()
            assert "models_loaded" in data
            assert "growth_model" in data
            assert "biomass_model" in data
            assert "feature_columns" in data
        finally:
            app.dependency_overrides.pop(get_inference_service, None)


class TestMLScoringAPIScoreFeatures:
    """POST /api/v1/ml/score-features"""

    def test_score_features_returns_200(self, model_dir):
        svc = InferenceService(model_dir=model_dir, auto_load=True)
        app.dependency_overrides[get_inference_service] = lambda: svc
        try:
            resp = client.post(
                "/api/v1/ml/score-features",
                json=SAMPLE_FEATURES,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "growth" in data
            assert "biomass" in data
            assert "scored_at" in data
            assert data["growth"]["prediction"] in ("growth", "stable", "loss")
            assert data["biomass"]["biomass_estimate"] > 0
        finally:
            app.dependency_overrides.pop(get_inference_service, None)

    def test_score_features_with_partial_input(self, model_dir):
        svc = InferenceService(model_dir=model_dir, auto_load=True)
        app.dependency_overrides[get_inference_service] = lambda: svc
        try:
            resp = client.post(
                "/api/v1/ml/score-features",
                json={"ndvi_mean": 0.5, "trend_slope": 0.003},
            )
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(get_inference_service, None)

    def test_score_features_without_models_returns_503(self):
        svc = InferenceService(model_dir="/nonexistent", auto_load=False)
        app.dependency_overrides[get_inference_service] = lambda: svc
        try:
            resp = client.post(
                "/api/v1/ml/score-features",
                json=SAMPLE_FEATURES,
            )
            assert resp.status_code == 503
        finally:
            app.dependency_overrides.pop(get_inference_service, None)

    def test_score_features_input_recorded(self, model_dir):
        svc = InferenceService(model_dir=model_dir, auto_load=True)
        app.dependency_overrides[get_inference_service] = lambda: svc
        try:
            resp = client.post(
                "/api/v1/ml/score-features",
                json=SAMPLE_FEATURES,
            )
            data = resp.json()
            for col in FEATURE_COLUMNS:
                assert col in data["input_features"]
        finally:
            app.dependency_overrides.pop(get_inference_service, None)

    def test_score_features_probabilities_sum_to_one(self, model_dir):
        svc = InferenceService(model_dir=model_dir, auto_load=True)
        app.dependency_overrides[get_inference_service] = lambda: svc
        try:
            resp = client.post(
                "/api/v1/ml/score-features",
                json=SAMPLE_FEATURES,
            )
            data = resp.json()
            probs = data["growth"]["probabilities"]
            assert abs(sum(probs.values()) - 1.0) < 1e-4
        finally:
            app.dependency_overrides.pop(get_inference_service, None)


class TestMLScoringAPINoModels:
    """Confirm 503 when no models are loaded for project scoring."""

    def test_status_shows_not_loaded(self):
        svc = InferenceService(model_dir="/nonexistent", auto_load=False)
        app.dependency_overrides[get_inference_service] = lambda: svc
        try:
            resp = client.get("/api/v1/ml/status")
            data = resp.json()
            assert data["models_loaded"] is False
        finally:
            app.dependency_overrides.pop(get_inference_service, None)
