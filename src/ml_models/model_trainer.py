"""
GeoMRV Model Trainer
====================
Train and evaluate ML models for vegetation growth classification and
biomass estimation.

Two model classes are provided:

1. **GrowthClassificationModel** – Gradient Boosting classifier that
   predicts growth / stable / loss (labels 1, 0, −1).
2. **BiomassEstimationModel** – Random Forest regressor that predicts
   continuous biomass proxy values.

Both models support:
- Training with automatic train/test split
- Cross-validated evaluation metrics
- Feature importance extraction
- Versioned save / load via ``joblib`` + JSON metadata
- Reproducibility via fixed ``random_state``

Usage
-----
    from src.ml_models.model_trainer import (
        GrowthClassificationModel,
        BiomassEstimationModel,
    )

    # Classification
    clf = GrowthClassificationModel()
    metrics = clf.train(X_train, y_train, X_test, y_test)
    preds, conf = clf.predict(X_new)
    clf.save("models/")

    # Regression
    reg = BiomassEstimationModel()
    metrics = reg.train(X_train, y_train, X_test, y_test)
    preds = reg.predict(X_new)
    reg.save("models/")
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, RandomForestRegressor
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import cross_val_score

from src.ml_models.data_preparation import FEATURE_COLUMNS, LABEL_NAMES

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Growth Classification Model
# ──────────────────────────────────────────────────────────────


class GrowthClassificationModel:
    """Gradient Boosting classifier for growth / stable / loss.

    Parameters
    ----------
    n_estimators : int
        Number of boosting stages.
    learning_rate : float
        Shrinkage applied to each tree's contribution.
    max_depth : int
        Maximum depth of each tree.
    random_state : int
        Seed for reproducibility.
    """

    MODEL_TYPE = "growth_classification"

    def __init__(
        self,
        n_estimators: int = 100,
        learning_rate: float = 0.1,
        max_depth: int = 5,
        min_samples_split: int = 5,
        min_samples_leaf: int = 2,
        random_state: int = 42,
    ) -> None:
        self.model = GradientBoostingClassifier(
            n_estimators=n_estimators,
            learning_rate=learning_rate,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            min_samples_leaf=min_samples_leaf,
            random_state=random_state,
        )
        self.version: str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self.metrics: Dict[str, Any] = {}
        self._is_trained = False

    # ── training ──────────────────────────────────────────────

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
        cv_folds: int = 5,
    ) -> Dict[str, Any]:
        """Train the classifier and compute evaluation metrics.

        Parameters
        ----------
        X_train, y_train : array-like
            Training split (already scaled).
        X_test, y_test : array-like
            Test split (already scaled).
        cv_folds : int
            Number of cross-validation folds on full training set.

        Returns
        -------
        dict – all evaluation metrics.
        """
        self.model.fit(X_train, y_train)
        self._is_trained = True

        y_pred = self.model.predict(X_test)

        # Cross-validation on train set
        cv_scores = cross_val_score(
            self.model, X_train, y_train, cv=min(cv_folds, len(np.unique(y_train)))
        )

        self.metrics = {
            "model_type": self.MODEL_TYPE,
            "version": self.version,
            "n_train": int(X_train.shape[0]),
            "n_test": int(X_test.shape[0]),
            "n_features": int(X_train.shape[1]),
            "feature_names": FEATURE_COLUMNS,
            "train_accuracy": round(float(self.model.score(X_train, y_train)), 4),
            "test_accuracy": round(float(self.model.score(X_test, y_test)), 4),
            "cv_mean": round(float(cv_scores.mean()), 4),
            "cv_std": round(float(cv_scores.std()), 4),
            "cv_scores": [round(float(s), 4) for s in cv_scores],
            "classification_report": classification_report(
                y_test,
                y_pred,
                output_dict=True,
                zero_division=0,
            ),
            "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
            "feature_importance": {
                name: round(float(imp), 6)
                for name, imp in zip(FEATURE_COLUMNS, self.model.feature_importances_)
            },
        }

        logger.info(
            "Growth model v%s trained — test acc %.3f, CV mean %.3f ± %.3f",
            self.version,
            self.metrics["test_accuracy"],
            self.metrics["cv_mean"],
            self.metrics["cv_std"],
        )
        return self.metrics

    # ── prediction ────────────────────────────────────────────

    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Predict class labels and per-sample confidence.

        Returns
        -------
        (predictions, confidences) – int array of labels and float array
        of max-probability values.
        """
        if not self._is_trained:
            raise RuntimeError("Model has not been trained or loaded.")
        predictions = self.model.predict(X)
        probabilities = self.model.predict_proba(X)
        confidences = probabilities.max(axis=1)
        return predictions, confidences

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Return full probability distribution over classes."""
        if not self._is_trained:
            raise RuntimeError("Model has not been trained or loaded.")
        return self.model.predict_proba(X)

    # ── persistence ───────────────────────────────────────────

    def save(self, directory: str) -> Dict[str, str]:
        """Save model and metadata to *directory*.

        Returns dict with ``model_path`` and ``metadata_path``.
        """
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)

        model_file = path / f"growth_model_{self.version}.pkl"
        meta_file = path / f"growth_metadata_{self.version}.json"

        joblib.dump(self.model, model_file)

        metadata = {
            "version": self.version,
            "model_type": self.MODEL_TYPE,
            "created_at": datetime.utcnow().isoformat(),
            "metrics": self.metrics,
            "feature_names": FEATURE_COLUMNS,
            "sklearn_params": self.model.get_params(),
        }
        with open(meta_file, "w") as f:
            json.dump(metadata, f, indent=2, default=str)

        logger.info("Growth model saved → %s", model_file)
        return {"model_path": str(model_file), "metadata_path": str(meta_file)}

    def load(self, model_path: str) -> None:
        """Load a previously saved model from *model_path*."""
        self.model = joblib.load(model_path)
        self._is_trained = True

        # Try loading metadata from sibling file
        p = Path(model_path)
        meta_file = p.parent / p.name.replace(
            "growth_model_", "growth_metadata_"
        ).replace(".pkl", ".json")
        if meta_file.exists():
            with open(meta_file) as f:
                data = json.load(f)
            self.version = data.get("version", self.version)
            self.metrics = data.get("metrics", {})

        logger.info("Growth model loaded from %s (v%s)", model_path, self.version)


# ──────────────────────────────────────────────────────────────
# Biomass Estimation Model
# ──────────────────────────────────────────────────────────────


class BiomassEstimationModel:
    """Random Forest regressor for continuous biomass proxy estimation.

    Parameters
    ----------
    n_estimators : int
        Number of trees in the forest.
    max_depth : int
        Maximum depth of each tree.
    random_state : int
        Seed for reproducibility.
    """

    MODEL_TYPE = "biomass_estimation"

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 10,
        min_samples_split: int = 5,
        random_state: int = 42,
    ) -> None:
        self.model = RandomForestRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            random_state=random_state,
        )
        self.version: str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self.metrics: Dict[str, Any] = {}
        self._is_trained = False

    # ── training ──────────────────────────────────────────────

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
        cv_folds: int = 5,
    ) -> Dict[str, Any]:
        """Train the regressor and compute evaluation metrics.

        Parameters
        ----------
        X_train, y_train : array-like
            Training split (features + continuous biomass targets).
        X_test, y_test : array-like
            Test split.
        cv_folds : int
            Number of cross-validation folds.

        Returns
        -------
        dict – all evaluation metrics.
        """
        self.model.fit(X_train, y_train)
        self._is_trained = True

        y_pred = self.model.predict(X_test)

        cv_scores = cross_val_score(self.model, X_train, y_train, cv=cv_folds)

        self.metrics = {
            "model_type": self.MODEL_TYPE,
            "version": self.version,
            "n_train": int(X_train.shape[0]),
            "n_test": int(X_test.shape[0]),
            "n_features": int(X_train.shape[1]),
            "feature_names": FEATURE_COLUMNS,
            "r2_score": round(float(r2_score(y_test, y_pred)), 4),
            "rmse": round(float(np.sqrt(mean_squared_error(y_test, y_pred))), 4),
            "mae": round(float(mean_absolute_error(y_test, y_pred)), 4),
            "cv_mean": round(float(cv_scores.mean()), 4),
            "cv_std": round(float(cv_scores.std()), 4),
            "cv_scores": [round(float(s), 4) for s in cv_scores],
            "feature_importance": {
                name: round(float(imp), 6)
                for name, imp in zip(FEATURE_COLUMNS, self.model.feature_importances_)
            },
        }

        logger.info(
            "Biomass model v%s trained — R² %.3f, RMSE %.3f, MAE %.3f",
            self.version,
            self.metrics["r2_score"],
            self.metrics["rmse"],
            self.metrics["mae"],
        )
        return self.metrics

    # ── prediction ────────────────────────────────────────────

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict continuous biomass values."""
        if not self._is_trained:
            raise RuntimeError("Model has not been trained or loaded.")
        return self.model.predict(X)

    # ── persistence ───────────────────────────────────────────

    def save(self, directory: str) -> Dict[str, str]:
        """Save model and metadata to *directory*."""
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)

        model_file = path / f"biomass_model_{self.version}.pkl"
        meta_file = path / f"biomass_metadata_{self.version}.json"

        joblib.dump(self.model, model_file)

        metadata = {
            "version": self.version,
            "model_type": self.MODEL_TYPE,
            "created_at": datetime.utcnow().isoformat(),
            "metrics": self.metrics,
            "feature_names": FEATURE_COLUMNS,
            "sklearn_params": self.model.get_params(),
        }
        with open(meta_file, "w") as f:
            json.dump(metadata, f, indent=2, default=str)

        logger.info("Biomass model saved → %s", model_file)
        return {"model_path": str(model_file), "metadata_path": str(meta_file)}

    def load(self, model_path: str) -> None:
        """Load a previously saved model from *model_path*."""
        self.model = joblib.load(model_path)
        self._is_trained = True

        p = Path(model_path)
        meta_file = p.parent / p.name.replace(
            "biomass_model_", "biomass_metadata_"
        ).replace(".pkl", ".json")
        if meta_file.exists():
            with open(meta_file) as f:
                data = json.load(f)
            self.version = data.get("version", self.version)
            self.metrics = data.get("metrics", {})

        logger.info("Biomass model loaded from %s (v%s)", model_path, self.version)
