"""
GeoMRV FastAPI Application
==========================
Main entry point for the API.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.config import settings
from src.api.routers import evidence, features, jobs, ml_scoring, projects, verification

app = FastAPI(
    title="GeoMRV API",
    description="Geospatial MRV (Monitoring, Reporting, Verification) backend for carbon projects",
    version="0.1.0",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(projects.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(evidence.router, prefix="/api/v1")
app.include_router(features.router, prefix="/api/v1")
app.include_router(verification.router, prefix="/api/v1")
app.include_router(ml_scoring.router, prefix="/api/v1")


@app.get("/health")
def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "service": "geomrv-api"}


@app.get("/")
def root() -> dict:
    """Root endpoint."""
    return {
        "service": "GeoMRV API",
        "version": "0.1.0",
        "docs": "/docs",
    }
