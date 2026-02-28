# India Data Sources (Satellite)

## Primary source (recommended)

### Google Earth Engine (GEE)

- Collections commonly used:
  - Sentinel-2: `COPERNICUS/S2` (or harmonized where applicable)
  - Landsat: `LANDSAT/*` collections depending on use case
- Pros:
  - Easy spatial/temporal filtering
  - Scales for prototyping and MVP
  - Good coverage for Indian regions

## Alternative sources

### USGS EarthExplorer
- Pros: direct downloads, official source
- Cons: manual workflow, local processing burden

### Copernicus Open Access Hub
- Pros: direct ESA Sentinel access
- Cons: account management + download logistics

## India-specific considerations

- Monsoon season can create persistent cloud cover; plan for:
  - stronger cloud masking
  - longer temporal windows (composites)
  - fallback data sources (e.g., Landsat)
- Different agro-climatic zones can affect NDVI baselines; document calibration assumptions per region.

## Quota / cost notes

- GEE workloads consume Earth Engine quota/limits (compute/pixels), not Azure credits.
- CI should avoid running heavy GEE computations on every PR.
