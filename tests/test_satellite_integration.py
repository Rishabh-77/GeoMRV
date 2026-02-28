"""
Integration Tests – Satellite Services
=======================================
Run with:
    pytest tests/test_satellite_integration.py -v

These tests require a working GEE authentication (``earthengine authenticate``).
They hit the live GEE API, so they are *integration* tests – keep the test
regions small to stay within free-tier quotas.
"""

import os
import pytest
import ee

# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def gee_client():
    """Provide a shared EarthEngineClient for the test module."""
    from src.satellite_services.earth_engine_client import EarthEngineClient
    return EarthEngineClient()


@pytest.fixture(scope="module")
def goa_geometry():
    """Small rectangle over Goa, India (~40 km²)."""
    return ee.Geometry.Rectangle([73.8, 15.35, 73.95, 15.45])


# Sample date range – 2 months to keep it fast
START_DATE = "2025-01-01"
END_DATE = "2025-03-01"


# ── 1. Earth Engine Client Tests ─────────────────────────────────────────

class TestEarthEngineClient:
    """Verify GEE initialisation and Sentinel-2 collection loading."""

    def test_connection(self, gee_client):
        result = gee_client.test_connection()
        assert result["status"] == "ok", f"GEE connection failed: {result['message']}"
        assert result["image_count"] >= 0

    def test_sentinel2_collection(self, gee_client, goa_geometry):
        col = gee_client.get_sentinel2(
            goa_geometry, START_DATE, END_DATE, max_cloud_pct=30
        )
        count = col.size().getInfo()
        assert count >= 0, "Collection size should be non-negative"
        # At least some Sentinel-2 images should exist for Goa in 2 months
        assert count > 0, (
            f"Expected >0 Sentinel-2 images for Goa ({START_DATE}–{END_DATE}), got {count}"
        )

    def test_geometry_from_bbox(self, gee_client):
        geom = gee_client.geometry_from_bbox(73.8, 15.35, 73.95, 15.45)
        assert isinstance(geom, ee.Geometry)

    def test_geometry_from_geojson(self, gee_client):
        geojson = {
            "type": "Polygon",
            "coordinates": [
                [[73.8, 15.35], [73.95, 15.35], [73.95, 15.45], [73.8, 15.45], [73.8, 15.35]]
            ],
        }
        geom = gee_client.geometry_from_geojson(geojson)
        assert isinstance(geom, ee.Geometry)

    def test_cloud_masking_applied(self, gee_client, goa_geometry):
        """Cloud masking should not remove all images."""
        col = gee_client.get_sentinel2(
            goa_geometry, START_DATE, END_DATE, max_cloud_pct=50, apply_cloud_mask=True
        )
        count = col.size().getInfo()
        assert count > 0, "Cloud masking removed all images unexpectedly"


# ── 2. NDVI Calculator Tests ────────────────────────────────────────────

class TestNDVICalculator:
    """Verify NDVI/EVI time-series computation."""

    def test_timeseries_returns_dataframe(self, gee_client, goa_geometry):
        from src.satellite_services.ndvi_calculator import NDVICalculator

        calc = NDVICalculator(client=gee_client)
        df = calc.compute_timeseries(
            goa_geometry, START_DATE, END_DATE, max_cloud_pct=30
        )

        assert not df.empty, "NDVI time-series DataFrame should not be empty"
        for col in ["date", "ndvi_mean", "cloud_cover_pct", "data_source"]:
            assert col in df.columns, f"Missing column: {col}"

    def test_ndvi_values_in_range(self, gee_client, goa_geometry):
        from src.satellite_services.ndvi_calculator import NDVICalculator

        calc = NDVICalculator(client=gee_client)
        df = calc.compute_timeseries(
            goa_geometry, START_DATE, END_DATE, max_cloud_pct=30
        )

        valid = df["ndvi_mean"].dropna()
        if not valid.empty:
            assert valid.min() >= -1.0, "NDVI should be >= -1"
            assert valid.max() <= 1.0, "NDVI should be <= 1"

    def test_cloud_cover_column(self, gee_client, goa_geometry):
        from src.satellite_services.ndvi_calculator import NDVICalculator

        calc = NDVICalculator(client=gee_client)
        df = calc.compute_timeseries(
            goa_geometry, START_DATE, END_DATE, max_cloud_pct=30
        )

        if not df.empty:
            assert (df["cloud_cover_pct"] <= 30).all(), (
                "All rows should have cloud_cover ≤ max_cloud_pct"
            )


# ── 3. Timelapse Exporter Tests ─────────────────────────────────────────

class TestTimelapseExporter:
    """Verify timelapse MP4 generation (does NOT upload to Azure)."""

    def test_generate_creates_mp4(self, gee_client, goa_geometry, tmp_path):
        from src.satellite_services.timelapse_exporter import TimelapseExporter

        exporter = TimelapseExporter(client=gee_client)
        output = str(tmp_path / "test_timelapse.mp4")

        mp4_path = exporter.generate(
            geometry=goa_geometry,
            start_date=START_DATE,
            end_date=END_DATE,
            interval_days=30,
            max_cloud_pct=40,
            fps=1,
            output_path=output,
        )

        assert os.path.isfile(mp4_path), f"MP4 not found at {mp4_path}"
        assert os.path.getsize(mp4_path) > 0, "MP4 file is empty"

    def test_generate_with_small_interval(self, gee_client, goa_geometry, tmp_path):
        """Two-week interval should produce more frames."""
        from src.satellite_services.timelapse_exporter import TimelapseExporter

        exporter = TimelapseExporter(client=gee_client)
        output = str(tmp_path / "timelapse_14d.mp4")

        mp4_path = exporter.generate(
            geometry=goa_geometry,
            start_date=START_DATE,
            end_date=END_DATE,
            interval_days=14,
            fps=2,
            output_path=output,
        )
        assert os.path.isfile(mp4_path)


# ── 4. Optional – Blob Upload (skipped if env vars missing) ─────────────

class TestBlobUpload:
    """Test Azure Blob upload – requires AZURE_STORAGE_CONNECTION_STRING."""

    @pytest.mark.skipif(
        not os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
        reason="AZURE_STORAGE_CONNECTION_STRING not set",
    )
    def test_upload_and_url(self, gee_client, goa_geometry, tmp_path):
        from src.satellite_services.timelapse_exporter import TimelapseExporter

        exporter = TimelapseExporter(client=gee_client)
        output = str(tmp_path / "upload_test.mp4")

        mp4_path = exporter.generate(
            geometry=goa_geometry,
            start_date=START_DATE,
            end_date=END_DATE,
            interval_days=60,
            fps=1,
            output_path=output,
        )

        blob_url = exporter.upload_to_blob(
            mp4_path,
            blob_name="test/integration_test_timelapse.mp4",
        )
        assert blob_url.startswith("https://"), f"Unexpected blob URL: {blob_url}"
