"""
late_recovery.py's own logic — comparing modes and reporting how late
each one would arrive — lives in lateness_minutes()/build_result(),
both pure. The surrounding main() is mostly calendar/OneMap plumbing
already covered by test_calendar_google.py and test_onemap.py.
"""

from datetime import datetime, timedelta

from late_recovery import lateness_minutes, build_result


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

    result = build_result(event, meeting_time, options)

    assert result["event"] == "SUTD Studio"
    assert result["meeting_time"] == "15:00"
    assert result["options"] == [
        {"mode": "public_transport", "expected_arrival": "15:10", "lateness_minutes": 10},
        {"mode": "drive", "expected_arrival": "14:58", "lateness_minutes": -2},
    ]
