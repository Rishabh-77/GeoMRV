"""
GeoMRV Evidence Pipeline Tests – Task 3.3
==========================================
Tests for PackageAssemblyService, EvidenceStorageService,
and the evidence router endpoints (generate + download).

Uses PostgreSQL-backed transactional test sessions and mocked
Azure storage interactions.

Run::

    python -m pytest tests/test_evidence_pipeline.py -v
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from src.api.models import (
    Base,
    Boundary,
    EvidencePackage as EvidencePackageModel,
    Job,
    Observation,
    Project,
)
from src.evidence_generation.package_assembly import PackageAssemblyService
from src.evidence_generation.package_schema import (
    DataSource,
    EvidencePackage,
    Feature,
    ProcessingStep,
    VerificationResult,
)
from src.api.database import engine as pg_engine
from src.evidence_generation.storage_service import EvidenceStorageService

# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    """Provide a PostgreSQL session isolated via nested transaction.

    This fixture intentionally uses the real PostgreSQL engine to keep
    JSONB behavior aligned with production. Each test runs inside an
    outer transaction that is rolled back at teardown.
    """
    test_db_url = os.getenv("TEST_DATABASE_URL")
    test_engine = pg_engine
    if test_db_url:
        from sqlalchemy import create_engine

        test_engine = create_engine(test_db_url)

    try:
        connection = test_engine.connect()
    except OperationalError as exc:
        pytest.skip(f"PostgreSQL test DB unreachable: {exc}")

    outer_txn = connection.begin()

    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()

    connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, trans):
        if trans.nested and not trans._parent.nested:
            connection.begin_nested()

    try:
        yield session
    finally:
        event.remove(session, "after_transaction_end", _restart_savepoint)
        session.close()
        outer_txn.rollback()
        connection.close()


@pytest.fixture()
def project_id() -> str:
    """Return a unique UUID string for test projects."""
    return str(uuid.uuid4())


@pytest.fixture()
def sample_project(db: Session, project_id: str) -> Project:
    """Insert a sample project and return it."""
    proj = Project(
        id=uuid.UUID(project_id),
        name="Test Carbon Project",
        description="A test project for evidence pipeline",
        location_name="Test Forest",
        country="India",
        region="Maharashtra",
        total_area_ha=250.0,
        project_type="forest",
        start_date=date(2024, 1, 1),
    )
    db.add(proj)
    db.commit()
    return proj


@pytest.fixture()
def sample_observations(
    db: Session, project_id: str, sample_project: Project
) -> List[Observation]:
    """Insert 12 monthly observations."""
    obs_list = []
    for month in range(1, 13):
        ndvi = 0.3 + 0.2 * (month / 12)
        obs = Observation(
            id=uuid.uuid4(),
            project_id=uuid.UUID(project_id),
            observation_date=date(2025, month, 15),
            ndvi=round(ndvi, 4),
            ndvi_std=round(ndvi * 0.1, 4),
            ndvi_count=50,
            evi=round(ndvi * 0.8, 4),
            biomass_estimate=round(ndvi * 100, 2),
            biomass_std=round(ndvi * 10, 2),
            data_source="Sentinel-2",
            cloud_cover_percent=round(10 + month, 2),
        )
        db.add(obs)
        obs_list.append(obs)
    db.commit()
    return obs_list


@pytest.fixture()
def sample_jobs(db: Session, project_id: str, sample_project: Project) -> List[Job]:
    """Insert processing jobs simulating a full pipeline run."""
    pid = uuid.UUID(project_id)
    jobs = []

    # 1) satellite_data_fetch
    j1 = Job(
        id=uuid.uuid4(),
        project_id=pid,
        operation_type="satellite_data_fetch",
        status="success",
        input_data={
            "collection": "COPERNICUS/S2_SR_HARMONIZED",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "cloud_cover_max": 30,
        },
        output_data={"observation_count": 12},
        execution_time_ms=4500,
        created_at=datetime(2025, 6, 1, 10, 0, 0),
    )
    db.add(j1)
    jobs.append(j1)

    # 2) feature_extraction
    j2 = Job(
        id=uuid.uuid4(),
        project_id=pid,
        operation_type="feature_extraction",
        status="success",
        input_data={"start_date": "2025-01-01", "end_date": "2025-12-31"},
        output_data={
            "ndvi_stats": {"mean": 0.42, "std": 0.08, "min": 0.30, "max": 0.55},
            "trend": {"trend_slope": 0.0003, "slope_per_year": 0.11, "r_squared": 0.85},
            "seasonality": {
                "peak_month": 8,
                "trough_month": 2,
                "seasonal_amplitude": 0.18,
            },
            "biomass_stats": {"mean": 42.0, "std": 8.0},
            "total_observations": 12,
            "clear_observations": 10,
        },
        execution_time_ms=1200,
        created_at=datetime(2025, 6, 1, 10, 5, 0),
    )
    db.add(j2)
    jobs.append(j2)

    # 3) ml_scoring
    j3 = Job(
        id=uuid.uuid4(),
        project_id=pid,
        operation_type="ml_scoring",
        status="success",
        input_data={"model_version": "biomass_v1"},
        output_data={
            "prediction": "growth",
            "confidence": 0.87,
        },
        execution_time_ms=800,
        created_at=datetime(2025, 6, 1, 10, 10, 0),
    )
    db.add(j3)
    jobs.append(j3)

    # 4) verification
    j4 = Job(
        id=uuid.uuid4(),
        project_id=pid,
        operation_type="verification",
        status="success",
        input_data={},
        output_data={
            "overall_status": "REVIEW_REQUIRED",
            "flags": [
                {
                    "rule_id": "R1",
                    "name": "Insufficient Observations",
                    "risk_level": "low",
                    "description": "12 observations found (minimum 6)",
                    "recommendation": "None required",
                },
                {
                    "rule_id": "R3",
                    "name": "Anomalous NDVI Spike",
                    "risk_level": "medium",
                    "description": "NDVI spike detected in month 8",
                    "recommendation": "Review seasonal pattern",
                },
            ],
        },
        execution_time_ms=350,
        created_at=datetime(2025, 6, 1, 10, 15, 0),
    )
    db.add(j4)
    jobs.append(j4)

    db.commit()
    return jobs


@pytest.fixture()
def tmp_dir() -> Generator[str, None, None]:
    """Provide a temporary directory cleaned up after the test."""
    d = tempfile.mkdtemp(prefix="geomrv_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture()
def sample_pdf(tmp_dir: str) -> str:
    """Create a small dummy PDF file for upload tests."""
    path = os.path.join(tmp_dir, "test_report.pdf")
    # Minimal valid-ish PDF content
    with open(path, "wb") as f:
        f.write(b"%PDF-1.4 test content " + os.urandom(256))
    return path


# ──────────────────────────────────────────────────────────────
# PackageAssemblyService Tests
# ──────────────────────────────────────────────────────────────


class TestPackageAssembly:
    """Tests for PackageAssemblyService."""

    def test_assemble_basic(
        self, db, project_id, sample_project, sample_jobs, sample_observations
    ):
        """Full assembly with all job types and observations."""
        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")

        assert pkg.project_id == project_id
        assert pkg.project_name == "Test Carbon Project"
        assert pkg.analysis_period_start == "2025-01-01"
        assert pkg.analysis_period_end == "2025-12-31"
        assert pkg.checksum  # sealed

    def test_processing_chain_built(self, db, project_id, sample_project, sample_jobs):
        """Processing chain matches the number of jobs."""
        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        assert len(pkg.processing_chain) == 4
        ops = [s.operation for s in pkg.processing_chain]
        assert "satellite_data_fetch" in ops
        assert "feature_extraction" in ops
        assert "ml_scoring" in ops
        assert "verification" in ops

    def test_processing_chain_sequence(
        self, db, project_id, sample_project, sample_jobs
    ):
        """Steps are numbered sequentially."""
        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        sequences = [s.sequence for s in pkg.processing_chain]
        assert sequences == [1, 2, 3, 4]

    def test_data_sources_from_collection(
        self, db, project_id, sample_project, sample_jobs
    ):
        """Data sources extracted from job input_data collection field."""
        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        assert len(pkg.data_sources) >= 1
        assert pkg.data_sources[0].collection == "COPERNICUS/S2_SR_HARMONIZED"
        assert pkg.data_sources[0].name == "Sentinel-2 L2A"

    def test_features_from_feature_extraction(
        self, db, project_id, sample_project, sample_jobs
    ):
        """Features pulled from feature_extraction job output_data."""
        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        names = [f.name for f in pkg.key_features]
        assert "ndvi_mean" in names
        assert "trend_slope" in names
        assert "biomass_mean" in names

    def test_ndvi_mean_value(self, db, project_id, sample_project, sample_jobs):
        """ndvi_mean value matches the feature extraction output."""
        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        ndvi = pkg.get_feature_by_name("ndvi_mean")
        assert ndvi is not None
        assert ndvi.value == 0.42

    def test_ml_results_extracted(self, db, project_id, sample_project, sample_jobs):
        """ML scoring results populate classification & confidence."""
        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        assert pkg.growth_classification == "growth"
        assert pkg.confidence_score == 87.0  # 0.87 × 100

    def test_verification_results(self, db, project_id, sample_project, sample_jobs):
        """Verification flags extracted from the verification job."""
        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        assert len(pkg.verification_results) == 2
        ids = [v.rule_id for v in pkg.verification_results]
        assert "R1" in ids
        assert "R3" in ids

    def test_verification_status_mapping(
        self, db, project_id, sample_project, sample_jobs
    ):
        """Risk levels mapped to correct status values."""
        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        r1 = next(v for v in pkg.verification_results if v.rule_id == "R1")
        r3 = next(v for v in pkg.verification_results if v.rule_id == "R3")
        assert r1.status == "pass"  # low risk
        assert r3.status == "flag"  # medium risk

    def test_overall_status_review_required(
        self, db, project_id, sample_project, sample_jobs
    ):
        """Overall status is REVIEW_REQUIRED when flags exist."""
        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        # R3 has medium risk → flag → REVIEW_REQUIRED
        assert pkg.overall_status == "REVIEW_REQUIRED"

    def test_summary_generated(self, db, project_id, sample_project, sample_jobs):
        """Summary text is generated."""
        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        assert "Test Carbon Project" in pkg.summary
        assert "growth" in pkg.summary
        assert "87.0%" in pkg.summary

    def test_data_quality_score(
        self, db, project_id, sample_project, sample_jobs, sample_observations
    ):
        """Data quality score computed from observations + features."""
        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        assert 50 <= pkg.data_quality_score <= 100

    def test_checksum_sealed(self, db, project_id, sample_project, sample_jobs):
        """Package is sealed with a valid checksum."""
        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        assert pkg.checksum != ""
        assert pkg.verify_integrity()

    def test_project_not_found(self, db):
        """ValueError raised for non-existent project."""
        svc = PackageAssemblyService(db)
        with pytest.raises(ValueError, match="Project not found"):
            svc.assemble_package(
                "99999999-9999-9999-9999-999999999999",
                "2025-01-01",
                "2025-12-31",
            )

    def test_invalid_project_id(self, db):
        """ValueError raised for malformed project UUID."""
        svc = PackageAssemblyService(db)
        with pytest.raises(ValueError, match="Project not found"):
            svc.assemble_package("not-a-uuid", "2025-01-01", "2025-12-31")

    def test_no_jobs_still_works(self, db, project_id, sample_project):
        """Assembly succeeds with no jobs (empty processing chain)."""
        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        assert pkg.project_name == "Test Carbon Project"
        assert len(pkg.processing_chain) == 0
        assert pkg.confidence_score == 50.0  # default
        assert pkg.growth_classification == "stable"  # default

    def test_no_observations_still_works(
        self, db, project_id, sample_project, sample_jobs
    ):
        """Assembly succeeds with no observations."""
        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        assert pkg.project_name == "Test Carbon Project"
        # Features come from jobs, not observations
        assert len(pkg.key_features) > 0

    def test_fallback_features_from_observations(
        self, db, project_id, sample_project, sample_observations
    ):
        """When no feature_extraction job exists, features from raw obs."""
        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        names = [f.name for f in pkg.key_features]
        assert "ndvi_mean" in names
        assert "total_observations" in names

    def test_default_data_source_fallback(self, db, project_id, sample_project):
        """Default data source added when no collection info in jobs."""
        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        assert len(pkg.data_sources) == 1
        assert pkg.data_sources[0].name == "Sentinel-2 L2A"

    def test_ml_confidence_already_0_100(self, db, project_id, sample_project):
        """ML confidence already in 0-100 range stays unchanged."""
        pid = uuid.UUID(project_id)
        job = Job(
            id=uuid.uuid4(),
            project_id=pid,
            operation_type="ml_scoring",
            status="success",
            input_data={},
            output_data={"prediction": "loss", "confidence": 72.5},
            execution_time_ms=100,
            created_at=datetime(2025, 6, 1, 10, 0, 0),
        )
        db.add(job)
        db.commit()

        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        assert pkg.confidence_score == 72.5
        assert pkg.growth_classification == "loss"

    def test_custom_script_version(self, db, project_id, sample_project, sample_jobs):
        """Custom script_version propagated to processing steps."""
        svc = PackageAssemblyService(db, script_version="2.0.0")
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        for step in pkg.processing_chain:
            assert step.script_version == "2.0.0"

    # ── observations DataFrame ────────────────────────────────

    def test_build_observations_dataframe(
        self, db, project_id, sample_project, sample_observations
    ):
        """build_observations_dataframe returns a DataFrame with expected columns."""
        svc = PackageAssemblyService(db)
        df = svc.build_observations_dataframe(project_id, "2025-01-01", "2025-12-31")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 12
        assert "date" in df.columns
        assert "ndvi" in df.columns
        assert "evi" in df.columns

    def test_build_observations_empty(self, db, project_id, sample_project):
        """Empty DataFrame when no observations exist."""
        svc = PackageAssemblyService(db)
        df = svc.build_observations_dataframe(project_id, "2025-01-01", "2025-12-31")
        assert df.empty

    def test_observations_sorted_by_date(
        self, db, project_id, sample_project, sample_observations
    ):
        """Observations DataFrame is sorted by date."""
        svc = PackageAssemblyService(db)
        df = svc.build_observations_dataframe(project_id, "2025-01-01", "2025-12-31")
        dates = df["date"].tolist()
        assert dates == sorted(dates)

    # ── date windowing ────────────────────────────────────────

    def test_date_window_filters_jobs(
        self, db, project_id, sample_project, sample_jobs
    ):
        """Only jobs within the date window are included."""
        svc = PackageAssemblyService(db)
        # Narrow window that excludes most jobs
        pkg = svc.assemble_package(project_id, "2025-06-01", "2025-06-01")
        # Jobs were all created on 2025-06-01 so they should be included
        assert len(pkg.processing_chain) == 4

    def test_date_window_excludes_jobs(
        self, db, project_id, sample_project, sample_jobs
    ):
        """Jobs outside the date window are excluded."""
        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2024-01-01", "2024-12-31")
        assert len(pkg.processing_chain) == 0

    # ── critical flags ────────────────────────────────────────

    def test_overall_status_fail_on_critical(self, db, project_id, sample_project):
        """FAIL status when critical verification flag exists."""
        pid = uuid.UUID(project_id)
        job = Job(
            id=uuid.uuid4(),
            project_id=pid,
            operation_type="verification",
            status="success",
            input_data={},
            output_data={
                "flags": [
                    {
                        "rule_id": "R99",
                        "name": "Critical Issue",
                        "risk_level": "critical",
                        "description": "Something critical",
                        "recommendation": "Immediate action",
                    }
                ]
            },
            created_at=datetime(2025, 6, 1, 10, 0, 0),
        )
        db.add(job)
        db.commit()

        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        assert pkg.overall_status == "FAIL"
        assert pkg.verification_results[0].status == "critical"

    def test_overall_status_pass_clean(self, db, project_id, sample_project):
        """PASS status with high confidence and no flags."""
        pid = uuid.UUID(project_id)
        # ML job with high confidence
        ml_job = Job(
            id=uuid.uuid4(),
            project_id=pid,
            operation_type="ml_scoring",
            status="success",
            input_data={},
            output_data={"prediction": "growth", "confidence": 0.92},
            created_at=datetime(2025, 6, 1, 10, 0, 0),
        )
        db.add(ml_job)
        db.commit()

        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        assert pkg.overall_status == "PASS"


# ──────────────────────────────────────────────────────────────
# EvidenceStorageService Tests (local fallback)
# ──────────────────────────────────────────────────────────────


class TestStorageServiceLocal:
    """Tests for EvidenceStorageService using local filesystem."""

    def test_local_init(self, tmp_dir):
        """Initialises in local mode when no connection string."""
        svc = EvidenceStorageService(local_storage_dir=tmp_dir)
        assert not svc.is_azure
        assert svc._local_dir is not None

    def test_upload_download_roundtrip(self, tmp_dir, sample_pdf):
        """Upload then download produces identical file."""
        svc = EvidenceStorageService(local_storage_dir=tmp_dir)

        result = svc.upload_package(sample_pdf, "pkg-test-001")
        assert result["blob_path"] == "packages/pkg-test-001.pdf"
        assert result["checksum"]
        assert result["size_bytes"] > 0
        assert "uploaded_at" in result

        # Download
        dl_path = os.path.join(tmp_dir, "downloaded.pdf")
        dl_result = svc.download_package(result["blob_path"], dl_path)
        assert os.path.exists(dl_path)
        assert dl_result["size_bytes"] == result["size_bytes"]

        # Content identical
        with open(sample_pdf, "rb") as f1, open(dl_path, "rb") as f2:
            assert f1.read() == f2.read()

    def test_upload_checksum(self, tmp_dir, sample_pdf):
        """Checksum is valid SHA-256."""
        svc = EvidenceStorageService(local_storage_dir=tmp_dir)
        result = svc.upload_package(sample_pdf, "pkg-checksum")

        with open(sample_pdf, "rb") as f:
            expected = hashlib.sha256(f.read()).hexdigest()
        assert result["checksum"] == expected

    def test_upload_file_not_found(self, tmp_dir):
        """FileNotFoundError for missing source file."""
        svc = EvidenceStorageService(local_storage_dir=tmp_dir)
        with pytest.raises(FileNotFoundError):
            svc.upload_package("/nonexistent/path.pdf", "pkg-missing")

    def test_download_not_found(self, tmp_dir):
        """FileNotFoundError when blob does not exist."""
        svc = EvidenceStorageService(local_storage_dir=tmp_dir)
        with pytest.raises(FileNotFoundError):
            svc.download_package(
                "packages/not-here.pdf", os.path.join(tmp_dir, "dl.pdf")
            )

    def test_package_exists(self, tmp_dir, sample_pdf):
        """package_exists returns True after upload."""
        svc = EvidenceStorageService(local_storage_dir=tmp_dir)
        result = svc.upload_package(sample_pdf, "pkg-exists")
        assert svc.package_exists(result["blob_path"]) is True
        assert svc.package_exists("packages/nope.pdf") is False

    def test_delete_package(self, tmp_dir, sample_pdf):
        """delete_package removes the file."""
        svc = EvidenceStorageService(local_storage_dir=tmp_dir)
        result = svc.upload_package(sample_pdf, "pkg-del")
        assert svc.package_exists(result["blob_path"])
        assert svc.delete_package(result["blob_path"]) is True
        assert not svc.package_exists(result["blob_path"])

    def test_delete_nonexistent(self, tmp_dir):
        """Deleting non-existent file returns False."""
        svc = EvidenceStorageService(local_storage_dir=tmp_dir)
        assert svc.delete_package("packages/ghost.pdf") is False

    def test_custom_blob_prefix(self, tmp_dir, sample_pdf):
        """Custom blob_prefix in upload."""
        svc = EvidenceStorageService(local_storage_dir=tmp_dir)
        result = svc.upload_package(sample_pdf, "pkg-custom", blob_prefix="custom-dir")
        assert result["blob_path"] == "custom-dir/pkg-custom.pdf"
        assert svc.package_exists("custom-dir/pkg-custom.pdf")

    def test_upload_preserves_extension(self, tmp_dir):
        """Non-PDF extensions are preserved."""
        json_path = os.path.join(tmp_dir, "package.json")
        with open(json_path, "w") as f:
            json.dump({"test": True}, f)

        svc = EvidenceStorageService(local_storage_dir=tmp_dir)
        result = svc.upload_package(json_path, "pkg-json")
        assert result["blob_path"] == "packages/pkg-json.json"

    def test_default_local_dir_created(self):
        """Default local directory is created when no args provided."""
        svc = EvidenceStorageService()
        assert svc._local_dir is not None
        assert svc._local_dir.exists()
        # Cleanup
        shutil.rmtree(svc._local_dir, ignore_errors=True)


class TestStorageServiceAzureMocked:
    """Tests for Azure code paths using mocked BlobServiceClient."""

    def test_azure_upload(self, tmp_dir, sample_pdf):
        """Azure upload calls blob_client.upload_blob."""
        mock_blob_svc = MagicMock()
        mock_blob_client = MagicMock()
        mock_blob_client.url = (
            "https://test.blob.core.windows.net/evidence/packages/pkg.pdf"
        )
        mock_blob_svc.get_blob_client.return_value = mock_blob_client

        # Patch container check
        mock_container = MagicMock()
        mock_container.exists.return_value = True
        mock_blob_svc.get_container_client.return_value = mock_container

        with patch(
            "src.evidence_generation.storage_service.EvidenceStorageService.__init__",
            lambda self, **kw: None,
        ):
            svc = EvidenceStorageService()
            svc._blob_service_client = mock_blob_svc
            svc._local_dir = None
            svc.container_name = "evidence-packages"

            result = svc.upload_package(sample_pdf, "pkg-azure")
            assert result["blob_path"] == "packages/pkg-azure.pdf"
            assert result["url"] == mock_blob_client.url
            mock_blob_client.upload_blob.assert_called_once()

    def test_azure_download(self, tmp_dir, sample_pdf):
        """Azure download writes blob content to local file."""
        content = b"fake-pdf-content-for-download"

        mock_blob_svc = MagicMock()
        mock_blob_client = MagicMock()
        mock_blob_client.download_blob.return_value.readall.return_value = content
        mock_blob_svc.get_blob_client.return_value = mock_blob_client

        with patch(
            "src.evidence_generation.storage_service.EvidenceStorageService.__init__",
            lambda self, **kw: None,
        ):
            svc = EvidenceStorageService()
            svc._blob_service_client = mock_blob_svc
            svc._local_dir = None
            svc.container_name = "evidence-packages"

            dl_path = os.path.join(tmp_dir, "azure_dl.pdf")
            result = svc.download_package("packages/pkg.pdf", dl_path)
            assert os.path.exists(dl_path)
            with open(dl_path, "rb") as f:
                assert f.read() == content

    def test_is_azure_property(self, tmp_dir):
        """is_azure reflects whether Azure client is active."""
        local_svc = EvidenceStorageService(local_storage_dir=tmp_dir)
        assert local_svc.is_azure is False

        with patch(
            "src.evidence_generation.storage_service.EvidenceStorageService.__init__",
            lambda self, **kw: None,
        ):
            azure_svc = EvidenceStorageService()
            azure_svc._blob_service_client = MagicMock()
            azure_svc._local_dir = None
            assert azure_svc.is_azure is True


# ──────────────────────────────────────────────────────────────
# End-to-End Pipeline Tests
# ──────────────────────────────────────────────────────────────


class TestEndToEndPipeline:
    """Integration: assembly → PDF → storage."""

    def test_assemble_and_generate_pdf(
        self, db, project_id, sample_project, sample_jobs, sample_observations, tmp_dir
    ):
        """Assemble package then generate a valid PDF."""
        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        obs_df = svc.build_observations_dataframe(
            project_id, "2025-01-01", "2025-12-31"
        )

        from src.evidence_generation.report_generator import PDFReportGenerator

        pdf_path = os.path.join(tmp_dir, "e2e_report.pdf")
        gen = PDFReportGenerator()
        gen.generate_report(pkg, pdf_path, observations_df=obs_df)

        assert os.path.exists(pdf_path)
        with open(pdf_path, "rb") as f:
            assert f.read(5) == b"%PDF-"

    def test_full_pipeline_assembly_pdf_storage(
        self, db, project_id, sample_project, sample_jobs, sample_observations, tmp_dir
    ):
        """Full pipeline: assemble → PDF → upload → download → verify."""
        # Assemble
        assembly = PackageAssemblyService(db)
        pkg = assembly.assemble_package(project_id, "2025-01-01", "2025-12-31")
        obs_df = assembly.build_observations_dataframe(
            project_id, "2025-01-01", "2025-12-31"
        )

        # Generate PDF
        from src.evidence_generation.report_generator import PDFReportGenerator

        pdf_path = os.path.join(tmp_dir, f"evidence_{pkg.package_id}.pdf")
        gen = PDFReportGenerator()
        gen.generate_report(pkg, pdf_path, observations_df=obs_df)
        assert os.path.exists(pdf_path)

        # Upload
        storage_dir = os.path.join(tmp_dir, "blob_storage")
        storage = EvidenceStorageService(local_storage_dir=storage_dir)
        upload = storage.upload_package(pdf_path, pkg.package_id)
        assert upload["checksum"]
        assert upload["size_bytes"] > 0

        # Download
        dl_path = os.path.join(tmp_dir, "downloaded.pdf")
        storage.download_package(upload["blob_path"], dl_path)
        assert os.path.exists(dl_path)

        # Verify identical
        with open(pdf_path, "rb") as f1, open(dl_path, "rb") as f2:
            assert f1.read() == f2.read()

    def test_package_metadata_serialisable(
        self, db, project_id, sample_project, sample_jobs
    ):
        """Assembled package can be serialised to JSON and back."""
        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")

        json_str = pkg.to_json()
        restored = EvidencePackage.from_json(json_str)

        assert restored.package_id == pkg.package_id
        assert restored.project_name == pkg.project_name
        assert restored.confidence_score == pkg.confidence_score
        assert len(restored.processing_chain) == len(pkg.processing_chain)
        assert restored.verify_integrity()

    def test_assemble_minimal_project(self, db, project_id, sample_project):
        """Minimal project (no jobs, no obs) produces valid sealed package."""
        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")

        assert pkg.project_name == "Test Carbon Project"
        assert pkg.verify_integrity()
        json_str = pkg.to_json()
        assert json_str  # serialisable

    def test_pdf_from_minimal_package(self, db, project_id, sample_project, tmp_dir):
        """PDF generation works even with a minimal package."""
        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")

        from src.evidence_generation.report_generator import PDFReportGenerator

        pdf_path = os.path.join(tmp_dir, "minimal.pdf")
        gen = PDFReportGenerator()
        gen.generate_report(pkg, pdf_path)
        assert os.path.exists(pdf_path)


# ──────────────────────────────────────────────────────────────
# Evidence Router Tests (unit-level with mocked deps)
# ──────────────────────────────────────────────────────────────


class TestEvidenceRouter:
    """Test the FastAPI evidence router endpoints."""

    def _get_test_client(self, db_session: Session):
        """Create a TestClient with a mocked DB dependency."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.database import get_db
        from src.api.routers.evidence import router

        app = FastAPI()
        app.include_router(router)

        def _override_db():
            yield db_session

        app.dependency_overrides[get_db] = _override_db
        return TestClient(app)

    def test_list_empty(self, db):
        """GET /evidence returns empty list initially."""
        client = self._get_test_client(db)
        resp = client.get(f"/evidence?project_id={uuid.uuid4()}")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_with_packages(self, db, project_id, sample_project):
        """GET /evidence returns inserted packages."""
        pkg = EvidencePackageModel(
            id=uuid.uuid4(),
            project_id=uuid.UUID(project_id),
            package_date=date(2025, 6, 1),
            period_start=date(2025, 1, 1),
            period_end=date(2025, 12, 31),
            status="PASS",
            s3_path="packages/test.pdf",
            checksum="abc123",
        )
        db.add(pkg)
        db.commit()

        client = self._get_test_client(db)
        resp = client.get(f"/evidence?project_id={project_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["status"] == "PASS"

    def test_get_by_id(self, db, project_id, sample_project):
        """GET /evidence/{id} returns the package."""
        pkg_id = uuid.uuid4()
        pkg = EvidencePackageModel(
            id=pkg_id,
            project_id=uuid.UUID(project_id),
            package_date=date(2025, 6, 1),
            period_start=date(2025, 1, 1),
            period_end=date(2025, 12, 31),
            status="REVIEW_REQUIRED",
            s3_path="packages/test.pdf",
            checksum="def456",
        )
        db.add(pkg)
        db.commit()

        client = self._get_test_client(db)
        resp = client.get(f"/evidence/{pkg_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "REVIEW_REQUIRED"

    def test_get_not_found(self, db):
        """GET /evidence/{id} returns 404 for missing package."""
        client = self._get_test_client(db)
        fake_id = uuid.uuid4()
        resp = client.get(f"/evidence/{fake_id}")
        assert resp.status_code == 404

    def test_generate_project_not_found(self, db):
        """POST /evidence/{project_id}/generate returns 404 for missing project."""
        client = self._get_test_client(db)
        fake_id = uuid.uuid4()
        resp = client.post(
            f"/evidence/{fake_id}/generate",
            json={"start_date": "2025-01-01", "end_date": "2025-12-31"},
        )
        assert resp.status_code == 404

    @patch("src.evidence_generation.storage_service.EvidenceStorageService")
    def test_generate_success(
        self,
        mock_storage_cls,
        db,
        project_id,
        sample_project,
        sample_jobs,
        sample_observations,
    ):
        """POST /evidence/{project_id}/generate succeeds end-to-end."""
        # Mock storage
        mock_storage = MagicMock()
        mock_storage.upload_package.return_value = {
            "blob_path": "packages/test.pdf",
            "checksum": "abc123",
            "size_bytes": 1024,
            "url": "https://test.blob/packages/test.pdf",
            "uploaded_at": "2025-06-01T00:00:00",
        }
        mock_storage_cls.return_value = mock_storage

        client = self._get_test_client(db)
        resp = client.post(
            f"/evidence/{project_id}/generate",
            json={"start_date": "2025-01-01", "end_date": "2025-12-31"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["project_id"] == project_id
        assert data["growth_classification"] == "growth"
        assert data["confidence_score"] == 87.0
        assert data["blob_path"] == "packages/test.pdf"

    def test_download_not_found(self, db):
        """GET /evidence/{id}/download returns 404 for missing package."""
        client = self._get_test_client(db)
        fake_id = uuid.uuid4()
        resp = client.get(f"/evidence/{fake_id}/download")
        assert resp.status_code == 404


# ──────────────────────────────────────────────────────────────
# Edge Cases & Regression
# ──────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Edge-case and regression tests."""

    def test_duplicate_collection_deduped(self, db, project_id, sample_project):
        """Multiple jobs with same collection produce one DataSource."""
        pid = uuid.UUID(project_id)
        for i in range(3):
            db.add(
                Job(
                    id=uuid.uuid4(),
                    project_id=pid,
                    operation_type="satellite_data_fetch",
                    status="success",
                    input_data={"collection": "COPERNICUS/S2_SR_HARMONIZED"},
                    output_data={},
                    created_at=datetime(2025, 6, 1, 10, i, 0),
                )
            )
        db.commit()

        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        assert len(pkg.data_sources) == 1

    def test_multiple_collections(self, db, project_id, sample_project):
        """Different collections produce separate DataSource entries."""
        pid = uuid.UUID(project_id)
        for coll in ["COPERNICUS/S2_SR_HARMONIZED", "LANDSAT/LC08/C02/T1_L2"]:
            db.add(
                Job(
                    id=uuid.uuid4(),
                    project_id=pid,
                    operation_type="satellite_data_fetch",
                    status="success",
                    input_data={"collection": coll},
                    output_data={},
                    created_at=datetime(2025, 6, 1, 10, 0, 0),
                )
            )
        db.commit()

        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        assert len(pkg.data_sources) == 2
        names = {ds.name for ds in pkg.data_sources}
        assert "Sentinel-2 L2A" in names
        assert "Landsat 8 L2" in names

    def test_failed_job_in_chain(self, db, project_id, sample_project):
        """Failed jobs are included in processing chain with error message."""
        pid = uuid.UUID(project_id)
        db.add(
            Job(
                id=uuid.uuid4(),
                project_id=pid,
                operation_type="satellite_data_fetch",
                status="failed",
                input_data={},
                output_data={},
                error_message="Timeout connecting to GEE",
                execution_time_ms=30000,
                created_at=datetime(2025, 6, 1, 10, 0, 0),
            )
        )
        db.commit()

        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        assert len(pkg.processing_chain) == 1
        assert pkg.processing_chain[0].status == "failed"
        assert "Timeout" in pkg.processing_chain[0].error_message

    def test_low_confidence_review_required(self, db, project_id, sample_project):
        """Low confidence triggers REVIEW_REQUIRED."""
        pid = uuid.UUID(project_id)
        db.add(
            Job(
                id=uuid.uuid4(),
                project_id=pid,
                operation_type="ml_scoring",
                status="success",
                input_data={},
                output_data={"prediction": "stable", "confidence": 0.45},
                created_at=datetime(2025, 6, 1, 10, 0, 0),
            )
        )
        db.commit()

        svc = PackageAssemblyService(db)
        pkg = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        assert pkg.confidence_score == 45.0
        assert pkg.overall_status == "REVIEW_REQUIRED"

    def test_storage_url_format_local(self, tmp_dir, sample_pdf):
        """Local storage URL is a file:// URI."""
        svc = EvidenceStorageService(local_storage_dir=tmp_dir)
        result = svc.upload_package(sample_pdf, "pkg-url")
        assert result["url"].startswith("file://")

    def test_concurrent_packages_different_ids(
        self, db, project_id, sample_project, sample_jobs
    ):
        """Two assemblies produce different package IDs."""
        svc = PackageAssemblyService(db)
        pkg1 = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        pkg2 = svc.assemble_package(project_id, "2025-01-01", "2025-12-31")
        assert pkg1.package_id != pkg2.package_id
