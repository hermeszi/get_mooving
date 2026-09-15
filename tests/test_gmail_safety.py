"""
The one security-relevant rule in the Gmail scripts: a reply/inbox
message is trusted by its real address, never by its display name,
which can say anything. extract_address() is where that's enforced;
load_trusted_emails() is the allowlist it's checked against. Both are
pure/file-only, tested without any real Gmail account.
"""

import json

import gmail_check_replies as gcr


def test_extract_address_from_display_name_and_address():
    assert gcr.extract_address("Sarah <sarah@example.com>") == "sarah@example.com"


def test_extract_address_lowercases():
    assert gcr.extract_address("Sarah <Sarah@Example.com>") == "sarah@example.com"


def test_extract_address_bare_address_no_display_name():
    assert gcr.extract_address("sarah@example.com") == "sarah@example.com"


def test_extract_address_spoofed_display_name_does_not_fool_it():
    # A display name claiming to be a trusted contact, but the real
    # address behind it belongs to someone else entirely — the address
    # is what must be checked against the allowlist, and this is what
    # extract_address() must actually return.
    spoofed = '"mingde@gmail.com" <attacker@evil.com>'
    assert gcr.extract_address(spoofed) == "attacker@evil.com"


def test_load_trusted_emails_reads_and_lowercases(tmp_path, monkeypatch):
    contacts_file = tmp_path / "trusted_contacts.json"
    contacts_file.write_text(json.dumps({"emails": ["Sarah@Example.com"]}))
    monkeypatch.setattr(gcr, "TRUSTED_CONTACTS_FILE", contacts_file)

    assert gcr.load_trusted_emails() == {"sarah@example.com"}


def test_load_trusted_emails_missing_file_returns_empty_set(tmp_path, monkeypatch):
    monkeypatch.setattr(gcr, "TRUSTED_CONTACTS_FILE", tmp_path / "does_not_exist.json")

    assert gcr.load_trusted_emails() == set()
