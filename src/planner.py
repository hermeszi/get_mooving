import json
from datetime import datetime, timedelta
from pathlib import Path


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
    event = load_json("mock_calendar.json")
    profile = load_json("profile.json")

    meeting_time = datetime.fromisoformat(event["start"])

    buffers = profile["buffers"]

    plan = calculate_plan(
        meeting_time=meeting_time,
        travel_minutes=profile["travel_minutes"],
        early_arrival_minutes=buffers["early_arrival_minutes"],
        invisible_delay_minutes=buffers["invisible_delay_minutes"],
        prep_minutes=buffers["prep_minutes"],
        task_switch_minutes=buffers["task_switch_minutes"],
    )

    print_plan(plan, event)


if __name__ == "__main__":
    main()