# GeoMRV Setup Guide

This guide is for new developers joining the project.

## 1) Clone and install

- Create venv:
  - `python -m venv .venv`
- Activate:
  - Git Bash (Windows): `source .venv/Scripts/activate`
  - PowerShell: `\.venv\Scripts\Activate.ps1`
- Install dependencies:
  - `python -m pip install --upgrade pip`
  - `pip install -r requirements.txt`

## 2) Configure environment

- Copy `.env.example` → `.env`
- Fill values for:
  - PostgreSQL: `POSTGRES_HOST`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
  - Azure Storage: `AZURE_STORAGE_CONNECTION_STRING` (preferred) or account+key
  - Earth Engine: `GOOGLE_EARTH_ENGINE_CREDENTIALS` and optional `GEE_PROJECT`

Notes:
- Keep `.env` local only. Do not commit.

## 3) Database (Postgres + PostGIS)

- Ensure PostGIS extension exists on the target database.
- Apply baseline schema (optional if already deployed):
  - `psql -h <host> -U <user> -d <db> -f database/schema.sql`

## 4) Validate all connections

Run:
- `python tests/test_setup.py`

Expected output includes:
- `✅ PostgreSQL connected`
- `✅ Azure Storage connected`
- `✅ Google Earth Engine authenticated`

## 5) Run tests + formatting

- Tests: `pytest -v`
- Format: `black src tests`
- Lint: `flake8 src tests --count --select=E9,F63,F7,F82 --show-source --statistics`

## 6) CI notes

CI runs on pull requests into `main`/`develop`:
- lint/format check
- unit tests
- DB schema validation

See: `docs/development_lifecycle/phase0_foundation.md`
