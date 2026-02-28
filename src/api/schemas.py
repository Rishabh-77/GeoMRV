"""
GeoMRV Pydantic Schemas
=======================
Request/response schemas for API validation.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel

# ─────────────────────────────────────────────────────────────
# Project Schemas
# ─────────────────────────────────────────────────────────────


class ProjectType(str, Enum):
    """Supported project types."""

    FOREST = "forest"
    AGROFORESTRY = "agroforestry"
    CROP = "crop"
    REGENERATIVE = "regenerative"


class ProjectCreate(BaseModel):
    """Schema for creating a new project."""

    name: str
    description: str | None = None
    location_name: str | None = None
    country: str | None = None
    region: str | None = None
    total_area_ha: float | None = None
    project_type: ProjectType | None = None
    start_date: date | None = None


class ProjectResponse(ProjectCreate):
    """Schema for project responses (includes id + timestamps)."""

    id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class ProjectUpdate(BaseModel):
    """Schema for updating an existing project (all fields optional)."""

    name: str | None = None
    description: str | None = None
    location_name: str | None = None
    country: str | None = None
    region: str | None = None
    total_area_ha: float | None = None
    project_type: ProjectType | None = None
    start_date: date | None = None


class BoundaryResponse(BaseModel):
    """Schema for boundary responses."""

    id: str
    project_id: str
    area_ha: float | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────
# Job Schemas
# ─────────────────────────────────────────────────────────────


class JobType(str, Enum):
    """Supported job types."""

    MONITORING = "monitoring"
    VERIFICATION = "verification"
    REPORTING = "reporting"


class JobCreate(BaseModel):
    """Schema for creating a processing job."""

    project_id: str
    start_date: date
    end_date: date
    job_type: JobType = JobType.MONITORING


class JobResponse(BaseModel):
    """Schema for job responses."""

    id: str
    project_id: str
    operation_type: str | None = None
    status: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────
# Observation Schemas
# ─────────────────────────────────────────────────────────────


class ObservationResponse(BaseModel):
    """Schema for satellite observation responses."""

    id: str
    project_id: str
    observation_date: date
    ndvi: float | None = None
    ndvi_std: float | None = None
    ndvi_count: int | None = None
    evi: float | None = None
    biomass_estimate: float | None = None
    biomass_std: float | None = None
    data_source: str | None = None
    cloud_cover_percent: float | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────
# Evidence Package Schemas
# ─────────────────────────────────────────────────────────────


class EvidencePackageResponse(BaseModel):
    """Schema for evidence package responses."""

    id: str
    project_id: str
    package_date: date | None = None
    period_start: date | None = None
    period_end: date | None = None
    status: str | None = None
    s3_path: str | None = None
    checksum: str | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True
