# Architecture Diagram (Draft)

This diagram represents the end-to-end data flow for GeoMRV.

```mermaid
flowchart LR
  A[Project Boundary (GeoJSON/Polygon)] --> B[Satellite Fetch (GEE Sentinel-2)]
  B --> C[Cloud Masking + Compositing]
  C --> D[Feature Extraction (NDVI/EVI/Biomass)]
  D --> E[(PostgreSQL + PostGIS)]
  D --> F[Cache Previews (Azure Blob)]
  E --> G[Evidence Packaging]
  F --> G
  G --> H[Evidence Package Artifacts (Azure Blob)]
  E --> I[API (FastAPI)]
  I --> J[Frontend]
```

## Notes

- Phase 0 validated GEE connectivity and basic satellite utilities.
- Phase 1 focuses on API + DB models and persistence.
