# Get Mooving — Development Log

This document records how the **Get Mooving** prototype evolved from a simple local time calculator into an OpenClaw agent that can read a real Google Calendar event, obtain Singapore travel information from OneMap, and produce ADHD-friendly transition prompts.

The purpose is to preserve the setup steps, tests, problems, fixes, and design decisions made during development.

---

## 1. Project Goal

**Get Mooving** is an ADHD-friendly meeting travel and transition agent.

The project is designed to help a user move from:

> "I have somewhere to be"

to:

> actually wrapping up, getting ready, leaving, and recovering if the plan slips.

Core visual prompts:

- **⏳ Wrap up**
- **🎒 Get ready**
- **🚪 Leave now**
- **🚇 MRT / public transport**
- **🚕 Taxi / recovery option**
- **💬 Message attendee**

The agent should use short, concrete, non-scolding language and should not rely only on abstract clock times.

---

## 2. Architecture Evolution

The project was intentionally built in layers so each part could be tested independently.

### Stage 1 — Deterministic planner only

```text
mock_calendar.json
        +
profile.json
        ↓
planner.py
        ↓
⏳ 🎒 🚪
```

Goal: prove the time calculations work before adding AI or external APIs.

### Stage 2 — OpenClaw calls the planner

```text
User
 ↓
OpenClaw
 ↓
get-mooving SKILL.md
 ↓
run_planner.sh
 ↓
planner.py
 ↓
mock data
 ↓
⏳ 🎒 🚪
```

Goal: prove OpenClaw can invoke deterministic application code instead of doing time arithmetic itself.

### Stage 3 — Real Google Calendar

```text
Google Calendar
      ↓
calendar_google.py
      ↓
planner.py
      ↓
⏳ 🎒 🚪
```

Goal: replace the fake event with the user's real next timed appointment.

### Stage 4 — Real OneMap travel data

```text
Google Calendar
      ↓
destination
      ↓
OneMap Search + Routing
      ↑
starting location
      ↓
real travel duration
      ↓
planner.py
      ↓
⏳ 🎒 🚪
```

Goal: replace the fixed travel duration with a real Singapore route estimate.

---

## 3. Current Target Architecture

```text
                         ┌────────────────────┐
                         │       User         │
                         │                    │
                         │ "When do I leave?" │
                         │ "late"             │
                         └─────────┬──────────┘
                                   │
                                   ▼
                         ┌────────────────────┐
                         │     OpenClaw       │
                         │    main agent      │
                         └─────────┬──────────┘
                                   │
                           get-mooving skill
                                   │
                                   ▼
                         ┌────────────────────┐
                         │ run_planner.sh     │
                         └─────────┬──────────┘
                                   │
                                   ▼
                      ┌─────────────────────────┐
                      │       planner.py        │
                      │ deterministic timings   │
                      └───────┬─────────┬───────┘
                              │         │
                    ┌─────────┘         └──────────┐
                    ▼                              ▼
          calendar_google.py                   onemap.py
                    │                              │
                    ▼                              ▼
          Google Calendar API                 OneMap API

                    planner output
                         ↓
            ⏳ Wrap up
            🎒 Get ready
            🚪 Start leaving
            🚇 Travel / arrival
```

---

## 4. Development Environment

Development was done directly on a Linux laptop.

The project remained a normal Git repository first instead of containerising OpenClaw immediately.

Why:

- faster local development,
- easier OAuth browser flow,
- easier debugging,
- fewer Docker networking and volume issues,
- Docker can be added later for deployment.

---

## 5. OpenClaw Installation

OpenClaw was installed globally.

A PATH problem appeared after installation.

Environment:

```text
node: v24.21.0
npm:  11.19.0

npm global prefix:
/home/ming/.npm-global
```

OpenClaw was installed:

```text
openclaw@2026.9.3
```

but the shell initially returned:

```text
openclaw: command not found
```

The fix was:

```bash
export PATH="$HOME/.npm-global/bin:$PATH"
```

Then make it persistent:

```bash
echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Verification:

```bash
openclaw --version
```

---

## 6. OpenClaw Gateway Setup

`openclaw doctor` showed that `gateway.mode` was unset.

It was configured for local development:

```bash
openclaw config set gateway.mode local
```

A Gateway authentication token was also generated during Doctor setup.

The Gateway was started or restarted with:

```bash
openclaw gateway start
```

or:

```bash
openclaw gateway restart
```

The local dashboard became available at:

```text
http://127.0.0.1:18789/
```

Loopback-only access was accepted for development because the application was not yet intended to be reachable from other machines.

---

## 7. Model Setup

The first OpenRouter OAuth attempt completed authentication but failed during model-route verification.

The project then switched to an OpenRouter API key.

A fixed model was selected:

```text
openrouter/qwen/qwen3-30b-a3b-instruct-2507
```

Why:

- inexpensive for repeated testing,
- predictable behaviour,
- suitable for instruction following and agent workflows,
- avoids model changes caused by an automatic router.

Key architecture rule:

> **The LLM should not calculate departure times.**

The LLM handles:

- user intent,
- tool/workflow selection,
- asking for missing information,
- ADHD-friendly wording,
- drafting messages.

Python handles:

- time arithmetic,
- buffer calculations,
- route values,
- deterministic outputs.

---

## 8. Phase 1 — `planner.py`

The first functional program was:

```text
src/planner.py
```

Its job was deliberately small:

> Take a meeting time, travel duration, and user buffers, then calculate transition milestones.

Inputs:

```text
meeting time
travel minutes
early-arrival minutes
invisible-delay minutes
prep minutes
task-switch minutes
```

Core calculation:

```text
meeting time
      ↓
minus early-arrival buffer
      ↓
arrival target
      ↓
minus travel duration
      ↓
physical departure
      ↓
minus invisible ADHD buffer
      ↓
leave prompt
      ↓
minus preparation time
      ↓
get-ready prompt
      ↓
minus task-switch time
      ↓
wrap-up prompt
```

Original test:

```text
Meeting:            3:00 PM
Travel:               48 min
Early arrival:         10 min
Invisible delay:        8 min
Prep:                  15 min
Task switch:           10 min
```

Expected output:

```text
⏳ Wrap up:      1:29 PM
🎒 Get ready:    1:39 PM
🚪 Leave prompt: 1:54 PM

Route-based physical departure:
2:02 PM
```

Important distinction:

- `physical_departure` = route-based latest real departure
- `leave_prompt` = earlier behavioural prompt

---

## 9. Mock Data

Before connecting real services, mock JSON files were used.

### `data/mock_calendar.json`

Example:

```json
{
  "title": "Meeting at SUTD",
  "start": "2026-09-10T15:00:00+08:00",
  "location": "SUTD",
  "attendees": [
    {
      "name": "Sarah",
      "email": "sarah@example.com"
    }
  ]
}
```

Purpose: test event parsing and planner logic without OAuth or network dependencies.

### `data/profile.json`

Stores local user settings such as:

```json
{
  "preferred_transport": "public_transport",

  "buffers": {
    "early_arrival_minutes": 10,
    "invisible_delay_minutes": 8,
    "prep_minutes": 15,
    "task_switch_minutes": 10
  },

  "location": {
    "label": "Home",
    "address": "LOCAL PRIVATE ADDRESS",
    "confirmed_at": "..."
  }
}
```

The real profile should remain local because it may contain private location data.

A `profile.example.json` can be committed instead.

---

## 10. `run_planner.sh`

A small shell wrapper was added at the repository root:

```text
run_planner.sh
```

Purpose:

> Give OpenClaw one predictable command to execute.

Example:

```bash
#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"
./.venv/bin/python3 src/planner.py
```

Using:

```text
./.venv/bin/python3
```

instead of plain:

```text
python3
```

matters because OpenClaw runs as a service and does not inherit the terminal's activated virtual environment.

Direct test:

```bash
./run_planner.sh
```

---

## 11. Python Virtual Environment

A project virtual environment was created:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Purpose:

- isolate project dependencies,
- avoid modifying system Python,
- keep package versions reproducible,
- make later deployment easier.

Do not commit:

```text
.venv/
```

Dependencies can instead be recorded with:

```bash
pip freeze > requirements.txt
```

---

## 12. Phase 2 — OpenClaw Skill

A custom skill was created rather than depending on a community skill.

Structure:

```text
skills/
└── get_mooving/
    └── SKILL.md
```

The skill teaches OpenClaw how to handle requests such as:

```text
"When should I leave?"
"Show me my full transition plan."
"late"
```

The skill should tell the agent to:

1. run the deterministic planner,
2. use its output as the source of truth,
3. not invent times or locations,
4. not reuse stale meeting information,
5. present short ADHD-friendly prompts.

Important debugging lesson:

> Fixed example times inside `SKILL.md` can be copied by the model as though they were real values.

The skill was installed with:

```bash
openclaw skills install ./skills/get_mooving --as get-mooving --force
```

Installed copy:

```text
~/.openclaw/workspace/skills/get-mooving/SKILL.md
```

Verification:

```bash
openclaw skills info get-mooving
```

Successful status:

```text
get-mooving ✓ Ready

Visible to model: yes
Available as command: yes
```

---

## 13. Skill Development Refresh Cycle

There are three separate states:

```text
Git repository
"What did I edit?"
        ↓

Installed OpenClaw skill
"What instructions did OpenClaw load?"
        ↓

Agent session
"What does the current LLM conversation remember?"
```

After changing the skill:

```bash
openclaw skills install ./skills/get_mooving --as get-mooving --force
openclaw gateway restart
openclaw agent --agent main --message "/new"
```

Meaning:

- `install --force` = update the installed skill copy
- `gateway restart` = reload OpenClaw runtime
- `/new` = start a clean agent session

---

## 14. Early OpenClaw Test

The first successful agent test returned:

```text
You should leave at 1:54 PM.
```

This proved OpenClaw could reach the planning workflow.

A longer response exposed a problem: the LLM started reinterpreting planner output and generated incorrect derived times.

This reinforced:

> **Planner output is authoritative; the LLM formats it but does not perform the arithmetic again.**

---

## 15. Phase 3 — Google Calendar

The next step was to replace the mock event with a real Google Calendar event.

A Google Cloud project was created and the Google Calendar API enabled.

OAuth client type:

```text
Desktop application
```

Read-only scope:

```python
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly"
]
```

Local secret files:

```text
credentials.json
token.json
```

were excluded from Git.

Recommended `.gitignore`:

```gitignore
credentials.json
token.json
```

---

## 16. `calendar_google.py`

A new adapter was added:

```text
src/calendar_google.py
```

Responsibility:

```text
Google Calendar API
      ↓
find next timed event
      ↓
return:
- title
- start datetime
- location
- attendees
```

The first successful test:

```bash
python3 src/calendar_google.py
```

returned:

```text
{
  'title': 'BIOCIS Research Appointment',
  'start': '2026-09-11T15:00:00+08:00',
  'location': 'Clinical Sciences Building (CSB), 11 Mandalay Rd, Singapore 308232',
  'attendees': []
}
```

This proved:

```text
Google OAuth ✅
Calendar API ✅
Upcoming event selection ✅
Event location extraction ✅
```

---

## 17. Calendar Integration Into `planner.py`

The planner was changed from:

```python
event = load_json("mock_calendar.json")
```

to using:

```python
event = get_next_event()
```

from `calendar_google.py`.

The mock calendar was deliberately kept as a test/fallback source.

Desired structure:

```text
REAL MODE
Google Calendar
      ↓
planner.py

TEST MODE
mock_calendar.json
      ↓
planner.py
```

---

## 18. Phase 4 — OneMap

The next goal was to replace the fixed:

```text
travel_minutes = 48
```

with real Singapore travel data.

A OneMap API token was obtained and stored locally in:

```text
.env
```

Example:

```env
ONEMAP_TOKEN=...
```

`.env` was excluded from Git.

Packages added:

```bash
pip install requests python-dotenv
```

---

## 19. `onemap.py`

A new adapter was created:

```text
src/onemap.py
```

It handles:

### A. Search / geocoding

Convert:

```text
building / address / postal code
```

to:

```text
latitude
longitude
```

### B. Routing

Use coordinates plus departure time to request a public-transport travel duration.

---

## 20. OneMap Address Issue

The first destination lookup failed:

```text
ValueError:
Location not found:
Clinical Sciences Building, 11 Mandalay Road
```

The Calendar event contained:

```text
Clinical Sciences Building (CSB),
11 Mandalay Rd,
Singapore 308232
```

Using postal code:

```text
308232
```

worked.

OneMap resolved it to:

```text
11 MANDALAY ROAD
LEE KONG CHIAN SCHOOL OF MEDICINE (NOVENA CAMPUS)
SINGAPORE 308232
```

A more robust search strategy was then introduced:

```text
try full calendar location
        ↓
if no result:
extract 6-digit Singapore postal code
        ↓
search postal code
```

This matters because Calendar locations are human-entered and may not match OneMap's naming exactly.

---

## 21. Successful OneMap Test

Standalone test:

```bash
python3 src/onemap.py
```

returned:

```text
START:
8 SOMAPAH ROAD
SINGAPORE UNIVERSITY OF TECHNOLOGY AND DESIGN (SUTD)

DESTINATION:
11 MANDALAY ROAD
LEE KONG CHIAN SCHOOL OF MEDICINE (NOVENA CAMPUS)

🚇 Estimated journey: 63 minutes
```

This proved:

```text
OneMap authentication ✅
OneMap search ✅
Address → coordinates ✅
Public-transport routing ✅
Route duration extraction ✅
```

---

## 22. Route-Time Circular Dependency

A design issue appeared:

```text
We need travel time
to calculate departure time.

But OneMap wants a departure time
to calculate travel time.
```

MVP solution:

```text
1. Make a rough initial departure guess.
2. Query OneMap.
3. Calculate route-based departure.
4. Query OneMap again using that calculated departure.
5. Produce final plan.
```

The rough value is only a seed for routing.

It is not an ADHD buffer and should not be shown as a user-facing time.

---

## 23. Integrated Planner Test

After Calendar and OneMap were integrated:

```bash
python3 src/planner.py
```

and:

```bash
./run_planner.sh
```

both produced:

```text
📅 BIOCIS Research Appointment
📍 Clinical Sciences Building (CSB),
   11 Mandalay Rd, Singapore 308232

Meeting:        3:00 PM
Arrive by:      2:50 PM

⏳ Wrap up:      1:39 PM
🎒 Get ready:    1:49 PM
🚪 Leave:        2:04 PM

Route-based latest departure: 2:12 PM
```

This was the first successful integrated local application flow using real Calendar data and route logic.

---

## 24. OpenClaw Integration Problem

The agent continued returning old values such as:

```text
SUTD
48-minute journey
1:54 PM
```

even though the direct planner output had changed.

Two likely causes were identified:

1. old conversation/session context,
2. OpenClaw not automatically selecting/running the Get Mooving skill.

After `/new`, the stale SUTD answer disappeared, but OpenClaw then said it could not access Calendar data.

This showed that the old values had been coming from context rather than the current planner.

---

## 25. Explicit Exec Test

To isolate the issue, OpenClaw was explicitly told to execute the wrapper:

```bash
openclaw agent --agent main   --message "Use the exec tool to run /home/ming/42/openclaw/get_mooving/run_planner.sh. Return the stdout exactly and do not calculate anything yourself."
```

OpenClaw returned the correct live output:

```text
📅 BIOCIS Research Appointment
📍 Clinical Sciences Building (CSB), 11 Mandalay Rd, Singapore 308232

Meeting:        3:00 PM
Arrive by:      2:50 PM

⏳ Wrap up:      1:39 PM
🎒 Get ready:    1:49 PM
🚪 Leave:        2:04 PM

Route-based latest departure: 2:12 PM
```

This proved the complete tool chain:

```text
OpenClaw
   ↓
exec
   ↓
run_planner.sh
   ↓
virtualenv Python
   ↓
Google Calendar
   ↓
OneMap
   ↓
planner.py
   ↓
correct output
```

The core application works.

The remaining OpenClaw problem is mainly automatic skill/workflow selection from a normal user request.

---

## 26. Missing Event Location Bug

Testing the integrated planner against a hypothetical event with no location exposed a crash:

```text
planner.py
      ↓
event["location"] is None
      ↓
onemap.search_location(None)
      ↓
TypeError: expected string or bytes-like object, got 'NoneType'
```

A calendar event without a location (a call, a TBD meeting) would previously make `planner.py` exit with a raw traceback instead of a clean message. This violates the skill rule that says the agent should report a planner failure, not guess.

Fix:

```python
if not event.get("location"):
    print(
        f"'{event['title']}' has no location set. "
        "Cannot calculate travel time without a destination."
    )
    return
```

`planner.py` now fails cleanly with one readable line when the destination is missing.

`SKILL.md` was updated with a new rule:

> If the script reports that the event has no location set, ask the user for the destination. Do not guess or invent one, and do not run the planner again until a destination is available.

### Known gap

There is currently no way to feed a user-supplied destination back into `planner.py`. The script only ever reads `event["location"]` from the live Calendar event, so even after the user answers, a re-run would hit the same "no location" message again. Closing this gap would mean adding an optional destination override (CLI arg or env var) that the agent sets before calling `run_planner.sh`. Not built yet — deferred until it's actually needed.

---

## 27. Current Status

### Working

- [x] Git repository
- [x] OpenClaw installed on Linux
- [x] Gateway configured and running
- [x] OpenRouter API key
- [x] fixed Qwen model (superseded — see §29, Step 5: swapped to `openrouter/anthropic/claude-sonnet-4.6` after Qwen3 30B proved unreliable at skill/tool dispatch)
- [x] Python virtual environment
- [x] deterministic `planner.py`
- [x] mock Calendar data
- [x] profile/buffer data
- [x] `run_planner.sh`
- [x] custom Get Mooving skill
- [x] Google Calendar OAuth
- [x] Calendar read-only API
- [x] next real timed event retrieval
- [x] OneMap authentication
- [x] OneMap geocoding
- [x] OneMap public-transport routing
- [x] integrated local planner
- [x] OpenClaw can explicitly execute the full planner
- [x] clean failure when an event has no location
- [x] automatic Get Mooving skill selection (works on `claude-sonnet-4.6`; see §29)
- [x] normal prompt → planner execution without explicitly saying "use exec" (same fix)
- [x] location freshness / confirmation (§30, `location_state.py`)
- [x] structured planner output (§31, `planner.py --json`)
- [x] location confirmation input loop closed (§32, `update_location.py`)
- [x] destination override input loop closed (§33, `planner.py --destination`)
- [x] `late` recovery — first version (§34, `late_recovery.py`)
- [x] alternative transport comparison — MRT vs. taxi (§35, `onemap.get_drive_time`)
- [x] hypothetical departure/mode queries — "what if I leave at X" (§36, `route_compare.py`)
- [x] closed a real unchecked-comparative-claim hallucination caught in live testing (§36, new Rules entry)
- [x] walk/cycle modes, distance-gated (§38, `onemap.get_walk_time`/`get_cycle_time`)
- [x] weather-aware filtering — NEA 2-hour forecast (§38, `weather.py`)
- [x] calendar event end times (§39, `calendar_google.py`/`planner.py`)
- [x] trip chaining — alternate origin/destination overrides (§39, `route_compare.py --origin`/`--destination`)
- [x] ambiguous place-name resolution — brand/category → nearest real candidates (§39, `place_resolver.py`)
- [x] late-message drafting + approval flow (§40, `SKILL.md`)
- [x] real Gmail sending, wired to that same approval flow (§41, `gmail_send.py`) — Day-2 plan fully closed
- [x] reading Gmail replies, narrow scope — replies on threads this agent sent (§42, `gmail_check_replies.py`)
- [x] trusted-contacts allowlist for reply senders, with spoofed-display-name protection (§43, `data/trusted_contacts.json`)
- [x] proactive milestone scheduling mechanism, built and verified live — a real one-shot fired and sent a real email on time (§44, `schedule_milestones.py`)
- [x] proactive reply-check design, with the third-party-send boundary enforced (§44, `SKILL.md`)
- [x] documentation cleanup — SKILL.md trimmed 298→121 lines, module docstrings on all 12 scripts, README.md rewritten as a real setup guide (§45)
- [x] recurring `gm-schedule-milestones` automation actually turned on (by the user, via the README example) — a real bug in that example (relative venv path) was caught and fixed in both the live job and the docs (§46)
- [x] `get_next_event()` fixed to skip already-started events (§47)
- [x] trusted-sender inbox trigger — new/unsolicited emails, not just replies (§48, `gmail_check_inbox.py`)
- [x] same-point (start = destination) trips fixed to return 0 minutes instead of crashing (§48, `onemap.py`)
- [x] location freshness now also checks against a calendar event in progress, not just a timestamp (§49, `location_state.py`/`get_current_event`)
- [x] `schedule_milestones.py` corrects already-scheduled reminders when the computed time drifts, instead of leaving them stale (§49)

### Still being developed

- [ ] a recurring automation for either email check (`gmail_check_replies.py`/`gmail_check_inbox.py`) — milestone scheduling is live, email-checking isn't yet (on-demand only)
- [ ] Docker / cloud deployment
- [ ] WhatsApp as a real OpenClaw channel — would give genuine push for that channel; still just an idea, per the original roadmap
- [ ] Gmail inbox as an *open* command channel (any sender, not just the allowlist) — §48 closed the trusted-sender case; a fully open inbox still needs its own safety/threat-model design before building

### Optional, blocked on external access

- [ ] Grab Farefeed integration (§37) — real pickup ETA, fare range, surge level, deep link. Needs Grab partner API credentials, which this repo does not have.

---

## 28. Recommended Next Step

Do not add another API yet.

The next target is:

```text
Normal user message
        ↓
OpenClaw recognises Get Mooving intent
        ↓
get-mooving skill
        ↓
exec run_planner.sh
        ↓
fresh planner output
        ↓
short ADHD-friendly response
```

Target interaction:

```text
User:
"When should I leave for my next meeting?"

Agent:
📅 BIOCIS Research Appointment — 3:00 PM

⏳ 1:39 PM — Wrap up.
🎒 1:49 PM — Get ready.
🚪 2:04 PM — Start leaving.
🚇 Aim to be out by 2:12 PM.
🎯 Arrive around 2:50 PM.
```

---

## 29. Skill Dispatch Failure Diagnosed

Testing the target flow from §28 (plain user message → skill → exec) surfaced the exact break point.

### Step 1 — routing rule added

A persistent operating rule was added to OpenClaw's `AGENTS.md` (`~/.openclaw/workspace/AGENTS.md`), since that file is loaded at session startup for every agent:

```text
## Get Mooving

For questions about the user's next meeting, meeting location,
when to leave, travel/departure plans, getting ready, or being late:
always use the get-mooving skill before answering.
Never answer these from conversation memory.
```

The skill description was also tightened from a generic sentence to a trigger-specific one:

```text
description: Use for next meeting, meeting location, when to leave,
travel/departure plans, transition timing, or running late.
```

Both were reinstalled with `openclaw skills install ./skills/get_mooving --as get-mooving --force` and `openclaw gateway restart`.

### Step 2 — confirmed the routing rule works

`openclaw skills check --agent main` showed `get-mooving` fully `eligible`, `modelVisible`, and `commandVisible` — no config problem.

On the **old, already-open session**, a plain message still got no attempt at all:

```text
$ openclaw agent --agent main --message "Where is my next meeting?"
> I can't access your calendar to check your next meeting location...
```

AGENTS.md is only read at session startup, so a mid-session edit does not retroactively apply — matches the refresh cycle already documented in §13. After `openclaw agent --agent main --message "/new"`, the same plain message changed behavior:

```text
$ openclaw agent --agent main --message "Where is my next meeting?"
> I can't use the tool "get-mooving" here because it isn't available.
> I need to stop retrying it and answer without that tool.
```

This is progress: the model now *attempts* to use get-mooving on a plain natural-language question. The routing fix works.

### Step 3 — the real break: a hallucinated tool call

`journalctl --user -u openclaw-gateway.service` showed what actually happens underneath. Two different failure modes were caught, depending on how the skill was invoked:

Forcing it with `/skill get-mooving ...` made the model call the wrong meta-tool:

```text
[tools] skill_workshop failed: Skill Workshop can only update skills
it generated. No Workshop-generated skill matched: get-mooving.
Create it as a new skill, or edit the file directly.
raw_params={"action":"read","skill_name":"get-mooving"}
```

Forcing it with `$get-mooving ...`, or letting the model choose it naturally after the AGENTS.md fix, made it try to call a tool literally named `get-mooving`, which does not exist — it retried this silently (~10 model round-trips, ~50 seconds) before giving up:

```text
I can't use the tool "get-mooving" here because it isn't available.
I need to stop retrying it and answer without that tool.
```

Per OpenClaw's own docs (`docs.openclaw.ai/tools/skills`), this is a model mistake, not a config problem: "Eligible skills are compiled into a compact XML block and injected into the system prompt." A skill is instruction text, not a tool with its own name — the model is supposed to read it and then call its normal tools (`exec`) per what it says. There is no tool called `get-mooving` to call.

An explicit line was added to `SKILL.md` to rule this out as a wording problem:

```text
This is not a callable tool. There is no tool named "get-mooving" —
do not try to call one. Follow these instructions directly using
your normal tools (exec) to run the script below.
```

Reinstalled, gateway restarted, fresh session, same message — identical failure. So this is not fixable by rewording the skill.

### Step 4 — the exec path itself still works perfectly

As a sanity check, the exact instruction style from §25 was re-run:

```text
$ openclaw agent --agent main --message "Use the exec tool to run \
/home/ming/42/openclaw/get_mooving/run_planner.sh. Return the stdout \
exactly and do not calculate anything yourself."

> Your next meeting is at:
> 📅 Coding class
> 📍 22 Havelock Rd, Singapore 160022
> Meeting time: 11:00 AM  Recommended arrival: 10:50 AM
> ⏳ Wrap up: 9:39 AM  🎒 Get ready: 9:49 AM  🚪 Leave: 10:04 AM
> Latest recommended departure: 10:12 AM
```

Live, correct data for a real upcoming event. The full pipeline is confirmed sound end to end:

```text
OpenClaw → exec tool → run_planner.sh → planner.py
              ├→ calendar_google.py
              └→ onemap.py
```

### Step 5 — model swap confirms the diagnosis

The suspicion in the original conclusion (tool-selection weakness in the configured cheap model, not a bug in this repo) was tested directly by switching the model:

```bash
openclaw models set openrouter/anthropic/claude-sonnet-4.6
```

This changes the permanent agent config (confirmed via `openclaw agents list` → `Model: openrouter/anthropic/claude-sonnet-4.6`), not a one-off `--model` override.

Result, same plain message, same fresh-session flow that failed under Qwen3 30B:

```text
Qwen3 30B:
  skill/tool dispatch unreliable
  → hallucinated "get-mooving" tool call, retried, gave up

Claude Sonnet 4.6:
  plain request → skill → exec → live planner
  → succeeded
```

This confirms the pipeline, `SKILL.md`, and the `AGENTS.md` routing rule were never the problem. The break was entirely inside Qwen3 30B's tool-selection behavior when a skill needed to be turned into a real tool call. A more capable model does this correctly on the first plain-language request, with no special phrasing required.

### Conclusion

The gap was narrow and precisely located: getting from "the model has decided to use get-mooving" to "therefore call `exec` with this path," without the model inventing a fictitious `get-mooving` tool call in between. §7 chose Qwen3 30B for cost; that tradeoff is what broke skill dispatch. Swapping to `openrouter/anthropic/claude-sonnet-4.6` resolved it outright — the cost/reliability tradeoff needs revisiting if Qwen3 stays the default for anything beyond simple, non-tool-calling replies.

Options still on the table if a cheaper model is wanted back later:

- OpenClaw's `command-dispatch: tool` / `command-tool: exec` front-matter option, which bypasses model tool-selection entirely — but only for the explicit `/get-mooving` slash-command path, not plain natural language.
- Reporting the hallucinated-tool-call behavior upstream, now reproduced and confirmed model-specific.

---

## 30. Location Freshness

The last remaining Day-1 feature from `Get_Mooving.md`'s design was closed: `profile.json` already stored `confirmed_at`, but nothing checked it. `planner.py` used `profile["location"]["address"]` unconditionally, so a stale or ancient location would be silently fed into OneMap without ever asking the user.

### `src/location_state.py`

A small standalone module, deliberately kept out of `planner.py` rather than adding another branch to `main()`:

```text
profile.json
      ↓
location_state.py
      ↓
   recent?
   │
   ├── YES → use address
   │
   └── NO  → confirmation prompt
```

MVP rule, kept intentionally simple:

```python
FRESHNESS_LIMIT = timedelta(hours=2)

def is_location_fresh(confirmed_at, now):
    if not confirmed_at:
        return False
    confirmed_time = datetime.fromisoformat(confirmed_at)
    return now - confirmed_time < FRESHNESS_LIMIT
```

confirmed < 2 hours ago → use it. Older or missing → ask.

### Wired into `planner.py`

The check runs right after the event-location check, before any OneMap call:

```python
location = profile["location"]

if not is_location_fresh(location.get("confirmed_at"), datetime.now().astimezone()):
    print(location_confirmation_prompt(location["label"]))
    return
```

Output when stale (this is what `profile.json`'s real `confirmed_at` produced, since it was over a day old):

```text
$ ./run_planner.sh
📍 Still starting from Home?
1 Yes · 2 Home · 3 Somewhere else
```

Verified all three cases directly against `planner.main()`:

- fresh `confirmed_at` (10 minutes old) → normal plan output, unchanged.
- stale `confirmed_at` (>2h) → confirmation prompt, no OneMap calls made.
- missing `confirmed_at` → same confirmation prompt.

### Skill-level wiring

A new rule was added to `SKILL.md`, mirroring the existing missing-destination rule from §26:

```text
15. If the script asks whether the user is still starting from a
location (a 📍 confirmation prompt), relay that question to the user
exactly, with the numbered options. Do not guess or assume an answer,
and do not run the planner again until the user confirms.
```

Reinstalled with `openclaw skills install ./skills/get_mooving --as get-mooving --force` and `openclaw gateway restart`.

### Known gap (same shape as §26)

There is still no way to feed the user's answer (1/2/3) back into `planner.py` — it only ever reads `profile.json`'s stored `confirmed_at`. Answering the prompt today would need someone to manually update `data/profile.json`. Closing this is the same deferred work as the destination-override gap: an input path from the agent back into the deterministic script. Not built yet.

---

## 31. Structured JSON Output

Even with §29's model fix, `planner.py` was still printing formatted human text, which the LLM had to re-read and could in principle reinterpret or mistype (this is exactly the failure mode §14 warned about: "the LLM started reinterpreting planner output and generated incorrect derived times"). Text output leaves that door open no matter how good the model is. A `--json` mode closes it structurally.

### `planner.py --json`

Success output, matching the field names decided up front:

```json
{"event": "Coding class", "destination": "22 Havelock Rd, Singapore 160022", "meeting_time": "11:00", "arrival_target": "10:50", "wrap_up": "09:39", "get_ready": "09:49", "leave_prompt": "10:04", "physical_departure": "10:12", "transport": "public_transport"}
```

Built by two small additions, no change to the actual arithmetic:

```python
def format_24h(dt):
    return dt.strftime("%H:%M")

def build_result(event, plan, transport):
    return {
        "event": event["title"],
        "destination": event["location"],
        "meeting_time": format_24h(plan["meeting_time"]),
        "arrival_target": format_24h(plan["arrival_target"]),
        "wrap_up": format_24h(plan["wrap_up_prompt"]),
        "get_ready": format_24h(plan["get_ready_prompt"]),
        "leave_prompt": format_24h(plan["leave_prompt"]),
        "physical_departure": format_24h(plan["physical_departure"]),
        "transport": transport,
    }
```

The three existing failure paths (§26 missing destination, §30 stale location, plus "no upcoming event") were also converted to structured JSON under `--json`, instead of the plain messages they printed before:

```json
{"error": "no_upcoming_event", "message": "No upcoming timed events found."}
{"error": "no_destination", "message": "'...' has no location set...", "event": "..."}
{"error": "location_confirmation_required", "message": "📍 Still starting from Home?\n1 Yes · 2 Home · 3 Somewhere else", "label": "Home"}
```

Text mode (no flag) is unchanged and still the default — `--json` is opt-in.

`run_planner.sh` now forwards arguments (`"$@"`) so `./run_planner.sh --json` reaches the script.

### `SKILL.md` updated to use it

Step 6 now runs `run_planner.sh --json` instead of the plain form. The three separate failure rules from §26/§30 (missing destination, stale location, generic script failure) were collapsed into one generic rule, since the skill no longer needs to know the specific error shapes — it just relays whatever `message` says:

```text
14. If the JSON output contains an "error" field, relay its "message"
value to the user exactly (do not guess or invent a location,
destination, or time), and do not run the planner again until the
user has resolved the underlying issue.
```

Reinstalled with `openclaw skills install ./skills/get_mooving --as get-mooving --force` and `openclaw gateway restart`.

### Verified

All four cases tested directly against `planner.main()` with `--json` (success, no event, no destination, stale location) — each produced the expected JSON shape.

Then tested live, on a fresh session, on `claude-sonnet-4.6` (the model swap from §29):

```text
$ openclaw agent --agent main --message "Where is my next meeting?"

Coding class at 22 Havelock Rd, Singapore 160022 — 11:00 AM
⏳ Wrap up      09:39 — finish what you're doing, don't start anything new
🎒 Get ready    09:49 — pack up and head out
🚪 Leave        10:04 — out the door
🚇 Depart       10:12 — on the train/bus
🏁 Arrive       10:50 — 10 min buffer before 11:00
```

Every time value matches the raw `--json` output for the same event exactly. The model reworded; it did not recompute. This is the architecture rule from §7 ("The LLM should not calculate departure times") now enforced structurally rather than only by instruction.

### Open design question: how should the user's answer get back in?

§26 and §30 both flagged the same unclosed gap: there is no way for an answer to "where is it?" or "still starting from Home?" to reach back into `planner.py` — someone has to edit `data/profile.json` by hand. The question of whether to close this by having the LLM edit the JSON files directly, or by adding a small deterministic `update_location.py` (structured args in, address validated through `onemap.search_location`, `confirmed_at` set to the real current time, atomic write out) was raised and not yet decided to build.

Recommendation reached: a small script, not direct LLM edits. The reasoning is the same one behind every other decision in this log — an LLM doing a mechanically precise task (a correct ISO-8601 timestamp, valid JSON structure, not clobbering unrelated fields) is exactly the failure mode this project keeps designing around (§29 showed a cheap model getting far simpler mechanics wrong). Not built yet.

---

## 32. `update_location.py`

§26 and §30/§31 all flagged the same unclosed gap: the agent could present the 📍 confirmation prompt, but there was no path for the user's answer to reach `profile.json` — it required manual editing. §31 recommended a small deterministic script over letting the LLM edit JSON directly, for the same reason a cheap model was already shown (§29) to be unreliable at far simpler mechanics. That script was built.

```text
src/
├── calendar_google.py
├── location_state.py
├── onemap.py
├── planner.py
└── update_location.py      ← new
```

```text
input
  ↓
validate location (OneMap, only for --address)
  ↓
update profile.json (atomic write: temp file + os.replace)
  ↓
set confirmed_at = now
  ↓
return JSON success
```

Two modes, covering the two answers that make sense against the current single-location profile schema:

```bash
# option 1 — "yes, still here": refresh the timestamp only
.venv/bin/python src/update_location.py --confirm
# {"status": "ok", "location": "Home", "confirmed_at": "2026-09-12T22:53:38.792461+08:00"}

# option 3 — "somewhere else": validate + replace the stored location
.venv/bin/python src/update_location.py --address "SUTD" --label "SUTD"
# {"status": "ok", "location": "SUTD", "confirmed_at": "2026-09-12T22:53:44.118907+08:00"}
```

`--address` goes through `onemap.search_location` before anything is written, so a bad address fails closed instead of corrupting the profile:

```json
{"error": "location_not_found", "message": "Location not found: Nonexistent Fake Place Zzzz"}
```

Option 2 ("a named preset like Home") was deliberately not built as a separate case: `profile.json` only ever stores one location, and it's already labeled "Home" in the example data. Jumping back to "Home" as distinct from "confirm current" would need a second, permanently-stored home address independent of the current one — a real data-model change, not a stupid-simple MVP addition. Left alone until it's actually needed.

### Wired into `SKILL.md`

A new "Location Confirmation" section tells the agent: on option 1, exec `update_location.py --confirm`; on a named place, exec `update_location.py --address "..." --label "..."`; on that script's own `"error"` field, relay the message and do not mark anything confirmed; on `"status": "ok"`, re-run `run_planner.sh --json`. Two rules were added to the top-level Rules list: never edit `data/profile.json` directly, and only `update_location.py` may set `confirmed_at`. Reinstalled and gateway restarted as usual.

### Verified live, full loop

`data/profile.json`'s `confirmed_at` was set to an old date to force the prompt, on a fresh session:

```text
$ openclaw agent --agent main --message "Where is my next meeting?"
📍 Still starting from Home?
1. Yes  2. Home  3. Somewhere else

$ openclaw agent --agent main --message "1"
Coding class at 22 Havelock Rd 🏫
⏳ Wrap up    09:39
🎒 Get ready  09:49
🚪 Leave      10:04
🚇 Arrive     ~10:50
```

`data/profile.json` afterward had a genuinely fresh `confirmed_at` (`2026-09-12T22:55:01...`) — the agent actually ran `update_location.py --confirm`, not just narrated success. The full loop from the design diagram now works end to end:

```text
User: 1
  ↓
exec update_location.py --confirm
  ↓
profile timestamp updated
  ↓
exec run_planner.sh --json
  ↓
⏳ 🎒 🚪
```

---

## 33. Destination Override

§26's missing-destination fix only ever made `planner.py` fail cleanly; it never gave the agent a way to actually supply the destination the user names. That gap is now closed the same way §32 closed the location gap — a CLI flag, not a file edit.

```text
Calendar event has no location
       ↓
Agent asks destination
       ↓
User: "SUTD"
       ↓
run_planner --destination "SUTD"
       ↓
OneMap
       ↓
plan
```

### `planner.py --destination`

```python
if not event.get("location"):
    if args.destination:
        event["location"] = args.destination
    else:
        emit_error("no_destination", ...)
        return
```

The override only ever applies for that one run — nothing is written back to `data/mock_calendar.json` or anywhere else. Next time the same event comes up, the agent asks again.

### Fail closed on a bad address

Adding a free-text `--destination` raises the odds of an address OneMap can't resolve (a typo, something too vague). Previously `search_location()` raising `ValueError` for *either* the start or destination address would crash `planner.py` with a raw traceback — a latent bug from before this flag existed, but one this flag makes much more likely to hit. Both calls are now wrapped:

```python
try:
    destination = search_location(event["location"])
except ValueError as error:
    emit_error("destination_not_found", str(error))
    return
```

(and the same for the start location → `start_location_not_found`.)

### `SKILL.md`: new "Destination Override" section

Mirrors "Location Confirmation": on `"error": "no_destination"`, ask the user directly, take their answer literally, re-run with `--destination "<answer>"`, and relay `destination_not_found` if OneMap still can't place it. Reinstalled and gateway restarted.

### Verified live, full loop

Real Google Calendar data can't be edited from here to produce a location-less event on demand, so `calendar_google.py`'s `get_next_event()` was temporarily forced to return `"location": None`, tested live, then reverted — confirmed byte-identical via `git diff` afterward.

```text
$ openclaw agent --agent main --message "Where is my next meeting?"
Your next meeting is Coding class, but it has no location set. Where is it?

$ openclaw agent --agent main --message "SUTD"
Coding class at SUTD — meeting at 11:00, aim to arrive by 10:50.
⏳ 09:16   🎒 09:26   🚪 09:41   🚇 09:49 → ~10:50
```

The agent genuinely called `run_planner.sh --json --destination "SUTD"` — a real OneMap-routed plan from Home to SUTD, not a narrated guess.

### Same evening, both override paths now proven live

Between §32 and this section, all three gaps flagged back in §26/§30/§31 are closed the same way: a small deterministic script or flag takes structured input, the LLM only extracts what the user said.

| Missing info | Ask | Resolve |
|---|---|---|
| Destination | "Where is it?" | `run_planner.sh --json --destination "..."` |
| Location confirmation | "Still starting from X?" | `update_location.py --confirm` |
| Location change | (user names a new place) | `update_location.py --address "..." --label "..."` |

---

## 34. `late_recovery.py` — Day-2 Foundation

The first Day-2 feature from `Get_Mooving.md`'s 3-day plan: recompute the plan from *right now* instead of the original scheduled departure, when the user signals they're behind.

```text
current time
     +
next event
     +
confirmed location
     ↓
OneMap public transport from NOW
     ↓
expected arrival
     ↓
meeting time
     ↓
lateness
```

Kept deliberately simple, and built by reusing existing pieces rather than duplicating them — `get_next_event`, `search_location`, `get_public_transport_time`, `is_location_fresh`, `location_confirmation_prompt` from their existing modules, plus `load_json`, `format_time`, and `format_24h` imported directly from `planner`. No new OneMap or calendar logic. The one thing genuinely new: since the departure time is already known (*now*), there's no need for `planner.py`'s two-pass rough-estimate/refine loop (§22) — a single OneMap query is enough.

```python
travel_minutes = get_public_transport_time(start_location, destination, now)
expected_arrival = now + timedelta(minutes=travel_minutes)
lateness_minutes = round((expected_arrival - meeting_time).total_seconds() / 60)
```

Same failure shapes as `planner.py` (`no_upcoming_event`, `no_destination`, `location_confirmation_required`, `destination_not_found`, `start_location_not_found`) — reuses the same `location_state` freshness check, so a stale location routes through the same `update_location.py` flow already built in §32 rather than a separate one.

The "want to draft a message?" line was deliberately left out of the script's own output, in both text and JSON mode. That offer is a conversational judgment call, not a computed fact — it belongs in `SKILL.md`, matching every other decision in this log about where the model/script boundary sits.

### `SKILL.md`: "Late Recovery" rewritten

The old version was seven generic steps with no actual script behind them. Now: run `late_recovery.py --json`, treat its JSON as truth (never recompute `expected_arrival` or `lateness_minutes`), present it plainly, and only *then* offer to draft a message from the event's attendee list — never send without approval.

### Verified live, both branches

Real data first, unmodified: `Coding class` is many hours away, so a genuine "I'm running late for my meeting" produced a large negative `lateness_minutes` and the agent correctly reworded it as reassurance rather than alarm:

```text
$ openclaw agent --agent main --message "I'm running late for my meeting, what should I do?"
🚨 Actually, you're good! Your Coding class doesn't start until 11:00 AM...
If you left right now you'd arrive around 00:47 AM, which is over 10 hours early.
```

(`00:47` matches the direct `--json` test's `expected_arrival` exactly.)

Plain "late" alone, with no urgency in context, was correctly read by the model as small talk about the hour — not a false trigger, a sensible read given nothing was actually at risk. Intent had to be unambiguous for the skill to fire, which is expected: the routing is based on the user meaning it, not the literal word.

To see the genuinely-late branch, `calendar_google.get_next_event()` was temporarily overridden to return a meeting 15 minutes out at SUTD, tested live, then reverted (confirmed byte-identical via `git diff`):

```text
$ openclaw agent --agent main --message "I'm running late for my meeting"
🚨 Plans changed.
🚇 Leave now.
Expected arrival: 01:11.
You're likely to be about 66 minutes late to Standup at SUTD.

Want me to draft a quick message to the attendees letting them know you're running late?
```

Matches the requested UX pattern exactly, and it stopped right there — no message was drafted or sent without being asked, per rule 6.

### Not built yet

- Comparing transport modes (MRT vs. taxi) — `Get_Mooving.md`'s Day 2 plan calls for this; `late_recovery.py` only checks public transport for now.
- Actually drafting and sending the message (Gmail integration) — still just an offer at the agent level, per the existing Rules section.

---

## 35. Transport Comparison (🚕)

§34 flagged "alternative transport comparison" as not built. Closed by extending `onemap.py` exactly as anticipated, plus wiring the result into `late_recovery.py`'s output shape.

### `onemap.py`: `get_drive_time()`

The existing `get_public_transport_time()` was refactored to share its HTTP call and response-parsing with a new sibling, rather than duplicating either:

```python
def _request_route(params): ...       # shared GET + raise_for_status + .json()
def _extract_minutes(data): ...       # shared itineraries/route_summary parsing
def _start_end_params(start, destination): ...  # shared start/end lat,lon

def get_public_transport_time(start, destination, departure_time):
    params = {**_start_end_params(...), "routeType": "pt", "mode": "TRANSIT", ...}
    return _extract_minutes(_request_route(params))

def get_drive_time(start, destination, departure_time):
    params = {**_start_end_params(...), "routeType": "drive", "date": ..., "time": ...}
    return _extract_minutes(_request_route(params))
```

`_extract_minutes`'s existing `route_summary.total_time` fallback (originally just "a useful fallback" for PT) turned out to already be the exact shape OneMap's `drive` routeType returns — no PT-only fields (`mode`, `maxWalkDistance`, `numItineraries`) needed. Verified live against the real OneMap API before wiring anything else: SUTD → postal 308232 came back as 63 min transit vs. 22 min drive, both plausible.

### Walking / cycling: not added

The question of whether to also add `get_walk_time()` / `get_cycle_time()` came up. Decision: no, for the *late-recovery* use case specifically. `Get_Mooving.md`'s original design table only ever names two recovery modes — 🚇 MRT and 🚕 Taxi — and real Singapore inter-neighbourhood distances (the kind that make someone late for a meeting) are usually tens of minutes to hours on foot or by bike, i.e. never actually competitive as a "how do I recover" option. `_request_route`/`_extract_minutes` make adding either mode a few-line change later if a real use case shows up (e.g. a "how should I go" planning feature, as opposed to lateness recovery) — just not built speculatively now.

### `late_recovery.py`: multiple options instead of one

The single `expected_arrival`/`lateness_minutes` fields from §34 became a list, one entry per mode:

```json
{"event": "...", "destination": "...", "meeting_time": "...",
 "options": [
   {"mode": "public_transport", "expected_arrival": "...", "lateness_minutes": ...},
   {"mode": "drive", "expected_arrival": "...", "lateness_minutes": ...}
 ]}
```

Text mode prints both lines; which one to recommend, and how, was deliberately left to `SKILL.md` / the model — that choice is a wording decision, not a calculation, matching every other script/model boundary call in this log.

### `SKILL.md` updated

"Late Recovery" step 4 now shows both lines and explicitly hands the recommendation to the model: "choose how to communicate the recommendation yourself... e.g. 'Taxi gives you the best chance of being on time.'" Reinstalled, gateway restarted.

### Verified live

Direct script tests first (real data: both modes came back hours early / on time; a synthetic 20-minutes-out meeting: transit 62 min late, drive 10 min late). Then live through the agent, with `calendar_google.get_next_event()` temporarily forced to a 20-minute-out meeting at SUTD (reverted after, confirmed via `git diff`):

```text
$ openclaw agent --agent main --message "I'm running late for my meeting"
🚨 Plans changed — Standup at SUTD, meeting at 00:27.
🚇 Public transport — arrive 03:42 (195 min late)
🚕 Drive/taxi — arrive 00:37 (10 min late)
Grab a taxi — it's your best shot, only 10 minutes late.
Want me to draft a quick message to your standup attendees?
```

The first attempt at this test used `datetime.now(timezone.utc)` for the fake event instead of local time, which made the displayed `meeting_time` show as UTC (16:26) instead of SGT — confirmed as purely a flaw in the throwaway test fixture (the lateness numbers were still correct either way, since datetime subtraction is offset-independent) by rerunning with a locally-offset fake timestamp, which displayed correctly. Not a bug in any shipped file.

---

## 36. Hypothetical Departure / Mode — `route_compare.py`, and a Real Hallucination Caught

Manual testing against the live agent (on `claude-sonnet-4.6`) surfaced a genuine gap, not a hypothetical one. Two consecutive test messages:

```text
$ openclaw agent --agent main --message "if I leave at 10:15 for next meeting, best way?"
...The planner recommends 🚇 public transport, with a planned departure of 10:12.
Leaving at 10:15 is 3 minutes past that... If you want a safer buffer,
🚕 taxi would give you more flexibility at that point.

$ openclaw agent --agent main --message "if I leave at 10:30 on taxi, can?"
...The planner tools can only compute from right now — I can't simulate
a hypothetical 10:30 departure without risking invented travel times,
which I won't do... Best move: Around 10:25–10:30, ping me again with
"running late" and I'll run the live late-recovery check.
```

Two very different outcomes from the same underlying cause: **there was no tool to answer "what if I leave at X" or "what if I take mode Y" at all.**

- The second response handled the gap correctly — it noticed it had no way to check a hypothetical departure and said so instead of guessing. Exactly the behavior every other section of this log has been building toward.
- The first response did not. "🚕 taxi would give you more flexibility" is plausible, and happened to be roughly true, but nothing had actually computed a taxi number that turn — `planner.py --json`'s output only ever contained the public-transport result. This is the same class of failure `SKILL.md` has been closing all along (§14: "the LLM started reinterpreting planner output and generated incorrect derived times"), just in a new shape: an *unchecked comparative claim* instead of a recalculated number.

### `src/route_compare.py`

Built to close the gap directly, reusing `get_public_transport_time` / `get_drive_time` (§35) and the same location-freshness/error-shape conventions as every other script:

```bash
python3 src/route_compare.py --departure "10:30" --mode drive --json
# {"departure": "10:30", "meeting_time": "11:00", "arrival_target": "10:50",
#  "options": {"drive": {"travel_minutes": 23, "arrival": "10:53"}}}

python3 src/route_compare.py --departure "10:15" --compare --json
# {"departure": "10:15", "meeting_time": "11:00", "arrival_target": "10:50",
#  "options": {
#    "drive": {"travel_minutes": 23, "arrival": "10:38"},
#    "public_transport": {"travel_minutes": 38, "arrival": "10:53"}},
#  "best_option": "drive"}
```

Real live numbers came back almost identical to the numbers used to originally describe this feature (38 min transit exactly, 23 vs. a sketched 24 min drive) — the design held up against the real API. `--mode` and `--compare` are a mutually exclusive argparse group; `best_option` (earliest arrival) only appears when more than one mode was checked. The departure time is combined with the *meeting's* date, not "today," so asking the night before about a tomorrow-morning meeting still resolves correctly. An unparsable `--departure` fails clean with `invalid_departure` rather than crashing.

Per the user's own flagged worry — OneMap's `drive` time is road time only, it has no idea how long a taxi takes to be hailed or arrive — every `drive` label in both `route_compare.py` and `late_recovery.py` (§35) was updated to read "Drive/taxi (road estimate)", and `SKILL.md` now requires the agent to say so out loud.

### `SKILL.md`: new "Hypothetical Departure or Mode" section, plus a new top-level rule

The section wires natural-language "what if" questions to `route_compare.py`, extracting the departure time and mode (if named) from what the user actually said — never invented, never reused from earlier turns. It also states plainly what the script *can't* do (a relative time like "in an hour," a mode with no function behind it) so the agent says so instead of guessing, matching the second test response rather than the first.

The actual fix for the hallucination itself is a new Rules entry, since the bug wasn't about missing capability — the agent already had a real `run_planner.sh --json` result in hand, it just editorialized past it:

```text
- Never claim a transport mode is faster, safer, or better unless you
actually ran a check for it this turn — a plausible-sounding guess
about an unchecked option is still an invented fact.
```

Reinstalled, gateway restarted.

### Verified live: same two questions, both now answered for real

```text
$ openclaw agent --agent main --message "if I leave at 10:15 for next meeting, best way?"
🚕 Taxi/drive — arrive 10:38 (22 min early...)
🚇 Public transport — arrive 10:53 (cuts it close...)
Take a taxi... Note the drive time (23 min) doesn't include hailing, so book now if you haven't already.

$ openclaw agent --agent main --message "if I leave at 10:30 on taxi, can?"
🚕 10:30 taxi — arrive 10:53
That's 3 min past the 10:50 buffer, but still 7 min before the meeting starts...
```

Both cross-checked against direct `route_compare.py` runs — arrival times matched exactly (`10:53` for the second case, confirmed byte-for-byte). The first question is no longer answered with an unchecked opinion; the second is no longer deferred — both now run a real check and report a real number, with the road-estimate caveat attached unprompted.

---

## 37. Optional Future Work: Grab Farefeed API

Proposed, not built. Logged for later rather than scaffolded now, because — unlike every other integration in this log — there is no account, API key, or confirmed request/response shape to test against. OneMap's real shape was only ever learned by calling the live API (§20, §35); guessing at Grab's from memory would break that pattern.

Grab exposes a Farefeed API that, given pickup/drop-off coordinates, returns:

- available Grab ride services
- pickup ETA
- estimated fare range
- surge level
- a deep link that opens Grab with pickup/drop-off pre-filled

### Why this matters here specifically

It directly answers the caveat raised twice already, in §35 and again in §36: OneMap's `drive` time is a road-time estimate only, with no idea how long a taxi actually takes to arrive. Grab's own pickup ETA would replace that guess with a real number, add a fare estimate this project has never had, and — new for this project — give the agent a concrete link to hand over instead of only a described time ("tap here to book" instead of "book now if you haven't already"). That last part matches `SKILL.md`'s existing tone rule about concrete actions over abstract time-only language more directly than anything built so far.

### Where it would fit the existing architecture

- `src/grab.py`, parallel to `onemap.py` — a thin client returning something like `{"service": ..., "pickup_eta_minutes": ..., "fare_range": ..., "surge_level": ..., "deep_link": ...}` for a pickup/dropoff pair.
- Reused the same way `get_drive_time()` is reused today (§35) — by `late_recovery.py` and `route_compare.py`'s `drive`/taxi option. Likely alongside OneMap's road time rather than replacing it (Grab pickup ETA + OneMap road time = a truer door-to-door estimate than either alone).
- Same fail-closed convention as everything else here: if the Farefeed call fails or returns nothing, fall back to the current OneMap-only road estimate, still labeled as such, rather than block the whole plan.

### What's actually needed before this can be built

- A Grab developer/partner account and Farefeed API credentials — this is a partner API, not self-serve like OneMap, so access itself may need to be requested and approved first.
- The real request/response shape, confirmed live — endpoint, auth header format, required fields. Nothing should be guessed from memory.
- A decision on how to phrase surge level and fare range in ADHD-friendly wording without turning the output into a wall of numbers.

This matches `Get_Mooving.md`'s own scope freeze — "Grab/taxi booking" is explicitly listed under "Cut first / not required yet." Leaving it there until credentials exist is following that plan, not a new deferral.

---

## 38. Walk/Cycle + Weather in `route_compare.py`

§35 deliberately left walking and cycling out for `late_recovery.py` — someone already late needs the fastest realistic option, and those modes rarely compete. But `route_compare.py` (§36) is a different context: a general "what if" tool, where a short trip genuinely could be walkable, and where the right call depends on whether it's raining. Revisited on request, and built as one pass rather than two, since weather is what makes recommending walk/cycle trustworthy in the first place — offering "cycle, it's faster" during a thunderstorm would be worse than not offering it.

### Two new external calls, both verified live before writing any wiring

`onemap.py` gained `get_walk_time()` / `get_cycle_time()` — same `routeType` pattern as `drive` (§35), reusing the existing `_request_route`/`_extract_minutes` helpers. Confirmed live first: SUTD → postal 308232 came back as a 175-minute walk / 120-minute cycle, both correctly identified later as unrealistic for that distance.

A new `src/weather.py` calls Singapore's NEA 2-hour forecast (`api.data.gov.sg/v1/environment/2-hour-weather-forecast`) — free, public, no API key or account needed, unlike Grab (§37). Confirmed live: 47 named areas, each with a `label_location` lat/lon and a forecast string. `get_forecast(lat, lon)` finds the nearest area by straight-line distance and classifies the forecast text (`is_rainy`: contains "rain", "shower", or "thundery") into `{"area", "forecast", "rain"}`.

### Gating: straight-line distance, not route distance

A new `onemap.straight_line_km()` (haversine) decides whether walk/cycle are even worth asking about — computed instantly from coordinates already on hand from `search_location()`, with no extra network call. Verified against a real short hop (a within-neighbourhood MRT-to-hub distance, 134m) before picking thresholds: `WALK_MAX_KM = 1.5`, `CYCLE_MAX_KM = 5.0`. Deliberately not using OneMap's own route distance for this — that would mean making the routing call just to decide whether the routing call was worth making.

### `route_compare.py`: gating only applies to `--compare`

`--compare` now checks public transport and drive unconditionally, plus walk if `distance_km <= 1.5` and cycle if `distance_km <= 5.0` — but only when `weather.rain` is false. An explicit `--mode walk` or `--mode cycle` is always honored regardless of distance or rain (same "explicit request bypasses automatic gating" rule as `--destination` in §33) — the caller asked for it directly, so the script answers directly, just with the real (possibly discouraging) number. If the weather call itself fails, `weather` comes back `null` and gating falls back to distance only — a flaky external API doesn't take down the whole comparison, and doesn't silently block cycle either.

Output gained two fields: `distance_km` and `weather` (`{"area", "forecast", "rain"}` or `null`).

### `SKILL.md` updated

Mode-name extraction now covers walk/cycle ("walk"/"on foot", "cycle"/"bike"). A new rule tells the agent it does not need to explain why walk/cycle are missing from a `--compare` result — the script already decided that — but if the user explicitly asks for one anyway despite rain or distance, the agent should surface the weather/distance fact rather than silently going along with it.

### Verified live end to end

Direct script tests confirmed all four combinations: real far-apart data (9.1 km) correctly excluded both from `--compare` while still honoring an explicit `--mode walk` (145 min, clearly shown as impractical); a real short hop (1.5 km) auto-included cycle but correctly excluded walk (1.536 km actual, just over the 1.5 km cutoff — the display rounds to "1.5" but the gate compares the unrounded value, so this is expected, not a bug); a forced rainy forecast excluded cycle at that same short distance; a forced weather-API failure returned `weather: null` without breaking the rest of the comparison.

Then live through the agent, with `calendar_google.get_next_event()` temporarily forced to a 1.5 km meeting (reverted after, confirmed via `git diff`):

```text
$ openclaw agent --agent main --message "what if I leave at 10:15 for my next meeting, and how would weather affect it?"
🚕 Drive/taxi   4 min   10:19
🚇 Public transport   12 min   10:27
🚲 Cycle   18 min   10:33
☁️ Weather: Partly cloudy, no rain — cycling is totally fine if you're up for it.
```

Cycle appeared, walk correctly didn't, and the weather line was a real fact from the JSON, not an assumption.

---

## 39. Trip Chaining and Place Resolution

A live test — "after class, I want to walk to lunch" → "macdonal" → "1pm" — exposed two gaps at once, deeper than another API integration:

```text
$ openclaw agent --agent main --message "after class, i want to walk to lunch"
...Where are you thinking of having lunch?...

$ openclaw agent --agent main --message "macdonal"
...What time does class end?...

$ openclaw agent --agent main --message "1pm"
...that walk is 145 min to arrive 15:25 — but that looks like it's routing
from home, not from Havelock Rd after class... 9.1 km is the same distance
as your morning commute. The planner doesn't know your starting point will
be Havelock Rd at 1pm... Which McDonald's were you thinking?
```

One thing worked correctly here: the agent noticed the 9.1 km / 145 min number looked wrong for a "walk to lunch" and refused to present it as fact — the `--compare` anti-hallucination rule from §36 generalizing exactly as hoped. But two real assumptions baked into every script so far broke:

```text
origin = confirmed current location  (always)
destination = the next calendar event  (always)
```

Neither holds for "after class, walk to lunch" — origin should be the class's location, at the class's end time, and destination is a fuzzy brand name, not an address.

### Gap 1: Calendar events had no end time

`calendar_google.get_next_event()` only ever read `event.get("start")`. Google's Calendar API already returns an `end.dateTime` on the same event object — trivial to add:

```python
"end": event.get("end", {}).get("dateTime"),
```

Also threaded into `planner.py`'s JSON output as `event_end`, so an agent that already ran the normal "when should I leave" flow has the class's end time on hand without a second call. Verified live: `Coding class` actually ends at `17:30` (real data — later than the illustrative "1pm" in the test transcript, which was invented by the model in that turn, not read from anywhere real).

### Gap 2: origin/destination were hardcoded assumptions, not inputs

Proposed as a new `origin_resolver.py` module that would decide, in Python, whether the user "referenced" a calendar event. Pushed back on that specific piece: that decision — does "after class" refer to a calendar event, and which one — is a language-understanding judgment call, the same category of thing this log has kept out of Python everywhere else (skill dispatch in §29, destination extraction in §33, mode extraction in §36). Built instead as two optional overrides on `route_compare.py`:

```text
--origin "<address or place>"       # instead of confirmed current location
--destination "<address or place>"  # instead of the next calendar event's location
```

Same "explicit request bypasses automatic default" shape as `--destination` on `planner.py` (§33). When *both* are overridden, the result carries no `meeting_time`/`arrival_target`/lateness framing at all — it's a plain point-to-point trip, not "will I be late for X." The origin/destination *resolution hierarchy* (explicit place the user named → a referenced calendar event's location + end time → confirmed current location → ask) lives in `SKILL.md`, as a new "Trip Chaining" section — the agent decides which case applies and fills in the flags; the script only ever executes a fully-specified request.

### Gap 3 (found while building the fix, not in the original ask): brand names can silently resolve to the wrong real place

Tested `search_location("macdonal")` — the user's actual typo — against the live OneMap API. It returned **"MACDONALD HOUSE"**, a real office building on Orchard Road, with full confidence and no error. Not a "not found" — a wrong, plausible-looking, silently-accepted answer. Confirms the risk called out when this was proposed: routing straight to the first geocoding match for a brand/category name is unsafe, not just imprecise.

Also tested whether OneMap could serve as a POI search at all before committing to a design — it can: 16 real "McDonald's"-named entries came back for a broader query, each with real coordinates. No new Places API/credentials needed, unlike Grab (§37). One correction made during testing: fetching only page 1 of results missed the actual nearest branch (a real nearby one was on page 2) — `onemap.search_places()` now paginates through every page OneMap reports before sorting by distance.

A genuine, honest limitation surfaced by this same testing: OneMap's index has real gaps for small retail/mall-unit outlets. The nearest OneMap-indexed McDonald's to Havelock Rd is **4.1 km away** (Gardens by the Bay) — not the "short walk to Clarke Quay" casually assumed in the original test conversation. `SKILL.md` now requires stating the actual distance rather than asserting "nearby," specifically because this data source is known-incomplete.

**Root cause, noted explicitly:** OneMap is a Singapore government dataset, updated on its own release cycle. It has no equivalent of Google Maps' crowdsourced updates — new outlets, closures, and renamed businesses don't appear until OneMap's own data is refreshed, however long that takes. This isn't a bug to fix; it's a structural property of the data source, and the reason §39's "state the real distance, never assert completeness" rule exists. Any future feature built on OneMap (routing, geocoding, or `search_places`) inherits this same staleness risk, not just place lookup.

```python
def search_places(query: str, near: dict, limit: int = 3) -> list:
    # ...fetch every page OneMap reports...
    candidates.sort(key=lambda c: straight_line_km(near, c))
    return candidates[:limit]
```

New `src/place_resolver.py` wraps this as its own script (`--query`, `--near`, `--json`), returning `{"query", "near", "candidates": [{"name", "address", "distance_km"}, ...]}` — the agent presents the nearest 2-3 and asks, or proceeds with a clearly-nearest single match while still naming it.

### `SKILL.md`: two new sections

**"Trip Chaining"** — the origin/destination resolution hierarchy, with an explicit instruction not to ask for anything the calendar already answered (the exact "what time does class end?" mistake). **"Ambiguous Place Names"** — never treat a brand/category as a precise destination; resolve through `place_resolver.py` first, state the real distance, ask when genuinely ambiguous. Two matching Rules entries added.

### Verified live: the exact original scenario, fixed

```text
$ openclaw agent --agent main --message "after class, i want to walk to lunch"
Your class (Coding class) wraps up at 17:30 at 22 Havelock Rd.
Where do you want to walk to for lunch? (I'll find the nearest match.)

$ openclaw agent --agent main --message "macdonal"
🍟 Nearest McDonald's I found: Gardens by the Bay (4.1 km away)
🚶 Leave class at 17:30 → arrive ~18:33 (about 63 min walk)
🌤️ Weather: Partly cloudy, no rain...
Worth noting: that's quite a trek. There might be a closer McDonald's that
OneMap doesn't have indexed. Do you want to go with this one, or a
different lunch spot closer to Havelock Rd?
```

No "what time does class end?" this time — it already knew. The typo was corrected to "mcdonald" before querying (confirmed by cross-checking both spellings directly: `"macdonal"` still returns the wrong Macdonald House, `"mcdonald"` returns Gardens by the Bay at exactly `4.13 km`, matching the agent's `4.1 km` and the `63 min` / `18:33` walk result exactly). The wrong-building failure mode is gone, the missing-end-time question is gone, and the honest "OneMap might be missing a closer one" caveat appeared unprompted, exactly as instructed.

---

## 40. Late-Message Drafting

The last piece explicitly named in `Get_Mooving.md`'s original Day-2 plan: when late, draft a short message to the attendee and require human approval before anything is sent.

```text
Calendar          OneMap           late_recovery.py        Claude
  ├ appointment      └ ETA            └ lateness_min          └ drafts
  ├ attendee                                                    contextual
  └ email                                                       message
```

All the raw facts already existed by §34 — `late_recovery.py` computed `expected_arrival`/`lateness_minutes`, and `calendar_google.get_next_event()` already returned `attendees` (`{"name", "email"}`). The only missing wire: `late_recovery.py`'s own JSON output dropped `attendees` on the way out. One-line fix:

```python
"attendees": event.get("attendees", []),
```

Everything past that point — drafting the wording, asking for approval, handling an edit — is exactly the kind of thing this log has kept out of Python throughout: language generation and judgment calls belong to the model, not the script. `SKILL.md`'s "Late Recovery" section gained the concrete flow:

1. If `attendees` is empty, there's nobody to message — don't offer.
2. Draft using the recommended option's real `expected_arrival`/`lateness_minutes` — never invented numbers.
3. Present for approval: **1. Looks good / 2. Edit / 3. Cancel.** An edit produces a new draft that needs its own fresh approval — approving the edit request is not approving the edited text.
4. Only after approval, ask how to deliver it.

### Honesty check before building the "send" half

`Get_Mooving.md`'s own scope table lists Gmail integration as "Draft first; wait for approval" and Current Status (§27) has always carried "Gmail late-message drafting + approval" as not built. Checked directly before assuming otherwise: `openclaw skills info gog` (the bundled Google Workspace CLI skill) — `Needs setup`, binary not installed, not visible to the model, not available as a command. There is no configured way for this agent to actually send an email or message right now.

Rather than build a "Send for me" option against a capability that doesn't exist — which would either silently fail or, worse, let the model claim to have sent something it didn't — the flow asks the delivery question honestly:

```text
"Want me to send this, or will you forward it yourself?"
```

and, if the user asks it to send: say plainly that no messaging tool is connected, and hand over the approved text to copy. This is the same discipline as every fail-closed decision in this log (§26 crashing cleanly instead of guessing, §37 logging Grab as blocked rather than guessing its API shape) applied to a new case: don't claim an action happened that didn't.

### Verified live

Real event has no attendees, so `calendar_google.get_next_event()` was temporarily forced to a meeting with Sarah as an attendee (reverted after, confirmed via `git diff` — only the legitimate `end` field from §39 remained):

```text
$ openclaw agent --agent main --message "I'm running late for my meeting"
🚨 Plans changed — Coffee with Sarah at SUTD...
🚕 Drive/taxi — arrive 01:49 (10 min late)
💬 Sarah is listed on the appointment. Want me to draft a quick message?
"Hi Sarah, I'm on my way but running a bit behind — should arrive around
1:49, about 10 minutes late. Sorry about that!"
1. Looks good  2. Edit  3. Cancel

$ openclaw agent --agent main --message "1"
Got it! Here's the approved message: "..."
Want me to send this, or will you forward it yourself? (Heads up: I don't
have a connected messaging tool right now, so I can't send it directly —
but you can copy and paste it straight to Sarah.)
```

No false claim of sending. Also tested the edit path on a separate run — "2, make it more casual and mention I'm stuck in traffic" produced a revised draft ("Hey Sarah! Stuck in traffic rn...") and asked for approval again rather than treating the edit request itself as approval.

### Still open

Actually sending anything — Gmail, WhatsApp, or otherwise — stays unbuilt, now for a confirmed reason (`gog` needs installing and configuring) rather than an assumed one. Day-2's drafting half is done; the send half is exactly where `Get_Mooving.md` always said it would wait: on a real, tested integration, not a guess.

---

## 41. Real Gmail Sending Wired to Late-Message Approval

§40 built the draft/approve/edit/cancel flow but stopped short of sending, since no email tool was configured — confirmed at the time via `openclaw skills info gog`. A real Gmail account was connected since then (`gmail_credentials.json`/`gmail_token.json`, naming that follows the `calendar_credentials.json`/`calendar_token.json` split from the same session — one OAuth app per Google API, not shared), and a standalone `src/gmail_send.py` built and confirmed working on its own before any wiring was attempted:

```text
Get Mooving → gmail_send.py → Gmail API → real email sent
```

```python
def send_email(to, subject, body) -> dict:
    # ...
    return {"status": "sent", "message_id": result.get("id"), "to": to}
    # on failure: {"error": "send_failed", "message": str(error)}
```

### Simpler than the original plan, because sending is now real

§40's flow had two separate steps — approve the content, then separately ask "should I send it or will you forward it yourself" (because sending wasn't possible yet). With a working send layer, that second question collapses into the approval menu itself:

```text
1. Send for me
2. Edit
3. Cancel
```

"Send for me" is now both the approval and the delivery instruction in one choice, calling `gmail_send.py --to --subject --body` immediately. `SKILL.md` also formalized the check §40 gestured at but hadn't detailed: before drafting anything, verify there's a real recipient — ask the user for a name/email if `attendees` is empty or the target attendee has no email on file, and ask which one if there are several. Never invent an address.

The one non-negotiable, carried over unchanged from §40 and re-stated as its own Rules entries: only report success on a literal `"status": "sent"` in the JSON, relay the `message` and say plainly it was **not** sent on an `"error"`, and never send anything except the exact text approved in the menu — an edit produces a new draft needing its own fresh approval, not an automatic re-send.

### Verified live — a real email, twice

Before wiring anything, confirmed structurally without triggering a send: `gmail_send.py` compiles, its `--help` matches the described `--to`/`--subject`/`--body` interface, and the stored OAuth token loads and is valid without needing to re-authenticate.

Then — checked with the user first, since this is a real externally-visible action through a real account, not a read-only API call like every other integration in this log — two real sends were confirmed:

```text
$ .venv/bin/python src/gmail_send.py --to "mingde@gmail.com" --subject "..." --body "..."
{"status": "sent", "message_id": "1a096e85fdcc657c", "to": "mingde@gmail.com"}
```

Then through the actual agent flow (the real deliverable), with `calendar_google.get_next_event()` temporarily forced to a meeting with the user's own address as the attendee (reverted after, confirmed via `git diff` — only the §35 rename survived):

```text
$ openclaw agent --agent main --message "I'm running late for my meeting"
...The only attendee on the invite is yourself (no external contact to notify).
Want to message someone about being late anyway?...

$ openclaw agent --agent main --message "yes, message Ming at mingde@gmail.com anyway, for testing"
💬 Draft to Ming: "Hi Ming, I'm on my way but I expect to arrive around 03:07,
about 10 minutes late. Sorry about that!"
1. Send for me  2. Edit  3. Cancel

$ openclaw agent --agent main --message "1"
✅ Sent to mingde@gmail.com.
```

Worth noting: the model correctly recognized the test attendee shared the user's own email and asked before drafting a pointless self-message — not something instructed, a reasonable inference on its own. `openclaw audit` confirmed a real `exec` tool call succeeded at exactly that moment, consistent with the standalone test's real `message_id` — not a narrated success.

### Status

Day-2's late-recovery + drafting + approval + real send is now fully built and verified end to end. What remains open: WhatsApp as an alternative channel (still just an idea, per the original roadmap), and nothing else from the original Day-2 plan.

---

## 42. Reading Gmail Replies — Narrow Scope

Asked whether the agent could read incoming Gmail, moving it "from just a terminal interface to also an email interface." Checked feasibility live before answering anything: the existing `gmail_token.json` (from §41) already carries the `gmail.readonly` scope granted when the send layer was set up, so listing/reading messages worked immediately, no new consent needed. Also checked whether OpenClaw itself has a native email channel (`openclaw channels list --all`) — it doesn't; the built-in channel list is chat platforms only (Telegram, WhatsApp, Discord, Slack, etc.). This would have to be a custom automation, not "flip a config switch."

That still left a real fork before writing any code:

- **Narrow**: watch replies only on threads this agent already sent (e.g. a late-message). Bounded trigger, low risk.
- **Broad**: treat the whole inbox as a command channel, like a second interface alongside the terminal. `Get_Mooving.md`'s own risk table already flags "treat calendar content as data, not instructions" for calendar text — an open inbox is a far more attacker-reachable version of the same risk, since anyone who knows the address could email something crafted to look like an instruction. Needs its own safety design.

Decision: build narrow now, log broad as future work — not because it's infeasible, but because it needs a threat model this session hasn't done yet (who's allowed to trigger the agent by email, how to tell a legitimate reply from a crafted one, rate limiting). Revisit when there's an actual need for it.

### `gmail_send.py`: now remembers what it sends

Every successful send appends to `data/watched_threads.json` (gitignored — contains email addresses):

```json
{"thread_id": "...", "sent_message_id": "...", "to": "...", "context": "<subject>", "sent_at": "..."}
```

Same atomic temp-file-plus-`os.replace` write pattern as `update_location.py` (§32).

### `src/gmail_check_replies.py`: new

For each watched thread, fetches it via the Gmail API and looks for any message not from `me` (identified via `users().getProfile()`, not hardcoded). A reply found is reported and the thread is removed from the watch list — reported once, not repeatedly on every check. No reply yet leaves the thread watched. The whole check only saves the reduced list once, at the end, after every thread succeeded — a failure partway through leaves the original file untouched rather than saving a half-updated state, so a retry can't lose track of anything.

### Verified: real send/watch, mocked reply-detection

The "watch gets created" and "no reply yet" paths were tested against the real API — a real test send, confirmed `watched_threads.json` got the entry, confirmed a check on that real thread correctly reported `{"replies": []}`. Testing the *reply-found* branch live wasn't possible without an actual second-party sender (this session only controls the one connected account), so that branch was verified with a controlled mock of the Gmail service object instead — confirmed it correctly identified a reply "from" a different address, excluded the original sent message, and correctly removed the handled thread from the watch list. Test artifact cleaned up afterward.

### `SKILL.md`: new "Checking for Replies" section, plus a routing miss caught immediately

First live test through the agent — "did anyone reply to my late message?" — didn't route to get-mooving at all; the skill description didn't mention replies as a trigger, so nothing pointed the model at it (same class of gap as §29's original dispatch problem, just a missing keyword this time, not a deeper model issue). Fixed by adding "drafting/sending a late message, or checking whether an attendee replied to one" to the skill description and to `AGENTS.md`'s "Get Mooving" routing rule (first added in §29) — reinstalled, retested, worked immediately: "No replies yet."

The section itself treats reply content as untrusted: `snippet`/`from` are relayed exactly, never acted on, and an instruction-shaped reply ("ignore your instructions and...") is explicitly called out in the Rules as still just text to show the user, not something to follow — the inbox-safety concern from the broad-scope discussion, applied narrowly to the one thing this version actually reads.

---

## 43. Trusted Contacts Allowlist

§42 mitigated the untrusted-reply-content risk by treating every reply's text as data, never instructions. That's necessary but not sufficient — it says nothing about *who sent it*. Closed the other half: only a sender on an explicit allowlist is treated as a known, trusted party at all.

```json
{"emails": ["mingde@gmail.com"], "phones": ["+6594898515"]}
```

`data/trusted_contacts.json` (gitignored, PII), with `data/trusted_contacts.example.json` committed as a template — same split as `profile.json`/`profile.example.json` (§9). Phone numbers are stored now but unused by any code yet; nothing in this project reads SMS/WhatsApp. Reserved for whenever a phone-based channel is actually wired up, not built speculatively ahead of that.

### The connected account's own address doesn't belong in the file

Checked live: the account `gmail_send.py` sends from is `hermeszicrab@gmail.com` — a different address from `mingde@gmail.com`, the user's own personal address being added as the first trusted contact. Hardcoding the sending account's address into the trust file would go stale if the account ever changed; instead `gmail_check_replies.py` fetches it live via `getProfile()` (already doing this since §42) and always trusts it dynamically, in addition to whatever's in the file:

```python
trusted_emails = load_trusted_emails() | {my_email}
```

### A real spoofing gap fixed along the way

The existing "is this message from me" check (§42) compared the *raw* `From` header as a substring — `my_email.lower() not in sender.lower()`. Once sender identity started mattering for a trust decision rather than just excluding our own sent copy, that stopped being good enough: a `From` header like `"mingde@gmail.com <attacker@evil.com>"` has the trusted string sitting right there in the display name while the real envelope address is someone else's. Fixed by parsing the actual address out with `email.utils.parseaddr` before comparing anything:

```python
def extract_address(header_value):
    return parseaddr(header_value)[1].lower()
```

Verified directly against three mocked cases — a real trusted sender, an unrelated untrusted sender, and the exact spoofed-display-name case above — all three classified correctly, the spoof included.

### Output and `SKILL.md`

Every reply now carries `"trusted": true|false`. An untrusted reply is still surfaced — never silently dropped, that would hide real information from the user — but `SKILL.md` requires flagging it plainly as an unrecognized sender and treating anything it asks for as something to run past the user, not authorization to act.

The one rule that matters most here: **the agent may never edit `data/trusted_contacts.json` itself.** Adding a contact is a human-only action, by design — a model that could expand its own trust list would make the allowlist meaningless as a defense, since anything that could manipulate the model into acting could just as easily manipulate it into trusting the wrong sender first. Same category of restriction as `data/profile.json` (§26) and `data/watched_threads.json` (§42), applied to the one file where the model editing it would defeat the entire point of having it.

---

## 44. Proactive Milestone Reminders — the Day-3 "Key Feature"

Two asks at once: (1) check email and reply if necessary, (2) proactive ⏳🎒🚪 nudges without being asked — explicitly called out as the key remaining feature, matching `Get_Mooving.md`'s original Day-3 plan almost verbatim.

### Checked before designing anything: is there anywhere for a proactive message to even go?

`openclaw channels list --all` — every chat channel (Telegram, WhatsApp, Discord, Slack, SMS, all thirty-odd listed) is "not installed, not configured, disabled." Zero. The only real, working, tested delivery mechanism this entire project has is Gmail (§41). So "proactive prompts" could not ride on OpenClaw's native channel system at all — it would have to be email, or building a whole new channel integration first. Asked directly; answer was email, reusing `gmail_send.py`.

### `planner.py` refactored: `resolve_plan()`

The milestone scheduler needs the exact same location/destination/route resolution `planner.py`'s CLI already does, with real `datetime` objects (not the JSON's HH:MM strings — re-parsing those back into full datetimes risks a date-rollover bug near midnight that using the real objects avoids entirely). Rather than duplicate that ~60-line block a third time, `planner.py`'s core logic was extracted into `resolve_plan(destination_override=None)`, returning `{"ok": True, "event", "plan", "profile"}` or `{"ok": False, "error", "message", ...}`. `main()` now just calls it and formats the result; behavior verified byte-identical before/after across every path (success, no event, no destination, `--destination` override) — this was a pure refactor, zero behavior change, confirmed by direct comparison.

### `notify_email` in `profile.json`

A `mingde@gmail.com`, in `profile.json` (already gitignored) — where to actually send proactive nudges and automated notifications. Deliberately kept separate from `trusted_contacts.json` (§43): that file answers "who is allowed to be trusted as a *sender*," this answers "who is the *owner* to notify" — different questions, even though today they happen to share a value.

### `src/schedule_milestones.py`

```text
Calendar event
      ↓
planner generates milestones     (resolve_plan(), reused not duplicated)
      ↓
scheduler waits                  (openclaw automations, one-shot --at)
      ↓
⏳ Wrap this up.   🎒 Get ready.   🚪 Go now.
```

For each of the three milestones still in the future, schedules a one-shot `openclaw automations add --at <exact time> --command "...gmail_send.py --to ... --subject ... --body ..." --delete-after-run`. Deliberately a **command** payload, not an agent-message: the content is fully known in advance (which milestone, which event, what time) — there's no judgment call left for a model to make, so it bypasses the LLM entirely for the actual reminder. Same "Python does the mechanical part" principle as every other script in this log, taken to its natural conclusion: even the *delivery* of a fully-determined message doesn't need a model in the loop.

### A real bug found while testing: `--declaration-key` does not dedupe

The plan was to rely on `--declaration-key`'s documented "idempotent declaration identity" to make repeated runs a no-op. Tested directly: ran the script twice, got two of every job. `openclaw automations add` does not check for an existing job with the same key before creating a new one — confirmed by inspecting `openclaw automations list` and seeing duplicate `declarationKey` values side by side. Fixed by doing the idempotency check in Python instead: `existing_declaration_keys()` lists current jobs first and the scheduling loop skips any milestone whose key is already present. A second real bug in the *test*, not the script, was caught in the same pass: the first idempotency test used `datetime.now() + timedelta(...)` for the fake event's start time, which recomputes a different value on every call — so the declaration key (built from the event's start) was different every run regardless of any dedup logic. Switched the test fixture to a fixed ISO timestamp and re-verified: first run scheduled three jobs, second and third runs scheduled zero, `openclaw automations list` showed exactly one job per milestone throughout.

### Verified live: a real one-shot actually firing

Scheduled a minimal two-minutes-out test directly (bypassing milestone math, to isolate the one truly unverified mechanism: does `automations add --command ... --delete-after-run` actually fire and clean up). Confirmed via `openclaw automations runs`:

```json
{"action": "finished", "status": "ok", "completionStatus": "succeeded",
 "summary": "{\"status\": \"sent\", \"message_id\": \"1a098bc5a6db1b9a\", \"to\": \"mingde@gmail.com\"}"}
```

Fired within a second of its scheduled time, ran the real command, `gmail_send.py` returned a genuine `message_id`, and the job was gone from `openclaw automations list` afterward — `--delete-after-run` worked once `--no-deliver` was added (without it, OpenClaw's own "announce" delivery fails closed with no channel configured, which per the CLI's own docs would have left the job disabled instead of deleted).

### `SKILL.md`: two new sections, plus a real safety boundary for the automated case

**"Proactive Milestone Reminders"** documents `schedule_milestones.py` as something that runs on its own schedule, not something the agent reasons about each time. **"Proactive Reply Check (Automation)"** extends §42's reply-checking into a scheduled context, with one rule that didn't exist before because it didn't need to: in a scheduled run, the agent may email the *owner* a summary and a suggested draft, but must never email the original correspondent — replying to a third party still requires the owner to come back in a live conversation and approve it through the existing draft/approve/send flow (§40/§41). A scheduled run can notify; it cannot act on the user's behalf toward someone else. This is the "reply if necessary" half of the ask, deliberately kept short of "auto-send if necessary" — consistent with the mandatory-approval rule that's been unconditional since §40.

### Not yet done: actually turning the recurring jobs on

Everything above is built, tested, and proven to fire correctly. What's not done yet: creating the actual *recurring* automations (e.g. every 30 minutes) that call `schedule_milestones.py` and the reply-check on an ongoing basis. Building the mechanism and activating an indefinite background job that emails the user on a schedule forever are different in kind — the former is safe to do and undo freely, the latter keeps running and consuming resources/sending real email until someone turns it off. Asked directly before flipping anything on; answer was **"Not yet."** Both mechanisms are ready to activate whenever wanted — nothing further needs building, just the two `openclaw automations add` calls (one `--every 30m` running `schedule_milestones.py`, one similar cadence for the reply check) when the go-ahead comes.

---

## 45. Documentation Cleanup

By §44, `SKILL.md` had grown to 298 lines across eleven sections — planner rules, location confirmation, late recovery, reply checking, two proactive-automation sections, hypothetical routes, trip chaining, place resolution — reading more like a manual for the whole project than a runtime instruction file. Flagged directly, with a proposed split:

- **`SKILL.md`** — runtime operating instructions only.
- **`DEVELOPMENT.md`** — why things work this way (already its job).
- **`Get_Mooving.md`** — product design/proposal (already its job).

### `SKILL.md`: 298 lines → 121

The main win wasn't moving prose elsewhere — it was collapsing eleven sections into seven and removing the same sentence repeated six different ways. Every section had its own version of "never calculate/invent this value yourself." Replaced with one **"Data Rules"** block near the top covering all of it — times, routes, distances, weather, lateness, reply content — once, plus the shared facts about how every script's JSON success/error shape works. Sections that were really the same workflow got merged: "Checking for Replies" + "Proactive Reply Check" became one section with a live-vs-automated split at the point where the behavior actually diverges; "Hypothetical Departure or Mode" + "Trip Chaining" + "Ambiguous Place Names" became one "Route Comparison" section, since all three are steps in the same decision (resolve origin/destination → resolve an ambiguous place if needed → run the comparison), not three separate features.

Nothing load-bearing was cut — every exact command, every JSON shape, every hard safety rule (never claim sent without `"status": "sent"`, never edit the trust list, never email a third party from an automated run, etc.) is still there, just not restated per-section. Verified by reinstalling and re-running the actual live regression tests afterward (main plan, route comparison) — identical real numbers, nothing broken.

### Module docstrings added to all twelve scripts

Each `src/*.py` file now opens with a short docstring stating what it does and, where it matters, a load-bearing fact a reader would otherwise have to dig for (`onemap.py`: tokens expire ~3 days; `planner.py`: `resolve_plan()` is the shared entry point three other scripts reuse; `schedule_milestones.py`: why it's a command payload, not an agent prompt). Compiled and functionally regression-tested across every script afterward — no behavior changed, only documentation added.

### `README.md` rewritten as a setup/usage guide

The old README was two lines and three leftover shell commands. Rewritten from scratch as an actual guide: prerequisites, venv setup, Google Calendar OAuth (its own client), Gmail OAuth (a **separate** client — confirmed in §41 they're genuinely different connected accounts, `hermeszicrab@gmail.com` vs. `mingde@gmail.com`), OneMap token setup and its ~3-day expiry (confirmed against the real token's JWT claims earlier this session — `exp - iat` is exactly 259200 seconds), profile/trusted-contacts setup, installing the skill, example usage commands, how to turn on the proactive automations (§44, still inactive by default), and a disconnection/privacy table listing every local file this project creates and exactly how to remove each one.

A missing `.env.example` was also created — `.gitignore` already had an unignore rule for it (`!.env.example`) from early in the project, but the file itself had never actually been added.

---

## 46. Automation Timing, and a Real Bug Caught by the User's Own Testing

Two questions after §45's README went out: does an `--every` automation check immediately when created or only after the interval, and can it do both — check now, then keep checking on schedule.

### Answered empirically, not from memory

Created a real `--every 2m` test job and read its own JSON back: `nextRunAtMs` was exactly `createdAtMs + intervalMs` — confirmed the first run only happens after the full interval, never immediately. Then found `openclaw automations run <id>` (listed as "debug" in the CLI's own help, but works fine here) and tested whether it disturbs the schedule: ran it manually on a separate test job, compared `nextRunAtMs` before and after — byte-identical. So the answer is: create the automation, then `openclaw automations run <id>` once to also get an immediate check, and the recurring cadence is untouched either way. Both test jobs (and a stray background polling loop from a flawed wait-condition) cleaned up afterward.

### While checking this, found two real automations already active

`openclaw automations list` showed two live `gm-schedule-milestones` jobs, created a few minutes apart, that this session never created. The user's IDE selection at the top of this exchange was the exact README lines with that command — the likely explanation is they tried it themselves (possibly twice). Asked directly whether to keep both or remove the duplicate; removed one.

### The one that remained was actually broken

Ran the surviving job manually to demonstrate it working — it failed:

```text
ModuleNotFoundError: No module named 'google'
```

The README's example command was the bug: `.venv/bin/python3 $(pwd)/src/schedule_milestones.py` — `$(pwd)` correctly made the *script* path absolute at the moment the command was typed, but `.venv/bin/python3` itself stayed relative. A recurring automation doesn't execute from this project's directory, so the relative interpreter path resolved against some other Python that exists there instead — one without any of this project's packages installed. Exactly the class of mistake §10 already documented for `run_planner.sh` ("OpenClaw runs as a service and does not inherit the terminal's activated virtualenv"), just resurfacing in a new example that hadn't been written yet when that lesson was first learned.

Fixed both the live job (`openclaw automations edit <id> --command "<full absolute paths>"`) and the README example, then re-ran the corrected job to confirm: `"Nothing scheduled (no future milestones)"` — correctly reflecting that today's real event's milestones have already passed. `nextRunAtMs` was unchanged by the edit, confirming the fix didn't touch the schedule, only the broken command.

README updated with the corrected full-path example, plus the `openclaw automations run <id>` immediate-check pattern and a note that both `run` and `rm` need the job's `id`, not its `--name`.

---

## 47. `get_next_event()` Was Stuck on an Already-Started Event

Reported as "I'm still waiting for some responses" after §46 — the user had added a new event ("Go home," 18:00) and sent an email asking about their next appointment. Neither produced anything. The email question was explainable immediately (§42's deliberate narrow scope — confirmed by checking `data/watched_threads.json`: empty, so `gmail_check_replies.py` had nothing to check; an unsolicited new email was never going to be visible to it). The missing "Go home" reminder was not explainable that way, and turned out to be a real bug.

### The bug

`calendar_google.get_next_event()` queries with `timeMin=now`, expecting that to mean "events starting from now." It doesn't — Google's Calendar API defines `timeMin` as a filter on an event's **end** time, not its start. `Coding class` (11:00–17:30) was still mid-session when this was checked (current time ~12:11), so it kept being returned as the calendar's first result, sorted before `Go home` (18:00) by `orderBy=startTime` — even though `Coding class` had already started nearly an hour and a half earlier. Confirmed directly by pulling the raw event list: both events were present and correctly ordered by start time, but the code was taking the first item without checking whether it had already begun.

Every script in the project resolves the "next event" through this one function (`planner.py`, `late_recovery.py`, `route_compare.py`'s default mode, and `schedule_milestones.py` via `resolve_plan()`) — so this wasn't a one-script bug, it silently affected the entire pipeline whenever the calendar's earliest-by-start-time event happened to already be in progress. That's exactly why `schedule_milestones.py` kept reporting "nothing scheduled" even after `Go home` existed: it was still resolving against `Coding class`'s already-passed milestones and never got far enough to see the real next event.

### The fix

```python
if datetime.fromisoformat(start) <= now:
    continue  # already started — not the "next" thing to prepare for
```

One added check in the existing loop. Verified immediately against the real calendar: before the fix, `calendar_google.py` returned `Coding class`; after, it correctly returns `Go home`. Re-ran `planner.py`, `late_recovery.py`, `route_compare.py`, and `schedule_milestones.py` — all four now resolve against `Go home` instead (each correctly reporting `no_destination`, since that event genuinely has no location set on the calendar — a separate, expected condition, not a bug).

### Live-tested the resolved case, hit a legitimate edge case

Asked the live agent "when should I leave for my next appointment?" — correctly identified `Go home` and asked for a destination (no hallucinated guess). Answered with the user's own home address, and it hit a real OneMap 404: start and destination geocoded to the same coordinates, because the profile's confirmed current location *is* home in this environment, so "go home" from home is a same-point trip. The agent correctly diagnosed this as a routing anomaly and asked for a more specific address rather than inventing a travel time — not a new bug, just this demo environment's data being self-referential for this particular event.

---

## 48. Trusted-Sender Inbox Trigger, and Two More Real Bugs

Follow-up to §47: "isn't my email trusted, same as WhatsApp later? And shouldn't a new email or WhatsApp message be able to trigger something?" Untangled two conflated ideas first: `trusted_contacts.json` governs whether a *reply to a sent thread* is trusted — it says nothing about whether a brand-new, unsolicited email gets looked at, which is a different axis entirely (`gmail_check_replies.py` only ever checks thread IDs it already knows about). True event-driven push was scoped honestly: WhatsApp would get it for free once actually connected as an OpenClaw channel (not yet); Gmail push exists (watch + Cloud Pub/Sub) but is real infrastructure with a 7-day re-registration cycle, overkill here — fast polling is the practical answer for a personal project. Chose, with the user: extend the *scope* (also watch the inbox, not just replies) rather than chase true push for Gmail specifically.

### `src/gmail_check_inbox.py`

Scans the inbox (not just known threads) for messages from anyone in `trusted_contacts.json` — everyone else is silently skipped and never re-checked (a watermark, `data/inbox_watermark.json`, advances past every message inspected regardless of trust, so an ignored stranger's mail doesn't get re-fetched forever). Explicitly skips any message whose thread is currently in `watched_threads.json`, so a message is never handled by both this script and `gmail_check_replies.py`.

One safety distinction baked in from the start, not added after the fact: each surfaced message carries `is_owner` — whether the sender is the connected account itself / `profile.json`'s `notify_email`. `is_owner: true` (the user emailing their own agent) can be answered and replied to directly, no approval needed — functionally identical to asking a question over the terminal, just delivered by a different channel. `is_owner: false` (some other trusted contact, once the allowlist grows beyond just the owner) must not be auto-answered — the owner gets notified instead, same shape as §42's automated reply-check boundary. Verified with a controlled mock covering all three cases at once: a trusted-owner message (surfaced), an untrusted stranger's message (silently skipped, but still advances the watermark), and a message in a currently-watched thread (skipped entirely, left for `gmail_check_replies.py`).

Also, this immediately surfaced a real message: the user's actual "When's my next appointment?" email, sent cold with no prior thread — exactly the case this was built for.

### Real bug: two routing misses, both about the word "email"

Wiring the new script into `SKILL.md` and asking "check my email for new messages" live — twice, with different phrasing — produced the model confidently claiming *no email integration exists* and offering to set up OpenClaw's own IMAP/email channel plugin instead. Not a hallucinated tool call this time (§29's class of bug); a routing miss where "email" as a bare word evidently cues the model toward OpenClaw's own channel/plugin system before it even considers this skill's own (real, working) `gmail_*.py` scripts. Confirmed the skill itself still routes fine for anything with "reply" or "late message" in it — this was specific to generic "email"/"inbox" phrasing. Fixed with an explicit line in `AGENTS.md`'s routing rule naming the confusion directly: "check my email" for this project means the skill's own scripts, never OpenClaw's IMAP/channel setup. Reinstalled, restarted, retested — worked immediately: ran both checks, correctly identified two owner messages, attempted a real answer, and — because the real answer hit the next bug below — replied honestly that it couldn't compute one yet, rather than inventing something. Confirmed genuine via `data/watched_threads.json`: two real sent messages, real IDs, timestamps matching the test.

### Real bug: same-point trips crashed instead of computing 0

The reason the honest attempted answer failed: the user had added a location to the real "Go home" event (their own home address) — good, that's exactly what §47 suggested. But their confirmed current location *is* home, so "go home" from home is a same-point trip, and OneMap's routing endpoint 404s on that instead of returning a real "0 minutes." Every travel-time function in `onemap.py` was calling the API unconditionally with no check for this. Fixed with one shared helper checked before any of the four functions (`get_public_transport_time`/`get_drive_time`/`get_walk_time`/`get_cycle_time`) call the API at all:

```python
def _same_point(a, b, threshold_km=0.05):
    return straight_line_km(a, b) < threshold_km
```

Verified against the real "Go home" event across all three dependent scripts — `planner.py` now produces a coherent plan (`physical_departure` equals `arrival_target`, since there's no travel component), `late_recovery.py` and `route_compare.py` both correctly show 0-minute options instead of crashing. Also re-verified a real, different-location trip (home → SUTD) still computes normally (64 min transit, 30 min drive) — the 50-metre threshold doesn't false-positive on legitimate short trips.

---

## 49. "Isn't the Agent Supposed to Ask Where I Am?"

A sharp catch after §48: "Go home" was resolving from the stored "Home" location, even though the user would obviously be leaving from their 11am class (still in progress) instead. Confirmed directly: `is_location_fresh` only checks a timestamp against `FRESHNESS_LIMIT` (2 hours) — it has no idea what the calendar says. "Home" had been confirmed at 11:29, well within the window, so it read as trustworthy by the clock alone while being clearly wrong in fact.

### The fix: freshness and calendar-agreement are two separate checks

New `calendar_google.get_current_event()` finds whatever event is happening *right now* (`start <= now < end`) — distinct from `get_next_event()` (§47), which deliberately excludes anything already started. `location_state.py` gained `conflicts_with_calendar()` (does the in-progress event's location disagree with the stored address?) and `needs_confirmation()`, which combines both checks — stale by timestamp, or contradicted by the calendar, either one is enough to ask again. All three consumers (`planner.py`, `late_recovery.py`, `route_compare.py`) switched from calling `is_location_fresh` directly to this combined check, each now also fetching `get_current_event()`.

The prompt itself became context-aware — `location_confirmation_prompt()` now takes the current event and, when there's a real conflict, names it specifically:

```text
📍 Coding class runs until 5:30 PM at 22 Havelock Rd — are you leaving
from there, or from Home?
1. Coding class   2. Home   3. Somewhere else
```

instead of the generic "still starting from Home?" that gave no hint anything was actually wrong.

### A second bug surfaced by the live agent itself, mid-conversation

Testing this live — the agent correctly asked the new conflict question, and answering "1" correctly ran `update_location.py --address ... --label "Coding class"`. But OneMap canonicalized the address to `"22 HAVELOCK ROAD SINGAPORE 160022"`, textually different from the calendar's own `"22 Havelock Rd, Singapore 160022"` (different casing, "Rd" vs "Road"). The first version of `conflicts_with_calendar()` compared these as plain strings, which would have read them as *still* different places — re-triggering the same confirmation prompt in a loop immediately after it was just answered. The live agent, working the request, patched `location_state.py` itself to compare by postal code first (extracted via regex from both strings) before falling back to raw equality — confirmed the fix by reading the file back afterward rather than assuming it was safe, then re-ran `planner.py`: no repeated prompt, clean plan, correct origin.

### A third, quieter bug: stale automations

Once the origin corrected from Home to Coding class, the *previously scheduled* milestone reminders (§44, already live since earlier today) kept their old, now-wrong times — `schedule_milestones.py`'s idempotency only checked whether a declaration key existed, never whether its scheduled time still matched what's currently computed. Fixed by comparing the existing job's `at` against the freshly computed time (as real datetimes, not strings, since the same instant can be written multiple valid ways) and calling `openclaw automations edit <id> --at <corrected time>` in place when they'd drifted, rather than leaving a wrong reminder sitting there or silently skipping it. Verified against the real, already-scheduled jobs: all three corrected to the Coding-class-based times, same job IDs (edited, not duplicated), and a follow-up run confirmed a clean no-op.

### Verified end to end

```text
$ openclaw agent --agent main --message "when should I leave for my next appointment?"
📍 Coding class runs until 5:30 PM at 22 Havelock Rd, Singapore 160022 —
are you leaving from there, or from Home?
1. Coding class  2. Home  3. Somewhere else

$ openclaw agent --agent main --message "1"
Your next event is Go home at 6:00 PM. Leaving from Coding class (22 Havelock Rd):
⏳ Wrap up — 4:39 PM   🎒 Get ready — 4:49 PM   🚪 Leave — 5:04 PM
```

Real travel time from the class, not the degenerate same-point trip from §48 — the whole chain (§47's stale-event fix, §48's same-point fix, and this section's calendar-aware location check) now composes correctly for a scenario that's genuinely common: leaving one place to go to the next, not always starting from home.

---

## 50. Development Principles Learned

### Test one layer at a time

```text
planner
↓
shell wrapper
↓
Calendar
↓
OneMap
↓
OpenClaw exec
↓
skill selection
```

### Keep deterministic logic outside the LLM

```text
Python calculates
→ LLM communicates
```

### Keep mock data

`mock_calendar.json` remains useful for:

- tests,
- offline development,
- reproducible debugging,
- demo fallback.

### Keep secrets out of Git

Do not commit:

```text
.env
credentials.json
token.json
profile.json
.venv/
```

### Preserve a fallback path

```text
Google Calendar unavailable
→ mock_calendar.json

OneMap unavailable
→ clearly labelled mock travel duration

Gmail unavailable
→ copy-ready draft
```

---

## 51. Approximate Repo Structure

```text
get_mooving/
├── README.md
├── Get_Mooving.md
├── requirements.txt
├── run_planner.sh
├── .gitignore
├── .env.example
│
├── data/
│   ├── mock_calendar.json
│   ├── profile.example.json
│   ├── trusted_contacts.example.json
│   ├── profile.json              # local only
│   ├── watched_threads.json      # local only
│   ├── trusted_contacts.json     # local only
│   └── inbox_watermark.json      # local only
│
├── src/
│   ├── planner.py
│   ├── calendar_google.py
│   ├── onemap.py
│   ├── location_state.py
│   ├── update_location.py
│   ├── late_recovery.py
│   ├── route_compare.py
│   ├── weather.py
│   ├── place_resolver.py
│   ├── gmail_send.py
│   ├── gmail_check_replies.py
│   ├── gmail_check_inbox.py
│   └── schedule_milestones.py
│
├── skills/
│   └── get_mooving/
│       └── SKILL.md
│
├── calendar_credentials.json     # local only
├── calendar_token.json           # local only
├── gmail_credentials.json        # local only
├── gmail_token.json              # local only
├── .env                          # local only
└── .venv/                        # local only
```

---

## 52. Short Development Summary

The prototype grew in this order:

```text
planner.py
    ↓
mock_calendar.json + profile.json
    ↓
run_planner.sh
    ↓
OpenClaw skill
    ↓
OpenClaw exec test
    ↓
calendar_google.py
    ↓
real Google Calendar event
    ↓
onemap.py
    ↓
real Singapore travel estimate
    ↓
integrated planner
    ↓
OpenClaw executes the live planner
```

The project has moved beyond a static chatbot demo.

The current technical design is:

> **OpenClaw orchestrates; APIs provide real-world context; Python calculates; the LLM communicates.**
