"""
GeoMRV Model Registry ORM
=========================
SQLAlchemy model for tracking ML model versions and deployment state.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.api.models import Base


class ModelRegistry(Base):
    """Track model versions, metrics, and deployment status."""

    __tablename__ = "model_registry"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    model_type: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="archived")
    model_path: Mapped[str] = mapped_column(String(500), nullable=False)
    metadata_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
