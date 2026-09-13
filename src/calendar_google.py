"""
Read-only Google Calendar adapter. Finds the next upcoming timed event
(title, start, end, location, attendees) via a browser OAuth flow on
first run, then a cached token thereafter.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


BASE_DIR = Path(__file__).resolve().parent.parent

CREDENTIALS_FILE = BASE_DIR / "calendar_credentials.json"
TOKEN_FILE = BASE_DIR / "calendar_token.json"

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

    now = datetime.now(timezone.utc)

    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now.isoformat(),
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

        # Google's timeMin filters by end time, not start time, so an
        # event already in progress (started, not yet ended) is still
        # returned here. It's not the "next" thing to prepare for, so
        # skip anything that has already started.
        if datetime.fromisoformat(start) <= now:
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
            "end": event.get("end", {}).get("dateTime"),
            "location": event.get("location"),
            "attendees": attendees,
        }

    return None


def get_current_event():
    """
    Find the event happening right now (start <= now < end), if any.
    Used to sanity-check the stored starting location: a location can
    be "fresh" by timestamp yet clearly wrong if the calendar shows
    the user should currently be somewhere else entirely.
    """

    creds = get_credentials()

    service = build(
        "calendar",
        "v3",
        credentials=creds,
    )

    now = datetime.now(timezone.utc)

    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=(now - timedelta(hours=12)).isoformat(),
            timeMax=now.isoformat(),
            maxResults=10,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    for event in result.get("items", []):
        start = event.get("start", {}).get("dateTime")
        end = event.get("end", {}).get("dateTime")

        if not start or not end:
            continue

        if datetime.fromisoformat(start) <= now < datetime.fromisoformat(end):
            return {
                "title": event.get("summary", "Untitled event"),
                "start": start,
                "end": end,
                "location": event.get("location"),
            }

    return None


if __name__ == "__main__":

    event = get_next_event()

    if not event:
        print("No upcoming timed events found.")
    else:
        print(event)