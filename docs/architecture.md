# GeoMRV – System Architecture

## 1. Architectural Goals

* low operational cost
* reproducible scientific workflows
* audit‑ready outputs
* minimal infrastructure complexity
* scalable to multiple projects

---

## 2. High‑Level Architecture

User Interface
→ API and Control Layer
→ Job Orchestration
→ Remote Sensing Processing
→ Feature Store
→ ML and Verification Layer
→ Evidence and Audit Package Layer

---

## 3. Component Overview

### 3.1 Frontend Dashboard

Responsibilities:

* project creation
* polygon drawing and upload
* run triggering
* results visualization
* audit package download

Technology:

* React
* static hosting

---

### 3.2 API and Control Layer

Responsibilities:

* authentication
* project and polygon management
* run lifecycle management
* access control

Technology:

* FastAPI

Main endpoints:

* create project
* upload polygon
* start run
* get run status
* get results
* generate audit package

---

### 3.3 Job Orchestration Service

Responsibilities:

* submit processing jobs to remote sensing platform
* track job status
* retry failed jobs
* store processing metadata

This service does not perform image processing.

---

### 3.4 Remote Sensing Processing Layer

Responsibilities:

* cloud masking
* compositing
* vegetation index calculation
* seasonal aggregation
* long‑term trend extraction

Output format:

* polygon‑level tabular features

No raster data is stored by the platform.

---

### 3.5 Feature Store

Responsibilities:

* store geometries
* store extracted time‑series features
* store run metadata
* store data quality indicators

Technology:

* PostgreSQL with spatial support

Core tables:

* projects
* boundaries (with PostGIS geometry + GeoJSON)
* observations (NDVI, EVI, biomass, cloud cover per date)
* processing_logs (job lifecycle + feature extraction outputs as JSONB)
* evidence_packages
* lineage_metadata

### 3.5.1 Feature Extraction Engine (Task 1.4 – Implemented)

Responsibilities:

* read satellite observations from the database
* filter by cloud cover threshold (default < 30%)
* compute standardised time‑series features:
  * **Trend** – linear regression slope on smoothed NDVI, R², annualised slope
  * **Seasonality** – peak / trough months, peak / trough NDVI, seasonal amplitude
  * **Growth period** – consecutive period above mean NDVI, duration in days
  * **Anomaly detection** – dates where NDVI deviates > 2σ from rolling mean
  * **NDVI statistics** – mean, std, min, max, median, count
  * **Biomass proxy** – linear estimate from NDVI + EVI (placeholder coefficients)
* persist feature sets as versioned processing_logs entries
* expose features via REST API for downstream consumers

Components:

* `FeatureCalculator` – stateless static methods (no DB dependency)
* `PipelineFeatureExtractor` – reads observations from DB, runs all calculators
* `FeatureStore` – read/write feature sets to `processing_logs` table

Location:

* `src/feature_extraction/feature_calculator.py`
* `src/feature_extraction/feature_store.py`
* `src/api/routers/features.py`

API Endpoints:

* `POST /api/v1/features/{project_id}/extract` – run extraction
* `GET  /api/v1/features/{project_id}/latest` – get last feature set
* `GET  /api/v1/features/{project_id}/history` – list all extraction runs

---

### 3.6 Machine Learning Layer

Responsibilities:

* score feature vectors
* predict growth and stability classes
* compute confidence and uncertainty metrics

Model types:

* gradient boosting
* random forest
* regression models

Inputs:

* seasonal statistics
* trend slopes
* anomaly indicators

Outputs:

* biomass or vegetation change class
* confidence score
* expected variance

---

### 3.7 Verification Rules Layer

Responsibilities:

* apply deterministic plausibility checks
* apply temporal consistency checks
* apply area and geometry consistency checks
* enforce data quality thresholds

Rules implemented (Task 1.5):

* R1 – Insufficient Observations (< 12 clear scenes → MEDIUM)
* R2 – High Cloud Cover (> 40 % rejection rate → MEDIUM)
* R3 – No Growth Detected (trend slope ≤ 0 → HIGH)
* R4 – Anomalous Values (≥ 1 anomalous date → MEDIUM)
* R5 – Vegetation Loss (NDVI swing > 0.5 with min < 0.2 and max > 0.7 → CRITICAL)
* R6 – Data Gap (> 60 days between observations → MEDIUM)
* R7 – Low Trend Confidence (R² < 0.3 → MEDIUM)

Confidence scoring:

* Starts at 100, deducts per-flag penalties and data quality adjustments
* Overall status: PASS (≥ 70), REVIEW_REQUIRED (40–69), FAIL (< 40)

Outputs:

* pass
* review
* fail

Components:

* `VerificationRulesEngine` – stateless rule evaluator + confidence scoring
* `RuleStore` – read/write verification results to `processing_logs` table

Location:

* `src/verification_rules/rules_engine.py`
* `src/verification_rules/rule_store.py`
* `src/api/routers/verification.py`

API Endpoints:

* `POST /api/v1/verification/{project_id}/verify` – run verification
* `GET  /api/v1/verification/{project_id}/latest` – get last result
* `GET  /api/v1/verification/{project_id}/history` – list all runs

This layer is independent of the ML model.

---

### 3.8 Evidence and Lineage Store

Responsibilities:

* store processing parameters
* store script and model versions
* store logs
* store generated charts and summaries

Technology:

* object storage

---

### 3.9 Audit Package Generator

Responsibilities:

* compile run outputs
* compile processing description
* embed charts and tables
* produce PDF or ZIP evidence bundle

---

## 4. Security and Access Control

* token‑based authentication
* role‑based permissions
* project‑level isolation

---

## 5. Observability and Logging

For every run the system records:

* user
* timestamp
* input geometry hash
* processing script version
* model version
* output checksums

---

## 6. End‑to‑End Data Flow

1. User creates project
2. User uploads or draws polygons
3. User starts monitoring run
4. Job orchestrator submits remote sensing job
5. Remote sensing platform generates polygon‑level features
6. Features stored in feature store
7. ML scoring is applied
8. Verification rules are evaluated
9. Results are stored
10. Audit package is generated

---

## 7. Deployment Architecture

Compute:

* API service
* background worker

Data services:

* relational spatial database
* object storage

The remote sensing processing runs on an external geospatial platform.

---

## 8. MVP Deployment

* single API service
* single worker service
* one database instance
* one storage account

---

## 9. Scaling Strategy

* separate worker pool
* asynchronous job queue
* multiple concurrent projects
* horizontal API scaling

---

## 10. Reproducibility Strategy

* immutable processing scripts
* versioned ML models
* stored configuration snapshots
* deterministic feature generation

---

## 11. Key Non‑Functional Requirements

* traceability
* reproducibility
* explainability
* audit readiness
* low operational overhead
