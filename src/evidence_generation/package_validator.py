"""
GeoMRV Evidence Package Validator
===================================
Validates evidence packages for completeness, consistency, and
audit-readiness before they are sealed and stored.

The validator runs a suite of checks grouped into four categories:

1. **Required fields** – identifiers, dates, and metadata must be present.
2. **Data lineage** – at least one data source and one processing step.
3. **Findings** – growth classification, confidence score, and features.
4. **Verification** – rule results must exist; critical flags are warned.

Each check produces zero or more validation **errors** (blocking) or
**warnings** (non-blocking). A package is considered valid only when
the error list is empty.

Usage
-----
    from src.evidence_generation.package_validator import (
        EvidencePackageValidator,
        ValidationReport,
    )

    validator = EvidencePackageValidator()
    report = validator.validate(package)

    if report.is_valid:
        print("Package is ready for sealing")
    else:
        print("Errors:", report.errors)
        print("Warnings:", report.warnings)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.evidence_generation.package_schema import (
    EvidencePackage,
    Feature,
    ProcessingStep,
    VerificationResult,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Validation report
# ──────────────────────────────────────────────────────────────


@dataclass
class ValidationReport:
    """Structured validation output.

    Attributes
    ----------
    errors : List[str]
        Blocking validation failures. Package must not be sealed.
    warnings : List[str]
        Non-blocking issues the auditor should be aware of.
    checked_at : str
        ISO timestamp when validation ran.
    package_id : str
        ID of the package that was validated.
    """

    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    checked_at: str = ""
    package_id: str = ""

    @property
    def is_valid(self) -> bool:
        """``True`` when no blocking errors were found."""
        return len(self.errors) == 0

    @property
    def total_issues(self) -> int:
        return len(self.errors) + len(self.warnings)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
            "checked_at": self.checked_at,
            "package_id": self.package_id,
        }


# ──────────────────────────────────────────────────────────────
# Validator
# ──────────────────────────────────────────────────────────────


class EvidencePackageValidator:
    """Validate an ``EvidencePackage`` for audit-readiness.

    All validation logic lives in discrete ``_check_*`` methods so that
    individual checks can be overridden or extended by subclasses.
    """

    # ── public API ────────────────────────────────────────────

    def validate(self, package: EvidencePackage) -> ValidationReport:
        """Run all validation checks and return a ``ValidationReport``.

        Parameters
        ----------
        package : EvidencePackage
            The evidence package to validate.

        Returns
        -------
        ValidationReport
        """
        report = ValidationReport(
            checked_at=datetime.now(timezone.utc).isoformat(),
            package_id=getattr(package, "package_id", "unknown"),
        )

        self._check_required_identifiers(package, report)
        self._check_analysis_period(package, report)
        self._check_data_sources(package, report)
        self._check_processing_chain(package, report)
        self._check_findings(package, report)
        self._check_verification_results(package, report)
        self._check_metadata(package, report)
        self._check_data_quality(package, report)

        if report.is_valid:
            logger.info(
                "Package %s passed validation (%d warnings)",
                package.package_id,
                len(report.warnings),
            )
        else:
            logger.warning(
                "Package %s failed validation: %d errors, %d warnings",
                package.package_id,
                len(report.errors),
                len(report.warnings),
            )

        return report

    def validate_and_raise(self, package: EvidencePackage) -> ValidationReport:
        """Validate and raise ``ValueError`` if the package is invalid."""
        report = self.validate(package)
        if not report.is_valid:
            raise ValueError(
                f"Evidence package validation failed with {len(report.errors)} "
                f"error(s): {'; '.join(report.errors)}"
            )
        return report

    # ── individual checks ─────────────────────────────────────

    def _check_required_identifiers(
        self, package: EvidencePackage, report: ValidationReport
    ) -> None:
        """Verify package_id, project_id, and project_name are set."""
        if not package.package_id:
            report.errors.append("Missing required field: package_id")
        if not package.project_id:
            report.errors.append("Missing required field: project_id")
        if not package.project_name:
            report.errors.append("Missing required field: project_name")

    def _check_analysis_period(
        self, package: EvidencePackage, report: ValidationReport
    ) -> None:
        """Verify analysis period dates are present and logically ordered."""
        if not package.analysis_period_start:
            report.errors.append("Missing required field: analysis_period_start")
            return
        if not package.analysis_period_end:
            report.errors.append("Missing required field: analysis_period_end")
            return

        # Parse and compare dates
        try:
            start = datetime.fromisoformat(package.analysis_period_start)
            end = datetime.fromisoformat(package.analysis_period_end)
            if end <= start:
                report.errors.append(
                    f"analysis_period_end ({package.analysis_period_end}) must be "
                    f"after analysis_period_start ({package.analysis_period_start})"
                )
            # Warn if period is very short (< 30 days)
            delta_days = (end - start).days
            if delta_days < 30:
                report.warnings.append(
                    f"Analysis period is only {delta_days} days "
                    "(recommended: >= 90 days for reliable trend detection)"
                )
        except ValueError:
            report.errors.append(
                "analysis_period_start/end must be valid ISO-8601 dates"
            )

        if not package.generated_date:
            report.warnings.append("Missing generated_date; will be set on seal")

    def _check_data_sources(
        self, package: EvidencePackage, report: ValidationReport
    ) -> None:
        """At least one data source must be documented."""
        if not package.data_sources or len(package.data_sources) == 0:
            report.errors.append("No data sources documented (at least 1 required)")
            return

        for i, ds in enumerate(package.data_sources):
            if not ds.name:
                report.errors.append(f"Data source [{i}]: missing name")
            if not ds.collection:
                report.warnings.append(
                    f"Data source [{i}] ({ds.name}): missing collection identifier"
                )
            if not ds.access_date:
                report.warnings.append(
                    f"Data source [{i}] ({ds.name}): missing access_date"
                )

    def _check_processing_chain(
        self, package: EvidencePackage, report: ValidationReport
    ) -> None:
        """At least one processing step must be logged."""
        if not package.processing_chain or len(package.processing_chain) == 0:
            report.errors.append(
                "No processing steps logged (at least 1 required for lineage)"
            )
            return

        # Check sequence ordering
        sequences = [s.sequence for s in package.processing_chain]
        if sequences != sorted(sequences):
            report.warnings.append(
                "Processing chain steps are not in ascending sequence order"
            )

        # Check for failed steps
        failed = [s for s in package.processing_chain if s.status == "failed"]
        if failed:
            report.warnings.append(
                f"{len(failed)} processing step(s) have status 'failed'"
            )

        # Verify each step has required fields
        for i, step in enumerate(package.processing_chain):
            if not step.operation:
                report.errors.append(f"Processing step [{i}]: missing operation name")
            if not step.timestamp:
                report.warnings.append(
                    f"Processing step [{i}] ({step.operation}): missing timestamp"
                )

    def _check_findings(
        self, package: EvidencePackage, report: ValidationReport
    ) -> None:
        """Validate growth classification, confidence score, and features."""
        # Growth classification
        if package.growth_classification not in EvidencePackage.VALID_CLASSIFICATIONS:
            report.errors.append(
                f"Invalid growth_classification '{package.growth_classification}'; "
                f"must be one of {EvidencePackage.VALID_CLASSIFICATIONS}"
            )

        # Confidence score range
        if package.confidence_score < 0 or package.confidence_score > 100:
            report.errors.append(
                f"confidence_score ({package.confidence_score}) must be between 0 and 100"
            )

        # Key features
        if not package.key_features or len(package.key_features) == 0:
            report.warnings.append(
                "No key features included (recommended for audit completeness)"
            )
        else:
            for i, feat in enumerate(package.key_features):
                if not feat.name:
                    report.errors.append(f"Feature [{i}]: missing name")
                if not feat.unit:
                    report.warnings.append(f"Feature [{i}] ({feat.name}): missing unit")
                if feat.source and feat.source not in Feature.VALID_SOURCES:
                    report.warnings.append(
                        f"Feature [{i}] ({feat.name}): source '{feat.source}' "
                        f"is not a standard source ({Feature.VALID_SOURCES})"
                    )

    def _check_verification_results(
        self, package: EvidencePackage, report: ValidationReport
    ) -> None:
        """Verify that verification results exist and flag critical issues."""
        if not package.verification_results or len(package.verification_results) == 0:
            report.errors.append(
                "No verification results (deterministic rules must be evaluated)"
            )
            return

        for i, vr in enumerate(package.verification_results):
            if not vr.rule_id:
                report.errors.append(f"Verification result [{i}]: missing rule_id")
            if vr.status and vr.status not in VerificationResult.VALID_STATUSES:
                report.warnings.append(
                    f"Verification result [{i}] ({vr.rule_id}): "
                    f"status '{vr.status}' is not standard"
                )
            if (
                vr.risk_level
                and vr.risk_level not in VerificationResult.VALID_RISK_LEVELS
            ):
                report.warnings.append(
                    f"Verification result [{i}] ({vr.rule_id}): "
                    f"risk_level '{vr.risk_level}' is not standard"
                )

        # Count and warn on critical flags
        critical_flags = [
            v for v in package.verification_results if v.risk_level == "critical"
        ]
        if critical_flags:
            report.warnings.append(
                f"{len(critical_flags)} critical verification flag(s) detected: "
                + ", ".join(f.rule_id for f in critical_flags)
            )

    def _check_metadata(
        self, package: EvidencePackage, report: ValidationReport
    ) -> None:
        """Validate metadata fields."""
        if not package.analyst:
            report.warnings.append("Missing analyst identifier")
        if not package.methodology_version:
            report.warnings.append("Missing methodology_version")
        if package.overall_status not in EvidencePackage.VALID_STATUSES:
            report.errors.append(
                f"Invalid overall_status '{package.overall_status}'; "
                f"must be one of {EvidencePackage.VALID_STATUSES}"
            )

    def _check_data_quality(
        self, package: EvidencePackage, report: ValidationReport
    ) -> None:
        """Validate data quality score range."""
        if package.data_quality_score < 0 or package.data_quality_score > 100:
            report.errors.append(
                f"data_quality_score ({package.data_quality_score}) "
                "must be between 0 and 100"
            )
        elif package.data_quality_score == 0:
            report.warnings.append(
                "data_quality_score is 0.0 (consider computing from observation stats)"
            )
