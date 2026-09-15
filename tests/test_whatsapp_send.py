"""
whatsapp_send.py wraps `openclaw message send` and must turn every one
of its failure shapes into the project's standard {"error", "message"}
JSON — never a raw subprocess/JSON-decode error. Mirrors how
test_onemap.py treats an external command's failure modes as data to
be classified, not exceptions to let escape.
"""

import json

from whatsapp_send import send_whatsapp


def _completed(stdout="", stderr=""):
    class Result:
        pass

    result = Result()
    result.stdout = stdout
    result.stderr = stderr
    return result


def test_send_whatsapp_success(mocker):
    mocker.patch(
        "whatsapp_send.subprocess.run",
        return_value=_completed(stdout=json.dumps({"ok": True, "id": "wamid.abc123"})),
    )

    result = send_whatsapp("+6591112222", "Wrap this up soon")

    assert result == {"status": "sent", "to": "+6591112222"}


def test_send_whatsapp_channel_error(mocker):
    # The real shape confirmed live: `openclaw message send` returns
    # this before WhatsApp is even linked.
    mocker.patch(
        "whatsapp_send.subprocess.run",
        return_value=_completed(stdout=json.dumps({
            "ok": False,
            "error": {"type": "cli_error", "message": "Channel is unavailable: whatsapp"},
        })),
    )

    result = send_whatsapp("+6591112222", "Wrap this up soon")

    assert result == {"error": "send_failed", "message": "Channel is unavailable: whatsapp"}


def test_send_whatsapp_non_json_output_does_not_crash(mocker):
    mocker.patch(
        "whatsapp_send.subprocess.run",
        return_value=_completed(stdout="", stderr="openclaw: command not found"),
    )

    result = send_whatsapp("+6591112222", "Wrap this up soon")

    assert result["error"] == "send_failed"
    assert "command not found" in result["message"]
