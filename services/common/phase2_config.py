"""
Project SRT — Phase 2 configuration (context/zones/baseline/anomaly/risk).

Same env-driven pattern as services/common/config.py from Phase 1 — kept as a
separate dataclass rather than merged into PipelineConfig so the two phases'
review diffs stay readable. Merge them by hand if the real repo already has a
single Settings object.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _get_float(name: str, default: float) -> float:
    val = os.getenv(name)
    return float(val) if val else default


def _get_int(name: str, default: int) -> int:
    val = os.getenv(name)
    return int(val) if val else default


@dataclass(frozen=True)
class Phase2Config:
    # --- Zones ---
    dwell_alert_seconds: float = field(default_factory=lambda: _get_float("DWELL_ALERT_SECONDS", 5.0))
    loitering_seconds: float = field(default_factory=lambda: _get_float("LOITERING_SECONDS", 10.0))

    # --- Time buckets (24h clock, local time of the video/camera) ---
    morning_start_hour: int = field(default_factory=lambda: _get_int("MORNING_START_HOUR", 6))
    afternoon_start_hour: int = field(default_factory=lambda: _get_int("AFTERNOON_START_HOUR", 12))
    evening_start_hour: int = field(default_factory=lambda: _get_int("EVENING_START_HOUR", 17))
    night_start_hour: int = field(default_factory=lambda: _get_int("NIGHT_START_HOUR", 21))

    # --- Baseline ---
    min_baseline_samples: int = field(default_factory=lambda: _get_int("MIN_BASELINE_SAMPLES", 20))
    baseline_high_confidence_samples: int = field(
        default_factory=lambda: _get_int("BASELINE_HIGH_CONFIDENCE_SAMPLES", 100)
    )

    # --- Anomaly ---
    anomaly_zscore_threshold: float = field(default_factory=lambda: _get_float("ANOMALY_ZSCORE_THRESHOLD", 2.0))
    anomaly_score_threshold: float = field(default_factory=lambda: _get_float("ANOMALY_SCORE_THRESHOLD", 0.5))
    isolation_forest_min_samples: int = field(
        default_factory=lambda: _get_int("ISOLATION_FOREST_MIN_SAMPLES", 50)
    )
    isolation_forest_contamination: float = field(
        default_factory=lambda: _get_float("ISOLATION_FOREST_CONTAMINATION", 0.05)
    )

    # --- Risk ---
    risk_low_max: float = field(default_factory=lambda: _get_float("RISK_LOW_MAX", 0.29))
    risk_medium_max: float = field(default_factory=lambda: _get_float("RISK_MEDIUM_MAX", 0.59))
    risk_high_max: float = field(default_factory=lambda: _get_float("RISK_HIGH_MAX", 0.79))
    # above risk_high_max => CRITICAL


DEFAULT_PHASE2_CONFIG = Phase2Config()
