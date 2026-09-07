"""
Project SRT — Crowd Context.

Just counts people/vehicles/animals per camera/zone at a point in time.
Deliberately does NOT decide anomaly here — "20 people detected" is a raw
feature; only the AnomalyEngine comparing it against its own baseline for
that camera/zone/time_bucket can call it unusual (section 22).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


@dataclass
class CrowdSnapshot:
    camera_id: str
    zone_id: str
    timestamp: float
    person_count: int
    vehicle_count: int
    animal_count: int


def summarize_crowd(
    camera_id: str,
    zone_id: str,
    timestamp: float,
    object_classes_in_zone: list[str],
) -> CrowdSnapshot:
    counts = Counter(object_classes_in_zone)
    vehicle_classes = {"car", "motorcycle", "bus", "truck", "bicycle"}
    animal_classes = {"bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe"}

    return CrowdSnapshot(
        camera_id=camera_id,
        zone_id=zone_id,
        timestamp=timestamp,
        person_count=counts.get("person", 0),
        vehicle_count=sum(counts.get(c, 0) for c in vehicle_classes),
        animal_count=sum(counts.get(c, 0) for c in animal_classes),
    )
