"""
Integration tests: Phase 2 risk/anomaly output -> Event -> Incident ->
Evidence -> Alert, exercised through services.common.phase3_pipeline.Phase3Pipeline
(Phase 3 spec, section 21 "Test INTEGRATION" and section 34 — verifying
actual behavior with realistic inputs, not just that classes exist).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.anomaly_detection.anomaly_engine import AnomalyObservation
from services.common.phase2_config import Phase2Config
from services.common.phase3_config import Phase3Config
from services.common.phase3_pipeline import Phase3Pipeline
from services.risk_engine.risk_engine import RiskLevel, RiskObservation


def _anomaly(score: float, reasons=None) -> AnomalyObservation:
    return AnomalyObservation(track_id=1, anomaly_score=score, confidence=0.9, reasons=reasons or [], timestamp=0.0)


def _risk(score: float, level: RiskLevel, contributors=None) -> RiskObservation:
    return RiskObservation(track_id=1, risk_score=score, risk_level=level, confidence=0.85, contributors=contributors or [], timestamp=0.0)


class TestNormalBehaviorProducesNothing:
    def test_normal_walking_low_risk_produces_no_event_incident_evidence_or_alert(self, tmp_path):
        pipeline = Phase3Pipeline(Phase3Config(), evidence_base_dir=tmp_path)
        result = pipeline.process_observation(
            track_id=1, camera_id="CAM-1",
            anomaly=_anomaly(0.05), risk=_risk(0.05, RiskLevel.LOW),
            behaviors=["walking"], timestamp=1.0,
        )
        assert result.event is None
        assert result.incident is None
        assert result.evidence is None
        assert result.alert is None


class TestFullChainForSustainedHighRisk:
    def test_full_chain_risk_to_event_to_incident_to_evidence_to_alert(self, tmp_path):
        pipeline = Phase3Pipeline(
            Phase3Config(event_confirm_min_observations=2, alert_min_risk_level="HIGH"),
            evidence_base_dir=tmp_path,
        )
        wc0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        risk = _risk(0.85, RiskLevel.HIGH, contributors=["restricted_zone_presence"])
        anomaly = _anomaly(0.7, reasons=["speed_deviation"])

        # First observation: DETECTED — not yet confirmed, so no evidence/alert yet.
        first = pipeline.process_observation(
            track_id=3, camera_id="CAM-1", anomaly=anomaly, risk=risk,
            behaviors=["running"], timestamp=1.0, is_restricted_zone=True, wall_clock=wc0,
        )
        assert first.event is not None
        assert first.event.status == "DETECTED"
        assert first.incident is not None
        assert first.evidence is None
        assert first.alert is None

        # Second observation of the same ongoing condition: CONFIRMED — now
        # evidence and an alert should be produced.
        second = pipeline.process_observation(
            track_id=3, camera_id="CAM-1", anomaly=anomaly, risk=risk,
            behaviors=["running"], timestamp=2.0, is_restricted_zone=True,
            wall_clock=wc0 + timedelta(seconds=1),
        )
        assert second.event.status == "CONFIRMED"
        assert second.event.event_id == first.event.event_id  # same event, deduplicated
        assert second.incident.incident_id == first.incident.incident_id  # same incident
        assert second.evidence is not None
        assert second.evidence.event_id == second.event.event_id
        assert second.evidence.incident_id == second.incident.incident_id
        assert second.alert is not None
        assert second.alert.incident_id == second.incident.incident_id
        assert second.alert.event_id == second.event.event_id

    def test_critical_risk_escalates_and_alerts_on_first_observation(self, tmp_path):
        pipeline = Phase3Pipeline(Phase3Config(alert_min_risk_level="HIGH"), evidence_base_dir=tmp_path)
        result = pipeline.process_observation(
            track_id=9, camera_id="CAM-2",
            anomaly=_anomaly(0.95, reasons=["speed_deviation"]),
            risk=_risk(0.97, RiskLevel.CRITICAL, contributors=["restricted_zone_presence"]),
            behaviors=["possible_physical_altercation"], timestamp=1.0,
        )
        assert result.event.status == "ESCALATED"
        assert result.incident.status == "CONFIRMED"
        assert result.evidence is not None
        assert result.alert is not None
        assert result.alert.severity == "critical"


class TestExpiryClosesStaleEventsAndIncidents:
    def test_expire_stale_closes_both_layers(self, tmp_path):
        pipeline = Phase3Pipeline(
            Phase3Config(event_correlation_window_seconds=5.0, incident_correlation_window_seconds=5.0),
            evidence_base_dir=tmp_path,
        )
        wc0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        pipeline.process_observation(
            track_id=1, camera_id="CAM-1", anomaly=_anomaly(0.5),
            risk=_risk(0.6, RiskLevel.HIGH), behaviors=["running"], timestamp=1.0, wall_clock=wc0,
        )

        closed_events, resolved_incidents = pipeline.expire_stale(wc0 + timedelta(seconds=30))
        assert len(closed_events) == 1
        assert len(resolved_incidents) == 1
