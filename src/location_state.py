"""
Decides whether the user's stored starting location is still trustworthy,
and builds the confirmation prompt to show when it isn't. Shared by
every script that needs a starting point, so the same rule applies
everywhere. "Trustworthy" means two independent things: confirmed
recently enough (is_location_fresh), AND not contradicted by a
calendar event currently in progress (conflicts_with_calendar) — a
location can be fresh by the clock yet clearly wrong if the calendar
says the user should be somewhere else right now.
"""

import re
from datetime import datetime, timedelta


FRESHNESS_LIMIT = timedelta(hours=2)


def _extract_postal(s: str) -> str | None:
    """Extract a 6-digit Singapore postal code from an address string."""
    m = re.search(r'\b(\d{6})\b', s)
    return m.group(1) if m else None


def is_location_fresh(confirmed_at: str, now: datetime) -> bool:
    """
    A location is fresh if it was confirmed within FRESHNESS_LIMIT.
    Missing or unparsable timestamps are never fresh.
    """
    if not confirmed_at:
        return False

    try:
        confirmed_time = datetime.fromisoformat(confirmed_at)
    except (ValueError, TypeError):
        return False

    return now - confirmed_time < FRESHNESS_LIMIT


def conflicts_with_calendar(address: str, current_event: dict) -> bool:
    """
    True if a calendar event happening right now has a different
    location than the stored address — a coarse text check, not
    geocoding, but enough to catch the common case (e.g. still marked
    "Home" while a class across town is in progress).
    """
    if not current_event or not current_event.get("location"):
        return False

    cal_loc = current_event["location"]
    # Compare by postal code first — unambiguous, unaffected by casing or
    # abbreviation differences (e.g. "Rd" vs "Road", OneMap uppercase vs
    # calendar mixed-case).
    cal_postal = _extract_postal(cal_loc)
    addr_postal = _extract_postal(address)
    if cal_postal and addr_postal:
        return cal_postal != addr_postal

    return cal_loc != address


def needs_confirmation(confirmed_at: str, address: str, now: datetime, current_event: dict = None) -> bool:
    return not is_location_fresh(confirmed_at, now) or conflicts_with_calendar(address, current_event)


def location_confirmation_prompt(label: str, current_event: dict = None) -> str:
    if current_event and current_event.get("location"):
        end_time = datetime.fromisoformat(current_event["end"]).strftime("%-I:%M %p")

        return (
            f"📍 {current_event['title']} runs until {end_time} at "
            f"{current_event['location']} — are you leaving from there, or from {label}?\n"
            f"1 {current_event['title']} · 2 {label} · 3 Somewhere else"
        )

    return (
        f"📍 Still starting from {label}?\n"
        "1 Yes · 2 Home · 3 Somewhere else"
    )
