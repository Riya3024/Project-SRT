"""
Project SRT — Phase 3 configuration (events/incidents/evidence/alerts).

Same env-driven dataclass pattern as services/common/config.py (Phase 1) and
services/common/phase2_config.py (Phase 2) — kept as its own dataclass rather
than merged into either, so each phase's review diff stays readable.

Deliberately reuses Phase 2's RiskLevel/anomaly thresholds for triggering
decisions (see event_engine.py / alert_engine.py) instead of introducing a
second, unrelated scoring system — per the Phase 3 spec's explicit
instruction not to invent a second risk model.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _get_float(name: str, default: float) -> float:
    val = os.getenv(name)
    return float(val) if val else default


def _get_int(name: str, default: int) -> int:
    val = os.getenv(name)
    return int(val) if val else default


def _get_str(name: str, default: str) -> str:
    val = os.getenv(name)
    return val if val else default


@dataclass(frozen=True)
class Phase3Config:
    # --- Event correlation / lifecycle ---
    # How long an event stays "open" for correlation (i.e. a new matching
    # observation updates it instead of creating a new one) without being
    # re-observed, before it's considered timed out / closed.
    event_correlation_window_seconds: float = field(
        default_factory=lambda: _get_float("EVENT_CORRELATION_WINDOW_SECONDS", 5.0)
    )
    # Number of distinct observations (frames/ticks) required before an
    # event is promoted from DETECTED to CONFIRMED (guards against a single
    # noisy frame becoming a "confirmed" event).
    event_confirm_min_observations: int = field(
        default_factory=lambda: _get_int("EVENT_CONFIRM_MIN_OBSERVATIONS", 2)
    )

    # --- Incident correlation ---
    incident_correlation_window_seconds: float = field(
        default_factory=lambda: _get_float("INCIDENT_CORRELATION_WINDOW_SECONDS", 30.0)
    )

    # --- Evidence ---
    evidence_pre_event_seconds: float = field(
        default_factory=lambda: _get_float("EVIDENCE_PRE_EVENT_SECONDS", 10.0)
    )
    evidence_post_event_seconds: float = field(
        default_factory=lambda: _get_float("EVIDENCE_POST_EVENT_SECONDS", 10.0)
    )
    # Local filesystem directory evidence is written under (relative to repo
    # root unless an absolute path is given). Designed to be swappable for
    # an object-storage-backed implementation later — see evidence_engine.py.
    evidence_storage_dir: str = field(
        default_factory=lambda: _get_str("EVIDENCE_STORAGE_DIR", "evidence_store")
    )

    # --- Alerts ---
    alert_cooldown_seconds: float = field(
        default_factory=lambda: _get_float("ALERT_COOLDOWN_SECONDS", 60.0)
    )
    # Minimum RiskLevel (from services.risk_engine.risk_engine.RiskLevel) an
    # incident must carry before an alert is generated at all. Reuses Phase
    # 2's risk levels rather than a separate alert-specific score.
    alert_min_risk_level: str = field(
        default_factory=lambda: _get_str("ALERT_MIN_RISK_LEVEL", "HIGH")
    )


DEFAULT_PHASE3_CONFIG = Phase3Config()
