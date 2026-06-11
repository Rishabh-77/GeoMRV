"""Assemble audit-ready evidence packages from database records."""

from __future__ import annotations

import logging
import statistics
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd
from sqlalchemy import and_, or_, select
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
_DEFAULT_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
_DEFAULT_URL = (
    "https://developers.google.com/earth-engine/datasets/catalog/"
    "COPERNICUS_S2_SR_HARMONIZED"
)


class PackageAssemblyService:
    """Assemble evidence packages from database records."""

    def __init__(self, db: Session, *, script_version: str = "0.1.0") -> None:
        self.db = db
        self.script_version = script_version

    def assemble_package(
        self,
        project_id: str,
        start_date: str,
        end_date: str,
    ) -> EvidencePackage:
        """Build a sealed evidence package for a project and period."""
        project = self._load_project(project_id)
        if project is None:
            raise ValueError(f"Project not found: {project_id}")

        jobs = self._load_jobs(project_id, start_date, end_date)
        observations = self._load_observations(project_id, start_date, end_date)
        key_features = self._extract_features(jobs, observations)
        verification_results = self._extract_verification(jobs)
        confidence, classification = self._extract_ml_results(jobs)

        package = EvidencePackage(
            package_id=str(uuid.uuid4()),
            project_id=str(project_id),
            project_name=project.name,
            analysis_period_start=start_date,
            analysis_period_end=end_date,
            generated_date=datetime.now(timezone.utc).isoformat(),
            data_sources=self._build_data_sources(jobs, start_date, end_date),
            processing_chain=self._build_processing_chain(jobs),
            key_features=key_features,
            growth_classification=classification,
            confidence_score=confidence,
            verification_results=verification_results,
            analyst="GeoMRV Automated Pipeline",
            methodology_version=self.script_version,
            data_quality_score=self._compute_data_quality(observations, key_features),
            overall_status=self._derive_overall_status(
                verification_results, confidence
            ),
            summary=self._build_summary(
                project.name, classification, confidence, verification_results
            ),
        )
        package.seal()
        return package

    def build_observations_dataframe(
        self,
        project_id: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """Return observation records as a dataframe for report charts."""
        observations = self._load_observations(project_id, start_date, end_date)
        if not observations:
            return pd.DataFrame(columns=["date", "ndvi", "evi", "biomass_estimate"])

        rows = [
            {
                "date": obs.observation_date,
                "ndvi": obs.ndvi,
                "ndvi_std": obs.ndvi_std,
                "evi": obs.evi,
                "biomass_estimate": obs.biomass_estimate,
                "cloud_cover_percent": obs.cloud_cover_percent,
                "data_source": obs.data_source,
            }
            for obs in observations
        ]
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date").reset_index(drop=True)

    def _load_project(self, project_id: str) -> Optional[Project]:
        try:
            return self.db.get(Project, uuid.UUID(project_id))
        except ValueError:
            return None

    def _load_jobs(
        self, project_id: str, start_date: str, end_date: str
    ) -> Sequence[Job]:
        """Fetch processing logs matched to the requested analysis period."""
        try:
            pid = uuid.UUID(project_id)
        except ValueError:
            return []

        period_match = and_(
            or_(
                Job.input_data["start_date"].astext == start_date,
                Job.input_data["period_start"].astext == start_date,
            ),
            or_(
                Job.input_data["end_date"].astext == end_date,
                Job.input_data["period_end"].astext == end_date,
            ),
        )
        rows = list(
            self.db.execute(
                select(Job)
                .where(Job.project_id == pid)
                .where(period_match)
                .order_by(Job.created_at)
            )
            .scalars()
            .all()
        )
        if rows:
            return rows

        fallback_rows = list(
            self.db.execute(
                select(Job).where(Job.project_id == pid).order_by(Job.created_at)
            )
            .scalars()
            .all()
        )
        latest_by_operation: dict[str, Job] = {}
        for row in fallback_rows:
            latest_by_operation[row.operation_type or "unknown"] = row
        return list(latest_by_operation.values())

    def _load_observations(
        self, project_id: str, start_date: str, end_date: str
    ) -> Sequence[Observation]:
        try:
            pid = uuid.UUID(project_id)
        except ValueError:
            return []

        stmt = (
            select(Observation)
            .where(
                and_(
                    Observation.project_id == pid,
                    Observation.observation_date >= _parse_date(start_date),
                    Observation.observation_date <= _parse_date(end_date),
                )
            )
            .order_by(Observation.observation_date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def _build_processing_chain(self, jobs: Sequence[Job]) -> List[ProcessingStep]:
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
        seen_collections: set[str] = set()
        sources: List[DataSource] = []
        for job in jobs:
            input_data = job.input_data or {}
            collection = input_data.get("collection")
            if not collection and input_data.get("source") == "Sentinel-2":
                collection = _DEFAULT_COLLECTION
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
        return sources or [
            DataSource(
                name="Sentinel-2 L2A",
                platform="ESA Copernicus",
                collection=_DEFAULT_COLLECTION,
                access_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                url=_DEFAULT_URL,
                spatial_resolution_m=10.0,
                temporal_range_start=start_date,
                temporal_range_end=end_date,
            )
        ]

    def _extract_features(
        self, jobs: Sequence[Job], observations: Sequence[Observation]
    ) -> List[Feature]:
        features: List[Feature] = []
        feat_job = _find_job(jobs, "feature_extraction")
        if feat_job and feat_job.output_data:
            features.extend(self._features_from_feature_job(feat_job.output_data))

        if not features and observations:
            ndvi_values = [o.ndvi for o in observations if o.ndvi is not None]
            if ndvi_values:
                uncertainty = (
                    statistics.stdev(ndvi_values) if len(ndvi_values) > 1 else 0.0
                )
                features.extend(
                    [
                        Feature(
                            name="ndvi_mean",
                            value=round(statistics.mean(ndvi_values), 4),
                            unit="index",
                            uncertainty=round(uncertainty, 4),
                            source="satellite_data",
                            description="Mean NDVI from raw observations",
                        ),
                        Feature(
                            name="total_observations",
                            value=float(len(ndvi_values)),
                            unit="count",
                            source="satellite_data",
                            description="Number of satellite observations",
                        ),
                    ]
                )
        return features

    @staticmethod
    def _features_from_feature_job(output_data: dict[str, Any]) -> List[Feature]:
        ndvi_stats = output_data.get("ndvi_stats", {})
        trend = output_data.get("trend", {})
        seasonality = output_data.get("seasonality", {})
        biomass = output_data.get("biomass_stats", {})
        specs = [
            ("ndvi_mean", ndvi_stats.get("mean"), "index", "satellite_data"),
            ("ndvi_min", ndvi_stats.get("min"), "index", "satellite_data"),
            ("ndvi_max", ndvi_stats.get("max"), "index", "satellite_data"),
            ("trend_slope", trend.get("trend_slope"), "index/day", "calculation"),
            ("slope_per_year", trend.get("slope_per_year"), "index/year", "calculation"),
            (
                "seasonal_amplitude",
                seasonality.get("seasonal_amplitude"),
                "index",
                "calculation",
            ),
            ("biomass_mean", biomass.get("mean"), "t/ha", "ml_model"),
            (
                "total_observations",
                output_data.get("total_observations"),
                "count",
                "satellite_data",
            ),
        ]
        features: List[Feature] = []
        for name, value, unit, source in specs:
            if value is not None:
                features.append(
                    Feature(
                        name=name,
                        value=float(value),
                        unit=unit,
                        uncertainty=(
                            float(ndvi_stats.get("std", 0))
                            if name == "ndvi_mean"
                            else 0.0
                        ),
                        source=source,
                        description=name.replace("_", " ").title(),
                    )
                )
        return features

    def _extract_verification(self, jobs: Sequence[Job]) -> List[VerificationResult]:
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
                    rule_name=flag.get("rule_name", flag.get("name", "")),
                    status=(
                        "critical"
                        if risk == "critical"
                        else "flag" if risk in ("high", "medium") else "pass"
                    ),
                    risk_level=risk,
                    description=flag.get("description", ""),
                    recommendation=flag.get(
                        "recommended_action", flag.get("recommendation", "Review flag")
                    ),
                )
            )

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
        """Return confidence and growth classification from ML output."""
        ml_job = _find_job(jobs, "ml_scoring")
        if not ml_job or not ml_job.output_data:
            return 50.0, "stable"

        output_data = ml_job.output_data
        growth = (
            output_data.get("growth")
            if isinstance(output_data.get("growth"), dict)
            else {}
        )
        raw_confidence = growth.get(
            "confidence",
            output_data.get("confidence", output_data.get("confidence_score", 50)),
        )
        classification = growth.get(
            "prediction",
            output_data.get(
                "prediction",
                output_data.get("growth_classification", "stable"),
            ),
        )
        if classification not in EvidencePackage.VALID_CLASSIFICATIONS:
            classification = "stable"
        return round(_normalise_confidence(raw_confidence), 2), classification

    @staticmethod
    def _compute_data_quality(
        observations: Sequence[Observation], features: List[Feature]
    ) -> float:
        score = 50.0
        if not observations:
            return score
        score += min(len(observations) / 5, 20)
        cloud_vals = [
            o.cloud_cover_percent
            for o in observations
            if o.cloud_cover_percent is not None
        ]
        if cloud_vals:
            score += max(0, 15 - (sum(cloud_vals) / len(cloud_vals)) / 5)
        score += min(len(features) * 2, 15)
        return round(min(score, 100.0), 2)

    @staticmethod
    def _derive_overall_status(
        verification_results: List[VerificationResult], confidence: float
    ) -> str:
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
        n_flags = sum(1 for v in verification_results if v.status != "pass")
        flag_text = (
            f"{n_flags} verification flag(s) require attention."
            if n_flags
            else "No verification flags were raised."
        )
        return (
            f"Analysis of project '{project_name}' indicates a '{classification}' "
            f"classification with {confidence:.1f}% confidence. {flag_text}"
        )


def _find_job(jobs: Sequence[Job], operation_type: str) -> Optional[Job]:
    match: Optional[Job] = None
    for job in jobs:
        if job.operation_type == operation_type:
            match = job
    return match


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _normalise_confidence(value: Any) -> float:
    if not isinstance(value, (int, float)):
        return 50.0
    confidence = float(value)
    if confidence <= 1.0:
        confidence *= 100.0
    return max(0.0, min(100.0, confidence))
