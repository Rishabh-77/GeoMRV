"""
GeoMRV ML Scoring Router
=========================
Endpoints for running ML inference on project features, retrieving
prediction results, and checking model status.

Endpoints
---------
- ``POST /api/v1/ml/score/{project_id}``  – score a project
- ``POST /api/v1/ml/score-features``       – score raw features directly
- ``GET  /api/v1/ml/status``               – model health & versions
- ``GET  /api/v1/ml/{project_id}/latest``  – latest scoring result
- ``GET  /api/v1/ml/{project_id}/history`` – all scoring runs
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.database import get_db
from src.api.models import Job, Project
from src.feature_extraction.feature_calculator import PipelineFeatureExtractor
from src.feature_extraction.feature_store import FeatureStore
from src.ml_models.inference_service import InferenceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml", tags=["ml-scoring"])

# ──────────────────────────────────────────────────────────────
# Singleton inference service instance
# ──────────────────────────────────────────────────────────────

_inference_service: Optional[InferenceService] = None


def get_inference_service() -> InferenceService:
    """FastAPI dependency – lazily initialise the InferenceService."""
    global _inference_service
    if _inference_service is None:
        _inference_service = InferenceService(model_dir="models/", auto_load=True)
    return _inference_service


# ──────────────────────────────────────────────────────────────
# Pydantic schemas
# ──────────────────────────────────────────────────────────────


class FeatureInput(BaseModel):
    """Raw feature vector for direct scoring."""

    ndvi_mean: float = 0.0
    ndvi_std: float = 0.0
    ndvi_min: float = 0.0
    ndvi_max: float = 0.0
    evi_mean: float = 0.0
    evi_std: float = 0.0
    cloud_cover_mean: float = 0.0
    observation_count: float = 0.0
    trend_slope: float = 0.0
    seasonal_amplitude: float = 0.0


class GrowthPrediction(BaseModel):
    prediction: str
    prediction_label: int
    confidence: float
    probabilities: Dict[str, float]
    model_version: str
    model_type: str
    inference_time_ms: int


class BiomassPrediction(BaseModel):
    biomass_estimate: float
    model_version: str
    model_type: str
    inference_time_ms: int


class ScoringResponse(BaseModel):
    project_id: str
    processing_log_id: str
    scored_at: str
    growth: Optional[Dict[str, Any]] = None
    biomass: Optional[Dict[str, Any]] = None
    input_features: Dict[str, float]
    total_inference_ms: int


class DirectScoringResponse(BaseModel):
    scored_at: str
    growth: Optional[Dict[str, Any]] = None
    biomass: Optional[Dict[str, Any]] = None
    input_features: Dict[str, float]
    total_inference_ms: int


class ModelStatusResponse(BaseModel):
    models_loaded: bool
    model_dir: str
    growth_model: Dict[str, Any]
    biomass_model: Dict[str, Any]
    feature_columns: list[str]


# ──────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────

OPERATION_TYPE = "ml_scoring"


@router.post("/score/{project_id}", response_model=ScoringResponse)
def score_project(
    project_id: UUID,
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    svc: InferenceService = Depends(get_inference_service),
) -> dict:
    """Score a project using ML models.

    1. Extracts features for the given date range (or re-uses cached).
    2. Flattens features into the model's expected input format.
    3. Runs growth classification and biomass estimation.
    4. Persists the result as a ``processing_logs`` entry with
       ``operation_type = 'ml_scoring'``.

    Query Parameters
    ----------------
    start_date : str  – ISO date (``YYYY-MM-DD``)
    end_date   : str  – ISO date (``YYYY-MM-DD``)
    """
    # Validate project exists
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check that at least one model is loaded
    if not svc._loaded:
        raise HTTPException(
            status_code=503,
            detail="ML models are not loaded.  Run the training pipeline first.",
        )

    # Extract features
    t0 = time.time()
    extractor = PipelineFeatureExtractor(db)
    raw_features = extractor.extract_features(
        project_id=str(project_id),
        start_date=start_date,
        end_date=end_date,
    )

    if "error" in raw_features:
        raise HTTPException(
            status_code=422,
            detail={
                "code": raw_features["error"],
                "message": f"Feature extraction failed: {raw_features['error']}",
            },
        )

    # Flatten Phase 1 features → flat dict for inference
    flat_features = svc.flatten_extracted_features(raw_features)

    # Run inference
    scoring_result = svc.score(flat_features)
    total_ms = int((time.time() - t0) * 1000)

    # Persist result
    log = Job(
        project_id=project_id,
        operation_type=OPERATION_TYPE,
        status="success",
        input_data={
            "start_date": start_date,
            "end_date": end_date,
            "features": flat_features,
        },
        output_data=scoring_result,
        execution_time_ms=total_ms,
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    return {
        "project_id": str(project_id),
        "processing_log_id": str(log.id),
        "scored_at": scoring_result["scored_at"],
        "growth": scoring_result.get("growth"),
        "biomass": scoring_result.get("biomass"),
        "input_features": scoring_result["input_features"],
        "total_inference_ms": total_ms,
    }


@router.post("/score-features", response_model=DirectScoringResponse)
def score_features_directly(
    features: FeatureInput,
    svc: InferenceService = Depends(get_inference_service),
) -> dict:
    """Score a raw feature vector directly (no project/DB lookup).

    Useful for testing, ad-hoc predictions, and external integrations.
    """
    if not svc._loaded:
        raise HTTPException(
            status_code=503,
            detail="ML models are not loaded.  Run the training pipeline first.",
        )

    flat = features.model_dump()
    result = svc.score(flat)

    return {
        "scored_at": result["scored_at"],
        "growth": result.get("growth"),
        "biomass": result.get("biomass"),
        "input_features": result["input_features"],
        "total_inference_ms": result["total_inference_ms"],
    }


@router.get("/status", response_model=ModelStatusResponse)
def model_status(
    svc: InferenceService = Depends(get_inference_service),
) -> dict:
    """Return loaded model versions, metrics, and health status."""
    return svc.status()


@router.get("/{project_id}/latest")
def get_latest_scoring(
    project_id: UUID,
    db: Session = Depends(get_db),
) -> dict:
    """Return the most recent ML scoring result for a project."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    stmt = (
        select(Job)
        .where(Job.project_id == project_id)
        .where(Job.operation_type == OPERATION_TYPE)
        .order_by(Job.created_at.desc())
        .limit(1)
    )
    log = db.execute(stmt).scalar_one_or_none()

    if log is None:
        raise HTTPException(
            status_code=404,
            detail="No ML scoring results found for this project",
        )

    return {
        "project_id": str(project_id),
        "processing_log_id": str(log.id),
        "scored_at": log.created_at.isoformat() if log.created_at else None,
        "scoring": log.output_data,
    }


@router.get("/{project_id}/history")
def list_scoring_history(
    project_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    """List all ML scoring runs for a project (newest first)."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    stmt = (
        select(Job)
        .where(Job.project_id == project_id)
        .where(Job.operation_type == OPERATION_TYPE)
        .order_by(Job.created_at.desc())
        .limit(limit)
    )
    logs = db.execute(stmt).scalars().all()

    history = [
        {
            "processing_log_id": str(log.id),
            "scored_at": log.created_at.isoformat() if log.created_at else None,
            "status": log.status,
            "execution_time_ms": log.execution_time_ms,
            "scoring": log.output_data,
        }
        for log in logs
    ]

    return {
        "project_id": str(project_id),
        "count": len(history),
        "history": history,
    }
