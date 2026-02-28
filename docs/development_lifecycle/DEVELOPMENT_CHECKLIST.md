# Development Checklist

Use this checklist to confirm a dev environment is ready and track implementation progress.

## Repo + Python
- [x] Repo cloned
- [x] `.venv` created and activated
- [x] `pip install -r requirements.txt` completed

## Environment variables
- [x] `.env` created from `.env.example`
- [x] PostgreSQL vars set (`POSTGRES_HOST/DB/USER/PASSWORD`)
- [x] Azure Storage vars set (`AZURE_STORAGE_CONNECTION_STRING` or account+key)
- [x] Earth Engine configured (credentials + optional project)

## Connectivity checks
- [x] `python tests/test_setup.py` passes

## Database
- [x] PostGIS available (`CREATE EXTENSION postgis` succeeds)
- [x] Baseline schema applied: `database/schema.sql`

## Tests + formatting
- [x] `pytest -v` runs
- [ ] `black --check src tests` passes

## CI
- [ ] Opened a PR to `main`/`develop`
- [ ] All required checks pass before merge

---

## Phase 1 Implementation Progress

### Task 1.1: FastAPI Backend Scaffolding ✅
- [x] `src/api/main.py` – FastAPI app with CORS, health check, root endpoint
- [x] `src/api/config.py` – `pydantic-settings` config from `.env`
- [x] `src/api/schemas.py` – Pydantic request/response models
- [x] `src/api/models.py` – SQLAlchemy ORM models (Project, Job, Boundary, Observation, EvidencePackage)
- [x] `src/api/database.py` – Engine, session, `get_db` dependency
- [x] Health check at `/health` returns `{"status":"healthy"}`
- [x] API docs accessible at `/docs`

### Task 1.2: Project Management Endpoints ✅
- [x] `src/api/routers/projects.py` – Full CRUD (`POST`, `GET`, `GET/{id}`, `PUT/{id}`, `DELETE/{id}`)
- [x] `src/api/services/project_service.py` – Business logic layer
- [x] Boundary upload: `POST /api/v1/projects/{id}/upload-boundary` (`.geojson`)
- [x] Boundary retrieval: `GET /api/v1/projects/{id}/boundary`
- [x] `tests/test_projects.py` – 15 tests passing

### Task 1.3: Satellite Data Fetching ✅
- [x] `src/satellite_services/data_fetcher.py` – `SatelliteDataFetcher` (Sentinel-2 via Earth Engine)
- [x] `src/api/routers/jobs.py` – Job CRUD + observation listing
- [x] `src/api/services/job_service.py` – Background job processing (pending → running → completed)
- [x] NDVI/EVI calculation verified with real Sentinel-2 data
- [x] Observations persisted to `observations` table
- [x] `tests/test_jobs.py`, `tests/test_satellite_fetcher.py`

### Task 1.4: Feature Extraction Engine ✅
- [x] `src/feature_extraction/__init__.py` – Package init
- [x] `src/feature_extraction/feature_calculator.py` – `FeatureCalculator` (6 static methods) + `PipelineFeatureExtractor`
- [x] `src/feature_extraction/feature_store.py` – `FeatureStore` (versioned read/write via `processing_logs`)
- [x] `src/api/routers/features.py` – 3 endpoints: extract, latest, history
- [x] Feature schemas added to `src/api/schemas.py`
- [x] Router registered in `src/api/main.py`
- [x] `scipy>=1.11` added to `requirements.txt`
- [x] All imports verified, synthetic data tests pass

### Task 1.5: Verification Rules Engine ⬜
- [ ] `src/verification_rules/rules_engine.py`
- [ ] `src/verification_rules/rule_store.py`
- [ ] `src/api/routers/verification.py`
- [ ] 6+ deterministic verification rules
- [ ] Confidence scoring algorithm
- [ ] `tests/test_verification_rules.py`
