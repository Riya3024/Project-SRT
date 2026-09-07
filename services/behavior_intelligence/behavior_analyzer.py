"""
Project SRT — human behavior intelligence.

Turns per-track MovementFeatures into structured, probabilistic behavior
observations. No claims of criminal intent, identity, or certainty — see
Rule/section 13, 14, 23. This is a lightweight statistical/rule layer, not a
trained action-recognition model (per section 12/17 — pose estimation is
optional future work, not required here).

Field names (track_id, behavior, confidence, timestamp, supporting_features)
follow the example in section 15 of the phase spec. VERIFY these against the
actual contracts/activity.schema.json and contracts/behavior_observation.schema.json
before merging — I was not able to read those two files directly in this
session, so this is a best-effort match, not a confirmed one.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

from services.behavior_intelligence.movement_features import MovementFeatures
from services.common.config import PipelineConfig


@dataclass
class BehaviorObservation:
    track_id: int
    behavior: str
    confidence: float
    timestamp: float
    supporting_features: dict = field(default_factory=dict)


def _clip(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def classify_single_track(
    features: MovementFeatures,
    timestamp: float,
    config: PipelineConfig,
) -> list[BehaviorObservation]:
    """Rule-based single-track classification. May emit zero, one, or several observations."""
    obs: list[BehaviorObservation] = []
    f = features

    if f.samples_used < 2:
        return obs

    # Stationary / loitering
    if f.is_stationary:
        if f.dwell_seconds >= config.loitering_dwell_seconds:
            obs.append(
                BehaviorObservation(
                    track_id=f.track_id,
                    behavior="possible_loitering",
                    confidence=_clip(0.5 + f.dwell_seconds / (config.loitering_dwell_seconds * 4)),
                    timestamp=timestamp,
                    supporting_features={"dwell_seconds": f.dwell_seconds, "speed_px_s": f.speed_px_s},
                )
            )
        else:
            obs.append(
                BehaviorObservation(
                    track_id=f.track_id,
                    behavior="stationary",
                    confidence=0.6,
                    timestamp=timestamp,
                    supporting_features={"dwell_seconds": f.dwell_seconds},
                )
            )
    elif f.speed_px_s >= config.running_speed_threshold:
        obs.append(
            BehaviorObservation(
                track_id=f.track_id,
                behavior="running",
                confidence=_clip(0.5 + (f.speed_px_s - config.running_speed_threshold) / config.running_speed_threshold),
                timestamp=timestamp,
                supporting_features={"speed_px_s": f.speed_px_s, "direction_deg": f.direction_deg},
            )
        )
    elif f.speed_px_s >= config.walking_speed_threshold:
        obs.append(
            BehaviorObservation(
                track_id=f.track_id,
                behavior="walking",
                confidence=0.6,
                timestamp=timestamp,
                supporting_features={"speed_px_s": f.speed_px_s, "direction_deg": f.direction_deg},
            )
        )

    # Sudden movement (large acceleration magnitude)
    if abs(f.acceleration_px_s2) >= config.sudden_movement_accel_threshold:
        obs.append(
            BehaviorObservation(
                track_id=f.track_id,
                behavior="sudden_movement",
                confidence=_clip(0.5 + abs(f.acceleration_px_s2) / (config.sudden_movement_accel_threshold * 3)),
                timestamp=timestamp,
                supporting_features={"acceleration_px_s2": f.acceleration_px_s2},
            )
        )

        # Possible fall: a large downward-dominant sudden acceleration on a
        # previously-moving track. Deliberately conservative language per section 14.
        if f.direction_deg is not None and 45 <= f.direction_deg <= 135:
            obs.append(
                BehaviorObservation(
                    track_id=f.track_id,
                    behavior="possible_fall",
                    confidence=_clip(0.4 + abs(f.acceleration_px_s2) / (config.sudden_movement_accel_threshold * 4)),
                    timestamp=timestamp,
                    supporting_features={
                        "acceleration_px_s2": f.acceleration_px_s2,
                        "direction_deg": f.direction_deg,
                        "note": "requires_operator_review",
                    },
                )
            )

    # Sudden direction change
    if f.direction_change_deg >= config.direction_change_threshold_deg:
        obs.append(
            BehaviorObservation(
                track_id=f.track_id,
                behavior="sudden_direction_change",
                confidence=_clip(0.5 + f.direction_change_deg / 180.0),
                timestamp=timestamp,
                supporting_features={"direction_change_deg": f.direction_change_deg},
            )
        )

    return obs


def detect_possible_altercations(
    person_features: Iterable[MovementFeatures],
    timestamp: float,
    config: PipelineConfig,
) -> list[BehaviorObservation]:
    """
    Pairwise check across currently-tracked people: rapid closing distance +
    elevated speed on both tracks. Explicitly probabilistic (section 13) —
    never asserts a fight, an attacker, or criminal intent.
    """
    feats = list(person_features)
    obs: list[BehaviorObservation] = []
    for i in range(len(feats)):
        for j in range(i + 1, len(feats)):
            a, b = feats[i], feats[j]
            if a.samples_used < 2 or b.samples_used < 2:
                continue
            fast_enough = (
                a.speed_px_s >= config.walking_speed_threshold
                and b.speed_px_s >= config.walking_speed_threshold
            )
            if not fast_enough:
                continue
            # We don't have both tracks' live positions here (features only),
            # so this check is intentionally shallow: flag as a joint
            # "requires closer proximity check" indicator when both tracks
            # show simultaneous sudden movement. Real proximity distance
            # should be computed by the caller (which has both bboxes) and
            # passed in — see run_phase1_demo.py for the fuller version.
            if a.acceleration_px_s2 >= config.sudden_movement_accel_threshold / 2 and \
               b.acceleration_px_s2 >= config.sudden_movement_accel_threshold / 2:
                obs.append(
                    BehaviorObservation(
                        track_id=a.track_id,
                        behavior="possible_physical_interaction",
                        confidence=0.4,
                        timestamp=timestamp,
                        supporting_features={
                            "other_track_id": b.track_id,
                            "note": "sudden_reciprocal_motion_requires_operator_review",
                        },
                    )
                )
    return obs
