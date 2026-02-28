# GeoMRV API Contract (Draft)

This is a Phase 1 deliverable draft. It defines the minimal API surfaces expected by frontend + ML pipelines.

**Last updated:** 2026-02-28 (Task 1.4 – Feature Extraction endpoints added)

## Conventions

- Base URL (local): `http://localhost:8000`
- Content-Type: `application/json`
- IDs: UUID
- Dates: ISO-8601 (`YYYY-MM-DD`)

## Entities (high level)

- Project
- Boundary (GeoJSON polygon)
- Observation (NDVI/EVI/biomass metrics)
- Feature Set (trend, seasonality, anomalies, growth period, biomass proxy)
- Evidence Package (generated outputs + lineage)

## Endpoints (implemented)

### Projects ✅ (Task 1.1 – 1.2)
- `POST /api/v1/projects`
  - Create a project
- `GET /api/v1/projects/{project_id}`
  - Fetch a project
- `GET /api/v1/projects`
  - List projects
- `PUT /api/v1/projects/{project_id}`
  - Update a project
- `DELETE /api/v1/projects/{project_id}`
  - Delete a project

### Boundaries ✅ (Task 1.2)
- `POST /api/v1/projects/{project_id}/upload-boundary`
  - Upload project boundary (`.geojson` file)
- `GET /api/v1/projects/{project_id}/boundary`
  - Get project boundary

### Jobs & Observations ✅ (Task 1.3)
- `POST /api/v1/jobs`
  - Create a processing job (triggers background satellite data fetch)
- `GET /api/v1/jobs`
  - List jobs (optional `?project_id=` filter)
- `GET /api/v1/jobs/{job_id}`
  - Get job status
- `GET /api/v1/jobs/projects/{project_id}/observations`
  - List satellite observations (optional `?start_date=&end_date=`)

### Features ✅ (Task 1.4)
- `POST /api/v1/features/{project_id}/extract?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
  - Extract time-series features from stored observations
  - Calculates: trend (slope, R²), seasonality (peak/trough), growth period, anomalies, NDVI stats, biomass proxy
  - Persists results as a versioned `processing_logs` entry (`operation_type: feature_extraction`)
  - Returns: `{ project_id, processing_log_id, execution_time_ms, features: {...} }`
- `GET /api/v1/features/{project_id}/latest`
  - Get the most recently extracted feature set
  - Returns: `{ project_id, features: {...} }`
- `GET /api/v1/features/{project_id}/history?limit=20`
  - List all feature extraction runs for a project (newest first)
  - Returns: `{ project_id, count, history: [...] }`

### Evidence Packages ✅ (scaffold)
- `GET /api/v1/evidence`
  - List evidence packages (optional `?project_id=` filter)
- `GET /api/v1/evidence/{evidence_id}`
  - Get package metadata

### Health & Info ✅
- `GET /health`
  - Returns `{ "status": "healthy", "service": "geomrv-api" }`
- `GET /`
  - Returns service metadata + link to `/docs`

## Endpoints (proposed – not yet implemented)

### Verification (Task 1.5)
- `POST /api/v1/verification/{project_id}/verify?start_date=&end_date=`
  - Run deterministic verification rules on extracted features
  - Returns: flags, confidence score, pass/review/fail status

### Evidence Package Creation (Phase 3)
- `POST /api/v1/projects/{project_id}/evidence-packages`
  - Generate evidence package for a period

## Feature Set Schema (Task 1.4)

The feature extraction endpoint returns the following structure inside `features`:

```json
{
  "project_id": "uuid",
  "period_start": "YYYY-MM-DD",
  "period_end": "YYYY-MM-DD",
  "total_observations": 15,
  "clear_observations": 12,
  "cloud_cover_threshold": 30.0,
  "extracted_at": "ISO-8601 timestamp",
  "trend": {
    "trend_slope": 0.002,
    "slope_per_year": 0.024,
    "r_squared": 0.85
  },
  "seasonality": {
    "peak_month": 9,
    "trough_month": 3,
    "peak_ndvi": 0.72,
    "trough_ndvi": 0.25,
    "seasonal_amplitude": 0.47
  },
  "growth_period": {
    "growth_start": "YYYY-MM-DD",
    "growth_end": "YYYY-MM-DD",
    "growth_days": 180,
    "ndvi_threshold": 0.45
  },
  "anomalies": ["YYYY-MM-DD", "..."],
  "ndvi_stats": {
    "mean": 0.48,
    "std": 0.12,
    "min": 0.22,
    "max": 0.73,
    "median": 0.47,
    "count": 12
  },
  "biomass_stats": {
    "mean": 32.5,
    "std": 8.1,
    "min": 16.0,
    "max": 45.0
  }
}
```

## Error model

- `400` validation error
- `401/403` auth error (Phase 2+)
- `404` not found
- `422` unprocessable (e.g., insufficient observations for feature extraction)
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
