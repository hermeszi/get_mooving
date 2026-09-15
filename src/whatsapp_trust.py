"""
Classifies a WhatsApp sender's phone number into a trust tier — the
same deterministic-check pattern gmail_check_inbox.py/
gmail_check_replies.py use for is_owner, just phone-based instead of
email-based. The agent must never decide someone's trust tier itself
from a number it saw in chat; it always calls this script and acts on
the tier it returns, same as it never trusts an email's display name
over extract_address()'s result.

Three tiers:
  "owner"   — profile.json's owner_whatsapp. Full access, same as any
              other channel the owner uses.
  "trusted" — data/trusted_contacts.json's "phones" list. Relay-only:
              SKILL.md must never reveal calendar/location/travel
              details to this tier, only accept a message to relay to
              the owner (see SKILL.md's "WhatsApp Channel" section).
  "unknown" — anyone else. Reject/ignore. In practice this should be
              rare here — the gateway's own dmPolicy/allowFrom should
              already stop an unrecognized number from ever reaching
              the agent (see SETUP.md) — this is a deterministic
              backstop in case that config is ever loosened, not the
              primary defense.
"""

import argparse
import json
import re

from planner import load_json, DATA_DIR


TRUSTED_CONTACTS_FILE = DATA_DIR / "trusted_contacts.json"


def normalize_phone(phone: str) -> str:
    """E.164-ish normalization: keep a leading '+' and digits only, so
    formatting differences (spaces, dashes, parentheses) between what
    profile.json/trusted_contacts.json store and what the channel
    reports don't cause a false "unknown"."""

    if not phone:
        return ""

    digits = re.sub(r"[^\d+]", "", phone)

    if not digits.startswith("+"):
        digits = f"+{digits}"

    return digits


def load_trusted_phones() -> set:
    if not TRUSTED_CONTACTS_FILE.exists():
        return set()

    with open(TRUSTED_CONTACTS_FILE, "r", encoding="utf-8") as file:
        contacts = json.load(file)

    return {normalize_phone(phone) for phone in contacts.get("phones", [])}


def classify(phone: str) -> str:
    normalized = normalize_phone(phone)

    if not normalized:
        return "unknown"

    profile = load_json("profile.json")
    owner_phone = normalize_phone(profile.get("owner_whatsapp") or "")

    if owner_phone and normalized == owner_phone:
        return "owner"

    if normalized in load_trusted_phones():
        return "trusted"

    return "unknown"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phone",
        required=True,
        help="Sender's WhatsApp number, as shown in this turn's channel context.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as JSON instead of plain text.",
    )
    args = parser.parse_args()

    tier = classify(args.phone)

    if args.json:
        print(json.dumps({"phone": normalize_phone(args.phone), "tier": tier}))
    else:
        print(tier)


if __name__ == "__main__":
    main()
