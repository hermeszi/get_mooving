# Get Mooving

**ADHD-friendly Singapore travel & transition agent.**

Reads your next Google Calendar event, works out real Singapore travel time (OneMap), and tells you when to wrap up, get ready, and leave — instead of just showing a meeting time. It also checks which calendar event is *currently* happening and asks before assuming you're still starting from home. If you're running late, it recomputes from right now and can draft (with your approval) a late message to the attendee, sent via Gmail. It can also proactively notify you those wrap-up/get-ready/leave-now nudges on a schedule (email or WhatsApp), and check your inbox for trusted questions like "when should I leave?" — not just when you ask in a terminal. WhatsApp is optional: once connected, you get full access from your own number, and trusted contacts get a strictly relay-only channel — they can ask the agent to pass you a message, never see your calendar.

**Nothing gets sent anywhere without your explicit approval first.**

---

## Where to go

| Doc | For |
|---|---|
| **[SETUP.md](SETUP.md)** | First-time install: file structure, dependencies, Google/OneMap accounts, profile config, installing the skill |
| **[OPERATING.md](OPERATING.md)** | Day-to-day use: OpenClaw basics, daily routine, the two proactive automations, model/cost |
| **[DEVELOPMENT.md](DEVELOPMENT.md)** | The *why* behind every decision, in chronological order — read this before changing how something works |
| **[TESTING.md](TESTING.md)** | How this project is tested — unit/smoke/user-flow levels, what's covered, how CI runs |
| **[Get_Mooving.md](Get_Mooving.md)** | The original product pitch and design |

New here? Start with **[SETUP.md](SETUP.md)**.

---

## Disconnecting / privacy

Everything this project stores locally, and how to remove it:

| What | Where | To remove |
|---|---|---|
| Calendar access | Google account | [myaccount.google.com/permissions](https://myaccount.google.com/permissions) → remove the app; delete `calendar_credentials.json` and `calendar_token.json` |
| Gmail access | Google account | Same page, remove the app; delete `gmail_credentials.json` and `gmail_token.json` |
| WhatsApp access (if connected) | Your phone | WhatsApp → Settings → Linked Devices → remove the OpenClaw device; also `openclaw channels remove --channel whatsapp` |
| OneMap token | `.env` | Delete the file, or blank `ONEMAP_TOKEN=` |
| Home address, buffers, WhatsApp/email notify settings | `data/profile.json` | Delete the file (falls back to needing re-setup, see SETUP.md) |
| Trusted contacts (emails + phone numbers) | `data/trusted_contacts.json` | Delete the file |
| Sent-message thread history | `data/watched_threads.json` | Delete the file |
| Proactive/email-check schedules | OpenClaw automations | `openclaw automations list --all` then `rm` any `gm-*` jobs |
| The skill itself | OpenClaw | `rm -rf ~/.openclaw/workspace/skills/get-mooving` then `openclaw gateway restart` — this was installed as a workspace skill (`skills install`), not a managed library skill, so there's no `skills remove` command for it |

Deleting the `data/*.json` files (all gitignored, all local-only) removes every piece of personal data this project holds — nothing is stored anywhere else.
