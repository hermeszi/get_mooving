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
- [x] fixed Qwen model
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

### Still being developed

- [ ] automatic Get Mooving skill selection
- [ ] normal prompt → planner execution without explicitly saying "use exec"
- [ ] location freshness / confirmation
- [ ] destination override input, so an answer to "where is it?" can reach `planner.py`
- [ ] proactive scheduled prompts
- [ ] `late` recovery
- [ ] alternative transport comparison
- [ ] Gmail late-message drafting + approval
- [ ] structured planner output
- [ ] Docker / cloud deployment

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

## 29. Development Principles Learned

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

## 30. Approximate Repo Structure

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
│   └── onemap.py
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

## 31. Short Development Summary

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
