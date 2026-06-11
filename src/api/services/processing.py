"""
GeoMRV Processing Service
=========================
Orchestration helpers for satellite data processing and evidence generation.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


async def process_satellite_data(
    project_id: str,
    start_date: str,
    end_date: str,
    db: Session | None = None,
) -> dict:
    """Create and process a satellite monitoring job.

    This wrapper keeps older orchestration callers working while delegating
    to the canonical ``JobService`` implementation.
    """
    from src.api.database import SessionLocal
    from src.api.schemas import JobCreate, JobType
    from src.api.services.job_service import JobService

    owns_session = db is None
    session = db or SessionLocal()
    try:
        svc = JobService(session)
        job = svc.create_job(
            JobCreate(
                project_id=project_id,
                start_date=start_date,
                end_date=end_date,
                job_type=JobType.MONITORING,
            )
        )
        svc.process_job(uuid.UUID(job.id))
        final_job = svc.get_job(uuid.UUID(job.id))
        return {
            "job_id": job.id,
            "project_id": project_id,
            "status": final_job.status if final_job else "unknown",
            "error_message": final_job.error_message if final_job else None,
        }
    finally:
        if owns_session:
            session.close()


async def generate_evidence_package(
    project_id: str,
    start_date: str,
    end_date: str,
    db: Session,
) -> dict:
    """Generate an evidence package for a project and analysis period.

    Delegates to :class:`PackageAssemblyService` for data assembly,
    :class:`PDFReportGenerator` for PDF creation, and
    :class:`EvidenceStorageService` for storage.
    """
    import os
    import tempfile

    from src.api.config import settings
    from src.evidence_generation.package_assembly import PackageAssemblyService
    from src.evidence_generation.report_generator import PDFReportGenerator
    from src.evidence_generation.storage_service import EvidenceStorageService

    # Assemble
    assembly = PackageAssemblyService(db)
    package = assembly.assemble_package(project_id, start_date, end_date)
    obs_df = assembly.build_observations_dataframe(project_id, start_date, end_date)

    # Generate PDF
    output_dir = os.path.join(tempfile.gettempdir(), "geomrv_reports")
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, f"evidence_{package.package_id}.pdf")

    gen = PDFReportGenerator()
    gen.generate_report(
        package,
        pdf_path,
        observations_df=obs_df if not obs_df.empty else None,
    )

    # Upload
    storage = EvidenceStorageService(
        connection_string=settings.AZURE_STORAGE_CONNECTION_STRING,
        container_name=settings.AZURE_STORAGE_CONTAINER_EVIDENCE,
    )
    upload = storage.upload_package(pdf_path, package.package_id)

    logger.info("Evidence package %s generated and stored", package.package_id)

    return {
        "package_id": package.package_id,
        "pdf_path": pdf_path,
        "blob_path": upload["blob_path"],
        "checksum": upload["checksum"],
        "overall_status": package.overall_status,
        "confidence_score": package.confidence_score,
        "growth_classification": package.growth_classification,
    }
