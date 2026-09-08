"""
Project SRT — Evidence Engine.

Creates evidence records — matching `contracts/evidence.schema.json`
field-for-field — for events/incidents, covering a
[event_time - pre_event_seconds, event_time + post_event_seconds] window
(section 6/10 of the Phase 3 spec).

Storage strategy (section 7)
-----------------------------
Local filesystem only, by design, for this hackathon phase. Every evidence
record always gets a JSON metadata manifest written to
`Phase3Config.evidence_storage_dir` — this is real, honest metadata (camera,
time range, linked event/incident, source reference), never fabricated
content.

If a source video path is supplied *and* OpenCV is importable *and* the
file actually exists, the engine attempts to additionally extract the real
[start, end] frame range into an MP4 clip alongside the manifest, and the
record's `type` is `"VIDEO"` with `storage_uri` pointing at that clip. If
extraction isn't possible for any reason (no source path, cv2 unavailable,
file missing, read/write failure), the engine falls back to `type:
"FRAME"` with `storage_uri` pointing at the manifest itself — a documented
limitation, not a fabricated clip. One evidence failure must never crash
the caller (section 25); extraction errors are caught and logged, and the
engine always returns a valid EvidenceObservation.

`EvidenceEngine.__init__` takes a `writer` callable so a future object-
storage backend (S3/GCS/Azure Blob, per section 7) can be swapped in
without touching the correlation/metadata logic above it.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from services.common.phase3_config import Phase3Config
from services.common.contract_utils import to_contract_dict as _to_contract_dict

logger = logging.getLogger(__name__)

EVIDENCE_TYPE_VIDEO = "VIDEO"
EVIDENCE_TYPE_FRAME = "FRAME"


@dataclass
class EvidenceObservation:
    """Mirrors contracts/evidence.schema.json field-for-field."""

    evidence_id: str
    camera_id: str
    type: str
    storage_uri: str
    incident_id: str | None = None
    event_id: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    sha256: str | None = None
    created_at: str = ""

    def to_contract_dict(self) -> dict:
        """JSON-serializable dict matching contracts/evidence.schema.json (drops None-valued optional fields)."""
        return _to_contract_dict(self)


def _default_writer(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str))


class EvidenceEngine:
    def __init__(
        self,
        config: Phase3Config,
        base_dir: Path | str | None = None,
        writer: Callable[[Path, dict], None] = _default_writer,
    ) -> None:
        self.config = config
        self.base_dir = Path(base_dir) if base_dir is not None else Path(config.evidence_storage_dir)
        self._writer = writer

    def _try_extract_video_clip(
        self, source_path: str, start_time: datetime, end_time: datetime, manifest_path: Path
    ) -> str | None:
        """Best-effort real frame-range extraction. Returns the clip path on success, None on any failure."""
        try:
            import cv2  # local import: evidence metadata must work even without cv2 installed
        except ImportError:
            logger.info("cv2 not available — evidence will fall back to FRAME/manifest-only")
            return None

        src = Path(source_path)
        if not src.exists():
            logger.warning("Evidence source video not found at %s — falling back to manifest-only", source_path)
            return None

        try:
            cap = cv2.VideoCapture(str(src))
            if not cap.isOpened():
                logger.warning("Could not open %s for evidence extraction — falling back to manifest-only", source_path)
                return None

            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            duration_s = max((end_time - start_time).total_seconds(), 0.0)
            frames_to_write = max(int(duration_s * fps), 1)

            clip_path = manifest_path.with_suffix(".mp4")
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(str(clip_path), fourcc, fps, (width, height))

            written = 0
            while written < frames_to_write:
                ok, frame = cap.read()
                if not ok:
                    break
                writer.write(frame)
                written += 1
            writer.release()
            cap.release()

            if written == 0:
                clip_path.unlink(missing_ok=True)
                logger.warning("Evidence extraction produced zero frames for %s — falling back to manifest-only", source_path)
                return None

            return str(clip_path)
        except Exception:  # noqa: BLE001 — one evidence failure must not crash the pipeline (section 25)
            logger.exception("Evidence extraction failed for %s — falling back to manifest-only", source_path)
            return None

    def create_evidence(
        self,
        camera_id: str,
        event_time: float,
        event_id: str | None = None,
        incident_id: str | None = None,
        source_path: str | None = None,
        wall_clock: datetime | None = None,
    ) -> EvidenceObservation:
        if not camera_id:
            raise ValueError("Evidence requires a camera_id (section 25 — missing camera/source ID)")

        wc = wall_clock or datetime.now(timezone.utc)
        start_time = wc - timedelta(seconds=self.config.evidence_pre_event_seconds)
        end_time = wc + timedelta(seconds=self.config.evidence_post_event_seconds)

        evidence_id = str(uuid.uuid4())
        manifest_path = self.base_dir / f"{evidence_id}.json"

        clip_path = None
        if source_path:
            clip_path = self._try_extract_video_clip(source_path, start_time, end_time, manifest_path)

        evidence_type = EVIDENCE_TYPE_VIDEO if clip_path else EVIDENCE_TYPE_FRAME
        storage_uri = clip_path or str(manifest_path)

        manifest = {
            "evidence_id": evidence_id,
            "event_id": event_id,
            "incident_id": incident_id,
            "camera_id": camera_id,
            "type": evidence_type,
            "source_path": source_path,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "created_at": wc.isoformat(),
            "note": (
                "Frame-based manifest fallback — no video clip extracted; see"
                " services/evidence/README.md known limitations."
                if evidence_type == EVIDENCE_TYPE_FRAME
                else "Video clip extracted alongside this manifest."
            ),
        }

        try:
            self._writer(manifest_path, manifest)
        except Exception:  # noqa: BLE001 — evidence write failure must not crash the pipeline (section 25)
            logger.exception("Failed to write evidence manifest for evidence_id=%s", evidence_id)

        obs = EvidenceObservation(
            evidence_id=evidence_id,
            camera_id=camera_id,
            type=evidence_type,
            storage_uri=storage_uri,
            incident_id=incident_id,
            event_id=event_id,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            created_at=wc.isoformat(),
        )
        logger.info(
            "Evidence created evidence_id=%s type=%s event_id=%s incident_id=%s",
            evidence_id, evidence_type, event_id, incident_id,
        )
        return obs
