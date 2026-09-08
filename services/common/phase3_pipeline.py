"""
Project SRT — Phase 2 -> Phase 3 orchestration.

The minimum wiring necessary to demonstrate:

    Risk observation -> EventEngine -> IncidentEngine -> EvidenceEngine -> AlertEngine

(Phase 3 spec, section 16/17). This is intentionally the *only* place that
imports all four Phase 3 engines together — MP4 and webcam sources both
funnel through this same `Phase3Pipeline`, per section 9's requirement that
there be one event/incident/evidence/alert system, not separate per-source
implementations.

Evidence and alerts are only generated once an event is CONFIRMED or
ESCALATED (i.e. EventEngine's own dedup logic has already ruled out
single-frame noise) — this avoids writing an evidence manifest or
evaluating an alert for every transient DETECTED blip, matching section 2's
"do not create spam" requirement one layer further downstream.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from services.anomaly_detection.anomaly_engine import AnomalyObservation
from services.alerts.alert_engine import AlertEngine, AlertObservation
from services.common.phase2_config import Phase2Config
from services.common.phase3_config import Phase3Config
from services.evidence.evidence_engine import EvidenceEngine, EvidenceObservation
from services.incident_intelligence.event_engine import EventEngine, EventObservation
from services.incident_intelligence.incident_engine import IncidentEngine, IncidentObservation
from services.risk_engine.risk_engine import RiskObservation


@dataclass
class Phase3Result:
    event: EventObservation | None
    incident: IncidentObservation | None
    evidence: EvidenceObservation | None
    alert: AlertObservation | None


class Phase3Pipeline:
    def __init__(
        self,
        config: Phase3Config,
        phase2_config: Phase2Config | None = None,
        evidence_base_dir: Path | str | None = None,
    ) -> None:
        self.config = config
        self.event_engine = EventEngine(config, phase2_config)
        self.incident_engine = IncidentEngine(config)
        self.evidence_engine = EvidenceEngine(config, base_dir=evidence_base_dir)
        self.alert_engine = AlertEngine(config)

    def process_observation(
        self,
        track_id: int,
        camera_id: str,
        anomaly: AnomalyObservation,
        risk: RiskObservation,
        behaviors: list[str],
        timestamp: float,
        is_restricted_zone: bool = False,
        source_path: str | None = None,
        event_type: str | None = None,
        wall_clock: datetime | None = None,
    ) -> Phase3Result:
        event = self.event_engine.process(
            track_id=track_id,
            camera_id=camera_id,
            anomaly=anomaly,
            risk=risk,
            behaviors=behaviors,
            timestamp=timestamp,
            is_restricted_zone=is_restricted_zone,
            event_type=event_type,
            wall_clock=wall_clock,
        )
        if event is None:
            return Phase3Result(event=None, incident=None, evidence=None, alert=None)

        incident = self.incident_engine.process(event, wall_clock=wall_clock)

        evidence: EvidenceObservation | None = None
        alert: AlertObservation | None = None
        if event.status in ("CONFIRMED", "ESCALATED"):
            evidence = self.evidence_engine.create_evidence(
                camera_id=camera_id,
                event_time=timestamp,
                event_id=event.event_id,
                incident_id=incident.incident_id,
                source_path=source_path,
                wall_clock=wall_clock,
            )
            alert = self.alert_engine.maybe_alert(
                incident=incident,
                event=event,
                evidence_id=evidence.evidence_id if evidence else None,
                wall_clock=wall_clock,
            )

        return Phase3Result(event=event, incident=incident, evidence=evidence, alert=alert)

    def expire_stale(self, now_wall_clock: datetime) -> tuple[list[EventObservation], list[IncidentObservation]]:
        """Call periodically (e.g. once per processed frame) to close timed-out events/incidents."""
        closed_events = self.event_engine.expire_stale(now_wall_clock)
        resolved_incidents = self.incident_engine.expire_stale(now_wall_clock)
        return closed_events, resolved_incidents
