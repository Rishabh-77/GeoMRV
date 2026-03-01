"""
GeoMRV Evidence Package Assembly
=================================
Assembles audit-ready evidence packages from database records.

Reads ``Project``, ``Job`` (processing_logs), and ``Observation``
rows, then constructs a fully populated
:class:`~src.evidence_generation.package_schema.EvidencePackage`
dataclass ready for PDF generation and storage.

Usage
-----
::

    from sqlalchemy.orm import Session
    from src.evidence_generation.package_assembly import PackageAssemblyService

    service = PackageAssemblyService(db_session)
    package = service.assemble_package(
        project_id="<uuid>",
        start_date="2025-01-01",
        end_date="2025-12-31",
    )
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, time, timezone
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from src.api.models import Job, Observation, Project
from src.evidence_generation.package_schema import (
    DataSource,
    EvidencePackage,
    Feature,
    ProcessingStep,
    VerificationResult,
)

logger = logging.getLogger(__name__)

# ── Mapping helpers ──────────────────────────────────────────

# Recognised data-source collections that may appear in job input_data
_COLLECTION_META: Dict[str, Dict[str, str]] = {
    "COPERNICUS/S2_SR_HARMONIZED": {
        "name": "Sentinel-2 L2A",
        "platform": "ESA Copernicus",
        "url": "https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED",
        "resolution": "10",
    },
    "COPERNICUS/S2": {
        "name": "Sentinel-2",
        "platform": "ESA Copernicus",
        "url": "https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2",
        "resolution": "10",
    },
    "LANDSAT/LC08/C02/T1_L2": {
        "name": "Landsat 8 L2",
        "platform": "USGS",
        "url": "https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LC08_C02_T1_L2",
        "resolution": "30",
    },
    "LANDSAT/LC09/C02/T1_L2": {
        "name": "Landsat 9 L2",
        "platform": "USGS",
        "url": "https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LC09_C02_T1_L2",
        "resolution": "30",
    },
}

_DEFAULT_SOURCE_NAME = "Sentinel-2 L2A"
_DEFAULT_PLATFORM = "ESA Copernicus"
_DEFAULT_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
_DEFAULT_URL = (
    "https://developers.google.com/earth-engine/datasets/catalog/"
    "COPERNICUS_S2_SR_HARMONIZED"
)


# ── Assembly service ─────────────────────────────────────────


class PackageAssemblyService:
    """Assemble evidence packages from database records.

    Parameters
    ----------
    db : sqlalchemy.orm.Session
        Active database session used to query projects, jobs, and
        observations.
    script_version : str
        Version tag embedded in every ``ProcessingStep``.
    """

    def __init__(self, db: Session, *, script_version: str = "0.1.0") -> None:
        self.db = db
        self.script_version = script_version

    # ── public API ────────────────────────────────────────────

    def assemble_package(
        self,
        project_id: str,
        start_date: str,
        end_date: str,
    ) -> EvidencePackage:
        """Build a complete :class:`EvidencePackage` for *project_id*.

        Parameters
        ----------
        project_id : str
            UUID of the project (string form).
        start_date : str
            ISO date – start of the analysis window (inclusive).
        end_date : str
            ISO date – end of the analysis window (inclusive).

        Returns
        -------
        EvidencePackage
            Sealed evidence package (checksum set).

        Raises
        ------
        ValueError
            If the project does not exist.
        """
        project = self._load_project(project_id)
        if project is None:
            raise ValueError(f"Project not found: {project_id}")

        jobs = self._load_jobs(project_id, start_date, end_date)
        observations = self._load_observations(project_id, start_date, end_date)

        processing_steps = self._build_processing_chain(jobs)
        data_sources = self._build_data_sources(jobs, start_date, end_date)
        key_features = self._extract_features(jobs, observations)
        verification_results = self._extract_verification(jobs)
        confidence, classification = self._extract_ml_results(jobs)
        data_quality = self._compute_data_quality(observations, key_features)
        overall_status = self._derive_overall_status(verification_results, confidence)
        summary = self._build_summary(
            project.name, classification, confidence, verification_results
        )

        package = EvidencePackage(
            package_id=str(uuid.uuid4()),
            project_id=str(project_id),
            project_name=project.name,
            analysis_period_start=start_date,
            analysis_period_end=end_date,
            generated_date=datetime.now(timezone.utc).isoformat(),
            data_sources=data_sources,
            processing_chain=processing_steps,
            key_features=key_features,
            growth_classification=classification,
            confidence_score=confidence,
            verification_results=verification_results,
            analyst="GeoMRV Automated Pipeline",
            methodology_version=self.script_version,
            data_quality_score=data_quality,
            overall_status=overall_status,
            summary=summary,
        )

        package.seal()
        logger.info(
            "Assembled evidence package %s for project %s (%s – %s), "
            "%d steps, %d features, %d verifications",
            package.package_id,
            project.name,
            start_date,
            end_date,
            len(processing_steps),
            len(key_features),
            len(verification_results),
        )
        return package

    def build_observations_dataframe(
        self,
        project_id: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """Return observation records as a :class:`pandas.DataFrame`.

        Useful for passing to ``PDFReportGenerator.generate_report()``
        when charts are required.
        """
        observations = self._load_observations(project_id, start_date, end_date)
        if not observations:
            return pd.DataFrame(columns=["date", "ndvi", "evi", "biomass_estimate"])

        rows = []
        for obs in observations:
            rows.append(
                {
                    "date": obs.observation_date,
                    "ndvi": obs.ndvi,
                    "ndvi_std": obs.ndvi_std,
                    "evi": obs.evi,
                    "biomass_estimate": obs.biomass_estimate,
                    "cloud_cover_percent": obs.cloud_cover_percent,
                    "data_source": obs.data_source,
                }
            )
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date").reset_index(drop=True)

    # ── database loaders ──────────────────────────────────────

    def _load_project(self, project_id: str) -> Optional[Project]:
        """Fetch the project row."""
        try:
            pid = uuid.UUID(project_id)
        except ValueError:
            return None
        return self.db.get(Project, pid)

    def _load_jobs(
        self, project_id: str, start_date: str, end_date: str
    ) -> Sequence[Job]:
        """Fetch processing_logs rows for the project in the window."""
        try:
            pid = uuid.UUID(project_id)
        except ValueError:
            return []

        # Job timestamps are datetimes; interpret ISO date inputs as whole-day
        # inclusive bounds in UTC-naive DB time.
        sd = datetime.combine(_parse_date(start_date), time.min)
        ed = datetime.combine(_parse_date(end_date), time.max)

        stmt = (
            select(Job)
            .where(
                and_(
                    Job.project_id == pid,
                    Job.created_at >= sd,
                    Job.created_at <= ed,
                )
            )
            .order_by(Job.created_at)
        )
        return list(self.db.execute(stmt).scalars().all())

    def _load_observations(
        self, project_id: str, start_date: str, end_date: str
    ) -> Sequence[Observation]:
        """Fetch observation rows for the project in the window."""
        try:
            pid = uuid.UUID(project_id)
        except ValueError:
            return []

        sd = _parse_date(start_date)
        ed = _parse_date(end_date)

        stmt = (
            select(Observation)
            .where(
                and_(
                    Observation.project_id == pid,
                    Observation.observation_date >= sd,
                    Observation.observation_date <= ed,
                )
            )
            .order_by(Observation.observation_date)
        )
        return list(self.db.execute(stmt).scalars().all())

    # ── builders ──────────────────────────────────────────────

    def _build_processing_chain(self, jobs: Sequence[Job]) -> List[ProcessingStep]:
        """Convert each :class:`Job` to a :class:`ProcessingStep`."""
        steps: List[ProcessingStep] = []
        for idx, job in enumerate(jobs, 1):
            steps.append(
                ProcessingStep(
                    sequence=idx,
                    operation=job.operation_type or "unknown",
                    timestamp=(
                        job.created_at.isoformat()
                        if job.created_at
                        else datetime.now(timezone.utc).isoformat()
                    ),
                    script_version=self.script_version,
                    parameters=job.input_data or {},
                    inputs={"project_id": str(job.project_id)},
                    outputs=job.output_data or {},
                    duration_ms=job.execution_time_ms or 0,
                    status=job.status or "unknown",
                    error_message=job.error_message or "",
                )
            )
        return steps

    def _build_data_sources(
        self, jobs: Sequence[Job], start_date: str, end_date: str
    ) -> List[DataSource]:
        """Infer data sources from job input_data."""
        seen_collections: set[str] = set()
        sources: List[DataSource] = []

        for job in jobs:
            if not job.input_data:
                continue
            collection = job.input_data.get("collection", "")
            if collection and collection not in seen_collections:
                seen_collections.add(collection)
                meta = _COLLECTION_META.get(collection, {})
                sources.append(
                    DataSource(
                        name=meta.get("name", collection),
                        platform=meta.get("platform", "Unknown"),
                        collection=collection,
                        access_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        url=meta.get("url", ""),
                        spatial_resolution_m=float(meta.get("resolution", 10)),
                        temporal_range_start=start_date,
                        temporal_range_end=end_date,
                    )
                )

        # Fallback: if no collection was found, add a default source
        if not sources:
            sources.append(
                DataSource(
                    name=_DEFAULT_SOURCE_NAME,
                    platform=_DEFAULT_PLATFORM,
                    collection=_DEFAULT_COLLECTION,
                    access_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    url=_DEFAULT_URL,
                    spatial_resolution_m=10.0,
                    temporal_range_start=start_date,
                    temporal_range_end=end_date,
                )
            )

        return sources

    def _extract_features(
        self, jobs: Sequence[Job], observations: Sequence[Observation]
    ) -> List[Feature]:
        """Pull features from the feature_extraction job output_data."""
        features: List[Feature] = []

        # --- from feature_extraction job ---
        feat_job = _find_job(jobs, "feature_extraction")
        if feat_job and feat_job.output_data:
            od = feat_job.output_data

            # NDVI stats
            ndvi_stats = od.get("ndvi_stats", {})
            if ndvi_stats.get("mean") is not None:
                features.append(
                    Feature(
                        name="ndvi_mean",
                        value=float(ndvi_stats["mean"]),
                        unit="index",
                        uncertainty=float(ndvi_stats.get("std", 0)),
                        source="satellite_data",
                        description="Mean NDVI over the analysis period",
                    )
                )
            if ndvi_stats.get("min") is not None:
                features.append(
                    Feature(
                        name="ndvi_min",
                        value=float(ndvi_stats["min"]),
                        unit="index",
                        source="satellite_data",
                        description="Minimum NDVI observed",
                    )
                )
            if ndvi_stats.get("max") is not None:
                features.append(
                    Feature(
                        name="ndvi_max",
                        value=float(ndvi_stats["max"]),
                        unit="index",
                        source="satellite_data",
                        description="Maximum NDVI observed",
                    )
                )

            # Trend
            trend = od.get("trend", {})
            if trend.get("trend_slope") is not None:
                features.append(
                    Feature(
                        name="trend_slope",
                        value=float(trend["trend_slope"]),
                        unit="index/day",
                        uncertainty=0.0,
                        source="calculation",
                        description="Linear trend slope of NDVI time-series",
                    )
                )
            if trend.get("slope_per_year") is not None:
                features.append(
                    Feature(
                        name="slope_per_year",
                        value=float(trend["slope_per_year"]),
                        unit="index/year",
                        source="calculation",
                        description="Annualised NDVI trend slope",
                    )
                )

            # Seasonality
            seas = od.get("seasonality", {})
            if seas.get("seasonal_amplitude") is not None:
                features.append(
                    Feature(
                        name="seasonal_amplitude",
                        value=float(seas["seasonal_amplitude"]),
                        unit="index",
                        source="calculation",
                        description="Seasonal NDVI amplitude (peak – trough)",
                    )
                )

            # Biomass stats
            biomass = od.get("biomass_stats", {})
            if biomass.get("mean") is not None:
                features.append(
                    Feature(
                        name="biomass_mean",
                        value=float(biomass["mean"]),
                        unit="t/ha",
                        uncertainty=float(biomass.get("std", 0)),
                        source="ml_model",
                        description="Mean estimated above-ground biomass",
                    )
                )

            # Observation counts
            total_obs = od.get("total_observations")
            if total_obs is not None:
                features.append(
                    Feature(
                        name="total_observations",
                        value=float(total_obs),
                        unit="count",
                        source="satellite_data",
                        description="Total satellite observations in analysis period",
                    )
                )

        # --- fallback from raw observations ---
        if not features and observations:
            ndvi_values = [o.ndvi for o in observations if o.ndvi is not None]
            if ndvi_values:
                import statistics

                features.append(
                    Feature(
                        name="ndvi_mean",
                        value=round(statistics.mean(ndvi_values), 4),
                        unit="index",
                        uncertainty=round(
                            (
                                statistics.stdev(ndvi_values)
                                if len(ndvi_values) > 1
                                else 0.0
                            ),
                            4,
                        ),
                        source="satellite_data",
                        description="Mean NDVI (from raw observations)",
                    )
                )
                features.append(
                    Feature(
                        name="total_observations",
                        value=float(len(ndvi_values)),
                        unit="count",
                        source="satellite_data",
                        description="Number of satellite observations",
                    )
                )

        return features

    def _extract_verification(self, jobs: Sequence[Job]) -> List[VerificationResult]:
        """Pull verification rule outcomes from the verification job."""
        results: List[VerificationResult] = []
        ver_job = _find_job(jobs, "verification")
        if not ver_job or not ver_job.output_data:
            return results

        flags = ver_job.output_data.get("flags", [])
        for flag in flags:
            risk = flag.get("risk_level", "low")
            results.append(
                VerificationResult(
                    rule_id=flag.get("rule_id", ""),
                    rule_name=flag.get("name", flag.get("rule_name", "")),
                    status=(
                        "critical"
                        if risk == "critical"
                        else "flag" if risk in ("high", "medium") else "pass"
                    ),
                    risk_level=risk,
                    description=flag.get("description", ""),
                    recommendation=flag.get("recommendation", "Review flag"),
                )
            )

        # Also include overall_status / classification if present
        overall = ver_job.output_data.get("overall_status")
        if overall and not results:
            results.append(
                VerificationResult(
                    rule_id="OVERALL",
                    rule_name="Overall Verification",
                    status="pass" if overall == "PASS" else "flag",
                    risk_level="low" if overall == "PASS" else "medium",
                    description=f"Overall verification status: {overall}",
                    recommendation="Review report" if overall != "PASS" else "None",
                )
            )

        return results

    def _extract_ml_results(self, jobs: Sequence[Job]) -> tuple[float, str]:
        """Return (confidence_score, growth_classification) from ML job."""
        ml_job = _find_job(jobs, "ml_scoring")
        if not ml_job or not ml_job.output_data:
            return 50.0, "stable"

        od = ml_job.output_data
        # confidence may be 0-1 or 0-100
        raw_confidence = od.get("confidence", od.get("confidence_score", 50))
        if isinstance(raw_confidence, (int, float)):
            confidence = float(raw_confidence)
            if confidence <= 1.0:
                confidence *= 100.0
        else:
            confidence = 50.0

        classification = od.get("prediction", od.get("growth_classification", "stable"))
        if classification not in EvidencePackage.VALID_CLASSIFICATIONS:
            classification = "stable"

        return round(confidence, 2), classification

    # ── derived metrics ───────────────────────────────────────

    @staticmethod
    def _compute_data_quality(
        observations: Sequence[Observation],
        features: List[Feature],
    ) -> float:
        """Heuristic data-quality score (0–100)."""
        score = 50.0  # baseline

        if not observations:
            return score

        # observation count bonus (up to +20)
        n_obs = len(observations)
        score += min(n_obs / 5, 20)

        # low cloud cover bonus (up to +15)
        cloud_vals = [
            o.cloud_cover_percent
            for o in observations
            if o.cloud_cover_percent is not None
        ]
        if cloud_vals:
            avg_cloud = sum(cloud_vals) / len(cloud_vals)
            score += max(0, 15 - avg_cloud / 5)

        # feature richness bonus (up to +15)
        score += min(len(features) * 2, 15)

        return round(min(score, 100.0), 2)

    @staticmethod
    def _derive_overall_status(
        verification_results: List[VerificationResult],
        confidence: float,
    ) -> str:
        """Derive overall package status from verification + confidence."""
        critical = sum(1 for v in verification_results if v.status == "critical")
        flags = sum(1 for v in verification_results if v.status == "flag")

        if critical > 0:
            return "FAIL"
        if flags > 0 or confidence < 60:
            return "REVIEW_REQUIRED"
        return "PASS"

    @staticmethod
    def _build_summary(
        project_name: str,
        classification: str,
        confidence: float,
        verification_results: List[VerificationResult],
    ) -> str:
        """Generate a free-text executive summary."""
        n_flags = sum(1 for v in verification_results if v.status != "pass")
        flag_text = (
            f"{n_flags} verification flag(s) require attention."
            if n_flags
            else "No verification flags were raised."
        )
        return (
            f"Analysis of project '{project_name}' indicates a "
            f"'{classification}' classification with {confidence:.1f}% "
            f"confidence. {flag_text}"
        )


# ── module-level helpers ──────────────────────────────────────


def _find_job(jobs: Sequence[Job], operation_type: str) -> Optional[Job]:
    """Return the *last* job matching *operation_type* (most recent)."""
    match: Optional[Job] = None
    for job in jobs:
        if job.operation_type == operation_type:
            match = job
    return match


def _parse_date(value: str) -> date:
    """Parse an ISO date string to :class:`datetime.date`."""
    return date.fromisoformat(value)
