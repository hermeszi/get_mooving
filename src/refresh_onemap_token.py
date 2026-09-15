"""
Fetches a fresh OneMap access token and writes it straight into .env,
replacing ONEMAP_TOKEN in place — the manual "get a new token every 3
days" step (SETUP.md step 5) that onemap.py's own error messages ask
for ("Please implement automatic renewal"). Needs ONEMAP_EMAIL and
ONEMAP_PASSWORD in .env (your OneMap account login, not the token
itself) — never printed, never committed (.env is gitignored, same as
the token).
"""

import argparse
import json
import os
import requests

from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

AUTH_URL = "https://www.onemap.gov.sg/api/auth/post/getToken"


def fetch_token(email: str, password: str) -> dict:
    response = requests.post(
        AUTH_URL,
        json={"email": email, "password": password},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def write_token_to_env(token: str) -> None:
    """
    Replace the ONEMAP_TOKEN= line in .env in place, preserving every
    other line — never rewrite the whole file, since .env may hold
    ONEMAP_EMAIL/ONEMAP_PASSWORD (and anything else added by hand)
    alongside it.
    """

    lines = ENV_FILE.read_text().splitlines(keepends=True) if ENV_FILE.exists() else []
    replaced = False
    new_lines = []

    for line in lines:
        if line.startswith("ONEMAP_TOKEN="):
            new_lines.append(f"ONEMAP_TOKEN={token}\n")
            replaced = True
        else:
            new_lines.append(line)

    if not replaced:
        new_lines.append(f"ONEMAP_TOKEN={token}\n")

    ENV_FILE.write_text("".join(new_lines))


def refresh() -> dict:
    load_dotenv()

    email = os.getenv("ONEMAP_EMAIL")
    password = os.getenv("ONEMAP_PASSWORD")

    if not email or not password:
        return {
            "error": "missing_credentials",
            "message": "Set ONEMAP_EMAIL and ONEMAP_PASSWORD in .env first (see SETUP.md step 5).",
        }

    try:
        data = fetch_token(email, password)
    except requests.exceptions.HTTPError as error:
        return {
            "error": "onemap_login_failed",
            "message": f"OneMap rejected the login (check ONEMAP_EMAIL/ONEMAP_PASSWORD): {error}",
        }
    except requests.exceptions.RequestException as error:
        return {"error": "onemap_unreachable", "message": f"Could not reach OneMap: {error}"}

    token = data.get("access_token")

    if not token:
        return {
            "error": "onemap_login_failed",
            "message": f"OneMap's response had no access_token: {data}",
        }

    write_token_to_env(token)

    expiry_timestamp = data.get("expiry_timestamp")
    expires_at = (
        datetime.fromtimestamp(int(expiry_timestamp), tz=timezone.utc).isoformat()
        if expiry_timestamp else None
    )

    return {"status": "refreshed", "expires_at": expires_at}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result (or any failure) as JSON instead of text.",
    )
    args = parser.parse_args()

    result = refresh()

    if args.json:
        print(json.dumps(result))
    elif "error" in result:
        print(f"{result['error']}: {result['message']}")
    else:
        print(f"ONEMAP_TOKEN refreshed. Expires at {result['expires_at']}.")


if __name__ == "__main__":
    main()
