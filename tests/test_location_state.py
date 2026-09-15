"""
location_state.py decides whether the stored starting location can be
trusted. All pure functions — no I/O, no network — so tested directly.
"""

from datetime import datetime, timedelta

from location_state import (
    is_location_fresh,
    conflicts_with_calendar,
    needs_confirmation,
)


NOW = datetime(2026, 1, 1, 12, 0).astimezone()


def test_fresh_timestamp_within_limit():
    confirmed_at = (NOW - timedelta(minutes=30)).isoformat()
    assert is_location_fresh(confirmed_at, NOW) is True


def test_stale_timestamp_past_limit():
    # FRESHNESS_LIMIT is 2 hours.
    confirmed_at = (NOW - timedelta(hours=3)).isoformat()
    assert is_location_fresh(confirmed_at, NOW) is False


def test_missing_timestamp_is_never_fresh():
    assert is_location_fresh(None, NOW) is False
    assert is_location_fresh("", NOW) is False


def test_invalid_timestamp_is_never_fresh():
    # Regression test for the bug where an unparsable confirmed_at
    # crashed instead of returning False (see DEVELOPMENT.md §52).
    assert is_location_fresh("garbage", NOW) is False


def test_conflicts_with_calendar_same_postal_code():
    address = "22 HAVELOCK ROAD SINGAPORE 160022"
    current_event = {"title": "Class", "location": "SUTD, 8 SOMAPAH ROAD 160022"}
    assert conflicts_with_calendar(address, current_event) is False


def test_conflicts_with_calendar_different_postal_code():
    address = "22 HAVELOCK ROAD SINGAPORE 160022"
    current_event = {"title": "Class", "location": "SUTD, 8 SOMAPAH ROAD 487372"}
    assert conflicts_with_calendar(address, current_event) is True


def test_conflicts_with_calendar_no_current_event():
    address = "22 HAVELOCK ROAD SINGAPORE 160022"
    assert conflicts_with_calendar(address, None) is False
    assert conflicts_with_calendar(address, {"title": "Focus block", "location": None}) is False


def test_needs_confirmation_fresh_and_no_conflict_is_trusted():
    confirmed_at = (NOW - timedelta(minutes=10)).isoformat()
    assert needs_confirmation(confirmed_at, "Home", NOW, None) is False


def test_needs_confirmation_stale_forces_confirmation_even_with_no_event():
    confirmed_at = (NOW - timedelta(hours=5)).isoformat()
    assert needs_confirmation(confirmed_at, "Home", NOW, None) is True


def test_needs_confirmation_fresh_but_calendar_conflict_still_forces_confirmation():
    confirmed_at = (NOW - timedelta(minutes=10)).isoformat()
    address = "22 HAVELOCK ROAD SINGAPORE 160022"
    current_event = {"title": "Class", "location": "SUTD, 8 SOMAPAH ROAD 487372"}
    assert needs_confirmation(confirmed_at, address, NOW, current_event) is True
