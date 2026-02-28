"""
Tests for Job Endpoints & JobService (Task 1.3)
================================================
Uses FastAPI TestClient to exercise job CRUD, background processing
(with mocked satellite fetcher), and observation retrieval endpoints.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)

# ────────────────────────────────────────────────────────────
# Fixtures / Helpers
# ────────────────────────────────────────────────────────────

SAMPLE_PROJECT = {
    "name": "Satellite Test Project",
    "description": "Project for job testing",
    "location_name": "Goa",
    "country": "India",
    "region": "Western Ghats",
    "total_area_ha": 100.0,
    "project_type": "forest",
    "start_date": "2025-01-01",
}

SAMPLE_GEOJSON_FEATURE = {
    "type": "Feature",
    "geometry": {
        "type": "Polygon",
        "coordinates": [
            [
                [73.8, 15.35],
                [73.95, 15.35],
                [73.95, 15.45],
                [73.8, 15.45],
                [73.8, 15.35],
            ]
        ],
    },
    "properties": {},
}

MOCK_TIMESERIES = pd.DataFrame(
    {
        "date": pd.to_datetime(["2025-01-15", "2025-02-14"]),
        "ndvi_mean": [0.45, 0.52],
        "ndvi_std": [0.05, 0.04],
        "ndvi_count": [1200, 1350],
        "evi_mean": [0.32, 0.38],
        "cloud_cover_pct": [12.0, 8.0],
        "data_source": [
            "Sentinel-2_SR_Harmonized",
            "Sentinel-2_SR_Harmonized",
        ],
    }
)


def _create_project(**overrides) -> dict:
    """Helper: POST a project and return its JSON."""
    payload = {**SAMPLE_PROJECT, **overrides}
    resp = client.post("/api/v1/projects", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _upload_boundary(project_id: str) -> dict:
    """Helper: upload a GeoJSON boundary for a project."""
    content = json.dumps(SAMPLE_GEOJSON_FEATURE).encode()
    resp = client.post(
        f"/api/v1/projects/{project_id}/upload-boundary",
        files={"file": ("test.geojson", content, "application/json")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ────────────────────────────────────────────────────────────
# Tests — Job CRUD
# ────────────────────────────────────────────────────────────


class TestCreateJob:
    """POST /api/v1/jobs"""

    def test_create_job_returns_201(self):
        project = _create_project(name="Job Create Test")
        resp = client.post(
            "/api/v1/jobs",
            json={
                "project_id": project["id"],
                "start_date": "2025-01-01",
                "end_date": "2025-06-01",
                "job_type": "monitoring",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["project_id"] == project["id"]
        assert data["status"] == "pending"
        assert data["operation_type"] == "monitoring"

    def test_create_job_default_type(self):
        project = _create_project(name="Job Default Type")
        resp = client.post(
            "/api/v1/jobs",
            json={
                "project_id": project["id"],
                "start_date": "2025-01-01",
                "end_date": "2025-03-01",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["operation_type"] == "monitoring"


class TestGetJob:
    """GET /api/v1/jobs/{job_id}"""

    def test_get_existing_job(self):
        project = _create_project(name="Job Get Test")
        create_resp = client.post(
            "/api/v1/jobs",
            json={
                "project_id": project["id"],
                "start_date": "2025-01-01",
                "end_date": "2025-06-01",
            },
        )
        job_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/jobs/{job_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == job_id

    def test_get_nonexistent_job_returns_404(self):
        resp = client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000099")
        assert resp.status_code == 404


class TestListJobs:
    """GET /api/v1/jobs"""

    def test_list_jobs(self):
        project = _create_project(name="Job List Test")
        client.post(
            "/api/v1/jobs",
            json={
                "project_id": project["id"],
                "start_date": "2025-01-01",
                "end_date": "2025-03-01",
            },
        )

        resp = client.get("/api/v1/jobs")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1

    def test_list_jobs_filter_by_project(self):
        p1 = _create_project(name="Job Filter P1")
        p2 = _create_project(name="Job Filter P2")

        client.post(
            "/api/v1/jobs",
            json={
                "project_id": p1["id"],
                "start_date": "2025-01-01",
                "end_date": "2025-03-01",
            },
        )
        client.post(
            "/api/v1/jobs",
            json={
                "project_id": p2["id"],
                "start_date": "2025-01-01",
                "end_date": "2025-03-01",
            },
        )

        resp = client.get(f"/api/v1/jobs?project_id={p1['id']}")
        assert resp.status_code == 200
        ids = {j["project_id"] for j in resp.json()}
        assert ids == {p1["id"]}


# ────────────────────────────────────────────────────────────
# Tests — Background Job Processing (mocked satellite fetch)
# ────────────────────────────────────────────────────────────


class TestJobProcessing:
    """Verify the JobService.process_job logic with mocked data fetcher."""

    @patch(
        "src.api.services.job_service.SatelliteDataFetcher",
    )
    def test_process_job_stores_observations(self, mock_fetcher_cls):
        """After processing, observations should be queryable."""
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch_sentinel2_data.return_value = MOCK_TIMESERIES.copy()

        # Create project + boundary
        project = _create_project(name="Process Job Test")
        _upload_boundary(project["id"])

        # Create job
        create_resp = client.post(
            "/api/v1/jobs",
            json={
                "project_id": project["id"],
                "start_date": "2025-01-01",
                "end_date": "2025-06-01",
            },
        )
        job_id = create_resp.json()["id"]

        # Manually run process_job (background tasks don't auto-run in TestClient)
        from src.api.database import SessionLocal
        from src.api.services.job_service import JobService

        db = SessionLocal()
        try:
            svc = JobService(db)
            svc.process_job(job_id)
        finally:
            db.close()

        # Verify job is completed
        resp = client.get(f"/api/v1/jobs/{job_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

        # Verify observations exist
        obs_resp = client.get(f"/api/v1/jobs/projects/{project['id']}/observations")
        assert obs_resp.status_code == 200
        observations = obs_resp.json()
        assert len(observations) == 2
        assert observations[0]["ndvi"] == 0.45
        assert observations[1]["ndvi"] == 0.52

    @patch(
        "src.api.services.job_service.SatelliteDataFetcher",
    )
    def test_process_job_fails_without_boundary(self, mock_fetcher_cls):
        """Job should fail if project has no boundary uploaded."""
        project = _create_project(name="No Boundary Job")

        create_resp = client.post(
            "/api/v1/jobs",
            json={
                "project_id": project["id"],
                "start_date": "2025-01-01",
                "end_date": "2025-06-01",
            },
        )
        job_id = create_resp.json()["id"]

        from src.api.database import SessionLocal
        from src.api.services.job_service import JobService

        db = SessionLocal()
        try:
            svc = JobService(db)
            svc.process_job(job_id)
        finally:
            db.close()

        resp = client.get(f"/api/v1/jobs/{job_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"
        assert "No boundary found" in resp.json()["error_message"]

    @patch(
        "src.api.services.job_service.SatelliteDataFetcher",
    )
    def test_process_job_handles_fetcher_exception(self, mock_fetcher_cls):
        """Job should be marked 'failed' when the fetcher raises."""
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch_sentinel2_data.side_effect = RuntimeError("GEE timeout")

        project = _create_project(name="Fetcher Error Job")
        _upload_boundary(project["id"])

        create_resp = client.post(
            "/api/v1/jobs",
            json={
                "project_id": project["id"],
                "start_date": "2025-01-01",
                "end_date": "2025-06-01",
            },
        )
        job_id = create_resp.json()["id"]

        from src.api.database import SessionLocal
        from src.api.services.job_service import JobService

        db = SessionLocal()
        try:
            svc = JobService(db)
            svc.process_job(job_id)
        finally:
            db.close()

        resp = client.get(f"/api/v1/jobs/{job_id}")
        assert resp.json()["status"] == "failed"
        assert "GEE timeout" in resp.json()["error_message"]


# ────────────────────────────────────────────────────────────
# Tests — Observations endpoint
# ────────────────────────────────────────────────────────────


class TestObservations:
    """GET /api/v1/jobs/projects/{project_id}/observations"""

    def test_empty_observations_for_new_project(self):
        project = _create_project(name="No Obs Project")
        resp = client.get(f"/api/v1/jobs/projects/{project['id']}/observations")
        assert resp.status_code == 200
        assert resp.json() == []

    @patch(
        "src.api.services.job_service.SatelliteDataFetcher",
    )
    def test_observations_date_filter(self, mock_fetcher_cls):
        """Observations should be filterable by start_date / end_date."""
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch_sentinel2_data.return_value = MOCK_TIMESERIES.copy()

        project = _create_project(name="Date Filter Obs")
        _upload_boundary(project["id"])

        create_resp = client.post(
            "/api/v1/jobs",
            json={
                "project_id": project["id"],
                "start_date": "2025-01-01",
                "end_date": "2025-06-01",
            },
        )
        job_id = create_resp.json()["id"]

        from src.api.database import SessionLocal
        from src.api.services.job_service import JobService

        db = SessionLocal()
        try:
            svc = JobService(db)
            svc.process_job(job_id)
        finally:
            db.close()

        # Filter to only January
        resp = client.get(
            f"/api/v1/jobs/projects/{project['id']}/observations"
            "?start_date=2025-01-01&end_date=2025-01-31"
        )
        assert resp.status_code == 200
        obs = resp.json()
        assert len(obs) == 1
        assert obs[0]["observation_date"] == "2025-01-15"


class TestProcessingLogs:
    """Verify that processing creates logs in the DB."""

    @patch(
        "src.api.services.job_service.SatelliteDataFetcher",
    )
    def test_processing_creates_log_entry(self, mock_fetcher_cls):
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch_sentinel2_data.return_value = MOCK_TIMESERIES.copy()

        project = _create_project(name="Log Entry Test")
        _upload_boundary(project["id"])

        create_resp = client.post(
            "/api/v1/jobs",
            json={
                "project_id": project["id"],
                "start_date": "2025-01-01",
                "end_date": "2025-06-01",
            },
        )
        job_id = create_resp.json()["id"]

        from src.api.database import SessionLocal
        from src.api.services.job_service import JobService

        db = SessionLocal()
        try:
            svc = JobService(db)
            svc.process_job(job_id)
        finally:
            db.close()

        # The processing log is stored as a Job row with operation_type=satellite_fetch
        resp = client.get(f"/api/v1/jobs?project_id={project['id']}")
        assert resp.status_code == 200
        jobs = resp.json()
        op_types = [j["operation_type"] for j in jobs]
        assert "satellite_fetch" in op_types
