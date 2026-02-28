"""
Timelapse Exporter
==================
Generates a Sentinel-2 true-colour (RGB) timelapse for a given area of
interest and uploads the resulting MP4 to Azure Blob Storage.

Strategy
--------
GEE video export only targets Google Cloud Storage / Drive, which we do not
use.  Instead we:

1. Build a monthly (or per-image) composite collection over the date range.
2. Download each composite as a thumbnail PNG via ``ee.Image.getThumbUrl``.
3. Stitch the frames into an MP4 with ``imageio``.
4. Upload the MP4 to the ``satellite-data-cache`` container in Azure Blob.
"""

import io
import logging
import os
import tempfile
from pathlib import Path
from typing import List, Optional

import ee
import requests

from .earth_engine_client import EarthEngineClient

logger = logging.getLogger(__name__)

# Visualisation parameters for Sentinel-2 true-colour RGB
_S2_VIS = {
    "bands": ["B4", "B3", "B2"],  # Red, Green, Blue
    "min": 0,
    "max": 3000,
    "dimensions": 640,  # px on the longest edge
}


class TimelapseExporter:
    """
    Generate a Sentinel-2 RGB timelapse (MP4) for a project boundary and
    optionally upload it to Azure Blob Storage.

    Usage::

        exporter = TimelapseExporter()
        mp4_path = exporter.generate(
            geometry=ee.Geometry.Rectangle([73.5, 15.2, 74.2, 15.6]),
            start_date="2024-01-01",
            end_date="2025-01-01",
            interval_days=30,
        )
        blob_url = exporter.upload_to_blob(mp4_path, "project-abc/timelapse.mp4")
    """

    def __init__(self, client: Optional[EarthEngineClient] = None):
        self.client = client or EarthEngineClient()

    # ------------------------------------------------------------------
    # Frame generation
    # ------------------------------------------------------------------

    @staticmethod
    def _monthly_composites(
        collection: ee.ImageCollection,
        geometry: ee.Geometry,
        start_date: str,
        end_date: str,
        interval_days: int = 30,
    ) -> List[ee.Image]:
        """
        Create median composites over rolling windows of *interval_days*
        and return them as a list of ``ee.Image`` objects.
        """
        import datetime as dt

        start = dt.datetime.strptime(start_date, "%Y-%m-%d")
        end = dt.datetime.strptime(end_date, "%Y-%m-%d")

        composites: List[ee.Image] = []
        cursor = start
        while cursor < end:
            window_end = cursor + dt.timedelta(days=interval_days)
            window_end_str = window_end.strftime("%Y-%m-%d")
            cursor_str = cursor.strftime("%Y-%m-%d")

            composite = (
                collection.filterDate(cursor_str, window_end_str).median().clip(geometry)
            )
            # Attach a label for annotation
            composite = composite.set("label", cursor_str)
            composites.append(composite)
            cursor = window_end

        return composites

    @staticmethod
    def _download_frame(image: ee.Image, geometry: ee.Geometry, vis: dict) -> bytes:
        """Download a single frame as PNG bytes via getThumbUrl."""
        url = image.getThumbUrl(
            {
                **vis,
                "region": geometry,
                "format": "png",
            }
        )
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        return resp.content

    # ------------------------------------------------------------------
    # MP4 generation
    # ------------------------------------------------------------------

    def generate(
        self,
        geometry: ee.Geometry,
        start_date: str,
        end_date: str,
        interval_days: int = 30,
        max_cloud_pct: float = 30,
        fps: int = 2,
        output_path: Optional[str] = None,
        vis_params: Optional[dict] = None,
    ) -> str:
        """
        Build a timelapse MP4 from Sentinel-2 monthly composites.

        Parameters
        ----------
        geometry : ee.Geometry
        start_date, end_date : str  (YYYY-MM-DD)
        interval_days : int   Composite window length in days.
        max_cloud_pct : float Scene-level cloud filter.
        fps : int             Frames per second in the output video.
        output_path : str     Destination file path.  Defaults to a temp file.
        vis_params : dict     Override default true-colour vis params.

        Returns
        -------
        str   Absolute path to the generated MP4 file.
        """
        try:
            import imageio.v3 as iio
        except ImportError:
            import imageio as iio  # fallback for older imageio

        vis = vis_params or _S2_VIS

        logger.info(
            "Generating timelapse: %s → %s (interval=%d days, cloud≤%d%%)",
            start_date,
            end_date,
            interval_days,
            max_cloud_pct,
        )

        collection = self.client.get_sentinel2(
            geometry, start_date, end_date, max_cloud_pct
        )

        composites = self._monthly_composites(
            collection, geometry, start_date, end_date, interval_days
        )

        if not composites:
            raise ValueError("No composites could be generated for the given range.")

        frames: list = []
        for idx, composite in enumerate(composites):
            try:
                png_bytes = self._download_frame(composite, geometry, vis)
                frame = iio.imread(io.BytesIO(png_bytes))
                frames.append(frame)
                logger.info("  Frame %d/%d downloaded", idx + 1, len(composites))
            except Exception as exc:
                logger.warning("  Frame %d skipped: %s", idx + 1, exc)

        if not frames:
            raise RuntimeError("All frames failed to download – no timelapse produced.")

        if output_path is None:
            output_path = os.path.join(tempfile.gettempdir(), "geomrv_timelapse.mp4")

        # Ensure parent directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Write MP4 using imageio + ffmpeg plugin
        try:
            iio.imwrite(output_path, frames, fps=fps, plugin="pyav")
        except Exception:
            # Fallback: try the legacy imageio writer
            import imageio
            writer = imageio.get_writer(output_path, fps=fps)
            for f in frames:
                writer.append_data(f)
            writer.close()

        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        logger.info(
            "Timelapse saved: %s (%.1f MB, %d frames @ %d fps)",
            output_path,
            file_size_mb,
            len(frames),
            fps,
        )
        return output_path

    # ------------------------------------------------------------------
    # Azure Blob upload
    # ------------------------------------------------------------------

    @staticmethod
    def upload_to_blob(
        local_path: str,
        blob_name: str,
        container: Optional[str] = None,
        connection_string: Optional[str] = None,
    ) -> str:
        """
        Upload the timelapse MP4 to Azure Blob Storage.

        Parameters
        ----------
        local_path : str         Path to the local MP4 file.
        blob_name : str          Blob path inside the container,
                                 e.g. ``timelapse/project-abc/2025.mp4``.
        container : str          Container name (default ``satellite-data-cache``).
        connection_string : str  Azure Storage connection string.

        Returns
        -------
        str   Full blob URL.
        """
        from azure.storage.blob import BlobServiceClient, ContentSettings

        container = container or os.getenv(
            "AZURE_STORAGE_CONTAINER_CACHE", "satellite-data-cache"
        )
        connection_string = connection_string or os.getenv(
            "AZURE_STORAGE_CONNECTION_STRING"
        )
        if not connection_string:
            raise EnvironmentError(
                "AZURE_STORAGE_CONNECTION_STRING is not set – cannot upload."
            )

        blob_service = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service.get_blob_client(container=container, blob=blob_name)

        with open(local_path, "rb") as fh:
            blob_client.upload_blob(
                fh,
                overwrite=True,
                content_settings=ContentSettings(content_type="video/mp4"),
            )

        url = blob_client.url
        logger.info("Timelapse uploaded to blob: %s", url)
        return url
