"""
GeoMRV Jobs Router
==================
Endpoints for processing job management and satellite observations.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.database import get_db
from src.api.schemas import JobCreate, JobResponse, ObservationResponse
from src.api.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


# ── helpers ──────────────────────────────────────────────────
def _svc(db: Session = Depends(get_db)) -> JobService:
    return JobService(db)


# ── Job CRUD ─────────────────────────────────────────────────


@router.get("", response_model=list[JobResponse])
def list_jobs(
    project_id: UUID | None = None,
    skip: int = 0,
    limit: int = 100,
    svc: JobService = Depends(_svc),
) -> list[JobResponse]:
    """List processing jobs, optionally filtered by project."""
    return svc.list_jobs(project_id=project_id, skip=skip, limit=limit)


@router.post("", response_model=JobResponse, status_code=201)
def create_job(
    payload: JobCreate,
    background_tasks: BackgroundTasks,
    svc: JobService = Depends(_svc),
) -> JobResponse:
    """Create a new processing job and start background satellite fetch."""
    job = svc.create_job(payload)

    # Schedule background processing
    background_tasks.add_task(svc.process_job, UUID(job.id))

    return job


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: UUID,
    svc: JobService = Depends(_svc),
) -> JobResponse:
    """Get a job by ID."""
    result = svc.get_job(job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Job not found")
    return result


# ── Observations ─────────────────────────────────────────────


@router.get(
    "/projects/{project_id}/observations",
    response_model=list[ObservationResponse],
)
def list_observations(
    project_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    svc: JobService = Depends(_svc),
) -> list[ObservationResponse]:
    """List satellite observations for a project, optionally filtered by date range."""
    observations = svc.list_observations(
        project_id=project_id,
        start_date=start_date.isoformat() if start_date else None,
        end_date=end_date.isoformat() if end_date else None,
    )
    return [
        ObservationResponse(
            id=str(o.id),
            project_id=str(o.project_id),
            observation_date=o.observation_date,
            ndvi=o.ndvi,
            ndvi_std=o.ndvi_std,
            ndvi_count=o.ndvi_count,
            evi=o.evi,
            biomass_estimate=o.biomass_estimate,
            biomass_std=o.biomass_std,
            data_source=o.data_source,
            cloud_cover_percent=o.cloud_cover_percent,
            created_at=o.created_at,
        )
        for o in observations
    ]
