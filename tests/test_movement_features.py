from services.behavior_intelligence.movement_features import compute_movement_features
from services.tracking.track_history import TrackHistoryStore


def _store_with(*positions_and_times):
    store = TrackHistoryStore(max_len=90, lost_ttl_frames=100)
    for frame_number, (pos, t) in enumerate(positions_and_times):
        x, y = pos
        store.update(1, "person", (x, y, x + 20, y + 40), frame_number=frame_number, timestamp=t)
    return store.get(1)


def test_insufficient_samples_reports_stationary_zero_speed():
    record = _store_with(((0, 0), 0.0))
    features = compute_movement_features(record, stationary_speed_threshold=8.0)
    assert features.samples_used == 1
    assert features.speed_px_s == 0.0
    assert features.is_stationary is True


def test_speed_calculation_moving_east():
    # center moves from (10,20) to (110,20) over 1 second -> 100 px/s east
    record = _store_with(((0, 0), 0.0), ((100, 0), 1.0))
    features = compute_movement_features(record, stationary_speed_threshold=8.0)
    assert abs(features.speed_px_s - 100.0) < 1e-6
    assert features.is_stationary is False
    assert features.direction_deg is not None


def test_stationary_detection_below_threshold():
    record = _store_with(((0, 0), 0.0), ((1, 0), 1.0))  # ~1 px/s
    features = compute_movement_features(record, stationary_speed_threshold=8.0)
    assert features.is_stationary is True


def test_direction_change_detected_on_reversal():
    # moves east, then reverses to west -> ~180 degree direction change
    record = _store_with(((0, 0), 0.0), ((100, 0), 1.0), ((0, 0), 2.0))
    features = compute_movement_features(record, stationary_speed_threshold=8.0)
    assert features.direction_change_deg > 150


def test_acceleration_sign_on_speed_increase():
    record = _store_with(((0, 0), 0.0), ((10, 0), 1.0), ((110, 0), 2.0))
    features = compute_movement_features(record, stationary_speed_threshold=8.0)
    assert features.acceleration_px_s2 > 0
