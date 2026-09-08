"""Tests for services.evidence.evidence_engine."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from services.common.phase3_config import Phase3Config
from services.evidence.evidence_engine import EvidenceEngine, EVIDENCE_TYPE_FRAME


def _engine(tmp_path: Path, **overrides) -> EvidenceEngine:
    config = Phase3Config(**overrides)
    return EvidenceEngine(config, base_dir=tmp_path)


class TestEvidenceCreation:
    def test_creates_evidence_with_required_contract_fields(self, tmp_path):
        engine = _engine(tmp_path)
        evidence = engine.create_evidence(camera_id="CAM-1", event_time=100.0, event_id="ev-1", incident_id="inc-1")

        assert evidence.evidence_id
        assert evidence.camera_id == "CAM-1"
        assert evidence.type in ("VIDEO", "FRAME")
        assert evidence.storage_uri

    def test_no_source_path_falls_back_to_frame_manifest(self, tmp_path):
        engine = _engine(tmp_path)
        evidence = engine.create_evidence(camera_id="CAM-1", event_time=100.0)
        assert evidence.type == EVIDENCE_TYPE_FRAME

    def test_missing_source_file_falls_back_gracefully_without_crashing(self, tmp_path):
        engine = _engine(tmp_path)
        evidence = engine.create_evidence(camera_id="CAM-1", event_time=100.0, source_path="/nonexistent/video.mp4")
        assert evidence.type == EVIDENCE_TYPE_FRAME

    def test_missing_camera_id_raises_instead_of_silently_fabricating(self, tmp_path):
        engine = _engine(tmp_path)
        try:
            engine.create_evidence(camera_id="", event_time=100.0)
            assert False, "expected ValueError for missing camera_id"
        except ValueError:
            pass


class TestEvidenceMetadataAndTimestamps:
    def test_manifest_file_is_actually_written_to_disk(self, tmp_path):
        engine = _engine(tmp_path)
        evidence = engine.create_evidence(camera_id="CAM-1", event_time=100.0, event_id="ev-1", incident_id="inc-1")

        manifest_path = tmp_path / f"{evidence.evidence_id}.json"
        assert manifest_path.exists()
        payload = json.loads(manifest_path.read_text())
        assert payload["camera_id"] == "CAM-1"
        assert payload["event_id"] == "ev-1"
        assert payload["incident_id"] == "inc-1"

    def test_pre_and_post_event_window_is_applied(self, tmp_path):
        engine = _engine(tmp_path, evidence_pre_event_seconds=10.0, evidence_post_event_seconds=5.0)
        wc = datetime(2026, 1, 1, 0, 0, 30, tzinfo=timezone.utc)
        evidence = engine.create_evidence(camera_id="CAM-1", event_time=100.0, wall_clock=wc)

        start = datetime.fromisoformat(evidence.start_time)
        end = datetime.fromisoformat(evidence.end_time)
        assert (wc - start).total_seconds() == 10.0
        assert (end - wc).total_seconds() == 5.0

    def test_created_at_is_populated(self, tmp_path):
        engine = _engine(tmp_path)
        evidence = engine.create_evidence(camera_id="CAM-1", event_time=100.0)
        assert evidence.created_at


class TestEvidenceLinkage:
    def test_links_to_event_and_incident_when_provided(self, tmp_path):
        engine = _engine(tmp_path)
        evidence = engine.create_evidence(camera_id="CAM-1", event_time=100.0, event_id="ev-42", incident_id="inc-7")
        assert evidence.event_id == "ev-42"
        assert evidence.incident_id == "inc-7"

    def test_linkage_fields_are_none_when_not_provided(self, tmp_path):
        engine = _engine(tmp_path)
        evidence = engine.create_evidence(camera_id="CAM-1", event_time=100.0)
        assert evidence.event_id is None
        assert evidence.incident_id is None


class TestEvidenceFailureHandling:
    def test_writer_failure_does_not_crash_pipeline(self, tmp_path):
        def _broken_writer(path, payload):
            raise OSError("disk full (simulated)")

        config = Phase3Config()
        engine = EvidenceEngine(config, base_dir=tmp_path, writer=_broken_writer)

        # Must not raise, even though the manifest write itself fails.
        evidence = engine.create_evidence(camera_id="CAM-1", event_time=100.0)
        assert evidence.evidence_id
