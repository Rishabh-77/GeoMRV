# Phase 0: Foundation & Dependencies (Weeks 1–2)

**Duration:** 2 weeks  
**Goal:** Establish Azure infrastructure, database, CI/CD pipeline, and external satellite data integration  
**Deliverable:** Fully functional development environment ready for backend engineering

---

## 📊 Phase Overview

This phase sets up all foundational components that the backend, ML, and frontend will depend on. Everything must be operational before Phase 1 begins.

### What Gets Built
- Azure resource group with all required services
- PostgreSQL database with PostGIS extension (geospatial support)
- Azure Storage (Blob Storage for evidence packages)
- CI/CD pipeline (GitHub Actions or Azure DevOps)
- Connection to satellite data source (Sentinel-2 via Google Earth Engine)
- Visual timelapse output for frontend (Sentinel-2 via Google Earth Engine)
- Local development environment
- Project folder structure and version control

### What This Phase Enables
- Backend team can begin API development in Week 3
- Database is ready for data models
- Remote sensing integration is validated
- Automated testing and deployment works

---

## 🎯 Tasks Breakdown

### Task 0.1: Azure Resource Group & Core Setup (Days 1–3)

**Objective:** Create Azure account, set up resource group, and prepare billing

**Steps:**

1. **Access Azure Student Pack**
   - Go to [Azure for Students](https://azure.microsoft.com/en-us/free/students/)
   - Sign in with your institution email
   - Activate $100/month credits (no credit card required initially)
   - Verify account and subscription

2. **Create Resource Group**
   - Open Azure Portal → Resource Groups
   - Create new RG named `geomrv-dev`
   - Region: `Southeast Asia` or `Central India` (for India-focused project)
   - Document subscription ID and RG name

3. **Create Azure Storage Account**
   - Resource type: Storage Account
   - Name: `geomrvstoragedev` (must be globally unique, lowercase)
   - Performance: Standard (sufficient for MVP)
   - Redundancy: Locally Redundant Storage (LRS) — low cost
   - Create blob container named `evidence-packages`
   - Create container named `satellite-data-cache`
   - Document storage account name and keys

4. **Create Key Vault**
   - Resource type: Key Vault
   - Name: `geomrv-kv`
   - Region: Same as RG
   - Purpose: Store API keys, database passwords, satellite service credentials
   - Enable soft delete and purge protection

5. **Enable Monitoring**
   - Create Application Insights resource in same RG
   - Name: `geomrv-insights`
   - Application type: Python

**Deliverables:**
- [x] Resource group created with all resources in same region
   - Verified resource group: `geomrv-dev` in `Central India`.
   - Verified core resources are deployed under same RG.
- [x] Storage account with containers ready
   - Verified storage account: `geomrvstoragedev`.
   - Verified containers: `evidence-packages`, `satellite-data-cache`.
- [x] Key Vault configured
   - Verified Key Vault: `geomrv-kv` using Azure RBAC model.
   - Verified secret naming convention documented and aligned with env mapping.
- [x] Application Insights instance
   - Verified Application Insights resource: `geomrv-insights`.
   - Verified connection string captured for secure usage via Key Vault mapping.
- [x] Azure credentials documented (securely)
   - Verified setup documentation in `infrastructure/azure_resource_setup.md`.
   - Verified placeholder-based template in `.env.example` (no hardcoded secrets).

**Files to Create:**
- `infrastructure/azure_resource_setup.md` (document all resource names and IDs)
- `.env.example` (template for environment variables)

---

### Task 0.2: PostgreSQL Database with PostGIS (Days 3–5)

**Objective:** Set up cloud database with spatial extensions for geospatial features

**Steps:**

1. **Create PostgreSQL Server**
   - Resource type: Azure Database for PostgreSQL - Single Server
   - Server name: `geomrv-postgres-dev`
   - Admin username: `geomrvadmin`
   - Password: Generate strong password → store in Key Vault
   - Backup retention: 7 days (default)
   - Version: PostgreSQL 13 or later

2. **Configure Firewall & Access**
   - Allow "Allow access to Azure services" = ON
   - Add firewall rule for your IP (for local development)
   - Create flexible auth: Enable "Require secure transport"

3. **Create Databases**
   - Connect via Azure Cloud Shell or pgAdmin
   - Create 3 databases:
     - `geomrv_dev` (development)
     - `geomrv_test` (testing)
     - `geomrv_prod` (production, for later)

4. **Enable PostGIS Extension**
   ```sql
   -- Connect to each database and run:
   CREATE EXTENSION IF NOT EXISTS postgis;
   CREATE EXTENSION IF NOT EXISTS uuid-ossp;
   ```

5. **Create Initial Schema**
   - Run the database schema initialization script
   - Tables: `projects`, `boundaries`, `observations`, `processing_logs`, `lineage_metadata`, `evidence_packages`
   - See **Schema Definition** section below

**Deliverables:**
- [x] PostgreSQL server running in Azure
   - Verified server: `geomrv-postgres-dev` accessible via pgAdmin.
- [x] PostGIS extension enabled
   - Verified extensions in target databases: `postgis`, `uuid-ossp`.
- [x] Development/test databases created
   - Verified: `geomrv_dev` and `geomrv_test` created and used for schema deployment.
   - Note: `geomrv_prod` intentionally deferred for later phase hardening.
- [x] Initial schema deployed
   - Verified tables: `projects`, `boundaries`, `observations`, `processing_logs`, `lineage_metadata`, `evidence_packages`.
   - Verified indexes: `idx_boundary_geom`, `idx_observation_project_date`, `idx_project_operation`, `idx_evidence_package_date`.
- [x] Connection string tested
   - Verified successful query execution and object listing from PostgreSQL.

**Database Schema (SQL Script):**

```sql
-- Create projects table
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    location_name VARCHAR(255),
    country VARCHAR(100),
    region VARCHAR(100),
    total_area_ha FLOAT,
    project_type VARCHAR(50),
    start_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create project boundaries (geometry)
CREATE TABLE boundaries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    boundary_geom GEOMETRY(Polygon, 4326),
    area_ha FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Spatial index for geometry (PostgreSQL/PostGIS syntax)
CREATE INDEX idx_boundary_geom ON boundaries USING GIST (boundary_geom);

-- Create time-series observations
CREATE TABLE observations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    observation_date DATE NOT NULL,
    ndvi FLOAT,
    ndvi_std FLOAT,
    ndvi_count INT,
    evi FLOAT,
    biomass_estimate FLOAT,
    biomass_std FLOAT,
    data_source VARCHAR(100),
    cloud_cover_percent FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_observation_project_date ON observations (project_id, observation_date);

-- Create processing logs for full lineage
CREATE TABLE processing_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    operation_type VARCHAR(100),
    status VARCHAR(50),
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    execution_time_ms INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_project_operation ON processing_logs (project_id, operation_type);

-- Create evidence packages table
CREATE TABLE evidence_packages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    package_date DATE,
    period_start DATE,
    period_end DATE,
    status VARCHAR(50),
    s3_path VARCHAR(500),
    checksum VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_evidence_package_date ON evidence_packages (project_id, package_date);

-- Create lineage/metadata table
CREATE TABLE lineage_metadata (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    processing_log_id UUID NOT NULL REFERENCES processing_logs(id) ON DELETE CASCADE,
    satellite_source VARCHAR(100),
    satellite_date DATE,
    script_version VARCHAR(50),
    model_version VARCHAR(50),
    rule_version VARCHAR(50),
    input_parameters JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Files to Create:**
- `database/schema.sql` (above script)
- `database/migrations/001_initial_schema.sql`
- `database/README.md` (connection instructions)

---

### Task 0.3: Remote Sensing Data Source Integration (Days 5–7)

**Objective:** Configure access to satellite imagery for India

**Steps:**

1. **Choose Primary Data Source**
   - **Option A: Google Earth Engine (GEE)** ✅ *Recommended*
     - Free tier for non-commercial use
     - Easy Python API
     - Sentinel-2 and Landsat available
     - No authentication complexity for Indian geography
   - **Option B: USGS EarthExplorer**
     - Free Landsat and Sentinel-2 access
     - More manual download process
   - **Option C: Copernicus Open Access Hub**
     - Direct ESA Sentinel-2 access
     - Requires account creation

2. **Set Up Google Earth Engine (Recommended)**
   ```bash
   # Install Earth Engine Python API
   pip install earthengine-api
   
   # Authenticate
   earthengine authenticate
   
   # This opens browser, allows you to authorize access
   # Creates credentials in ~/.config/earthengine/
   ```

3. **Create Utility Scripts**
   - Script to fetch Sentinel-2 data for a polygon and date range
   - Script to calculate NDVI time series
   - Script to detect cloud cover
   - Store in `src/satellite_services/` folder

4. **Test Sentinel-2 Access**
   - Use sample Indian project boundary (e.g., Goa region)
   - Fetch 1 month of Sentinel-2 data
   - Calculate NDVI
   - Verify data in database

5. **Generate Timelapse Visual (Frontend Preview)**
   - Create a simple Sentinel-2 timelapse for the project boundary and date range
   - Output format: MP4 (or a sequence of PNG frames)
   - Store output in Azure Blob Storage:
     - `satellite-data-cache` for cached previews
     - `evidence-packages` when bundling into an evidence package later

6. **Document API Quotas**
   - GEE has monthly compute quotas (~40M pixels/month free tier)
   - Test with small pilot area before scaling

**Example Earth Engine Script (Python):**

```python
import ee
import pandas as pd
from datetime import datetime, timedelta

def fetch_ndvi_timeseries(geometry, start_date, end_date):
    """
    Fetch Sentinel-2 NDVI time series for a polygon
    
    Args:
        geometry: ee.Geometry polygon
        start_date: string (YYYY-MM-DD)
        end_date: string (YYYY-MM-DD)
    
    Returns:
        DataFrame with date, ndvi_mean, cloud_cover_percent
    """
    ee.Initialize()
    
    # Load Sentinel-2 collection
    s2 = ee.ImageCollection('COPERNICUS/S2') \
        .filterBounds(geometry) \
        .filterDate(start_date, end_date) \
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30))
    
    def add_ndvi(image):
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
        return image.addBands(ndvi)
    
    # Calculate NDVI for each image
    ndvi_collection = s2.map(add_ndvi)
    
    # Get statistics
    results = []
    for i in range(ndvi_collection.size().getInfo()):
        image = ee.Image(ndvi_collection.toList(ndvi_collection.size()).get(i))
        stats = image.select('NDVI').reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geometry,
            scale=20
        ).getInfo()
        
        cloud_cover = image.get('CLOUDY_PIXEL_PERCENTAGE').getInfo()
        date = ee.Date(image.get('system:time_start')).format('YYYY-MM-DD').getInfo()
        
        results.append({
            'date': date,
            'ndvi_mean': stats.get('NDVI', None),
            'cloud_cover': cloud_cover
        })
    
    return pd.DataFrame(results)
```

**Deliverables:**
- [x] Google Earth Engine credentials configured
   - Verified `earthengine authenticate` completed successfully.
   - GEE project: `geomrv-earth-engine` (project number `166748716378`).
- [x] Python scripts for data fetching
   - Created `earth_engine_client.py`, `ndvi_calculator.py`, `timelapse_exporter.py`.
- [x] Test run successful with sample Indian region
   - Verified: 17 Sentinel-2 images for Goa (73.8°E–73.95°E, 15.35°N–15.45°N), Jan–Mar 2025.
   - NDVI range: 0.047 – 0.211 (17 observations).
- [x] Cloud cover filtering working
   - Verified: scene-level filter (`CLOUDY_PIXEL_PERCENTAGE < 30`) + per-pixel QA60 cloud masking.
- [ ] Data stored in PostgreSQL
   - Script ready (`NDVICalculator.store_to_postgres`); will execute when a project row exists.
- [x] Timelapse preview generated (Sentinel-2 via GEE)
   - Verified: 2-frame MP4 (101.5 KB, 1 fps) generated from monthly composites.
- [x] Timelapse asset stored in Blob Storage for frontend use
   - Verified upload to `satellite-data-cache/timelapse/goa-test/2025-jan-mar.mp4`.
   - Blob URL: `https://geomrvstoragedev.blob.core.windows.net/satellite-data-cache/timelapse/goa-test/2025-jan-mar.mp4`
- [x] Documentation for satellite data quotas
   - Documented in `src/satellite_services/README.md` with quota table and usage guidance.

**Files to Create:**
- `src/satellite_services/earth_engine_client.py`
- `src/satellite_services/ndvi_calculator.py`
- `src/satellite_services/timelapse_exporter.py`
- `src/satellite_services/README.md`
- `tests/test_satellite_integration.py`

---

### Task 0.4: CI/CD Pipeline Setup (Days 6–8)

**Objective:** Automate testing and deployment

**Steps:**

1. **Create GitHub Repository**
   - Go to GitHub.com → New Repository
   - Name: `geomrv`
   - Private (for now)
   - Clone locally: `git clone https://github.com/your-username/geomrv.git`

2. **Folder Structure**
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
   ├── tests/
   ├── infrastructure/
   │   ├── terraform/ (optional for Phase 2+)
   │   └── docker/ (optional for containerization)
   ├── docs/
   │   └── development_lifecycle/
   ├── requirements.txt
   ├── setup.py
   ├── .github/workflows/ (CI/CD)
   ├── .env.example
   ├── .gitignore
   └── README.md
   ```

3. **Create GitHub Actions Workflow**
   - File: `.github/workflows/ci.yml`
   - Triggers on: push to main/dev, pull requests
   - Steps:
     1. Checkout code
     2. Set up Python 3.9+
     3. Install dependencies
     4. Run linters (flake8, black)
     5. Run unit tests (pytest)
     6. Generate coverage report
     7. (Later) Deploy to Azure if tests pass

4. **Set Up Secrets in GitHub**
   - Go to Settings → Secrets and variables
   - Add:
     - `AZURE_SUBSCRIPTION_ID`
     - `AZURE_RESOURCE_GROUP`
     - `AZURE_STORAGE_ACCOUNT_KEY`
     - `POSTGRES_PASSWORD`
     - `POSTGRES_HOST`
     - `GOOGLE_EARTH_ENGINE_CREDENTIALS` (if applicable)

5. **Create Development Branch Protection**
   - Settings → Branches
   - Protect `main` branch
   - Require PR reviews before merge
   - Require CI checks to pass

**Example GitHub Actions Workflow:**

```yaml
name: CI Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgis/postgis:13-3.1
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: geomrv_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python 3.9
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov flake8 black
    
    - name: Lint with flake8
      run: |
        flake8 src tests --count --select=E9,F63,F7,F82 --show-source --statistics
    
    - name: Format check with black
      run: black --check src tests
    
    - name: Run tests
      env:
        POSTGRES_HOST: localhost
        POSTGRES_USER: postgres
        POSTGRES_PASSWORD: postgres
        POSTGRES_DB: geomrv_test
      run: |
        pytest tests/ -v --cov=src --cov-report=xml
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        files: ./coverage.xml
```

**Deliverables:**
- [x] GitHub repository created
   - Verified repository initialized and remote configured for collaborative workflow.
   - Verified feature branch flow used (`ci-check` branch created, pushed, and merged via PR).
- [x] Folder structure initialized
   - Verified core structure present: `src/`, `tests/`, `docs/`, `infrastructure/`, and `.github/workflows/`.
   - Verified required baseline files exist for Phase 0 (`requirements.txt`, `.gitignore`, `.env.example`, CI workflow).
- [x] GitHub Actions workflow configured
   - Verified workflow file: `.github/workflows/ci.yml`.
   - Verified pipeline checks implemented: `Lint & Format Check`, `Unit Tests`, and `DB Schema Validation`.
   - Verified triggers configured for `push` and `pull_request` on `main` and `develop`.
- [x] Secrets added to GitHub
   - Verified repository secrets configured in GitHub Actions settings.
   - Verified active secrets include: `AZURE_RESOURCE_GROUP`, `AZURE_STORAGE_ACCOUNT`, `AZURE_STORAGE_ACCOUNT_KEY`, `AZURE_SUBSCRIPTION_ID`, `GOOGLE_EARTH_ENGINE_CREDENTIALS`, `POSTGRES_PASSWORD`, `POSTGRES_USER`.
- [x] Branch protection rules active
   - Verified branch protection enabled for `main`.
   - Verified PR-based merges and required status checks are configured before merge.
- [x] First CI run successful
   - Verified CI executed on PR flow and branch merge path.
   - Verified formatting-related failures were resolved and workflow proceeded with configured checks.

**Files to Create:**
- `.github/workflows/ci.yml`
- `.env.example`
- `.gitignore`
- `requirements.txt` (base dependencies)

---

### Task 0.5: Local Development Environment (Days 8–10)

**Objective:** Set up local development tools and testing database

**Steps:**

1. **Create Python Virtual Environment**
   ```bash
   cd geomrv
   python -m venv venv
   # Windows: venv\Scripts\activate
   # Mac/Linux: source venv/bin/activate
   pip install --upgrade pip
   ```

2. **Install Base Dependencies**
   ```bash
   pip install fastapi uvicorn
   pip install sqlalchemy psycopg2-binary alembic
   pip install geopandas shapely
   pip install pandas numpy scikit-learn
   pip install pydantic python-dotenv
   pip install pytest pytest-cov
   pip install earthengine-api
   pip install reportlab # for PDF generation
   pip install matplotlib seaborn # for plots
   ```

   Save to `requirements.txt`:
   ```bash
   pip freeze > requirements.txt
   ```

3. **Set Up Local PostgreSQL (Optional)**
   - For Windows: Download PostgreSQL installer, install with PostGIS
   - Create local database: `geomrv_dev`
   - Update `.env` with local credentials

   OR use Docker:
   ```bash
   docker run --name geomrv-postgres \
     -e POSTGRES_PASSWORD=dev_password \
     -e POSTGRES_DB=geomrv_dev \
     -p 5432:5432 \
     -d postgis/postgis:13-3.1
   ```

4. **Create `.env` File (Local)**
   ```bash
   # Copy from .env.example
   cp .env.example .env
   # Edit .env with local values:
   
   POSTGRES_HOST=localhost
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=dev_password
   POSTGRES_DB=geomrv_dev
   
   AZURE_STORAGE_ACCOUNT=geomrvstoragedev
   AZURE_STORAGE_KEY=<your_key>
   
   GOOGLE_EARTH_ENGINE_CREDENTIALS=~/.config/earthengine/credentials
   ```

5. **Initialize Database Schema Locally**
   ```bash
   psql -h localhost -U postgres -d geomrv_dev < database/schema.sql
   ```

6. **Test Connections**
   - Python script to test:
     - PostgreSQL connection
     - Azure Storage connection
     - Google Earth Engine access

**Test Script (test_setup.py):**

```python
import os
from dotenv import load_dotenv
import psycopg2
from azure.storage.blob import BlobServiceClient
import ee

load_dotenv()

def test_postgres():
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST'),
            database=os.getenv('POSTGRES_DB'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD')
        )
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()
        print(f"✅ PostgreSQL connected: {version[0]}")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ PostgreSQL error: {e}")

def test_azure_storage():
    try:
        blob_client = BlobServiceClient.from_connection_string(
            os.getenv('AZURE_STORAGE_CONNECTION_STRING')
        )
        properties = blob_client.get_account_information()
        print(f"✅ Azure Storage connected")
    except Exception as e:
        print(f"❌ Azure Storage error: {e}")

def test_earth_engine():
    try:
        ee.Initialize()
        print(f"✅ Google Earth Engine authenticated")
    except Exception as e:
        print(f"❌ Earth Engine error: {e}")

if __name__ == '__main__':
    test_postgres()
    test_azure_storage()
    test_earth_engine()
```

**Deliverables:**
- [x] Virtual environment created and activated
   - Verified local virtual environment `.venv` is created and activated for project isolation.
- [x] All dependencies installed
   - Verified required setup dependencies installed from `requirements.txt` (including `setuptools` for packaging support).
- [x] Local database configured
   - Verified PostgreSQL database connectivity from local environment and successful connection via setup test.
- [x] `.env` file created with local values
   - Verified local `.env` exists and is used by setup validation script.
- [x] All connection tests passing
   - Verified `python tests/test_setup.py` output:
     - `✅ PostgreSQL connected`
     - `✅ Azure Storage connected`
     - `✅ Google Earth Engine authenticated`
     - `✅ All setup checks passed`
- [x] Ready for backend development
   - Verified local environment, cloud connections, and setup scripts are operational for Phase 1 development.

**Files to Create:**
- `requirements.txt`
- `.env` (local, never commit to git)
- `setup.py`
- `tests/test_setup.py`

---

### Task 0.6: Documentation & Handoff (Days 10–14)

**Objective:** Document all setup so Phase 1 team can begin immediately

**Steps:**

1. **Create SETUP.md**
   - Step-by-step guide for new team members
   - Azure resource list
   - Database connection details
   - Local development setup

2. **Create API Contract Document**
   - Define endpoints Phase 1 will implement
   - Input/output schemas
   - Error handling conventions

3. **Create Architecture Diagram**
   - Show data flow: Project Boundary → Satellite Data → Features → Storage
   - Document all external dependencies

4. **Document India-Specific Considerations**
   - Sentinel-2 data availability in Indian regions
   - Monsoon season data gaps
   - Regional climate zones

5. **Create Development Checklist**
   - Verify all Azure resources operational
   - Test database with sample query
   - Verify CI/CD pipeline working
   - Earth Engine API quota monitoring

**Files to Create:**
- `SETUP.md`
- `API_CONTRACT.md`
- `docs/architecture_diagram.md`
- `docs/india_data_sources.md`
- `DEVELOPMENT_CHECKLIST.md`

---

## ✅ Phase 0 Checklist

- [x] Azure account activated with Student Pack
- [x] Resource group created with all services
- [x] PostgreSQL database running with PostGIS
- [x] Database schema deployed
- [x] Azure Storage configured
- [x] Google Earth Engine API working
- [x] GitHub repository created
- [x] CI/CD pipeline configured
- [x] Local dev environment set up
- [x] All connections tested
- [ ] Documentation completed
- [ ] Phase 1 team ready to begin

---

## 📊 Phase 0 Deliverables Summary

| Item | Status | Owner |
|------|--------|-------|
| Azure Infrastructure | ✅ | DevOps |
| PostgreSQL + Schema | ✅ | Backend |
| Satellite Integration | ✅ | Backend |
| CI/CD Pipeline | ✅ | DevOps |
| Local Dev Environment | ✅ | All |
| Documentation | ⏳ | Tech Lead |

---

## 🎯 Success Criteria for Phase 0

✅ All Azure services created and running  
✅ PostgreSQL accessible from local machine and CI pipeline  
✅ Google Earth Engine returns Sentinel-2 data for Indian region  
✅ GitHub Actions CI tests pass (even if just placeholder tests)  
✅ New developer can clone repo and be ready to code in 30 minutes  
✅ No hardcoded credentials in repository  

---

**Next Phase:** [Phase 1: Backend Engine](phase1_backend_engine.md)  
**Timeline:** Start Phase 1 in Week 3
