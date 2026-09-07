from services.baseline.baseline_engine import BaselineKey, BaselineStore
from services.common.phase2_config import Phase2Config
from services.context.context_engine import TimeBucket


def _key():
    return BaselineKey("cam1", "z1", TimeBucket.NIGHT, "speed_px_s")


def test_mean_accumulates_correctly():
    store = BaselineStore()
    key = _key()
    for v in [10.0, 20.0, 30.0]:
        stats = store.update(key, v, timestamp=0.0)
    assert abs(stats.mean - 20.0) < 1e-9
    assert stats.sample_count == 3


def test_variance_zero_for_identical_samples():
    store = BaselineStore()
    key = _key()
    for _ in range(5):
        stats = store.update(key, 50.0, timestamp=0.0)
    assert stats.variance == 0.0


def test_variance_nonzero_for_varying_samples():
    store = BaselineStore()
    key = _key()
    for v in [10.0, 50.0, 90.0]:
        stats = store.update(key, v, timestamp=0.0)
    assert stats.variance > 0


def test_confidence_low_with_few_samples():
    config = Phase2Config()
    store = BaselineStore()
    key = _key()
    stats = store.update(key, 10.0, timestamp=0.0)
    assert stats.confidence(config) < 0.1


def test_confidence_high_with_many_samples():
    config = Phase2Config()
    store = BaselineStore()
    key = _key()
    for i in range(config.baseline_high_confidence_samples + 5):
        stats = store.update(key, 10.0 + i % 3, timestamp=0.0)
    assert stats.confidence(config) == 1.0


def test_zscore_none_with_insufficient_samples():
    store = BaselineStore()
    key = _key()
    stats = store.update(key, 10.0, timestamp=0.0)
    assert stats.zscore(100.0) is None


def test_zscore_computed_with_enough_samples():
    store = BaselineStore()
    key = _key()
    for v in [10.0, 12.0, 8.0, 11.0, 9.0]:
        stats = store.update(key, v, timestamp=0.0)
    z = stats.zscore(50.0)
    assert z is not None and z > 2.0  # far from a tight cluster around ~10
