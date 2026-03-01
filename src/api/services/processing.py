"""
GeoMRV Processing Service
=========================
Orchestration for satellite data processing and evidence generation.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


async def process_satellite_data(project_id: str, start_date: str, end_date: str):
    """
    Orchestrate satellite data fetching and processing.

    This is a stub - actual implementation will use:
    - src.satellite_services.earth_engine_client
    - src.satellite_services.ndvi_calculator
    - src.satellite_services.timelapse_exporter
    """
    raise NotImplementedError("Satellite processing not yet implemented")


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

    Parameters
    ----------
    project_id : str
        UUID of the project.
    start_date, end_date : str
        ISO date boundaries of the analysis window.
    db : Session
        Active SQLAlchemy session.

    Returns
    -------
    dict
        Keys: ``package_id``, ``pdf_path``, ``blob_path``, ``checksum``,
        ``overall_status``, ``confidence_score``, ``growth_classification``.
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
