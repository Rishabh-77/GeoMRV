"""
GeoMRV Training Pipeline
=========================
End-to-end pipeline that generates data, trains both ML models, evaluates
them, and saves versioned artifacts to disk.

The pipeline can run from the command line::

    python -m src.ml_models.training_pipeline --output models/

Or be used programmatically::

    from src.ml_models.training_pipeline import TrainingPipeline

    pipeline = TrainingPipeline()
    results  = pipeline.run(output_path="models/")
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from src.ml_models.data_preparation import (
    FEATURE_COLUMNS,
    LABEL_NAMES,
    TrainingDataPreparator,
)
from src.ml_models.model_trainer import (
    BiomassEstimationModel,
    GrowthClassificationModel,
)
from src.ml_models.registry_service import RegistryService
from src.ml_models.synthetic_data_generator import (
    SyntheticDataGenerator,
    generate_synthetic_training_data,
)

logger = logging.getLogger(__name__)


class TrainingPipeline:
    """Orchestrate data generation → training → evaluation → save.

    Parameters
    ----------
    data_source : str
        ``"synthetic"`` (default) or ``"extracted"`` (Phase 1 DB output).
    n_projects : int
        Number of synthetic projects to generate.
    random_state : int
        Global seed for reproducibility.
    """

    def __init__(
        self,
        data_source: str = "synthetic",
        n_projects: int = 60,
        random_state: int = 42,
    ) -> None:
        self.data_source = data_source
        self.n_projects = n_projects
        self.random_state = random_state

        self.preparator = TrainingDataPreparator()
        self.growth_model = GrowthClassificationModel(random_state=random_state)
        self.biomass_model = BiomassEstimationModel(random_state=random_state)

    # ── public entry point ────────────────────────────────────

    def run(
        self,
        output_path: str = "models/",
        test_size: float = 0.2,
        register_models: bool = True,
        activate_registered_models: bool = True,
    ) -> Dict[str, Any]:
        """Run the full training pipeline.

        Steps
        -----
        1. Generate / load data
        2. Build feature matrix (X, y_growth)
        3. Compute synthetic biomass targets (y_biomass)
        4. Split train/test (stratified for classification)
        5. Train GrowthClassificationModel
        6. Train BiomassEstimationModel
        7. Save models + metadata + pipeline report
        8. Return summary dict

        Parameters
        ----------
        output_path : str
            Directory for model artifacts.
        test_size : float
            Fraction of data reserved for testing.
        register_models : bool
            If True, register saved model artifacts in ``model_registry``.
        activate_registered_models : bool
            If True, mark newly registered model versions as active.

        Returns
        -------
        dict with ``growth_metrics``, ``biomass_metrics``,
        ``data_quality``, ``saved_files``.
        """
        start_time = datetime.utcnow()
        logger.info("=== Training Pipeline started ===")

        # ── 1. Data ──────────────────────────────────────────
        projects = self._load_data()
        logger.info("Loaded %d projects (source=%s)", len(projects), self.data_source)

        # ── 2. Growth labels (X, y_growth) ───────────────────
        X_scaled, y_growth = self.preparator.create_training_dataset(projects)
        logger.info(
            "Feature matrix: %s, labels: %s",
            X_scaled.shape,
            dict(zip(*np.unique(y_growth, return_counts=True))),
        )

        # ── 3. Biomass targets ───────────────────────────────
        y_biomass = self._compute_biomass_targets(projects)

        # ── 4. Split ─────────────────────────────────────────
        X_train, X_test, yg_train, yg_test = self.preparator.split_dataset(
            X_scaled,
            y_growth,
            test_size=test_size,
            random_state=self.random_state,
        )
        # Biomass split uses same indices
        # Recreate split manually to keep alignment
        from sklearn.model_selection import train_test_split

        _, _, yb_train, yb_test = train_test_split(
            X_scaled,
            y_biomass,
            test_size=test_size,
            random_state=self.random_state,
            stratify=y_growth,  # keep same stratification
        )

        logger.info(
            "Split: train=%d, test=%d (%.0f%%)",
            X_train.shape[0],
            X_test.shape[0],
            test_size * 100,
        )

        # ── 5. Train growth classifier ───────────────────────
        growth_metrics = self.growth_model.train(
            X_train,
            yg_train,
            X_test,
            yg_test,
        )

        # ── 6. Train biomass regressor ───────────────────────
        biomass_metrics = self.biomass_model.train(
            X_train,
            yb_train,
            X_test,
            yb_test,
        )

        # ── 7. Save ──────────────────────────────────────────
        growth_files = self.growth_model.save(output_path)
        biomass_files = self.biomass_model.save(output_path)

        registry_result = {
            "registered": False,
            "activated": False,
            "growth_registry_id": None,
            "biomass_registry_id": None,
            "error": None,
        }
        if register_models:
            registry_result = self._register_saved_models(
                growth_files=growth_files,
                biomass_files=biomass_files,
                growth_metrics=growth_metrics,
                biomass_metrics=biomass_metrics,
                activate=activate_registered_models,
            )

        # Data quality report
        quality = self.preparator.data_quality_report(X_scaled, y_growth)

        # Pipeline summary
        elapsed_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        summary = {
            "pipeline_version": "1.0",
            "run_at": start_time.isoformat(),
            "elapsed_ms": elapsed_ms,
            "data_source": self.data_source,
            "n_projects": len(projects),
            "data_quality": quality,
            "growth_metrics": growth_metrics,
            "biomass_metrics": biomass_metrics,
            "saved_files": {**growth_files, **biomass_files},
            "registry": registry_result,
        }

        # Save pipeline report
        report_path = (
            Path(output_path) / f"pipeline_report_{self.growth_model.version}.json"
        )
        with open(report_path, "w") as f:
            json.dump(summary, f, indent=2, default=str)
        logger.info("Pipeline report → %s", report_path)

        logger.info(
            "=== Pipeline complete in %d ms — Growth acc %.3f, Biomass R² %.3f ===",
            elapsed_ms,
            growth_metrics.get("test_accuracy", 0),
            biomass_metrics.get("r2_score", 0),
        )
        return summary

    # ── private helpers ───────────────────────────────────────

    def _load_data(self):
        """Load or generate training data."""
        if self.data_source == "synthetic":
            return generate_synthetic_training_data(
                n_projects=self.n_projects,
                random_state=self.random_state,
            )
        else:
            raise NotImplementedError(
                f"Data source '{self.data_source}' not implemented yet.  "
                "Use 'synthetic' for MVP or add a DB loader."
            )

    @staticmethod
    def _compute_biomass_targets(projects) -> np.ndarray:
        """Derive continuous biomass proxy targets from project features.

        Uses a simple linear model:
            biomass = 50 × ndvi_mean + 30 × evi_mean + 5
        matching the placeholder coefficients in
        ``FeatureCalculator.calculate_biomass_proxy``.
        """
        targets = []
        for p in projects:
            f = p["features"]
            ndvi_mean = f.get("ndvi_mean", 0.0)
            evi_mean = f.get("evi_mean", 0.0)
            biomass = 50.0 * ndvi_mean + 30.0 * evi_mean + 5.0
            targets.append(biomass)
        return np.array(targets, dtype=np.float64)

    def _register_saved_models(
        self,
        growth_files: Dict[str, str],
        biomass_files: Dict[str, str],
        growth_metrics: Dict[str, Any],
        biomass_metrics: Dict[str, Any],
        activate: bool,
    ) -> Dict[str, Any]:
        """Register saved models in the model registry.

        This is best-effort: if DB/registry is unavailable, training still
        succeeds and registry status is returned with an error message.
        """
        try:
            from src.api.database import SessionLocal

            db = SessionLocal()
            try:
                registry = RegistryService(db)

                growth_entry = registry.register_model(
                    model_type=self.growth_model.MODEL_TYPE,
                    version=self.growth_model.version,
                    metrics=growth_metrics,
                    model_path=growth_files["model_path"],
                    metadata_path=growth_files.get("metadata_path"),
                )
                biomass_entry = registry.register_model(
                    model_type=self.biomass_model.MODEL_TYPE,
                    version=self.biomass_model.version,
                    metrics=biomass_metrics,
                    model_path=biomass_files["model_path"],
                    metadata_path=biomass_files.get("metadata_path"),
                )

                activated = False
                if activate:
                    registry.activate_model(growth_entry.id)
                    registry.activate_model(biomass_entry.id)
                    activated = True

                return {
                    "registered": True,
                    "activated": activated,
                    "growth_registry_id": growth_entry.id,
                    "biomass_registry_id": biomass_entry.id,
                    "error": None,
                }
            finally:
                db.close()
        except Exception as exc:
            logger.warning("Model registry integration skipped due to error: %s", exc)
            return {
                "registered": False,
                "activated": False,
                "growth_registry_id": None,
                "biomass_registry_id": None,
                "error": str(exc),
            }


# ──────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────


def main() -> None:
    """Command-line interface for the training pipeline."""
    parser = argparse.ArgumentParser(
        description="GeoMRV ML Training Pipeline",
    )
    parser.add_argument(
        "--output",
        default="models/",
        help="Directory for saved models (default: models/)",
    )
    parser.add_argument(
        "--n-projects",
        type=int,
        default=60,
        help="Number of synthetic projects (default: 60)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )

    pipeline = TrainingPipeline(
        n_projects=args.n_projects,
        random_state=args.seed,
    )
    results = pipeline.run(output_path=args.output)

    print("\n" + "=" * 60)
    print("GROWTH CLASSIFICATION")
    print(f"  Train accuracy : {results['growth_metrics']['train_accuracy']}")
    print(f"  Test accuracy  : {results['growth_metrics']['test_accuracy']}")
    print(
        f"  CV mean ± std  : {results['growth_metrics']['cv_mean']} ± {results['growth_metrics']['cv_std']}"
    )
    print()
    print("BIOMASS ESTIMATION")
    print(f"  R²    : {results['biomass_metrics']['r2_score']}")
    print(f"  RMSE  : {results['biomass_metrics']['rmse']}")
    print(f"  MAE   : {results['biomass_metrics']['mae']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
