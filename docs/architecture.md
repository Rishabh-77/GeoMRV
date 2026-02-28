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
* polygons
* feature_timeseries
* run_metadata
* quality_flags

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

Outputs:

* pass
* review
* fail

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
