"""
GeoMRV Verification Rules Engine
=================================
Apply deterministic verification rules to extracted feature sets.

The engine ships with **7** built-in rules:

+----+---------------------------+----------+--------------------------------------------+
| ID | Name                      | Risk     | Description                                |
+----+---------------------------+----------+--------------------------------------------+
| R1 | Insufficient Observations | MEDIUM   | < 12 clear observations in period          |
| R2 | High Cloud Cover          | MEDIUM   | > 40 % avg cloud cover across scenes       |
| R3 | No Growth Detected        | HIGH     | Trend slope ≤ 0 (negative or flat)         |
| R4 | Anomalous Values          | MEDIUM   | ≥ 1 anomalous NDVI dates detected          |
| R5 | Vegetation Loss           | CRITICAL | Large NDVI swing (max − min > 0.5)         |
| R6 | Data Gap                  | MEDIUM   | Longest gap between observations > 60 days |
| R7 | Low Trend Confidence      | MEDIUM   | Trend R² < 0.3 (poor linear fit)           |
+----+---------------------------+----------+--------------------------------------------+

Each rule returns a ``VerificationFlag`` when triggered. The module also
provides a confidence scoring algorithm (0–100) whose details are documented
in the docstring of ``VerificationRulesEngine.get_confidence_score``.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Enums & data classes
# ──────────────────────────────────────────────────────────────


class RiskLevel(str, Enum):
    """Severity of a verification flag."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class VerificationFlag:
    """Single verification finding produced by a rule."""

    rule_id: str
    rule_name: str
    risk_level: RiskLevel
    description: str
    affected_period: str
    recommended_action: str

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dictionary (JSON-safe)."""
        d = asdict(self)
        d["risk_level"] = self.risk_level.value
        return d


# ──────────────────────────────────────────────────────────────
# Rules engine
# ──────────────────────────────────────────────────────────────


class VerificationRulesEngine:
    """Apply deterministic verification rules to extracted features.

    Usage::

        engine = VerificationRulesEngine()
        flags  = engine.verify(features)
        score  = engine.get_confidence_score(features, flags)
        status = engine.get_overall_status(score)
    """

    # Thresholds (class-level so tests can override via subclass)
    MIN_OBSERVATIONS: int = 12
    MAX_AVG_CLOUD_COVER: float = 40.0  # percent
    MAX_DATA_GAP_DAYS: int = 60
    NDVI_SWING_THRESHOLD: float = 0.5
    NDVI_MIN_FOR_LOSS: float = 0.2
    NDVI_MAX_FOR_LOSS: float = 0.7
    MIN_TREND_R_SQUARED: float = 0.3

    def __init__(self) -> None:
        self.rules = self._load_rules()

    # ── Rule definitions ──────────────────────────────────────

    @staticmethod
    def _load_rules() -> Dict[str, Dict[str, Any]]:
        """Return built-in rule metadata.

        In a future phase these could be loaded from a database or config
        file to support per-project rule customisation.
        """
        return {
            "R1_insufficient_data": {
                "name": "Insufficient Observations",
                "description": "Fewer than 12 clear observations in period",
                "risk_level": RiskLevel.MEDIUM,
            },
            "R2_high_cloud_cover": {
                "name": "High Cloud Cover",
                "description": "Average cloud cover exceeds 40 %",
                "risk_level": RiskLevel.MEDIUM,
            },
            "R3_no_growth_detected": {
                "name": "No Growth Detected",
                "description": "Trend slope near zero or negative",
                "risk_level": RiskLevel.HIGH,
            },
            "R4_anomalous_spike": {
                "name": "Anomalous Values",
                "description": "NDVI spike likely due to atmospheric or sensor artifact",
                "risk_level": RiskLevel.MEDIUM,
            },
            "R5_forest_loss": {
                "name": "Vegetation Loss",
                "description": "Significant NDVI decrease detected",
                "risk_level": RiskLevel.CRITICAL,
            },
            "R6_data_gap": {
                "name": "Data Gap",
                "description": "No observations for > 60 days",
                "risk_level": RiskLevel.MEDIUM,
            },
            "R7_low_trend_confidence": {
                "name": "Low Trend Confidence",
                "description": "Trend R² below 0.3 — poor linear fit",
                "risk_level": RiskLevel.MEDIUM,
            },
        }

    # ── Main entry point ──────────────────────────────────────

    def verify(self, features: dict) -> List[VerificationFlag]:
        """Run **all** verification rules on an extracted feature set.

        Parameters
        ----------
        features : dict
            The output of ``PipelineFeatureExtractor.extract_features``.

        Returns
        -------
        list[VerificationFlag]
            Flags raised (empty when everything passes).
        """
        flags: List[VerificationFlag] = []
        period = self._period_label(features)

        self._r1_insufficient_data(features, period, flags)
        self._r2_high_cloud_cover(features, period, flags)
        self._r3_no_growth(features, period, flags)
        self._r4_anomalies(features, period, flags)
        self._r5_vegetation_loss(features, period, flags)
        self._r6_data_gap(features, period, flags)
        self._r7_low_trend_confidence(features, period, flags)

        logger.info("Verification complete: %d flag(s) raised", len(flags))
        return flags

    # ── Individual rules ──────────────────────────────────────

    def _r1_insufficient_data(
        self, features: dict, period: str, flags: List[VerificationFlag]
    ) -> None:
        clear_obs = features.get("clear_observations") or features.get(
            "observation_count", 0
        )
        if clear_obs < self.MIN_OBSERVATIONS:
            flags.append(
                VerificationFlag(
                    rule_id="R1_insufficient_data",
                    rule_name="Insufficient Observations",
                    risk_level=RiskLevel.MEDIUM,
                    description=(
                        f"Only {clear_obs} clear observations found; "
                        f"recommend {self.MIN_OBSERVATIONS}+ per year"
                    ),
                    affected_period=period,
                    recommended_action=(
                        "Extend monitoring period or use fallback Landsat data"
                    ),
                )
            )

    def _r2_high_cloud_cover(
        self, features: dict, period: str, flags: List[VerificationFlag]
    ) -> None:
        total = features.get("total_observations", 0)
        clear = features.get("clear_observations") or features.get(
            "observation_count", 0
        )
        if total > 0:
            rejection_pct = ((total - clear) / total) * 100
            if rejection_pct > self.MAX_AVG_CLOUD_COVER:
                flags.append(
                    VerificationFlag(
                        rule_id="R2_high_cloud_cover",
                        rule_name="High Cloud Cover",
                        risk_level=RiskLevel.MEDIUM,
                        description=(
                            f"{rejection_pct:.1f} % of scenes rejected for cloud cover "
                            f"(threshold {self.MAX_AVG_CLOUD_COVER} %)"
                        ),
                        affected_period=period,
                        recommended_action=(
                            "Supplement with SAR data (Sentinel-1) or extend window"
                        ),
                    )
                )

    def _r3_no_growth(
        self, features: dict, period: str, flags: List[VerificationFlag]
    ) -> None:
        trend = features.get("trend", {})
        slope = trend.get("trend_slope")
        if slope is not None and slope <= 0:
            flags.append(
                VerificationFlag(
                    rule_id="R3_no_growth_detected",
                    rule_name="No Growth Detected",
                    risk_level=RiskLevel.HIGH,
                    description=(
                        f"Trend slope: {slope:.6f} (threshold: > 0)"
                    ),
                    affected_period=period,
                    recommended_action=(
                        "Investigate ground conditions or verify project implementation"
                    ),
                )
            )

    def _r4_anomalies(
        self, features: dict, period: str, flags: List[VerificationFlag]
    ) -> None:
        anomalies = features.get("anomalies", [])
        if len(anomalies) > 0:
            sample = ", ".join(anomalies[:3])
            suffix = "..." if len(anomalies) > 3 else ""
            flags.append(
                VerificationFlag(
                    rule_id="R4_anomalous_spike",
                    rule_name="Anomalous Values Detected",
                    risk_level=RiskLevel.MEDIUM,
                    description=f"Found {len(anomalies)} anomalous observation(s)",
                    affected_period=f"{sample}{suffix}" if anomalies else period,
                    recommended_action=(
                        "Review satellite data quality; may indicate cloud shadows "
                        "or sun glint"
                    ),
                )
            )

    def _r5_vegetation_loss(
        self, features: dict, period: str, flags: List[VerificationFlag]
    ) -> None:
        ndvi = features.get("ndvi_stats", {})
        ndvi_min = ndvi.get("min")
        ndvi_max = ndvi.get("max")
        if ndvi_min is not None and ndvi_max is not None:
            swing = ndvi_max - ndvi_min
            if (
                ndvi_min < self.NDVI_MIN_FOR_LOSS
                and ndvi_max > self.NDVI_MAX_FOR_LOSS
                and swing > self.NDVI_SWING_THRESHOLD
            ):
                flags.append(
                    VerificationFlag(
                        rule_id="R5_forest_loss",
                        rule_name="Vegetation Loss Detected",
                        risk_level=RiskLevel.CRITICAL,
                        description=(
                            f"Large NDVI swing: {swing:.2f} "
                            f"(min={ndvi_min:.2f}, max={ndvi_max:.2f})"
                        ),
                        affected_period=period,
                        recommended_action="Conduct urgent field verification",
                    )
                )

    def _r6_data_gap(
        self, features: dict, period: str, flags: List[VerificationFlag]
    ) -> None:
        gap_days = features.get("max_observation_gap_days")
        if gap_days is not None and gap_days > self.MAX_DATA_GAP_DAYS:
            flags.append(
                VerificationFlag(
                    rule_id="R6_data_gap",
                    rule_name="Data Gap",
                    risk_level=RiskLevel.MEDIUM,
                    description=(
                        f"Longest gap between observations: {gap_days} days "
                        f"(threshold: {self.MAX_DATA_GAP_DAYS} days)"
                    ),
                    affected_period=period,
                    recommended_action=(
                        "Investigate possible seasonal cloud cover or sensor downtime"
                    ),
                )
            )

    def _r7_low_trend_confidence(
        self, features: dict, period: str, flags: List[VerificationFlag]
    ) -> None:
        trend = features.get("trend", {})
        r_sq = trend.get("r_squared")
        if r_sq is not None and r_sq < self.MIN_TREND_R_SQUARED:
            flags.append(
                VerificationFlag(
                    rule_id="R7_low_trend_confidence",
                    rule_name="Low Trend Confidence",
                    risk_level=RiskLevel.MEDIUM,
                    description=(
                        f"Trend R² = {r_sq:.4f} (threshold: ≥ {self.MIN_TREND_R_SQUARED})"
                    ),
                    affected_period=period,
                    recommended_action=(
                        "Increase monitoring frequency or review data filtering"
                    ),
                )
            )

    # ── Confidence scoring ────────────────────────────────────

    def get_confidence_score(
        self,
        features: dict,
        flags: List[VerificationFlag],
    ) -> float:
        """Calculate a confidence score (0–100) for the verification run.

        Scoring algorithm
        -----------------
        1. Start at 100.
        2. Deduct 2 pts per missing observation below 12.
        3. Deduct up to 25 pts for low R² (linear interpolation 0→0.5).
        4. Deduct a penalty per flag based on its risk level:
            - LOW      → −5
            - MEDIUM   → −15
            - HIGH     → −30
            - CRITICAL → −50
        5. Clamp to [0, 100].

        Parameters
        ----------
        features : dict
            Extracted feature set.
        flags : list[VerificationFlag]
            Flags produced by ``verify``.

        Returns
        -------
        float  – score in range [0, 100].
        """
        score = 100.0

        # 1. Observation penalty
        clear_obs = features.get("clear_observations") or features.get(
            "observation_count", 0
        )
        if clear_obs < 12:
            score -= (12 - clear_obs) * 2

        # 2. Trend quality penalty
        trend = features.get("trend", {})
        r_squared = trend.get("r_squared", 0)
        if r_squared < 0.5:
            score -= (0.5 - r_squared) * 50  # max −25 pts

        # 3. Per-flag penalty
        penalties = {
            RiskLevel.LOW: 5,
            RiskLevel.MEDIUM: 15,
            RiskLevel.HIGH: 30,
            RiskLevel.CRITICAL: 50,
        }
        for flag in flags:
            score -= penalties.get(flag.risk_level, 0)

        return round(max(0.0, min(100.0, score)), 2)

    # ── Overall status ────────────────────────────────────────

    @staticmethod
    def get_overall_status(confidence_score: float) -> str:
        """Map a confidence score to a human-readable status.

        * **PASS**            – score ≥ 70
        * **REVIEW_REQUIRED** – 40 ≤ score < 70
        * **FAIL**            – score < 40

        Returns
        -------
        str – one of ``"PASS"``, ``"REVIEW_REQUIRED"``, ``"FAIL"``.
        """
        if confidence_score >= 70:
            return "PASS"
        if confidence_score >= 40:
            return "REVIEW_REQUIRED"
        return "FAIL"

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _period_label(features: dict) -> str:
        start = features.get("period_start", "?")
        end = features.get("period_end", "?")
        return f"{start} to {end}"
