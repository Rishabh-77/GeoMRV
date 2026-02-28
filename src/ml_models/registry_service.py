"""
GeoMRV Model Registry Service
=============================
Service layer for model version registration, activation, and audit trail.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.ml_models.model_registry import ModelRegistry

logger = logging.getLogger(__name__)


class RegistryService:
    """CRUD + lifecycle operations for the ``model_registry`` table."""

    STATUS_ACTIVE = "active"
    STATUS_ARCHIVED = "archived"
    STATUS_DEPRECATED = "deprecated"

    def __init__(self, db: Session):
        self.db = db

    def register_model(
        self,
        model_type: str,
        version: str,
        metrics: dict[str, Any] | None,
        model_path: str,
        metadata_path: str | None = None,
        status: str = STATUS_ARCHIVED,
    ) -> ModelRegistry:
        """Register a model version if it does not already exist."""
        model_id = f"{model_type}_{version}"

        existing = self.db.get(ModelRegistry, model_id)
        if existing is not None:
            logger.info("Model already registered: %s", model_id)
            return existing

        entry = ModelRegistry(
            id=model_id,
            model_type=model_type,
            version=version,
            metrics=metrics,
            status=status,
            model_path=model_path,
            metadata_path=metadata_path,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)

        logger.info(
            "Registered model %s version %s with status=%s",
            model_type,
            version,
            status,
        )
        return entry

    def activate_model(self, model_id: str) -> ModelRegistry:
        """Set one model version active and archive sibling active versions."""
        target = self.db.get(ModelRegistry, model_id)
        if target is None:
            raise ValueError(f"Model id not found: {model_id}")

        stmt = (
            select(ModelRegistry)
            .where(ModelRegistry.model_type == target.model_type)
            .where(ModelRegistry.status == self.STATUS_ACTIVE)
            .where(ModelRegistry.id != model_id)
        )
        currently_active = self.db.execute(stmt).scalars().all()
        for row in currently_active:
            row.status = self.STATUS_ARCHIVED

        target.status = self.STATUS_ACTIVE
        target.deployed_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(target)

        logger.info("Activated model: %s", model_id)
        return target

    def deprecate_model(self, model_id: str) -> ModelRegistry:
        """Mark a model version deprecated."""
        target = self.db.get(ModelRegistry, model_id)
        if target is None:
            raise ValueError(f"Model id not found: {model_id}")

        target.status = self.STATUS_DEPRECATED
        self.db.commit()
        self.db.refresh(target)

        logger.info("Deprecated model: %s", model_id)
        return target

    def get_active_model(self, model_type: str) -> ModelRegistry | None:
        """Return currently active model for a given type."""
        stmt = (
            select(ModelRegistry)
            .where(ModelRegistry.model_type == model_type)
            .where(ModelRegistry.status == self.STATUS_ACTIVE)
            .order_by(ModelRegistry.deployed_at.desc(), ModelRegistry.created_at.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_models(
        self,
        model_type: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[ModelRegistry]:
        """List model versions with optional filters."""
        stmt = select(ModelRegistry)
        if model_type:
            stmt = stmt.where(ModelRegistry.model_type == model_type)
        if status:
            stmt = stmt.where(ModelRegistry.status == status)

        stmt = stmt.order_by(ModelRegistry.created_at.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())
