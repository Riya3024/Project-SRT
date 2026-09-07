"""
Project SRT — Normal Behavior Baseline.

Incremental (Welford's online algorithm) mean/variance per
(camera_id, zone_id, time_bucket, feature_name) key. No unbounded history —
each key stores only running statistics, not raw samples (section 14).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from services.common.phase2_config import Phase2Config
from services.context.context_engine import TimeBucket


@dataclass
class BaselineKey:
    camera_id: str
    zone_id: str
    time_bucket: TimeBucket
    feature_name: str

    def as_tuple(self) -> tuple:
        return (self.camera_id, self.zone_id, self.time_bucket.value, self.feature_name)


@dataclass
class BaselineStats:
    sample_count: int = 0
    mean: float = 0.0
    _m2: float = 0.0  # sum of squared differences from the mean (Welford)
    version: int = 1
    last_updated: float = 0.0

    @property
    def variance(self) -> float:
        if self.sample_count < 2:
            return 0.0
        return self._m2 / (self.sample_count - 1)

    @property
    def std(self) -> float:
        return math.sqrt(self.variance)

    def confidence(self, config: Phase2Config) -> float:
        if self.sample_count < config.min_baseline_samples:
            # Linear ramp from 0 up to 0.5 as samples approach the minimum.
            return 0.5 * (self.sample_count / max(config.min_baseline_samples, 1))
        if self.sample_count >= config.baseline_high_confidence_samples:
            return 1.0
        # Linear ramp from 0.5 to 1.0 between min and high-confidence sample counts.
        span = max(config.baseline_high_confidence_samples - config.min_baseline_samples, 1)
        return 0.5 + 0.5 * ((self.sample_count - config.min_baseline_samples) / span)

    def zscore(self, value: float) -> float | None:
        if self.sample_count < 2 or self.std == 0:
            return None
        return (value - self.mean) / self.std


class BaselineStore:
    def __init__(self) -> None:
        self._stats: dict[tuple, BaselineStats] = {}

    def update(self, key: BaselineKey, value: float, timestamp: float) -> BaselineStats:
        k = key.as_tuple()
        stats = self._stats.setdefault(k, BaselineStats())
        stats.sample_count += 1
        delta = value - stats.mean
        stats.mean += delta / stats.sample_count
        delta2 = value - stats.mean
        stats._m2 += delta * delta2
        stats.last_updated = timestamp
        return stats

    def get(self, key: BaselineKey) -> BaselineStats | None:
        return self._stats.get(key.as_tuple())
