import argparse
import base64
import json
import os
import tempfile

from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

CREDENTIALS_FILE = BASE_DIR / "gmail_credentials.json"
TOKEN_FILE = BASE_DIR / "gmail_token.json"
WATCHED_THREADS_FILE = DATA_DIR / "watched_threads.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


def get_credentials():
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(
            TOKEN_FILE,
            SCOPES,
        )

    if not creds or not creds.valid:

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE,
                SCOPES,
            )

            creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(creds.to_json())

    return creds


def watch_thread(thread_id: str, message_id: str, to: str, context: str) -> None:
    """
    Remember a sent thread so gmail_check_replies.py can later check
    whether the recipient replied.
    """

    threads = []

    if WATCHED_THREADS_FILE.exists():
        with open(WATCHED_THREADS_FILE, "r", encoding="utf-8") as file:
            threads = json.load(file)

    threads.append({
        "thread_id": thread_id,
        "sent_message_id": message_id,
        "to": to,
        "context": context,
        "sent_at": datetime.now().astimezone().isoformat(),
    })

    tmp_fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")

    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as file:
            json.dump(threads, file, indent=2)
            file.write("\n")

        os.replace(tmp_path, WATCHED_THREADS_FILE)

    except Exception:
        os.unlink(tmp_path)
        raise


def send_email(to: str, subject: str, body: str) -> dict:
    creds = get_credentials()

    service = build(
        "gmail",
        "v1",
        credentials=creds,
    )

    message = EmailMessage()

    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    encoded_message = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode()

    result = (
        service.users()
        .messages()
        .send(
            userId="me",
            body={"raw": encoded_message},
        )
        .execute()
    )

    watch_thread(result.get("threadId"), result.get("id"), to, subject)

    return {
        "status": "sent",
        "message_id": result.get("id"),
        "to": to,
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--to", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--body", required=True)

    args = parser.parse_args()

    try:
        result = send_email(
            args.to,
            args.subject,
            args.body,
        )

        print(json.dumps(result))

    except Exception as error:

        print(json.dumps({
            "error": "send_failed",
            "message": str(error),
        }))


if __name__ == "__main__":
    main()