# Get Mooving

**ADHD-friendly Singapore travel & transition agent.**

This is a setup and usage guide. For *why* it's built this way, see [DEVELOPMENT.md](DEVELOPMENT.md). For the original product pitch and design, see [Get_Mooving.md](Get_Mooving.md).

---

## What it does

Reads your next Google Calendar event, works out real Singapore travel time (OneMap), and tells you when to wrap up, get ready, and leave — instead of just showing a meeting time. If you're running late, it recomputes from right now and can draft (with your approval) a late message to the attendee, sent via Gmail. It can also proactively email you those wrap-up/get-ready/leave-now nudges on a schedule, not just when you ask.

Nothing gets sent anywhere without your explicit approval first.

---

## 1. Prerequisites

- Python 3.12+ and a virtual environment
- [OpenClaw](https://docs.openclaw.ai) installed and running (`openclaw doctor` should be clean)
- A Google account (Calendar + Gmail)
- A free OneMap account (Singapore government routing/geocoding API)

## 2. Install dependencies

```bash
cd get_mooving
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

Everything in this project is run through `.venv/bin/python3` explicitly (never plain `python3`) — OpenClaw runs as a background service and does not inherit your shell's activated virtualenv.

## 3. Connect Google Calendar (read-only)

1. In the [Google Cloud Console](https://console.cloud.google.com), create or select a project, then enable the **Google Calendar API**.
2. Configure the OAuth consent screen (External is fine; add your own Google account as a test user if the app stays in "Testing" mode).
3. Create an OAuth Client ID of type **Desktop app**, then download its JSON.
4. Save that file as `calendar_credentials.json` in the project root (already gitignored).
5. Run:

   ```bash
   .venv/bin/python3 src/calendar_google.py
   ```

   This opens a browser for you to sign in and approve read-only Calendar access, then saves `calendar_token.json` — you won't need to repeat this unless that token is deleted or revoked. It should print your next upcoming event as JSON.

## 4. Connect Gmail (read + send)

Gmail uses a **separate** OAuth client from Calendar — a different Google Cloud project/client is fine, or the same project with the Gmail API also enabled.

1. In the same or a new Cloud project, enable the **Gmail API**.
2. Create another OAuth Client ID (Desktop app), download it, save as `gmail_credentials.json` in the project root.
3. Run:

   ```bash
   .venv/bin/python3 -c "from sys import path; path.insert(0,'src'); from gmail_send import get_credentials; get_credentials()"
   ```

   Approve access when the browser opens (scopes: read + send). This saves `gmail_token.json`.
4. Confirm it works by sending yourself a test email:

   ```bash
   .venv/bin/python3 src/gmail_send.py --to "you@example.com" --subject "Test" --body "It works."
   ```

## 5. Get a OneMap API token

OneMap (Singapore's routing/geocoding API) needs a free account and a token — separate from Google entirely.

1. Register at [onemap.gov.sg](https://www.onemap.gov.sg) for API access.
2. Get a token (check [their API docs](https://www.onemap.gov.sg/apidocs/) for the current method — typically a POST request to their auth endpoint with your registered email/password, returning a bearer token).
3. Copy `.env.example` to `.env` and paste the token in:

   ```bash
   cp .env.example .env
   # then edit .env: ONEMAP_TOKEN=<your token>
   ```

**OneMap tokens expire roughly every 3 days.** When `onemap.py` calls start failing with an auth error, repeat step 2 and update `.env` — there's no automatic refresh built in yet.

## 6. Set your profile

```bash
cp data/profile.example.json data/profile.json
```

Edit `data/profile.json`:

- `location.address` — your default starting address (home). `confirmed_at` gets managed automatically by the app from here on — leave it as-is.
- `notify_email` — where proactive reminders and automated notifications go (usually your own address).
- `buffers` — your personal prep/task-switch/early-arrival minutes; tune these to how you actually operate.

```bash
cp data/trusted_contacts.example.json data/trusted_contacts.json
```

Edit `data/trusted_contacts.json` — emails (and, reserved for future use, phone numbers) of people whose *replies* to a late-message should be treated as trusted. Your own Gmail address is always trusted automatically; this file is for everyone else. **Only edit this file by hand** — the agent is deliberately never allowed to add to it itself.

All four files above (`.env`, `data/profile.json`, `data/trusted_contacts.json`, and both credential/token pairs) are gitignored — never commit them.

## 7. Install the skill into OpenClaw

```bash
openclaw skills install ./skills/get_mooving --as get-mooving --force
openclaw gateway restart
```

Repeat both commands any time you edit `skills/get_mooving/SKILL.md`. If OpenClaw seems to be answering from stale memory after a change, also start a fresh session:

```bash
openclaw agent --agent main --message "/new"
```

## 8. Use it

Talk to your OpenClaw agent normally — no special syntax:

```bash
openclaw agent --agent main --message "when should I leave for my next meeting?"
openclaw agent --agent main --message "I'm running late"
openclaw agent --agent main --message "what if I leave at 10:30 by taxi?"
openclaw agent --agent main --message "did anyone reply to my late message?"
```

Or in whatever chat surface your OpenClaw is connected to — same skill, same behavior.

The first time it asks "Still starting from Home?", answer it (or run `.venv/bin/python3 src/update_location.py --confirm` directly) — this is the location-freshness check, and it re-asks every 2 hours.

## 9. Proactive reminders (optional)

The ⏳🎒🚪 nudges (emailed automatically, no need to ask) run on two scripts that are built and tested but **not scheduled by default**:

```bash
.venv/bin/python3 src/schedule_milestones.py --json   # schedules today's reminder emails
.venv/bin/python3 src/gmail_check_replies.py --json   # checks for new replies
```

To make either run on its own schedule, use the **full absolute path** to `.venv/bin/python3` — not a relative one. A recurring automation doesn't execute from this project's directory, so a relative `.venv/bin/python3` resolves against whatever Python it happens to find there instead, missing every package this project needs (confirmed by hitting exactly this: `ModuleNotFoundError: No module named 'google'`):

```bash
openclaw automations add --every 30m --name gm-schedule-milestones \
  --command "/home/ming/42/openclaw/get_mooving/.venv/bin/python3 /home/ming/42/openclaw/get_mooving/src/schedule_milestones.py" \
  --no-deliver
```

`add` prints the new job's `id` in its JSON output. To make it check immediately as well as on the recurring schedule (an `--every` job's first run only happens after the full interval, not right away):

```bash
openclaw automations run <id>
```

This runs it once immediately without disturbing the recurring schedule. List/remove with `openclaw automations list` / `openclaw automations rm <id>` (both need the job's `id`, not its `--name`).

## 10. Disconnecting / privacy

Everything this project stores locally, and how to remove it:

| What | Where | To remove |
|---|---|---|
| Calendar access | Google account | [myaccount.google.com/permissions](https://myaccount.google.com/permissions) → remove the app; delete `calendar_credentials.json` and `calendar_token.json` |
| Gmail access | Google account | Same page, remove the app; delete `gmail_credentials.json` and `gmail_token.json` |
| OneMap token | `.env` | Delete the file, or blank `ONEMAP_TOKEN=` |
| Home address, buffers | `data/profile.json` | Delete the file (falls back to needing re-setup, step 6) |
| Trusted contacts | `data/trusted_contacts.json` | Delete the file |
| Sent-message thread history | `data/watched_threads.json` | Delete the file |
| Proactive schedules | OpenClaw automations | `openclaw automations list` then `rm` any `gm-*` jobs |
| The skill itself | OpenClaw | `openclaw skills remove get-mooving` (or your platform's equivalent) |

Deleting the `data/*.json` files (all gitignored, all local-only) removes every piece of personal data this project holds — nothing is stored anywhere else.

---

For the reasoning behind every design decision above (why two separate Google OAuth clients, why replies are filtered through an allowlist, why sending always needs approval, etc.), see [DEVELOPMENT.md](DEVELOPMENT.md).
