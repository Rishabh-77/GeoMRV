"""
GeoMRV Projects Router
======================
CRUD endpoints for project management.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.database import get_db
from src.api.models import Project
from src.api.schemas import ProjectCreate, ProjectResponse

if TYPE_CHECKING:
    pass

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
) -> list[Project]:
    """List all projects with pagination."""
    stmt = select(Project).offset(skip).limit(limit)
    result = db.execute(stmt).scalars().all()
    return [
        ProjectResponse(
            id=str(p.id),
            name=p.name,
            description=p.description,
            location_name=p.location_name,
            country=p.country,
            region=p.region,
            total_area_ha=p.total_area_ha,
            project_type=p.project_type,
            start_date=p.start_date,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in result
    ]


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(
    payload: ProjectCreate, db: Session = Depends(get_db)
) -> ProjectResponse:
    """Create a new project."""
    project = Project(
        name=payload.name,
        description=payload.description,
        location_name=payload.location_name,
        country=payload.country,
        region=payload.region,
        total_area_ha=payload.total_area_ha,
        project_type=payload.project_type.value if payload.project_type else None,
        start_date=payload.start_date,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        description=project.description,
        location_name=project.location_name,
        country=project.country,
        region=project.region,
        total_area_ha=project.total_area_ha,
        project_type=project.project_type,
        start_date=project.start_date,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: UUID, db: Session = Depends(get_db)) -> ProjectResponse:
    """Get a project by ID."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        description=project.description,
        location_name=project.location_name,
        country=project.country,
        region=project.region,
        total_area_ha=project.total_area_ha,
        project_type=project.project_type,
        start_date=project.start_date,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: UUID, db: Session = Depends(get_db)) -> None:
    """Delete a project by ID."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
