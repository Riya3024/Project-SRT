"""
Project SRT — Event Engine.

Converts Phase 2 output (AnomalyObservation + RiskObservation + behavior
labels) into discrete, deduplicated `EventObservation` records matching the
frozen `contracts/event.schema.json` exactly (field names, types, and the
`status` enum — DETECTED/CONFIRMED/DISMISSED/ESCALATED — come from the real
contract, not the phase spec's illustrative OPEN/UPDATED/RESOLVED wording,
which the contract does not define for events).

Design notes
------------
- Trigger condition reuses Phase 2's own RiskLevel/anomaly-score thresholds
  (no second, unrelated risk model): an event is only created/updated when
  risk_level is at least MEDIUM or the anomaly score clears
  `Phase2Config.anomaly_score_threshold`. A normal-walking, low-risk
  observation produces no event at all.
- Deduplication: observations are correlated by (camera_id, track_id,
  event_type). A new observation for the same key within
  `event_correlation_window_seconds` updates the existing open event
  in-place (same event_id) instead of creating a new one. A key with no
  further observation for longer than the window is closed.
- Lifecycle: DETECTED on first observation. Promoted to CONFIRMED once seen
  `event_confirm_min_observations` times (guards against single-frame
  noise). Promoted to ESCALATED if risk reaches CRITICAL at any point.
  If a key times out while still at DETECTED (never confirmed), it is
  closed with status DISMISSED — the contract has no "resolved" status for
  events (that concept exists at the Incident level instead), so a
  never-confirmed, timed-out event is the closest honest fit for DISMISSED.
  A timed-out CONFIRMED/ESCALATED event keeps that status; only its
  `is_open` bookkeeping (internal, not a contract field) changes.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from services.anomaly_detection.anomaly_engine import AnomalyObservation
from services.common.contract_utils import to_contract_dict as _to_contract_dict
from services.common.phase2_config import Phase2Config
from services.common.phase3_config import Phase3Config
from services.risk_engine.risk_engine import RiskObservation

logger = logging.getLogger(__name__)

# Kept in sync with services.risk_engine.risk_engine.RiskLevel's ordering.
_RISK_LEVEL_ORDER: dict[str, int] = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

# Illustrative event_type values from the Phase 3 spec (section 1). The
# contract leaves event_type as a free string, so these are conventions,
# not an enum — callers may pass any string.
EVENT_TYPE_RESTRICTED_ZONE_ENTRY = "restricted_zone_entry"
EVENT_TYPE_PROLONGED_LOITERING = "prolonged_loitering"
EVENT_TYPE_POSSIBLE_FALL = "possible_fall"
EVENT_TYPE_POSSIBLE_ALTERCATION = "possible_physical_altercation"
EVENT_TYPE_SUDDEN_MOVEMENT = "sudden_movement"
EVENT_TYPE_UNUSUAL_NIGHT_MOVEMENT = "unusual_night_movement"
EVENT_TYPE_HIGH_ANOMALY_OBSERVATION = "high_anomaly_observation"
EVENT_TYPE_HIGH_RISK_OBSERVATION = "high_risk_observation"

_EVENT_STATUS_DETECTED = "DETECTED"
_EVENT_STATUS_CONFIRMED = "CONFIRMED"
_EVENT_STATUS_DISMISSED = "DISMISSED"
_EVENT_STATUS_ESCALATED = "ESCALATED"


@dataclass
class EventObservation:
    """Mirrors contracts/event.schema.json field-for-field."""

    event_id: str
    camera_id: str
    timestamp: str  # ISO-8601 date-time string, per the contract
    event_type: str
    confidence: float  # 0..1, required
    anomaly_score: float | None = None  # 0..100, nullable
    risk_score: float | None = None  # 0..100, nullable
    risk_level: str | None = None
    track_ids: list[int] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    status: str = _EVENT_STATUS_DETECTED

    def to_contract_dict(self) -> dict:
        """JSON-serializable dict matching contracts/event.schema.json (drops None-valued optional fields)."""
        return _to_contract_dict(self)


@dataclass
class _ActiveEventState:
    observation: EventObservation
    observation_count: int
    last_seen_wall_clock: datetime
    is_open: bool = True


def infer_event_type(
    behaviors: list[str],
    risk: RiskObservation,
    anomaly: AnomalyObservation,
    is_restricted_zone: bool,
    anomaly_dominant_threshold: float = 0.6,
) -> str:
    """
    Best-effort event_type classification from available signals. Callers
    with more specific context (e.g. an explicit zone-entry trigger) should
    pass their own event_type to EventEngine.process() instead of relying
    on this.
    """
    if "possible_physical_altercation" in behaviors or "possible_physical_interaction" in behaviors:
        return EVENT_TYPE_POSSIBLE_ALTERCATION
    if "possible_fall" in behaviors:
        return EVENT_TYPE_POSSIBLE_FALL
    if is_restricted_zone:
        return EVENT_TYPE_RESTRICTED_ZONE_ENTRY
    if "possible_loitering" in behaviors:
        return EVENT_TYPE_PROLONGED_LOITERING
    if "sudden_movement" in behaviors or "sudden_direction_change" in behaviors:
        return EVENT_TYPE_SUDDEN_MOVEMENT
    if any("night" in r for r in risk.contributors):
        return EVENT_TYPE_UNUSUAL_NIGHT_MOVEMENT
    # No specific behavior/zone signal fired — fall back to whichever of
    # anomaly vs. risk was the dominant contributor.
    if anomaly.anomaly_score >= anomaly_dominant_threshold:
        return EVENT_TYPE_HIGH_ANOMALY_OBSERVATION
    return EVENT_TYPE_HIGH_RISK_OBSERVATION


class EventEngine:
    """
    Stateful engine: holds open events keyed by (camera_id, track_id,
    event_type) so repeated observations of the same ongoing condition
    update one event instead of spawning duplicates.
    """

    def __init__(self, config: Phase3Config, phase2_config: Phase2Config | None = None) -> None:
        self.config = config
        self.phase2_config = phase2_config or Phase2Config()
        self._active: dict[tuple[str, int, str], _ActiveEventState] = {}

    def _should_trigger(self, anomaly: AnomalyObservation, risk: RiskObservation) -> bool:
        risk_level_rank = _RISK_LEVEL_ORDER.get(risk.risk_level.value, 0)
        anomaly_triggers = anomaly.anomaly_score >= self.phase2_config.anomaly_score_threshold
        risk_triggers = risk_level_rank >= _RISK_LEVEL_ORDER["MEDIUM"]
        return anomaly_triggers or risk_triggers

    def expire_stale(self, now_wall_clock: datetime) -> list[EventObservation]:
        """Close any active event whose correlation window has elapsed. Returns the closed events."""
        closed: list[EventObservation] = []
        window = self.config.event_correlation_window_seconds
        for key, state in list(self._active.items()):
            elapsed = (now_wall_clock - state.last_seen_wall_clock).total_seconds()
            if elapsed <= window:
                continue
            if state.observation.status == _EVENT_STATUS_DETECTED:
                state.observation.status = _EVENT_STATUS_DISMISSED
            state.is_open = False
            closed.append(state.observation)
            logger.info(
                "Event closed key=%s event_id=%s final_status=%s",
                key, state.observation.event_id, state.observation.status,
            )
            del self._active[key]
        return closed

    def _apply_status_promotion(self, obs: EventObservation, state: _ActiveEventState, risk: RiskObservation) -> None:
        """Shared CRITICAL-escalation / min-observations-confirmation logic for both new and updated events."""
        if risk.risk_level.value == "CRITICAL":
            obs.status = _EVENT_STATUS_ESCALATED
        elif state.observation_count >= self.config.event_confirm_min_observations and obs.status == _EVENT_STATUS_DETECTED:
            obs.status = _EVENT_STATUS_CONFIRMED
            logger.info("Event confirmed event_id=%s after %d observations", obs.event_id, state.observation_count)

    def process(
        self,
        track_id: int,
        camera_id: str,
        anomaly: AnomalyObservation,
        risk: RiskObservation,
        behaviors: list[str],
        timestamp: float,
        is_restricted_zone: bool = False,
        event_type: str | None = None,
        wall_clock: datetime | None = None,
    ) -> EventObservation | None:
        """
        Evaluate one Phase 2 observation for one track. Returns the
        resulting EventObservation (new or updated), or None if the
        observation does not clear the trigger threshold (e.g. normal
        walking / low risk — no event at all, per the Phase 3 spec's
        explicit "no alert for normal behavior" requirement).
        """
        if not self._should_trigger(anomaly, risk):
            return None

        wc = wall_clock or datetime.now(timezone.utc)
        etype = event_type or infer_event_type(behaviors, risk, anomaly, is_restricted_zone)
        key = (camera_id, track_id, etype)

        reasons = list(dict.fromkeys(list(risk.contributors) + list(anomaly.reasons)))
        confidence = max(0.0, min(1.0, (anomaly.confidence + risk.confidence) / 2.0))
        anomaly_score_pct = round(anomaly.anomaly_score * 100.0, 2)
        risk_score_pct = round(risk.risk_score * 100.0, 2)

        existing = self._active.get(key)
        if existing is None:
            obs = EventObservation(
                event_id=str(uuid.uuid4()),
                camera_id=camera_id,
                timestamp=wc.isoformat(),
                event_type=etype,
                confidence=confidence,
                anomaly_score=anomaly_score_pct,
                risk_score=risk_score_pct,
                risk_level=risk.risk_level.value,
                track_ids=[track_id],
                reasons=reasons,
                status=_EVENT_STATUS_DETECTED,
            )
            state = _ActiveEventState(observation=obs, observation_count=1, last_seen_wall_clock=wc)
            self._active[key] = state
            self._apply_status_promotion(obs, state, risk)
            logger.info("Event created event_id=%s type=%s camera=%s track=%s", obs.event_id, etype, camera_id, track_id)
            return obs

        # Update in place — same event_id, refreshed snapshot.
        state = existing
        state.observation_count += 1
        state.last_seen_wall_clock = wc
        obs = state.observation
        obs.timestamp = wc.isoformat()
        obs.confidence = confidence
        obs.anomaly_score = anomaly_score_pct
        obs.risk_score = risk_score_pct
        obs.risk_level = risk.risk_level.value
        obs.reasons = reasons
        if track_id not in obs.track_ids:
            obs.track_ids.append(track_id)

        self._apply_status_promotion(obs, state, risk)

        return obs
