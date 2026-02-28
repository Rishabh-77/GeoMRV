"""
GeoMRV Features Router
======================
Endpoints for extracting, retrieving, and listing time-series features.
"""

from __future__ import annotations

import logging
import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.database import get_db
from src.api.models import Project
from src.feature_extraction.feature_calculator import PipelineFeatureExtractor
from src.feature_extraction.feature_store import FeatureStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/features", tags=["features"])


# ── Extract features ──────────────────────────────────────────


@router.post("/{project_id}/extract")
def extract_project_features(
    project_id: UUID,
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> dict:
    """Extract standardised time-series features for a project.

    Reads satellite observations from the database, filters by cloud
    cover, calculates trend / seasonality / anomalies / growth period /
    biomass proxy, persists the results as a processing-log entry, and
    returns the full feature dictionary.

    Query Parameters
    ----------------
    start_date : str   – ISO date (``YYYY-MM-DD``)
    end_date   : str   – ISO date (``YYYY-MM-DD``)
    """
    # Validate that the project exists
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Run extraction
    t0 = time.time()
    extractor = PipelineFeatureExtractor(db)
    features = extractor.extract_features(
        project_id=str(project_id),
        start_date=start_date,
        end_date=end_date,
    )
    elapsed_ms = int((time.time() - t0) * 1000)

    # Check for errors from the extractor
    if "error" in features:
        raise HTTPException(
            status_code=422,
            detail={
                "code": features["error"],
                "message": f"Feature extraction failed: {features['error']}",
                "details": features,
            },
        )

    # Persist
    store = FeatureStore(db)
    log = store.save_features(
        project_id=str(project_id),
        features=features,
        execution_time_ms=elapsed_ms,
    )

    return {
        "project_id": str(project_id),
        "processing_log_id": str(log.id),
        "execution_time_ms": elapsed_ms,
        "features": features,
    }


# ── Get latest features ──────────────────────────────────────


@router.get("/{project_id}/latest")
def get_latest_features(
    project_id: UUID,
    db: Session = Depends(get_db),
) -> dict:
    """Return the most recently extracted feature set for a project."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    store = FeatureStore(db)
    features = store.get_latest_features(str(project_id))

    if features is None:
        raise HTTPException(
            status_code=404,
            detail="No features extracted yet for this project",
        )

    return {"project_id": str(project_id), "features": features}


# ── Feature history ───────────────────────────────────────────


@router.get("/{project_id}/history")
def list_feature_history(
    project_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    """Return the extraction history (newest first) for a project.

    Useful for comparing feature evolution over multiple extraction runs.
    """
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    store = FeatureStore(db)
    history = store.list_feature_history(str(project_id), limit=limit)

    return {
        "project_id": str(project_id),
        "count": len(history),
        "history": history,
    }
