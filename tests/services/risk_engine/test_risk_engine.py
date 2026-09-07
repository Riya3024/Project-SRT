from services.anomaly_detection.anomaly_engine import AnomalyObservation
from services.common.phase2_config import Phase2Config
from services.risk_engine.risk_engine import RiskLevel, compute_risk


def _anomaly(score, confidence=0.8, reasons=None):
    return AnomalyObservation(
        track_id=1, anomaly_score=score, confidence=confidence,
        reasons=reasons or [], timestamp=0.0, supporting_features={},
    )


def test_low_risk_level():
    config = Phase2Config()
    obs = compute_risk(1, _anomaly(0.05), [], False, False, 0.9, config, 0.0)
    assert obs.risk_level == RiskLevel.LOW


def test_medium_risk_level():
    config = Phase2Config()
    obs = compute_risk(1, _anomaly(0.45), [], False, False, 0.9, config, 0.0)
    assert obs.risk_level == RiskLevel.MEDIUM


def test_high_risk_level_from_restricted_zone_plus_behavior():
    config = Phase2Config()
    obs = compute_risk(1, _anomaly(0.35), ["running"], True, False, 0.9, config, 0.0)
    assert obs.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
    assert "restricted_zone_presence" in obs.contributors
    assert "behavior:running" in obs.contributors


def test_critical_risk_level_from_multiple_strong_signals():
    config = Phase2Config()
    obs = compute_risk(
        1, _anomaly(0.7, reasons=["speed significantly above normal baseline (z=3.10)"]),
        ["possible_physical_altercation"], True, True, 0.9, config, 0.0,
    )
    assert obs.risk_level == RiskLevel.CRITICAL


def test_risk_score_clamped_to_one():
    config = Phase2Config()
    obs = compute_risk(
        1, _anomaly(1.0), ["possible_physical_altercation", "possible_fall"], True, True, 1.0, config, 0.0,
    )
    assert obs.risk_score <= 1.0


def test_confidence_independent_of_score_level():
    """A HIGH/CRITICAL score built on weak detection confidence should still
    report low confidence — level and confidence are separate axes."""
    config = Phase2Config()
    obs = compute_risk(1, _anomaly(0.9, confidence=0.1), [], True, True, 0.1, config, 0.0)
    assert obs.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
    assert obs.confidence < 0.3


def test_contributors_deduplicated():
    config = Phase2Config()
    obs = compute_risk(
        1, _anomaly(0.5, reasons=["restricted_zone_presence"]), [], True, False, 0.9, config, 0.0,
    )
    assert obs.contributors.count("restricted_zone_presence") == 1
