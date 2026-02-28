"""
Satellite Data Fetcher
======================
High-level orchestrator that fetches Sentinel-2 (and optionally Landsat)
NDVI / EVI time-series for a given GeoJSON boundary.

This module builds on top of the Phase 0 ``EarthEngineClient`` and
``NDVICalculator`` but exposes a simpler interface geared toward the
``JobService`` in Phase 1.
"""

from __future__ import annotations

import logging
from typing import Optional

import ee
import pandas as pd

from .earth_engine_client import EarthEngineClient
from .ndvi_calculator import NDVICalculator

logger = logging.getLogger(__name__)


class SatelliteDataFetcher:
    """
    Fetch satellite vegetation indices for a project boundary.

    Usage::

        fetcher = SatelliteDataFetcher()
        df = fetcher.fetch_sentinel2_data(
            boundary_geojson={"type": "Polygon", "coordinates": [...]},
            start_date="2025-01-01",
            end_date="2025-06-01",
        )
    """

    def __init__(self, project: Optional[str] = None):
        """
        Initialise the fetcher (also initialises Earth Engine).

        Parameters
        ----------
        project : str, optional
            GEE cloud-project ID.  Passed through to ``EarthEngineClient``.
        """
        self.client = EarthEngineClient(project=project)
        self.calculator = NDVICalculator(client=self.client)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_sentinel2_data(
        self,
        boundary_geojson: dict,
        start_date: str,
        end_date: str,
        max_cloud_cover: float = 30,
        scale: int = 20,
    ) -> pd.DataFrame:
        """
        Fetch Sentinel-2 NDVI / EVI time-series for the given boundary.

        Parameters
        ----------
        boundary_geojson : dict
            GeoJSON Geometry, Feature, or FeatureCollection describing the
            project area of interest.
        start_date, end_date : str
            ISO-8601 date strings (``YYYY-MM-DD``).
        max_cloud_cover : float
            Maximum scene-level cloud-cover percentage (0–100).
        scale : int
            Spatial resolution in metres (default 20 m).

        Returns
        -------
        pd.DataFrame
            Columns: ``date``, ``ndvi_mean``, ``ndvi_std``, ``ndvi_count``,
            ``evi_mean``, ``cloud_cover_pct``, ``data_source``.
        """
        ee_geom = EarthEngineClient.geometry_from_geojson(boundary_geojson)

        df = self.calculator.compute_timeseries(
            geometry=ee_geom,
            start_date=start_date,
            end_date=end_date,
            max_cloud_pct=max_cloud_cover,
            scale=scale,
        )

        logger.info(
            "Sentinel-2 fetch complete: %d observations (%s → %s)",
            len(df),
            start_date,
            end_date,
        )
        return df

    def fetch_landsat_data(
        self,
        boundary_geojson: dict,
        start_date: str,
        end_date: str,
        max_cloud_cover: float = 30,
        scale: int = 30,
    ) -> pd.DataFrame:
        """
        Fetch Landsat 8/9 NDVI / EVI time-series as a fallback source.

        Uses Landsat Collection 2, Level-2 Surface Reflectance.
        Band mapping: B5 = NIR, B4 = RED, B2 = BLUE.

        Parameters
        ----------
        boundary_geojson : dict
            GeoJSON geometry for the area of interest.
        start_date, end_date : str
            ISO-8601 date strings.
        max_cloud_cover : float
            Max scene cloud-cover percentage.
        scale : int
            Spatial resolution (default 30 m for Landsat).

        Returns
        -------
        pd.DataFrame
            Same column schema as ``fetch_sentinel2_data``.
        """
        ee_geom = EarthEngineClient.geometry_from_geojson(boundary_geojson)

        collection = (
            ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
            .merge(ee.ImageCollection("LANDSAT/LC09/C02/T1_L2"))
            .filterBounds(ee_geom)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lt("CLOUD_COVER", max_cloud_cover))
        )

        def _add_indices(image: ee.Image) -> ee.Image:
            # Scale factors for Landsat C2 L2
            sr = image.select(["SR_B2", "SR_B4", "SR_B5"]).multiply(0.0000275).add(-0.2)
            nir = sr.select("SR_B5")
            red = sr.select("SR_B4")
            blue = sr.select("SR_B2")

            ndvi = nir.subtract(red).divide(nir.add(red)).rename("NDVI")
            evi = (
                nir.subtract(red)
                .multiply(2.5)
                .divide(nir.add(red.multiply(6)).subtract(blue.multiply(7.5)).add(1))
                .rename("EVI")
            )
            return image.addBands([ndvi, evi])

        collection = collection.map(_add_indices)
        n_images = collection.size().getInfo()

        if n_images == 0:
            logger.warning("No Landsat images found for the given filters.")
            return pd.DataFrame(
                columns=[
                    "date",
                    "ndvi_mean",
                    "ndvi_std",
                    "ndvi_count",
                    "evi_mean",
                    "cloud_cover_pct",
                    "data_source",
                ]
            )

        image_list = collection.toList(n_images)
        rows = []

        for idx in range(n_images):
            image = ee.Image(image_list.get(idx))
            stats = (
                image.select(["NDVI", "EVI"])
                .reduceRegion(
                    reducer=ee.Reducer.mean()
                    .combine(ee.Reducer.stdDev(), sharedInputs=True)
                    .combine(ee.Reducer.count(), sharedInputs=True),
                    geometry=ee_geom,
                    scale=scale,
                    maxPixels=1e9,
                )
                .getInfo()
            )
            cloud_pct = image.get("CLOUD_COVER").getInfo()
            obs_date = (
                ee.Date(image.get("system:time_start")).format("YYYY-MM-dd").getInfo()
            )
            rows.append(
                {
                    "date": obs_date,
                    "ndvi_mean": stats.get("NDVI_mean"),
                    "ndvi_std": stats.get("NDVI_stdDev"),
                    "ndvi_count": stats.get("NDVI_count"),
                    "evi_mean": stats.get("EVI_mean"),
                    "cloud_cover_pct": cloud_pct,
                    "data_source": "Landsat-8/9_C2_L2",
                }
            )

        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df.sort_values("date", inplace=True)
        df.reset_index(drop=True, inplace=True)

        logger.info(
            "Landsat fetch complete: %d observations (%s → %s)",
            len(df),
            start_date,
            end_date,
        )
        return df

    def fetch_data(
        self,
        boundary_geojson: dict,
        start_date: str,
        end_date: str,
        max_cloud_cover: float = 30,
        source: str = "sentinel2",
    ) -> pd.DataFrame:
        """
        Unified entry point — choose source via *source* parameter.

        Parameters
        ----------
        source : str
            ``"sentinel2"`` (default) or ``"landsat"``.

        Returns
        -------
        pd.DataFrame
        """
        if source == "landsat":
            return self.fetch_landsat_data(
                boundary_geojson, start_date, end_date, max_cloud_cover
            )
        return self.fetch_sentinel2_data(
            boundary_geojson, start_date, end_date, max_cloud_cover
        )

    # ------------------------------------------------------------------
    # Connectivity check
    # ------------------------------------------------------------------

    def test_connection(self) -> dict:
        """Delegate to EarthEngineClient.test_connection."""
        return self.client.test_connection()
