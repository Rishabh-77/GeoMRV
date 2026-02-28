# GeoMRV

GeoMRV is a geospatial Monitoring, Reporting, and Verification (MRV) project focused on satellite-based vegetation monitoring (e.g., Sentinel-2 NDVI via Google Earth Engine) with an Azure-backed deployment target.

This repository currently contains Phase 0 foundations (CI, environment setup, satellite integration utilities, and documentation) and is ready to start Phase 1 backend development.

## Quick start (local dev)

### Prerequisites
- Python 3.11+
- Git
- PostgreSQL (or Azure Database for PostgreSQL) + PostGIS available
- Google Earth Engine account access (for satellite features)

### Setup
1. Create a virtual environment:
   - `python -m venv .venv`

2. Activate it:
   - Git Bash (Windows): `source .venv/Scripts/activate`
   - PowerShell: `\.venv\Scripts\Activate.ps1`

3. Install dependencies:
   - `python -m pip install --upgrade pip`
   - `pip install -r requirements.txt`

4. Configure environment variables:
   - Copy `.env.example` → `.env`
   - Fill in values for PostgreSQL, Azure Storage, and (optionally) Earth Engine.

5. Validate connections (DB + Azure + GEE):
   - `python tests/test_setup.py`

## Common commands

- Run unit tests:
  - `pytest -v`

- Format Python code:
  - `black src tests`

- Check formatting only (CI-style):
  - `black --check src tests`

- Lint (syntax/undefined-name focused, matching CI):
  - `flake8 src tests --count --select=E9,F63,F7,F82 --show-source --statistics`

## CI/CD

GitHub Actions workflow: `.github/workflows/ci.yml`

Current CI jobs:
- Lint & Format check (flake8 + black)
- Unit tests (pytest, with coverage)
- DB schema validation (runs `database/schema.sql` if present)

## Repo structure

See current vs intended structure in: `currentinfra.md`.

Key paths:
- `src/satellite_services/`: Earth Engine client + NDVI + timelapse utilities
- `tests/`: integration and environment verification scripts
- `docs/development_lifecycle/`: phased plan and execution docs
- `database/schema.sql`: baseline schema for Postgres/PostGIS

## Security notes

- Do not commit `.env` (it contains secrets). Use `.env.example` as a template.
- If secrets are ever pasted into issues/PRs/logs, rotate them in Azure/Postgres.
