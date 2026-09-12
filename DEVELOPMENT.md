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

### Still being developed

- [ ] destination override input, so an answer to "where is it?" can reach `planner.py`
- [ ] location confirmation input, so a 1/2/3 answer can reach `planner.py` (same shape as above; §31 recommends a small `update_location.py` script over letting the LLM edit JSON directly)
- [ ] proactive scheduled prompts
- [ ] `late` recovery
- [ ] alternative transport comparison
- [ ] Gmail late-message drafting + approval
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

## 32. Development Principles Learned

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

## 33. Approximate Repo Structure

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
│   └── location_state.py
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

## 34. Short Development Summary

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
