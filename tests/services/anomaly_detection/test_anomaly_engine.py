from services.anomaly_detection.anomaly_engine import AnomalyEngine
from services.baseline.baseline_engine import BaselineKey, BaselineStore
from services.common.phase2_config import Phase2Config
from services.context.context_engine import TimeBucket


def _seed_baseline(store, config, feature="speed_px_s", values=None):
    values = values or [10.0, 12.0, 9.0, 11.0, 10.0, 13.0, 9.5, 10.5, 11.5, 10.0] * 3
    key = BaselineKey("cam1", "z1", TimeBucket.NIGHT, feature)
    for v in values:
        store.update(key, v, timestamp=0.0)
    return key


def test_normal_observation_scores_low():
    config = Phase2Config()
    store = BaselineStore()
    _seed_baseline(store, config)
    engine = AnomalyEngine(store, config)
    obs = engine.evaluate(
        track_id=1, camera_id="cam1", zone_id="z1", time_bucket=TimeBucket.NIGHT,
        features={"speed_px_s": 10.5}, context_flags=[], timestamp=0.0,
    )
    assert obs.anomaly_score < 0.2
    assert obs.reasons == []


def test_statistical_deviation_flagged():
    config = Phase2Config()
    store = BaselineStore()
    _seed_baseline(store, config)
    engine = AnomalyEngine(store, config)
    obs = engine.evaluate(
        track_id=1, camera_id="cam1", zone_id="z1", time_bucket=TimeBucket.NIGHT,
        features={"speed_px_s": 500.0}, context_flags=[], timestamp=0.0,
    )
    assert obs.anomaly_score > 0.3
    assert any("speed_px_s" in r for r in obs.reasons)


def test_insufficient_baseline_gives_zero_statistical_score():
    config = Phase2Config()
    store = BaselineStore()  # no seeding at all
    engine = AnomalyEngine(store, config)
    obs = engine.evaluate(
        track_id=1, camera_id="cam1", zone_id="z1", time_bucket=TimeBucket.NIGHT,
        features={"speed_px_s": 500.0}, context_flags=[], timestamp=0.0,
    )
    assert obs.anomaly_score == 0.0
    assert obs.confidence == 0.0


def test_context_flags_contribute_without_statistics():
    config = Phase2Config()
    store = BaselineStore()
    engine = AnomalyEngine(store, config)
    obs = engine.evaluate(
        track_id=1, camera_id="cam1", zone_id="z1", time_bucket=TimeBucket.NIGHT,
        features={}, context_flags=["restricted_zone_presence"], timestamp=0.0,
    )
    assert obs.anomaly_score > 0.0
    assert "restricted_zone_presence" in obs.reasons


def test_crowd_count_alone_is_not_automatically_anomalous():
    """Guard against section-22 regressions: raw counts must go through the
    same baseline-comparison path as any other feature, never a shortcut."""
    config = Phase2Config()
    store = BaselineStore()
    # Baseline says ~5 people is typical for this camera/zone/time.
    key = BaselineKey("cam1", "z1", TimeBucket.NIGHT, "person_count")
    for v in [4, 5, 6, 5, 5, 4, 6, 5]:
        store.update(key, float(v), timestamp=0.0)
    engine = AnomalyEngine(store, config)
    # A count in line with baseline should NOT be flagged just for existing.
    obs = engine.evaluate(
        track_id=0, camera_id="cam1", zone_id="z1", time_bucket=TimeBucket.NIGHT,
        features={"person_count": 5.0}, context_flags=[], timestamp=0.0,
    )
    assert obs.anomaly_score < 0.2


def test_reasons_never_empty_when_score_is_high():
    config = Phase2Config()
    store = BaselineStore()
    _seed_baseline(store, config)
    engine = AnomalyEngine(store, config)
    obs = engine.evaluate(
        track_id=1, camera_id="cam1", zone_id="z1", time_bucket=TimeBucket.NIGHT,
        features={"speed_px_s": 500.0}, context_flags=[], timestamp=0.0,
    )
    if obs.anomaly_score > 0.3:
        assert len(obs.reasons) > 0
