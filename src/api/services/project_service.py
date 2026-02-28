"""
GeoMRV Project Service
======================
Business logic for project and boundary management.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.models import Boundary, Project
from src.api.schemas import (
    BoundaryResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)


def _project_to_response(project: Project) -> ProjectResponse:
    """Convert a Project ORM instance to a ProjectResponse schema."""
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


class ProjectService:
    """Encapsulates project CRUD and boundary operations."""

    def __init__(self, db: Session):
        self.db = db

    # ── Projects ──────────────────────────────────────────────

    def list_projects(self, skip: int = 0, limit: int = 100) -> list[ProjectResponse]:
        """Return paginated list of projects."""
        stmt = select(Project).offset(skip).limit(limit)
        rows = self.db.execute(stmt).scalars().all()
        return [_project_to_response(p) for p in rows]

    def create_project(self, data: ProjectCreate) -> ProjectResponse:
        """Insert a new project and return its response."""
        project = Project(
            name=data.name,
            description=data.description,
            location_name=data.location_name,
            country=data.country,
            region=data.region,
            total_area_ha=data.total_area_ha,
            project_type=data.project_type.value if data.project_type else None,
            start_date=data.start_date,
        )
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return _project_to_response(project)

    def get_project(self, project_id: uuid.UUID) -> ProjectResponse | None:
        """Fetch a single project by primary key."""
        project = self.db.get(Project, project_id)
        if not project:
            return None
        return _project_to_response(project)

    def update_project(
        self, project_id: uuid.UUID, data: ProjectUpdate
    ) -> ProjectResponse | None:
        """Partially update a project (only supplied fields are changed)."""
        project = self.db.get(Project, project_id)
        if not project:
            return None

        update_fields = data.model_dump(exclude_unset=True)
        for key, value in update_fields.items():
            if key == "project_type" and value is not None:
                value = value.value
            setattr(project, key, value)

        project.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(project)
        return _project_to_response(project)

    def delete_project(self, project_id: uuid.UUID) -> bool:
        """Delete a project. Returns True if found and deleted."""
        project = self.db.get(Project, project_id)
        if not project:
            return False
        self.db.delete(project)
        self.db.commit()
        return True

    # ── Boundaries ────────────────────────────────────────────

    def save_boundary(
        self,
        project_id: uuid.UUID,
        geojson: dict,
        area_ha: float | None = None,
    ) -> BoundaryResponse:
        """Persist a GeoJSON boundary for a project."""
        boundary = Boundary(
            project_id=project_id,
            boundary_geojson=geojson,
            area_ha=area_ha,
        )
        self.db.add(boundary)
        self.db.commit()
        self.db.refresh(boundary)
        return BoundaryResponse(
            id=str(boundary.id),
            project_id=str(boundary.project_id),
            area_ha=boundary.area_ha,
            created_at=boundary.created_at,
        )

    def get_boundary(self, project_id: uuid.UUID) -> BoundaryResponse | None:
        """Return the latest boundary for a project."""
        stmt = (
            select(Boundary)
            .where(Boundary.project_id == project_id)
            .order_by(Boundary.created_at.desc())
            .limit(1)
        )
        boundary = self.db.execute(stmt).scalar_one_or_none()
        if not boundary:
            return None
        return BoundaryResponse(
            id=str(boundary.id),
            project_id=str(boundary.project_id),
            area_ha=boundary.area_ha,
            created_at=boundary.created_at,
        )

    @staticmethod
    def calculate_area_ha(geojson: dict) -> float | None:
        """Estimate area in hectares from a GeoJSON geometry using shapely."""
        try:
            from shapely.geometry import shape

            geom = shape(geojson)
            # Rough conversion: 1 degree ≈ 111 km at equator
            # Area in sq degrees → sq metres → hectares
            area_sq_deg = geom.area
            area_ha = area_sq_deg * (111_320**2) / 10_000
            return round(area_ha, 2)
        except Exception:
            return None
