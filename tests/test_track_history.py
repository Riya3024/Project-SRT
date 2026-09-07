from services.tracking.track_history import TrackHistoryStore


def test_creates_new_track_on_first_update():
    store = TrackHistoryStore(max_len=10, lost_ttl_frames=5)
    record = store.update(1, "person", (0, 0, 10, 10), frame_number=0, timestamp=0.0)
    assert record.track_id == 1
    assert len(record.samples) == 1


def test_persistent_id_across_frames():
    store = TrackHistoryStore(max_len=10, lost_ttl_frames=5)
    store.update(7, "person", (0, 0, 10, 10), frame_number=0, timestamp=0.0)
    store.update(7, "person", (5, 5, 15, 15), frame_number=1, timestamp=0.1)
    record = store.get(7)
    assert record is not None
    assert len(record.samples) == 2
    assert record.samples[-1].center == (10.0, 10.0)


def test_bounded_history_length():
    store = TrackHistoryStore(max_len=3, lost_ttl_frames=100)
    for i in range(10):
        store.update(1, "person", (i, i, i + 10, i + 10), frame_number=i, timestamp=float(i))
    record = store.get(1)
    assert record is not None
    assert len(record.samples) == 3  # bounded, not 10


def test_track_expiry_after_ttl():
    store = TrackHistoryStore(max_len=10, lost_ttl_frames=2)
    store.update(1, "person", (0, 0, 10, 10), frame_number=0, timestamp=0.0)
    expired = store.expire(current_frame=5)
    assert 1 in expired
    assert store.get(1) is None


def test_active_tracks_excludes_expired():
    store = TrackHistoryStore(max_len=10, lost_ttl_frames=2)
    store.update(1, "person", (0, 0, 10, 10), frame_number=0, timestamp=0.0)
    store.update(2, "person", (0, 0, 10, 10), frame_number=4, timestamp=0.4)
    active = store.all_active(current_frame=5)
    active_ids = {r.track_id for r in active}
    assert active_ids == {2}
