"""
Project SRT — Risk Engine.

Fuses behavior + zone + time + anomaly into a 0..1 risk score, maps it to a
configurable LOW/MEDIUM/HIGH/CRITICAL level, and reports contributors + a
confidence that is explicitly separate from the level (section 26/27) —
e.g. a HIGH risk level can still carry LOW confidence when the underlying
baseline or detections are weak. Never claims criminal intent, identity, or
certainty (section 28).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from services.anomaly_detection.anomaly_engine import AnomalyObservation
from services.common.phase2_config import Phase2Config


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# Behavior labels from Phase 1's BehaviorAnalyzer that contribute risk weight
# when present, beyond whatever the anomaly score already captured.
_BEHAVIOR_RISK_WEIGHTS: dict[str, float] = {
    "running": 0.10,
    "sudden_movement": 0.10,
    "sudden_direction_change": 0.08,
    "possible_loitering": 0.10,
    "possible_fall": 0.15,
    "possible_physical_altercation": 0.25,
    "possible_physical_interaction": 0.20,
}

_RESTRICTED_ZONE_WEIGHT = 0.20
_NIGHT_TIME_WEIGHT = 0.10


@dataclass
class RiskObservation:
    track_id: int
    risk_score: float
    risk_level: RiskLevel
    confidence: float
    contributors: list[str]
    timestamp: float


def _level_for_score(score: float, config: Phase2Config) -> RiskLevel:
    if score <= config.risk_low_max:
        return RiskLevel.LOW
    if score <= config.risk_medium_max:
        return RiskLevel.MEDIUM
    if score <= config.risk_high_max:
        return RiskLevel.HIGH
    return RiskLevel.CRITICAL


def compute_risk(
    track_id: int,
    anomaly: AnomalyObservation,
    behaviors: list[str],
    is_restricted_zone: bool,
    is_night_time: bool,
    detection_confidence: float,
    config: Phase2Config,
    timestamp: float,
) -> RiskObservation:
    score = anomaly.anomaly_score
    contributors: list[str] = list(anomaly.reasons)

    for behavior in behaviors:
        weight = _BEHAVIOR_RISK_WEIGHTS.get(behavior)
        if weight:
            score += weight
            contributors.append(f"behavior:{behavior}")

    if is_restricted_zone:
        score += _RESTRICTED_ZONE_WEIGHT
        contributors.append("restricted_zone_presence")

    if is_night_time:
        score += _NIGHT_TIME_WEIGHT
        contributors.append("unusual_night_time_activity")

    score = max(0.0, min(1.0, score))
    level = _level_for_score(score, config)

    # Confidence blends: how reliable was the anomaly/baseline signal, and how
    # confident was the underlying detection/tracking. Both matter — a HIGH
    # risk score built on a shaky baseline or a low-confidence detection
    # should not be reported with high confidence (section 26).
    confidence = min(1.0, max(0.0, (anomaly.confidence + detection_confidence) / 2.0))

    # Deduplicate contributors while preserving order.
    seen: set[str] = set()
    unique_contributors = [c for c in contributors if not (c in seen or seen.add(c))]

    return RiskObservation(
        track_id=track_id,
        risk_score=score,
        risk_level=level,
        confidence=confidence,
        contributors=unique_contributors,
        timestamp=timestamp,
    )
