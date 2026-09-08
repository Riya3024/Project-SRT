"""
Project SRT — Alert Engine.

Turns a qualifying IncidentObservation (+ its latest EventObservation, +
optional EvidenceObservation) into an operator-facing AlertObservation
matching `contracts/alert.schema.json` field-for-field.

Trigger gating (section 12) deliberately reuses signals already computed
upstream instead of inventing a second risk model:
- The incident's `severity` must be at least `Phase3Config.alert_min_risk_level`
  (reusing services.risk_engine.risk_engine.RiskLevel's ordering).
- The triggering event must have reached CONFIRMED or ESCALATED status —
  i.e. EventEngine's own dedup/confirmation already ruled out single-frame
  noise. A DETECTED-only event never alerts on its own.

Deduplication/cooldown (section 14): keyed by incident_id. Within
`alert_cooldown_seconds` of the last alert for the same incident, a new
alert is suppressed *unless* severity has escalated since the last alert
for that incident (an escalation always gets through, even in cooldown).

Responsible language (section "RESPONSIBLE ALERT/EVENT LANGUAGE"): messages
never claim criminal intent, identity, or certainty — see
_FORBIDDEN_TERMS_TEST in tests/services/alerts/test_alert_engine.py, which
guards against regressions.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from services.common.phase3_config import Phase3Config
from services.common.contract_utils import to_contract_dict as _to_contract_dict
from services.incident_intelligence.event_engine import EventObservation
from services.incident_intelligence.incident_engine import IncidentObservation

logger = logging.getLogger(__name__)

_ALERT_STATUS_OPEN = "OPEN"

# Kept in sync with services.risk_engine.risk_engine.RiskLevel's ordering.
_SEVERITY_ORDER: dict[str, int] = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

_SEVERITY_LABEL: dict[str, str] = {
    "LOW": "informational",
    "MEDIUM": "warning",
    "HIGH": "high-priority",
    "CRITICAL": "critical",
}

_EVENT_TYPE_DISPLAY: dict[str, str] = {
    "restricted_zone_entry": "Restricted-zone entry detected",
    "prolonged_loitering": "Potential prolonged loitering detected",
    "possible_fall": "Possible fall-like movement detected",
    "possible_physical_altercation": "Potential physical altercation detected",
    "sudden_movement": "Potential unusual movement detected",
    "unusual_night_movement": "Potential unusual night-time movement detected",
    "high_anomaly_observation": "Potential unusual activity detected",
    "high_risk_observation": "Potential high-risk activity detected",
}


@dataclass
class AlertObservation:
    """Mirrors contracts/alert.schema.json field-for-field."""

    alert_id: str
    camera_id: str
    severity: str
    title: str
    message: str
    incident_id: str | None = None
    event_id: str | None = None
    risk_score: float = 0.0  # 0..100, required
    status: str = _ALERT_STATUS_OPEN
    created_at: str = ""

    def to_contract_dict(self) -> dict:
        """JSON-serializable dict matching contracts/alert.schema.json (drops None-valued optional fields)."""
        return _to_contract_dict(self)


@dataclass
class _CooldownState:
    last_alert_wall_clock: datetime
    last_severity: str


def _build_message(
    title: str, camera_id: str, severity: str, wc: datetime,
    event_id: str | None, incident_id: str | None, evidence_id: str | None,
) -> str:
    lines = [
        f"{title}",
        "",
        f"Camera: {camera_id}",
        f"Severity: {severity}",
        f"Time: {wc.isoformat()}",
    ]
    if event_id:
        lines.append(f"Event: {event_id}")
    if incident_id:
        lines.append(f"Incident: {incident_id}")
    if evidence_id:
        lines.append(f"Evidence: {evidence_id}")
    lines.append("")
    lines.append("This is an automated indicator for human operator review. It does not")
    lines.append("constitute a determination of criminal intent or identity.")
    return "\n".join(lines)


class AlertEngine:
    def __init__(self, config: Phase3Config) -> None:
        self.config = config
        self._cooldowns: dict[str, _CooldownState] = {}

    def _passes_severity_gate(self, severity: str) -> bool:
        return _SEVERITY_ORDER.get(severity, 0) >= _SEVERITY_ORDER.get(self.config.alert_min_risk_level, 2)

    def _passes_cooldown(self, incident_id: str, severity: str, wc: datetime) -> bool:
        state = self._cooldowns.get(incident_id)
        if state is None:
            return True
        elapsed = (wc - state.last_alert_wall_clock).total_seconds()
        if elapsed >= self.config.alert_cooldown_seconds:
            return True
        # Escalation override: always let a higher-severity alert through,
        # even inside the cooldown window.
        return _SEVERITY_ORDER.get(severity, 0) > _SEVERITY_ORDER.get(state.last_severity, 0)

    def maybe_alert(
        self,
        incident: IncidentObservation,
        event: EventObservation,
        evidence_id: str | None = None,
        wall_clock: datetime | None = None,
    ) -> AlertObservation | None:
        """
        Returns a new AlertObservation if this incident/event clears the
        severity gate, the triggering event is confirmed/escalated (not
        single-frame noise), and cooldown/dedup allows it — otherwise None.
        """
        if event.status not in ("CONFIRMED", "ESCALATED"):
            return None
        if not self._passes_severity_gate(incident.severity):
            return None

        wc = wall_clock or datetime.now(timezone.utc)
        if not self._passes_cooldown(incident.incident_id, incident.severity, wc):
            logger.info(
                "Alert suppressed (cooldown) incident_id=%s severity=%s",
                incident.incident_id, incident.severity,
            )
            return None

        title = _EVENT_TYPE_DISPLAY.get(event.event_type, "Potential unusual activity detected")
        message = _build_message(
            title, event.camera_id, incident.severity, wc, event.event_id, incident.incident_id, evidence_id,
        )

        alert = AlertObservation(
            alert_id=str(uuid.uuid4()),
            camera_id=event.camera_id,
            severity=_SEVERITY_LABEL.get(incident.severity, incident.severity.lower()),
            title=title,
            message=message,
            incident_id=incident.incident_id,
            event_id=event.event_id,
            risk_score=event.risk_score or 0.0,
            status=_ALERT_STATUS_OPEN,
            created_at=wc.isoformat(),
        )
        self._cooldowns[incident.incident_id] = _CooldownState(last_alert_wall_clock=wc, last_severity=incident.severity)
        logger.info(
            "Alert generated alert_id=%s incident_id=%s severity=%s",
            alert.alert_id, incident.incident_id, incident.severity,
        )
        return alert
