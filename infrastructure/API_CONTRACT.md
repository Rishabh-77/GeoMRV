# GeoMRV API Contract (Draft)

This is a Phase 1 deliverable draft. It defines the minimal API surfaces expected by frontend + ML pipelines.

**Last updated:** 2026-02-28 (Task 1.5 – Verification Rules endpoints added)

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

### Verification ✅ (Task 1.5)
- `POST /api/v1/verification/{project_id}/verify?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
  - Run deterministic verification rules on extracted features
  - Applies 7 rules: insufficient data, high cloud cover, no growth, anomalies, vegetation loss, data gap, low trend confidence
  - Computes confidence score (0–100) and overall status (PASS / REVIEW_REQUIRED / FAIL)
  - Persists results as a `processing_logs` entry (`operation_type: verification`)
  - Returns: `{ project_id, processing_log_id, confidence_score, overall_status, flag_count, verification_flags: [...] }`
- `GET /api/v1/verification/{project_id}/latest`
  - Get the most recent verification result
  - Returns: `{ project_id, verification: { flags, confidence_score, overall_status, ... } }`
- `GET /api/v1/verification/{project_id}/history?limit=20`
  - List all verification runs for a project (newest first)
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
  "max_observation_gap_days": 45,
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

## Verification Result Schema (Task 1.5)

The verification endpoint returns the following structure:

```json
{
  "project_id": "uuid",
  "processing_log_id": "uuid",
  "execution_time_ms": 150,
  "confidence_score": 85.0,
  "overall_status": "PASS",
  "flag_count": 1,
  "verification_flags": [
    {
      "rule_id": "R4_anomalous_spike",
      "rule_name": "Anomalous Values Detected",
      "risk_level": "medium",
      "description": "Found 2 anomalous observation(s)",
      "affected_period": "2025-03-15, 2025-06-20",
      "recommended_action": "Review satellite data quality; may indicate cloud shadows or sun glint"
    }
  ],
  "features_summary": {
    "period_start": "2025-01-01",
    "period_end": "2025-12-31",
    "total_observations": 20,
    "clear_observations": 18
  }
}
```

### Verification Rules Reference

| Rule ID | Name | Risk Level | Trigger Condition |
|---------|------|------------|-------------------|
| R1 | Insufficient Observations | MEDIUM | < 12 clear observations |
| R2 | High Cloud Cover | MEDIUM | > 40% of scenes rejected |
| R3 | No Growth Detected | HIGH | Trend slope ≤ 0 |
| R4 | Anomalous Values | MEDIUM | ≥ 1 anomalous date |
| R5 | Vegetation Loss | CRITICAL | NDVI swing > 0.5 (min < 0.2, max > 0.7) |
| R6 | Data Gap | MEDIUM | > 60 days between observations |
| R7 | Low Trend Confidence | MEDIUM | R² < 0.3 |

### Confidence Scoring

- Starts at 100
- −2 per missing observation below 12
- Up to −25 for low R² (linear 0 → 0.5)
- Per-flag: LOW −5, MEDIUM −15, HIGH −30, CRITICAL −50
- Overall: **PASS** (≥ 70), **REVIEW_REQUIRED** (40–69), **FAIL** (< 40)

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
