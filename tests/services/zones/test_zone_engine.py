from services.zones.zone_engine import Zone, ZoneEngine, ZoneType, bottom_center

SQUARE = [(100, 100), (500, 100), (500, 400), (100, 400)]


def test_point_inside_polygon():
    zone = Zone("z1", "cam1", "Restricted", SQUARE, ZoneType.RESTRICTED)
    assert zone.contains_point(300, 250) is True


def test_point_outside_polygon():
    zone = Zone("z1", "cam1", "Restricted", SQUARE, ZoneType.RESTRICTED)
    assert zone.contains_point(50, 50) is False


def test_bottom_center_used_for_membership():
    bbox = (100.0, 100.0, 200.0, 300.0)
    assert bottom_center(bbox) == (150.0, 300.0)


def test_zone_entry_detected():
    zone = Zone("z1", "cam1", "Restricted", SQUARE, ZoneType.RESTRICTED)
    engine = ZoneEngine([zone])
    event = engine.update(track_id=1, bbox=(280, 200, 320, 260), timestamp=0.0)
    assert event.event_type == "entered"
    assert event.zone_id == "z1"


def test_zone_dwell_accumulates():
    zone = Zone("z1", "cam1", "Restricted", SQUARE, ZoneType.RESTRICTED)
    engine = ZoneEngine([zone])
    engine.update(track_id=1, bbox=(280, 200, 320, 260), timestamp=0.0)
    event = engine.update(track_id=1, bbox=(285, 205, 325, 265), timestamp=5.0)
    assert event.event_type == "inside"
    assert abs(event.dwell_seconds - 5.0) < 1e-6


def test_zone_exit_detected():
    zone = Zone("z1", "cam1", "Restricted", SQUARE, ZoneType.RESTRICTED)
    engine = ZoneEngine([zone])
    engine.update(track_id=1, bbox=(280, 200, 320, 260), timestamp=0.0)
    event = engine.update(track_id=1, bbox=(10, 10, 30, 30), timestamp=2.0)
    assert event.event_type == "exited"


def test_track_outside_any_zone():
    zone = Zone("z1", "cam1", "Restricted", SQUARE, ZoneType.RESTRICTED)
    engine = ZoneEngine([zone])
    event = engine.update(track_id=2, bbox=(10, 10, 30, 30), timestamp=0.0)
    assert event.event_type == "outside"


def test_disabled_zone_never_matches():
    zone = Zone("z1", "cam1", "Restricted", SQUARE, ZoneType.RESTRICTED, enabled=False)
    engine = ZoneEngine([zone])
    event = engine.update(track_id=1, bbox=(280, 200, 320, 260), timestamp=0.0)
    assert event.event_type == "outside"
