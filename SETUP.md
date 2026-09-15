# Setup

One-time setup: install dependencies, connect Google Calendar and Gmail, get a OneMap token, configure your profile, and install the skill into OpenClaw.

Once this is done, see **[OPERATING.md](OPERATING.md)** for day-to-day use.

---

## File structure

```text
get_mooving/
├── README.md               quick overview + links to the other docs
├── SETUP.md                 this file
├── OPERATING.md              day-to-day use, automations, model/cost
├── DEVELOPMENT.md           the "why" behind every decision, in chronological order
├── Get_Mooving.md           original product pitch/design
├── requirements.txt         Python dependencies
├── run_planner.sh           wrapper OpenClaw actually calls for the main plan
├── .gitignore
├── .env                     ONEMAP_TOKEN (gitignored — you create this)
├── .env.example             template for the above
│
├── data/
│   ├── profile.json               your address, buffers, notify email (gitignored — you create this)
│   ├── profile.example.json       template
│   ├── trusted_contacts.json      allowlist of senders (gitignored — you create this)
│   ├── trusted_contacts.example.json
│   ├── watched_threads.json       threads gmail_send.py sent, auto-managed
│   ├── inbox_watermark.json       auto-managed, tracks what's already been checked
│   └── mock_calendar.json         unused test fixture from early development
│
├── src/                    every script here has a `--json` mode and a docstring
│   ├── planner.py                 core plan: wrap-up/get-ready/leave/arrival
│   ├── calendar_google.py         reads your Calendar (read-only)
│   ├── onemap.py                  geocoding + travel time (Singapore)
│   ├── refresh_onemap_token.py    fetches a fresh ONEMAP_TOKEN, writes it into .env
│   ├── location_state.py          "is the stored location still trustworthy?"
│   ├── update_location.py         the only script allowed to change your stored location
│   ├── late_recovery.py           recompute from right now, compare transport modes
│   ├── route_compare.py           "what if I leave at X" / different origin-destination
│   ├── weather.py                 NEA 2-hour forecast (for walk/cycle suggestions)
│   ├── place_resolver.py          resolve a brand/category name ("McDonald's") to a real place
│   ├── gmail_send.py              the only script allowed to send email
│   ├── gmail_check_replies.py     replies to threads this agent sent
│   ├── gmail_check_inbox.py       new emails from trusted senders
│   ├── schedule_milestones.py     schedules the proactive ⏳🎒🚪 reminders (email or WhatsApp)
│   ├── whatsapp_trust.py          "is this WhatsApp sender the owner, a trusted contact, or unknown?"
│   └── whatsapp_send.py           the only script allowed to send an out-of-band WhatsApp message
│
├── skills/get_mooving/SKILL.md    what OpenClaw actually reads at runtime
│
├── calendar_credentials.json      Google OAuth client for Calendar (gitignored)
├── calendar_token.json            saved Calendar login (gitignored)
├── gmail_credentials.json         separate Google OAuth client for Gmail (gitignored)
└── gmail_token.json               saved Gmail login (gitignored)
```

Every `data/*.json` file and every `*_credentials.json`/`*_token.json` file holds something personal and is gitignored — never commit them. The `.example.json` versions are the only ones meant to be committed.

---

## 1. Prerequisites

- Python 3.12+ and a virtual environment
- [OpenClaw](https://docs.openclaw.ai) installed (`openclaw doctor` should be clean)
- A Google account (Calendar + Gmail)
- A free OneMap account (Singapore government routing/geocoding API)

## 2. Install dependencies

```bash
cd get_mooving
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

Everything in this project is run through `.venv/bin/python3` explicitly (never plain `python3`) — OpenClaw runs as a background service and does not inherit your shell's activated virtualenv. This trips people up constantly; see OPERATING.md's note on absolute paths.

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
2. Copy `.env.example` to `.env`:

   ```bash
   cp .env.example .env
   ```

3. Get a token — either way ends with `ONEMAP_TOKEN` set in `.env`:

   - **Manually**: POST your registered email/password to `https://www.onemap.gov.sg/api/auth/post/getToken` (check [their API docs](https://www.onemap.gov.sg/apidocs/) if this changes) and paste the returned `access_token` in as `ONEMAP_TOKEN=<token>`.
   - **Automatically**: set `ONEMAP_EMAIL`/`ONEMAP_PASSWORD` in `.env` instead, then run:

     ```bash
     .venv/bin/python3 src/refresh_onemap_token.py --json
     ```

     → `{"status": "refreshed", "expires_at": "..."}` — fetches a token and writes `ONEMAP_TOKEN` into `.env` in place, or a clean `{"error", "message"}` if the login fails or OneMap can't be reached.

**OneMap tokens expire roughly every 3 days.** When `onemap.py` calls start failing with an auth error (`{"error": "onemap_auth_failed", ...}`), re-run whichever of the two options above you set up. If you used the automatic option, this is also a good candidate for a recurring `openclaw automations add --every 2d ...` job (see OPERATING.md) so you never have to think about it.

## 6. Set your profile

```bash
cp data/profile.example.json data/profile.json
```

Edit `data/profile.json`:

- `location.address` — your default starting address (home). `confirmed_at` gets managed automatically by the app from here on — leave it as-is.
- `notify_email` — your own address. Where proactive reminders and automated notifications go if `notify_channel` is `"gmail"` (the default), and it's automatically trusted everywhere (no need to duplicate it into `trusted_contacts.json` below).
- `notify_channel` — `"gmail"` or `"whatsapp"`. Which channel proactive reminders (`schedule_milestones.py`) go out on. Leave as `"gmail"` unless you've done step 8 below.
- `owner_whatsapp` — your own WhatsApp number (E.164, e.g. `+6591234567`). Only needed if `notify_channel` is `"whatsapp"`, or if you want WhatsApp messages from your own number recognized as the owner (see step 8).
- `buffers` — your personal prep/task-switch/early-arrival minutes; tune these to how you actually operate.

```bash
cp data/trusted_contacts.example.json data/trusted_contacts.json
```

Edit `data/trusted_contacts.json` — emails and phone numbers of anyone *other than yourself* whose replies/emails/WhatsApp messages should be treated as trusted (phone numbers matter only if you do step 8). Your own address (both the connected Gmail account and `notify_email`) is always trusted automatically; your own WhatsApp number is trusted automatically once `owner_whatsapp` is set — neither needs duplicating here. **Only edit this file by hand** — the agent is deliberately never allowed to add to it itself; that's what keeps it meaningful as a safety boundary.

## 7. Install the skill into OpenClaw

```bash
openclaw skills install ./skills/get_mooving --as get-mooving --force
openclaw gateway restart
```

Repeat both commands any time you edit `skills/get_mooving/SKILL.md`. If OpenClaw seems to be answering from stale memory after a change, also start a fresh session:

```bash
openclaw agent --agent main --message "/new"
```

## 8. Connect WhatsApp (optional)

Lets you (and, in a deliberately limited way, trusted contacts) message the agent over WhatsApp instead of only the terminal or email. Skip this section entirely if you don't want it — everything above works without it.

**This step needs your own terminal and your phone** — it can't be done for you. From the project root:

```bash
openclaw channels add --channel whatsapp
```

Pick **npm** when asked where to install the plugin from, then scan the QR code it shows with WhatsApp on your phone (Settings → Linked Devices → Link a Device). Confirm it's connected:

```bash
openclaw channels status
```

**Then lock down who can reach the agent at all** — this is the primary defense against unknown numbers, enforced by the gateway before your agent ever runs, not by the skill:

```bash
openclaw config set channels.whatsapp.dmPolicy allowlist
openclaw config set channels.whatsapp.allowFrom '["+<your number>", "+<a trusted friend>", ...]' --strict-json
```

Every number in `allowFrom` can reach the agent; anyone else is rejected at the gateway. Being in `allowFrom` only gets a message *to* the agent — what it's allowed to *do* once there is a second, separate layer:

- Set `owner_whatsapp` in `data/profile.json` to your own number (step 6) — that's what tells the skill "this sender is me," giving full access, same as the terminal or your own email.
- Every other number in `allowFrom` should also be in `data/trusted_contacts.json`'s `phones` list (step 6) — those get **relay-only** access: they can ask the agent to pass a message to you, but never see your calendar, location, or travel times. See `SKILL.md`'s "WhatsApp Channel" section for the exact rules, and `TESTING.md` for how this was unit-tested (`whatsapp_trust.py`) before ever being tried against a real number.
- A number in `allowFrom` but in neither place gets treated as `"unknown"` by the skill itself too — a second backstop, not just the gateway.

**Confirmed live** (see DEVELOPMENT.md §54): the gateway prefixes the message text itself with the sender's number before the agent ever sees it, e.g. `[WhatsApp +6594898515 +2d Wed 2026-09-16 00:12:22 GMT+8] +6594898515: What's my next meeting?` — `SKILL.md`'s "WhatsApp Channel" section reads the number from that prefix. Worth sending yourself one real test message anyway (and, once you've added a friend's number, having them send one too) to confirm `whatsapp_trust.py` gets called with the right number and returns the tier you expect — this is exactly the kind of thing Level 2 (smoke) testing exists for.

---

Setup done — next: **[OPERATING.md](OPERATING.md)** for day-to-day use, testing, and the proactive automations.
