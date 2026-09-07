from services.behavior_intelligence.behavior_analyzer import classify_single_track
from services.behavior_intelligence.movement_features import MovementFeatures
from services.common.config import PipelineConfig


def _features(**overrides) -> MovementFeatures:
    base = dict(
        track_id=1,
        speed_px_s=0.0,
        direction_deg=0.0,
        acceleration_px_s2=0.0,
        direction_change_deg=0.0,
        is_stationary=True,
        dwell_seconds=0.0,
        displacement_px=0.0,
        samples_used=5,
    )
    base.update(overrides)
    return MovementFeatures(**base)


def test_running_classified_above_threshold():
    config = PipelineConfig()
    f = _features(speed_px_s=config.running_speed_threshold + 50, is_stationary=False)
    obs = classify_single_track(f, timestamp=1.0, config=config)
    behaviors = {o.behavior for o in obs}
    assert "running" in behaviors


def test_walking_classified_between_thresholds():
    config = PipelineConfig()
    mid_speed = (config.walking_speed_threshold + config.running_speed_threshold) / 2
    f = _features(speed_px_s=mid_speed, is_stationary=False)
    obs = classify_single_track(f, timestamp=1.0, config=config)
    behaviors = {o.behavior for o in obs}
    assert "walking" in behaviors


def test_loitering_flagged_after_dwell_threshold():
    config = PipelineConfig()
    f = _features(is_stationary=True, dwell_seconds=config.loitering_dwell_seconds + 1)
    obs = classify_single_track(f, timestamp=1.0, config=config)
    behaviors = {o.behavior for o in obs}
    assert "possible_loitering" in behaviors


def test_plain_stationary_below_loitering_threshold():
    config = PipelineConfig()
    f = _features(is_stationary=True, dwell_seconds=1.0)
    obs = classify_single_track(f, timestamp=1.0, config=config)
    behaviors = {o.behavior for o in obs}
    assert "stationary" in behaviors
    assert "possible_loitering" not in behaviors


def test_sudden_movement_flagged_on_high_acceleration():
    config = PipelineConfig()
    f = _features(
        speed_px_s=config.walking_speed_threshold,
        is_stationary=False,
        acceleration_px_s2=config.sudden_movement_accel_threshold + 10,
    )
    obs = classify_single_track(f, timestamp=1.0, config=config)
    behaviors = {o.behavior for o in obs}
    assert "sudden_movement" in behaviors


def test_no_behaviors_flagged_with_insufficient_samples():
    config = PipelineConfig()
    f = _features(samples_used=1)
    obs = classify_single_track(f, timestamp=1.0, config=config)
    assert obs == []


def test_behavior_language_is_probabilistic_not_certain():
    """Guard against regressions into certainty language (section 13/14/23)."""
    config = PipelineConfig()
    f = _features(
        speed_px_s=config.walking_speed_threshold,
        is_stationary=False,
        acceleration_px_s2=config.sudden_movement_accel_threshold + 10,
        direction_deg=90,
    )
    obs = classify_single_track(f, timestamp=1.0, config=config)
    forbidden = {"criminal", "attacker", "violent", "fighting", "kidnapping"}
    for o in obs:
        assert not (forbidden & set(o.behavior.replace("_", " ").split()))
