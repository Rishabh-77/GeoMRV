"""
Tests for Project Management Endpoints (Task 1.2)
==================================================
Uses FastAPI TestClient to exercise CRUD + boundary upload.
"""

import json
import io

import pytest
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)

# ────────────────────────────────────────────────────────────
# Fixtures / Helpers
# ────────────────────────────────────────────────────────────

SAMPLE_PROJECT = {
    "name": "Test Afforestation",
    "description": "A sample reforestation project in Goa",
    "location_name": "Goa",
    "country": "India",
    "region": "Western Ghats",
    "total_area_ha": 120.5,
    "project_type": "forest",
    "start_date": "2025-06-01",
}

SAMPLE_GEOJSON = {
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


def _create_project(**overrides) -> dict:
    """Helper: POST a project and return the JSON response body."""
    payload = {**SAMPLE_PROJECT, **overrides}
    resp = client.post("/api/v1/projects", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ────────────────────────────────────────────────────────────
# Tests — Project CRUD
# ────────────────────────────────────────────────────────────


class TestCreateProject:
    def test_create_minimal(self):
        resp = client.post("/api/v1/projects", json={"name": "Minimal"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Minimal"
        assert data["id"]  # UUID assigned

    def test_create_full(self):
        data = _create_project()
        assert data["name"] == SAMPLE_PROJECT["name"]
        assert data["country"] == "India"
        assert data["project_type"] == "forest"


class TestListProjects:
    def test_list_returns_array(self):
        resp = client.get("/api/v1/projects")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_with_pagination(self):
        resp = client.get("/api/v1/projects?skip=0&limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) <= 2


class TestGetProject:
    def test_get_existing(self):
        created = _create_project(name="GetMe")
        resp = client.get(f"/api/v1/projects/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "GetMe"

    def test_get_not_found(self):
        resp = client.get("/api/v1/projects/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


class TestUpdateProject:
    def test_update_partial(self):
        created = _create_project(name="BeforeUpdate")
        resp = client.put(
            f"/api/v1/projects/{created['id']}",
            json={"name": "AfterUpdate", "country": "Brazil"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "AfterUpdate"
        assert data["country"] == "Brazil"
        # unchanged fields persist
        assert data["region"] == SAMPLE_PROJECT["region"]

    def test_update_not_found(self):
        resp = client.put(
            "/api/v1/projects/00000000-0000-0000-0000-000000000000",
            json={"name": "Ghost"},
        )
        assert resp.status_code == 404


class TestDeleteProject:
    def test_delete_existing(self):
        created = _create_project(name="DeleteMe")
        resp = client.delete(f"/api/v1/projects/{created['id']}")
        assert resp.status_code == 204
        # confirm gone
        resp2 = client.get(f"/api/v1/projects/{created['id']}")
        assert resp2.status_code == 404

    def test_delete_not_found(self):
        resp = client.delete("/api/v1/projects/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


# ────────────────────────────────────────────────────────────
# Tests — Boundary Upload
# ────────────────────────────────────────────────────────────


class TestBoundaryUpload:
    def test_upload_geojson(self):
        project = _create_project(name="BoundaryProject")
        pid = project["id"]

        file_bytes = json.dumps(SAMPLE_GEOJSON).encode()
        resp = client.post(
            f"/api/v1/projects/{pid}/upload-boundary",
            files={
                "file": ("boundary.geojson", io.BytesIO(file_bytes), "application/json")
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["project_id"] == pid
        assert data["area_ha"] is not None

    def test_upload_invalid_extension(self):
        project = _create_project(name="BadExt")
        resp = client.post(
            f"/api/v1/projects/{project['id']}/upload-boundary",
            files={"file": ("boundary.txt", b"not geojson", "text/plain")},
        )
        assert resp.status_code == 400

    def test_upload_invalid_json(self):
        project = _create_project(name="BadJSON")
        resp = client.post(
            f"/api/v1/projects/{project['id']}/upload-boundary",
            files={"file": ("boundary.geojson", b"not json", "application/json")},
        )
        assert resp.status_code == 400

    def test_get_boundary(self):
        project = _create_project(name="GetBoundary")
        pid = project["id"]
        file_bytes = json.dumps(SAMPLE_GEOJSON).encode()
        client.post(
            f"/api/v1/projects/{pid}/upload-boundary",
            files={
                "file": ("boundary.geojson", io.BytesIO(file_bytes), "application/json")
            },
        )
        resp = client.get(f"/api/v1/projects/{pid}/boundary")
        assert resp.status_code == 200
        assert resp.json()["project_id"] == pid

    def test_get_boundary_not_found(self):
        project = _create_project(name="NoBoundary")
        resp = client.get(f"/api/v1/projects/{project['id']}/boundary")
        assert resp.status_code == 404
