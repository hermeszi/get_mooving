"""
get_next_event()/get_current_event() are thin wrappers around the
Google Calendar API — never called against a real account here.
get_credentials() and build() are mocked so the tests exercise only
this module's own filtering logic: skip all-day events, skip an event
already in progress (the real bug fixed in DEVELOPMENT.md §47), and
find the one event actually happening right now.
"""

from datetime import datetime, timedelta, timezone

import calendar_google as cg


def _mock_service(mocker, list_items):
    """
    Builds a fake `service.events().list().execute()` chain returning
    {"items": list_items}, and patches get_credentials()/build() so no
    real OAuth flow or network call ever happens.
    """

    mocker.patch.object(cg, "get_credentials", return_value=object())

    service = mocker.Mock()
    service.events.return_value.list.return_value.execute.return_value = {"items": list_items}
    mocker.patch.object(cg, "build", return_value=service)

    return service


def test_get_next_event_skips_all_day_events(mocker):
    now = datetime.now(timezone.utc)

    items = [
        {"summary": "All-day thing", "start": {"date": now.date().isoformat()}},
        {
            "summary": "Real meeting",
            "start": {"dateTime": (now + timedelta(hours=1)).isoformat()},
            "end": {"dateTime": (now + timedelta(hours=2)).isoformat()},
            "location": "SUTD",
            "attendees": [{"email": "a@example.com", "displayName": "A"}],
        },
    ]
    _mock_service(mocker, items)

    event = cg.get_next_event()

    assert event["title"] == "Real meeting"
    assert event["location"] == "SUTD"
    assert event["attendees"] == [{"email": "a@example.com", "name": "A"}]


def test_get_next_event_skips_already_started_events(mocker):
    # Regression test for §47: Google's timeMin filters by end time,
    # not start time, so an in-progress event can still come back from
    # the API — it must not be treated as "next".
    now = datetime.now(timezone.utc)

    items = [
        {
            "summary": "Already started",
            "start": {"dateTime": (now - timedelta(minutes=10)).isoformat()},
            "end": {"dateTime": (now + timedelta(minutes=20)).isoformat()},
            "location": "Somewhere",
        },
        {
            "summary": "Actually next",
            "start": {"dateTime": (now + timedelta(hours=1)).isoformat()},
            "end": {"dateTime": (now + timedelta(hours=2)).isoformat()},
            "location": "Elsewhere",
        },
    ]
    _mock_service(mocker, items)

    event = cg.get_next_event()

    assert event["title"] == "Actually next"


def test_get_next_event_returns_none_when_no_timed_events(mocker):
    _mock_service(mocker, [{"summary": "All-day only", "start": {"date": "2026-01-01"}}])

    assert cg.get_next_event() is None


def test_get_current_event_finds_in_progress_event(mocker):
    now = datetime.now(timezone.utc)

    items = [
        {
            "summary": "Happening now",
            "start": {"dateTime": (now - timedelta(minutes=10)).isoformat()},
            "end": {"dateTime": (now + timedelta(minutes=20)).isoformat()},
            "location": "SUTD",
        }
    ]
    _mock_service(mocker, items)

    event = cg.get_current_event()

    assert event["title"] == "Happening now"


def test_get_current_event_returns_none_when_nothing_in_progress(mocker):
    now = datetime.now(timezone.utc)

    items = [
        {
            "summary": "Already ended",
            "start": {"dateTime": (now - timedelta(hours=2)).isoformat()},
            "end": {"dateTime": (now - timedelta(hours=1)).isoformat()},
            "location": "SUTD",
        }
    ]
    _mock_service(mocker, items)

    assert cg.get_current_event() is None
