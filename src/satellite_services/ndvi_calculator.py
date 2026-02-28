"""
NDVI Calculator
===============
Extracts NDVI (and optionally EVI) time-series from Sentinel-2 imagery
via Google Earth Engine, with optional persistence to PostgreSQL.
"""

import logging
import os
from datetime import datetime
from typing import Optional

import ee
import pandas as pd

from .earth_engine_client import EarthEngineClient

logger = logging.getLogger(__name__)


class NDVICalculator:
    """
    Calculate NDVI / EVI statistics for a given area of interest over
    a date range using Sentinel-2 Surface Reflectance via GEE.

    Usage::

        calc = NDVICalculator()
        df = calc.compute_timeseries(
            geometry=ee.Geometry.Rectangle([73.5, 15.2, 74.2, 15.6]),
            start_date="2025-01-01",
            end_date="2025-06-01",
        )
        print(df.head())
    """

    def __init__(self, client: Optional[EarthEngineClient] = None):
        self.client = client or EarthEngineClient()

    # ------------------------------------------------------------------
    # Core computation
    # ------------------------------------------------------------------

    @staticmethod
    def _add_indices(image: ee.Image) -> ee.Image:
        """Add NDVI and EVI bands to a Sentinel-2 image."""
        # NDVI = (B8 – B4) / (B8 + B4)
        ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")

        # EVI = 2.5 * (B8 – B4) / (B8 + 6*B4 – 7.5*B2 + 1)
        evi = image.expression(
            "2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))",
            {
                "NIR": image.select("B8"),
                "RED": image.select("B4"),
                "BLUE": image.select("B2"),
            },
        ).rename("EVI")

        return image.addBands([ndvi, evi])

    def compute_timeseries(
        self,
        geometry: ee.Geometry,
        start_date: str,
        end_date: str,
        max_cloud_pct: float = 30,
        scale: int = 20,
    ) -> pd.DataFrame:
        """
        Fetch an NDVI / EVI time-series for *geometry* between the given dates.

        Parameters
        ----------
        geometry : ee.Geometry
            Area of interest polygon.
        start_date, end_date : str
            ISO-8601 date strings.
        max_cloud_pct : float
            Scene-level cloud threshold.
        scale : int
            Spatial resolution in metres (default 20 m for Sentinel-2 red-edge).

        Returns
        -------
        pd.DataFrame
            Columns: ``date``, ``ndvi_mean``, ``ndvi_std``, ``ndvi_count``,
            ``evi_mean``, ``cloud_cover_pct``, ``data_source``.
        """
        collection = self.client.get_sentinel2(
            geometry, start_date, end_date, max_cloud_pct
        )
        collection = collection.map(self._add_indices)

        n_images = collection.size().getInfo()
        if n_images == 0:
            logger.warning("No Sentinel-2 images found for the given filters.")
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

            # Reducers ---------------------------------------------------
            stats = (
                image.select(["NDVI", "EVI"])
                .reduceRegion(
                    reducer=ee.Reducer.mean()
                    .combine(ee.Reducer.stdDev(), sharedInputs=True)
                    .combine(ee.Reducer.count(), sharedInputs=True),
                    geometry=geometry,
                    scale=scale,
                    maxPixels=1e9,
                )
                .getInfo()
            )

            cloud_pct = image.get("CLOUDY_PIXEL_PERCENTAGE").getInfo()
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
                    "data_source": "Sentinel-2_SR_Harmonized",
                }
            )

        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df.sort_values("date", inplace=True)
        df.reset_index(drop=True, inplace=True)

        logger.info(
            "NDVI time-series computed: %d observations (%s → %s)",
            len(df),
            start_date,
            end_date,
        )
        return df

    # ------------------------------------------------------------------
    # PostgreSQL persistence
    # ------------------------------------------------------------------

    @staticmethod
    def store_to_postgres(
        df: pd.DataFrame,
        project_id: str,
        connection_string: Optional[str] = None,
    ) -> int:
        """
        Insert NDVI observations into the ``observations`` table.

        Parameters
        ----------
        df : pd.DataFrame
            Output of :pymeth:`compute_timeseries`.
        project_id : str
            UUID of the project row in the ``projects`` table.
        connection_string : str, optional
            SQLAlchemy-style DSN.  Falls back to env vars if omitted.

        Returns
        -------
        int   Number of rows inserted.
        """
        from sqlalchemy import create_engine, text

        if connection_string is None:
            host = os.getenv("POSTGRES_HOST")
            port = os.getenv("POSTGRES_PORT", "5432")
            db = os.getenv("POSTGRES_DB")
            user = os.getenv("POSTGRES_USER")
            pwd = os.getenv("POSTGRES_PASSWORD")
            sslmode = os.getenv("POSTGRES_SSLMODE", "require")
            connection_string = (
                f"postgresql://{user}:{pwd}@{host}:{port}/{db}" f"?sslmode={sslmode}"
            )

        engine = create_engine(connection_string)

        insert_sql = text("""
            INSERT INTO observations
                (project_id, observation_date, ndvi, ndvi_std, ndvi_count,
                 evi, data_source, cloud_cover_percent)
            VALUES
                (:project_id, :obs_date, :ndvi, :ndvi_std, :ndvi_count,
                 :evi, :data_source, :cloud_cover)
            ON CONFLICT DO NOTHING
            """)

        inserted = 0
        with engine.begin() as conn:
            for _, row in df.iterrows():
                conn.execute(
                    insert_sql,
                    {
                        "project_id": project_id,
                        "obs_date": row["date"],
                        "ndvi": row.get("ndvi_mean"),
                        "ndvi_std": row.get("ndvi_std"),
                        "ndvi_count": row.get("ndvi_count"),
                        "evi": row.get("evi_mean"),
                        "data_source": row.get("data_source"),
                        "cloud_cover": row.get("cloud_cover_pct"),
                    },
                )
                inserted += 1

        logger.info(
            "Inserted %d rows into 'observations' for project %s", inserted, project_id
        )
        return inserted
