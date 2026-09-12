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

### Still being developed

- [ ] proactive scheduled prompts
- [ ] Gmail late-message drafting + approval
- [ ] Docker / cloud deployment

### Optional, blocked on external access (§37)

- [ ] Grab Farefeed integration — real pickup ETA, fare range, surge level, deep link. Needs Grab partner API credentials, which this repo does not have.

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

## 39. Development Principles Learned

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

## 40. Approximate Repo Structure

```text
get_mooving/
├── README.md
├── Get_Mooving.md
├── requirements.txt
├── run_planner.sh
├── .gitignore
│
├── data/
│   ├── mock_calendar.json
│   ├── profile.example.json
│   └── profile.json              # local only
│
├── src/
│   ├── planner.py
│   ├── calendar_google.py
│   ├── onemap.py
│   ├── location_state.py
│   ├── update_location.py
│   ├── late_recovery.py
│   ├── route_compare.py
│   └── weather.py
│
├── skills/
│   └── get_mooving/
│       └── SKILL.md
│
├── credentials.json              # local only
├── token.json                    # local only
├── .env                          # local only
└── .venv/                        # local only
```

---

## 41. Short Development Summary

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
