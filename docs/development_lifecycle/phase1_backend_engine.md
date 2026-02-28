# Phase 1: Core Backend Engine (Weeks 3–6)

**Duration:** 4 weeks  
**Goal:** Build functional API, remote sensing data pipeline, feature extraction, and verification rules  
**Deliverable:** Fully operational backend that accepts projects, ingests satellite data, and generates features

---

## 📊 Phase Overview

This is the core engine phase. The backend must:
1. Accept project boundaries (GeoJSON/shapefile)
2. Orchestrate satellite data retrieval
3. Calculate standardized features (NDVI, biomass proxies, trends)
4. Apply deterministic verification rules
5. Store everything with full lineage metadata

### Success Metrics
- API responds to all required endpoints
- Satellite data fetched for test projects
- Features calculated and stored
- Processing logs complete with metadata
- Backend ready for ML scoring (Phase 2)

---

## ✅ Prerequisites (Completed in Phase 0)

Before starting Phase 1 implementation, confirm these Phase 0 foundations are already in place:

- CI/CD is configured (GitHub Actions runs `flake8`, `black --check`, and `pytest`).
- Local development environment is ready (venv created, dependencies installed).
- `.env` is configured using `.env.example` and secrets are stored in GitHub/Azure Key Vault.
- Connectivity checks pass (`python tests/test_setup.py`):
    - PostgreSQL
    - Azure Storage
    - Google Earth Engine
- Baseline database schema exists (`database/schema.sql`).

Notes:
- Use `AZURE_STORAGE_ACCOUNT_KEY` (not `AZURE_STORAGE_KEY`) to match `.env.example` and GitHub secrets naming.
- Phase 1 config code expects `pydantic-settings` (add to `requirements.txt`).

---

## 🎯 Tasks Breakdown

### Task 1.1: FastAPI Backend Scaffolding (Days 1–3)

**Objective:** Set up API project structure with core endpoints

**Steps:**

1. **Create FastAPI Application Structure**
   ```
   src/api/
   ├── main.py
   ├── config.py
   ├── schemas.py
   ├── models.py
   ├── database.py
   ├── routers/
   │   ├── projects.py
   │   ├── jobs.py
   │   └── evidence.py
   ├── services/
   │   ├── project_service.py
   │   ├── job_service.py
   │   └── evidence_service.py
   ├── utils/
   │   ├── logger.py
   │   ├── validators.py
   │   └── exceptions.py
   └── tests/
       ├── test_projects.py
       ├── test_jobs.py
       └── test_integration.py
   ```

2. **Create main.py (FastAPI App)**
   ```python
   from fastapi import FastAPI
   from fastapi.middleware.cors import CORSMiddleware
   from src.api.config import settings
   from src.api.routers import projects, jobs, evidence
   
   app = FastAPI(
       title="GeoMRV API",
       description="Remote sensing MRV engine for carbon projects",
       version="0.1.0"
   )
   
   # CORS middleware
   app.add_middleware(
       CORSMiddleware,
       allow_origins=settings.CORS_ORIGINS,
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   
   # Include routers
   app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
   app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["jobs"])
   app.include_router(evidence.router, prefix="/api/v1/evidence", tags=["evidence"])
   
   @app.get("/health")
   def health_check():
       return {"status": "healthy"}
   
   if __name__ == "__main__":
       import uvicorn
       uvicorn.run(app, host="0.0.0.0", port=8000)
   ```

3. **Create config.py (Environment Configuration)**
   ```python
   from pydantic_settings import BaseSettings
   
   class Settings(BaseSettings):
       # Database
       POSTGRES_HOST: str
       POSTGRES_USER: str
       POSTGRES_PASSWORD: str
       POSTGRES_DB: str
       DATABASE_URL: str = None
       
       # Azure
       AZURE_STORAGE_ACCOUNT: str
    AZURE_STORAGE_ACCOUNT_KEY: str
    AZURE_STORAGE_CONNECTION_STRING: str = None
       AZURE_STORAGE_CONTAINER: str = "evidence-packages"
       
       # Satellite
       GOOGLE_EARTH_ENGINE_CREDENTIALS: str
       
       # API
       CORS_ORIGINS: list = ["*"]
       DEBUG: bool = False
       
       class Config:
           env_file = ".env"
       
       @property
       def db_url(self):
           return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}/{self.POSTGRES_DB}"
   
   settings = Settings()
   ```

4. **Create schemas.py (Pydantic Models)**
   ```python
   from pydantic import BaseModel
   from typing import Optional
   from datetime import date
   from enum import Enum
   
   class ProjectType(str, Enum):
       FOREST = "forest"
       AGROFORESTRY = "agroforestry"
       CROP = "crop"
       REGENERATIVE = "regenerative"
   
   class ProjectCreate(BaseModel):
       name: str
       description: Optional[str] = None
       location_name: str
       country: str
       region: str
       total_area_ha: float
       project_type: ProjectType
       start_date: date
   
   class ProjectResponse(ProjectCreate):
       id: str
       created_at: str
       updated_at: str
   
   class JobCreate(BaseModel):
       project_id: str
       start_date: date
       end_date: date
       job_type: str = "monitoring"  # monitoring, verification, reporting
   
   class JobResponse(JobCreate):
       id: str
       status: str  # pending, running, completed, failed
       created_at: str
       updated_at: str
   
   class EvidencePackageResponse(BaseModel):
       id: str
       project_id: str
       package_date: date
       period_start: date
       period_end: date
       s3_path: str
       created_at: str
   ```

5. **Create models.py (SQLAlchemy Models)**
   ```python
   from sqlalchemy import Column, String, Float, Date, DateTime, Enum as SQLEnum
   from sqlalchemy.dialects.postgresql import UUID, JSONB
   from sqlalchemy.ext.declarative import declarative_base
   from datetime import datetime
   import uuid
   
   Base = declarative_base()
   
   class Project(Base):
       __tablename__ = "projects"
       
       id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
       name = Column(String(255), nullable=False)
       description = Column(String(500))
       location_name = Column(String(255))
       country = Column(String(100))
       region = Column(String(100))
       total_area_ha = Column(Float)
       project_type = Column(String(50))
       start_date = Column(Date)
       created_at = Column(DateTime, default=datetime.utcnow)
       updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
   
   class Job(Base):
       __tablename__ = "jobs"
       
       id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
       project_id = Column(UUID(as_uuid=True), nullable=False)
       status = Column(String(50))
       job_type = Column(String(50))
       start_date = Column(Date)
       end_date = Column(Date)
       error_message = Column(String(1000))
       created_at = Column(DateTime, default=datetime.utcnow)
       updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
   ```

6. **Create database.py (Database Connection)**
   ```python
   from sqlalchemy import create_engine
   from sqlalchemy.orm import sessionmaker
   from src.api.config import settings
   
   engine = create_engine(settings.db_url)
   SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
   
   def get_db():
       db = SessionLocal()
       try:
           yield db
       finally:
           db.close()
   ```

**Deliverables:**
- [x] FastAPI application created and running
    - Verified app is running on `127.0.0.1:8000` and responds successfully.
- [x] All core routes defined (scaffold)
    - Verified routers are mounted under `/api/v1` for `projects`, `jobs`, and `evidence`.
    - Verified route response from `/api/v1/projects` with HTTP 200.
- [x] Database connections working
    - Verified SQLAlchemy session can execute `SELECT 1` successfully (`DB_OK: True`).
    - Verified API route `/api/v1/projects` returns persisted project data from PostgreSQL.
- [x] Configuration loaded from `.env`
    - Verified required environment settings are loaded (`ENV_FILE_OK: True`).
    - Verified settings are consumed by database/session initialization.
- [x] Health check endpoint works
    - Verified `/health` returns `{"status":"healthy","service":"geomrv-api"}`.
- [x] API documentation at `/docs`
    - Verified `/docs` is accessible (HTTP 200).

**Files to Create:**
- [x] `src/api/main.py`
- [x] `src/api/config.py`
- [x] `src/api/schemas.py`
- [x] `src/api/models.py`
- [x] `src/api/database.py`

---

### Task 1.2: Project Management Endpoints (Days 3–5)

**Objective:** Implement CRUD endpoints for projects and boundaries

**Steps:**

1. **Create projects.py Router**
   ```python
   from fastapi import APIRouter, Depends, HTTPException
   from sqlalchemy.orm import Session
   from src.api.schemas import ProjectCreate, ProjectResponse
   from src.api.models import Project
   from src.api.database import get_db
   from src.api.services.project_service import ProjectService
   
   router = APIRouter()
   
   @router.post("/", response_model=ProjectResponse)
   def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
       """Create a new project"""
       service = ProjectService(db)
       return service.create_project(project)
   
   @router.get("/", response_model=list[ProjectResponse])
   def list_projects(db: Session = Depends(get_db)):
       """List all projects"""
       return db.query(Project).all()
   
   @router.get("/{project_id}", response_model=ProjectResponse)
   def get_project(project_id: str, db: Session = Depends(get_db)):
       """Get specific project"""
       project = db.query(Project).filter(Project.id == project_id).first()
       if not project:
           raise HTTPException(status_code=404, detail="Project not found")
       return project
   
   @router.put("/{project_id}", response_model=ProjectResponse)
   def update_project(project_id: str, project: ProjectCreate, db: Session = Depends(get_db)):
       """Update project"""
       service = ProjectService(db)
       return service.update_project(project_id, project)
   
   @router.delete("/{project_id}")
   def delete_project(project_id: str, db: Session = Depends(get_db)):
       """Delete project"""
       service = ProjectService(db)
       service.delete_project(project_id)
       return {"message": "Project deleted"}
   ```

2. **Create Boundary Upload Endpoint**
   ```python
   from fastapi import UploadFile, File
   import geopandas as gpd
   from shapely.geometry import mapping
   from geoalchemy2 import Geometry
   
   @router.post("/{project_id}/upload-boundary")
   async def upload_boundary(
       project_id: str,
       file: UploadFile = File(...),
       db: Session = Depends(get_db)
   ):
       """Upload boundary as shapefile or GeoJSON"""
       # Read file
       contents = await file.read()
       
       # Parse geometry
       if file.filename.endswith('.geojson'):
           import json
           geom = json.loads(contents)
       elif file.filename.endswith('.zip'):
           # Handle shapefile
           gdf = gpd.read_file(contents)
           geom = mapping(gdf.geometry[0])
       
       # Store in database with WKT format
       service = ProjectService(db)
       service.save_boundary(project_id, geom)
       
       return {"message": "Boundary uploaded", "area_ha": calculate_area(geom)}
   
   def calculate_area(geom):
       """Calculate area in hectares"""
       from shapely.geometry import shape
       s = shape(geom)
       # Use simple approximation for now
       return s.area * 10000  # rough estimate
   ```

3. **Create ProjectService**
   ```python
   # src/api/services/project_service.py
   from sqlalchemy.orm import Session
   from src.api.models import Project, Boundary
   from src.api.schemas import ProjectCreate
   from geoalchemy2.functions import ST_GeomFromText
   from datetime import datetime
   import uuid
   
   class ProjectService:
       def __init__(self, db: Session):
           self.db = db
       
       def create_project(self, project_data: ProjectCreate) -> Project:
           project = Project(**project_data.dict())
           project.id = uuid.uuid4()
           self.db.add(project)
           self.db.commit()
           self.db.refresh(project)
           return project
       
       def update_project(self, project_id: str, project_data: ProjectCreate) -> Project:
           project = self.db.query(Project).filter(Project.id == project_id).first()
           for key, value in project_data.dict().items():
               setattr(project, key, value)
           project.updated_at = datetime.utcnow()
           self.db.commit()
           self.db.refresh(project)
           return project
       
       def delete_project(self, project_id: str):
           project = self.db.query(Project).filter(Project.id == project_id).first()
           self.db.delete(project)
           self.db.commit()
       
       def save_boundary(self, project_id: str, geometry_dict: dict):
           # Convert GeoJSON to WKT for storage
           from shapely.geometry import shape
           geom = shape(geometry_dict)
           wkt = geom.wkt
           
           boundary = Boundary(
               id=uuid.uuid4(),
               project_id=project_id,
               boundary_geom=f"SRID=4326;{wkt}",
               area_ha=geom.area * 10000
           )
           self.db.add(boundary)
           self.db.commit()
   ```

**Deliverables:**
- [x] Project CRUD endpoints working
    - Verified endpoints: `POST /api/v1/projects`, `GET /api/v1/projects`, `GET /api/v1/projects/{project_id}`, `PUT /api/v1/projects/{project_id}`, `DELETE /api/v1/projects/{project_id}`.
    - Verified success and not-found flows through automated tests.
- [x] Boundary upload endpoint
    - Verified endpoint: `POST /api/v1/projects/{project_id}/upload-boundary` with `.geojson` upload support.
    - Verified boundary retrieval endpoint: `GET /api/v1/projects/{project_id}/boundary`.
    - Verified invalid extension and invalid JSON paths return proper 400 errors.
- [x] ProjectService implemented
    - Verified service file created: `src/api/services/project_service.py`.
    - Verified service methods for list/create/get/update/delete project and save/get boundary are used by router.
- [x] Endpoints tested with sample data
    - Verified test suite: `tests/test_projects.py`.
    - Verified result: `15 passed` (CRUD + boundary upload/retrieval + error paths).
- [x] API documentation updated
    - Verified OpenAPI docs include new project update and boundary endpoints under `/docs`.

**Files to Create:**
- [x] `src/api/routers/projects.py`
- [x] `src/api/services/project_service.py`
- [x] `tests/test_projects.py`

---

### Task 1.3: Satellite Data Fetching Service (Days 5–8)

**Objective:** Implement satellite image retrieval and storage

**Steps:**

1. **Create SatelliteDataService**
   ```python
   # src/satellite_services/data_fetcher.py
   import ee
   import pandas as pd
   from datetime import datetime, timedelta
   from typing import List, Tuple
   import logging
   
   logger = logging.getLogger(__name__)
   
   class SatelliteDataFetcher:
       def __init__(self, credentials_path=None):
           """Initialize Earth Engine client"""
           try:
               ee.Initialize()
           except:
               if credentials_path:
                   ee.Authenticate()
               ee.Initialize()
       
       def fetch_sentinel2_data(
           self,
           geometry_wkt: str,
           start_date: str,
           end_date: str,
           max_cloud_cover: float = 30
       ) -> pd.DataFrame:
           """
           Fetch Sentinel-2 imagery for polygon and date range
           
           Args:
               geometry_wkt: WKT polygon string
               start_date: YYYY-MM-DD
               end_date: YYYY-MM-DD
               max_cloud_cover: Maximum cloud cover percentage
           
           Returns:
               DataFrame with date, ndvi, evi, cloud_cover
           """
           from shapely.wkt import loads
           
           # Convert WKT to ee.Geometry
           geom = loads(geometry_wkt)
           coords = list(geom.exterior.coords)
           ee_geom = ee.Geometry.Polygon(coords)
           
           # Load Sentinel-2 collection
           s2 = (ee.ImageCollection('COPERNICUS/S2_SR')
                 .filterBounds(ee_geom)
                 .filterDate(start_date, end_date)
                 .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', max_cloud_cover))
                 .sort('system:time_start'))
           
           # Calculate indices
           def add_indices(image):
               # NDVI = (NIR - RED) / (NIR + RED)
               ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
               
               # EVI = 2.5 * (NIR - RED) / (NIR + 6*RED - 7.5*BLUE + 1)
               nir = image.select('B8').divide(10000)
               red = image.select('B4').divide(10000)
               blue = image.select('B2').divide(10000)
               
               evi = nir.subtract(red).multiply(2.5).divide(
                   nir.add(red.multiply(6)).subtract(blue.multiply(7.5)).add(1)
               ).rename('EVI')
               
               return image.addBands([ndvi, evi])
           
           indices = s2.map(add_indices)
           
           # Extract statistics
           results = []
           image_list = indices.toList(indices.size()).getInfo()
           
           for i in range(len(image_list)):
               image = ee.Image(indices.toList(indices.size()).get(i))
               
               # Get date
               date_str = ee.Date(image.get('system:time_start')).format('YYYY-MM-DD').getInfo()
               
               # Calculate mean for NDVI and EVI
               ndvi_stats = image.select('NDVI').reduceRegion(
                   reducer=ee.Reducer.mean(),
                   geometry=ee_geom,
                   scale=20
               ).getInfo()
               
               evi_stats = image.select('EVI').reduceRegion(
                   reducer=ee.Reducer.mean(),
                   geometry=ee_geom,
                   scale=20
               ).getInfo()
               
               cloud_cover = image.get('CLOUDY_PIXEL_PERCENTAGE').getInfo()
               
               results.append({
                   'date': date_str,
                   'ndvi': ndvi_stats.get('NDVI'),
                   'evi': evi_stats.get('EVI'),
                   'cloud_cover': cloud_cover
               })
               
               logger.info(f"Processed {date_str}: NDVI={ndvi_stats.get('NDVI')}")
           
           return pd.DataFrame(results)
       
       def fetch_landsat_data(
           self,
           geometry_wkt: str,
           start_date: str,
           end_date: str,
           max_cloud_cover: float = 30
       ) -> pd.DataFrame:
           """
           Fetch Landsat 8/9 data as fallback for cloud cover or temporal gaps
           """
           # Similar implementation for Landsat
           pass
   ```

2. **Create Job Orchestration Endpoint**
   ```python
   # src/api/routers/jobs.py
   from fastapi import APIRouter, Depends, BackgroundTasks
   from src.api.schemas import JobCreate, JobResponse
   from src.api.services.job_service import JobService
   from src.api.database import get_db
   
   router = APIRouter()
   
   @router.post("/", response_model=JobResponse)
   def create_job(
       job: JobCreate,
       background_tasks: BackgroundTasks,
       db = Depends(get_db)
   ):
       """
       Create a monitoring job (satellite data fetch + processing)
       """
       service = JobService(db)
       job_obj = service.create_job(job)
       
       # Schedule background task
       background_tasks.add_task(service.process_job, job_obj.id)
       
       return job_obj
   
   @router.get("/{job_id}", response_model=JobResponse)
   def get_job(job_id: str, db = Depends(get_db)):
       """Get job status"""
       service = JobService(db)
       return service.get_job(job_id)
   ```

3. **Create JobService**
   ```python
   # src/api/services/job_service.py
   from sqlalchemy.orm import Session
   from src.api.models import Job, Observation, ProcessingLog
   from src.satellite_services.data_fetcher import SatelliteDataFetcher
   from datetime import datetime
   import logging
   
   logger = logging.getLogger(__name__)
   
   class JobService:
       def __init__(self, db: Session):
           self.db = db
           self.fetcher = SatelliteDataFetcher()
       
       def create_job(self, job_data):
           job = Job(
               project_id=job_data.project_id,
               status="pending",
               job_type=job_data.job_type,
               start_date=job_data.start_date,
               end_date=job_data.end_date
           )
           self.db.add(job)
           self.db.commit()
           return job
       
       def process_job(self, job_id: str):
           """Background task: fetch satellite data and calculate features"""
           try:
               job = self.db.query(Job).filter(Job.id == job_id).first()
               job.status = "running"
               self.db.commit()
               
               # Get project boundary
               from src.api.models import Project, Boundary
               project = self.db.query(Project).filter(Project.id == job.project_id).first()
               boundary = self.db.query(Boundary).filter(Boundary.project_id == job.project_id).first()
               
               # Fetch satellite data
               df = self.fetcher.fetch_sentinel2_data(
                   geometry_wkt=boundary.boundary_geom,
                   start_date=job.start_date.isoformat(),
                   end_date=job.end_date.isoformat()
               )
               
               # Store observations
               for _, row in df.iterrows():
                   obs = Observation(
                       project_id=job.project_id,
                       observation_date=row['date'],
                       ndvi=row['ndvi'],
                       evi=row['evi'],
                       cloud_cover_percent=row['cloud_cover'],
                       data_source='Sentinel-2'
                   )
                   self.db.add(obs)
               
               # Create processing log
               log = ProcessingLog(
                   project_id=job.project_id,
                   operation_type="satellite_fetch",
                   status="success",
                   input_data={"start_date": job.start_date.isoformat(), "end_date": job.end_date.isoformat()},
                   output_data={"records": len(df)}
               )
               self.db.add(log)
               
               job.status = "completed"
               self.db.commit()
               logger.info(f"Job {job_id} completed successfully")
               
           except Exception as e:
               job.status = "failed"
               job.error_message = str(e)
               self.db.commit()
               logger.error(f"Job {job_id} failed: {e}")
       
       def get_job(self, job_id: str):
           return self.db.query(Job).filter(Job.id == job_id).first()
   ```

**Deliverables:**
- [ ] SatelliteDataFetcher implemented
- [ ] Sentinel-2 NDVI/EVI calculation working
- [ ] Job creation endpoint functional
- [ ] Background job processing working
- [ ] Observations stored in database
- [ ] Processing logs created
- [ ] Tested with real Indian region (e.g., Goa)

**Files to Create:**
- `src/satellite_services/data_fetcher.py`
- `src/api/routers/jobs.py`
- `src/api/services/job_service.py`
- `tests/test_satellite_fetcher.py`
- `tests/test_jobs.py`

---

### Task 1.4: Feature Extraction Engine (Days 8–12)

**Objective:** Calculate standardized time-series features from satellite observations

**Steps:**

1. **Create Feature Extractor**
   ```python
   # src/feature_extraction/feature_calculator.py
   import pandas as pd
   import numpy as np
   from scipy import signal
   from datetime import datetime, timedelta
   import logging
   
   logger = logging.getLogger(__name__)
   
   class FeatureCalculator:
       """Calculate standardized features from satellite observations"""
       
       @staticmethod
       def calculate_trend(df: pd.DataFrame, window_days: int = 30) -> dict:
           """
           Calculate vegetation trend
           
           Args:
               df: DataFrame with date and ndvi columns
               window_days: Moving window for smoothing
           
           Returns:
               Dictionary with trend metrics
           """
           df = df.sort_values('date')
           df['ndvi_smooth'] = df['ndvi'].rolling(window=3, center=True).mean()
           
           # Linear regression on smoothed data
           x = np.arange(len(df))
           y = df['ndvi_smooth'].values
           
           # Remove NaN values
           mask = ~np.isnan(y)
           x_clean = x[mask]
           y_clean = y[mask]
           
           if len(x_clean) < 2:
               return {"trend_slope": None, "r_squared": 0}
           
           coeffs = np.polyfit(x_clean, y_clean, 1)
           slope = coeffs[0]  # pixels per day
           
           # R-squared
           y_pred = np.polyval(coeffs, x_clean)
           ss_res = np.sum((y_clean - y_pred) ** 2)
           ss_tot = np.sum((y_clean - np.mean(y_clean)) ** 2)
           r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
           
           return {
               "trend_slope": slope,
               "r_squared": r_squared,
               "slope_per_year": slope * 365  # annualized
           }
       
       @staticmethod
       def calculate_seasonality(df: pd.DataFrame) -> dict:
           """
           Detect seasonal patterns
           """
           df = df.sort_values('date')
           
           # Extract month
           df['month'] = pd.to_datetime(df['date']).dt.month
           
           # Group by month and calculate mean NDVI
           seasonal = df.groupby('month')['ndvi'].agg(['mean', 'std'])
           
           # Peak month
           peak_month = seasonal['mean'].idxmax()
           trough_month = seasonal['mean'].idxmin()
           
           return {
               "peak_month": int(peak_month),
               "trough_month": int(trough_month),
               "peak_ndvi": float(seasonal.loc[peak_month, 'mean']),
               "trough_ndvi": float(seasonal.loc[trough_month, 'mean']),
               "seasonal_amplitude": float(seasonal['mean'].max() - seasonal['mean'].min())
           }
       
       @staticmethod
       def calculate_anomalies(df: pd.DataFrame, std_threshold: float = 2.0) -> list:
           """
           Detect anomalous observations
           
           Returns:
               List of anomalous dates
           """
           df = df.sort_values('date')
           
           # Calculate rolling mean and std
           ndvi_mean = df['ndvi'].rolling(window=10, center=True).mean()
           ndvi_std = df['ndvi'].rolling(window=10, center=True).std()
           
           # Flag anomalies (> 2 std from rolling mean)
           anomalies = np.abs(df['ndvi'] - ndvi_mean) > (std_threshold * ndvi_std)
           
           anomalous_dates = df[anomalies]['date'].tolist()
           return [str(d) for d in anomalous_dates]
       
       @staticmethod
       def calculate_growth_period(df: pd.DataFrame) -> dict:
           """
           Identify growing season and growth rate
           """
           df = df.sort_values('date')
           
           # Simple approach: identify when NDVI > mean
           ndvi_threshold = df['ndvi'].mean()
           growing = df[df['ndvi'] > ndvi_threshold]
           
           if len(growing) == 0:
               return {"growth_start": None, "growth_end": None, "growth_days": 0}
           
           growth_start = growing['date'].min()
           growth_end = growing['date'].max()
           growth_days = (growth_end - growth_start).days if isinstance(growth_start, pd.Timestamp) else 0
           
           return {
               "growth_start": str(growth_start),
               "growth_end": str(growth_end),
               "growth_days": int(growth_days)
           }
       
       @staticmethod
       def calculate_biomass_proxy(ndvi: float, evi: float) -> float:
           """
           Estimate biomass from vegetation indices
           
           Simple linear regression: Biomass = a*NDVI + b*EVI + c
           These coefficients are India-region-specific and would be calibrated
           """
           # Placeholder coefficients - should be trained on reference data
           a = 50  # NDVI weight
           b = 30  # EVI weight
           c = 5   # intercept
           
           biomass = a * ndvi + b * evi + c
           return max(0, biomass)  # Biomass can't be negative
   
   class PipelineFeatureExtractor:
       """Extract all features for a project"""
       
       def __init__(self, db_session):
           self.db = db_session
           self.calculator = FeatureCalculator()
       
       def extract_features(self, project_id: str, start_date: str, end_date: str) -> dict:
           """
           Extract all standardized features for a project
           """
           from src.api.models import Observation
           
           # Query observations
           obs = self.db.query(Observation).filter(
               (Observation.project_id == project_id) &
               (Observation.observation_date >= start_date) &
               (Observation.observation_date <= end_date)
           ).all()
           
           if not obs:
               logger.warning(f"No observations found for project {project_id}")
               return {}
           
           # Convert to DataFrame
           df = pd.DataFrame([
               {
                   'date': o.observation_date,
                   'ndvi': o.ndvi,
                   'evi': o.evi if hasattr(o, 'evi') else None,
                   'cloud_cover': o.cloud_cover_percent
               }
               for o in obs
           ])
           
           # Filter by cloud cover
           df = df[df['cloud_cover'] < 30]
           
           if len(df) < 3:
               logger.warning(f"Insufficient clear observations for {project_id}")
               return {}
           
           # Calculate all features
           features = {
               "project_id": project_id,
               "period_start": start_date,
               "period_end": end_date,
               "observation_count": len(df),
               "trend": self.calculator.calculate_trend(df),
               "seasonality": self.calculator.calculate_seasonality(df),
               "growth_period": self.calculator.calculate_growth_period(df),
               "anomalies": self.calculator.calculate_anomalies(df),
               "ndvi_stats": {
                   "mean": float(df['ndvi'].mean()),
                   "std": float(df['ndvi'].std()),
                   "min": float(df['ndvi'].min()),
                   "max": float(df['ndvi'].max())
               }
           }
           
           # Estimate biomass
           if 'evi' in df.columns:
               df['biomass'] = df.apply(
                   lambda row: self.calculator.calculate_biomass_proxy(row['ndvi'], row['evi']),
                   axis=1
               )
               features['biomass_stats'] = {
                   "mean": float(df['biomass'].mean()),
                   "std": float(df['biomass'].std()),
                   "min": float(df['biomass'].min()),
                   "max": float(df['biomass'].max())
               }
           
           return features
   ```

2. **Create Feature Storage**
   ```python
   # src/feature_extraction/feature_store.py
   from sqlalchemy.orm import Session
   from sqlalchemy.dialects.postgresql import insert
   from src.api.models import ProcessingLog
   import json
   from datetime import datetime
   
   class FeatureStore:
       """Store extracted features in database with versioning"""
       
       def __init__(self, db: Session):
           self.db = db
       
       def save_features(self, project_id: str, features: dict):
           """Save features as processing log entry"""
           log = ProcessingLog(
               project_id=project_id,
               operation_type="feature_extraction",
               status="success",
               input_data={
                   "period_start": features.get("period_start"),
                   "period_end": features.get("period_end")
               },
               output_data=features,
               execution_time_ms=0  # Could measure this
           )
           self.db.add(log)
           self.db.commit()
           return log
   ```

3. **Create Feature Extraction Endpoint**
   ```python
   # In src/api/routers/features.py (new file)
   from fastapi import APIRouter, Depends
   from src.api.database import get_db
   from src.feature_extraction.feature_calculator import PipelineFeatureExtractor
   from src.feature_extraction.feature_store import FeatureStore
   
   router = APIRouter()
   
   @router.post("/{project_id}/extract")
   def extract_project_features(
       project_id: str,
       start_date: str,
       end_date: str,
       db = Depends(get_db)
   ):
       """Extract features for a project in date range"""
       extractor = PipelineFeatureExtractor(db)
       features = extractor.extract_features(project_id, start_date, end_date)
       
       # Store features
       store = FeatureStore(db)
       log = store.save_features(project_id, features)
       
       return {
           "project_id": project_id,
           "features": features,
           "processing_log_id": str(log.id)
       }
   ```

**Deliverables:**
- [ ] Feature calculator with trend, seasonality, anomalies
- [ ] Biomass estimation (placeholder model)
- [ ] Feature extraction pipeline
- [ ] Feature storage with versioning
- [ ] Extract endpoint working
- [ ] Features calculated for test data

**Files to Create:**
- `src/feature_extraction/feature_calculator.py`
- `src/feature_extraction/feature_store.py`
- `src/api/routers/features.py`
- `tests/test_feature_extraction.py`

---

### Task 1.5: Verification Rules Engine (Days 12–16)

**Objective:** Apply deterministic rules to flag inconsistencies and verify growth claims

**Steps:**

1. **Create Verification Rules Engine**
   ```python
   # src/verification_rules/rules_engine.py
   from typing import List, Dict
   from dataclasses import dataclass
   from enum import Enum
   import logging
   
   logger = logging.getLogger(__name__)
   
   class RiskLevel(str, Enum):
       LOW = "low"
       MEDIUM = "medium"
       HIGH = "high"
       CRITICAL = "critical"
   
   @dataclass
   class VerificationFlag:
       rule_id: str
       rule_name: str
       risk_level: RiskLevel
       description: str
       affected_period: str
       recommended_action: str
   
   class VerificationRulesEngine:
       """Apply deterministic verification rules to features"""
       
       def __init__(self):
           self.rules = self._load_rules()
       
       def _load_rules(self) -> Dict:
           """Load rule definitions - could be DB or config file"""
           return {
               "R1_insufficient_data": {
                   "name": "Insufficient Observations",
                   "description": "Fewer than 12 observations in period",
                   "risk_level": RiskLevel.MEDIUM
               },
               "R2_high_cloud_cover": {
                   "name": "High Cloud Cover",
                   "description": "Average cloud cover > 40%",
                   "risk_level": RiskLevel.MEDIUM
               },
               "R3_no_growth_detected": {
                   "name": "No Growth Detected",
                   "description": "Trend slope near zero or negative",
                   "risk_level": RiskLevel.HIGH
               },
               "R4_anomalous_spike": {
                   "name": "Anomalous Value",
                   "description": "NDVI spike likely due to atmospheric artifact",
                   "risk_level": RiskLevel.MEDIUM
               },
               "R5_forest_loss": {
                   "name": "Vegetation Loss",
                   "description": "Significant NDVI decrease detected",
                   "risk_level": RiskLevel.CRITICAL
               },
               "R6_data_gap": {
                   "name": "Data Gap",
                   "description": "No observations for > 60 days",
                   "risk_level": RiskLevel.MEDIUM
               }
           }
       
       def verify(self, features: dict) -> List[VerificationFlag]:
           """
           Run all verification rules on extracted features
           
           Returns:
               List of flags (empty if no issues)
           """
           flags = []
           
           # R1: Check observation count
           if features.get("observation_count", 0) < 12:
               flags.append(VerificationFlag(
                   rule_id="R1_insufficient_data",
                   rule_name="Insufficient Observations",
                   risk_level=RiskLevel.MEDIUM,
                   description="Only {} observations found; recommend 12+ per year".format(
                       features.get("observation_count")
                   ),
                   affected_period=f"{features.get('period_start')} to {features.get('period_end')}",
                   recommended_action="Extend monitoring period or use fallback Landsat data"
               ))
           
           # R3: Check growth trend
           trend = features.get("trend", {})
           if trend.get("trend_slope", 0) <= 0:
               flags.append(VerificationFlag(
                   rule_id="R3_no_growth_detected",
                   rule_name="No Growth Detected",
                   risk_level=RiskLevel.HIGH,
                   description=f"Trend slope: {trend.get('trend_slope'):.4f} (threshold: > 0)",
                   affected_period=f"{features.get('period_start')} to {features.get('period_end')}",
                   recommended_action="Investigate ground conditions or verify project implementation"
               ))
           
           # R5: Check for vegetation loss
           ndvi_stats = features.get("ndvi_stats", {})
           if ndvi_stats.get("min", 0) < 0.2 and ndvi_stats.get("max", 1) > 0.7:
               ndvi_change = ndvi_stats["max"] - ndvi_stats["min"]
               if ndvi_change > 0.5:  # Large swing suggests loss
                   flags.append(VerificationFlag(
                       rule_id="R5_forest_loss",
                       rule_name="Vegetation Loss Detected",
                       risk_level=RiskLevel.CRITICAL,
                       description=f"Large NDVI swing: {ndvi_change:.2f} (min={ndvi_stats['min']:.2f}, max={ndvi_stats['max']:.2f})",
                       affected_period=f"{features.get('period_start')} to {features.get('period_end')}",
                       recommended_action="Conduct urgent field verification"
                   ))
           
           # R4: Check for anomalies
           anomalies = features.get("anomalies", [])
           if len(anomalies) > 0:
               flags.append(VerificationFlag(
                   rule_id="R4_anomalous_spike",
                   rule_name="Anomalous Values Detected",
                   risk_level=RiskLevel.MEDIUM,
                   description=f"Found {len(anomalies)} anomalous observations",
                   affected_period=", ".join(anomalies[:3]) + ("..." if len(anomalies) > 3 else ""),
                   recommended_action="Review satellite data quality; may indicate cloud shadows or sun glint"
               ))
           
           logger.info(f"Verification complete: {len(flags)} flags found")
           return flags
       
       def get_confidence_score(self, features: dict, flags: List[VerificationFlag]) -> float:
           """
           Calculate confidence score (0-100) based on feature quality and flags
           """
           score = 100.0
           
           # Penalty for insufficient observations
           obs_count = features.get("observation_count", 0)
           if obs_count < 12:
               score -= (12 - obs_count) * 2
           
           # Penalty for high uncertainty in trend
           trend = features.get("trend", {})
           r_squared = trend.get("r_squared", 0)
           if r_squared < 0.5:
               score -= (0.5 - r_squared) * 50
           
           # Penalty for each flag
           flag_penalties = {
               RiskLevel.LOW: 5,
               RiskLevel.MEDIUM: 15,
               RiskLevel.HIGH: 30,
               RiskLevel.CRITICAL: 50
           }
           for flag in flags:
               score -= flag_penalties.get(flag.risk_level, 0)
           
           return max(0, min(100, score))
   ```

2. **Create Rule Storage & Reporting**
   ```python
   # src/verification_rules/rule_store.py
   from src.api.models import ProcessingLog
   from sqlalchemy.orm import Session
   import json
   
   class RuleStore:
       def __init__(self, db: Session):
           self.db = db
       
       def save_verification_results(self, project_id: str, flags: list, confidence_score: float):
           """Save verification results"""
           log = ProcessingLog(
               project_id=project_id,
               operation_type="verification",
               status="completed",
               output_data={
                   "flags": [
                       {
                           "rule_id": f.rule_id,
                           "name": f.rule_name,
                           "risk_level": f.risk_level,
                           "description": f.description
                       }
                       for f in flags
                   ],
                   "confidence_score": confidence_score,
                   "has_critical_flags": any(f.risk_level == "critical" for f in flags)
               }
           )
           self.db.add(log)
           self.db.commit()
           return log
   ```

3. **Create Verification Endpoint**
   ```python
   # In src/api/routers/verification.py (new file)
   from fastapi import APIRouter, Depends
   from src.api.database import get_db
   from src.verification_rules.rules_engine import VerificationRulesEngine
   from src.verification_rules.rule_store import RuleStore
   from src.feature_extraction.feature_calculator import PipelineFeatureExtractor
   
   router = APIRouter()
   
   @router.post("/{project_id}/verify")
   def verify_project(
       project_id: str,
       start_date: str,
       end_date: str,
       db = Depends(get_db)
   ):
       """Run verification on project"""
       # Extract features first
       extractor = PipelineFeatureExtractor(db)
       features = extractor.extract_features(project_id, start_date, end_date)
       
       # Run verification
       engine = VerificationRulesEngine()
       flags = engine.verify(features)
       confidence_score = engine.get_confidence_score(features, flags)
       
       # Store results
       store = RuleStore(db)
       log = store.save_verification_results(project_id, flags, confidence_score)
       
       return {
           "project_id": project_id,
           "verification_flags": [
               {
                   "rule_id": f.rule_id,
                   "name": f.rule_name,
                   "risk_level": f.risk_level.value,
                   "description": f.description,
                   "recommended_action": f.recommended_action
               }
               for f in flags
           ],
           "confidence_score": confidence_score,
           "status": "PASS" if confidence_score >= 70 else "REVIEW_REQUIRED"
       }
   ```

**Deliverables:**
- [ ] Rules engine with 6+ verification rules
- [ ] Confidence scoring algorithm
- [ ] Rule storage with lineage
- [ ] Verification endpoint working
- [ ] Rules tested with sample features
- [ ] Clear documentation of each rule

**Files to Create:**
- `src/verification_rules/rules_engine.py`
- `src/verification_rules/rule_store.py`
- `src/api/routers/verification.py`
- `tests/test_verification_rules.py`

---

## ✅ Phase 1 Checklist

- [ ] FastAPI app created and running
- [ ] Project management endpoints working (CRUD)
- [ ] Boundary upload working
- [ ] Sentinel-2 data fetching operational
- [ ] NDVI/EVI calculation verified
- [ ] Feature extraction pipeline complete
- [ ] Verification rules engine implemented
- [ ] All endpoints tested with sample data
- [ ] Confidence scoring working
- [ ] Processing logs complete
- [ ] CI/CD pipeline tests passing
- [ ] API documentation updated
- [ ] Ready for Phase 2 (ML models)

---

## 📊 Phase 1 Deliverables

| Component | Status | Notes |
|-----------|--------|-------|
| FastAPI Backend | ✅ | Complete API structure |
| Project Management | ✅ | Full CRUD operations |
| Satellite Data Fetcher | ✅ | Sentinel-2 integration |
| Feature Extraction | ✅ | 5+ standardized features |
| Verification Rules | ✅ | 6 deterministic rules |
| Database Integration | ✅ | PostgreSQL + PostGIS |
| Logging & Lineage | ✅ | Full processing trails |

---

**Next Phase:** [Phase 2: ML Scoring Layer](phase2_ml_scoring.md)  
**Timeline:** Weeks 7–9
