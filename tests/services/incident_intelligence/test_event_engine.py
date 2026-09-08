"""Tests for services.incident_intelligence.event_engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.anomaly_detection.anomaly_engine import AnomalyObservation
from services.common.phase2_config import Phase2Config
from services.common.phase3_config import Phase3Config
from services.incident_intelligence.event_engine import (
    EVENT_TYPE_POSSIBLE_ALTERCATION,
    EventEngine,
)
from services.risk_engine.risk_engine import RiskLevel, RiskObservation


def _anomaly(score: float, confidence: float = 0.9, reasons=None) -> AnomalyObservation:
    return AnomalyObservation(track_id=1, anomaly_score=score, confidence=confidence, reasons=reasons or [], timestamp=0.0)


def _risk(score: float, level: RiskLevel, confidence: float = 0.85, contributors=None) -> RiskObservation:
    return RiskObservation(track_id=1, risk_score=score, risk_level=level, confidence=confidence, contributors=contributors or [], timestamp=0.0)


def _config(**overrides) -> Phase3Config:
    base = {}
    base.update(overrides)
    return Phase3Config(**base)


class TestEventCreation:
    def test_normal_low_risk_produces_no_event(self):
        engine = EventEngine(_config())
        result = engine.process(
            track_id=1, camera_id="CAM-1",
            anomaly=_anomaly(0.05), risk=_risk(0.05, RiskLevel.LOW),
            behaviors=["walking"], timestamp=1.0,
        )
        assert result is None

    def test_high_risk_creates_event_with_contract_fields(self):
        engine = EventEngine(_config())
        risk = _risk(0.8, RiskLevel.HIGH, contributors=["anomaly_high"])
        event = engine.process(
            track_id=7, camera_id="CAM-1",
            anomaly=_anomaly(0.7, reasons=["speed_deviation"]), risk=risk,
            behaviors=["running"], timestamp=1.0,
        )
        assert event is not None
        # Required-by-contract fields must always be present.
        assert event.event_id
        assert event.camera_id == "CAM-1"
        assert event.timestamp
        assert event.event_type
        assert 0.0 <= event.confidence <= 1.0
        # risk_level must be a plain contract-valid string, not "RiskLevel.HIGH".
        assert event.risk_level == "HIGH"
        assert event.anomaly_score == 70.0
        assert event.risk_score == 80.0
        assert event.status == "DETECTED"
        assert event.track_ids == [7]
        assert "anomaly_high" in event.reasons
        assert "speed_deviation" in event.reasons

    def test_altercation_behavior_sets_event_type(self):
        engine = EventEngine(_config())
        event = engine.process(
            track_id=1, camera_id="CAM-1",
            anomaly=_anomaly(0.5), risk=_risk(0.6, RiskLevel.HIGH),
            behaviors=["possible_physical_altercation"], timestamp=1.0,
        )
        assert event.event_type == EVENT_TYPE_POSSIBLE_ALTERCATION


class TestEventDeduplication:
    def test_repeated_observation_updates_same_event_not_a_new_one(self):
        engine = EventEngine(_config())
        risk = _risk(0.6, RiskLevel.HIGH)
        anomaly = _anomaly(0.5)

        first = engine.process(track_id=1, camera_id="CAM-1", anomaly=anomaly, risk=risk, behaviors=["running"], timestamp=1.0)
        second = engine.process(track_id=1, camera_id="CAM-1", anomaly=anomaly, risk=risk, behaviors=["running"], timestamp=2.0)

        assert first.event_id == second.event_id

    def test_different_track_creates_a_separate_event(self):
        engine = EventEngine(_config())
        risk = _risk(0.6, RiskLevel.HIGH)
        anomaly = _anomaly(0.5)

        a = engine.process(track_id=1, camera_id="CAM-1", anomaly=anomaly, risk=risk, behaviors=["running"], timestamp=1.0)
        b = engine.process(track_id=2, camera_id="CAM-1", anomaly=anomaly, risk=risk, behaviors=["running"], timestamp=1.0)

        assert a.event_id != b.event_id


class TestEventLifecycle:
    def test_promotes_to_confirmed_after_min_observations(self):
        engine = EventEngine(_config(event_confirm_min_observations=2))
        risk = _risk(0.6, RiskLevel.HIGH)
        anomaly = _anomaly(0.5)

        first = engine.process(track_id=1, camera_id="CAM-1", anomaly=anomaly, risk=risk, behaviors=["running"], timestamp=1.0)
        assert first.status == "DETECTED"

        second = engine.process(track_id=1, camera_id="CAM-1", anomaly=anomaly, risk=risk, behaviors=["running"], timestamp=2.0)
        assert second.status == "CONFIRMED"
        assert second.event_id == first.event_id

    def test_critical_risk_escalates_immediately(self):
        engine = EventEngine(_config())
        event = engine.process(
            track_id=1, camera_id="CAM-1",
            anomaly=_anomaly(0.9), risk=_risk(0.95, RiskLevel.CRITICAL),
            behaviors=["possible_physical_altercation"], timestamp=1.0,
        )
        assert event.status == "ESCALATED"

    def test_timed_out_unconfirmed_event_is_dismissed(self):
        engine = EventEngine(_config(event_correlation_window_seconds=5.0))
        wc0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        risk = _risk(0.6, RiskLevel.HIGH)
        anomaly = _anomaly(0.5)

        event = engine.process(track_id=1, camera_id="CAM-1", anomaly=anomaly, risk=risk, behaviors=["running"], timestamp=1.0, wall_clock=wc0)
        assert event.status == "DETECTED"

        closed = engine.expire_stale(wc0 + timedelta(seconds=10))
        assert len(closed) == 1
        assert closed[0].event_id == event.event_id
        assert closed[0].status == "DISMISSED"

    def test_timed_out_confirmed_event_keeps_its_status(self):
        engine = EventEngine(_config(event_confirm_min_observations=1, event_correlation_window_seconds=5.0))
        wc0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        risk = _risk(0.6, RiskLevel.HIGH)
        anomaly = _anomaly(0.5)

        # event_confirm_min_observations=1 means it's confirmed on first sight.
        event = engine.process(track_id=1, camera_id="CAM-1", anomaly=anomaly, risk=risk, behaviors=["running"], timestamp=1.0, wall_clock=wc0)
        assert event.status == "CONFIRMED"

        closed = engine.expire_stale(wc0 + timedelta(seconds=10))
        assert closed[0].status == "CONFIRMED"

    def test_still_within_window_is_not_expired(self):
        engine = EventEngine(_config(event_correlation_window_seconds=5.0))
        wc0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        engine.process(track_id=1, camera_id="CAM-1", anomaly=_anomaly(0.5), risk=_risk(0.6, RiskLevel.HIGH), behaviors=["running"], timestamp=1.0, wall_clock=wc0)

        closed = engine.expire_stale(wc0 + timedelta(seconds=2))
        assert closed == []
