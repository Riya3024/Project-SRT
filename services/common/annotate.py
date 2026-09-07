"""
Project SRT — annotated output for the Phase 1 demo (section 8/19).
"""

from __future__ import annotations

import cv2
import numpy as np

from services.behavior_intelligence.behavior_analyzer import BehaviorObservation
from services.tracking.tracker import TrackedObject

_COLOR_PERSON = (60, 220, 60)
_COLOR_VEHICLE = (60, 160, 255)
_COLOR_ANIMAL = (200, 60, 200)
_COLOR_DEFAULT = (200, 200, 200)

_PERSON_SET = {"person"}
_VEHICLE_SET = {"car", "motorcycle", "bus", "truck", "bicycle"}


def _color_for(class_name: str) -> tuple[int, int, int]:
    if class_name in _PERSON_SET:
        return _COLOR_PERSON
    if class_name in _VEHICLE_SET:
        return _COLOR_VEHICLE
    return _COLOR_ANIMAL if class_name not in _PERSON_SET | _VEHICLE_SET else _COLOR_DEFAULT


def annotate_frame(
    image: np.ndarray,
    tracks: list[TrackedObject],
    behaviors_by_track: dict[int, list[BehaviorObservation]],
    fps: float,
) -> np.ndarray:
    out = image.copy()
    for t in tracks:
        x1, y1, x2, y2 = (int(v) for v in t.bbox)
        color = _color_for(t.class_name)
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        label = f"{t.class_name.upper()} #{t.track_id} {t.confidence:.2f}"
        cv2.putText(out, label, (x1, max(0, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)

        behaviors = behaviors_by_track.get(t.track_id, [])
        for i, b in enumerate(behaviors):
            text = f"{b.behavior} ({b.confidence:.2f})"
            cv2.putText(
                out, text, (x1, y2 + 16 + 16 * i),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255) if "possible" in b.behavior else color,
                1, cv2.LINE_AA,
            )

    cv2.putText(out, f"FPS: {fps:.1f}", (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    return out
