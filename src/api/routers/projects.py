"""
GeoMRV Projects Router
======================
CRUD endpoints for project management + boundary upload.
"""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from src.api.database import get_db
from src.api.schemas import (
    BoundaryResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)
from src.api.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


# ── helpers ──────────────────────────────────────────────────
def _svc(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


# ── CRUD ─────────────────────────────────────────────────────


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    skip: int = 0,
    limit: int = 100,
    svc: ProjectService = Depends(_svc),
) -> list[ProjectResponse]:
    """List all projects with pagination."""
    return svc.list_projects(skip=skip, limit=limit)


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(
    payload: ProjectCreate,
    svc: ProjectService = Depends(_svc),
) -> ProjectResponse:
    """Create a new project."""
    return svc.create_project(payload)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: UUID,
    svc: ProjectService = Depends(_svc),
) -> ProjectResponse:
    """Get a project by ID."""
    result = svc.get_project(project_id)
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    svc: ProjectService = Depends(_svc),
) -> ProjectResponse:
    """Update a project (partial update — only supplied fields are changed)."""
    result = svc.update_project(project_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: UUID,
    svc: ProjectService = Depends(_svc),
) -> None:
    """Delete a project by ID."""
    if not svc.delete_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")


# ── Boundary ─────────────────────────────────────────────────


@router.post(
    "/{project_id}/upload-boundary",
    response_model=BoundaryResponse,
    status_code=201,
)
async def upload_boundary(
    project_id: UUID,
    file: UploadFile,
    svc: ProjectService = Depends(_svc),
) -> BoundaryResponse:
    """Upload a GeoJSON boundary file for a project.

    Accepts a ``.geojson`` file.  The geometry is stored and the
    approximate area (in hectares) is computed automatically.
    """
    # Ensure project exists
    if not svc.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    if not file.filename or not file.filename.endswith(".geojson"):
        raise HTTPException(
            status_code=400,
            detail="Only .geojson files are supported",
        )

    contents = await file.read()
    try:
        geojson = json.loads(contents)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in uploaded file")

    # Extract the geometry object
    geometry = geojson
    if geojson.get("type") == "FeatureCollection":
        features = geojson.get("features", [])
        if not features:
            raise HTTPException(
                status_code=400, detail="FeatureCollection has no features"
            )
        geometry = features[0].get("geometry", geojson)
    elif geojson.get("type") == "Feature":
        geometry = geojson.get("geometry", geojson)

    area_ha = ProjectService.calculate_area_ha(geometry)
    return svc.save_boundary(project_id, geometry, area_ha)


@router.get(
    "/{project_id}/boundary",
    response_model=BoundaryResponse,
)
def get_boundary(
    project_id: UUID,
    svc: ProjectService = Depends(_svc),
) -> BoundaryResponse:
    """Get the latest boundary for a project."""
    if not svc.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    boundary = svc.get_boundary(project_id)
    if not boundary:
        raise HTTPException(status_code=404, detail="No boundary found for project")
    return boundary
