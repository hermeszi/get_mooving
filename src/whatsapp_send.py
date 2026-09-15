"""
Sends an outbound WhatsApp message via OpenClaw's own channel CLI
(`openclaw message send`) — used only for proactive/out-of-band sends
(a scheduled milestone reminder, relaying a trusted contact's message
to the owner). Never used to reply within a live WhatsApp conversation
— OpenClaw already delivers the agent's own turn response back through
whichever channel the inbound message arrived on; sending a second,
separate message on top of that would just double up.
"""

import argparse
import json
import subprocess


def send_whatsapp(to: str, message: str) -> dict:
    result = subprocess.run(
        [
            "openclaw", "message", "send",
            "--channel", "whatsapp",
            "--target", to,
            "--message", message,
            "--json",
        ],
        capture_output=True,
        text=True,
    )

    try:
        payload = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return {
            "error": "send_failed",
            "message": (result.stderr or result.stdout or "openclaw returned no output.").strip(),
        }

    if payload.get("ok") is False:
        error = payload.get("error") or {}
        return {
            "error": "send_failed",
            "message": error.get("message", "openclaw reported a failure with no message."),
        }

    return {"status": "sent", "to": to}


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--to", required=True, help="Recipient's WhatsApp number, E.164 format.")
    parser.add_argument("--message", required=True)

    args = parser.parse_args()

    print(json.dumps(send_whatsapp(args.to, args.message)))


if __name__ == "__main__":
    main()
