"""
Tests for Satellite Data Fetcher (Task 1.3)
===========================================
Unit tests that mock the Google Earth Engine API so they run
without GEE credentials.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# ────────────────────────────────────────────────────────────
# Fixtures / Helpers
# ────────────────────────────────────────────────────────────

SAMPLE_BOUNDARY = {
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
}

MOCK_TIMESERIES = pd.DataFrame(
    {
        "date": pd.to_datetime(["2025-01-15", "2025-02-14", "2025-03-16"]),
        "ndvi_mean": [0.45, 0.52, 0.58],
        "ndvi_std": [0.05, 0.04, 0.03],
        "ndvi_count": [1200, 1350, 1500],
        "evi_mean": [0.32, 0.38, 0.42],
        "cloud_cover_pct": [12.0, 8.0, 5.0],
        "data_source": [
            "Sentinel-2_SR_Harmonized",
            "Sentinel-2_SR_Harmonized",
            "Sentinel-2_SR_Harmonized",
        ],
    }
)


# ────────────────────────────────────────────────────────────
# Tests — SatelliteDataFetcher
# ────────────────────────────────────────────────────────────


class TestSatelliteDataFetcherInit:
    """Verify fetcher initialises its sub-clients."""

    @patch("src.satellite_services.data_fetcher.EarthEngineClient")
    @patch("src.satellite_services.data_fetcher.NDVICalculator")
    def test_init_creates_client_and_calculator(self, mock_calc_cls, mock_ee_cls):
        from src.satellite_services.data_fetcher import SatelliteDataFetcher

        fetcher = SatelliteDataFetcher(project="test-proj")
        mock_ee_cls.assert_called_once_with(project="test-proj")
        mock_calc_cls.assert_called_once_with(client=mock_ee_cls.return_value)
        assert fetcher.client is mock_ee_cls.return_value
        assert fetcher.calculator is mock_calc_cls.return_value


class TestFetchSentinel2:
    """Sentinel-2 fetching via the EarthEngineClient + NDVICalculator."""

    @patch("src.satellite_services.data_fetcher.EarthEngineClient")
    @patch("src.satellite_services.data_fetcher.NDVICalculator")
    def test_returns_dataframe(self, mock_calc_cls, mock_ee_cls):
        mock_calc = mock_calc_cls.return_value
        mock_calc.compute_timeseries.return_value = MOCK_TIMESERIES.copy()

        mock_client = mock_ee_cls.return_value
        mock_ee_cls.geometry_from_geojson.return_value = "mock_ee_geom"

        from src.satellite_services.data_fetcher import SatelliteDataFetcher

        fetcher = SatelliteDataFetcher()
        df = fetcher.fetch_sentinel2_data(
            boundary_geojson=SAMPLE_BOUNDARY,
            start_date="2025-01-01",
            end_date="2025-04-01",
        )

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert "ndvi_mean" in df.columns
        assert "evi_mean" in df.columns
        assert "cloud_cover_pct" in df.columns

    @patch("src.satellite_services.data_fetcher.EarthEngineClient")
    @patch("src.satellite_services.data_fetcher.NDVICalculator")
    def test_empty_dataframe_for_no_images(self, mock_calc_cls, mock_ee_cls):
        mock_calc = mock_calc_cls.return_value
        mock_calc.compute_timeseries.return_value = pd.DataFrame(
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
        mock_ee_cls.geometry_from_geojson.return_value = "mock_ee_geom"

        from src.satellite_services.data_fetcher import SatelliteDataFetcher

        fetcher = SatelliteDataFetcher()
        df = fetcher.fetch_sentinel2_data(
            boundary_geojson=SAMPLE_BOUNDARY,
            start_date="2025-01-01",
            end_date="2025-01-02",
        )

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    @patch("src.satellite_services.data_fetcher.EarthEngineClient")
    @patch("src.satellite_services.data_fetcher.NDVICalculator")
    def test_passes_cloud_cover_and_scale(self, mock_calc_cls, mock_ee_cls):
        mock_calc = mock_calc_cls.return_value
        mock_calc.compute_timeseries.return_value = MOCK_TIMESERIES.copy()
        mock_ee_cls.geometry_from_geojson.return_value = "mock_ee_geom"

        from src.satellite_services.data_fetcher import SatelliteDataFetcher

        fetcher = SatelliteDataFetcher()
        fetcher.fetch_sentinel2_data(
            boundary_geojson=SAMPLE_BOUNDARY,
            start_date="2025-01-01",
            end_date="2025-06-01",
            max_cloud_cover=15,
            scale=10,
        )

        mock_calc.compute_timeseries.assert_called_once_with(
            geometry="mock_ee_geom",
            start_date="2025-01-01",
            end_date="2025-06-01",
            max_cloud_pct=15,
            scale=10,
        )


class TestFetchUnified:
    """The unified fetch_data entry point delegates correctly."""

    @patch("src.satellite_services.data_fetcher.EarthEngineClient")
    @patch("src.satellite_services.data_fetcher.NDVICalculator")
    def test_default_source_is_sentinel2(self, mock_calc_cls, mock_ee_cls):
        mock_calc = mock_calc_cls.return_value
        mock_calc.compute_timeseries.return_value = MOCK_TIMESERIES.copy()
        mock_ee_cls.geometry_from_geojson.return_value = "mock_ee_geom"

        from src.satellite_services.data_fetcher import SatelliteDataFetcher

        fetcher = SatelliteDataFetcher()
        df = fetcher.fetch_data(
            boundary_geojson=SAMPLE_BOUNDARY,
            start_date="2025-01-01",
            end_date="2025-06-01",
        )
        # Should call compute_timeseries (Sentinel-2 path)
        mock_calc.compute_timeseries.assert_called_once()
        assert len(df) == 3


class TestTestConnection:
    """Test connectivity check delegation."""

    @patch("src.satellite_services.data_fetcher.EarthEngineClient")
    @patch("src.satellite_services.data_fetcher.NDVICalculator")
    def test_delegates_to_client(self, mock_calc_cls, mock_ee_cls):
        mock_client = mock_ee_cls.return_value
        mock_client.test_connection.return_value = {
            "status": "ok",
            "message": "Connected",
            "image_count": 5,
        }

        from src.satellite_services.data_fetcher import SatelliteDataFetcher

        fetcher = SatelliteDataFetcher()
        result = fetcher.test_connection()
        assert result["status"] == "ok"
        mock_client.test_connection.assert_called_once()
