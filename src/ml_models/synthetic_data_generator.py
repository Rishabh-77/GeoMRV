"""
GeoMRV Synthetic Training Data Generator
=========================================
Generate realistic synthetic satellite observation data for ML model
training when ground-truth reference data is unavailable.

The generator creates three vegetation profiles calibrated for Indian
agro-climatic regions:

- **Growth** – steadily increasing NDVI (afforestation / restoration)
- **Stable** – flat or seasonal-only NDVI (established forest)
- **Loss** – declining NDVI (deforestation / degradation)

Each profile includes monsoon-aware seasonality, cloud-cover simulation,
and realistic noise levels derived from Sentinel-2 observation
characteristics.

Usage
-----
    from src.ml_models.synthetic_data_generator import SyntheticDataGenerator

    gen = SyntheticDataGenerator(random_state=42)

    # Generate 100 projects (balanced across profiles)
    projects = gen.generate(n_projects=100)

    # Each project dict has keys: project_id, observations (DataFrame),
    # label (int), features (dict), region, profile.

    # Quick conversion to (X, y) via TrainingDataPreparator
    from src.ml_models.data_preparation import TrainingDataPreparator
    preparator = TrainingDataPreparator()
    X, y = preparator.create_training_dataset(projects)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Region definitions (India agro-climatic zones)
# ──────────────────────────────────────────────────────────────

@dataclass
class RegionProfile:
    """Baseline vegetation parameters for an Indian region."""
    name: str
    base_ndvi_range: tuple[float, float]   # (low, high) NDVI baseline
    monsoon_boost: float                    # NDVI increase during monsoon (Jun–Sep)
    cloud_cover_monsoon: float              # avg cloud % during monsoon
    cloud_cover_dry: float                  # avg cloud % during dry season
    noise_std: float                        # observation noise σ


INDIA_REGIONS: list[RegionProfile] = [
    RegionProfile(
        name="Western Ghats",
        base_ndvi_range=(0.55, 0.75),
        monsoon_boost=0.12,
        cloud_cover_monsoon=55.0,
        cloud_cover_dry=15.0,
        noise_std=0.04,
    ),
    RegionProfile(
        name="Deccan Plateau",
        base_ndvi_range=(0.30, 0.50),
        monsoon_boost=0.18,
        cloud_cover_monsoon=45.0,
        cloud_cover_dry=10.0,
        noise_std=0.05,
    ),
    RegionProfile(
        name="Indo-Gangetic Plain",
        base_ndvi_range=(0.40, 0.60),
        monsoon_boost=0.15,
        cloud_cover_monsoon=50.0,
        cloud_cover_dry=12.0,
        noise_std=0.04,
    ),
    RegionProfile(
        name="Himalayan Foothills",
        base_ndvi_range=(0.50, 0.70),
        monsoon_boost=0.10,
        cloud_cover_monsoon=60.0,
        cloud_cover_dry=20.0,
        noise_std=0.05,
    ),
    RegionProfile(
        name="Arid Rajasthan",
        base_ndvi_range=(0.15, 0.35),
        monsoon_boost=0.20,
        cloud_cover_monsoon=35.0,
        cloud_cover_dry=5.0,
        noise_std=0.06,
    ),
]


# ──────────────────────────────────────────────────────────────
# Generator
# ──────────────────────────────────────────────────────────────

class SyntheticDataGenerator:
    """Generate synthetic satellite observations for training.

    Parameters
    ----------
    random_state : int
        Seed for reproducibility.
    start_date : str
        First observation date (ISO format).
    end_date : str
        Last observation date (ISO format).
    cadence_days : int
        Interval between observations (Sentinel-2 ≈ 10 days).
    """

    # Vegetation profile names →  trend slope per observation step
    PROFILES: dict[str, tuple[float, float]] = {
        "growth":  (0.0005, 0.004),   # positive trend range
        "stable":  (-0.0003, 0.0003), # near-zero trend
        "loss":    (-0.004, -0.0005), # negative trend (degradation)
    }

    PROFILE_LABELS: dict[str, int] = {
        "growth": 1,
        "stable": 0,
        "loss": -1,
    }

    def __init__(
        self,
        random_state: int = 42,
        start_date: str = "2021-01-01",
        end_date: str = "2023-12-31",
        cadence_days: int = 10,
    ) -> None:
        self.rng = np.random.RandomState(random_state)
        self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d")
        self.cadence_days = cadence_days

    # ── public API ────────────────────────────────────────────

    def generate(
        self,
        n_projects: int = 50,
        profile_weights: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """Generate *n_projects* synthetic project datasets.

        Parameters
        ----------
        n_projects : int
            Total number of projects to create (≥ 3 recommended for
            stratified splitting).
        profile_weights : dict, optional
            Relative weights for each profile.  Defaults to balanced
            (⅓ growth, ⅓ stable, ⅓ loss).

        Returns
        -------
        List of dicts, each containing:
            - project_id : str
            - observations : DataFrame (date, ndvi, evi, cloud_cover)
            - label : int  (1, 0, -1)
            - features : dict  (flat feature dict matching FEATURE_COLUMNS)
            - region : str
            - profile : str
        """
        if profile_weights is None:
            profile_weights = {"growth": 1.0, "stable": 1.0, "loss": 1.0}

        # Resolve counts per profile
        profiles = list(profile_weights.keys())
        weights = np.array([profile_weights[p] for p in profiles])
        weights = weights / weights.sum()
        counts = np.round(weights * n_projects).astype(int)
        # Fix rounding to hit exact total
        counts[-1] = n_projects - counts[:-1].sum()

        projects: List[Dict[str, Any]] = []
        idx = 0
        for profile, count in zip(profiles, counts):
            for _ in range(count):
                project = self._generate_single(idx, profile)
                projects.append(project)
                idx += 1

        # Shuffle to avoid ordering bias
        self.rng.shuffle(projects)

        logger.info(
            "Generated %d synthetic projects: %s",
            len(projects),
            {p: int(c) for p, c in zip(profiles, counts)},
        )
        return projects

    # ── single project generator ──────────────────────────────

    def _generate_single(self, idx: int, profile: str) -> Dict[str, Any]:
        """Create one synthetic project with the given vegetation profile."""

        # Pick a random Indian region
        region = INDIA_REGIONS[self.rng.randint(len(INDIA_REGIONS))]

        # Random baseline NDVI within region range
        base_ndvi = self.rng.uniform(*region.base_ndvi_range)

        # Random trend slope within profile range
        slope_lo, slope_hi = self.PROFILES[profile]
        trend_slope = self.rng.uniform(slope_lo, slope_hi)

        # Generate date range
        dates = self._generate_dates()
        n_obs = len(dates)

        # Build NDVI time-series
        ndvi = np.full(n_obs, base_ndvi, dtype=np.float64)

        # 1) Add trend component
        ndvi += trend_slope * np.arange(n_obs)

        # 2) Add monsoon seasonality (June–September boost)
        months = np.array([d.month for d in dates])
        monsoon_mask = (months >= 6) & (months <= 9)
        # Smooth seasonal curve: peak in August
        seasonal = np.zeros(n_obs)
        for i, m in enumerate(months):
            if 6 <= m <= 9:
                # Bell curve peaking at month 8
                seasonal[i] = region.monsoon_boost * np.exp(
                    -0.5 * ((m - 8) / 1.2) ** 2
                )
        ndvi += seasonal

        # 3) Add random noise
        ndvi += self.rng.normal(0, region.noise_std, n_obs)

        # Clamp to valid range
        ndvi = np.clip(ndvi, 0.05, 0.98)

        # EVI ≈ 0.65–0.75 × NDVI (empirical relationship)
        evi_ratio = self.rng.uniform(0.65, 0.75)
        evi = ndvi * evi_ratio

        # Cloud cover: higher during monsoon
        cloud_cover = np.where(
            monsoon_mask,
            self.rng.uniform(
                region.cloud_cover_monsoon - 15,
                region.cloud_cover_monsoon + 15,
                n_obs,
            ),
            self.rng.uniform(
                region.cloud_cover_dry,
                region.cloud_cover_dry + 20,
                n_obs,
            ),
        )
        cloud_cover = np.clip(cloud_cover, 0, 100)

        # Build observations DataFrame
        obs_df = pd.DataFrame({
            "date": dates,
            "ndvi": np.round(ndvi, 6),
            "evi": np.round(evi, 6),
            "cloud_cover": np.round(cloud_cover, 2),
        })

        # Compute flat features for the training matrix
        features = self._compute_features(obs_df)

        # Determine label
        label = self.PROFILE_LABELS[profile]

        return {
            "project_id": f"synthetic_{idx:04d}",
            "observations": obs_df,
            "label": label,
            "features": features,
            "region": region.name,
            "profile": profile,
        }

    # ── helpers ───────────────────────────────────────────────

    def _generate_dates(self) -> list[datetime]:
        """Generate observation dates at configured cadence, with
        occasional random gaps to simulate missing acquisitions."""
        dates: list[datetime] = []
        current = self.start_date
        while current <= self.end_date:
            dates.append(current)
            # Occasionally add an extra gap (10 % chance of skipping one cycle)
            skip = 2 if self.rng.random() < 0.10 else 1
            current += timedelta(days=self.cadence_days * skip)
        return dates

    def _compute_features(self, obs_df: pd.DataFrame) -> Dict[str, float]:
        """Compute the flat feature dict that aligns with
        ``FEATURE_COLUMNS`` in ``data_preparation.py``."""
        obs = obs_df.copy()
        obs["date"] = pd.to_datetime(obs["date"])
        obs = obs.sort_values("date")

        # Trend slope
        x = np.arange(len(obs))
        y = obs["ndvi"].values
        mask = ~np.isnan(y)
        if mask.sum() >= 2:
            coeffs = np.polyfit(x[mask], y[mask], 1)
            trend_slope = float(coeffs[0])
        else:
            trend_slope = 0.0

        # Seasonal amplitude
        obs["month"] = obs["date"].dt.month
        monthly_mean = obs.groupby("month")["ndvi"].mean()
        seasonal_amplitude = (
            float(monthly_mean.max() - monthly_mean.min()) if len(monthly_mean) > 0 else 0.0
        )

        return {
            "ndvi_mean": round(float(obs["ndvi"].mean()), 6),
            "ndvi_std": round(float(obs["ndvi"].std()), 6) if len(obs) > 1 else 0.0,
            "ndvi_min": round(float(obs["ndvi"].min()), 6),
            "ndvi_max": round(float(obs["ndvi"].max()), 6),
            "evi_mean": round(float(obs["evi"].mean()), 6),
            "evi_std": round(float(obs["evi"].std()), 6) if len(obs) > 1 else 0.0,
            "cloud_cover_mean": round(float(obs["cloud_cover"].mean()), 2),
            "observation_count": len(obs),
            "trend_slope": round(trend_slope, 8),
            "seasonal_amplitude": round(seasonal_amplitude, 6),
        }


# ──────────────────────────────────────────────────────────────
# Convenience function (backward-compatible with phase2 doc)
# ──────────────────────────────────────────────────────────────

def generate_synthetic_training_data(
    n_projects: int = 50,
    random_state: int = 42,
) -> list[dict[str, Any]]:
    """Shortcut: generate synthetic training data in one call.

    Returns the same list-of-dicts structure as
    ``SyntheticDataGenerator.generate``.
    """
    gen = SyntheticDataGenerator(random_state=random_state)
    return gen.generate(n_projects=n_projects)
