"""
Project SRT — Video ingestion.

A single VideoSource abstraction over cv2.VideoCapture that works identically
for an MP4 file, a webcam index, or an RTSP URL, with frame sampling/skip,
resize, and graceful end-of-stream handling.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Iterator, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class VideoSourceError(RuntimeError):
    """Raised when a video source cannot be opened or read."""


@dataclass
class Frame:
    image: np.ndarray
    frame_number: int
    timestamp: float  # seconds, monotonic from stream start
    source_fps: float
    width: int
    height: int


class VideoSource:
    """
    Opens an MP4 file path, a webcam index (e.g. "0"), or an RTSP URL and
    yields Frame objects. RTSP works out of the box via cv2.VideoCapture — no
    special-casing needed beyond passing the URL through.
    """

    def __init__(
        self,
        source: str,
        frame_skip: int = 0,
        target_fps: float = 0.0,
        resize_width: int = 0,
        resize_height: int = 0,
    ) -> None:
        self._source_arg: str | int = int(source) if source.isdigit() else source
        self.frame_skip = max(0, frame_skip)
        self.target_fps = target_fps
        self.resize_width = resize_width
        self.resize_height = resize_height

        self._cap: Optional[cv2.VideoCapture] = None
        self.source_fps: float = 0.0
        self.width: int = 0
        self.height: int = 0
        self._frame_number = 0
        self._start_time: Optional[float] = None

    def open(self) -> "VideoSource":
        cap = cv2.VideoCapture(self._source_arg)
        if not cap.isOpened():
            raise VideoSourceError(f"Could not open video source: {self._source_arg!r}")
        self._cap = cap
        self.source_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        self.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._frame_number = 0
        self._start_time = time.monotonic()
        logger.info(
            "Opened video source %r (%dx%d @ %.2f fps)",
            self._source_arg, self.width, self.height, self.source_fps,
        )
        return self

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __enter__(self) -> "VideoSource":
        return self.open()

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _resize(self, image: np.ndarray) -> np.ndarray:
        if not self.resize_width:
            return image
        h, w = image.shape[:2]
        target_w = self.resize_width
        target_h = self.resize_height or int(h * (target_w / w))
        return cv2.resize(image, (target_w, target_h), interpolation=cv2.INTER_LINEAR)

    def frames(self) -> Iterator[Frame]:
        """Yield Frame objects until end-of-stream or an unrecoverable read failure."""
        if self._cap is None:
            raise VideoSourceError("VideoSource.open() must be called before frames()")

        min_frame_interval = (1.0 / self.target_fps) if self.target_fps > 0 else 0.0
        next_emit_time = 0.0
        consecutive_failures = 0
        max_consecutive_failures = 10  # tolerate transient RTSP hiccups, then give up

        while True:
            ok, raw = self._cap.read()
            if not ok:
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    logger.info("End of stream (or unrecoverable read failure) at frame %d", self._frame_number)
                    return
                continue
            consecutive_failures = 0

            frame_index = self._frame_number
            self._frame_number += 1

            if self.frame_skip and frame_index % (self.frame_skip + 1) != 0:
                continue

            elapsed = time.monotonic() - (self._start_time or time.monotonic())
            if min_frame_interval and elapsed < next_emit_time:
                continue
            next_emit_time = elapsed + min_frame_interval

            image = self._resize(raw)
            yield Frame(
                image=image,
                frame_number=frame_index,
                timestamp=elapsed,
                source_fps=self.source_fps,
                width=image.shape[1],
                height=image.shape[0],
            )
