"""
"I'm running late" recovery: recomputes travel from right now (not the
original planned departure) for the next calendar event, comparing
public transport and drive side by side, so the plan can react to a
slipped schedule instead of just repeating stale numbers.
"""

import argparse
import json
from datetime import datetime, timedelta

from calendar_google import get_next_event, get_current_event
from onemap import (
    search_location,
    get_public_transport_time,
    get_drive_time,
    OneMapError,
    onemap_error_reason,
)
from location_state import needs_confirmation, location_confirmation_prompt
from planner import load_json, format_time, format_24h


MODE_DISPLAY = {
    "public_transport": ("🚇", "Public transport"),
    "drive": ("🚕", "Drive/taxi (road estimate)"),
}


def lateness_minutes(meeting_time: datetime, expected_arrival: datetime) -> int:
    return round((expected_arrival - meeting_time).total_seconds() / 60)


def build_result(event: dict, meeting_time: datetime, options: list) -> dict:
    return {
        "event": event["title"],
        "destination": event["location"],
        "meeting_time": format_24h(meeting_time),
        "attendees": event.get("attendees", []),
        "options": [
            {
                "mode": mode,
                "expected_arrival": format_24h(arrival),
                "lateness_minutes": lateness_minutes(meeting_time, arrival),
            }
            for mode, arrival in options
        ],
    }


def print_result(meeting_time: datetime, options: list) -> None:
    print()
    print("🚨 Plans changed.")
    print()

    for mode, arrival in options:
        emoji, label = MODE_DISPLAY.get(mode, ("•", mode))
        late = lateness_minutes(meeting_time, arrival)
        status = f"{late} min late" if late > 0 else "on time"
        print(f"{emoji} {label:<17} arrive {format_time(arrival)} ({status})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result (or any failure) as JSON instead of text.",
    )
    args = parser.parse_args()

    def emit_error(reason: str, message: str, **extra) -> None:
        if args.json:
            print(json.dumps({"error": reason, "message": message, **extra}))
        else:
            print(message)

    event = get_next_event()
    profile = load_json("profile.json")

    if not event:
        emit_error("no_upcoming_event", "No upcoming timed events found.")
        return

    if not event.get("location"):
        emit_error(
            "no_destination",
            f"'{event['title']}' has no location set. "
            "Cannot calculate travel time without a destination.",
            event=event["title"],
        )
        return

    location = profile["location"]
    now = datetime.now().astimezone()
    current_event = get_current_event()

    if needs_confirmation(location.get("confirmed_at"), location["address"], now, current_event):
        emit_error(
            "location_confirmation_required",
            location_confirmation_prompt(location["label"], current_event),
            label=location["label"],
        )
        return

    meeting_time = datetime.fromisoformat(event["start"])

    try:
        start_location = search_location(location["address"])
    except ValueError as error:
        emit_error("start_location_not_found", str(error))
        return
    except OneMapError as error:
        emit_error(onemap_error_reason(error), str(error))
        return

    try:
        destination = search_location(event["location"])
    except ValueError as error:
        emit_error("destination_not_found", str(error))
        return
    except OneMapError as error:
        emit_error(onemap_error_reason(error), str(error))
        return

    try:
        transit_minutes = get_public_transport_time(start_location, destination, now)
        drive_minutes = get_drive_time(start_location, destination, now)
    except OneMapError as error:
        emit_error(onemap_error_reason(error), str(error))
        return

    options = [
        ("public_transport", now + timedelta(minutes=transit_minutes)),
        ("drive", now + timedelta(minutes=drive_minutes)),
    ]

    if args.json:
        print(json.dumps(build_result(event, meeting_time, options)))
    else:
        print_result(meeting_time, options)


if __name__ == "__main__":
    main()
