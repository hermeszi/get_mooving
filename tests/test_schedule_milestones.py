"""
schedule_milestones.py's own logic is the dedupe/reschedule/past-time
bookkeeping around subprocess calls to `openclaw automations`, not
plan resolution (that's planner.resolve_plan(), already covered by
test_planner.py and exercised live in DEVELOPMENT.md §44). So here
resolve_plan() and subprocess.run() are both mocked, isolating exactly
the behavior this module is responsible for.
"""

import json
from datetime import datetime, timedelta

import pytest

import schedule_milestones as sm


NOW = datetime.now().astimezone()

EVENT = {
    "title": "SUTD Studio",
    "location": "SUTD, 8 Somapah Road",
    "start": (NOW + timedelta(hours=2)).isoformat(),
    "attendees": [],
}

PROFILE = {"notify_email": "mingde@gmail.com"}


def make_plan(wrap_up_delta, get_ready_delta, leave_delta):
    return {
        "meeting_time": NOW + timedelta(hours=2),
        "wrap_up_prompt": NOW + timedelta(minutes=wrap_up_delta),
        "get_ready_prompt": NOW + timedelta(minutes=get_ready_delta),
        "leave_prompt": NOW + timedelta(minutes=leave_delta),
    }


def mock_resolve_plan(mocker, plan):
    return mocker.patch(
        "schedule_milestones.resolve_plan",
        return_value={"ok": True, "event": EVENT, "plan": plan, "profile": PROFILE},
    )


def mock_subprocess(mocker, existing_jobs):
    """
    Routes `openclaw automations list` to the given existing jobs and
    records every `add`/`edit` call for assertions, without touching a
    real openclaw install.
    """

    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)

        if args[1:3] == ["automations", "list"]:
            return mocker.Mock(stdout=json.dumps({"jobs": existing_jobs}))

        return mocker.Mock(stdout="")

    run = mocker.patch("schedule_milestones.subprocess.run", side_effect=fake_run)
    return run, calls


def test_schedule_all_adds_new_milestones(mocker):
    plan = make_plan(30, 45, 60)  # all in the future
    mock_resolve_plan(mocker, plan)
    run, calls = mock_subprocess(mocker, existing_jobs=[])

    result = sm.schedule_all()

    assert len(result["scheduled"]) == 3
    assert result["rescheduled"] == []
    add_calls = [c for c in calls if c[1:3] == ["automations", "add"]]
    assert len(add_calls) == 3


def test_schedule_all_does_not_duplicate_existing_jobs(mocker):
    plan = make_plan(30, 45, 60)
    mock_resolve_plan(mocker, plan)

    existing_jobs = [
        {
            "declarationKey": f"gm-{field}-{EVENT['start']}",
            "id": f"job-{field}",
            "schedule": {"at": plan[field].isoformat()},
        }
        for field in ("wrap_up_prompt", "get_ready_prompt", "leave_prompt")
    ]
    run, calls = mock_subprocess(mocker, existing_jobs=existing_jobs)

    result = sm.schedule_all()

    assert result["scheduled"] == []
    assert result["rescheduled"] == []
    add_or_edit_calls = [c for c in calls if c[1:3] in (["automations", "add"], ["automations", "edit"])]
    assert add_or_edit_calls == []


def test_schedule_all_reschedules_stale_job(mocker):
    plan = make_plan(30, 45, 60)
    mock_resolve_plan(mocker, plan)

    stale_key = f"gm-wrap_up_prompt-{EVENT['start']}"
    wrong_time = (plan["wrap_up_prompt"] + timedelta(minutes=15)).isoformat()
    existing_jobs = [{"declarationKey": stale_key, "id": "job-1", "schedule": {"at": wrong_time}}]
    run, calls = mock_subprocess(mocker, existing_jobs=existing_jobs)

    result = sm.schedule_all()

    assert result["rescheduled"] == [
        {"milestone": "wrap_up_prompt", "label": "⏳ Wrap this up", "at": plan["wrap_up_prompt"].isoformat()}
    ]
    edit_calls = [c for c in calls if c[1:3] == ["automations", "edit"]]
    assert len(edit_calls) == 1
    assert edit_calls[0][3] == "job-1"
    assert "--at" in edit_calls[0]
    assert edit_calls[0][edit_calls[0].index("--at") + 1] == plan["wrap_up_prompt"].isoformat()

    # The other two milestones weren't touched by the reschedule case.
    assert len(result["scheduled"]) == 2


def test_schedule_all_ignores_past_milestones(mocker):
    # wrap_up_prompt already happened; the other two are still ahead.
    plan = make_plan(-10, 45, 60)
    mock_resolve_plan(mocker, plan)
    run, calls = mock_subprocess(mocker, existing_jobs=[])

    result = sm.schedule_all()

    scheduled_fields = {item["milestone"] for item in result["scheduled"]}
    assert scheduled_fields == {"get_ready_prompt", "leave_prompt"}

    add_calls = [c for c in calls if c[1:3] == ["automations", "add"]]
    assert len(add_calls) == 2


def test_schedule_all_skips_when_resolve_plan_fails(mocker):
    mocker.patch(
        "schedule_milestones.resolve_plan",
        return_value={"ok": False, "error": "no_upcoming_event", "message": "No upcoming timed events found."},
    )
    run, calls = mock_subprocess(mocker, existing_jobs=[])

    result = sm.schedule_all()

    assert result == {"scheduled": [], "reason": "no_upcoming_event"}
    assert calls == []


def test_schedule_all_skips_when_no_notify_email(mocker):
    plan = make_plan(30, 45, 60)
    mocker.patch(
        "schedule_milestones.resolve_plan",
        return_value={"ok": True, "event": EVENT, "plan": plan, "profile": {}},
    )
    run, calls = mock_subprocess(mocker, existing_jobs=[])

    result = sm.schedule_all()

    assert result == {"scheduled": [], "reason": "no_notify_email"}
    assert calls == []


def test_schedule_all_uses_whatsapp_when_configured(mocker):
    plan = make_plan(30, 45, 60)
    whatsapp_profile = {"notify_channel": "whatsapp", "owner_whatsapp": "+6591112222"}
    mocker.patch(
        "schedule_milestones.resolve_plan",
        return_value={"ok": True, "event": EVENT, "plan": plan, "profile": whatsapp_profile},
    )
    run, calls = mock_subprocess(mocker, existing_jobs=[])

    result = sm.schedule_all()

    assert len(result["scheduled"]) == 3
    add_calls = [c for c in calls if c[1:3] == ["automations", "add"]]
    commands = [c[c.index("--command") + 1] for c in add_calls]
    assert all("whatsapp_send.py" in command for command in commands)
    assert all("gmail_send.py" not in command for command in commands)
    assert all('"+6591112222"' in command for command in commands)


def test_schedule_all_skips_when_whatsapp_configured_but_no_owner_number(mocker):
    plan = make_plan(30, 45, 60)
    whatsapp_profile = {"notify_channel": "whatsapp"}
    mocker.patch(
        "schedule_milestones.resolve_plan",
        return_value={"ok": True, "event": EVENT, "plan": plan, "profile": whatsapp_profile},
    )
    run, calls = mock_subprocess(mocker, existing_jobs=[])

    result = sm.schedule_all()

    assert result == {"scheduled": [], "reason": "no_owner_whatsapp"}
    assert calls == []


def test_build_command_gmail_vs_whatsapp():
    gmail_command = sm._build_command("gmail", "you@example.com", "Subject", "Body text")
    assert "gmail_send.py" in gmail_command
    assert '--subject "Subject"' in gmail_command
    assert '--body "Body text"' in gmail_command

    whatsapp_command = sm._build_command("whatsapp", "+6591112222", "Subject", "Body text")
    assert "whatsapp_send.py" in whatsapp_command
    assert '--to "+6591112222"' in whatsapp_command
    assert "Subject\nBody text" in whatsapp_command
