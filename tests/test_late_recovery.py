"""
late_recovery.py's own logic — comparing modes and reporting how late
each one would arrive — lives in lateness_minutes()/build_result()/
compute_options(), all covered here without a real OneMap call
(compute_options mocks the two mode functions directly). The
surrounding main() is mostly calendar/OneMap plumbing already covered
by test_calendar_google.py and test_onemap.py.

compute_options() in particular is a regression test: it used to wrap
both transport-mode calls in one shared try/except, so a single mode's
OneMap failure (confirmed live — a real 404 for a real trip, unrelated
to the model powering the agent) discarded a working result from the
other mode too, exactly when the user most needed whatever options
still existed.
"""

from datetime import datetime, timedelta

import late_recovery as lr
from late_recovery import lateness_minutes, build_result, compute_options
from onemap import OneMapUnavailableError, OneMapAuthError


def test_lateness_minutes_positive_when_arriving_after_meeting():
    meeting_time = datetime(2026, 1, 1, 15, 0)
    expected_arrival = meeting_time + timedelta(minutes=12)

    assert lateness_minutes(meeting_time, expected_arrival) == 12


def test_lateness_minutes_negative_when_arriving_early():
    meeting_time = datetime(2026, 1, 1, 15, 0)
    expected_arrival = meeting_time - timedelta(minutes=5)

    assert lateness_minutes(meeting_time, expected_arrival) == -5


def test_build_result_shapes_options_by_mode():
    meeting_time = datetime(2026, 1, 1, 15, 0)
    event = {
        "title": "SUTD Studio",
        "location": "SUTD",
        "attendees": [{"email": "a@example.com", "name": "A"}],
    }
    options = [
        ("public_transport", meeting_time + timedelta(minutes=10)),
        ("drive", meeting_time - timedelta(minutes=2)),
    ]

    result = build_result(event, meeting_time, options, unavailable=[])

    assert result["event"] == "SUTD Studio"
    assert result["meeting_time"] == "15:00"
    assert result["options"] == [
        {"mode": "public_transport", "expected_arrival": "15:10", "lateness_minutes": 10},
        {"mode": "drive", "expected_arrival": "14:58", "lateness_minutes": -2},
    ]
    assert "unavailable_modes" not in result


def test_build_result_includes_unavailable_modes_when_present():
    meeting_time = datetime(2026, 1, 1, 15, 0)
    event = {"title": "SUTD Studio", "location": "SUTD", "attendees": []}
    unavailable = [{"mode": "public_transport", "error": "onemap_unavailable", "message": "OneMap returned HTTP 404."}]

    result = build_result(event, meeting_time, options=[], unavailable=unavailable)

    assert result["unavailable_modes"] == unavailable


def test_compute_options_one_mode_failing_does_not_discard_the_other(monkeypatch):
    now = datetime(2026, 1, 1, 12, 0)

    def fake_transit(start, destination, departure):
        raise OneMapUnavailableError("OneMap returned HTTP 404.")

    def fake_drive(start, destination, departure):
        return 44

    monkeypatch.setitem(lr.MODE_FUNCTIONS, "public_transport", fake_transit)
    monkeypatch.setitem(lr.MODE_FUNCTIONS, "drive", fake_drive)

    options, unavailable = compute_options({}, {}, now)

    assert options == [("drive", now + timedelta(minutes=44))]
    assert unavailable == [
        {"mode": "public_transport", "error": "onemap_unavailable", "message": "OneMap returned HTTP 404."}
    ]


def test_compute_options_both_modes_succeed(monkeypatch):
    now = datetime(2026, 1, 1, 12, 0)

    monkeypatch.setitem(lr.MODE_FUNCTIONS, "public_transport", lambda s, d, t: 30)
    monkeypatch.setitem(lr.MODE_FUNCTIONS, "drive", lambda s, d, t: 20)

    options, unavailable = compute_options({}, {}, now)

    assert options == [
        ("public_transport", now + timedelta(minutes=30)),
        ("drive", now + timedelta(minutes=20)),
    ]
    assert unavailable == []


def test_compute_options_both_modes_fail(monkeypatch):
    now = datetime(2026, 1, 1, 12, 0)

    def fake_fail(start, destination, departure):
        raise OneMapAuthError("OneMap authentication failed.")

    monkeypatch.setitem(lr.MODE_FUNCTIONS, "public_transport", fake_fail)
    monkeypatch.setitem(lr.MODE_FUNCTIONS, "drive", fake_fail)

    options, unavailable = compute_options({}, {}, now)

    assert options == []
    assert len(unavailable) == 2
    assert all(failure["error"] == "onemap_auth_failed" for failure in unavailable)
