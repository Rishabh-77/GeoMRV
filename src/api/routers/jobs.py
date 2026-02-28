"""
GeoMRV Jobs Router
==================
Endpoints for processing job management.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.database import get_db
from src.api.models import Job
from src.api.schemas import JobCreate, JobResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobResponse])
def list_jobs(
    project_id: UUID | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[JobResponse]:
    """List processing jobs, optionally filtered by project."""
    stmt = select(Job).offset(skip).limit(limit)
    if project_id:
        stmt = stmt.where(Job.project_id == project_id)
    result = db.execute(stmt).scalars().all()
    return [
        JobResponse(
            id=str(j.id),
            project_id=str(j.project_id),
            operation_type=j.operation_type,
            status=j.status,
            error_message=j.error_message,
            created_at=j.created_at,
            updated_at=j.updated_at,
        )
        for j in result
    ]


@router.post("", response_model=JobResponse, status_code=201)
def create_job(payload: JobCreate, db: Session = Depends(get_db)) -> JobResponse:
    """Create a new processing job."""
    job = Job(
        project_id=UUID(payload.project_id),
        operation_type=payload.job_type.value,
        status="pending",
        input_data={
            "start_date": payload.start_date.isoformat(),
            "end_date": payload.end_date.isoformat(),
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return JobResponse(
        id=str(job.id),
        project_id=str(job.project_id),
        operation_type=job.operation_type,
        status=job.status,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: UUID, db: Session = Depends(get_db)) -> JobResponse:
    """Get a job by ID."""
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(
        id=str(job.id),
        project_id=str(job.project_id),
        operation_type=job.operation_type,
        status=job.status,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
