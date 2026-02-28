"""
GeoMRV Feature Calculator
=========================
Calculate standardised time-series features (trend, seasonality, anomalies,
growth period, biomass proxy) from satellite observations stored in the DB.

Usage
-----
    from src.feature_extraction.feature_calculator import (
        FeatureCalculator,
        PipelineFeatureExtractor,
    )

    # Standalone (DataFrame already in hand)
    trend = FeatureCalculator.calculate_trend(df)

    # Full pipeline (reads observations from DB)
    extractor = PipelineFeatureExtractor(db_session)
    features  = extractor.extract_features(project_id, start_date, end_date)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Low-level calculators (all static – no DB dependency)
# ──────────────────────────────────────────────────────────────


class FeatureCalculator:
    """Calculate standardised features from a DataFrame of observations."""

    # ── Trend ─────────────────────────────────────────────────

    @staticmethod
    def calculate_trend(df: pd.DataFrame, window: int = 3) -> dict[str, Any]:
        """Linear trend over the smoothed NDVI time-series.

        Parameters
        ----------
        df : DataFrame
            Must contain ``date`` (datetime-like) and ``ndvi`` (float) columns.
        window : int
            Rolling-mean window (number of observations) for smoothing.

        Returns
        -------
        dict with ``trend_slope``, ``slope_per_year``, ``r_squared``.
        """
        df = df.sort_values("date").copy()
        df["ndvi_smooth"] = df["ndvi"].rolling(window=window, center=True).mean()

        y = df["ndvi_smooth"].values
        mask = ~np.isnan(y)
        x = np.arange(len(y))[mask]
        y = y[mask]

        if len(x) < 2:
            return {"trend_slope": None, "slope_per_year": None, "r_squared": 0.0}

        coeffs = np.polyfit(x, y, 1)
        slope = float(coeffs[0])

        y_pred = np.polyval(coeffs, x)
        ss_res = float(np.sum((y - y_pred) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot != 0 else 0.0

        # Annualise: assume ~12 observations/year for Sentinel-2 monthly composites
        # Adjust if your cadence differs.
        obs_per_year = max(len(df) / max((df["date"].max() - df["date"].min()).days / 365.25, 0.01), 1)
        slope_per_year = slope * obs_per_year

        return {
            "trend_slope": round(slope, 8),
            "slope_per_year": round(slope_per_year, 6),
            "r_squared": round(r_squared, 6),
        }

    # ── Seasonality ───────────────────────────────────────────

    @staticmethod
    def calculate_seasonality(df: pd.DataFrame) -> dict[str, Any]:
        """Monthly seasonal pattern: peak / trough months and amplitude.

        Parameters
        ----------
        df : DataFrame
            Must contain ``date`` (datetime-like) and ``ndvi`` (float) columns.
        """
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        df["month"] = df["date"].dt.month

        seasonal = df.groupby("month")["ndvi"].agg(["mean", "std"]).fillna(0)

        peak_month = int(seasonal["mean"].idxmax())
        trough_month = int(seasonal["mean"].idxmin())

        return {
            "peak_month": peak_month,
            "trough_month": trough_month,
            "peak_ndvi": round(float(seasonal.loc[peak_month, "mean"]), 6),
            "trough_ndvi": round(float(seasonal.loc[trough_month, "mean"]), 6),
            "seasonal_amplitude": round(
                float(seasonal["mean"].max() - seasonal["mean"].min()), 6
            ),
        }

    # ── Anomalies ─────────────────────────────────────────────

    @staticmethod
    def calculate_anomalies(
        df: pd.DataFrame,
        std_threshold: float = 2.0,
        rolling_window: int = 10,
    ) -> list[str]:
        """Detect dates where NDVI deviates > *std_threshold* σ from the rolling mean.

        Parameters
        ----------
        df : DataFrame
            Must contain ``date`` (datetime-like) and ``ndvi`` (float) columns.
        std_threshold : float
            Number of standard deviations to flag as anomaly.
        rolling_window : int
            Window size for the rolling statistics.

        Returns
        -------
        List of ISO-format date strings.
        """
        df = df.sort_values("date").copy()

        # Use a smaller effective window when there are fewer observations
        effective_window = min(rolling_window, max(len(df) // 2, 2))

        ndvi_mean = df["ndvi"].rolling(window=effective_window, center=True).mean()
        ndvi_std = df["ndvi"].rolling(window=effective_window, center=True).std()

        # Avoid flagging when std is essentially zero (flat signal)
        ndvi_std = ndvi_std.replace(0, np.nan)

        anomalies = np.abs(df["ndvi"] - ndvi_mean) > (std_threshold * ndvi_std)
        anomalies = anomalies.fillna(False)

        return [str(d.date()) if hasattr(d, "date") else str(d) for d in df.loc[anomalies, "date"]]

    # ── Growth Period ─────────────────────────────────────────

    @staticmethod
    def calculate_growth_period(df: pd.DataFrame) -> dict[str, Any]:
        """Identify the growing season (consecutive period above mean NDVI).

        Parameters
        ----------
        df : DataFrame
            Must contain ``date`` (datetime-like) and ``ndvi`` (float) columns.
        """
        df = df.sort_values("date").copy()
        df["date"] = pd.to_datetime(df["date"])

        ndvi_threshold = float(df["ndvi"].mean())
        growing = df[df["ndvi"] > ndvi_threshold]

        if growing.empty:
            return {
                "growth_start": None,
                "growth_end": None,
                "growth_days": 0,
                "ndvi_threshold": round(ndvi_threshold, 6),
            }

        growth_start = growing["date"].min()
        growth_end = growing["date"].max()
        growth_days = (growth_end - growth_start).days

        return {
            "growth_start": str(growth_start.date()),
            "growth_end": str(growth_end.date()),
            "growth_days": int(growth_days),
            "ndvi_threshold": round(ndvi_threshold, 6),
        }

    # ── Biomass Proxy ─────────────────────────────────────────

    @staticmethod
    def calculate_biomass_proxy(ndvi: float, evi: float | None = None) -> float:
        """Simple linear biomass proxy (tonnes / ha).

        The coefficients are *placeholders* – they should be calibrated
        against India-region ground-truth data in Phase 2.

        Formula:  ``biomass = a × NDVI + b × EVI + c``
        """
        a = 50.0   # NDVI weight
        b = 30.0   # EVI weight
        c = 5.0    # intercept

        evi_value = evi if evi is not None else 0.0
        biomass = a * ndvi + b * evi_value + c
        return round(max(0.0, biomass), 4)

    # ── NDVI Statistics ───────────────────────────────────────

    @staticmethod
    def calculate_ndvi_stats(df: pd.DataFrame) -> dict[str, float]:
        """Basic descriptive statistics for the NDVI series."""
        return {
            "mean": round(float(df["ndvi"].mean()), 6),
            "std": round(float(df["ndvi"].std()), 6),
            "min": round(float(df["ndvi"].min()), 6),
            "max": round(float(df["ndvi"].max()), 6),
            "median": round(float(df["ndvi"].median()), 6),
            "count": int(df["ndvi"].count()),
        }


# ──────────────────────────────────────────────────────────────
# High-level pipeline extractor (reads from DB)
# ──────────────────────────────────────────────────────────────


class PipelineFeatureExtractor:
    """Orchestrate feature extraction for a project over a date range.

    Reads observations from the database, filters by cloud cover, runs
    all calculators, and returns a single feature dictionary.
    """

    MAX_CLOUD_COVER: float = 30.0  # percent – discard cloudier scenes

    def __init__(self, db: Session):
        self.db = db
        self.calculator = FeatureCalculator()

    # ------------------------------------------------------------------

    def extract_features(
        self,
        project_id: str,
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        """Run the full extraction pipeline.

        Parameters
        ----------
        project_id : str
            UUID of the project.
        start_date, end_date : str
            ISO-format dates (``YYYY-MM-DD``).

        Returns
        -------
        dict  – all computed features, ready for storage or API response.
        """
        from src.api.models import Observation

        # --- query observations ---
        stmt = (
            select(Observation)
            .where(Observation.project_id == uuid.UUID(project_id))
            .where(Observation.observation_date >= start_date)
            .where(Observation.observation_date <= end_date)
            .order_by(Observation.observation_date)
        )
        obs_rows = self.db.execute(stmt).scalars().all()

        if not obs_rows:
            logger.warning("No observations found for project %s", project_id)
            return {"project_id": project_id, "error": "no_observations"}

        # --- build DataFrame ---
        records = []
        for o in obs_rows:
            records.append(
                {
                    "date": o.observation_date,
                    "ndvi": o.ndvi,
                    "evi": o.evi,
                    "cloud_cover": o.cloud_cover_percent,
                }
            )
        df = pd.DataFrame(records)

        total_obs = len(df)

        # --- cloud filter ---
        df = df[df["cloud_cover"].fillna(100) < self.MAX_CLOUD_COVER].copy()

        if len(df) < 3:
            logger.warning(
                "Only %d clear observations for project %s (need ≥ 3)",
                len(df),
                project_id,
            )
            return {
                "project_id": project_id,
                "error": "insufficient_clear_observations",
                "total_obs": total_obs,
                "clear_obs": len(df),
            }

        # --- calculate features ---
        features: dict[str, Any] = {
            "project_id": project_id,
            "period_start": start_date,
            "period_end": end_date,
            "total_observations": total_obs,
            "clear_observations": len(df),
            "cloud_cover_threshold": self.MAX_CLOUD_COVER,
            "extracted_at": datetime.utcnow().isoformat(),
            "trend": self.calculator.calculate_trend(df),
            "seasonality": self.calculator.calculate_seasonality(df),
            "growth_period": self.calculator.calculate_growth_period(df),
            "anomalies": self.calculator.calculate_anomalies(df),
            "ndvi_stats": self.calculator.calculate_ndvi_stats(df),
        }

        # --- biomass proxy (requires EVI) ---
        has_evi = df["evi"].notna().any()
        if has_evi:
            df["biomass"] = df.apply(
                lambda row: self.calculator.calculate_biomass_proxy(
                    row["ndvi"], row["evi"]
                ),
                axis=1,
            )
            features["biomass_stats"] = {
                "mean": round(float(df["biomass"].mean()), 4),
                "std": round(float(df["biomass"].std()), 4),
                "min": round(float(df["biomass"].min()), 4),
                "max": round(float(df["biomass"].max()), 4),
            }
        else:
            # EVI not available – estimate from NDVI alone
            df["biomass"] = df["ndvi"].apply(
                lambda n: self.calculator.calculate_biomass_proxy(n)
            )
            features["biomass_stats"] = {
                "mean": round(float(df["biomass"].mean()), 4),
                "std": round(float(df["biomass"].std()), 4),
                "min": round(float(df["biomass"].min()), 4),
                "max": round(float(df["biomass"].max()), 4),
                "note": "EVI unavailable – biomass estimated from NDVI only",
            }

        return features
