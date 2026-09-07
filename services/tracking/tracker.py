"""
Project SRT — object tracking.

Uses Ultralytics' built-in ByteTrack integration (model.track(...,
tracker="bytetrack.yaml")), which performs detection + tracking together in
one call. This is the "simpler, lighter, more reliable in the existing
environment" option per section 9 — a standalone ByteTrack/BoT-SORT package
would duplicate what ultralytics already ships and adds another moving part
for a solo hackathon build. Re-ID and cross-camera matching are explicitly
out of scope for this phase.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import numpy as np

from services.common.config import PipelineConfig
from services.tracking.track_history import TrackHistoryStore, TrackRecord

logger = logging.getLogger(__name__)


@dataclass
class TrackedObject:
    track_id: int
    class_name: str
    confidence: float
    bbox: tuple[float, float, float, float]
    frame_number: int
    timestamp: float


@dataclass
class TrackingResult:
    tracks: list[TrackedObject]
    history: list[TrackRecord]
    inference_latency_s: float
    device_used: str


class Tracker:
    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self._model = None
        self._device = "cpu"
        self.history = TrackHistoryStore(
            max_len=config.track_history_len,
            lost_ttl_frames=config.track_lost_ttl_frames,
        )

    def load(self) -> "Tracker":
        from ultralytics import YOLO
        import torch

        self._device = "cuda" if (self.config.device in ("auto", "cuda") and torch.cuda.is_available()) else "cpu"
        self._model = YOLO(self.config.model_path)
        self._model.to(self._device)
        logger.info("Loaded tracker model %s on device=%s", self.config.model_path, self._device)
        return self

    @property
    def device(self) -> str:
        return self._device

    def track(self, image: np.ndarray, frame_number: int, timestamp: float) -> TrackingResult:
        if self._model is None:
            raise RuntimeError("Tracker.load() must be called before track()")

        allowed = self.config.allowed_classes()
        start = time.perf_counter()
        results = self._model.track(
            image,
            conf=self.config.confidence_threshold,
            device=self._device,
            tracker=self.config.tracker_config,
            persist=True,
            verbose=False,
        )
        latency = time.perf_counter() - start

        tracked: list[TrackedObject] = []
        touched_ids: list[int] = []
        for result in results:
            names = result.names
            boxes = result.boxes
            if boxes is None or boxes.id is None:
                continue  # nothing tracked yet this frame (e.g. track not confirmed)
            for box, track_id in zip(boxes, boxes.id):
                class_name = names[int(box.cls[0])]
                if class_name not in allowed:
                    continue
                tid = int(track_id)
                x1, y1, x2, y2 = (float(v) for v in box.xyxy[0])
                obj = TrackedObject(
                    track_id=tid,
                    class_name=class_name,
                    confidence=float(box.conf[0]),
                    bbox=(x1, y1, x2, y2),
                    frame_number=frame_number,
                    timestamp=timestamp,
                )
                tracked.append(obj)
                self.history.update(tid, class_name, obj.bbox, frame_number, timestamp)
                touched_ids.append(tid)

        self.history.expire(frame_number)
        active_history = [self.history.get(tid) for tid in touched_ids]
        return TrackingResult(
            tracks=tracked,
            history=[h for h in active_history if h is not None],
            inference_latency_s=latency,
            device_used=self._device,
        )
