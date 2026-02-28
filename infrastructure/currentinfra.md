# Current Infra / Repo Structure

This doc helps keep the current repository structure aligned with the intended Phase 0+ structure.

## Current repository structure (as of 2026-02-28)

```
GeoMRV/
├── .github/
│   └── workflows/
│       └── ci.yml
├── database/
│   └── schema.sql
├── docs/
│   ├── development_lifecycle/
│   │   ├── azure_cost_estimation.md
│   │   ├── EXECUTIVE_SUMMARY.md
│   │   ├── india_specific_enhancements.md
│   │   ├── phase0_foundation.md
│   │   ├── phase1_backend_engine.md
│   │   ├── phase2_ml_scoring.md
│   │   ├── phase3_evidence_packaging.md
│   │   ├── phase4_frontend_integration.md
│   │   ├── phase5_testing_launch.md
│   │   ├── QUICK_REFERENCE.md
│   │   └── README.md
│   ├── architecture.md
│   └── idea.md
├── infrastructure/
│   └── azure_resource_setup.md
├── src/
│   └── satellite_services/
│       ├── __init__.py
│       ├── earth_engine_client.py
│       ├── ndvi_calculator.py
│       ├── README.md
│       └── timelapse_exporter.py
├── tests/
│   ├── __init__.py
│   ├── test_satellite_integration.py
│   └── test_setup.py
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
└── setup.py
```

## Intended structure (from Phase 0 plan)

```
geomrv/
├── src/
│   ├── api/
│   ├── satellite_services/
│   ├── feature_extraction/
│   ├── ml_models/
│   ├── verification_rules/
│   └── evidence_generation/
├── database/
│   ├── schema.sql
│   ├── migrations/
│   │   └── 001_initial_schema.sql
│   └── README.md
├── tests/
├── infrastructure/
│   ├── terraform/               (optional)
│   └── docker/                  (optional)
├── docs/
│   └── development_lifecycle/
├── requirements.txt
├── setup.py
├── .github/workflows/
├── .env.example
├── .gitignore
└── README.md
```

## Alignment summary

Already present (✅):
- `README.md` (root)
- `.github/workflows/ci.yml`
- `database/schema.sql`
- `src/satellite_services/*`
- `tests/` (includes `test_setup.py`)
- `.env.example`, `.gitignore`, `requirements.txt`

Not created yet (⏳) — add when starting Phase 1+:
- `src/api/`
- `src/feature_extraction/`
- `src/ml_models/`
- `src/verification_rules/`
- `src/evidence_generation/`
- `database/migrations/001_initial_schema.sql`
- `database/README.md`
- Optional infra scaffolding: `infrastructure/terraform/`, `infrastructure/docker/`

## What to create next (recommended order)

1. Backend skeleton: `src/api/` (FastAPI app + routers)
2. Database docs + migrations: `database/README.md` and `database/migrations/`
3. Minimal API contract alignment: update `API_CONTRACT.md` as endpoints finalize
