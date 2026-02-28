"""
GeoMRV ML Inference Service
============================
Production-ready inference service that loads trained models and produces
growth classification and biomass estimation predictions.

The service:
- Discovers and loads the latest versioned model artifacts from disk
- Accepts raw or pre-scaled feature dictionaries
- Returns predictions with confidence scores and probability distributions
- Tracks model version metadata for audit lineage
- Handles missing-model and malformed-input errors gracefully

Usage
-----
    from src.ml_models.inference_service import InferenceService

    service = InferenceService(model_dir="models/")

    # Growth classification
    result = service.predict_growth({
        "ndvi_mean": 0.55, "ndvi_std": 0.08, "ndvi_min": 0.30,
        "ndvi_max": 0.75, "evi_mean": 0.40, "evi_std": 0.05,
        "cloud_cover_mean": 15.0, "observation_count": 80,
        "trend_slope": 0.005, "seasonal_amplitude": 0.35,
    })

    # Biomass estimation
    result = service.predict_biomass({...})

    # Full scoring (both models)
    result = service.score(features_dict)
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from src.ml_models.data_preparation import FEATURE_COLUMNS, LABEL_NAMES
from src.ml_models.model_trainer import (
    BiomassEstimationModel,
    GrowthClassificationModel,
)

logger = logging.getLogger(__name__)


class InferenceService:
    """Load trained models and serve predictions.

    Parameters
    ----------
    model_dir : str
        Path to the directory containing saved model ``.pkl`` and
        metadata ``.json`` files.
    auto_load : bool
        If ``True`` (default), attempt to load models immediately on
        construction.  Set to ``False`` for lazy loading.
    """

    def __init__(self, model_dir: str = "models/", auto_load: bool = True) -> None:
        self.model_dir = Path(model_dir)
        self.growth_model: Optional[GrowthClassificationModel] = None
        self.biomass_model: Optional[BiomassEstimationModel] = None
        self.growth_metadata: Dict[str, Any] = {}
        self.biomass_metadata: Dict[str, Any] = {}
        self._loaded = False

        if auto_load:
            self.load_models()

    # ── model loading ─────────────────────────────────────────

    def load_models(self) -> Dict[str, bool]:
        """Discover and load the latest model versions from disk.

        Returns
        -------
        dict  – ``{"growth_loaded": bool, "biomass_loaded": bool}``
        """
        status = {"growth_loaded": False, "biomass_loaded": False}

        if not self.model_dir.exists():
            logger.warning("Model directory does not exist: %s", self.model_dir)
            return status

        # ── Growth model ─────────────────────────────────────
        growth_files = sorted(self.model_dir.glob("growth_model_*.pkl"))
        if growth_files:
            latest = growth_files[-1]
            self.growth_model = GrowthClassificationModel()
            self.growth_model.load(str(latest))
            self.growth_metadata = self._load_metadata(
                latest, prefix="growth_model_", meta_prefix="growth_metadata_"
            )
            status["growth_loaded"] = True
            logger.info(
                "Growth model loaded: %s (v%s)",
                latest.name,
                self.growth_metadata.get("version", "unknown"),
            )

        # ── Biomass model ────────────────────────────────────
        biomass_files = sorted(self.model_dir.glob("biomass_model_*.pkl"))
        if biomass_files:
            latest = biomass_files[-1]
            self.biomass_model = BiomassEstimationModel()
            self.biomass_model.load(str(latest))
            self.biomass_metadata = self._load_metadata(
                latest, prefix="biomass_model_", meta_prefix="biomass_metadata_"
            )
            status["biomass_loaded"] = True
            logger.info(
                "Biomass model loaded: %s (v%s)",
                latest.name,
                self.biomass_metadata.get("version", "unknown"),
            )

        self._loaded = status["growth_loaded"] or status["biomass_loaded"]
        return status

    # ── predictions ───────────────────────────────────────────

    def predict_growth(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Predict growth classification from a flat feature dictionary.

        Parameters
        ----------
        features : dict
            Keys must include all of ``FEATURE_COLUMNS``.  Missing keys
            default to ``0.0``.

        Returns
        -------
        dict with ``prediction`` (str), ``prediction_label`` (int),
        ``confidence`` (float 0–1), ``probabilities`` (dict), and
        ``model_version`` (str).

        Raises
        ------
        RuntimeError
            If the growth model has not been loaded.
        """
        if self.growth_model is None:
            raise RuntimeError(
                "Growth model not loaded.  Ensure model files exist in "
                f"'{self.model_dir}' and call load_models()."
            )

        X = self._features_to_array(features)

        t0 = time.time()
        predictions, confidences = self.growth_model.predict(X)
        probabilities = self.growth_model.predict_proba(X)
        inference_ms = int((time.time() - t0) * 1000)

        prediction_int = int(predictions[0])
        confidence = float(confidences[0])

        # Map class indices to probability keys
        # The classifier's classes_ attribute tells us label ordering
        classes = self.growth_model.model.classes_
        prob_dict = {
            LABEL_NAMES.get(int(c), str(c)): round(float(p), 6)
            for c, p in zip(classes, probabilities[0])
        }

        return {
            "prediction": LABEL_NAMES.get(prediction_int, str(prediction_int)),
            "prediction_label": prediction_int,
            "confidence": round(confidence, 6),
            "probabilities": prob_dict,
            "model_version": self.growth_metadata.get("version", "unknown"),
            "model_type": "growth_classification",
            "inference_time_ms": inference_ms,
        }

    def predict_biomass(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Predict biomass proxy value from a flat feature dictionary.

        Parameters
        ----------
        features : dict
            Keys must include all of ``FEATURE_COLUMNS``.

        Returns
        -------
        dict with ``biomass_estimate`` (float), ``model_version`` (str),
        and ``inference_time_ms`` (int).

        Raises
        ------
        RuntimeError
            If the biomass model has not been loaded.
        """
        if self.biomass_model is None:
            raise RuntimeError(
                "Biomass model not loaded.  Ensure model files exist in "
                f"'{self.model_dir}' and call load_models()."
            )

        X = self._features_to_array(features)

        t0 = time.time()
        prediction = self.biomass_model.predict(X)
        inference_ms = int((time.time() - t0) * 1000)

        return {
            "biomass_estimate": round(float(prediction[0]), 4),
            "model_version": self.biomass_metadata.get("version", "unknown"),
            "model_type": "biomass_estimation",
            "inference_time_ms": inference_ms,
        }

    def score(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Run both models and return a combined scoring result.

        Parameters
        ----------
        features : dict
            Flat feature dictionary (same as ``predict_growth``).

        Returns
        -------
        dict with ``growth``, ``biomass``, ``input_features``,
        ``scored_at``, and ``feature_columns`` keys.
        """
        t0 = time.time()
        result: Dict[str, Any] = {
            "scored_at": datetime.utcnow().isoformat(),
            "feature_columns": FEATURE_COLUMNS,
            "input_features": {
                col: features.get(col, 0.0) for col in FEATURE_COLUMNS
            },
        }

        if self.growth_model is not None:
            result["growth"] = self.predict_growth(features)
        else:
            result["growth"] = {"error": "Growth model not loaded"}

        if self.biomass_model is not None:
            result["biomass"] = self.predict_biomass(features)
        else:
            result["biomass"] = {"error": "Biomass model not loaded"}

        result["total_inference_ms"] = int((time.time() - t0) * 1000)
        return result

    # ── feature bridging ──────────────────────────────────────

    @staticmethod
    def flatten_extracted_features(ef: Dict[str, Any]) -> Dict[str, float]:
        """Convert Phase 1 nested feature output into flat feature dict.

        This is a convenience wrapper around
        ``TrainingDataPreparator._flatten_extracted_features`` so that
        callers of the inference service do not need to import the
        data-preparation module.

        Parameters
        ----------
        ef : dict
            Full output of ``PipelineFeatureExtractor.extract_features``.

        Returns
        -------
        dict keyed by ``FEATURE_COLUMNS``.
        """
        from src.ml_models.data_preparation import TrainingDataPreparator

        return TrainingDataPreparator._flatten_extracted_features(ef)

    # ── status / introspection ────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """Return a summary of loaded models and their versions."""
        return {
            "models_loaded": self._loaded,
            "model_dir": str(self.model_dir),
            "growth_model": {
                "loaded": self.growth_model is not None,
                "version": self.growth_metadata.get("version"),
                "metrics": {
                    k: self.growth_metadata.get("metrics", {}).get(k)
                    for k in ("test_accuracy", "cv_mean", "cv_std")
                },
            },
            "biomass_model": {
                "loaded": self.biomass_model is not None,
                "version": self.biomass_metadata.get("version"),
                "metrics": {
                    k: self.biomass_metadata.get("metrics", {}).get(k)
                    for k in ("r2_score", "rmse", "mae")
                },
            },
            "feature_columns": FEATURE_COLUMNS,
        }

    # ── private helpers ───────────────────────────────────────

    @staticmethod
    def _features_to_array(features: Dict[str, Any]) -> np.ndarray:
        """Convert a flat feature dict to a 2-D numpy array (1 × n_features).

        Missing keys default to ``0.0``.
        """
        row = [float(features.get(col, 0.0)) for col in FEATURE_COLUMNS]
        return np.array([row], dtype=np.float64)

    @staticmethod
    def _load_metadata(
        model_path: Path,
        prefix: str,
        meta_prefix: str,
    ) -> Dict[str, Any]:
        """Attempt to load the JSON metadata sidecar for a model file."""
        meta_file = model_path.parent / model_path.name.replace(
            prefix, meta_prefix
        ).replace(".pkl", ".json")
        if meta_file.exists():
            with open(meta_file) as f:
                return json.load(f)
        return {}
