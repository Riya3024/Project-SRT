"""
Project SRT — Combined Phase 1 pipeline configuration.

Kept separate from backend/app/config.py because that file's current contents
were not inspected directly (GitHub's web UI didn't expose the raw content in
this session). Reconcile/merge with the existing Settings class by hand before
merging this branch — do not blindly overwrite backend/app/config.py.

All values are environment-driven per Rule 16 / section 20 of the phase spec.
Add these keys to .env.example (with placeholder values) when integrating.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

DeviceOption = Literal["auto", "cpu", "cuda"]


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _get_float(name: str, default: float) -> float:
    val = os.getenv(name)
    return float(val) if val else default


def _get_int(name: str, default: int) -> int:
    val = os.getenv(name)
    return int(val) if val else default


@dataclass(frozen=True)
class PipelineConfig:
    # --- Video ingestion ---
    video_source: str = field(default_factory=lambda: os.getenv("VIDEO_SOURCE", "0"))
    # "0" (or any int-like string) = webcam index; a path/URL = file or RTSP.
    frame_skip: int = field(default_factory=lambda: _get_int("FRAME_SKIP", 0))
    target_fps: float = field(default_factory=lambda: _get_float("TARGET_FPS", 0.0))
    # 0 = process at source FPS, no throttling.
    resize_width: int = field(default_factory=lambda: _get_int("RESIZE_WIDTH", 960))
    resize_height: int = field(default_factory=lambda: _get_int("RESIZE_HEIGHT", 0))
    # 0 = preserve aspect ratio from resize_width.

    # --- Detection ---
    model_path: str = field(default_factory=lambda: os.getenv("MODEL_PATH", "yolov8n.pt"))
    confidence_threshold: float = field(default_factory=lambda: _get_float("CONFIDENCE_THRESHOLD", 0.4))
    device: DeviceOption = field(default_factory=lambda: os.getenv("DEVICE", "auto"))  # type: ignore[assignment]

    # --- Tracking ---
    tracker_config: str = field(default_factory=lambda: os.getenv("TRACKER", "bytetrack.yaml"))
    track_history_len: int = field(default_factory=lambda: _get_int("TRACK_HISTORY_LEN", 90))
    track_lost_ttl_frames: int = field(default_factory=lambda: _get_int("TRACK_LOST_TTL_FRAMES", 30))

    # --- Behavior thresholds (pixels/sec are in *resized-frame* pixel units —
    #     good enough for a hackathon demo; real-world calibration is future work) ---
    running_speed_threshold: float = field(default_factory=lambda: _get_float("RUNNING_SPEED_THRESHOLD", 220.0))
    walking_speed_threshold: float = field(default_factory=lambda: _get_float("WALKING_SPEED_THRESHOLD", 40.0))
    sudden_movement_accel_threshold: float = field(
        default_factory=lambda: _get_float("SUDDEN_MOVEMENT_ACCEL_THRESHOLD", 300.0)
    )
    direction_change_threshold_deg: float = field(
        default_factory=lambda: _get_float("DIRECTION_CHANGE_THRESHOLD_DEG", 60.0)
    )
    stationary_speed_threshold: float = field(default_factory=lambda: _get_float("STATIONARY_SPEED_THRESHOLD", 8.0))
    loitering_dwell_seconds: float = field(default_factory=lambda: _get_float("LOITERING_DWELL_SECONDS", 10.0))
    fall_vertical_ratio_threshold: float = field(
        default_factory=lambda: _get_float("FALL_VERTICAL_RATIO_THRESHOLD", 0.5)
    )
    altercation_proximity_px: float = field(default_factory=lambda: _get_float("ALTERCATION_PROXIMITY_PX", 80.0))
    altercation_closing_speed_px_s: float = field(
        default_factory=lambda: _get_float("ALTERCATION_CLOSING_SPEED_PX_S", 150.0)
    )

    # --- Detector class filter (mapped onto whichever pretrained model is loaded) ---
    person_classes: tuple[str, ...] = ("person",)
    vehicle_classes: tuple[str, ...] = ("car", "motorcycle", "bus", "truck", "bicycle")
    animal_classes: tuple[str, ...] = (
        "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe",
    )

    def allowed_classes(self) -> set[str]:
        return set(self.person_classes) | set(self.vehicle_classes) | set(self.animal_classes)


DEFAULT_CONFIG = PipelineConfig()
