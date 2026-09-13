"""
Proactive reminders: computes the next event's wrap-up/get-ready/
leave-now times and schedules a one-shot OpenClaw automation for each
one still in the future, which emails the user (via gmail_send.py)
exactly when it fires. Deliberately a command payload, not an agent
prompt — the content is fully known in advance, so there's no judgment
call left for a model to make. Safe to run repeatedly: checks what's
already scheduled first (openclaw automations add's --declaration-key
does NOT dedupe on its own — confirmed by testing) and only adds
what's missing.
"""

import argparse
import json
import subprocess
from datetime import datetime

from planner import resolve_plan, format_time, BASE_DIR


VENV_PYTHON = BASE_DIR / ".venv" / "bin" / "python3"
GMAIL_SEND = BASE_DIR / "src" / "gmail_send.py"

MILESTONES = [
    ("wrap_up_prompt", "⏳ Wrap this up"),
    ("get_ready_prompt", "🎒 Get ready"),
    ("leave_prompt", "🚪 Go now"),
]


def existing_declaration_keys() -> set:
    """
    openclaw automations add's --declaration-key does NOT dedupe on its
    own (confirmed by testing: re-running with the same key created a
    second job). So idempotency is handled here instead: check what's
    already scheduled before adding anything.
    """

    result = subprocess.run(
        ["openclaw", "automations", "list", "--json"],
        check=True,
        capture_output=True,
        text=True,
    )

    jobs = json.loads(result.stdout).get("jobs", [])

    return {job.get("declarationKey") for job in jobs if job.get("declarationKey")}


def schedule_all() -> dict:
    """
    Ensure a one-shot reminder is scheduled for every milestone of the
    next event that hasn't happened yet. Safe to call repeatedly (e.g.
    from a periodic maintenance job) — see existing_declaration_keys().
    """

    result = resolve_plan()

    if not result["ok"]:
        return {"scheduled": [], "reason": result["error"]}

    event = result["event"]
    plan = result["plan"]
    profile = result["profile"]

    notify_email = profile.get("notify_email")

    if not notify_email:
        return {"scheduled": [], "reason": "no_notify_email"}

    now = datetime.now().astimezone()
    existing_keys = existing_declaration_keys()
    scheduled = []

    for field, label in MILESTONES:
        when = plan[field]

        if when <= now:
            continue

        key = f"gm-{field}-{event['start']}"

        if key in existing_keys:
            continue

        subject = f"{label} — {event['title']}"
        body = (
            f"{label} for {event['title']} at {event['location']}. "
            f"Meeting at {format_time(plan['meeting_time'])}."
        )

        command = (
            f'{VENV_PYTHON} {GMAIL_SEND} '
            f'--to "{notify_email}" --subject "{subject}" --body "{body}"'
        )

        subprocess.run(
            [
                "openclaw", "automations", "add",
                "--at", when.isoformat(),
                "--name", key,
                "--command", command,
                "--declaration-key", key,
                "--delete-after-run",
                "--no-deliver",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        scheduled.append({"milestone": field, "label": label, "at": when.isoformat()})

    return {"scheduled": scheduled}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as JSON instead of text.",
    )
    args = parser.parse_args()

    result = schedule_all()

    if args.json:
        print(json.dumps(result))
    elif not result["scheduled"]:
        print(f"Nothing scheduled ({result.get('reason', 'no future milestones')}).")
    else:
        for item in result["scheduled"]:
            print(f"- {item['label']} at {item['at']}")


if __name__ == "__main__":
    main()
