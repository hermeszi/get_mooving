import argparse
import json
import os
import tempfile

from email.utils import parseaddr

from googleapiclient.discovery import build

from gmail_send import get_credentials, DATA_DIR, WATCHED_THREADS_FILE


TRUSTED_CONTACTS_FILE = DATA_DIR / "trusted_contacts.json"


def load_watched_threads() -> list:
    if not WATCHED_THREADS_FILE.exists():
        return []

    with open(WATCHED_THREADS_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def load_trusted_emails() -> set:
    if not TRUSTED_CONTACTS_FILE.exists():
        return set()

    with open(TRUSTED_CONTACTS_FILE, "r", encoding="utf-8") as file:
        contacts = json.load(file)

    return {email.lower() for email in contacts.get("emails", [])}


def extract_address(header_value: str) -> str:
    """
    Pull the real address out of a From header, e.g.
    'Sarah <sarah@example.com>' -> 'sarah@example.com'. Never trust a
    display name alone — it can say anything.
    """

    return parseaddr(header_value)[1].lower()


def save_watched_threads(threads: list) -> None:
    tmp_fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")

    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as file:
            json.dump(threads, file, indent=2)
            file.write("\n")

        os.replace(tmp_path, WATCHED_THREADS_FILE)

    except Exception:
        os.unlink(tmp_path)
        raise


def check_replies() -> list:
    """
    Check every watched thread for a reply from someone other than us.
    Replied threads are removed from the watch list (handled, won't be
    reported again); threads with no reply yet stay watched.
    """

    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)

    my_email = service.users().getProfile(userId="me").execute()["emailAddress"].lower()
    trusted_emails = load_trusted_emails() | {my_email}

    watched = load_watched_threads()
    still_watching = []
    replies = []

    for entry in watched:
        thread = (
            service.users()
            .threads()
            .get(
                userId="me",
                id=entry["thread_id"],
                format="metadata",
                metadataHeaders=["From", "Date"],
            )
            .execute()
        )

        reply = None

        for message in thread.get("messages", []):
            if message["id"] == entry["sent_message_id"]:
                continue

            headers = {h["name"]: h["value"] for h in message["payload"]["headers"]}
            sender = headers.get("From", "")
            sender_address = extract_address(sender)

            if sender_address != my_email:
                reply = {
                    "from": sender,
                    "snippet": message.get("snippet", ""),
                    "received_at": headers.get("Date", ""),
                    "trusted": sender_address in trusted_emails,
                }
                break

        if reply:
            replies.append({
                "thread_id": entry["thread_id"],
                "to": entry["to"],
                "context": entry["context"],
                **reply,
            })
        else:
            still_watching.append(entry)

    save_watched_threads(still_watching)

    return replies


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result (or any failure) as JSON instead of text.",
    )
    args = parser.parse_args()

    try:
        replies = check_replies()
    except Exception as error:
        if args.json:
            print(json.dumps({"error": "check_failed", "message": str(error)}))
        else:
            print(f"Could not check for replies: {error}")
        return

    if args.json:
        print(json.dumps({"replies": replies}))
    elif not replies:
        print("No new replies.")
    else:
        for reply in replies:
            flag = "" if reply["trusted"] else " [UNRECOGNIZED SENDER]"
            print(f"- {reply['from']}{flag} replied about '{reply['context']}': {reply['snippet']}")


if __name__ == "__main__":
    main()
