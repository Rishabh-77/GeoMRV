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
# Feature Extraction Schemas
# ─────────────────────────────────────────────────────────────


class FeatureExtractionRequest(BaseModel):
    """Query-parameter schema for triggering feature extraction."""

    start_date: date
    end_date: date


class TrendFeatures(BaseModel):
    trend_slope: float | None = None
    slope_per_year: float | None = None
    r_squared: float | None = None


class SeasonalityFeatures(BaseModel):
    peak_month: int | None = None
    trough_month: int | None = None
    peak_ndvi: float | None = None
    trough_ndvi: float | None = None
    seasonal_amplitude: float | None = None


class GrowthPeriodFeatures(BaseModel):
    growth_start: str | None = None
    growth_end: str | None = None
    growth_days: int = 0
    ndvi_threshold: float | None = None


class NDVIStats(BaseModel):
    mean: float | None = None
    std: float | None = None
    min: float | None = None
    max: float | None = None
    median: float | None = None
    count: int | None = None


class BiomassStats(BaseModel):
    mean: float | None = None
    std: float | None = None
    min: float | None = None
    max: float | None = None
    note: str | None = None


class FeatureSet(BaseModel):
    """Full set of extracted features for a project period."""

    project_id: str
    period_start: str | None = None
    period_end: str | None = None
    total_observations: int | None = None
    clear_observations: int | None = None
    cloud_cover_threshold: float | None = None
    extracted_at: str | None = None
    trend: TrendFeatures | None = None
    seasonality: SeasonalityFeatures | None = None
    growth_period: GrowthPeriodFeatures | None = None
    anomalies: list[str] | None = None
    ndvi_stats: NDVIStats | None = None
    biomass_stats: BiomassStats | None = None


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
