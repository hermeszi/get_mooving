"""
Scans the inbox for new messages from trusted senders — not replies to
a thread this agent already sent (that's gmail_check_replies.py's
job; this script explicitly skips anything in a currently-watched
thread, so the same message is never handled by both paths). Only
trusted_contacts.json senders (plus the connected account itself) are
ever surfaced; everyone else is silently skipped and never re-checked
again, keeping an otherwise-open inbox bounded to an explicit
allowlist.
"""

import argparse
import json
import os
import tempfile

from googleapiclient.discovery import build

from gmail_send import get_credentials, DATA_DIR
from gmail_check_replies import load_trusted_emails, load_watched_threads, extract_address
from planner import load_json


WATERMARK_FILE = DATA_DIR / "inbox_watermark.json"


def load_watermark() -> int:
    if not WATERMARK_FILE.exists():
        return 0

    with open(WATERMARK_FILE, "r", encoding="utf-8") as file:
        return json.load(file).get("last_seen_internal_date_ms", 0)


def save_watermark(value: int) -> None:
    tmp_fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")

    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as file:
            json.dump({"last_seen_internal_date_ms": value}, file, indent=2)
            file.write("\n")

        os.replace(tmp_path, WATERMARK_FILE)

    except Exception:
        os.unlink(tmp_path)
        raise


def check_inbox() -> list:
    """
    Returns new inbox messages from trusted senders since the last
    check. The watermark advances past every message inspected
    (trusted or not) so an untrusted sender's mail is never re-checked
    forever — it's just never surfaced.
    """

    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)

    my_email = service.users().getProfile(userId="me").execute()["emailAddress"].lower()
    owner_email = (load_json("profile.json").get("notify_email") or "").lower()
    trusted_emails = load_trusted_emails() | {my_email}

    watched_thread_ids = {entry["thread_id"] for entry in load_watched_threads()}

    watermark = load_watermark()
    max_seen = watermark

    result = (
        service.users()
        .messages()
        .list(userId="me", labelIds=["INBOX"], maxResults=20)
        .execute()
    )

    new_messages = []

    for item in result.get("messages", []):
        if item["threadId"] in watched_thread_ids:
            continue

        message = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=item["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            )
            .execute()
        )

        internal_date = int(message.get("internalDate", 0))

        if internal_date <= watermark:
            continue

        max_seen = max(max_seen, internal_date)

        headers = {h["name"]: h["value"] for h in message["payload"]["headers"]}
        sender = headers.get("From", "")
        sender_address = extract_address(sender)

        if sender_address not in trusted_emails:
            continue

        new_messages.append({
            "message_id": message["id"],
            "thread_id": message["threadId"],
            "from": sender,
            "subject": headers.get("Subject", ""),
            "snippet": message.get("snippet", ""),
            "received_at": headers.get("Date", ""),
            "is_owner": sender_address == owner_email,
        })

    save_watermark(max_seen)

    return new_messages


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result (or any failure) as JSON instead of text.",
    )
    args = parser.parse_args()

    try:
        messages = check_inbox()
    except Exception as error:
        if args.json:
            print(json.dumps({"error": "check_failed", "message": str(error)}))
        else:
            print(f"Could not check the inbox: {error}")
        return

    if args.json:
        print(json.dumps({"messages": messages}))
    elif not messages:
        print("No new messages.")
    else:
        for message in messages:
            who = "owner" if message["is_owner"] else "trusted contact"
            print(f"- {message['from']} ({who}): {message['subject']} — {message['snippet']}")


if __name__ == "__main__":
    main()
