"""
calculate_plan() is the one function the entire app's timing depends
on — every prompt (wrap up / get ready / leave) and every automation
schedule ultimately comes out of it. It's pure (no I/O, no network),
so it's tested directly against hand-computed expected output rather
than mocked.
"""

from datetime import datetime

from planner import calculate_plan


def test_calculate_plan_original_worked_example():
    # Meeting 15:00, travel 48m, early 10m, invisible 8m, prep 15m, switch 10m
    # -> wrap up 13:29, get ready 13:39, leave 13:54, physical departure 14:02,
    # arrival target 14:50. This is the example the whole project was
    # designed around (see DEVELOPMENT.md).
    meeting_time = datetime(2026, 1, 1, 15, 0)

    plan = calculate_plan(
        meeting_time=meeting_time,
        travel_minutes=48,
        early_arrival_minutes=10,
        invisible_delay_minutes=8,
        prep_minutes=15,
        task_switch_minutes=10,
    )

    assert plan["wrap_up_prompt"] == datetime(2026, 1, 1, 13, 29)
    assert plan["get_ready_prompt"] == datetime(2026, 1, 1, 13, 39)
    assert plan["leave_prompt"] == datetime(2026, 1, 1, 13, 54)
    assert plan["physical_departure"] == datetime(2026, 1, 1, 14, 2)
    assert plan["arrival_target"] == datetime(2026, 1, 1, 14, 50)
    assert plan["meeting_time"] == meeting_time


def test_calculate_plan_zero_buffers_collapse_to_meeting_time():
    meeting_time = datetime(2026, 1, 1, 15, 0)

    plan = calculate_plan(
        meeting_time=meeting_time,
        travel_minutes=0,
        early_arrival_minutes=0,
        invisible_delay_minutes=0,
        prep_minutes=0,
        task_switch_minutes=0,
    )

    assert plan["arrival_target"] == meeting_time
    assert plan["physical_departure"] == meeting_time
    assert plan["leave_prompt"] == meeting_time
    assert plan["get_ready_prompt"] == meeting_time
    assert plan["wrap_up_prompt"] == meeting_time


def test_calculate_plan_prompts_are_strictly_ordered():
    # Every prompt should walk backwards from the meeting time in a
    # fixed order — a regression here would show up as e.g. "get
    # ready" firing after "leave now".
    meeting_time = datetime(2026, 1, 1, 15, 0)

    plan = calculate_plan(
        meeting_time=meeting_time,
        travel_minutes=48,
        early_arrival_minutes=10,
        invisible_delay_minutes=8,
        prep_minutes=15,
        task_switch_minutes=10,
    )

    assert (
        plan["wrap_up_prompt"]
        < plan["get_ready_prompt"]
        < plan["leave_prompt"]
        < plan["physical_departure"]
        < plan["arrival_target"]
        <= plan["meeting_time"]
    )
