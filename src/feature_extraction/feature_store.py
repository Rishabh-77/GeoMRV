"""
GeoMRV Feature Store
====================
Persist extracted features as ``processing_logs`` entries and retrieve
them for downstream consumers (verification rules, evidence packaging).

Each saved feature set is stored as a processing-log row with
``operation_type = 'feature_extraction'`` so the existing lineage
tracking infrastructure is re-used without schema changes.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.models import Job  # Job model maps to processing_logs table

logger = logging.getLogger(__name__)


class FeatureStore:
    """Read / write feature sets via the ``processing_logs`` table."""

    OPERATION_TYPE = "feature_extraction"

    def __init__(self, db: Session):
        self.db = db

    # ── write ─────────────────────────────────────────────────

    def save_features(
        self,
        project_id: str,
        features: dict[str, Any],
        execution_time_ms: int = 0,
    ) -> Job:
        """Persist a feature dictionary as a processing-log entry.

        Parameters
        ----------
        project_id : str
            UUID of the project the features belong to.
        features : dict
            The full feature dictionary produced by
            ``PipelineFeatureExtractor.extract_features``.
        execution_time_ms : int
            Wall-clock time taken for extraction (for auditing).

        Returns
        -------
        Job (processing_logs row) with generated ``id``.
        """
        log = Job(
            project_id=uuid.UUID(project_id),
            operation_type=self.OPERATION_TYPE,
            status="success",
            input_data={
                "period_start": features.get("period_start"),
                "period_end": features.get("period_end"),
                "cloud_cover_threshold": features.get("cloud_cover_threshold"),
            },
            output_data=features,
            execution_time_ms=execution_time_ms,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)

        logger.info(
            "Saved features for project %s (log id=%s)", project_id, log.id
        )
        return log

    # ── read ──────────────────────────────────────────────────

    def get_latest_features(self, project_id: str) -> dict[str, Any] | None:
        """Return the most recent feature set for *project_id*, or ``None``.

        Returns
        -------
        dict – the ``output_data`` JSONB column from the latest
        ``feature_extraction`` processing-log entry.
        """
        stmt = (
            select(Job)
            .where(Job.project_id == uuid.UUID(project_id))
            .where(Job.operation_type == self.OPERATION_TYPE)
            .where(Job.status == "success")
            .order_by(Job.created_at.desc())
            .limit(1)
        )
        row = self.db.execute(stmt).scalar_one_or_none()
        if row is None:
            return None
        return row.output_data

    def list_feature_history(
        self,
        project_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return feature extraction history (newest first).

        Each item contains the log metadata **and** the feature payload
        so consumers can compare feature versions over time.
        """
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
