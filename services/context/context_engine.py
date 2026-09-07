"""
Project SRT — Context Engine.

Combines Phase 1's TrackedObject + BehaviorObservation with WHERE (camera,
zone) and WHEN (timestamp, time bucket) into a single ContextObservation.
track_id is explicitly NOT an identity — no face recognition, no Re-ID, no
"this is person X" inference (section 6).

Field names are a best-effort match to contracts/context.schema.json — NOT
verified against the real file in this session. Reconcile before merging.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from services.common.phase2_config import Phase2Config


class TimeBucket(str, Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"


def time_bucket_for_hour(hour: int, config: Phase2Config) -> TimeBucket:
    if config.morning_start_hour <= hour < config.afternoon_start_hour:
        return TimeBucket.MORNING
    if config.afternoon_start_hour <= hour < config.evening_start_hour:
        return TimeBucket.AFTERNOON
    if config.evening_start_hour <= hour < config.night_start_hour:
        return TimeBucket.EVENING
    return TimeBucket.NIGHT


@dataclass
class ContextObservation:
    # WHO
    track_id: int
    object_type: str  # "person" | "vehicle" | "animal"

    # WHAT
    behaviors: list[str]

    # WHERE
    camera_id: str
    zone_id: str | None
    zone_type: str | None

    # WHEN
    timestamp: float
    wall_clock_hour: int
    time_bucket: TimeBucket
    day_of_week: int  # 0=Monday .. 6=Sunday

    supporting_features: dict = field(default_factory=dict)


def build_context(
    track_id: int,
    object_type: str,
    behaviors: list[str],
    camera_id: str,
    zone_id: str | None,
    zone_type: str | None,
    timestamp: float,
    config: Phase2Config,
    wall_clock: datetime | None = None,
    supporting_features: dict | None = None,
) -> ContextObservation:
    """
    `timestamp` is the pipeline's stream-relative seconds (as produced by
    Phase 1's VideoSource). `wall_clock` is the actual date/time to bucket
    against — pass the real capture time for a live/RTSP feed, or a
    configured video-start timestamp for a recorded MP4. Defaults to "now"
    (UTC) only as a last resort — that's almost never what you want for a
    recorded demo clip, so pass it explicitly in the real pipeline wiring.
    """
    wc = wall_clock or datetime.now(timezone.utc)
    return ContextObservation(
        track_id=track_id,
        object_type=object_type,
        behaviors=behaviors,
        camera_id=camera_id,
        zone_id=zone_id,
        zone_type=zone_type,
        timestamp=timestamp,
        wall_clock_hour=wc.hour,
        time_bucket=time_bucket_for_hour(wc.hour, config),
        day_of_week=wc.weekday(),
        supporting_features=supporting_features or {},
    )
