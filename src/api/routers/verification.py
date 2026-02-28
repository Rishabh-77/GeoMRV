"""
GeoMRV Verification Router
============================
Endpoints for running deterministic verification rules on extracted
features, retrieving results, and listing verification history.
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
from src.verification_rules.rule_store import RuleStore
from src.verification_rules.rules_engine import VerificationRulesEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/verification", tags=["verification"])


# ── Run verification ──────────────────────────────────────────


@router.post("/{project_id}/verify")
def verify_project(
    project_id: UUID,
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> dict:
    """Run deterministic verification rules on a project's features.

    The endpoint first extracts (or re-extracts) features for the given
    date range, then applies all verification rules, computes a
    confidence score, and persists the results as a processing-log entry.

    Query Parameters
    ----------------
    start_date : str  – ISO date (``YYYY-MM-DD``)
    end_date   : str  – ISO date (``YYYY-MM-DD``)
    """
    # Validate project exists
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    t0 = time.time()

    # 1. Extract features
    extractor = PipelineFeatureExtractor(db)
    features = extractor.extract_features(
        project_id=str(project_id),
        start_date=start_date,
        end_date=end_date,
    )

    if "error" in features:
        raise HTTPException(
            status_code=422,
            detail={
                "code": features["error"],
                "message": f"Cannot verify: {features['error']}",
                "details": features,
            },
        )

    # 2. Run verification rules
    engine = VerificationRulesEngine()
    flags = engine.verify(features)
    confidence_score = engine.get_confidence_score(features, flags)
    overall_status = engine.get_overall_status(confidence_score)

    elapsed_ms = int((time.time() - t0) * 1000)

    # 3. Persist results
    store = RuleStore(db)
    log = store.save_verification_results(
        project_id=str(project_id),
        flags=flags,
        confidence_score=confidence_score,
        overall_status=overall_status,
        features_input=features,
        execution_time_ms=elapsed_ms,
    )

    return {
        "project_id": str(project_id),
        "processing_log_id": str(log.id),
        "execution_time_ms": elapsed_ms,
        "confidence_score": confidence_score,
        "overall_status": overall_status,
        "flag_count": len(flags),
        "verification_flags": [f.to_dict() for f in flags],
        "features_summary": {
            "period_start": features.get("period_start"),
            "period_end": features.get("period_end"),
            "total_observations": features.get("total_observations"),
            "clear_observations": features.get("clear_observations"),
        },
    }


# ── Get latest result ─────────────────────────────────────────


@router.get("/{project_id}/latest")
def get_latest_verification(
    project_id: UUID,
    db: Session = Depends(get_db),
) -> dict:
    """Return the most recent verification result for a project."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    store = RuleStore(db)
    result = store.get_latest_verification(str(project_id))

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No verification results found for this project",
        )

    return {"project_id": str(project_id), "verification": result}


# ── Verification history ──────────────────────────────────────


@router.get("/{project_id}/history")
def list_verification_history(
    project_id: UUID,
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    db: Session = Depends(get_db),
) -> dict:
    """List all verification runs for a project (newest first)."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    store = RuleStore(db)
    history = store.list_verification_history(str(project_id), limit=limit)

    return {
        "project_id": str(project_id),
        "count": len(history),
        "history": history,
    }
