"""
GeoMRV Evidence Router
======================
Endpoints for evidence package retrieval.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.database import get_db
from src.api.models import EvidencePackage
from src.api.schemas import EvidencePackageResponse

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("", response_model=list[EvidencePackageResponse])
def list_evidence_packages(
    project_id: UUID | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[EvidencePackageResponse]:
    """List evidence packages, optionally filtered by project."""
    stmt = select(EvidencePackage).offset(skip).limit(limit)
    if project_id:
        stmt = stmt.where(EvidencePackage.project_id == project_id)
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
    evidence = db.get(EvidencePackage, evidence_id)
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
