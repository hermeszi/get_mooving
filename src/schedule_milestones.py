"""
Proactive reminders: computes the next event's wrap-up/get-ready/
leave-now times and schedules a one-shot OpenClaw automation for each
one still in the future, which notifies the user (via gmail_send.py or
whatsapp_send.py, per profile.json's notify_channel) exactly when it
fires. Deliberately a command payload, not an agent prompt — the
content is fully known in advance, so there's no judgment call left
for a model to make. Safe to run repeatedly: checks what's already
scheduled first (openclaw automations add's --declaration-key does NOT
dedupe on its own — confirmed by testing) and only adds what's
missing.
"""

import argparse
import json
import subprocess
from datetime import datetime

from planner import resolve_plan, format_time, BASE_DIR


VENV_PYTHON = BASE_DIR / ".venv" / "bin" / "python3"
GMAIL_SEND = BASE_DIR / "src" / "gmail_send.py"
WHATSAPP_SEND = BASE_DIR / "src" / "whatsapp_send.py"

MILESTONES = [
    ("wrap_up_prompt", "⏳ Wrap this up"),
    ("get_ready_prompt", "🎒 Get ready"),
    ("leave_prompt", "🚪 Go now"),
]


def existing_jobs() -> dict:
    """
    openclaw automations add's --declaration-key does NOT dedupe on its
    own (confirmed by testing: re-running with the same key created a
    second job). So idempotency is handled here instead: check what's
    already scheduled before adding anything — keyed by declarationKey,
    with each job's id and current "at" time, so a stale time (e.g. the
    origin location changed after the first schedule) can be corrected
    instead of silently left wrong.
    """

    result = subprocess.run(
        ["openclaw", "automations", "list", "--json"],
        check=True,
        capture_output=True,
        text=True,
    )

    jobs = json.loads(result.stdout).get("jobs", [])

    return {
        job["declarationKey"]: {"id": job["id"], "at": job.get("schedule", {}).get("at")}
        for job in jobs
        if job.get("declarationKey")
    }


def _notify_target(profile: dict):
    """
    Which channel/address to notify on, per profile.json's
    notify_channel (defaults to "gmail" for existing profiles that
    predate WhatsApp support). Returns (channel, target) or
    (None, reason) if the chosen channel isn't configured.
    """

    channel = profile.get("notify_channel", "gmail")

    if channel == "whatsapp":
        target = profile.get("owner_whatsapp")
        return (channel, target) if target else (None, "no_owner_whatsapp")

    target = profile.get("notify_email")
    return (channel, target) if target else (None, "no_notify_email")


def _build_command(channel: str, target: str, subject: str, body: str) -> str:
    if channel == "whatsapp":
        message = f"{subject}\n{body}"
        return f'{VENV_PYTHON} {WHATSAPP_SEND} --to "{target}" --message "{message}"'

    return f'{VENV_PYTHON} {GMAIL_SEND} --to "{target}" --subject "{subject}" --body "{body}"'


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

    channel, target = _notify_target(profile)

    if not channel:
        return {"scheduled": [], "reason": target}

    now = datetime.now().astimezone()
    existing = existing_jobs()
    scheduled = []
    rescheduled = []

    for field, label in MILESTONES:
        when = plan[field]

        if when <= now:
            continue

        key = f"gm-{field}-{event['start']}"
        existing_job = existing.get(key)

        if existing_job:
            existing_at = existing_job["at"]

            # Compare as real datetimes, not raw strings — same instant
            # can be written with a different offset/precision and
            # still be correct.
            if existing_at and datetime.fromisoformat(existing_at.replace("Z", "+00:00")) == when:
                continue

            # A job exists for this milestone but at the wrong time —
            # e.g. the starting location was corrected after the first
            # schedule, shifting every computed time. Fix it in place
            # rather than leaving a stale reminder sitting there.
            subprocess.run(
                [
                    "openclaw", "automations", "edit", existing_job["id"],
                    "--at", when.isoformat(),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            rescheduled.append({"milestone": field, "label": label, "at": when.isoformat()})
            continue

        subject = f"{label} — {event['title']}"
        body = (
            f"{label} for {event['title']} at {event['location']}. "
            f"Meeting at {format_time(plan['meeting_time'])}."
        )

        command = _build_command(channel, target, subject, body)

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

    return {"scheduled": scheduled, "rescheduled": rescheduled}


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
    elif not result["scheduled"] and not result.get("rescheduled"):
        print(f"Nothing scheduled ({result.get('reason', 'no future milestones')}).")
    else:
        for item in result["scheduled"]:
            print(f"- {item['label']} at {item['at']}")
        for item in result.get("rescheduled", []):
            print(f"- {item['label']} corrected to {item['at']}")


if __name__ == "__main__":
    main()
