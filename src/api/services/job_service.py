"""
GeoMRV Job Service
==================
Business logic for processing-job lifecycle: create, run, and track
satellite data-fetching jobs.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.models import Boundary, Job, Observation, Project
from src.api.schemas import JobCreate, JobResponse

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Helper to convert ORM → schema
# ──────────────────────────────────────────────────────────────


def _job_to_response(job: Job) -> JobResponse:
    return JobResponse(
        id=str(job.id),
        project_id=str(job.project_id),
        operation_type=job.operation_type,
        status=job.status,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


class JobService:
    """Create, run, and query processing jobs."""

    def __init__(self, db: Session):
        self.db = db

    # ── queries ───────────────────────────────────────────────

    def list_jobs(
        self,
        project_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[JobResponse]:
        """Return paginated list of jobs, optionally filtered by project."""
        stmt = select(Job).offset(skip).limit(limit)
        if project_id:
            stmt = stmt.where(Job.project_id == project_id)
        rows = self.db.execute(stmt).scalars().all()
        return [_job_to_response(j) for j in rows]

    def get_job(self, job_id: uuid.UUID) -> JobResponse | None:
        """Get a single job by ID."""
        job = self.db.get(Job, job_id)
        if not job:
            return None
        return _job_to_response(job)

    # ── create ────────────────────────────────────────────────

    def create_job(self, data: JobCreate) -> JobResponse:
        """Persist a new job in *pending* state and return its response."""
        job = Job(
            project_id=uuid.UUID(data.project_id),
            operation_type=data.job_type.value,
            status="pending",
            input_data={
                "start_date": data.start_date.isoformat(),
                "end_date": data.end_date.isoformat(),
            },
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return _job_to_response(job)

    # ── background processing ────────────────────────────────

    def process_job(self, job_id: uuid.UUID) -> None:
        """
        Background task: fetch satellite data for the job's project
        boundary and persist observations + processing log.

        This method is designed to be called via
        ``BackgroundTasks.add_task(service.process_job, job_id)``.
        """
        start_time = time.time()
        job = self.db.get(Job, job_id)
        if not job:
            logger.error("process_job: Job %s not found", job_id)
            return

        try:
            # Mark running
            job.status = "running"
            self.db.commit()

            # Validate project + boundary exist
            project = self.db.get(Project, job.project_id)
            if not project:
                raise ValueError(f"Project {job.project_id} not found")

            boundary = self.db.execute(
                select(Boundary)
                .where(Boundary.project_id == job.project_id)
                .order_by(Boundary.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if not boundary or not boundary.boundary_geojson:
                raise ValueError(f"No boundary found for project {job.project_id}")

            # Fetch satellite data
            from src.satellite_services.data_fetcher import SatelliteDataFetcher

            fetcher = SatelliteDataFetcher()
            input_data = job.input_data or {}

            df = fetcher.fetch_sentinel2_data(
                boundary_geojson=boundary.boundary_geojson,
                start_date=input_data.get("start_date", ""),
                end_date=input_data.get("end_date", ""),
            )

            # Store observations
            obs_count = 0
            for _, row in df.iterrows():
                obs = Observation(
                    project_id=job.project_id,
                    observation_date=row["date"],
                    ndvi=row.get("ndvi_mean"),
                    ndvi_std=row.get("ndvi_std"),
                    ndvi_count=row.get("ndvi_count"),
                    evi=row.get("evi_mean"),
                    data_source=row.get("data_source", "Sentinel-2"),
                    cloud_cover_percent=row.get("cloud_cover_pct"),
                )
                self.db.add(obs)
                obs_count += 1

            # Create processing log
            elapsed_ms = int((time.time() - start_time) * 1000)
            log = Job(
                project_id=job.project_id,
                operation_type="satellite_fetch",
                status="success",
                input_data={
                    "start_date": input_data.get("start_date"),
                    "end_date": input_data.get("end_date"),
                    "source": "Sentinel-2",
                },
                output_data={
                    "observations_stored": obs_count,
                },
                execution_time_ms=elapsed_ms,
            )
            self.db.add(log)

            # Mark completed
            job.status = "completed"
            job.output_data = {"observations_stored": obs_count}
            job.execution_time_ms = elapsed_ms
            self.db.commit()

            logger.info(
                "Job %s completed: %d observations stored in %d ms",
                job_id,
                obs_count,
                elapsed_ms,
            )

        except Exception as exc:
            elapsed_ms = int((time.time() - start_time) * 1000)
            job.status = "failed"
            job.error_message = str(exc)
            job.execution_time_ms = elapsed_ms
            self.db.commit()
            logger.error("Job %s failed: %s", job_id, exc)

    # ── observations ──────────────────────────────────────────

    def list_observations(
        self,
        project_id: uuid.UUID,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[Observation]:
        """Return observations for a project, optionally filtered by date range."""
        stmt = (
            select(Observation)
            .where(Observation.project_id == project_id)
            .order_by(Observation.observation_date)
        )
        if start_date:
            stmt = stmt.where(Observation.observation_date >= start_date)
        if end_date:
            stmt = stmt.where(Observation.observation_date <= end_date)
        return list(self.db.execute(stmt).scalars().all())
