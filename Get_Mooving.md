# Get Mooving

**ADHD-Friendly Meeting Travel & Transition Agent**  

> **Project theme:** OpenClaw agent + messaging app communication demo  
> **Scope key:** Build/demo scope first. Future ideas should not block the 3-day MVP.

---

## 1. Selected Problem Statement

### Target users

People with ADHD or time blindness who experience recurring difficulty:

- tracking time,
- starting preparation on time,
- switching away from current tasks,
- leaving on time,
- and recovering calmly when running late.

This proposal frames the solution as **executive-function support** — scaffolding for time perception, transitions, and communication — not as a medical or clinical treatment.

Calendar and mapping apps usually remind or estimate, but they do not manage the transition from:

> "I need to go"

to:

> actually leaving.

### How might we...

How might we build an agent that combines a person's:

- calendar,
- Singapore travel estimates,
- location confirmation,
- and personal time buffers

to help them transition, leave on time, re-plan when delayed, and communicate gracefully when they will be late?

---

## Why standard reminders fail: lateness as a chain reaction

Lateness for individuals with ADHD is rarely caused by simple math errors about travel duration. It can involve several executive-function stages:

1. **Time blindness** — difficulty intuitively tracking time passing.
2. **Procrastination / delayed start** — underestimating prep time and deferring initial action.
3. **Transition difficulty** — hyperfocusing or struggling to stop a current task.
4. **Lateness** — slipping past the true physical departure window.
5. **Panic & shame** — executive overload that can cause further delay, freeze, or avoidance.

Standard calendar reminders such as "15 minutes before" may arrive too late if task switching and preparation have not started. Mapping apps also tend to assume the user can depart immediately from a known location.

---

## Core ADHD Design Features

| ADHD challenge | Design feature | What it solves | MVP behaviour |
|---|---|---|---|
| Time blindness | **External Time Cues** | Difficulty sensing passing time internally | Agent pushes structured milestones anchored to the current appointment |
| Procrastination & delayed start | **Earlier Prep Prompts** | Underestimating pre-departure preparation | Prep prompt is separated from the actual leave prompt |
| Transition difficulty | **Push Scaffolding** | Difficulty breaking focus and switching tasks | Distinct "wrap up", "get ready", and "leave now" cues |
| Optimistic time estimates | **The Invisible Buffer** | Assuming friction-free best-case timing | Prompts shift earlier without falsifying the route ETA |
| Late panic & shame | **The Guilt-Free Command** | Panic/shame delaying recovery action | Texting `late` recalculates ETA, compares options, and prepares an apology |

### Demo promise

In one short flow, the agent:

1. conducts a morning check-in,
2. finds the next meeting,
3. confirms the current/starting location,
4. calculates route + personal buffers,
5. issues wrap-up / get-ready / leave-now prompts,
6. re-checks when context is uncertain or the user is delayed,
7. provides late recovery,
8. and drafts a message to the attendee.

---

# 2. Scope and Proposed Approach

The scope is frozen around a **3-day build**. Each day must end with something demoable.

## Day 1 — The Foundation

### Goal

Make this work end-to-end:

> **"When should I leave for my next meeting?"**

### Build / deliverables

- Install and configure OpenClaw.
- Connect or mock Google Calendar.
- Read the next relevant calendar event.
- Extract:
  - event time,
  - destination,
  - attendee when available.
- Establish starting location.
- Store:
  - last-confirmed location,
  - confirmation timestamp.
- Ask again when location is missing or stale.
- Resolve preferred transport.
- Query OneMap or a test route provider.
- Calculate:
  - arrival target,
  - physical departure,
  - invisible buffer,
  - get-ready time,
  - wrap-up time.
- Return one clear departure plan.

### Example morning check-in

> **Agent:** Starting from where today?  
> `1 = Home`  
> `2 = SUTD / Work`  
> `3 = Other`

### Exit criterion

Do not stop until:

> **Calendar → event → location → route → personalised departure time**

works end-to-end.

---

## Day 2 — Late Recovery

### Goal

Make the command:

> `late`

trigger a useful recovery plan.

### Build / deliverables

- Parse the `late` text command.
- Re-read:
  - current time,
  - next appointment,
  - current/last-known location.
- Re-confirm location when needed.
- Recalculate travel from **now**.
- Compare:
  - public transport,
  - drive/taxi.
- Calculate expected arrival and lateness.
- Recommend the best practical option.
- Pull attendee information from the calendar event.
- Draft a short late message.
- Ask the user to approve before sending.
- Support:
  - approve,
  - edit,
  - cancel.
- Add tool-failure fallbacks.
- Run several scripted late scenarios.

### Exit criterion

Do not stop until:

> **`late` → fresh route → recovery recommendation → message draft → approval**

works without the user re-entering meeting context.

---

## Day 3 — Proactive Coach + Demo

### Goal

Make the agent proactively help the user transition before the appointment.

### Build / deliverables

- Configure scheduler / cron / OpenClaw automation.
- Trigger:
  - **wrap up soon**
  - **get ready**
  - **leave now**
- Add simple snooze / acknowledge if stable.
- Make invisible buffer editable.
- Polish agent wording.
- Polish server / tool-call logs for exhibition.
- Rehearse 3 scripted scenarios.
- Prepare fallback route data.
- Record a short backup demo if practical.
- Attempt WhatsApp only if the core demo is already stable.

### Exit criterion

Freeze code early enough to rehearse.

> **Reliability beats one more feature.**

---

## Scope Freeze

### Must build

- Next calendar event
- Last-known / confirmed location
- Location confirmation logic
- Travel ETA
- Personal time buffers
- Push departure plan
- `late` recovery
- Email late-message draft + approval

### Nice if stable

- Proactive prompts
- Snooze / acknowledge
- Two transport modes
- WhatsApp message sending

### Cut first / not required yet

- Live GPS
- Continuous tracking
- Automatic buffer learning
- Grab/taxi booking
- Payments
- Complex optimisation

---

# Proposed Solution Overview

**Get Mooving** is an ADHD-friendly travel and transition agent for appointments.

It acts between the user's calendar and travel tools.

Instead of only reporting journey duration, it calculates:

- when the user should begin switching tasks,
- when they should get ready,
- and when they should physically leave.

If the plan slips, the agent re-plans from the current time and can prepare a context-aware late message.

## Design principle

The agent should be **practical and non-scolding**.

When the situation changes, it gives the next useful action rather than reminding the user that they failed the previous plan.

---

# Core Time Calculation

| Step | Calculation | Meaning |
|---|---|---|
| 1. Arrival target | Meeting time − early-arrival buffer | When the user wants to be at the destination |
| 2. Physical departure | Arrival target − live travel ETA | Latest route-based departure time |
| 3. Agent leave prompt | Physical departure − invisible delay buffer | Prompt earlier to account for real behaviour |
| 4. Get-ready prompt | Agent leave prompt − prep time | Start packing / shoes / laptop / toilet / etc. |
| 5. Wrap-up prompt | Get-ready prompt − task-switch warning | Stop starting new work and close the current task |

> **Important:** The invisible buffer changes prompt timing. It does **not** fake or inflate the route ETA shown to the user.

---

# Agent Loop

1. Read next appointment.
2. Check starting-location state and confidence.
   - Use the last confirmed location if recent.
   - Ask the user if it is old or missing.
3. Resolve origin + preferred transport.
4. Query travel estimate.
5. Apply personal transition buffers.
6. Tell the user what to do next.
7. Observe time / user state.
8. If delayed, re-plan and propose recovery.

---

# Personal Time Profile

| Setting | Example |
|---|---:|
| Prep time | 15 min |
| Early arrival | 10 min |
| Invisible delay | 8 min |
| Task-switch warning | 10 min |
| Transport preference | MRT / bus |

---

# Where Am I Now?

## Starting Location & Confidence Logic

Before calculating routes or departure buffers, the agent must establish the user's current starting-location state.

Live background GPS tracking is **not required** for the MVP.

### High confidence

If the location was explicitly set or confirmed recently:

- use it automatically,
- avoid bothering the user again.

Example:

```text
location: Home
confirmed_at: 13:30
confidence: high
```

### Low confidence

If the last confirmation is old or missing:

> **Agent:** Still starting from Home?  
> `1 = Yes`  
> `2 = Work / SUTD`  
> `3 = Other`

The agent should know when it **does not know** the user's location and ask instead of guessing.

---

# 3. Delivery, Measurement and Controls

## Data, Tools & Operating Constraints

| Data / Tool | Source | Owner | Access | Privacy / quality concern |
|---|---|---|---|---|
| Next appointment | Google Calendar | User | Read | Calendar may contain private event details |
| Event location | Calendar / user clarification | User | Read | Location may be missing or vague |
| Starting location | User profile / typed input | User | Read | Avoid storing precise location unless needed |
| Travel ETA | OneMap routing or test provider | External service | Read | ETA can change; route availability may fail |
| Personal buffers | Local JSON / SQLite profile | User | Read/Write | Keep simple and user-editable |
| Attendee contact | Calendar attendee / Gmail | User | Read | Must match the correct event/person |

---

# AI Models & Tools

| Model / Tool | Role | Constraint / fallback |
|---|---|---|
| Qwen3 30B A3B Instruct 2507 via OpenRouter | Intent understanding, tool selection, response generation, message drafting | Keep arithmetic and schedule calculations in code |
| OpenClaw | Agent loop, workflow and tool orchestration | Only authorised actions |
| LLM / AWS Bedrock | Interpret user requests, reason about next step, draft messages | Do not invent calendar, route, location, or attendee facts |
| Google Calendar | Read next event, destination and attendee | Read-only in MVP |
| OneMap | Travel-time estimate | Use test/mock ETA if live route integration fails |
| Local JSON / SQLite | Store profile and last-known location | Start simple |
| Scheduler / cron | Trigger proactive messages | Use simulated triggers if scheduler is unstable |
| Gmail | Prepare/send late message | Draft first; wait for approval |
| WhatsApp | Optional communication path | Only attempt after Gmail/core workflow works |

## Model Selection

**Current model:** `openrouter/qwen/qwen3-30b-a3b-instruct-2507`

**Why this model was chosen:**
- low cost for repeated agent testing,
- good instruction following,
- supports tool-oriented workflows,
- fixed model gives more consistent behaviour than `openrouter/auto`.

**Usage rule:**
- deterministic calculations such as departure times, buffers, and ETA arithmetic should be handled by application code,
- the LLM should mainly handle intent understanding, tool selection, missing-context questions, ADHD-friendly phrasing, and message drafting.

**Future option:**
- switch to another OpenRouter model or AWS Bedrock without changing the core application logic.

---

# Agent / Workflow Roles

These can be roles inside **one OpenClaw agent**. The MVP does not need separate LLM agents.

| Role | Responsibility | Input | Output | Ask / escalate when |
|---|---|---|---|---|
| Calendar Reader | Find next relevant appointment and extract context | Calendar + current time | Time, location, attendee | No event, missing location, ambiguous event |
| Location Resolver | Maintain starting-location state and confidence | Last-known state + user response | Confirmed origin | Location is stale or missing |
| Departure Planner | Combine ETA and personal buffers | Event + origin + travel ETA + profile | Wrap-up, prep, leave times | Origin or transport preference missing |
| Transition Coach | Issue calm prompts before departure | Milestones + timer | Wrap up / get ready / leave now | User disables or repeatedly snoozes |
| Late Recovery Planner | Re-plan from now and compare travel options | Current time + event + fresh ETA | Best option + expected arrival | All options are late or route data unavailable |
| Communication Assistant | Draft a short delay message | Event + attendee + ETA | Draft / approved send | Attendee missing/ambiguous or no user approval |

---

# Integrations and Manual Fallback

The demo should never depend on every external service working live.

- If **Google Calendar** fails: use a manual test event.
- If **OneMap** fails: ask for a travel duration or use a clearly labelled test/mock ETA.
- If **Gmail** fails: show a copy-ready message.
- If **proactive scheduling** fails: expose manual demo controls for wrap-up, get-ready and leave-now.

The core reasoning flow should remain demonstrable.

---

# Interaction Tone

| Avoid | Prefer |
|---|---|
| "You should have left 18 minutes ago." | "Plans changed. MRT now arrives about 3:14; taxi about 2:54." |
| Long explanations when already late | One next action, one ETA, one recovery choice |
| Shame or scolding | Neutral, practical recovery language |

---

# ADHD-Friendly Temporal Language

The agent should communicate time in ways that are **concrete, immediate, and easy to act on**.

Abstract clock times and durations can be difficult to hold onto when someone experiences time blindness. Where practical, the agent should pair clock time with an **event marker, countdown, physical action, or familiar comparison**.

## Communication Rules

### 1. Pair clock time with a concrete event

Avoid giving only:

> Leave at 1:52 PM.

Prefer:

> **Leave when this countdown ends — about 1:52 PM.**

Or, when the context is known:

> **When your current meeting ends, pack up and head out.**

The clock time should still be available for accuracy, but it should not be the only cue.

### 2. Convert distant actions into “what happens next”

Instead of:

> Your meeting is in 1 hour 25 minutes.

Prefer:

> **You do not need to leave yet. Finish this task, then get ready.**

Instead of:

> Leave in 20 minutes.

Prefer:

> **One more short task, then shoes on.**

### 3. Make transition cues physical

Use short action language:

- **Wrap this up.**
- **Save your work.**
- **Pack your laptop.**
- **Use the toilet now if you need to.**
- **Shoes on.**
- **Leave now.**

The goal is to reduce the amount of interpretation required from the user.

### 4. Use event-based markers when the agent knows the context

Examples:

> **When this video ends, start packing.**

> **When the laundry cycle finishes, it is time to get ready.**

> **After this meeting, do not start another task — leave for SUTD.**

> **When your 1 PM class ends, go straight to the MRT.**

The agent should only use event markers it actually knows about. It must not invent what the user is currently doing.

### 5. Use familiar comparisons for short durations

Where useful, pair minutes with something concrete:

> **About 5 minutes — roughly one youtube video.**

> **About 10 minutes — enough time to make a drink and pack your bag.**

These are optional communication aids, not replacements for the real timing calculation.

### 6. Bring preparation into the “Now” zone

Instead of treating the appointment as one distant deadline, break it into the next immediate action.

Example:

```text
3:00 PM meeting at SUTD

NOW
Finish your current task.

NEXT
Pack your laptop and get ready.

THEN
Leave.

LATER
Arrive around 2:50 PM.
```

This lets the user focus on one transition at a time.

### 7. When the user is late, reduce language further

Avoid:

> You should have left 18 minutes ago. Public transport will now take 48 minutes and your expected arrival time is 3:14 PM.

Prefer:

> **Plans changed.**
>
> 🚕 Taxi: arrive ~2:54 PM  
> 🚇 MRT: arrive ~3:14 PM
>
> **Best move: take a taxi now.**

Then offer one next action:

> **Want me to draft a message to Sarah?**

### 8. Use supportive recovery language, not blame

When the user misses a cue:

Avoid:

> You missed your departure time again.

Prefer:

> **We missed the original leave window. Here is the fastest plan now.**

The agent should help the user recover from the current situation rather than explain what they should have done earlier.

---

## Temporal Language Examples

| Situation | Avoid | Prefer |
|---|---|---|
| Early reminder | "Meeting in 75 minutes." | "You have time for one more task. After that, start getting ready." |
| Wrap-up | "Leave in 25 minutes." | "Finish what you are doing. Do not start another task." |
| Prep | "15 minutes until departure." | "Pack your things and put your shoes on." |
| Departure | "It is 1:52 PM." | **Leave now.** MRT arrival is about 2:50 PM. |
| Short delay | "You are 8 minutes behind schedule." | "Leave now and you should still arrive close to time." |
| Late | "You should have left 18 minutes ago." | "Plans changed. Taxi gets you there fastest." |
| Very late | "You will be 12 minutes late." | "Earliest arrival is about 3:12 PM. I can draft a message now." |

---

## Design Rule

> **Time should be communicated as an action, not only as a number.**

The agent can still show exact times for accuracy, but every important time cue should answer:

> **What should I do now?**

---

# Demo Storyboard / Shared User Stories

> Travel times below are illustrative demo values, not live OneMap estimates.

## Scenario 1 — Morning Setup

```text
Agent: Starting location today?
       1 = Home
       2 = SUTD
       3 = Other

User: 1
```

## Scenario 2 — Location Re-check

```text
Agent: Your next meeting is at SUTD at 3:00 PM.
       Still starting from Home?

       Y = Yes
       N = No
```

## Scenario 3 — Task Switching

The agent pairs exact timing with concrete actions:

```text
1:35 PM — Finish what you are doing. Do not start another task.
1:40 PM — Pack your laptop, get your things, shoes on.
1:52 PM — Leave now. MRT arrival is about 2:50 PM.
```

If the agent knows a suitable event marker, it can use that too:

```text
When this meeting ends, pack up and head straight to the MRT.
```

## Scenario 4 — Late Recovery

```text
User: late

Agent:
Transit: arrive ~3:14 PM
Taxi:    arrive ~2:54 PM

Recommendation: Taxi.
If needed, I can prepare a message for Sarah.
```

Late-message draft:

```text
Hi Sarah, I'm on my way but I'm likely to arrive around 3:12 PM,
about 12 minutes late. Sorry about the delay — I'll see you shortly.

Send?
[Y] Approve
[E] Edit
[N] Cancel
```

---

# Exhibition Controls

| Control | Purpose |
|---|---|
| **WHEN SHOULD I LEAVE?** | Normal planning flow |
| **I'M LATE** | Instant recovery / re-plan |
| **TELL THEM I'M LATE** | Draft + human approval |

---

# Success Measures

| Metric | Baseline | Target | How measured | Review |
|---|---|---|---|---|
| User knows next action | Ambiguous reminders | 100% single clear directive | User-flow evaluation during demo | Day 1 |
| Concrete temporal language | Clock-only reminders | Every major prompt includes a clear action, event cue, or immediate next step | Review scripted prompts | Day 3 |
| Location certainty | Stale/unknown origin may be assumed | Never calculate from stale/unknown location without confirmation | Test recent, stale, and missing location states | Day 1 |
| Zero-remember app checking | User must remember to open app | 100% proactive push prompts | Scheduler audit | Day 3 |
| Low-effort late recovery | Manual multi-app switching | ≤3 simple user inputs | Count steps during `late` | Day 2 |
| Missing-context resolution | Agent assumes or fails silently | Agent always asks when required context is uncertain | Test incomplete calendar/location cases | Day 1 |
| Explicit message approval | Uncontrolled automated messaging | 0 unapproved messages sent | Action log audit | All days |

## What a Successful 3-Minute Demo Looks Like

- The next event is retrieved without the presenter retyping its context.
- The agent establishes or confirms the starting location.
- The agent explains one realistic leave time and the personal buffers behind it.
- The user receives wrap-up / get-ready / leave-now prompts.
- `late` visibly triggers a fresh plan instead of repeating an old reminder.
- The agent proposes communication only when useful.
- No external message is sent until the user approves it.
- At least one external-tool failure can be simulated without collapsing the demo.

---

# Risks, Guardrails and Human Approval

| Risk | Consequence | Preventive control | Human owner |
|---|---|---|---|
| Wrong calendar event | User plans for wrong meeting | Show event title/time/location; allow "not this one" | User |
| Missing / wrong location | Bad route and leave time | Ask for clarification; do not guess | User |
| Stale location | Route begins from wrong origin | Track confirmation timestamp; re-confirm when stale | Agent/User |
| Stale / wrong ETA | Late arrival despite plan | Timestamp route data; label as estimate; recheck when late | Agent/User |
| Message sent to wrong person | Social/privacy harm | Use attendee from selected event; show recipient; explicit approval | User |
| Calendar/email privacy exposure | Sensitive information shown | Use minimum fields; avoid logging full event text | Builder/User |
| Prompt injection in calendar text | Event text redirects agent | Treat calendar content as data, not instructions | Builder |
| Notification fatigue | User ignores prompts | Use a few clear stages; allow snooze/disable | User |
| Invisible buffer feels deceptive | Loss of trust | Never falsify ETA; only shift coach prompt timing | Builder/User |

## Human Approval Points

Human approval is required:

- before any email / message is sent,
- before changing or cancelling a calendar event,
- when the selected attendee is ambiguous or missing,
- when route data fails or ETA is unreliable,
- before any paid transport action,
- and when all routes indicate lateness and a social response is needed.

---

# Research Notes

The project is informed by ADHD-related difficulties involving:

- executive function,
- time perception / time blindness,
- task initiation,
- task transitions,
- and chronic lateness.

The product should stay focused on **practical executive-function scaffolding**, not diagnosis or treatment.

Useful design ideas include:

- making time more visible,
- separating "start getting ready" from "leave now",
- breaking transitions into small actions,
- using external prompts,
- and planning for transition time rather than only travel time.

---

# 3-Day Build Board

## Day 1 — Plan

### Morning

- [ ] Create repository.
- [ ] Install OpenClaw.
- [ ] Complete onboarding.
- [ ] Verify model access.
- [ ] Create minimal Get Mooving skill / instructions.
- [ ] Connect or mock Google Calendar.
- [ ] Write next-event selector.
- [ ] Define user profile JSON.
- [ ] Define location-state JSON.
- [ ] Implement time calculation as a pure function.

### Afternoon / evening

- [ ] Connect OneMap or route stub.
- [ ] Ask for origin / transport when missing.
- [ ] Add location freshness / confidence check.
- [ ] Return prepare + leave time.
- [ ] Add basic tests for time formula.
- [ ] Freeze response format.

### Stop condition

> Do not stop until **"When should I leave?"** works end-to-end.

---

## Day 2 — Recover

### Morning

- [ ] Parse `late` command.
- [ ] Recalculate from current time.
- [ ] Re-confirm location if stale.
- [ ] Compare two route modes.
- [ ] Define late / very-late states.

### Afternoon / evening

- [ ] Connect Gmail for draft/send.
- [ ] Pull attendee from event.
- [ ] Ask for approval via text.
- [ ] Add approve / edit / cancel.
- [ ] Add tool-failure fallbacks.
- [ ] Run at least 5 scripted late scenarios.

### Stop condition

> Do not stop until **late recovery + message draft + approval** works reliably via text.

---

## Day 3 — Coach + Demo

### Morning

- [ ] Add scheduler / simulated prompt triggers.
- [ ] Implement wrap-up / prep / leave messages.
- [ ] Add snooze / acknowledge if stable.
- [ ] Make invisible buffer editable.

### Afternoon / evening

- [ ] Attempt WhatsApp only if core flow is stable.
- [ ] Polish server/tool logs for exhibition.
- [ ] Show tool-call / action log.
- [ ] Rehearse 3 demo scenarios.
- [ ] Prepare fallback / offline route values.
- [ ] Record a backup demo if practical.

### Stop condition

> Freeze code early enough to rehearse. **Reliability beats one more feature.**

---

# Definition of Done

- [ ] Calendar → next event → location → route → personalised departure time works.
- [ ] Agent never silently assumes a stale/unknown location.
- [ ] External time cues are visible in the demo.
- [ ] Major prompts use concrete, action-based temporal language rather than clock time alone.
- [ ] Earlier prep prompt is visible.
- [ ] Invisible buffer is visible in the timing logic.
- [ ] Task-switch scaffolding is visible.
- [ ] `late` produces a fresh ETA and recovery recommendation.
- [ ] A context-aware late message can be drafted from event data.
- [ ] Sending requires explicit human approval.
- [ ] At least one failure path has a manual fallback.
- [ ] Demo can run from a fresh start in under 3 minutes.
- [ ] Live GPS, auto-learning, taxi booking, payments and WhatsApp do not block the core demo.

---

# One-Line Pitch

> **Get Mooving manages the gap between "I have somewhere to be" and actually getting out the door — then helps the user recover calmly when the plan slips.**
