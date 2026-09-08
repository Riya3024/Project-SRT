"""Tests for services.alerts.alert_engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.alerts.alert_engine import AlertEngine
from services.common.phase3_config import Phase3Config
from services.incident_intelligence.event_engine import EventObservation
from services.incident_intelligence.incident_engine import IncidentObservation

# Section "RESPONSIBLE ALERT/EVENT LANGUAGE" — phrases the system must never produce.
_FORBIDDEN_TERMS = [
    "criminal detected", "criminal activity confirmed", "kidnapper detected",
    "kidnapping detected", "terrorist detected", "person is dangerous",
    "person committed a crime",
]


def _event(event_id="ev-1", camera_id="CAM-1", event_type="sudden_movement", status="CONFIRMED", risk_score=80.0) -> EventObservation:
    return EventObservation(
        event_id=event_id, camera_id=camera_id, timestamp="2026-01-01T00:00:00+00:00",
        event_type=event_type, confidence=0.8, anomaly_score=70.0, risk_score=risk_score,
        risk_level="HIGH", track_ids=[1], reasons=["x"], status=status,
    )


def _incident(incident_id="inc-1", severity="HIGH", status="CONFIRMED") -> IncidentObservation:
    return IncidentObservation(
        incident_id=incident_id, incident_type="sudden_movement", status=status, severity=severity,
        start_time="2026-01-01T00:00:00+00:00", event_ids=["ev-1"], camera_ids=["CAM-1"],
    )


class TestAlertCreation:
    def test_confirmed_high_severity_incident_generates_an_alert(self):
        engine = AlertEngine(Phase3Config(alert_min_risk_level="HIGH"))
        alert = engine.maybe_alert(_incident(severity="HIGH"), _event(status="CONFIRMED"))

        assert alert is not None
        assert alert.alert_id
        assert alert.camera_id == "CAM-1"
        assert alert.incident_id == "inc-1"
        assert alert.event_id == "ev-1"
        assert alert.risk_score == 80.0
        assert alert.status == "OPEN"
        assert alert.created_at

    def test_detected_only_event_does_not_alert(self):
        engine = AlertEngine(Phase3Config(alert_min_risk_level="HIGH"))
        alert = engine.maybe_alert(_incident(severity="HIGH"), _event(status="DETECTED"))
        assert alert is None

    def test_below_min_severity_does_not_alert(self):
        engine = AlertEngine(Phase3Config(alert_min_risk_level="HIGH"))
        alert = engine.maybe_alert(_incident(severity="MEDIUM"), _event(status="CONFIRMED"))
        assert alert is None

    def test_escalated_event_alerts_too(self):
        engine = AlertEngine(Phase3Config(alert_min_risk_level="HIGH"))
        alert = engine.maybe_alert(_incident(severity="CRITICAL"), _event(status="ESCALATED"))
        assert alert is not None


class TestSeverityMapping:
    def test_high_maps_to_high_priority(self):
        engine = AlertEngine(Phase3Config(alert_min_risk_level="HIGH"))
        alert = engine.maybe_alert(_incident(severity="HIGH"), _event())
        assert alert.severity == "high-priority"

    def test_critical_maps_to_critical(self):
        engine = AlertEngine(Phase3Config(alert_min_risk_level="HIGH"))
        alert = engine.maybe_alert(_incident(severity="CRITICAL"), _event())
        assert alert.severity == "critical"


class TestAlertDeduplication:
    def test_second_alert_within_cooldown_is_suppressed(self):
        engine = AlertEngine(Phase3Config(alert_min_risk_level="HIGH", alert_cooldown_seconds=60.0))
        wc0 = datetime(2026, 1, 1, tzinfo=timezone.utc)

        first = engine.maybe_alert(_incident(severity="HIGH"), _event(), wall_clock=wc0)
        second = engine.maybe_alert(_incident(severity="HIGH"), _event(), wall_clock=wc0 + timedelta(seconds=5))

        assert first is not None
        assert second is None

    def test_alert_allowed_again_after_cooldown_elapses(self):
        engine = AlertEngine(Phase3Config(alert_min_risk_level="HIGH", alert_cooldown_seconds=60.0))
        wc0 = datetime(2026, 1, 1, tzinfo=timezone.utc)

        engine.maybe_alert(_incident(severity="HIGH"), _event(), wall_clock=wc0)
        later = engine.maybe_alert(_incident(severity="HIGH"), _event(), wall_clock=wc0 + timedelta(seconds=90))

        assert later is not None

    def test_escalation_overrides_cooldown(self):
        engine = AlertEngine(Phase3Config(alert_min_risk_level="HIGH", alert_cooldown_seconds=60.0))
        wc0 = datetime(2026, 1, 1, tzinfo=timezone.utc)

        engine.maybe_alert(_incident(incident_id="inc-1", severity="HIGH"), _event(), wall_clock=wc0)
        escalated = engine.maybe_alert(
            _incident(incident_id="inc-1", severity="CRITICAL"), _event(status="ESCALATED"), wall_clock=wc0 + timedelta(seconds=5),
        )
        assert escalated is not None
        assert escalated.severity == "critical"

    def test_different_incidents_have_independent_cooldowns(self):
        engine = AlertEngine(Phase3Config(alert_min_risk_level="HIGH", alert_cooldown_seconds=60.0))
        wc0 = datetime(2026, 1, 1, tzinfo=timezone.utc)

        a = engine.maybe_alert(_incident(incident_id="inc-A", severity="HIGH"), _event(), wall_clock=wc0)
        b = engine.maybe_alert(_incident(incident_id="inc-B", severity="HIGH"), _event(), wall_clock=wc0 + timedelta(seconds=1))

        assert a is not None
        assert b is not None


class TestAlertLinkageAndLanguage:
    def test_evidence_id_appears_in_message_when_provided(self):
        engine = AlertEngine(Phase3Config(alert_min_risk_level="HIGH"))
        alert = engine.maybe_alert(_incident(severity="HIGH"), _event(), evidence_id="ev-evidence-1")
        assert "ev-evidence-1" in alert.message

    def test_message_never_contains_forbidden_certainty_language(self):
        engine = AlertEngine(Phase3Config(alert_min_risk_level="HIGH"))
        alert = engine.maybe_alert(_incident(severity="CRITICAL"), _event(event_type="possible_physical_altercation", status="ESCALATED"))

        combined = (alert.title + " " + alert.message).lower()
        for forbidden in _FORBIDDEN_TERMS:
            assert forbidden not in combined, f"forbidden phrase leaked into alert: {forbidden!r}"

    def test_message_uses_probabilistic_language_for_altercation(self):
        engine = AlertEngine(Phase3Config(alert_min_risk_level="HIGH"))
        alert = engine.maybe_alert(_incident(severity="CRITICAL"), _event(event_type="possible_physical_altercation", status="ESCALATED"))
        assert "potential" in alert.title.lower() or "possible" in alert.title.lower()
