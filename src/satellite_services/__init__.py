"""
GeoMRV Satellite Services
=========================
Modules for fetching, processing, and exporting satellite imagery
via Google Earth Engine (Sentinel-2).

Modules:
    earth_engine_client  – GEE authentication, collection loading, cloud masking
    ndvi_calculator      – NDVI / EVI time-series extraction
    timelapse_exporter   – RGB timelapse generation (MP4) + Azure Blob upload
"""

from .earth_engine_client import EarthEngineClient
from .ndvi_calculator import NDVICalculator
from .timelapse_exporter import TimelapseExporter

__all__ = ["EarthEngineClient", "NDVICalculator", "TimelapseExporter"]
