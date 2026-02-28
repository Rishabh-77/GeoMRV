"""
GeoMRV Rule Store
=================
Persist verification results as ``processing_logs`` entries and retrieve
them for downstream consumers (evidence packaging, audit reports).

Each saved result is stored as a processing-log row with
``operation_type = 'verification'`` so the existing lineage tracking
infrastructure is re-used without schema changes.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.models import Job  # maps to processing_logs table
from src.verification_rules.rules_engine import RiskLevel, VerificationFlag

logger = logging.getLogger(__name__)


class RuleStore:
    """Read / write verification results via the ``processing_logs`` table."""

    OPERATION_TYPE = "verification"

    def __init__(self, db: Session):
        self.db = db

    # ── write ─────────────────────────────────────────────────

    def save_verification_results(
        self,
        project_id: str,
        flags: List[VerificationFlag],
        confidence_score: float,
        overall_status: str,
        features_input: dict | None = None,
        execution_time_ms: int = 0,
    ) -> Job:
        """Persist a verification run as a processing-log entry.

        Parameters
        ----------
        project_id : str
            UUID of the verified project.
        flags : list[VerificationFlag]
            Flags raised by the rules engine.
        confidence_score : float
            Computed confidence score (0–100).
        overall_status : str
            ``PASS``, ``REVIEW_REQUIRED``, or ``FAIL``.
        features_input : dict | None
            Summary of the feature set that was verified (for lineage).
        execution_time_ms : int
            Wall-clock time taken for the verification run.

        Returns
        -------
        Job (processing_logs row) with generated ``id``.
        """
        has_critical = any(f.risk_level == RiskLevel.CRITICAL for f in flags)

        log = Job(
            project_id=uuid.UUID(project_id),
            operation_type=self.OPERATION_TYPE,
            status="completed",
            input_data={
                "period_start": (features_input or {}).get("period_start"),
                "period_end": (features_input or {}).get("period_end"),
            },
            output_data={
                "flags": [f.to_dict() for f in flags],
                "flag_count": len(flags),
                "confidence_score": confidence_score,
                "overall_status": overall_status,
                "has_critical_flags": has_critical,
                "verified_at": datetime.utcnow().isoformat(),
            },
            execution_time_ms=execution_time_ms,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)

        logger.info(
            "Saved verification for project %s — score=%.1f status=%s (log id=%s)",
            project_id,
            confidence_score,
            overall_status,
            log.id,
        )
        return log

    # ── read ──────────────────────────────────────────────────

    def get_latest_verification(self, project_id: str) -> Dict[str, Any] | None:
        """Return the most recent verification result for *project_id*.

        Returns
        -------
        dict – the ``output_data`` JSONB column, or ``None``.
        """
        stmt = (
            select(Job)
            .where(Job.project_id == uuid.UUID(project_id))
            .where(Job.operation_type == self.OPERATION_TYPE)
            .where(Job.status == "completed")
            .order_by(Job.created_at.desc())
            .limit(1)
        )
        row = self.db.execute(stmt).scalar_one_or_none()
        if row is None:
            return None
        return row.output_data

    def list_verification_history(
        self,
        project_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return verification history for a project (newest first)."""
        stmt = (
            select(Job)
            .where(Job.project_id == uuid.UUID(project_id))
            .where(Job.operation_type == self.OPERATION_TYPE)
            .order_by(Job.created_at.desc())
            .limit(limit)
        )
        rows = self.db.execute(stmt).scalars().all()
        return [
            {
                "id": str(r.id),
                "project_id": str(r.project_id),
                "status": r.status,
                "input_data": r.input_data,
                "output_data": r.output_data,
                "execution_time_ms": r.execution_time_ms,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
