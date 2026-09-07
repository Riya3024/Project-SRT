"""
Project SRT — Zone Engine.

Polygon zones (NORMAL / RESTRICTED at minimum), bottom-center-of-bbox
membership testing (better ground-position approximation than bbox center
per section 9), and per-track entry/exit/dwell state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ZoneType(str, Enum):
    NORMAL = "normal"
    RESTRICTED = "restricted"


@dataclass
class Zone:
    zone_id: str
    camera_id: str
    name: str
    polygon: list[tuple[float, float]]  # image-coordinate points, in order
    zone_type: ZoneType = ZoneType.NORMAL
    enabled: bool = True

    def contains_point(self, x: float, y: float) -> bool:
        """Standard ray-casting point-in-polygon test."""
        if not self.enabled or len(self.polygon) < 3:
            return False
        inside = False
        n = len(self.polygon)
        j = n - 1
        for i in range(n):
            xi, yi = self.polygon[i]
            xj, yj = self.polygon[j]
            intersects = ((yi > y) != (yj > y)) and (
                x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi
            )
            if intersects:
                inside = not inside
            j = i
        return inside


def bottom_center(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2.0, y2)


@dataclass
class ZoneMembershipEvent:
    track_id: int
    zone_id: str
    event_type: str  # "entered" | "exited" | "inside" | "outside"
    timestamp: float
    dwell_seconds: float = 0.0


@dataclass
class _TrackZoneState:
    zone_id: str | None = None
    entry_timestamp: float | None = None


class ZoneEngine:
    def __init__(self, zones: list[Zone]) -> None:
        self.zones = zones
        self._state: dict[int, _TrackZoneState] = {}

    def zone_for_point(self, x: float, y: float) -> Zone | None:
        # First match wins; overlapping zones aren't resolved further (out of
        # scope for a hackathon build — document if you add overlapping zones).
        for zone in self.zones:
            if zone.contains_point(x, y):
                return zone
        return None

    def update(
        self,
        track_id: int,
        bbox: tuple[float, float, float, float],
        timestamp: float,
    ) -> ZoneMembershipEvent:
        x, y = bottom_center(bbox)
        current_zone = self.zone_for_point(x, y)
        state = self._state.setdefault(track_id, _TrackZoneState())

        if current_zone is None:
            if state.zone_id is not None:
                # was inside a zone, now outside -> exited
                event = ZoneMembershipEvent(track_id, state.zone_id, "exited", timestamp)
                state.zone_id = None
                state.entry_timestamp = None
                return event
            return ZoneMembershipEvent(track_id, "", "outside", timestamp)

        if state.zone_id != current_zone.zone_id:
            # entering a new zone (possibly from another zone directly)
            state.zone_id = current_zone.zone_id
            state.entry_timestamp = timestamp
            return ZoneMembershipEvent(track_id, current_zone.zone_id, "entered", timestamp)

        dwell = timestamp - (state.entry_timestamp if state.entry_timestamp is not None else timestamp)
        return ZoneMembershipEvent(track_id, current_zone.zone_id, "inside", timestamp, dwell_seconds=dwell)

    def dwell_seconds(self, track_id: int, timestamp: float) -> float:
        state = self._state.get(track_id)
        if state is None or state.entry_timestamp is None:
            return 0.0
        return max(0.0, timestamp - state.entry_timestamp)

    def clear_track(self, track_id: int) -> None:
        self._state.pop(track_id, None)
