import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

from calendar_google import get_next_event
from onemap import search_location, get_public_transport_time
from location_state import is_location_fresh, location_confirmation_prompt


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

    event = get_next_event()
    profile = load_json("profile.json")

    if not event:
        emit_error("no_upcoming_event", "No upcoming timed events found.")
        return

    if not event.get("location"):
        if args.destination:
            event["location"] = args.destination
        else:
            emit_error(
                "no_destination",
                f"'{event['title']}' has no location set. "
                "Cannot calculate travel time without a destination.",
                event=event["title"],
            )
            return

    location = profile["location"]

    if not is_location_fresh(location.get("confirmed_at"), datetime.now().astimezone()):
        emit_error(
            "location_confirmation_required",
            location_confirmation_prompt(location["label"]),
            label=location["label"],
        )
        return

    meeting_time = datetime.fromisoformat(event["start"])

    buffers = profile["buffers"]

    try:
        start_location = search_location(location["address"])
    except ValueError as error:
        emit_error("start_location_not_found", str(error))
        return

    try:
        destination = search_location(event["location"])
    except ValueError as error:
        emit_error("destination_not_found", str(error))
        return

    #do one rough estimate
    rough_departure = meeting_time - timedelta(
        minutes=buffers["early_arrival_minutes"] + 60)

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

    plan = calculate_plan(
        meeting_time=meeting_time,
        travel_minutes=travel_minutes,
        early_arrival_minutes=buffers["early_arrival_minutes"],
        invisible_delay_minutes=buffers["invisible_delay_minutes"],
        prep_minutes=buffers["prep_minutes"],
        task_switch_minutes=buffers["task_switch_minutes"],
    )

    if args.json:
        print(json.dumps(build_result(event, plan, profile["preferred_transport"])))
    else:
        print_plan(plan, event)


if __name__ == "__main__":
    main()