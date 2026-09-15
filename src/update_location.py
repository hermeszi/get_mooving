"""
Confirms the user is still at their stored starting location, or
changes it to a new one — validating any new address through OneMap
first so a typo or ambiguous name can't silently corrupt profile.json.
This is the only script allowed to write data/profile.json's location.
"""

import argparse
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from onemap import search_location, OneMapError, onemap_error_reason


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PROFILE_PATH = DATA_DIR / "profile.json"


def load_profile() -> dict:
    with open(PROFILE_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def save_profile(profile: dict) -> None:
    tmp_fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")

    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as file:
            json.dump(profile, file, indent=2)
            file.write("\n")

        os.replace(tmp_path, PROFILE_PATH)

    except Exception:
        os.unlink(tmp_path)
        raise


def emit_error(reason: str, message: str, **extra) -> None:
    print(json.dumps({"error": reason, "message": message, **extra}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm the current stored location is still correct.",
    )
    parser.add_argument(
        "--address",
        help="Set a new starting location (validated via OneMap).",
    )
    parser.add_argument(
        "--label",
        help="Short name for the new location (used with --address).",
    )
    args = parser.parse_args()

    if not args.confirm and not args.address:
        emit_error("missing_input", "Specify --confirm or --address.")
        return

    profile = load_profile()
    now = datetime.now().astimezone().isoformat()

    if args.address:
        try:
            resolved = search_location(args.address)
        except ValueError as error:
            emit_error("location_not_found", str(error))
            return
        except OneMapError as error:
            emit_error(onemap_error_reason(error), str(error))
            return

        profile["location"] = {
            "label": args.label or "Somewhere else",
            "address": resolved["address"],
            "confirmed_at": now,
        }
    else:
        profile["location"]["confirmed_at"] = now

    save_profile(profile)

    print(json.dumps({
        "status": "ok",
        "location": profile["location"]["label"],
        "confirmed_at": profile["location"]["confirmed_at"],
    }))


if __name__ == "__main__":
    main()
