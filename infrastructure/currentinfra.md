# Current Infra / Repo Structure

This doc helps keep the current repository structure aligned with the intended Phase 0+ structure.

## Current repository structure (as of 2026-03-01)

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
│   │   ├── DEVELOPMENT_CHECKLIST.md
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
│   ├── architecture_diagram.md
│   ├── idea.md
│   └── india_data_sources.md
├── infrastructure/
│   ├── API_CONTRACT.md
│   ├── azure_resource_setup.md
│   └── currentinfra.md
├── src/
│   ├── __init__.py
│   ├── api/                              # Tasks 1.1 – 2.4
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── schemas.py
│   │   ├── models.py
│   │   ├── database.py
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── projects.py
│   │   │   ├── jobs.py
│   │   │   ├── evidence.py
│   │   │   ├── features.py              # Task 1.4
│   │   │   ├── ml_scoring.py            # Tasks 2.3 – 2.4 integration
│   │   │   └── verification.py          # Task 1.5
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── project_service.py
│   │   │   ├── job_service.py
│   │   │   └── processing.py
│   │   └── utils/
│   │       └── __init__.py
│   ├── feature_extraction/               # Task 1.4
│   │   ├── __init__.py
│   │   ├── feature_calculator.py
│   │   └── feature_store.py
│   ├── ml_models/                        # Tasks 2.1 – 2.4
│   │   ├── __init__.py
│   │   ├── data_preparation.py
│   │   ├── synthetic_data_generator.py
│   │   ├── model_trainer.py
│   │   ├── training_pipeline.py
│   │   ├── inference_service.py
│   │   ├── model_registry.py
│   │   └── registry_service.py
│   ├── verification_rules/               # Task 1.5
│   │   ├── __init__.py
│   │   ├── rules_engine.py
│   │   └── rule_store.py
│   └── satellite_services/               # Phase 0 + Task 1.3
│       ├── __init__.py
│       ├── data_fetcher.py
│       ├── earth_engine_client.py
│       ├── ndvi_calculator.py
│       ├── README.md
│       └── timelapse_exporter.py
├── tests/
│   ├── __init__.py
│   ├── test_inference_service.py
│   ├── test_jobs.py
│   ├── test_projects.py
│   ├── test_satellite_fetcher.py
│   ├── test_satellite_integration.py
│   ├── test_setup.py
│   ├── test_verification_rules.py
│   └── fixtures/
│       └── sample.geojson
├── .env
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
├── setup.py
└── SETUP.md
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


1. **Intended Structure from phase 1** (✅ largely achieved)
   ```
   src/api/
   ├── main.py                    ✅
   ├── config.py                  ✅
   ├── schemas.py                 ✅
   ├── models.py                  ✅
   ├── database.py                ✅
   ├── routers/
   │   ├── projects.py            ✅
   │   ├── jobs.py                ✅
   │   ├── evidence.py            ✅
   │   ├── features.py            ✅  (Task 1.4 addition)
   │   ├── ml_scoring.py          ✅  (Tasks 2.3 – 2.4 addition)
   │   └── verification.py        ✅  (Task 1.5 addition)
   ├── services/
   │   ├── project_service.py     ✅
   │   ├── job_service.py         ✅
   │   └── processing.py          ✅
   └── utils/
       └── __init__.py            ✅
   ```

2. **Feature Extraction module** (✅ Task 1.4)
   ```
   src/feature_extraction/
   ├── __init__.py
   ├── feature_calculator.py      # FeatureCalculator + PipelineFeatureExtractor
   └── feature_store.py           # FeatureStore (read/write via processing_logs)
   ```

3. **Verification Rules module** (✅ Task 1.5)
   ```
   src/verification_rules/
   ├── __init__.py
   ├── rules_engine.py      # VerificationRulesEngine (7 rules + confidence scoring)
   └── rule_store.py         # RuleStore (read/write via processing_logs)
   ```

4. **ML Models module** (✅ Tasks 2.1 – 2.4)
   ```
   src/ml_models/
   ├── data_preparation.py      # TrainingDataPreparator + FEATURE_COLUMNS
   ├── synthetic_data_generator.py
   ├── model_trainer.py         # Growth + Biomass model classes
   ├── training_pipeline.py     # End-to-end training + registry registration/activation
   ├── inference_service.py     # Registry-aware model loading + scoring
   ├── model_registry.py        # SQLAlchemy model for registry table
   └── registry_service.py      # Register / activate / deprecate / list / get_active
   ```

5. **Evidence Generation module** (✅ Task 3.1 – schema & validation)
   ```
   src/evidence_generation/
   ├── __init__.py              # Public exports
   ├── package_schema.py        # EvidencePackage + DataSource + ProcessingStep + VerificationResult + Feature
   └── package_validator.py     # EvidencePackageValidator + ValidationReport
   ```
## Alignment summary

Already present (✅):
- `README.md` (root)
- `.github/workflows/ci.yml`
- `database/schema.sql`
- `src/satellite_services/*` (Phase 0 + Task 1.3)
- `src/api/*` (Tasks 1.1 – 1.3)
- `src/feature_extraction/*` (Task 1.4)
- `src/verification_rules/*` (Task 1.5)
- `src/ml_models/*` (Tasks 2.1 – 2.4, including runtime registry integration)
- `src/evidence_generation/*` (Task 3.1 – schema & validation)
- `tests/` (test_setup, test_projects, test_jobs, test_satellite_fetcher, test_verification_rules, test_inference_service, test_package_schema)
- `.env.example`, `.gitignore`, `requirements.txt`

Not created yet (⏳) — add when continuing Phase 3:
- `src/evidence_generation/visualizations.py` ← Task 3.2
- `src/evidence_generation/report_generator.py` ← Task 3.2
- `src/evidence_generation/package_assembly.py` ← Task 3.3
- `src/evidence_generation/storage_service.py` ← Task 3.3
- `database/migrations/001_initial_schema.sql`
- `database/README.md`
- Optional infra scaffolding: `infrastructure/terraform/`, `infrastructure/docker/`

## What to create next (recommended order)

1. Report visualizations + PDF generator: `src/evidence_generation/visualizations.py`, `report_generator.py` (Task 3.2)
2. Package assembly + storage: `src/evidence_generation/package_assembly.py`, `storage_service.py` (Task 3.3)
3. Database docs + migrations: `database/README.md` and `database/migrations/`
4. Optional infra scaffolding: `infrastructure/terraform/`, `infrastructure/docker/`
