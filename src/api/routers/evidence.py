"""
GeoMRV Evidence Router
======================
Endpoints for evidence package generation, retrieval, and download.
"""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.config import settings
from src.api.database import get_db
from src.api.models import EvidencePackage as EvidencePackageModel
from src.api.models import Project
from src.api.schemas import (
    EvidenceGenerateRequest,
    EvidenceGenerateResponse,
    EvidencePackageResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/evidence", tags=["evidence"])


# ── List / Get ────────────────────────────────────────────────


@router.get("", response_model=list[EvidencePackageResponse])
def list_evidence_packages(
    project_id: UUID | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[EvidencePackageResponse]:
    """List evidence packages, optionally filtered by project."""
    stmt = select(EvidencePackageModel).offset(skip).limit(limit)
    if project_id:
        stmt = stmt.where(EvidencePackageModel.project_id == project_id)
    result = db.execute(stmt).scalars().all()
    return [
        EvidencePackageResponse(
            id=str(e.id),
            project_id=str(e.project_id),
            package_date=e.package_date,
            period_start=e.period_start,
            period_end=e.period_end,
            status=e.status,
            s3_path=e.s3_path,
            checksum=e.checksum,
            created_at=e.created_at,
        )
        for e in result
    ]


@router.get("/{evidence_id}", response_model=EvidencePackageResponse)
def get_evidence_package(
    evidence_id: UUID, db: Session = Depends(get_db)
) -> EvidencePackageResponse:
    """Get an evidence package by ID."""
    evidence = db.get(EvidencePackageModel, evidence_id)
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence package not found")
    return EvidencePackageResponse(
        id=str(evidence.id),
        project_id=str(evidence.project_id),
        package_date=evidence.package_date,
        period_start=evidence.period_start,
        period_end=evidence.period_end,
        status=evidence.status,
        s3_path=evidence.s3_path,
        checksum=evidence.checksum,
        created_at=evidence.created_at,
    )


# ── Generate ──────────────────────────────────────────────────


@router.post(
    "/{project_id}/generate",
    response_model=EvidenceGenerateResponse,
    status_code=201,
)
def generate_evidence_package(
    project_id: UUID,
    body: EvidenceGenerateRequest,
    db: Session = Depends(get_db),
) -> EvidenceGenerateResponse:
    """Assemble an evidence package, generate a PDF, and upload to storage.

    Steps executed synchronously:
    1. Validate project exists.
    2. Assemble evidence package from DB records.
    3. Generate PDF report (with observation charts when available).
    4. Upload PDF to Azure Blob Storage (or local fallback).
    5. Persist metadata row in ``evidence_packages`` table.
    """
    # 1 ── validate project
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    start_str = body.start_date.isoformat()
    end_str = body.end_date.isoformat()

    try:
        # 2 ── assemble
        from src.evidence_generation.package_assembly import PackageAssemblyService

        assembly = PackageAssemblyService(db)
        package = assembly.assemble_package(str(project_id), start_str, end_str)
        obs_df = assembly.build_observations_dataframe(
            str(project_id), start_str, end_str
        )

        # 3 ── generate PDF
        from src.evidence_generation.report_generator import PDFReportGenerator

        output_dir = os.path.join(tempfile.gettempdir(), "geomrv_reports")
        os.makedirs(output_dir, exist_ok=True)
        pdf_filename = f"evidence_{package.package_id}.pdf"
        pdf_path = os.path.join(output_dir, pdf_filename)

        generator = PDFReportGenerator()
        generator.generate_report(
            package,
            pdf_path,
            observations_df=obs_df if not obs_df.empty else None,
        )

        # 4 ── upload to storage
        from src.evidence_generation.storage_service import EvidenceStorageService

        storage = EvidenceStorageService(
            connection_string=settings.AZURE_STORAGE_CONNECTION_STRING,
            container_name=settings.AZURE_STORAGE_CONTAINER_EVIDENCE,
        )
        upload_result = storage.upload_package(pdf_path, package.package_id)

        # 5 ── persist metadata
        db_pkg = EvidencePackageModel(
            id=uuid.UUID(package.package_id),
            project_id=project_id,
            package_date=date.today(),
            period_start=body.start_date,
            period_end=body.end_date,
            status=package.overall_status,
            s3_path=upload_result["blob_path"],
            checksum=upload_result["checksum"],
        )
        db.add(db_pkg)
        db.commit()

        logger.info(
            "Evidence package %s generated for project %s",
            package.package_id,
            project_id,
        )

        return EvidenceGenerateResponse(
            package_id=package.package_id,
            project_id=str(project_id),
            status=package.overall_status,
            growth_classification=package.growth_classification,
            confidence_score=package.confidence_score,
            overall_status=package.overall_status,
            blob_path=upload_result["blob_path"],
            checksum=upload_result["checksum"],
            pdf_path=pdf_path,
        )

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(
            "Evidence generation failed for project %s: %s",
            project_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(exc))


# ── Download ──────────────────────────────────────────────────


@router.get("/{evidence_id}/download")
def download_evidence_package(
    evidence_id: UUID,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Download an evidence package PDF.

    Retrieves the file from Azure Blob Storage (or local fallback)
    and returns it as a streaming file response.
    """
    evidence = db.get(EvidencePackageModel, evidence_id)
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence package not found")

    if not evidence.s3_path:
        raise HTTPException(
            status_code=404, detail="No file path recorded for this package"
        )

    try:
        from src.evidence_generation.storage_service import EvidenceStorageService

        storage = EvidenceStorageService(
            connection_string=settings.AZURE_STORAGE_CONNECTION_STRING,
            container_name=settings.AZURE_STORAGE_CONTAINER_EVIDENCE,
        )

        download_dir = os.path.join(tempfile.gettempdir(), "geomrv_downloads")
        os.makedirs(download_dir, exist_ok=True)
        local_path = os.path.join(download_dir, f"{evidence_id}.pdf")

        storage.download_package(evidence.s3_path, local_path)

        return FileResponse(
            path=local_path,
            filename=f"evidence_{evidence_id}.pdf",
            media_type="application/pdf",
        )

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Evidence package file not found in storage",
        )
    except Exception as exc:
        logger.error(
            "Download failed for package %s: %s",
            evidence_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(exc))
