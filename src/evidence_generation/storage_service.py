"""
GeoMRV Evidence Storage Service
================================
Upload, download, and manage evidence packages in Azure Blob Storage.

Supports both connection-string and account-key authentication.
When no Azure credentials are available, falls back to local filesystem
storage so the pipeline remains testable offline.

Usage
-----
::

    from src.evidence_generation.storage_service import EvidenceStorageService

    # Azure mode
    svc = EvidenceStorageService(
        connection_string="DefaultEndpointsProtocol=https;...",
        container_name="evidence-packages",
    )

    # Local-fallback mode (no Azure)
    svc = EvidenceStorageService(local_storage_dir="./evidence_output")

    result = svc.upload_package("/tmp/report.pdf", "pkg-001")
    svc.download_package(result["blob_path"], "/tmp/downloaded.pdf")
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class EvidenceStorageService:
    """Store and retrieve evidence packages.

    Parameters
    ----------
    connection_string : str | None
        Azure Blob Storage connection string.  When provided, blobs are
        stored in Azure.
    container_name : str
        Azure container name (default ``"evidence-packages"``).
    local_storage_dir : str | None
        Path to a local directory used for offline / test storage.
        Used when *connection_string* is ``None``.
    """

    def __init__(
        self,
        connection_string: Optional[str] = None,
        container_name: str = "evidence-packages",
        local_storage_dir: Optional[str] = None,
    ) -> None:
        self.container_name = container_name
        self._connection_string = connection_string
        self._blob_service_client: Any = None

        if connection_string:
            try:
                from azure.storage.blob import BlobServiceClient

                self._blob_service_client = BlobServiceClient.from_connection_string(
                    connection_string
                )
                self._ensure_container()
                logger.info(
                    "EvidenceStorageService initialised (Azure, container=%s)",
                    container_name,
                )
            except Exception:
                logger.warning(
                    "Failed to connect to Azure Blob Storage – "
                    "falling back to local storage.",
                    exc_info=True,
                )
                self._blob_service_client = None

        # Local fallback directory
        self._local_dir: Optional[Path] = None
        if self._blob_service_client is None:
            base = local_storage_dir or os.path.join("output", "evidence_storage")
            self._local_dir = Path(base)
            self._local_dir.mkdir(parents=True, exist_ok=True)
            logger.info(
                "EvidenceStorageService initialised (local, dir=%s)",
                self._local_dir,
            )

    # ── public API ────────────────────────────────────────────

    @property
    def is_azure(self) -> bool:
        """Whether Azure Blob Storage is active."""
        return self._blob_service_client is not None

    def upload_package(
        self,
        file_path: str,
        package_id: str,
        *,
        blob_prefix: str = "packages",
    ) -> Dict[str, Any]:
        """Upload an evidence package file.

        Parameters
        ----------
        file_path : str
            Absolute path to the local file to upload.
        package_id : str
            Unique package identifier used in the blob name.
        blob_prefix : str
            Virtual directory prefix inside the container.

        Returns
        -------
        dict
            ``blob_path``, ``checksum`` (SHA-256), ``size_bytes``,
            ``url``, ``uploaded_at``.

        Raises
        ------
        FileNotFoundError
            If *file_path* does not exist.
        """
        src = Path(file_path)
        if not src.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")

        blob_data = src.read_bytes()
        checksum = hashlib.sha256(blob_data).hexdigest()
        size_bytes = len(blob_data)

        # Determine extension
        ext = src.suffix or ".pdf"
        blob_name = f"{blob_prefix}/{package_id}{ext}"

        if self._blob_service_client is not None:
            return self._upload_azure(blob_name, blob_data, checksum, size_bytes)

        return self._upload_local(blob_name, blob_data, checksum, size_bytes)

    def download_package(
        self,
        blob_name: str,
        local_path: str,
    ) -> Dict[str, Any]:
        """Download an evidence package to a local file.

        Parameters
        ----------
        blob_name : str
            Blob path (e.g. ``"packages/pkg-001.pdf"``).
        local_path : str
            Destination path on the local filesystem.

        Returns
        -------
        dict
            ``local_path``, ``size_bytes``, ``downloaded_at``.

        Raises
        ------
        FileNotFoundError
            If the blob/file does not exist.
        """
        if self._blob_service_client is not None:
            return self._download_azure(blob_name, local_path)

        return self._download_local(blob_name, local_path)

    def delete_package(self, blob_name: str) -> bool:
        """Delete a package from storage. Returns ``True`` on success."""
        if self._blob_service_client is not None:
            return self._delete_azure(blob_name)
        return self._delete_local(blob_name)

    def package_exists(self, blob_name: str) -> bool:
        """Check whether a package exists in storage."""
        if self._blob_service_client is not None:
            return self._exists_azure(blob_name)
        return self._exists_local(blob_name)

    # ── Azure operations ──────────────────────────────────────

    def _ensure_container(self) -> None:
        """Create the Azure container if it does not exist."""
        try:
            container_client = self._blob_service_client.get_container_client(
                self.container_name
            )
            if not container_client.exists():
                self._blob_service_client.create_container(self.container_name)
                logger.info("Created Azure container: %s", self.container_name)
        except Exception:
            logger.warning(
                "Could not verify/create container %s",
                self.container_name,
                exc_info=True,
            )

    def _upload_azure(
        self,
        blob_name: str,
        blob_data: bytes,
        checksum: str,
        size_bytes: int,
    ) -> Dict[str, Any]:
        from azure.core.exceptions import AzureError

        try:
            blob_client = self._blob_service_client.get_blob_client(
                container=self.container_name, blob=blob_name
            )
            blob_client.upload_blob(blob_data, overwrite=True)
            url = blob_client.url

            logger.info(
                "Uploaded %s (%d bytes, sha256=%s…)",
                blob_name,
                size_bytes,
                checksum[:16],
            )
            return {
                "blob_path": blob_name,
                "checksum": checksum,
                "size_bytes": size_bytes,
                "url": url,
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
            }
        except AzureError as exc:
            logger.error("Azure upload failed for %s: %s", blob_name, exc)
            raise

    def _download_azure(self, blob_name: str, local_path: str) -> Dict[str, Any]:
        from azure.core.exceptions import AzureError, ResourceNotFoundError

        try:
            blob_client = self._blob_service_client.get_blob_client(
                container=self.container_name, blob=blob_name
            )
            data = blob_client.download_blob().readall()
            dest = Path(local_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)

            logger.info(
                "Downloaded %s → %s (%d bytes)", blob_name, local_path, len(data)
            )
            return {
                "local_path": str(dest),
                "size_bytes": len(data),
                "downloaded_at": datetime.now(timezone.utc).isoformat(),
            }
        except ResourceNotFoundError:
            raise FileNotFoundError(f"Blob not found: {blob_name}")
        except AzureError as exc:
            logger.error("Azure download failed for %s: %s", blob_name, exc)
            raise

    def _delete_azure(self, blob_name: str) -> bool:
        try:
            blob_client = self._blob_service_client.get_blob_client(
                container=self.container_name, blob=blob_name
            )
            blob_client.delete_blob()
            logger.info("Deleted Azure blob: %s", blob_name)
            return True
        except Exception:
            logger.warning("Failed to delete Azure blob: %s", blob_name, exc_info=True)
            return False

    def _exists_azure(self, blob_name: str) -> bool:
        try:
            blob_client = self._blob_service_client.get_blob_client(
                container=self.container_name, blob=blob_name
            )
            blob_client.get_blob_properties()
            return True
        except Exception:
            return False

    # ── local filesystem operations ───────────────────────────

    def _upload_local(
        self,
        blob_name: str,
        blob_data: bytes,
        checksum: str,
        size_bytes: int,
    ) -> Dict[str, Any]:
        assert self._local_dir is not None
        dest = self._local_dir / blob_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob_data)

        logger.info(
            "Stored locally %s (%d bytes, sha256=%s…)",
            dest,
            size_bytes,
            checksum[:16],
        )
        return {
            "blob_path": blob_name,
            "checksum": checksum,
            "size_bytes": size_bytes,
            "url": f"file://{dest.resolve()}",
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }

    def _download_local(self, blob_name: str, local_path: str) -> Dict[str, Any]:
        assert self._local_dir is not None
        src = self._local_dir / blob_name
        if not src.is_file():
            raise FileNotFoundError(f"Local blob not found: {src}")

        dest = Path(local_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dest))

        logger.info("Copied %s → %s", src, dest)
        return {
            "local_path": str(dest),
            "size_bytes": src.stat().st_size,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
        }

    def _delete_local(self, blob_name: str) -> bool:
        assert self._local_dir is not None
        target = self._local_dir / blob_name
        if target.is_file():
            target.unlink()
            logger.info("Deleted local file: %s", target)
            return True
        return False

    def _exists_local(self, blob_name: str) -> bool:
        assert self._local_dir is not None
        return (self._local_dir / blob_name).is_file()
