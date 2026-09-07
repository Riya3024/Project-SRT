"""
Project SRT — Anomaly Engine.

Primary method: z-score deviation from the relevant BaselineStats, gated by
baseline confidence (no meaningful z-score with too few samples — section
18). Isolation Forest (scikit-learn) is used only as a secondary signal when
enough samples exist (section 19/20) — it is optional and the engine works
without scikit-learn installed at all.

Crowd count alone is explicitly never treated as an anomaly by this engine —
callers must compare crowd size against its own baseline like any other
feature (section 22); there is no separate "crowd anomaly" shortcut here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from services.baseline.baseline_engine import BaselineKey, BaselineStats, BaselineStore
from services.common.phase2_config import Phase2Config
from services.context.context_engine import TimeBucket


@dataclass
class AnomalyObservation:
    track_id: int
    anomaly_score: float  # 0.0 normal .. 1.0 highly anomalous
    confidence: float  # separate from score — reflects baseline reliability
    reasons: list[str]
    timestamp: float
    supporting_features: dict = field(default_factory=dict)


def _statistical_component(
    feature_name: str,
    value: float,
    stats: BaselineStats | None,
    config: Phase2Config,
) -> tuple[float, float, str | None]:
    """Returns (score_contribution 0..1, confidence 0..1, reason or None)."""
    if stats is None or stats.sample_count < 2:
        return 0.0, 0.0, None  # insufficient baseline -> no statistical claim (section 18)

    z = stats.zscore(value)
    confidence = stats.confidence(config)
    if z is None:
        return 0.0, confidence, None

    if abs(z) < config.anomaly_zscore_threshold:
        return 0.0, confidence, None

    # Normalize |z| beyond the threshold into a 0..1-ish contribution.
    score = min(1.0, (abs(z) - config.anomaly_zscore_threshold) / (config.anomaly_zscore_threshold * 2))
    direction = "above" if z > 0 else "below"
    reason = f"{feature_name} significantly {direction} normal baseline (z={z:.2f})"
    return score, confidence, reason


class AnomalyEngine:
    def __init__(self, baseline_store: BaselineStore, config: Phase2Config) -> None:
        self.baseline_store = baseline_store
        self.config = config
        self._isolation_forest = None  # lazily trained, optional

    def evaluate(
        self,
        track_id: int,
        camera_id: str,
        zone_id: str,
        time_bucket: TimeBucket,
        features: dict[str, float],
        context_flags: list[str],
        timestamp: float,
    ) -> AnomalyObservation:
        """
        `features`: e.g. {"speed_px_s": 260.0, "dwell_seconds": 12.0}
        `context_flags`: pre-computed non-statistical reasons the caller already
            knows about (e.g. "restricted_zone_presence", "night_time_activity") —
            this engine does not invent zone/time judgments itself; it fuses
            whatever the Context/Zone engines already determined (section 23).
        """
        component_scores: list[float] = []
        component_confidences: list[float] = []
        reasons: list[str] = list(context_flags)

        for feature_name, value in features.items():
            key = BaselineKey(camera_id, zone_id, time_bucket, feature_name)
            stats = self.baseline_store.get(key)
            score, confidence, reason = _statistical_component(feature_name, value, stats, self.config)
            if score > 0:
                component_scores.append(score)
                component_confidences.append(confidence)
                if reason:
                    reasons.append(reason)

        # context_flags contribute to the score too, but conservatively — they're
        # qualitative signals (e.g. "in a restricted zone"), not statistical ones.
        if context_flags:
            component_scores.append(min(1.0, 0.25 * len(context_flags)))
            component_confidences.append(0.7)

        if not component_scores:
            return AnomalyObservation(
                track_id=track_id,
                anomaly_score=0.0,
                confidence=0.0,
                reasons=[],
                timestamp=timestamp,
                supporting_features=features,
            )

        # Combine via a capped sum rather than a plain average, so multiple
        # simultaneous weak signals can still add up to a meaningful score
        # (section 21 — "unusual combinations of multiple signals") without
        # letting a single strong one saturate immediately.
        combined_score = min(1.0, sum(component_scores) / max(len(component_scores), 1) + 0.15 * (len(component_scores) - 1))
        combined_confidence = sum(component_confidences) / len(component_confidences)

        return AnomalyObservation(
            track_id=track_id,
            anomaly_score=combined_score,
            confidence=combined_confidence,
            reasons=reasons,
            timestamp=timestamp,
            supporting_features=features,
        )

    def isolation_forest_score(self, feature_matrix: list[list[float]], sample: list[float]) -> float | None:
        """
        Optional secondary ML signal (section 19/20). Returns None if
        scikit-learn isn't installed or there aren't enough samples yet —
        callers should treat None as "no ML signal available", not as zero.
        """
        if len(feature_matrix) < self.config.isolation_forest_min_samples:
            return None
        try:
            from sklearn.ensemble import IsolationForest
        except ImportError:
            return None

        if self._isolation_forest is None:
            self._isolation_forest = IsolationForest(
                contamination=self.config.isolation_forest_contamination,
                random_state=42,
            )
            self._isolation_forest.fit(feature_matrix)

        # decision_function: higher = more normal. Convert to 0..1 anomaly score.
        raw = self._isolation_forest.decision_function([sample])[0]
        return float(max(0.0, min(1.0, 0.5 - raw)))
