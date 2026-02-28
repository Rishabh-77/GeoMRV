# GeoMRV API Contract (Draft)

This is a Phase 1 deliverable draft. It defines the minimal API surfaces expected by frontend + ML pipelines.

## Conventions

- Base URL (local): `http://localhost:8000`
- Content-Type: `application/json`
- IDs: UUID
- Dates: ISO-8601 (`YYYY-MM-DD`)

## Entities (high level)

- Project
- Boundary (GeoJSON polygon)
- Observation (NDVI/EVI/biomass metrics)
- Evidence Package (generated outputs + lineage)

## Endpoints (proposed)

### Projects
- `POST /projects`
  - Create a project
- `GET /projects/{project_id}`
  - Fetch a project
- `GET /projects`
  - List projects

### Boundaries
- `POST /projects/{project_id}/boundary`
  - Set/replace project boundary (GeoJSON)
- `GET /projects/{project_id}/boundary`
  - Get project boundary

### Observations
- `POST /projects/{project_id}/observations:compute`
  - Compute observations from satellite data (async recommended)
- `GET /projects/{project_id}/observations?start=YYYY-MM-DD&end=YYYY-MM-DD`
  - List observations

### Evidence Packages
- `POST /projects/{project_id}/evidence-packages`
  - Create evidence package for a period
- `GET /projects/{project_id}/evidence-packages/{package_id}`
  - Get package metadata

## Error model

- `400` validation error
- `401/403` auth error (Phase 2+)
- `404` not found
- `500` internal error

Response shape (recommended):

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "...",
    "details": {}
  }
}
```
