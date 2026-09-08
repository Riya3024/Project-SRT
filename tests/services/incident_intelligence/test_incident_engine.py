"""Tests for services.incident_intelligence.incident_engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.common.phase3_config import Phase3Config
from services.incident_intelligence.event_engine import EventObservation
from services.incident_intelligence.incident_engine import IncidentEngine


def _event(event_id="ev-1", camera_id="CAM-1", track_ids=None, event_type="sudden_movement", risk_level="HIGH", confidence=0.7, status="CONFIRMED") -> EventObservation:
    return EventObservation(
        event_id=event_id, camera_id=camera_id, timestamp="2026-01-01T00:00:00+00:00",
        event_type=event_type, confidence=confidence, anomaly_score=70.0, risk_score=80.0,
        risk_level=risk_level, track_ids=track_ids if track_ids is not None else [1], reasons=["x"], status=status,
    )


class TestIncidentCreation:
    def test_first_event_creates_an_open_incident(self):
        engine = IncidentEngine(Phase3Config())
        incident = engine.process(_event())

        assert incident.incident_id
        assert incident.status == "OPEN"
        assert incident.severity == "HIGH"
        assert incident.start_time
        assert incident.event_ids == ["ev-1"]
        assert incident.camera_ids == ["CAM-1"]

    def test_incident_type_derived_from_event_type(self):
        engine = IncidentEngine(Phase3Config())
        incident = engine.process(_event(event_type="restricted_zone_entry"))
        assert incident.incident_type == "restricted_zone_entry"


class TestEventAssociationAndGrouping:
    def test_same_track_id_associates_with_existing_incident(self):
        engine = IncidentEngine(Phase3Config())
        first = engine.process(_event(event_id="ev-1", track_ids=[5], event_type="running"))
        second = engine.process(_event(event_id="ev-2", track_ids=[5], event_type="loitering"))

        assert second.incident_id == first.incident_id
        assert set(second.event_ids) == {"ev-1", "ev-2"}

    def test_same_event_type_associates_even_with_different_track(self):
        engine = IncidentEngine(Phase3Config())
        first = engine.process(_event(event_id="ev-1", track_ids=[5], event_type="restricted_zone_entry"))
        second = engine.process(_event(event_id="ev-2", track_ids=[9], event_type="restricted_zone_entry"))

        assert second.incident_id == first.incident_id

    def test_unrelated_events_remain_separate_incidents(self):
        engine = IncidentEngine(Phase3Config())
        a = engine.process(_event(event_id="ev-1", camera_id="CAM-1", track_ids=[1], event_type="running"))
        b = engine.process(_event(event_id="ev-2", camera_id="CAM-1", track_ids=[2], event_type="possible_fall"))

        assert a.incident_id != b.incident_id

    def test_different_cameras_never_share_an_incident(self):
        engine = IncidentEngine(Phase3Config())
        a = engine.process(_event(event_id="ev-1", camera_id="CAM-1", track_ids=[1], event_type="running"))
        b = engine.process(_event(event_id="ev-2", camera_id="CAM-2", track_ids=[1], event_type="running"))

        assert a.incident_id != b.incident_id

    def test_severity_escalates_but_never_downgrades(self):
        engine = IncidentEngine(Phase3Config())
        first = engine.process(_event(event_id="ev-1", track_ids=[1], event_type="running", risk_level="MEDIUM"))
        assert first.severity == "MEDIUM"

        escalated = engine.process(_event(event_id="ev-2", track_ids=[1], event_type="running", risk_level="CRITICAL"))
        assert escalated.severity == "CRITICAL"

        back_down = engine.process(_event(event_id="ev-3", track_ids=[1], event_type="running", risk_level="LOW"))
        assert back_down.severity == "CRITICAL"  # never auto-downgraded


class TestIncidentLifecycle:
    def test_escalated_event_confirms_the_incident(self):
        engine = IncidentEngine(Phase3Config())
        incident = engine.process(_event(event_id="ev-1", track_ids=[1], status="ESCALATED"))
        assert incident.status == "CONFIRMED"

    def test_multiple_events_move_open_incident_to_investigating(self):
        engine = IncidentEngine(Phase3Config())
        engine.process(_event(event_id="ev-1", track_ids=[1], status="DETECTED"))
        second = engine.process(_event(event_id="ev-2", track_ids=[1], status="DETECTED"))
        assert second.status == "INVESTIGATING"

    def test_timed_out_incident_is_resolved(self):
        engine = IncidentEngine(Phase3Config(incident_correlation_window_seconds=10.0))
        wc0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        incident = engine.process(_event(event_id="ev-1", track_ids=[1]), wall_clock=wc0)

        resolved = engine.expire_stale(wc0 + timedelta(seconds=20))
        assert len(resolved) == 1
        assert resolved[0].incident_id == incident.incident_id
        assert resolved[0].status == "RESOLVED"
        assert resolved[0].end_time is not None

    def test_dismiss_stops_further_correlation(self):
        engine = IncidentEngine(Phase3Config())
        incident = engine.process(_event(event_id="ev-1", track_ids=[1], camera_id="CAM-1"))
        engine.dismiss(incident, camera_id="CAM-1")
        assert incident.status == "DISMISSED"

        # A new event for the same track should now start a fresh incident.
        new_incident = engine.process(_event(event_id="ev-2", track_ids=[1], camera_id="CAM-1"))
        assert new_incident.incident_id != incident.incident_id
