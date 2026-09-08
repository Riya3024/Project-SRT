"""
Project SRT — Incident Engine.

Groups related EventObservations (from event_engine.py) into higher-level
IncidentObservation records matching `contracts/incident.schema.json`
field-for-field. Correlation is deterministic — same camera plus (same
track_id OR same event_type) within `incident_correlation_window_seconds` —
per the Phase 3 spec's instruction not to over-engineer a distributed
correlation system.

Distinguishing OBSERVATION / EVENT / INCIDENT (per spec section 5):
- Many Phase 2 observations of the same ongoing condition -> one EVENT
  (event_engine.py's own deduplication).
- One or more related EVENTs for the same camera/track/timeframe -> one
  INCIDENT (this module).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from services.common.contract_utils import to_contract_dict as _to_contract_dict
from services.common.phase3_config import Phase3Config
from services.incident_intelligence.event_engine import EventObservation

logger = logging.getLogger(__name__)

_INCIDENT_STATUS_OPEN = "OPEN"
_INCIDENT_STATUS_INVESTIGATING = "INVESTIGATING"
_INCIDENT_STATUS_CONFIRMED = "CONFIRMED"
_INCIDENT_STATUS_DISMISSED = "DISMISSED"
_INCIDENT_STATUS_RESOLVED = "RESOLVED"

# Kept in sync with services.risk_engine.risk_engine.RiskLevel's ordering.
_SEVERITY_ORDER: dict[str, int] = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


@dataclass
class IncidentObservation:
    """Mirrors contracts/incident.schema.json field-for-field."""

    incident_id: str
    incident_type: str
    status: str
    severity: str
    start_time: str  # ISO-8601 date-time string
    tenant_id: str | None = None
    end_time: str | None = None
    event_ids: list[str] = field(default_factory=list)
    camera_ids: list[str] = field(default_factory=list)
    correlation_confidence: float | None = None
    timeline: list[dict] = field(default_factory=list)

    def to_contract_dict(self) -> dict:
        """JSON-serializable dict matching contracts/incident.schema.json (drops None-valued optional fields)."""
        return _to_contract_dict(self)


@dataclass
class _ActiveIncidentState:
    observation: IncidentObservation
    track_ids: set[int]
    event_types: set[str]
    last_seen_wall_clock: datetime
    is_open: bool = True


class IncidentEngine:
    def __init__(self, config: Phase3Config) -> None:
        self.config = config
        # Keyed by camera_id -> list of active incident states for that
        # camera (a camera can have multiple unrelated concurrent incidents).
        self._active: dict[str, list[_ActiveIncidentState]] = {}

    def _find_matching_incident(
        self, camera_id: str, track_ids: list[int], event_type: str
    ) -> _ActiveIncidentState | None:
        for state in self._active.get(camera_id, []):
            if state.track_ids & set(track_ids):
                return state
            if event_type in state.event_types:
                return state
        return None

    def expire_stale(self, now_wall_clock: datetime) -> list[IncidentObservation]:
        """Resolve any active incident whose correlation window has elapsed."""
        resolved: list[IncidentObservation] = []
        window = self.config.incident_correlation_window_seconds
        for camera_id, states in list(self._active.items()):
            still_active = []
            for state in states:
                elapsed = (now_wall_clock - state.last_seen_wall_clock).total_seconds()
                if elapsed <= window:
                    still_active.append(state)
                    continue
                if state.observation.status not in (_INCIDENT_STATUS_DISMISSED,):
                    state.observation.status = _INCIDENT_STATUS_RESOLVED
                state.observation.end_time = now_wall_clock.isoformat()
                state.is_open = False
                resolved.append(state.observation)
                logger.info(
                    "Incident resolved incident_id=%s camera=%s final_status=%s",
                    state.observation.incident_id, camera_id, state.observation.status,
                )
            if still_active:
                self._active[camera_id] = still_active
            else:
                del self._active[camera_id]
        return resolved

    def process(self, event: EventObservation, wall_clock: datetime | None = None) -> IncidentObservation:
        """
        Associate `event` with an existing open incident on the same camera
        (matched by shared track_id or event_type), or create a new one.
        Always returns an IncidentObservation — every qualifying event
        (EventEngine already gated triggering) belongs to some incident.
        """
        wc = wall_clock or datetime.now(timezone.utc)
        existing = self._find_matching_incident(event.camera_id, event.track_ids, event.event_type)

        if existing is None:
            initial_status = _INCIDENT_STATUS_CONFIRMED if event.status == "ESCALATED" else _INCIDENT_STATUS_OPEN
            obs = IncidentObservation(
                incident_id=str(uuid.uuid4()),
                incident_type=event.event_type,
                status=initial_status,
                severity=event.risk_level or "LOW",
                start_time=wc.isoformat(),
                event_ids=[event.event_id],
                camera_ids=[event.camera_id],
                correlation_confidence=event.confidence,
                timeline=[{"event_id": event.event_id, "timestamp": event.timestamp, "event_type": event.event_type}],
            )
            state = _ActiveIncidentState(
                observation=obs,
                track_ids=set(event.track_ids),
                event_types={event.event_type},
                last_seen_wall_clock=wc,
            )
            self._active.setdefault(event.camera_id, []).append(state)
            logger.info(
                "Incident created incident_id=%s type=%s camera=%s",
                obs.incident_id, obs.incident_type, obs.camera_ids,
            )
            return obs

        state = existing
        obs = state.observation
        state.last_seen_wall_clock = wc
        state.track_ids |= set(event.track_ids)
        state.event_types.add(event.event_type)

        if event.event_id not in obs.event_ids:
            obs.event_ids.append(event.event_id)
        if event.camera_id not in obs.camera_ids:
            obs.camera_ids.append(event.camera_id)
        obs.timeline.append({"event_id": event.event_id, "timestamp": event.timestamp, "event_type": event.event_type})

        # Escalate severity if this event's risk level is higher than what
        # the incident currently carries; never downgrade automatically.
        if _SEVERITY_ORDER.get(event.risk_level or "LOW", 0) > _SEVERITY_ORDER.get(obs.severity, 0):
            obs.severity = event.risk_level or obs.severity

        # Multiple confirmed/escalated events correlating together raises
        # confidence that this is a real, multi-signal incident.
        if obs.correlation_confidence is not None:
            obs.correlation_confidence = max(0.0, min(1.0, (obs.correlation_confidence + event.confidence) / 2.0 + 0.05))

        if event.status == "ESCALATED":
            obs.status = _INCIDENT_STATUS_CONFIRMED
        elif obs.status == _INCIDENT_STATUS_OPEN and len(obs.event_ids) >= 2:
            obs.status = _INCIDENT_STATUS_INVESTIGATING

        return obs

    def mark_investigating(self, incident: IncidentObservation) -> None:
        """Operator action: mark an incident as under active investigation."""
        incident.status = _INCIDENT_STATUS_INVESTIGATING

    def dismiss(self, incident: IncidentObservation, camera_id: str) -> None:
        """Operator action: dismiss a false-positive incident and stop tracking it."""
        incident.status = _INCIDENT_STATUS_DISMISSED
        self._active[camera_id] = [s for s in self._active.get(camera_id, []) if s.observation.incident_id != incident.incident_id]
