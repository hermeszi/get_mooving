from datetime import datetime, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


BASE_DIR = Path(__file__).resolve().parent.parent

CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly"
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


def get_next_event():
    creds = get_credentials()

    service = build(
        "calendar",
        "v3",
        credentials=creds,
    )

    now = datetime.now(timezone.utc).isoformat()

    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now,
            maxResults=10,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = result.get("items", [])

    for event in events:

        # Ignore all-day events for the MVP
        start = event.get("start", {}).get("dateTime")

        if not start:
            continue

        attendees = []

        for attendee in event.get("attendees", []):
            attendees.append({
                "email": attendee.get("email"),
                "name": attendee.get("displayName"),
            })

        return {
            "title": event.get(
                "summary",
                "Untitled event",
            ),
            "start": start,
            "location": event.get("location"),
            "attendees": attendees,
        }

    return None


if __name__ == "__main__":

    event = get_next_event()

    if not event:
        print("No upcoming timed events found.")
    else:
        print(event)