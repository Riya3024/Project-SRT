"""
Project SRT — bounded track history.

Stores a fixed-length rolling window of positions/timestamps per track_id so
memory does not grow unbounded over a long-running stream (section 10/17).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class TrackSample:
    frame_number: int
    timestamp: float
    bbox: tuple[float, float, float, float]
    center: tuple[float, float]


@dataclass
class TrackRecord:
    track_id: int
    class_name: str
    samples: deque[TrackSample] = field(default_factory=deque)
    first_seen: float = 0.0
    last_seen: float = 0.0
    last_frame_seen: int = 0


class TrackHistoryStore:
    def __init__(self, max_len: int = 90, lost_ttl_frames: int = 30) -> None:
        self.max_len = max_len
        self.lost_ttl_frames = lost_ttl_frames
        self._tracks: dict[int, TrackRecord] = {}

    def update(
        self,
        track_id: int,
        class_name: str,
        bbox: tuple[float, float, float, float],
        frame_number: int,
        timestamp: float,
    ) -> TrackRecord:
        x1, y1, x2, y2 = bbox
        center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
        record = self._tracks.get(track_id)
        if record is None:
            record = TrackRecord(
                track_id=track_id,
                class_name=class_name,
                samples=deque(maxlen=self.max_len),
                first_seen=timestamp,
            )
            self._tracks[track_id] = record
        record.samples.append(TrackSample(frame_number, timestamp, bbox, center))
        record.last_seen = timestamp
        record.last_frame_seen = frame_number
        return record

    def get(self, track_id: int) -> TrackRecord | None:
        return self._tracks.get(track_id)

    def all_active(self, current_frame: int) -> list[TrackRecord]:
        return [
            r for r in self._tracks.values()
            if current_frame - r.last_frame_seen <= self.lost_ttl_frames
        ]

    def expire(self, current_frame: int) -> list[int]:
        """Drop tracks that have exceeded the lost-track TTL; return their IDs."""
        expired = [
            tid for tid, r in self._tracks.items()
            if current_frame - r.last_frame_seen > self.lost_ttl_frames
        ]
        for tid in expired:
            del self._tracks[tid]
        return expired
