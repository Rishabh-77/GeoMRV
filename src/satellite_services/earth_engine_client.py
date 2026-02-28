"""
Earth Engine Client
===================
Core wrapper around the Google Earth Engine Python API.
Handles authentication, Sentinel-2 collection loading, and cloud masking.
"""

import logging
import os
from typing import Optional

import ee

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sentinel-2 cloud-masking helpers (uses the QA60 bitmask band)
# ---------------------------------------------------------------------------


def _mask_s2_clouds(image: ee.Image) -> ee.Image:
    """Mask clouds and cirrus in a Sentinel-2 SR image using the QA60 band."""
    qa = image.select("QA60")
    # Bits 10 and 11 are clouds and cirrus respectively
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    return image.updateMask(mask)


class EarthEngineClient:
    """
    Singleton-style wrapper for Google Earth Engine interactions.

    Usage::

        client = EarthEngineClient()          # auto-initialises GEE
        collection = client.get_sentinel2(
            geometry=ee.Geometry.Rectangle([73.5, 15.2, 74.2, 15.6]),
            start_date="2025-01-01",
            end_date="2025-03-01",
            max_cloud_pct=20,
        )
    """

    _initialised: bool = False

    def __init__(self, project: Optional[str] = None):
        """
        Initialise the Earth Engine API.

        Parameters
        ----------
        project : str, optional
            GEE cloud project ID.  Falls back to the env var
            ``GEE_PROJECT`` if not supplied.  If neither is set the
            default project from ``earthengine authenticate`` is used.
        """
        if not EarthEngineClient._initialised:
            self._init_ee(project)
            EarthEngineClient._initialised = True

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    @staticmethod
    def _init_ee(project: Optional[str] = None) -> None:
        project = project or os.getenv("GEE_PROJECT", "geomrv-earth-engine")
        try:
            ee.Initialize(project=project)
            logger.info("Google Earth Engine initialised (project=%s).", project)
        except Exception as exc:
            logger.error("GEE initialisation failed: %s", exc)
            raise

    # ------------------------------------------------------------------
    # Sentinel-2 helpers
    # ------------------------------------------------------------------

    @staticmethod
    def get_sentinel2(
        geometry: ee.Geometry,
        start_date: str,
        end_date: str,
        max_cloud_pct: float = 30,
        apply_cloud_mask: bool = True,
    ) -> ee.ImageCollection:
        """
        Load a cloud-filtered Sentinel-2 Surface Reflectance collection.

        Parameters
        ----------
        geometry : ee.Geometry
            Area of interest.
        start_date, end_date : str
            ISO-8601 date strings (``YYYY-MM-DD``).
        max_cloud_pct : float
            Maximum scene-level cloud cover percentage (0–100).
        apply_cloud_mask : bool
            If *True*, per-pixel cloud masking via QA60 is applied.

        Returns
        -------
        ee.ImageCollection
        """
        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(geometry)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud_pct))
        )

        if apply_cloud_mask:
            collection = collection.map(_mask_s2_clouds)

        count = collection.size().getInfo()
        logger.info(
            "Sentinel-2 collection loaded: %d images (%s → %s, ≤%d%% cloud)",
            count,
            start_date,
            end_date,
            max_cloud_pct,
        )
        return collection

    @staticmethod
    def geometry_from_geojson(geojson: dict) -> ee.Geometry:
        """
        Convert a GeoJSON Feature / FeatureCollection / Geometry dict into an
        ``ee.Geometry``.
        """
        geo_type = geojson.get("type", "")
        if geo_type == "FeatureCollection":
            return ee.FeatureCollection(geojson).geometry()
        if geo_type == "Feature":
            return ee.Geometry(geojson["geometry"])
        return ee.Geometry(geojson)

    @staticmethod
    def geometry_from_bbox(
        west: float, south: float, east: float, north: float
    ) -> ee.Geometry:
        """Create an ``ee.Geometry.Rectangle`` from a bounding box."""
        return ee.Geometry.Rectangle([west, south, east, north])

    # ------------------------------------------------------------------
    # Quick-test helper
    # ------------------------------------------------------------------

    def test_connection(self) -> dict:
        """
        Lightweight connectivity check.

        Returns
        -------
        dict  with keys ``status``, ``message``, and ``image_count``
            (using a tiny 1-month window over Goa, India).
        """
        try:
            test_geom = ee.Geometry.Rectangle([73.5, 15.2, 74.2, 15.6])
            col = self.get_sentinel2(
                geometry=test_geom,
                start_date="2025-01-01",
                end_date="2025-02-01",
                max_cloud_pct=30,
            )
            count = col.size().getInfo()
            return {
                "status": "ok",
                "message": f"Connected – {count} Sentinel-2 images found for Goa test region",
                "image_count": count,
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc), "image_count": 0}
