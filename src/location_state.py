"""
Decides whether the user's stored starting location is still fresh
enough to trust (confirmed within FRESHNESS_LIMIT), and builds the
confirmation prompt to show when it isn't. Shared by every script that
needs a starting point, so the same staleness rule applies everywhere.
"""

from datetime import datetime, timedelta


FRESHNESS_LIMIT = timedelta(hours=2)


def is_location_fresh(confirmed_at: str, now: datetime) -> bool:
    """
    A location is fresh if it was confirmed within FRESHNESS_LIMIT.
    Missing or unparsable timestamps are never fresh.
    """
    if not confirmed_at:
        return False

    confirmed_time = datetime.fromisoformat(confirmed_at)

    return now - confirmed_time < FRESHNESS_LIMIT


def location_confirmation_prompt(label: str) -> str:
    return (
        f"📍 Still starting from {label}?\n"
        "1 Yes · 2 Home · 3 Somewhere else"
    )
