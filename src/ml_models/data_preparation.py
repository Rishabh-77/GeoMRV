"""
GeoMRV Training Data Preparation
=================================
Prepare feature matrices for ML training from satellite observations.

This module converts raw observation DataFrames (or pre-extracted feature
dictionaries produced by ``PipelineFeatureExtractor``) into scaled numeric
matrices suitable for scikit-learn models.

Usage
-----
    from src.ml_models.data_preparation import TrainingDataPreparator

    preparator = TrainingDataPreparator()

    # From a raw observations DataFrame
    feature_row = preparator.prepare_feature_matrix(obs_df)

    # From a list of project feature dicts → (X, y)
    X, y = preparator.create_training_dataset(projects_features)

    # From pre-extracted feature dicts (Phase 1 output) → (X, y)
    X, y = preparator.create_training_dataset_from_extracted(extracted_features)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Feature column definitions (single source of truth)
# ──────────────────────────────────────────────────────────────

# These are the columns expected as model input.  Downstream modules
# (model_trainer, inference_service) import this list to guarantee
# consistent ordering.

FEATURE_COLUMNS: list[str] = [
    "ndvi_mean",
    "ndvi_std",
    "ndvi_min",
    "ndvi_max",
    "evi_mean",
    "evi_std",
    "cloud_cover_mean",
    "observation_count",
    "trend_slope",
    "seasonal_amplitude",
]

# Growth class labels
LABEL_GROWTH = 1
LABEL_STABLE = 0
LABEL_LOSS = -1

LABEL_NAMES: dict[int, str] = {
    LABEL_GROWTH: "growth",
    LABEL_STABLE: "stable",
    LABEL_LOSS: "loss",
}


class TrainingDataPreparator:
    """Prepare features for ML training.

    The class is stateful because it holds a fitted ``StandardScaler``
    instance.  Call ``create_training_dataset`` (which calls
    ``fit_transform``) *before* using ``transform_single`` at inference
    time.
    """

    def __init__(self) -> None:
        self.scaler = StandardScaler()
        self._is_fitted = False

    # ── from raw observations ─────────────────────────────────

    def prepare_feature_matrix(
        self,
        observations_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Convert a single project's observation DataFrame to a 1-row
        feature DataFrame.

        Parameters
        ----------
        observations_df : DataFrame
            Must contain columns ``date``, ``ndvi``.
            Optional columns: ``evi``, ``cloud_cover``.

        Returns
        -------
        1-row DataFrame with columns matching ``FEATURE_COLUMNS``.
        """
        obs = observations_df.copy()
        obs["date"] = pd.to_datetime(obs["date"])
        obs = obs.sort_values("date")

        features: Dict[str, Any] = {
            "ndvi_mean": float(obs["ndvi"].mean()),
            "ndvi_std": float(obs["ndvi"].std()) if len(obs) > 1 else 0.0,
            "ndvi_min": float(obs["ndvi"].min()),
            "ndvi_max": float(obs["ndvi"].max()),
            "evi_mean": float(obs["evi"].mean()) if "evi" in obs.columns else 0.0,
            "evi_std": (
                float(obs["evi"].std()) if "evi" in obs.columns and len(obs) > 1 else 0.0
            ),
            "cloud_cover_mean": (
                float(obs["cloud_cover"].mean()) if "cloud_cover" in obs.columns else 0.0
            ),
            "observation_count": len(obs),
        }

        # Trend slope via linear regression on NDVI
        x = np.arange(len(obs))
        y = obs["ndvi"].values
        mask = ~np.isnan(y)
        if mask.sum() >= 2:
            coeffs = np.polyfit(x[mask], y[mask], 1)
            features["trend_slope"] = float(coeffs[0])
        else:
            features["trend_slope"] = 0.0

        # Seasonal amplitude
        obs["month"] = obs["date"].dt.month
        monthly_mean = obs.groupby("month")["ndvi"].mean()
        if len(monthly_mean) > 0:
            features["seasonal_amplitude"] = float(
                monthly_mean.max() - monthly_mean.min()
            )
        else:
            features["seasonal_amplitude"] = 0.0

        return pd.DataFrame([features])[FEATURE_COLUMNS]

    # ── from raw observation list → (X, y) ────────────────────

    def create_training_dataset(
        self,
        projects_features: List[Dict[str, Any]],
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Build scaled feature matrix and label vector from a list of
        project dictionaries.

        Each element of *projects_features* must have:
        - ``features`` : dict with keys matching ``FEATURE_COLUMNS``
        - ``label``    : int  (1 = growth, 0 = stable, -1 = loss)
          *or* the label will be inferred from ``trend_slope``.

        Parameters
        ----------
        projects_features : list of dicts

        Returns
        -------
        (X_scaled, y) – numpy arrays ready for ``model.fit()``.
        """
        X_list: list[list[float]] = []
        y_list: list[int] = []

        for project in projects_features:
            fd = project["features"]
            row = [fd.get(col, 0.0) for col in FEATURE_COLUMNS]
            X_list.append(row)

            # Explicit label takes priority; fall back to trend heuristic
            if "label" in project:
                y_list.append(int(project["label"]))
            else:
                slope = fd.get("trend_slope", 0.0)
                y_list.append(
                    LABEL_GROWTH if slope > 0.001
                    else (LABEL_LOSS if slope < -0.001 else LABEL_STABLE)
                )

        X = np.array(X_list, dtype=np.float64)
        y = np.array(y_list, dtype=np.int32)

        X_scaled = self.scaler.fit_transform(X)
        self._is_fitted = True

        logger.info(
            "Training dataset prepared: %d samples, %d features, label distribution: %s",
            X.shape[0],
            X.shape[1],
            dict(zip(*np.unique(y, return_counts=True))),
        )
        return X_scaled, y

    # ── from Phase 1 extracted feature dicts ──────────────────

    def create_training_dataset_from_extracted(
        self,
        extracted_features: List[Dict[str, Any]],
        labels: Optional[List[int]] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Build (X, y) from the nested feature dictionaries produced by
        ``PipelineFeatureExtractor.extract_features``.

        This bridges Phase 1 output directly into Phase 2 training.

        Parameters
        ----------
        extracted_features : list of dicts
            Each dict is the full output of ``extract_features`` (contains
            nested keys like ``trend.trend_slope``, ``ndvi_stats.mean``, etc.).
        labels : list of int, optional
            Ground-truth labels aligned with *extracted_features*.  If
            ``None``, labels are inferred from trend slope.

        Returns
        -------
        (X_scaled, y) – numpy arrays.
        """
        projects: List[Dict[str, Any]] = []
        for i, ef in enumerate(extracted_features):
            flat = self._flatten_extracted_features(ef)
            label = labels[i] if labels is not None else None
            entry: Dict[str, Any] = {"features": flat}
            if label is not None:
                entry["label"] = label
            projects.append(entry)

        return self.create_training_dataset(projects)

    # ── transform at inference time ───────────────────────────

    def transform_single(self, features: Dict[str, Any]) -> np.ndarray:
        """Scale a single feature dict using the already-fitted scaler.

        Parameters
        ----------
        features : dict
            Keys matching ``FEATURE_COLUMNS``.

        Returns
        -------
        1-D numpy array (scaled features).

        Raises
        ------
        RuntimeError
            If the scaler has not been fitted yet.
        """
        if not self._is_fitted:
            raise RuntimeError(
                "Scaler has not been fitted.  Call create_training_dataset first."
            )
        row = np.array(
            [[features.get(col, 0.0) for col in FEATURE_COLUMNS]],
            dtype=np.float64,
        )
        return self.scaler.transform(row).flatten()

    # ── train/test split helper ───────────────────────────────

    @staticmethod
    def split_dataset(
        X: np.ndarray,
        y: np.ndarray,
        test_size: float = 0.2,
        random_state: int = 42,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Stratified train/test split.

        Returns
        -------
        (X_train, X_test, y_train, y_test)
        """
        return train_test_split(
            X, y,
            test_size=test_size,
            random_state=random_state,
            stratify=y,
        )

    # ── quality report ────────────────────────────────────────

    @staticmethod
    def data_quality_report(
        X: np.ndarray,
        y: np.ndarray,
        feature_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Return a summary dict describing the training data quality.

        Useful for documentation and auditing.
        """
        if feature_names is None:
            feature_names = FEATURE_COLUMNS

        unique_labels, counts = np.unique(y, return_counts=True)
        label_dist = {
            LABEL_NAMES.get(int(lbl), str(lbl)): int(cnt)
            for lbl, cnt in zip(unique_labels, counts)
        }

        report: Dict[str, Any] = {
            "n_samples": int(X.shape[0]),
            "n_features": int(X.shape[1]),
            "feature_names": feature_names,
            "label_distribution": label_dist,
            "has_nan": bool(np.isnan(X).any()),
            "has_inf": bool(np.isinf(X).any()),
        }

        # Per-feature stats (on unscaled data is more informative, but
        # this works for a quick sanity check)
        for i, name in enumerate(feature_names):
            col = X[:, i]
            report[f"feature_{name}_mean"] = round(float(np.nanmean(col)), 6)
            report[f"feature_{name}_std"] = round(float(np.nanstd(col)), 6)

        return report

    # ── private helpers ───────────────────────────────────────

    @staticmethod
    def _flatten_extracted_features(ef: Dict[str, Any]) -> Dict[str, float]:
        """Flatten the nested Phase 1 feature dict into a flat dict keyed
        by ``FEATURE_COLUMNS``.

        Mapping:
            trend.trend_slope        → trend_slope
            seasonality.seasonal_amplitude → seasonal_amplitude
            ndvi_stats.mean          → ndvi_mean
            ndvi_stats.std           → ndvi_std
            ndvi_stats.min           → ndvi_min
            ndvi_stats.max           → ndvi_max
            (evi stats not in Phase 1 output; default to 0)
        """
        trend = ef.get("trend", {})
        season = ef.get("seasonality", {})
        stats = ef.get("ndvi_stats", {})

        return {
            "ndvi_mean": stats.get("mean", 0.0),
            "ndvi_std": stats.get("std", 0.0),
            "ndvi_min": stats.get("min", 0.0),
            "ndvi_max": stats.get("max", 0.0),
            "evi_mean": 0.0,  # not in Phase 1 feature output
            "evi_std": 0.0,
            "cloud_cover_mean": ef.get("cloud_cover_threshold", 0.0),
            "observation_count": ef.get("clear_observations", 0),
            "trend_slope": trend.get("trend_slope", 0.0) or 0.0,
            "seasonal_amplitude": season.get("seasonal_amplitude", 0.0),
        }
