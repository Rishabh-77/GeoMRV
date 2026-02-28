# Development Checklist

Use this checklist to confirm a dev environment is ready.

## Repo + Python
- [ ] Repo cloned
- [ ] `.venv` created and activated
- [ ] `pip install -r requirements.txt` completed

## Environment variables
- [ ] `.env` created from `.env.example`
- [ ] PostgreSQL vars set (`POSTGRES_HOST/DB/USER/PASSWORD`)
- [ ] Azure Storage vars set (`AZURE_STORAGE_CONNECTION_STRING` or account+key)
- [ ] Earth Engine configured (credentials + optional project)

## Connectivity checks
- [ ] `python tests/test_setup.py` passes

## Database
- [ ] PostGIS available (`CREATE EXTENSION postgis` succeeds)
- [ ] Baseline schema applied (optional): `database/schema.sql`

## Tests + formatting
- [ ] `pytest -v` runs
- [ ] `black --check src tests` passes

## CI
- [ ] Opened a PR to `main`/`develop`
- [ ] All required checks pass before merge
