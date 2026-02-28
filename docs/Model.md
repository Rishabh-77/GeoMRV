# GeoMRV — ML Model R&D Documentation

**Last updated:** 2026-02-28  
**Status:** Phase 2 (Tasks 2.1–2.2 complete)

---

## What This Document Covers

This is a high-level overview of the machine learning models built for GeoMRV — what they do, why they were chosen, what data they use, how well they perform, and what the numbers mean in plain English.

---

## 1. The Problem (In Plain English)

GeoMRV monitors forests and plantations using satellite imagery to verify that trees are actually growing for carbon credit projects. Satellites take pictures of the ground every ~10 days. From those pictures, we extract a "greenness score" (called NDVI) that tells us how healthy and dense the vegetation is.

The challenge: **How do you take hundreds of greenness measurements over 3 years and turn them into a simple answer — "Yes, this forest is growing" or "No, something is wrong"?**

That's what the ML models do. They look at patterns in the data and give two answers:

1. **Is this project growing, stable, or losing vegetation?** (Classification)
2. **How much biomass (plant matter) is there?** (Estimation)

---

## 2. Why These Models (Not Deep Learning)

| Consideration | Our Choice | Why |
|---|---|---|
| Data type | Tabular (10 numeric features) | Not images or text — no need for neural networks |
| Dataset size | 60 projects (MVP) | Deep learning needs thousands; classical ML works with dozens |
| Explainability | Required for auditors | Gradient boosting gives feature importance; neural nets are "black boxes" |
| Compute cost | Must run on Azure Student Pack | Tree-based models train in <1 second; no GPU needed |
| Audit compliance | Must explain every decision | Regulators and carbon auditors need to understand *why* a score was given |

**Bottom line:** We use simple, proven algorithms that are fast, explainable, and work well with small datasets. This is the standard approach in environmental monitoring and scientific applications.

---

## 3. The Two Models

### 3.1 Growth Classification Model

**What it does:** Looks at satellite data and classifies each project as one of three categories:

| Label | Meaning | When it triggers |
|---|---|---|
| **Growth** (+1) | Vegetation is increasing | NDVI trending upward over time |
| **Stable** (0) | Vegetation is flat | No significant change in greenness |
| **Loss** (−1) | Vegetation is declining | NDVI trending downward — could indicate deforestation or drought |

**Algorithm:** Gradient Boosting Classifier (100 decision trees that learn from each other's mistakes)

**Think of it like this:** Imagine 100 experts each looking at the data. Each expert focuses on the mistakes of the previous one. At the end, they all vote, and the majority wins. That's gradient boosting.

**Key hyperparameters:**

| Parameter | Value | What it means |
|---|---|---|
| `n_estimators` | 100 | 100 sequential decision trees |
| `learning_rate` | 0.1 | Each tree only makes a small correction (prevents overconfidence) |
| `max_depth` | 5 | Each tree can ask up to 5 yes/no questions |
| `min_samples_split` | 5 | Won't split a group smaller than 5 projects |
| `min_samples_leaf` | 2 | Every final group must have at least 2 projects |
| `random_state` | 42 | Fixed seed so results are reproducible every time |

### 3.2 Biomass Estimation Model

**What it does:** Predicts how much plant biomass (in tonnes per hectare) a project area holds, based on the same satellite features.

**Algorithm:** Random Forest Regressor (100 independent decision trees that each give an estimate; the average is the final answer)

**Think of it like this:** Imagine asking 100 people to estimate the weight of a tree by looking at its greenness from a photo. Some will guess high, some low, but the average of all their guesses is usually very close to the truth. That's a random forest.

**Key hyperparameters:**

| Parameter | Value | What it means |
|---|---|---|
| `n_estimators` | 100 | 100 independent decision trees |
| `max_depth` | 10 | Each tree can ask up to 10 yes/no questions |
| `min_samples_split` | 5 | Won't split small groups |
| `random_state` | 42 | Reproducible results |

---

## 4. What the Models Look At (10 Features)

Each project is summarised into 10 numbers before being fed to the models:

| # | Feature | What it measures | Layman's explanation |
|---|---|---|---|
| 1 | `ndvi_mean` | Average greenness | How green is this area on average? |
| 2 | `ndvi_std` | Greenness variability | Does the greenness bounce around a lot? |
| 3 | `ndvi_min` | Lowest greenness recorded | How bad does it get in the worst season? |
| 4 | `ndvi_max` | Highest greenness recorded | How lush does it get at its peak? |
| 5 | `evi_mean` | Average enhanced vegetation index | A second "greenness" check (more accurate in dense forests) |
| 6 | `evi_std` | EVI variability | Stability of the secondary greenness measure |
| 7 | `cloud_cover_mean` | Average cloud cover | How often were satellite images blocked by clouds? |
| 8 | `observation_count` | Number of clear images | How many clean data points do we have? |
| 9 | `trend_slope` | Direction of change over time | Is the greenness going up, down, or flat? |
| 10 | `seasonal_amplitude` | Monsoon vs. dry season difference | How much does greenness change with seasons? |

All features are **standardised** (scaled to mean=0, std=1) before training so that no single feature dominates just because its numbers are bigger.

---

## 5. Training Data

### Why synthetic data?

Real ground-truth biomass data from Indian carbon projects is expensive and scarce. For the MVP, we generate realistic synthetic data that mimics actual satellite patterns.

### How synthetic data is generated

Each fake "project" gets:
- A **region** — randomly picked from 5 Indian agro-climatic zones (Western Ghats, Deccan Plateau, Indo-Gangetic Plain, Himalayan Foothills, Arid Rajasthan)
- A **vegetation profile** — growth, stable, or loss
- A **3-year time series** — ~100 observations at 10-day intervals (Sentinel-2 cadence)
- **Monsoon seasonality** — NDVI boost during June–September with Gaussian peak in August
- **Realistic cloud cover** — higher during monsoon, lower in dry season
- **Random noise** — matching real Sentinel-2 observation quality

### Dataset statistics

| Metric | Value |
|---|---|
| Total projects | 60 |
| Growth projects | 20 |
| Stable projects | 20 |
| Loss projects | 20 |
| Observations per project | ~94–106 (variable, simulating real gaps) |
| Time span | 2021-01-01 to 2023-12-31 |
| India regions covered | 5 |

### Train / test split

| Split | Count | Purpose |
|---|---|---|
| Training | 48 (80%) | Model learns from this data |
| Testing | 12 (20%) | Model is evaluated on data it has never seen |

The split is **stratified** — each split has equal proportions of growth/stable/loss labels. This prevents the model from being biased toward one category.

---

## 6. How Well Do They Perform?

### Growth Classification

| Metric | Value | What it means |
|---|---|---|
| **Test Accuracy** | 91.7% | Gets the right answer 11 out of 12 times |
| **CV Mean ± Std** | 89.6% ± 10.6% | Consistent across different data splits |
| **Growth Precision** | 100% | When it says "growth," it's always right |
| **Growth Recall** | 100% | Catches every growth project |
| **Loss Precision** | 80% | When it says "loss," it's right 4 out of 5 times |
| **Loss Recall** | 100% | Catches every loss project |
| **Stable Precision** | 100% | When it says "stable," it's always right |
| **Stable Recall** | 75% | Misses 1 out of 4 stable projects (labels it as loss) |

**Confusion matrix (what the model predicted vs. reality):**

|  | Predicted Loss | Predicted Stable | Predicted Growth |
|---|---|---|---|
| **Actual Loss** | 4 ✅ | 0 | 0 |
| **Actual Stable** | 1 ❌ | 3 ✅ | 0 |
| **Actual Growth** | 0 | 0 | 4 ✅ |

**In plain terms:** The model is very good at detecting growth and loss. Its only weakness is occasionally confusing a stable project with a loss project — which is actually a conservative (safe) mistake for a verification system.

### Biomass Estimation

| Metric | Value | What it means |
|---|---|---|
| **R²** | 0.995 | Model explains 99.5% of the variation in biomass |
| **RMSE** | 1.15 t/ha | Typical error is ~1.15 tonnes per hectare |
| **MAE** | 0.87 t/ha | Average error is less than 1 tonne per hectare |
| **CV Mean** | 0.965 | Consistent performance across 5-fold cross-validation |

**In plain terms:** The biomass estimates are extremely close to the calculated targets. An error of ~1 tonne per hectare is excellent for satellite-based estimation.

---

## 7. What Drives the Predictions?

### Growth Classification — Feature Importance

```
trend_slope          ████████████████████████████████████  72.0%
ndvi_std             ████████████  24.5%
cloud_cover_mean     ██  3.5%
other features       ░  0%
```

**Insight:** The model relies almost entirely on `trend_slope` — the direction the greenness is heading. This makes intuitive sense: the most reliable way to tell if a forest is growing is to look at whether the greenness line goes up or down over time.

### Biomass Estimation — Feature Importance

```
ndvi_mean            ██████████████████████  44.6%
evi_mean             ████████████████████  38.8%
ndvi_max             ████  8.7%
ndvi_min             ███  5.7%
cloud_cover_mean     █  1.4%
other features       ░  <1%
```

**Insight:** Biomass depends mainly on average (NDVI and EVI), not trend. This makes sense: how much plant matter is there *right now* depends on the current greenness level, not whether it's increasing or decreasing.

---

## 8. Model Versioning

Every training run produces uniquely versioned artifacts:

```
models/
├── growth_model_20260228_165439.pkl         # Trained classifier (binary)
├── growth_metadata_20260228_165439.json     # Full metrics + params
├── biomass_model_20260228_165439.pkl        # Trained regressor (binary)
├── biomass_metadata_20260228_165439.json    # Full metrics + params
└── pipeline_report_20260228_165439.json     # End-to-end run summary
```

Version format: `YYYYMMDD_HHMMSS` (UTC timestamp at training time).

This means:
- Every model can be traced back to exactly when it was trained
- Old models can be loaded for comparison or rollback
- Audit trail is preserved for carbon credit verification

---

## 9. Known Limitations & Next Steps

| Limitation | Impact | Planned Fix |
|---|---|---|
| Synthetic training data only | Model hasn't seen real-world noise | Replace with real project data when available |
| Small dataset (60 projects) | Limited generalisation | Expand to 200+ with regional calibration |
| No regional sub-models | Single model for all of India | Train separate models per agro-climatic zone |
| Biomass proxy formula is placeholder | Coefficients not calibrated to India | Calibrate against field measurements |
| No uncertainty quantification | Model gives a single prediction | Add prediction intervals (conformal prediction) |
| No model drift monitoring | Performance may degrade over time | Add periodic retraining + monitoring pipeline |

### Production readiness path

1. **Task 2.3 (next):** Build inference service (API endpoint for real-time predictions)
2. **Task 2.4:** Model registry in database (versioning + activation tracking)
3. **Phase 3:** Connect ML scores to evidence packages for auditors
4. **Post-MVP:** Replace synthetic data with field-validated ground truth

---

## 10. How to Reproduce

```bash
# Train both models from scratch (deterministic, same results every time)
python -m src.ml_models.training_pipeline --output models/ --n-projects 60 --seed 42

# Expected output:
# Growth accuracy  : 91.7%
# Biomass R²       : 0.995
# Files saved      : 5 artifacts in models/
```

---

## Glossary

| Term | Definition |
|---|---|
| **NDVI** | Normalized Difference Vegetation Index — a 0-to-1 score of how green/healthy vegetation is. Measured from satellite images. |
| **EVI** | Enhanced Vegetation Index — similar to NDVI but better in dense forests. |
| **Gradient Boosting** | An ML technique where many small decision trees are trained sequentially, each correcting the errors of the previous one. |
| **Random Forest** | An ML technique where many decision trees are trained independently and their predictions are averaged. |
| **R²** | How much of the variation in the data the model explains. 1.0 = perfect; 0.0 = no better than guessing the average. |
| **RMSE** | Root Mean Squared Error — typical prediction error in the same units as the target. |
| **MAE** | Mean Absolute Error — average prediction error, ignoring direction. |
| **Cross-validation** | Testing the model on multiple different train/test splits to check consistency. |
| **Stratified split** | Ensuring each data split has the same proportion of each label (growth/stable/loss). |
| **Feature importance** | How much each input variable contributes to the model's decisions. |
| **Overfitting** | When a model memorises training data instead of learning general patterns. Detected when train accuracy >> test accuracy. |
