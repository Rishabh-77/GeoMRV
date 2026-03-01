"""
GeoMRV Report Visualizations
===============================
Generate publication-quality charts for evidence reports.

Provides four chart types used by the PDF report generator:

1. **NDVI time-series** – raw observations, smoothed trend, linear fit
2. **Seasonal pattern** – monthly NDVI bar chart with std-dev error bars
3. **Verification summary** – risk-level breakdown of verification flags
4. **Confidence gauge** – semi-circular gauge showing confidence score

All methods return a ``BytesIO`` buffer containing a PNG image that
can be embedded directly into a PDF or saved to disk.

Usage
-----
    from src.evidence_generation.visualizations import ReportVisualizations
    import pandas as pd

    viz = ReportVisualizations()

    # From a DataFrame of observations
    obs_df = pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=24, freq="15D"),
        "ndvi": [0.3 + 0.01*i for i in range(24)],
    })
    buf = viz.create_ndvi_timeseries(obs_df)  # PNG bytes

    # From verification results dicts
    buf = viz.create_verification_summary([
        {"rule_id": "R1", "risk_level": "medium", "status": "flag"},
    ])

    # Confidence gauge
    buf = viz.create_confidence_gauge(82.5)
"""

from __future__ import annotations

import logging
from io import BytesIO
from typing import Any, Dict, List, Optional

import matplotlib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# Use non-interactive backend (safe for headless / CI environments)
matplotlib.use("Agg")

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Colour palette
# ──────────────────────────────────────────────────────────────

_RISK_COLORS: Dict[str, str] = {
    "critical": "#d62728",  # red
    "high": "#ff7f0e",  # orange
    "medium": "#ffbb78",  # light orange
    "low": "#2ca02c",  # green
    "pass": "#90ee90",  # light green
}

_BRAND_BLUE = "#1f4e78"
_BRAND_LIGHT_BLUE = "#2e75b6"


# ──────────────────────────────────────────────────────────────
# Visualizations class
# ──────────────────────────────────────────────────────────────


class ReportVisualizations:
    """Generate charts for GeoMRV evidence reports.

    All charts are returned as ``BytesIO`` buffers containing PNG data
    at 150 DPI.  The class is stateless; a single instance can produce
    any number of charts.
    """

    DPI: int = 150

    def __init__(self) -> None:
        sns.set_style("whitegrid")
        plt.rcParams.update(
            {
                "figure.figsize": (12, 6),
                "font.family": "sans-serif",
                "axes.titleweight": "bold",
            }
        )

    # ── helpers ───────────────────────────────────────────────

    @staticmethod
    def _save_figure(fig: plt.Figure) -> BytesIO:
        """Render *fig* to a PNG ``BytesIO`` and close it."""
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=ReportVisualizations.DPI, bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)
        return buf

    # ── 1. NDVI time-series ───────────────────────────────────

    def create_ndvi_timeseries(
        self,
        observations_df: pd.DataFrame,
        *,
        title: str = "Vegetation Index Time Series (NDVI)",
        show_trend: bool = True,
        show_smooth: bool = True,
    ) -> BytesIO:
        """Plot NDVI time-series with optional smoothed and linear trend lines.

        Parameters
        ----------
        observations_df : pd.DataFrame
            Must contain ``date`` (datetime-like) and ``ndvi`` (float)
            columns.  An optional ``evi`` column will be plotted on a
            secondary axis if present.
        title : str
            Chart title.
        show_trend : bool
            Overlay a linear-regression trend line.
        show_smooth : bool
            Overlay a rolling-mean smoothed curve.

        Returns
        -------
        BytesIO
            PNG image buffer.
        """
        fig, ax = plt.subplots(figsize=(12, 5))

        obs = observations_df.copy()
        obs["date"] = pd.to_datetime(obs["date"])
        obs = obs.sort_values("date")

        # Raw observations
        ax.scatter(
            obs["date"],
            obs["ndvi"],
            alpha=0.6,
            s=40,
            color=_BRAND_LIGHT_BLUE,
            label="Raw NDVI",
            zorder=3,
        )

        # Smoothed trend (rolling mean, window=5 or len//5, whichever is smaller)
        if show_smooth and len(obs) >= 5:
            window = min(5, max(3, len(obs) // 5))
            obs["ndvi_smooth"] = (
                obs["ndvi"].rolling(window=window, center=True, min_periods=1).mean()
            )
            ax.plot(
                obs["date"],
                obs["ndvi_smooth"],
                color="#e74c3c",
                linewidth=2,
                label="Smoothed trend",
            )

        # Linear trend line
        if show_trend and len(obs) >= 2:
            x_num = np.arange(len(obs), dtype=float)
            y = obs["ndvi"].values.astype(float)
            mask = ~np.isnan(y)
            if mask.sum() >= 2:
                coeffs = np.polyfit(x_num[mask], y[mask], 1)
                trend_line = np.polyval(coeffs, x_num)
                ax.plot(
                    obs["date"],
                    trend_line,
                    "g--",
                    linewidth=2,
                    alpha=0.7,
                    label=f"Linear trend (slope={coeffs[0]:.5f}/obs)",
                )

        # Optional EVI on secondary axis
        if "evi" in obs.columns and obs["evi"].notna().any():
            ax2 = ax.twinx()
            ax2.plot(
                obs["date"],
                obs["evi"],
                color="#9b59b6",
                linewidth=1.5,
                alpha=0.6,
                label="EVI",
            )
            ax2.set_ylabel("EVI", fontsize=11, color="#9b59b6")
            ax2.tick_params(axis="y", labelcolor="#9b59b6")

        ax.set_xlabel("Date", fontsize=12)
        ax.set_ylabel("NDVI", fontsize=12)
        ax.set_title(title, fontsize=14, color=_BRAND_BLUE)
        ax.legend(loc="best", fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        fig.autofmt_xdate(rotation=45)
        fig.tight_layout()

        logger.debug("Created NDVI time-series chart (%d points)", len(obs))
        return self._save_figure(fig)

    # ── 2. Seasonal pattern ──────────────────────────────────

    def create_seasonal_pattern(
        self,
        observations_df: pd.DataFrame,
        *,
        title: str = "Seasonal NDVI Pattern",
    ) -> BytesIO:
        """Plot monthly average NDVI with standard-deviation error bars.

        Parameters
        ----------
        observations_df : pd.DataFrame
            Must contain ``date`` and ``ndvi`` columns.

        Returns
        -------
        BytesIO
            PNG image buffer.
        """
        fig, ax = plt.subplots(figsize=(10, 5))

        obs = observations_df.copy()
        obs["date"] = pd.to_datetime(obs["date"])
        obs["month"] = obs["date"].dt.month

        monthly = obs.groupby("month")["ndvi"].agg(["mean", "std"]).reindex(range(1, 13))
        monthly["std"] = monthly["std"].fillna(0)

        months = monthly.index.values
        means = monthly["mean"].values
        stds = monthly["std"].values

        bars = ax.bar(
            months,
            means,
            yerr=stds,
            capsize=4,
            alpha=0.75,
            color="steelblue",
            edgecolor="black",
            linewidth=0.5,
        )

        # Highlight peak and trough
        if not np.all(np.isnan(means)):
            valid_mask = ~np.isnan(means)
            if valid_mask.any():
                peak_idx = np.nanargmax(means)
                trough_idx = np.nanargmin(means)
                bars[peak_idx].set_color("#2ca02c")
                bars[trough_idx].set_color("#d62728")
                ax.annotate(
                    f"Peak: {means[peak_idx]:.3f}",
                    xy=(months[peak_idx], means[peak_idx]),
                    xytext=(0, 10),
                    textcoords="offset points",
                    ha="center",
                    fontsize=8,
                    fontweight="bold",
                )

        month_labels = [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        ]
        ax.set_xticks(range(1, 13))
        ax.set_xticklabels(month_labels)
        ax.set_xlabel("Month", fontsize=12)
        ax.set_ylabel("Mean NDVI", fontsize=12)
        ax.set_title(title, fontsize=14, color=_BRAND_BLUE)
        ax.grid(True, alpha=0.3, axis="y")
        fig.tight_layout()

        logger.debug("Created seasonal pattern chart")
        return self._save_figure(fig)

    # ── 3. Verification summary ──────────────────────────────

    def create_verification_summary(
        self,
        verification_results: List[Dict[str, Any]],
        *,
        title: str = "Verification Rule Outcomes",
    ) -> BytesIO:
        """Plot verification flag counts grouped by risk level.

        Parameters
        ----------
        verification_results : list[dict]
            Each dict must have ``risk_level`` and optionally ``status``.
            Accepts both dicts and ``VerificationResult`` dataclass
            instances (via ``to_dict()``).

        Returns
        -------
        BytesIO
            PNG image buffer.
        """
        fig, ax = plt.subplots(figsize=(10, 5))

        if not verification_results:
            ax.text(
                0.5,
                0.5,
                "No verification flags — all rules passed",
                ha="center",
                va="center",
                fontsize=14,
                color="#2ca02c",
                fontweight="bold",
                transform=ax.transAxes,
            )
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis("off")
            ax.set_title(title, fontsize=14, color=_BRAND_BLUE)
            fig.tight_layout()
            return self._save_figure(fig)

        # Count by risk level
        risk_counts: Dict[str, int] = {}
        for r in verification_results:
            level = r.get("risk_level", "unknown") if isinstance(r, dict) else getattr(r, "risk_level", "unknown")
            risk_counts[level] = risk_counts.get(level, 0) + 1

        # Order: critical → high → medium → low
        order = ["critical", "high", "medium", "low"]
        levels = [l for l in order if l in risk_counts]
        # Add any unexpected levels at the end
        levels += [l for l in risk_counts if l not in order]
        counts = [risk_counts[l] for l in levels]
        bar_colors = [_RISK_COLORS.get(l, "#999999") for l in levels]

        bars = ax.bar(
            levels,
            counts,
            color=bar_colors,
            edgecolor="black",
            alpha=0.85,
            linewidth=0.5,
        )

        # Value labels on bars
        for bar, count in zip(bars, counts):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.1,
                str(count),
                ha="center",
                va="bottom",
                fontweight="bold",
                fontsize=11,
            )

        ax.set_ylabel("Number of Flags", fontsize=12)
        ax.set_xlabel("Risk Level", fontsize=12)
        ax.set_title(title, fontsize=14, color=_BRAND_BLUE)
        ax.grid(True, alpha=0.3, axis="y")

        # Integer y-axis
        max_count = max(counts) if counts else 1
        ax.set_ylim(0, max_count + 1)
        ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))

        fig.tight_layout()
        logger.debug("Created verification summary chart (%d flags)", sum(counts))
        return self._save_figure(fig)

    # ── 4. Confidence gauge ──────────────────────────────────

    def create_confidence_gauge(
        self,
        confidence_score: float,
        *,
        title: str = "",
    ) -> BytesIO:
        """Create a semi-circular gauge for the confidence score (0–100).

        The gauge transitions through red → yellow → green as the
        score increases.

        Parameters
        ----------
        confidence_score : float
            Score between 0 and 100.
        title : str
            Optional override for the chart title.

        Returns
        -------
        BytesIO
            PNG image buffer.
        """
        score = max(0.0, min(100.0, confidence_score))
        fig, ax = plt.subplots(figsize=(8, 5))

        # Draw coloured arc segments (wedge approach)
        n_segments = 100
        angles = np.linspace(180, 0, n_segments + 1)
        for i in range(n_segments):
            color = plt.cm.RdYlGn(i / n_segments)
            wedge = matplotlib.patches.Wedge(
                center=(0.5, 0),
                r=0.45,
                theta1=angles[i + 1],
                theta2=angles[i],
                width=0.12,
                facecolor=color,
                edgecolor="none",
            )
            ax.add_patch(wedge)

        # Draw needle
        needle_angle = np.radians(180 - (score / 100) * 180)
        needle_x = 0.5 + 0.38 * np.cos(needle_angle)
        needle_y = 0.38 * np.sin(needle_angle)
        ax.plot(
            [0.5, needle_x],
            [0, needle_y],
            color="black",
            linewidth=2.5,
            solid_capstyle="round",
        )
        # Needle hub
        hub = matplotlib.patches.Circle((0.5, 0), 0.025, color="black", zorder=5)
        ax.add_patch(hub)

        # Score text
        ax.text(
            0.5,
            -0.08,
            f"{score:.1f}",
            ha="center",
            va="top",
            fontsize=28,
            fontweight="bold",
            color=_BRAND_BLUE,
        )
        ax.text(
            0.5,
            -0.16,
            "Confidence Score",
            ha="center",
            va="top",
            fontsize=12,
            color="#666666",
        )

        # Scale labels
        for val, angle_deg in [(0, 180), (25, 135), (50, 90), (75, 45), (100, 0)]:
            rad = np.radians(angle_deg)
            lx = 0.5 + 0.52 * np.cos(rad)
            ly = 0.52 * np.sin(rad)
            ax.text(lx, ly, str(val), ha="center", va="center", fontsize=9, color="#444444")

        # Status label
        if score >= 70:
            status_text, status_color = "PASS", "#2ca02c"
        elif score >= 40:
            status_text, status_color = "REVIEW REQUIRED", "#ff7f0e"
        else:
            status_text, status_color = "FAIL", "#d62728"

        ax.text(
            0.5,
            -0.24,
            status_text,
            ha="center",
            va="top",
            fontsize=14,
            fontweight="bold",
            color=status_color,
        )

        if title:
            ax.set_title(title, fontsize=14, color=_BRAND_BLUE, pad=15)

        ax.set_xlim(-0.1, 1.1)
        ax.set_ylim(-0.3, 0.6)
        ax.set_aspect("equal")
        ax.axis("off")
        fig.tight_layout()

        logger.debug("Created confidence gauge (score=%.1f)", score)
        return self._save_figure(fig)

    # ── 5. Feature importance bar chart (bonus) ──────────────

    def create_feature_importance(
        self,
        features: List[Dict[str, Any]],
        *,
        title: str = "Key Feature Values",
        max_features: int = 10,
    ) -> BytesIO:
        """Horizontal bar chart of key features sorted by absolute value.

        Parameters
        ----------
        features : list[dict]
            Each dict must have ``name`` and ``value`` keys.
            Optionally ``unit`` for axis label annotation.

        Returns
        -------
        BytesIO
            PNG image buffer.
        """
        fig, ax = plt.subplots(figsize=(10, max(4, len(features) * 0.5 + 1)))

        if not features:
            ax.text(0.5, 0.5, "No features available", ha="center", va="center",
                    fontsize=14, transform=ax.transAxes)
            ax.axis("off")
            fig.tight_layout()
            return self._save_figure(fig)

        # Sort by absolute value, take top N
        sorted_feats = sorted(features, key=lambda f: abs(f.get("value", 0)))
        sorted_feats = sorted_feats[-max_features:]

        names = [f["name"] for f in sorted_feats]
        values = [f["value"] for f in sorted_feats]
        colors = [_BRAND_LIGHT_BLUE if v >= 0 else "#d62728" for v in values]

        ax.barh(names, values, color=colors, edgecolor="black", linewidth=0.3, alpha=0.85)

        # Value labels
        for i, (name, val) in enumerate(zip(names, values)):
            unit = ""
            for f in sorted_feats:
                if f["name"] == name:
                    unit = f.get("unit", "")
                    break
            ax.text(
                val + (max(abs(v) for v in values) * 0.02 * (1 if val >= 0 else -1)),
                i,
                f"{val:.4f} {unit}".strip(),
                va="center",
                fontsize=8,
            )

        ax.set_xlabel("Value", fontsize=11)
        ax.set_title(title, fontsize=14, color=_BRAND_BLUE)
        ax.grid(True, alpha=0.3, axis="x")
        fig.tight_layout()

        logger.debug("Created feature importance chart (%d features)", len(sorted_feats))
        return self._save_figure(fig)
