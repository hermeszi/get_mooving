import argparse
import json
from datetime import datetime, timedelta

from calendar_google import get_next_event
from onemap import (
    search_location,
    get_public_transport_time,
    get_drive_time,
    get_walk_time,
    get_cycle_time,
    straight_line_km,
)
from location_state import is_location_fresh, location_confirmation_prompt
from planner import load_json, format_24h
from weather import get_forecast


MODE_DISPLAY = {
    "public_transport": "🚇 Public transport",
    "drive": "🚕 Drive/taxi (road estimate)",
    "walk": "🚶 Walk",
    "cycle": "🚲 Cycle",
}

MODE_FUNCTIONS = {
    "public_transport": get_public_transport_time,
    "drive": get_drive_time,
    "walk": get_walk_time,
    "cycle": get_cycle_time,
}

# Straight-line distance beyond which walking/cycling stop being
# realistic recovery options and are left out of --compare.
WALK_MAX_KM = 1.5
CYCLE_MAX_KM = 5.0


def build_result(
    departure_time: datetime,
    meeting_time: datetime,
    arrival_target: datetime,
    options: dict,
    distance_km: float,
    weather: dict,
) -> dict:
    result = {
        "departure": format_24h(departure_time),
        "meeting_time": format_24h(meeting_time),
        "arrival_target": format_24h(arrival_target),
        "distance_km": round(distance_km, 1),
        "weather": weather,
        "options": {
            mode: {
                "travel_minutes": travel_minutes,
                "arrival": format_24h(arrival),
            }
            for mode, (travel_minutes, arrival) in options.items()
        },
    }

    if len(options) > 1:
        result["best_option"] = min(
            options, key=lambda mode: options[mode][1]
        )

    return result


def print_result(result: dict) -> None:
    print()
    print(
        f"Departure {result['departure']} -> meeting {result['meeting_time']} "
        f"(arrival target {result['arrival_target']}, {result['distance_km']} km)"
    )

    if result["weather"]:
        print(f"Weather ({result['weather']['area']}): {result['weather']['forecast']}")

    print()

    for mode, option in result["options"].items():
        label = MODE_DISPLAY.get(mode, mode)
        print(f"{label:<28} {option['travel_minutes']} min -> arrive {option['arrival']}")

    if "best_option" in result:
        print()
        print(f"Best option: {result['best_option']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--departure",
        required=True,
        help='Hypothetical departure time, 24-hour "HH:MM".',
    )
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--mode",
        choices=sorted(MODE_FUNCTIONS),
        help="Check a single transport mode (always honored, even if far or raining).",
    )
    mode_group.add_argument(
        "--compare",
        action="store_true",
        help="Check every transport mode and report the best one.",
    )
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

    try:
        departure_clock = datetime.strptime(args.departure, "%H:%M").time()
    except ValueError:
        emit_error(
            "invalid_departure",
            f"'{args.departure}' is not a valid 24-hour HH:MM time.",
        )
        return

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

    if not is_location_fresh(location.get("confirmed_at"), datetime.now().astimezone()):
        emit_error(
            "location_confirmation_required",
            location_confirmation_prompt(location["label"]),
            label=location["label"],
        )
        return

    meeting_time = datetime.fromisoformat(event["start"])
    departure_time = datetime.combine(
        meeting_time.date(), departure_clock, tzinfo=meeting_time.tzinfo
    )
    arrival_target = meeting_time - timedelta(
        minutes=profile["buffers"]["early_arrival_minutes"]
    )

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

    distance_km = straight_line_km(start_location, destination)

    try:
        weather = get_forecast(start_location["latitude"], start_location["longitude"])
    except Exception:
        weather = None

    raining = bool(weather and weather["rain"])

    if args.mode:
        modes = [args.mode]
    else:
        modes = ["public_transport", "drive"]

        if not raining and distance_km <= WALK_MAX_KM:
            modes.append("walk")

        if not raining and distance_km <= CYCLE_MAX_KM:
            modes.append("cycle")

    options = {}

    for mode in modes:
        travel_minutes = MODE_FUNCTIONS[mode](start_location, destination, departure_time)
        options[mode] = (travel_minutes, departure_time + timedelta(minutes=travel_minutes))

    result = build_result(
        departure_time, meeting_time, arrival_target, options, distance_km, weather
    )

    if args.json:
        print(json.dumps(result))
    else:
        print_result(result)


if __name__ == "__main__":
    main()
