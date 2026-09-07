"""
Project SRT — human movement features.

Derives speed, direction, acceleration, direction-change, stationary state,
and dwell duration from a TrackRecord's rolling sample history. All figures
are in pixel space (frame coordinates) / seconds — a hackathon-appropriate
approximation; converting to real-world units needs camera calibration,
which is out of scope here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from services.tracking.track_history import TrackRecord


@dataclass
class MovementFeatures:
    track_id: int
    speed_px_s: float
    direction_deg: float | None  # None if stationary/insufficient motion
    acceleration_px_s2: float
    direction_change_deg: float
    is_stationary: bool
    dwell_seconds: float
    displacement_px: float
    samples_used: int


def _angle_deg(dx: float, dy: float) -> float | None:
    if dx == 0 and dy == 0:
        return None
    return math.degrees(math.atan2(dy, dx)) % 360.0


def _angle_diff_deg(a: float, b: float) -> float:
    diff = abs(a - b) % 360.0
    return min(diff, 360.0 - diff)


def compute_movement_features(
    record: TrackRecord,
    stationary_speed_threshold: float,
) -> MovementFeatures:
    samples = list(record.samples)
    if len(samples) < 2:
        return MovementFeatures(
            track_id=record.track_id,
            speed_px_s=0.0,
            direction_deg=None,
            acceleration_px_s2=0.0,
            direction_change_deg=0.0,
            is_stationary=True,
            dwell_seconds=0.0,
            displacement_px=0.0,
            samples_used=len(samples),
        )

    prev, curr = samples[-2], samples[-1]
    dt = max(curr.timestamp - prev.timestamp, 1e-6)
    dx = curr.center[0] - prev.center[0]
    dy = curr.center[1] - prev.center[1]
    step_dist = math.hypot(dx, dy)
    speed = step_dist / dt
    direction = _angle_deg(dx, dy)

    # Acceleration: compare current speed to the speed of the previous step, if available.
    acceleration = 0.0
    direction_change = 0.0
    if len(samples) >= 3:
        prev2 = samples[-3]
        dt_prev = max(prev.timestamp - prev2.timestamp, 1e-6)
        dx_prev = prev.center[0] - prev2.center[0]
        dy_prev = prev.center[1] - prev2.center[1]
        prev_speed = math.hypot(dx_prev, dy_prev) / dt_prev
        acceleration = (speed - prev_speed) / dt
        prev_direction = _angle_deg(dx_prev, dy_prev)
        if direction is not None and prev_direction is not None:
            direction_change = _angle_diff_deg(direction, prev_direction)

    # Dwell: how long the track has stayed within a small radius of its recent
    # position (a simple stand-in for "hasn't materially moved").
    dwell = 0.0
    anchor = samples[-1].center
    for s in reversed(samples):
        if math.hypot(s.center[0] - anchor[0], s.center[1] - anchor[1]) <= stationary_speed_threshold * 2:
            dwell = samples[-1].timestamp - s.timestamp
        else:
            break

    total_dx = samples[-1].center[0] - samples[0].center[0]
    total_dy = samples[-1].center[1] - samples[0].center[1]
    displacement = math.hypot(total_dx, total_dy)

    return MovementFeatures(
        track_id=record.track_id,
        speed_px_s=speed,
        direction_deg=direction,
        acceleration_px_s2=acceleration,
        direction_change_deg=direction_change,
        is_stationary=speed <= stationary_speed_threshold,
        dwell_seconds=dwell,
        displacement_px=displacement,
        samples_used=len(samples),
    )
