# Satellite Services Module

This package provides all remote-sensing functionality for GeoMRV.
It wraps the **Google Earth Engine (GEE)** Python API and works with
**Sentinel-2 Surface Reflectance** imagery.

---

## Modules

| Module | Purpose |
|--------|---------|
| `earth_engine_client.py` | GEE authentication, Sentinel-2 collection loading, cloud masking (QA60) |
| `ndvi_calculator.py` | NDVI / EVI time-series extraction + PostgreSQL persistence |
| `timelapse_exporter.py` | RGB timelapse MP4 generation + Azure Blob upload |

---

## Prerequisites

```bash
pip install earthengine-api pandas requests imageio imageio-ffmpeg
pip install azure-storage-blob        # for blob upload
pip install sqlalchemy psycopg2-binary # for DB persistence
```

You must have authenticated with GEE at least once:

```bash
earthengine authenticate
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GEE_PROJECT` | *(optional)* GEE cloud project ID |
| `POSTGRES_HOST` | Azure PostgreSQL host |
| `POSTGRES_PORT` | PostgreSQL port (default `5432`) |
| `POSTGRES_DB` | Database name (e.g. `geomrv_dev`) |
| `POSTGRES_USER` | Database user |
| `POSTGRES_PASSWORD` | Database password |
| `POSTGRES_SSLMODE` | SSL mode (default `require`) |
| `AZURE_STORAGE_CONNECTION_STRING` | Azure Storage connection string |
| `AZURE_STORAGE_CONTAINER_CACHE` | Blob container for timelapse files (default `satellite-data-cache`) |

---

## Quick Start

```python
from src.satellite_services import EarthEngineClient, NDVICalculator, TimelapseExporter
import ee

# 1. Initialise client (authenticates GEE)
client = EarthEngineClient()

# 2. Test connection
print(client.test_connection())

# 3. NDVI time-series
calc = NDVICalculator(client)
geometry = ee.Geometry.Rectangle([73.5, 15.2, 74.2, 15.6])  # Goa, India
df = calc.compute_timeseries(geometry, "2025-01-01", "2025-06-01")
print(df)

# 4. Store to PostgreSQL
# calc.store_to_postgres(df, project_id="<uuid>")

# 5. Generate timelapse
exporter = TimelapseExporter(client)
mp4 = exporter.generate(geometry, "2024-01-01", "2025-01-01", interval_days=30)
print(f"Timelapse saved to {mp4}")

# 6. Upload to Azure Blob
# url = exporter.upload_to_blob(mp4, "timelapse/goa/2024.mp4")
```

---

## GEE Quota Notes

| Resource | Free-tier Limit |
|----------|----------------|
| Earth Engine compute | ~40 M pixels/month |
| Concurrent requests | ~10 |
| Thumbnail downloads | Fair-use, no hard cap |

**Recommendation:** Start with small pilot areas (< 10 km²) and 1-month
windows. Scale up only after verifying quota usage in the
[GEE Asset Manager](https://code.earthengine.google.com/assets).

---

## File Structure

```
src/satellite_services/
├── __init__.py
├── earth_engine_client.py
├── ndvi_calculator.py
├── timelapse_exporter.py
└── README.md                ← you are here
```
