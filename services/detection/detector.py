"""
Project SRT — Object detection.

Wraps a pretrained Ultralytics YOLO model. Filters to person/vehicle/animal
classes per the pipeline config. GPU is used automatically when available and
DEVICE="auto"; otherwise falls back to CPU. Nothing here trains a model.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from services.common.config import PipelineConfig

logger = logging.getLogger(__name__)


@dataclass
class Detection:
    class_name: str
    confidence: float
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2 in pixel coords
    frame_number: int
    timestamp: float


@dataclass
class DetectionResult:
    detections: list[Detection]
    inference_latency_s: float
    device_used: str


class Detector:
    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self._model = None
        self._device = "cpu"

    def load(self) -> "Detector":
        # Imported lazily so importing this module doesn't require torch/ultralytics
        # to be installed just to run non-model tests (e.g. movement/behavior tests).
        from ultralytics import YOLO
        import torch

        self._device = "cuda" if (self.config.device in ("auto", "cuda") and torch.cuda.is_available()) else "cpu"
        if self.config.device == "cuda" and self._device == "cpu":
            logger.warning("DEVICE=cuda requested but CUDA is not available — falling back to CPU.")

        self._model = YOLO(self.config.model_path)
        self._model.to(self._device)
        logger.info("Loaded detector %s on device=%s", self.config.model_path, self._device)
        return self

    @property
    def device(self) -> str:
        return self._device

    def detect(self, image: np.ndarray, frame_number: int, timestamp: float) -> DetectionResult:
        if self._model is None:
            raise RuntimeError("Detector.load() must be called before detect()")

        start = time.perf_counter()
        results = self._model.predict(
            image,
            conf=self.config.confidence_threshold,
            device=self._device,
            verbose=False,
        )
        latency = time.perf_counter() - start

        allowed = self.config.allowed_classes()
        detections: list[Detection] = []
        for result in results:
            names = result.names
            for box in result.boxes:
                class_name = names[int(box.cls[0])]
                if class_name not in allowed:
                    continue
                x1, y1, x2, y2 = (float(v) for v in box.xyxy[0])
                detections.append(
                    Detection(
                        class_name=class_name,
                        confidence=float(box.conf[0]),
                        bbox=(x1, y1, x2, y2),
                        frame_number=frame_number,
                        timestamp=timestamp,
                    )
                )
        return DetectionResult(detections=detections, inference_latency_s=latency, device_used=self._device)
