# Phase 2: ML Scoring Layer (Weeks 7–9)

**Duration:** 3 weeks  
**Goal:** Build machine learning models for confidence scoring, biomass estimation, and risk classification  
**Deliverable:** ML pipeline integrated with backend, producing confidence-scored outputs

---

## 📊 Phase Overview

Phase 2 adds predictive ML models on top of the deterministic features from Phase 1. The ML layer:
- Trains gradient boosting models on reference data
- Scores confidence for growth claims
- Flags high-risk projects
- Provides anomaly detection
- Maintains full model versioning for reproducibility

### Success Metrics
- ML models trained and evaluated
- Inference endpoint operational
- Confidence scores align with verification rules
- Model version tracking working
- Ready for evidence packaging (Phase 3)

---

## 🎯 Tasks Breakdown

### Task 2.1: Training Data Preparation (Days 1–3)

**Objective:** Create training dataset for ML models

**Steps:**

1. **Define Training Data Schema**
   ```python
   # src/ml_models/data_preparation.py
   import pandas as pd
   import numpy as np
   from sklearn.preprocessing import StandardScaler
   from typing import Tuple
   
   class TrainingDataPreparator:
       """Prepare features for ML training"""
       
       def __init__(self):
           self.scaler = StandardScaler()
       
       def prepare_feature_matrix(self, observations_df: pd.DataFrame) -> pd.DataFrame:
           """
           Convert observations to model input features
           
           Input columns:
               - date
               - ndvi
               - evi
               - cloud_cover
           
           Output features (all numeric):
               - ndvi_mean, ndvi_std, ndvi_trend
               - evi_mean, evi_std
               - cloud_cover_mean
               - trend_slope
               - seasonal_amplitude
               - observation_count
           """
           obs_df = observations_df.copy()
           obs_df = obs_df.sort_values('date')
           
           # Time-series features
           features = {
               'ndvi_mean': obs_df['ndvi'].mean(),
               'ndvi_std': obs_df['ndvi'].std(),
               'ndvi_min': obs_df['ndvi'].min(),
               'ndvi_max': obs_df['ndvi'].max(),
               'evi_mean': obs_df['evi'].mean() if 'evi' in obs_df else 0,
               'evi_std': obs_df['evi'].std() if 'evi' in obs_df else 0,
               'cloud_cover_mean': obs_df['cloud_cover'].mean(),
               'observation_count': len(obs_df),
           }
           
           # Trend
           x = np.arange(len(obs_df))
           y = obs_df['ndvi'].values
           mask = ~np.isnan(y)
           if len(x[mask]) >= 2:
               coeffs = np.polyfit(x[mask], y[mask], 1)
               features['trend_slope'] = coeffs[0]
           else:
               features['trend_slope'] = 0
           
           # Seasonality
           obs_df['month'] = pd.to_datetime(obs_df['date']).dt.month
           monthly = obs_df.groupby('month')['ndvi'].agg(['mean', 'std'])
           if len(monthly) > 0:
               features['seasonal_amplitude'] = monthly['mean'].max() - monthly['mean'].min()
           else:
               features['seasonal_amplitude'] = 0
           
           return pd.DataFrame([features])
       
       def create_training_dataset(self, projects_features: list) -> Tuple[np.ndarray, np.ndarray]:
           """
           Create X, y matrices from project features
           
           X: Feature matrix
           y: Ground truth labels (0=no growth, 1=growth, -1=loss)
           """
           X_list = []
           y_list = []
           
           for project in projects_features:
               features_dict = project['features']
               X_list.append([
                   features_dict.get('ndvi_mean', 0),
                   features_dict.get('ndvi_std', 0),
                   features_dict.get('trend_slope', 0),
                   features_dict.get('seasonal_amplitude', 0),
                   features_dict.get('observation_count', 0),
               ])
               
               # Label based on trend and verification
               trend_slope = features_dict.get('trend_slope', 0)
               if trend_slope > 0.001:  # positive growth
                   y_list.append(1)
               elif trend_slope < -0.001:  # loss
                   y_list.append(-1)
               else:
                   y_list.append(0)
           
           X = np.array(X_list)
           y = np.array(y_list)
           
           # Scale features
           X_scaled = self.scaler.fit_transform(X)
           
           return X_scaled, y
   ```

2. **Create Reference Dataset**
   - If real reference data unavailable, create synthetic training data based on:
     - NDVI patterns from public datasets (FAO, GEE)
     - Indian agroforestry/forest region characteristics
     - Annotated outcomes from carbon projects
   
   ```python
   # src/ml_models/synthetic_data_generator.py
   import numpy as np
   import pandas as pd
   from datetime import datetime, timedelta
   
   def generate_synthetic_training_data(n_projects: int = 50) -> list:
       """Generate synthetic training data for MVP"""
       projects = []
       
       for i in range(n_projects):
           # Random project characteristics
           base_ndvi = np.random.uniform(0.3, 0.7)  # baseline NDVI
           trend = np.random.uniform(-0.001, 0.005)  # growth trend
           
           # Generate time series
           dates = pd.date_range('2021-01-01', '2023-12-31', freq='10D')
           ndvi_values = base_ndvi + trend * np.arange(len(dates)) + np.random.normal(0, 0.05, len(dates))
           ndvi_values = np.clip(ndvi_values, 0.2, 1.0)
           
           # Create observation record
           obs = pd.DataFrame({
               'date': dates,
               'ndvi': ndvi_values,
               'evi': ndvi_values * 0.7,  # EVI correlated with NDVI
               'cloud_cover': np.random.uniform(0, 40, len(dates))
           })
           
           # Calculate growth label
           x = np.arange(len(obs))
           y = obs['ndvi'].values
           coeffs = np.polyfit(x, y, 1)
           slope = coeffs[0]
           
           label = 1 if slope > 0.001 else (-1 if slope < -0.001 else 0)
           
           projects.append({
               'project_id': f'synthetic_{i}',
               'observations': obs,
               'label': label,
               'features': {
                   'ndvi_mean': obs['ndvi'].mean(),
                   'ndvi_std': obs['ndvi'].std(),
                   'trend_slope': slope,
                   'seasonal_amplitude': obs.groupby(obs['date'].dt.month)['ndvi'].mean().max() - obs.groupby(obs['date'].dt.month)['ndvi'].mean().min()
               }
           })
       
       return projects
   ```

3. **Document Training Data Requirements**
   - For production: Ground-truth biomass measurements from 20+ projects
   - Temporal coverage: At least 2-3 years per project
   - Geographic diversity: Across Indian agro-climatic zones
   - Regional calibration: Separate models for Himalayan, Western Ghats, Deccan regions

**Deliverables:**
- [ ] TrainingDataPreparator class
- [ ] Synthetic training dataset generated (50+ examples)
- [ ] Feature engineering pipeline
- [ ] Train/test split strategy defined
- [ ] Data quality documentation

**Files to Create:**
- `src/ml_models/data_preparation.py`
- `src/ml_models/synthetic_data_generator.py`
- `tests/test_data_preparation.py`

---

### Task 2.2: Model Training & Evaluation (Days 3–6)

**Objective:** Train ML models for growth classification and confidence scoring

**Steps:**

1. **Create Model Trainer**
   ```python
   # src/ml_models/model_trainer.py
   import numpy as np
   import pandas as pd
   from sklearn.ensemble import GradientBoostingClassifier, RandomForestRegressor
   from sklearn.model_selection import train_test_split, cross_val_score
   from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score, roc_curve
   import joblib
   import json
   from datetime import datetime
   import logging
   
   logger = logging.getLogger(__name__)
   
   class GrowthClassificationModel:
       """Gradient boosting model for growth classification"""
       
       def __init__(self):
           self.model = GradientBoostingClassifier(
               n_estimators=100,
               learning_rate=0.1,
               max_depth=5,
               min_samples_split=5,
               min_samples_leaf=2,
               random_state=42
           )
           self.version = datetime.now().strftime("%Y%m%d_%H%M%S")
           self.metrics = {}
       
       def train(self, X: np.ndarray, y: np.ndarray):
           """Train model on features and labels"""
           # Train/test split
           X_train, X_test, y_train, y_test = train_test_split(
               X, y, test_size=0.2, random_state=42, stratify=y
           )
           
           # Train
           self.model.fit(X_train, y_train)
           
           # Evaluate
           y_pred = self.model.predict(X_test)
           y_proba = self.model.predict_proba(X_test)
           
           self.metrics = {
               'train_score': self.model.score(X_train, y_train),
               'test_score': self.model.score(X_test, y_test),
               'cv_scores': cross_val_score(self.model, X, y, cv=5).tolist(),
               'classification_report': classification_report(y_test, y_pred, output_dict=True),
               'feature_importance': self.model.feature_importances_.tolist(),
               'confusion_matrix': confusion_matrix(y_test, y_pred).tolist()
           }
           
           logger.info(f"Model trained: test accuracy = {self.metrics['test_score']:.3f}")
           return self.metrics
       
       def predict(self, X: np.ndarray):
           """Predict class and confidence"""
           predictions = self.model.predict(X)
           probabilities = self.model.predict_proba(X)
           
           # Confidence = max probability
           confidence = probabilities.max(axis=1)
           
           return predictions, confidence
       
       def save(self, path: str):
           """Save model and metadata"""
           joblib.dump(self.model, f"{path}/growth_model_{self.version}.pkl")
           
           # Save metadata
           metadata = {
               'version': self.version,
               'created_at': datetime.now().isoformat(),
               'model_type': 'GradientBoostingClassifier',
               'metrics': self.metrics,
               'feature_names': ['ndvi_mean', 'ndvi_std', 'trend_slope', 'seasonal_amplitude', 'obs_count']
           }
           
           with open(f"{path}/model_metadata_{self.version}.json", 'w') as f:
               json.dump(metadata, f, indent=2)
           
           logger.info(f"Model saved to {path}")
   
   class BiomassEstimationModel:
       """Random forest model for continuous biomass estimation"""
       
       def __init__(self):
           self.model = RandomForestRegressor(
               n_estimators=100,
               max_depth=10,
               min_samples_split=5,
               random_state=42
           )
           self.version = datetime.now().strftime("%Y%m%d_%H%M%S")
           self.metrics = {}
       
       def train(self, X: np.ndarray, y: np.ndarray):
           """Train biomass estimation model"""
           X_train, X_test, y_train, y_test = train_test_split(
               X, y, test_size=0.2, random_state=42
           )
           
           self.model.fit(X_train, y_train)
           
           # Metrics
           from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
           y_pred = self.model.predict(X_test)
           
           self.metrics = {
               'r2_score': r2_score(y_test, y_pred),
               'rmse': np.sqrt(mean_squared_error(y_test, y_pred)),
               'mae': mean_absolute_error(y_test, y_pred),
               'feature_importance': self.model.feature_importances_.tolist()
           }
           
           logger.info(f"Biomass model trained: R² = {self.metrics['r2_score']:.3f}")
           return self.metrics
       
       def predict(self, X: np.ndarray):
           """Predict biomass values"""
           predictions = self.model.predict(X)
           return predictions
   ```

2. **Create Training Pipeline**
   ```python
   # src/ml_models/training_pipeline.py
   from src.ml_models.data_preparation import TrainingDataPreparator
   from src.ml_models.synthetic_data_generator import generate_synthetic_training_data
   from src.ml_models.model_trainer import GrowthClassificationModel, BiomassEstimationModel
   
   class TrainingPipeline:
       def __init__(self, data_source='synthetic'):
           self.data_source = data_source
           self.growth_model = GrowthClassificationModel()
           self.biomass_model = BiomassEstimationModel()
       
       def run(self, output_path='models/'):
           """Run full training pipeline"""
           # Get training data
           if self.data_source == 'synthetic':
               projects = generate_synthetic_training_data(n_projects=50)
           else:
               projects = self._load_real_data()
           
           # Prepare features
           preparator = TrainingDataPreparator()
           X = []
           y_growth = []
           y_biomass = []
           
           for project in projects:
               X.append(self._extract_features(project))
               y_growth.append(project.get('label', 0))
               y_biomass.append(project.get('biomass_label', 50))
           
           X = np.array(X)
           y_growth = np.array(y_growth)
           y_biomass = np.array(y_biomass)
           
           # Train models
           self.growth_model.train(X, y_growth)
           self.biomass_model.train(X, y_biomass)
           
           # Save models
           self.growth_model.save(output_path)
           self.biomass_model.save(output_path)
           
           return {
               'growth_metrics': self.growth_model.metrics,
               'biomass_metrics': self.biomass_model.metrics
           }
   ```

3. **Run Training & Log Results**
   ```bash
   python -m src.ml_models.training_pipeline --output models/
   ```

**Deliverables:**
- [ ] Growth classification model trained
- [ ] Biomass estimation model trained
- [ ] Model metrics documented
- [ ] Feature importance analyzed
- [ ] Models saved with versioning
- [ ] Training reproducible with fixed random seed

**Files to Create:**
- `src/ml_models/model_trainer.py`
- `src/ml_models/training_pipeline.py`
- `models/` (directory for saved models)
- `tests/test_model_trainer.py`

---

### Task 2.3: ML Inference Service (Days 6–9)

**Objective:** Create production-ready inference service

**Steps:**

1. **Create Inference Service**
   ```python
   # src/ml_models/inference_service.py
   import joblib
   import json
   from pathlib import Path
   import logging
   
   logger = logging.getLogger(__name__)
   
   class InferenceService:
       """Load models and make predictions"""
       
       def __init__(self, model_dir: str = 'models/'):
           self.model_dir = model_dir
           self.growth_model = None
           self.biomass_model = None
           self.metadata = None
           self.load_models()
       
       def load_models(self):
           """Load latest model versions"""
           model_path = Path(self.model_dir)
           
           # Find latest model files
           growth_models = list(model_path.glob('growth_model_*.pkl'))
           if growth_models:
               latest = sorted(growth_models)[-1]
               self.growth_model = joblib.load(latest)
               logger.info(f"Loaded growth model: {latest.name}")
           
           # Load metadata
           metadata_files = list(model_path.glob('model_metadata_*.json'))
           if metadata_files:
               latest = sorted(metadata_files)[-1]
               with open(latest) as f:
                   self.metadata = json.load(f)
               logger.info(f"Loaded metadata: {latest.name}")
       
       def predict_growth(self, features: dict) -> dict:
           """
           Predict growth classification and confidence
           
           Input features:
               - ndvi_mean
               - ndvi_std
               - trend_slope
               - seasonal_amplitude
               - observation_count
           
           Returns:
               {
                   'prediction': 'growth' | 'stable' | 'loss',
                   'confidence': 0.0-1.0,
                   'probability_distribution': {growth, stable, loss}
               }
           """
           if not self.growth_model:
               raise RuntimeError("Model not loaded")
           
           # Convert to feature array
           X = np.array([[
               features.get('ndvi_mean', 0),
               features.get('ndvi_std', 0),
               features.get('trend_slope', 0),
               features.get('seasonal_amplitude', 0),
               features.get('observation_count', 0)
           ]])
           
           # Predict
           prediction = self.growth_model.predict(X)[0]
           probabilities = self.growth_model.predict_proba(X)[0]
           confidence = probabilities.max()
           
           # Map prediction to label
           label_map = {-1: 'loss', 0: 'stable', 1: 'growth'}
           
           return {
               'prediction': label_map[prediction],
               'confidence': float(confidence),
               'probabilities': {
                   'loss': float(probabilities[0]),
                   'stable': float(probabilities[1]),
                   'growth': float(probabilities[2])
               }
           }
   ```

2. **Create Inference Endpoint**
   ```python
   # src/api/routers/ml_scoring.py
   from fastapi import APIRouter, Depends
   from pydantic import BaseModel
   from src.api.database import get_db
   from src.ml_models.inference_service import InferenceService
   from src.feature_extraction.feature_calculator import PipelineFeatureExtractor
   
   router = APIRouter()
   inference_service = InferenceService()
   
   class ScoringRequest(BaseModel):
       project_id: str
       start_date: str
       end_date: str
   
   class ScoringResponse(BaseModel):
       project_id: str
       prediction: str
       confidence: float
       probabilities: dict
   
   @router.post("/score", response_model=ScoringResponse)
   def score_project(
       request: ScoringRequest,
       db = Depends(get_db)
   ):
       """ML scoring for project"""
       # Extract features
       extractor = PipelineFeatureExtractor(db)
       features = extractor.extract_features(
           request.project_id,
           request.start_date,
           request.end_date
       )
       
       # Get ML prediction
       result = inference_service.predict_growth(features)
       
       # Log prediction
       from src.api.models import ProcessingLog
       log = ProcessingLog(
           project_id=request.project_id,
           operation_type="ml_scoring",
           status="success",
           output_data=result
       )
       db.add(log)
       db.commit()
       
       return ScoringResponse(
           project_id=request.project_id,
           **result
       )
   ```

**Deliverables:**
- [ ] InferenceService loads and serves models
- [ ] ML scoring endpoint operational
- [ ] Predictions logged with versioning
- [ ] Inference response time < 500ms
- [ ] Model versioning tracked
- [ ] Error handling for missing models

**Files to Create:**
- `src/ml_models/inference_service.py`
- `src/api/routers/ml_scoring.py`
- `tests/test_inference_service.py`

---

### Task 2.4: Model Registry & Versioning (Days 8–9)

**Objective:** Track model versions and enable rollback

**Steps:**

1. **Create Model Registry**
   ```python
   # src/ml_models/model_registry.py
   from sqlalchemy import Column, String, DateTime, Float, JSON
   from sqlalchemy.ext.declarative import declarative_base
   from datetime import datetime
   import json
   
   Base = declarative_base()
   
   class ModelRegistry(Base):
       __tablename__ = "model_registry"
       
       id = Column(String, primary_key=True)
       model_type = Column(String)  # growth_classification, biomass_estimation
       version = Column(String)
       metrics = Column(JSON)
       status = Column(String)  # active, archived, deprecated
       created_at = Column(DateTime, default=datetime.utcnow)
       deployed_at = Column(DateTime)
       model_path = Column(String)
   ```

2. **Create Registry Service**
   ```python
   # src/ml_models/registry_service.py
   from sqlalchemy.orm import Session
   
   class RegistryService:
       def __init__(self, db: Session):
           self.db = db
       
       def register_model(self, model_type, version, metrics, model_path):
           """Register trained model"""
           from src.ml_models.model_registry import ModelRegistry
           
           registry = ModelRegistry(
               id=f"{model_type}_{version}",
               model_type=model_type,
               version=version,
               metrics=metrics,
               status='archived',
               model_path=model_path
           )
           self.db.add(registry)
           self.db.commit()
       
       def activate_model(self, model_id):
           """Deploy model to production"""
           model = self.db.query(ModelRegistry).filter(
               ModelRegistry.id == model_id
           ).first()
           model.status = 'active'
           model.deployed_at = datetime.utcnow()
           self.db.commit()
       
       def list_models(self, model_type):
           """List all versions of a model"""
           return self.db.query(ModelRegistry).filter(
               ModelRegistry.model_type == model_type
           ).order_by(ModelRegistry.created_at.desc()).all()
   ```

**Deliverables:**
- [ ] Model registry database table
- [ ] Registry service for tracking versions
- [ ] Ability to activate/deprecate models
- [ ] Model metrics stored with each version
- [ ] Deployment audit trail

**Files to Create:**
- `src/ml_models/model_registry.py`
- `src/ml_models/registry_service.py`

---

## ✅ Phase 2 Checklist

- [ ] Training data prepared (synthetic + real where available)
- [ ] Growth classification model trained and evaluated
- [ ] Biomass estimation model trained and evaluated
- [ ] Model metrics documented and acceptable
- [ ] InferenceService implemented
- [ ] ML scoring endpoint working
- [ ] Model registry tracking versions
- [ ] Model versioning system operational
- [ ] All CI/CD tests passing
- [ ] ML predictions integrated with verification rules
- [ ] Ready for evidence packaging (Phase 3)

---

## 📊 Phase 2 Deliverables

| Component | Status | Notes |
|-----------|--------|-------|
| Training Data | ✅ | Synthetic + reference data |
| Classification Model | ✅ | Gradient boosting with metrics |
| Biomass Model | ✅ | Random forest regression |
| Inference Service | ✅ | Production-ready predictions |
| Model Registry | ✅ | Version tracking & deployment |
| Scoring Endpoint | ✅ | API integration |

---

**Next Phase:** [Phase 3: Evidence & Audit Packaging](phase3_evidence_packaging.md)  
**Timeline:** Weeks 10–11
