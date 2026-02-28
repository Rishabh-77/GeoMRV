# GeoMRV Development Lifecycle - Complete Roadmap

**Project:** GeoMRV (Digital Carbon Verification Platform for India)  
**Duration:** 4–5 months (16 weeks)  
**Target:** MVP delivering remote sensing-based biomass verification for Indian carbon projects  
**Tech Stack:** FastAPI, React, PostgreSQL+PostGIS, Azure Cloud, Python ML stack

---

## 📅 Development Timeline Overview

```
PHASE 0: Foundation & Dependencies (Weeks 1–2)
    └─ Azure setup, Database, CI/CD, Satellite integration

PHASE 1: Core Backend Engine (Weeks 3–6) [4 weeks]
    └─ API layer, Remote sensing fetcher, Feature extraction, Verification rules

PHASE 2: ML Scoring Layer (Weeks 7–9) [3 weeks]
    └─ Model training, Confidence scoring, Risk flagging

PHASE 3: Evidence & Audit Packaging (Weeks 10–11) [2 weeks]
    └─ PDF generation, Visualizations, Lineage tracking

PHASE 4: Frontend & Integration (Weeks 12–13) [2 weeks]
    └─ React dashboard, Project upload, Static hosting

PHASE 5: Testing, Documentation & Launch (Weeks 14–16) [3 weeks]
    └─ Unit testing, API docs, Deployment, Launch prep
```

---

## 🗂️ Folder Structure

```
development_lifecycle/
├── README.md                          (this file)
├── phase0_foundation.md               (Azure setup, database, external dependencies)
├── phase1_backend_engine.md           (API, remote sensing, feature extraction)
├── phase2_ml_scoring.md               (ML models, confidence scoring)
├── phase3_evidence_packaging.md       (Evidence generation, reports, lineage)
├── phase4_frontend_integration.md     (Dashboard, UI, testing)
├── phase5_testing_launch.md           (Testing strategy, documentation, deployment)
├── azure_cost_estimation.md           (Budget breakdown & free tier strategy)
├── india_specific_enhancements.md     (Regional calibration, data sources)
└── deployment_runbook.md              (Step-by-step production deployment)
```

---

## 🎯 What Each Phase Delivers

| Phase | Deliverable | Status |
|-------|-------------|--------|
| 0 | Working Azure environment, database schema, CI/CD pipeline | Foundation ready |
| 1 | Functional backend API, satellite data ingestion, feature extraction | Core engine ready |
| 2 | ML model pipeline, confidence scoring system | Predictions working |
| 3 | Audit-ready evidence packages with visualizations | Reports generated |
| 4 | React web dashboard, project management interface | UI interactive |
| 5 | Complete test suite, documentation, deployment runbook | Launch ready |

---

## 💡 Key Principles

1. **Azure-First:** Use Azure Student Pack resources ($100/month credits) for all infrastructure
2. **Reproducibility:** Every processing step logged with metadata for audit trails
3. **India-Focused:** Region-specific satellite data sources, climate calibration, language support
4. **MVP Scope:** Minimize external dependencies; use free/low-cost data sources
5. **Audit-Ready:** Every output designed for verification partner acceptance

---

## 🚀 Quick Navigation

- **[Phase 0: Foundation & Dependencies](phase0_foundation.md)** — Azure environment setup, database, CI/CD
- **[Phase 1: Backend Engine](phase1_backend_engine.md)** — API, remote sensing, feature extraction
- **[Phase 2: ML Scoring](phase2_ml_scoring.md)** — Models, confidence scoring, risk flags
- **[Phase 3: Evidence Packaging](phase3_evidence_packaging.md)** — PDF generation, audit lineage
- **[Phase 4: Frontend & Integration](phase4_frontend_integration.md)** — Dashboard, UI, end-to-end testing
- **[Phase 5: Testing & Launch](phase5_testing_launch.md)** — Quality assurance, documentation, deployment
- **[Azure Cost Estimation](azure_cost_estimation.md)** — Budget & free tier strategy
- **[India-Specific Enhancements](india_specific_enhancements.md)** — Regional calibration, data sources
- **[Deployment Runbook](deployment_runbook.md)** — Production deployment steps

---

## ✅ Success Criteria (MVP Launch)

✅ At least one real or mock Indian carbon project successfully processed  
✅ Evidence package generated and audit-ready  
✅ All processing steps fully traceable and reproducible  
✅ Backend and frontend deployed on Azure and accessible  
✅ Documentation complete and deployment runbook validated  
✅ Cost estimate < $200/month for single-project operation  

---

## 📋 Getting Started

1. Read [Phase 0: Foundation & Dependencies](phase0_foundation.md) first
2. Follow the Azure setup steps
3. Create local development environment
4. Work through each phase sequentially
5. Complete testing and launch prep before going live

**Current Status:** Documentation complete | Implementation ready | Azure Student Pack required

---

*Last Updated: Feb 27, 2026*
