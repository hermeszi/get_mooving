"""
whatsapp_trust.py is the deterministic gate between "a number the
agent was shown in a WhatsApp turn" and "what that sender is allowed
to do" (SKILL.md's owner/trusted/unknown tiers) — the phone-number
equivalent of gmail_check_inbox.py's is_owner check, so it gets the
same kind of test coverage: fresh, normalized, missing, and each tier.
"""

import json

import whatsapp_trust as wt


OWNER = "+6591112222"
FRIEND = "+6593334444"
STRANGER = "+6599998888"


def _set_owner(monkeypatch, owner_phone):
    monkeypatch.setattr(
        wt,
        "load_json",
        lambda filename: {"owner_whatsapp": owner_phone},
    )


def _set_trusted_contacts(tmp_path, monkeypatch, phones):
    contacts_file = tmp_path / "trusted_contacts.json"
    contacts_file.write_text(json.dumps({"phones": phones}))
    monkeypatch.setattr(wt, "TRUSTED_CONTACTS_FILE", contacts_file)


def test_normalize_phone_strips_formatting():
    assert wt.normalize_phone("+65 9111 2222") == "+6591112222"
    assert wt.normalize_phone("(65) 9111-2222") == "+6591112222"


def test_normalize_phone_adds_missing_plus():
    assert wt.normalize_phone("6591112222") == "+6591112222"


def test_normalize_phone_empty_input():
    assert wt.normalize_phone("") == ""
    assert wt.normalize_phone(None) == ""


def test_classify_owner(tmp_path, monkeypatch):
    _set_owner(monkeypatch, OWNER)
    _set_trusted_contacts(tmp_path, monkeypatch, [FRIEND])

    assert wt.classify(OWNER) == "owner"


def test_classify_owner_matches_despite_formatting_differences(tmp_path, monkeypatch):
    _set_owner(monkeypatch, "+65 9111 2222")
    _set_trusted_contacts(tmp_path, monkeypatch, [])

    assert wt.classify("6591112222") == "owner"


def test_classify_trusted_contact(tmp_path, monkeypatch):
    _set_owner(monkeypatch, OWNER)
    _set_trusted_contacts(tmp_path, monkeypatch, [FRIEND])

    assert wt.classify(FRIEND) == "trusted"


def test_classify_unknown_number(tmp_path, monkeypatch):
    _set_owner(monkeypatch, OWNER)
    _set_trusted_contacts(tmp_path, monkeypatch, [FRIEND])

    assert wt.classify(STRANGER) == "unknown"


def test_classify_missing_phone_is_unknown(tmp_path, monkeypatch):
    _set_owner(monkeypatch, OWNER)
    _set_trusted_contacts(tmp_path, monkeypatch, [FRIEND])

    assert wt.classify("") == "unknown"


def test_classify_no_owner_configured_yet(tmp_path, monkeypatch):
    # A profile.json that predates owner_whatsapp shouldn't crash —
    # just nobody qualifies for the "owner" tier.
    _set_owner(monkeypatch, None)
    _set_trusted_contacts(tmp_path, monkeypatch, [FRIEND])

    assert wt.classify(FRIEND) == "trusted"
    assert wt.classify(STRANGER) == "unknown"


def test_load_trusted_phones_missing_file_returns_empty_set(tmp_path, monkeypatch):
    monkeypatch.setattr(wt, "TRUSTED_CONTACTS_FILE", tmp_path / "does_not_exist.json")

    assert wt.load_trusted_phones() == set()
