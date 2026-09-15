"""
The core deterministic planner. Computes the full departure plan for
the next calendar event — wrap-up, get-ready, leave, and arrival times
— from the meeting time, live travel time, and the user's buffers.
resolve_plan() is the shared entry point reused by late_recovery.py
and schedule_milestones.py so this resolution logic exists in one
place, not three.
"""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

from calendar_google import get_next_event, get_current_event
from onemap import search_location, get_public_transport_time, OneMapError, onemap_error_reason
from location_state import needs_confirmation, location_confirmation_prompt


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def load_json(filename: str) -> dict:
    path = DATA_DIR / filename

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def calculate_plan(
    meeting_time: datetime,
    travel_minutes: int,
    early_arrival_minutes: int,
    invisible_delay_minutes: int,
    prep_minutes: int,
    task_switch_minutes: int,
) -> dict:

    arrival_target = meeting_time - timedelta(
        minutes=early_arrival_minutes
    )

    physical_departure = arrival_target - timedelta(
        minutes=travel_minutes
    )

    leave_prompt = physical_departure - timedelta(
        minutes=invisible_delay_minutes
    )

    get_ready_prompt = leave_prompt - timedelta(
        minutes=prep_minutes
    )

    wrap_up_prompt = get_ready_prompt - timedelta(
        minutes=task_switch_minutes
    )

    return {
        "meeting_time": meeting_time,
        "arrival_target": arrival_target,
        "physical_departure": physical_departure,
        "leave_prompt": leave_prompt,
        "get_ready_prompt": get_ready_prompt,
        "wrap_up_prompt": wrap_up_prompt,
    }


def format_time(dt: datetime) -> str:
    return dt.strftime("%-I:%M %p")


def format_24h(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def build_result(event: dict, plan: dict, transport: str) -> dict:
    return {
        "event": event["title"],
        "destination": event["location"],
        "meeting_time": format_24h(plan["meeting_time"]),
        "event_end": (
            format_24h(datetime.fromisoformat(event["end"]))
            if event.get("end") else None
        ),
        "arrival_target": format_24h(plan["arrival_target"]),
        "wrap_up": format_24h(plan["wrap_up_prompt"]),
        "get_ready": format_24h(plan["get_ready_prompt"]),
        "leave_prompt": format_24h(plan["leave_prompt"]),
        "physical_departure": format_24h(plan["physical_departure"]),
        "transport": transport,
    }


def print_plan(plan: dict, event: dict) -> None:
    print()
    print(f"📅 {event['title']}")
    print(f"📍 {event['location']}")
    print()

    print(f"Meeting:        {format_time(plan['meeting_time'])}")
    print(f"Arrive by:      {format_time(plan['arrival_target'])}")
    print()

    print(f"⏳ Wrap up:      {format_time(plan['wrap_up_prompt'])}")
    print(f"🎒 Get ready:    {format_time(plan['get_ready_prompt'])}")
    print(f"🚪 Leave:        {format_time(plan['leave_prompt'])}")
    print()

    print(
        f"Route-based latest departure: "
        f"{format_time(plan['physical_departure'])}"
    )


def _onemap_error_result(error: OneMapError) -> dict:
    return {"ok": False, "error": onemap_error_reason(error), "message": str(error)}


def resolve_plan(destination_override: str = None) -> dict:
    """
    Compute the full plan for the next calendar event. Shared by
    planner.py's CLI and by anything else that needs the same
    resolution (e.g. schedule_milestones.py) without duplicating the
    location/destination/route logic.

    Returns {"ok": True, "event": ..., "plan": ..., "profile": ...}
    or {"ok": False, "error": ..., "message": ..., **extra}.
    """

    event = get_next_event()
    profile = load_json("profile.json")

    if not event:
        return {"ok": False, "error": "no_upcoming_event", "message": "No upcoming timed events found."}

    if not event.get("location"):
        if destination_override:
            event["location"] = destination_override
        else:
            return {
                "ok": False,
                "error": "no_destination",
                "message": (
                    f"'{event['title']}' has no location set. "
                    "Cannot calculate travel time without a destination."
                ),
                "event": event["title"],
            }

    location = profile["location"]
    current_event = get_current_event()

    if needs_confirmation(location.get("confirmed_at"), location["address"], datetime.now().astimezone(), current_event):
        return {
            "ok": False,
            "error": "location_confirmation_required",
            "message": location_confirmation_prompt(location["label"], current_event),
            "label": location["label"],
        }

    meeting_time = datetime.fromisoformat(event["start"])
    buffers = profile["buffers"]

    try:
        start_location = search_location(location["address"])
    except ValueError as error:
        return {"ok": False, "error": "start_location_not_found", "message": str(error)}
    except OneMapError as error:
        return _onemap_error_result(error)

    try:
        destination = search_location(event["location"])
    except ValueError as error:
        return {"ok": False, "error": "destination_not_found", "message": str(error)}
    except OneMapError as error:
        return _onemap_error_result(error)

    #do one rough estimate
    rough_departure = meeting_time - timedelta(
        minutes=buffers["early_arrival_minutes"] + 60)

    try:
        travel_minutes = get_public_transport_time(
            start_location,
            destination,
            rough_departure,
        )

        #first plan
        plan = calculate_plan(
            meeting_time=meeting_time,
            travel_minutes=travel_minutes,
            early_arrival_minutes=buffers["early_arrival_minutes"],
            invisible_delay_minutes=buffers["invisible_delay_minutes"],
            prep_minutes=buffers["prep_minutes"],
            task_switch_minutes=buffers["task_switch_minutes"],
            )

        #again with the actual departure time
        travel_minutes = get_public_transport_time(
            start_location,
            destination,
            plan["physical_departure"],
        )
    except OneMapError as error:
        return _onemap_error_result(error)

    plan = calculate_plan(
        meeting_time=meeting_time,
        travel_minutes=travel_minutes,
        early_arrival_minutes=buffers["early_arrival_minutes"],
        invisible_delay_minutes=buffers["invisible_delay_minutes"],
        prep_minutes=buffers["prep_minutes"],
        task_switch_minutes=buffers["task_switch_minutes"],
    )

    return {"ok": True, "event": event, "plan": plan, "profile": profile}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the plan (or any failure) as JSON instead of text.",
    )
    parser.add_argument(
        "--destination",
        help="Destination to use when the calendar event has no location.",
    )
    args = parser.parse_args()

    def emit_error(reason: str, message: str, **extra) -> None:
        if args.json:
            print(json.dumps({"error": reason, "message": message, **extra}))
        else:
            print(message)

    result = resolve_plan(destination_override=args.destination)

    if not result["ok"]:
        extra = {k: v for k, v in result.items() if k not in ("ok", "error", "message")}
        emit_error(result["error"], result["message"], **extra)
        return

    event = result["event"]
    plan = result["plan"]
    profile = result["profile"]

    if args.json:
        print(json.dumps(build_result(event, plan, profile["preferred_transport"])))
    else:
        print_plan(plan, event)


if __name__ == "__main__":
    main()