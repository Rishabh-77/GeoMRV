"""
GeoMRV Evidence Package Schema
================================
Audit-ready evidence package data structures.

Defines the complete schema for evidence packages used in carbon credit
verification. Each package captures:

- **Data sources** – which satellite collections were used and when
- **Processing chain** – every step from raw data to final output
- **Key features** – extracted metrics with units and uncertainty
- **Verification results** – deterministic rule outcomes
- **Metadata** – analyst, methodology version, quality scores

All dataclasses support JSON serialisation via ``to_dict()`` / ``to_json()``
and can be round-tripped through ``from_dict()`` / ``from_json()``.

Usage
-----
    from src.evidence_generation.package_schema import (
        EvidencePackage, DataSource, ProcessingStep,
        VerificationResult, Feature,
    )

    pkg = EvidencePackage(
        package_id="uuid-here",
        project_id="project-uuid",
        project_name="Western Ghats Restoration",
        analysis_period_start="2025-01-01",
        analysis_period_end="2025-12-31",
        generated_date="2026-03-01T12:00:00",
        data_sources=[...],
        processing_chain=[...],
        key_features=[...],
        growth_classification="growth",
        confidence_score=85.0,
        verification_results=[...],
        analyst="GeoMRV Automated Pipeline",
        methodology_version="1.0.0",
        data_quality_score=92.5,
    )

    json_str = pkg.to_json()
    restored = EvidencePackage.from_json(json_str)
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ──────────────────────────────────────────────────────────────
# Supporting dataclasses
# ──────────────────────────────────────────────────────────────


@dataclass
class DataSource:
    """A satellite or ancillary data source used in the analysis.

    Attributes
    ----------
    name : str
        Human-readable name (e.g. "Sentinel-2", "Landsat 8").
    platform : str
        Operator or programme (e.g. "ESA", "USGS", "GEE").
    collection : str
        Collection identifier (e.g. "COPERNICUS/S2_SR_HARMONIZED").
    access_date : str
        ISO-8601 date when the data was accessed / downloaded.
    url : str
        Reference URL or catalogue link to the original data.
    spatial_resolution_m : float
        Native spatial resolution in metres (e.g. 10.0 for Sentinel-2).
    temporal_range_start : str
        Earliest observation date included from this source.
    temporal_range_end : str
        Latest observation date included from this source.
    """

    name: str
    platform: str
    collection: str
    access_date: str
    url: str
    spatial_resolution_m: float = 10.0
    temporal_range_start: str = ""
    temporal_range_end: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DataSource":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ProcessingStep:
    """A single step in the processing chain (lineage).

    Attributes
    ----------
    sequence : int
        1-based order in the pipeline.
    operation : str
        Operation name (e.g. "satellite_data_fetch", "feature_extraction",
        "ml_scoring", "verification").
    timestamp : str
        ISO-8601 timestamp when this step executed.
    script_version : str
        Version or git hash of the code that ran this step.
    parameters : Dict
        Input parameters used (e.g. cloud cover threshold, date range).
    inputs : Dict
        Description of input data (e.g. observation count, project_id).
    outputs : Dict
        Summary of outputs produced (e.g. feature count, model version).
    duration_ms : int
        Wall-clock execution time in milliseconds.
    status : str
        Outcome: ``"success"`` or ``"failed"``.
    error_message : str
        Error details if ``status == "failed"``, empty string otherwise.
    """

    sequence: int
    operation: str
    timestamp: str
    script_version: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0
    status: str = "success"
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProcessingStep":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class VerificationResult:
    """Outcome of a single deterministic verification rule.

    Maps to the verification flags produced by
    ``src.verification_rules.rules_engine.VerificationRulesEngine``.

    Attributes
    ----------
    rule_id : str
        Rule identifier (e.g. "R1", "R3").
    rule_name : str
        Human-readable rule name (e.g. "Insufficient Observations").
    status : str
        Outcome: ``"pass"``, ``"flag"``, or ``"critical"``.
    risk_level : str
        Severity: ``"low"``, ``"medium"``, ``"high"``, ``"critical"``.
    description : str
        Explanation of what was checked and why it triggered (or passed).
    recommendation : str
        Suggested action for the auditor / project developer.
    """

    rule_id: str
    rule_name: str
    status: str  # pass, flag, critical
    risk_level: str  # low, medium, high, critical
    description: str
    recommendation: str

    # Accepted values for validation
    VALID_STATUSES = {"pass", "flag", "critical"}
    VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VerificationResult":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Feature:
    """A single extracted or predicted metric included in the package.

    Attributes
    ----------
    name : str
        Feature name (e.g. "ndvi_mean", "trend_slope", "biomass_estimate").
    value : float
        Numeric value.
    unit : str
        Measurement unit (e.g. "index", "index/day", "t/ha").
    uncertainty : float
        Estimated uncertainty or standard deviation (0.0 if unavailable).
    source : str
        Origin: ``"satellite_data"``, ``"ml_model"``, ``"calculation"``.
    description : str
        Brief human-readable explanation of the feature.
    """

    name: str
    value: float
    unit: str
    uncertainty: float = 0.0
    source: str = "satellite_data"
    description: str = ""

    VALID_SOURCES = {"satellite_data", "ml_model", "calculation", "derived"}

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Feature":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ──────────────────────────────────────────────────────────────
# Main evidence package
# ──────────────────────────────────────────────────────────────


@dataclass
class EvidencePackage:
    """Complete audit-ready evidence package.

    Aggregates every piece of information an auditor needs to
    independently verify a carbon-credit claim for a given project
    and analysis period.

    Attributes
    ----------
    package_id : str
        Unique package identifier (UUID).
    project_id : str
        Associated project UUID.
    project_name : str
        Human-readable project name.
    analysis_period_start : str
        ISO date – start of the analysis window.
    analysis_period_end : str
        ISO date – end of the analysis window.
    generated_date : str
        ISO timestamp when this package was generated.
    data_sources : List[DataSource]
        Satellite / ancillary data sources consumed.
    processing_chain : List[ProcessingStep]
        Ordered lineage of processing steps.
    key_features : List[Feature]
        Extracted / predicted metrics.
    growth_classification : str
        Model output: ``"growth"``, ``"stable"``, or ``"loss"``.
    confidence_score : float
        Overall confidence (0–100) combining ML + verification.
    verification_results : List[VerificationResult]
        Deterministic rule outcomes.
    analyst : str
        Who / what generated this package.
    methodology_version : str
        Version tag of the analysis methodology.
    data_quality_score : float
        Data quality metric (0–100).
    overall_status : str
        Aggregate status: ``"PASS"``, ``"REVIEW_REQUIRED"``, ``"FAIL"``.
    summary : str
        Free-text executive summary of findings.
    checksum : str
        SHA-256 checksum computed over the canonical JSON representation.
    """

    # Required identifiers
    package_id: str
    project_id: str
    project_name: str

    # Analysis window
    analysis_period_start: str
    analysis_period_end: str
    generated_date: str

    # Data lineage
    data_sources: List[DataSource] = field(default_factory=list)
    processing_chain: List[ProcessingStep] = field(default_factory=list)

    # Findings
    key_features: List[Feature] = field(default_factory=list)
    growth_classification: str = "stable"
    confidence_score: float = 0.0

    # Verification
    verification_results: List[VerificationResult] = field(default_factory=list)

    # Metadata
    analyst: str = "GeoMRV Automated Pipeline"
    methodology_version: str = "1.0.0"
    data_quality_score: float = 0.0
    overall_status: str = "REVIEW_REQUIRED"
    summary: str = ""

    # Integrity
    checksum: str = ""

    # Valid values
    VALID_CLASSIFICATIONS = {"growth", "stable", "loss"}
    VALID_STATUSES = {"PASS", "REVIEW_REQUIRED", "FAIL"}

    # ── serialisation ─────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Convert entire package to a plain dict (JSON-safe)."""
        return asdict(self)

    def to_json(self, pretty: bool = True) -> str:
        """Serialise to JSON string.

        Parameters
        ----------
        pretty : bool
            If ``True``, use 2-space indentation. Otherwise compact.
        """
        indent = 2 if pretty else None
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidencePackage":
        """Reconstruct an EvidencePackage from a plain dict.

        Nested lists of ``DataSource``, ``ProcessingStep``,
        ``VerificationResult``, and ``Feature`` are automatically
        deserialised.
        """
        data = dict(data)  # shallow copy to avoid mutating input

        # Deserialise nested objects
        if "data_sources" in data and data["data_sources"]:
            data["data_sources"] = [
                DataSource.from_dict(d) if isinstance(d, dict) else d
                for d in data["data_sources"]
            ]
        if "processing_chain" in data and data["processing_chain"]:
            data["processing_chain"] = [
                ProcessingStep.from_dict(s) if isinstance(s, dict) else s
                for s in data["processing_chain"]
            ]
        if "verification_results" in data and data["verification_results"]:
            data["verification_results"] = [
                VerificationResult.from_dict(v) if isinstance(v, dict) else v
                for v in data["verification_results"]
            ]
        if "key_features" in data and data["key_features"]:
            data["key_features"] = [
                Feature.from_dict(f) if isinstance(f, dict) else f
                for f in data["key_features"]
            ]

        # Filter to only valid fields
        valid_fields = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    @classmethod
    def from_json(cls, json_str: str) -> "EvidencePackage":
        """Deserialise from a JSON string."""
        return cls.from_dict(json.loads(json_str))

    # ── integrity ─────────────────────────────────────────────

    def compute_checksum(self) -> str:
        """Compute SHA-256 checksum of the canonical JSON (excl. checksum field).

        The checksum is calculated over the JSON representation with
        the ``checksum`` field set to an empty string to avoid circular
        dependency.
        """
        # Build a copy without the existing checksum
        data = self.to_dict()
        data["checksum"] = ""
        canonical = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def seal(self) -> "EvidencePackage":
        """Compute and set the checksum, returning self for chaining."""
        self.checksum = self.compute_checksum()
        return self

    def verify_integrity(self) -> bool:
        """Verify that the current checksum matches the content.

        Returns ``True`` if the checksum is valid, ``False`` otherwise.
        Returns ``False`` if no checksum has been set.
        """
        if not self.checksum:
            return False
        return self.checksum == self.compute_checksum()

    # ── factory helpers ───────────────────────────────────────

    @staticmethod
    def generate_id() -> str:
        """Generate a new UUID string for ``package_id``."""
        return str(uuid.uuid4())

    @staticmethod
    def timestamp_now() -> str:
        """Return current UTC timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat()

    # ── convenience ───────────────────────────────────────────

    @property
    def flag_count(self) -> int:
        """Number of verification results that are not 'pass'."""
        return sum(1 for v in self.verification_results if v.status != "pass")

    @property
    def critical_flag_count(self) -> int:
        """Number of critical-level verification flags."""
        return sum(
            1
            for v in self.verification_results
            if v.risk_level == "critical"
        )

    @property
    def processing_step_count(self) -> int:
        """Number of recorded processing steps."""
        return len(self.processing_chain)

    @property
    def has_ml_scoring(self) -> bool:
        """Whether ML scoring was part of the processing chain."""
        return any(s.operation == "ml_scoring" for s in self.processing_chain)

    @property
    def has_verification(self) -> bool:
        """Whether verification rules were evaluated."""
        return len(self.verification_results) > 0

    def get_feature_by_name(self, name: str) -> Optional[Feature]:
        """Look up a feature by name. Returns ``None`` if not found."""
        for f in self.key_features:
            if f.name == name:
                return f
        return None

    def __repr__(self) -> str:
        return (
            f"EvidencePackage(id={self.package_id!r}, "
            f"project={self.project_name!r}, "
            f"period={self.analysis_period_start}..{self.analysis_period_end}, "
            f"status={self.overall_status!r}, "
            f"confidence={self.confidence_score})"
        )
