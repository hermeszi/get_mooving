# Operating Get Mooving

Day-to-day use, once [SETUP.md](SETUP.md) is done: OpenClaw basics, the daily routine, using it, the proactive automations, and model/cost.

---

## OpenClaw basics

If you've never used OpenClaw before, here's what you actually need to know to operate it for this project.

**The Gateway** is OpenClaw's runtime — it has to be running for anything (a message, a scheduled reminder, an email check) to happen at all.

```bash
openclaw gateway status     # is it running?
openclaw gateway start      # start it as a background service
openclaw gateway restart    # restart (needed after config/skill changes)
openclaw gateway stop       # stop it
```

There are two ways to run it:

- **Background service** (`openclaw gateway start`) — keeps running after you close the terminal. This is what you want for Get Mooving, since scheduled reminders and email polling need it running continuously.
- **Foreground** (`openclaw gateway run`) — takes over the terminal and prints logs directly there. Stop it with `Ctrl+C`. Useful for watching what's happening live while debugging, not for normal use.

If something seems broken:

```bash
openclaw doctor           # health check + suggested fixes
openclaw logs --follow    # tail the live gateway logs
```

## Daily routine

**Starting work:**

```bash
cd ~/42/openclaw/get_mooving
openclaw gateway start
openclaw gateway status
```

**If you changed `SKILL.md`:**

```bash
openclaw skills install ./skills/get_mooving --as get-mooving --force
openclaw gateway restart
```

**Test it:**

```bash
openclaw agent --agent main --message "When should I leave for my next appointment?"
```

**Finishing up:**

```bash
openclaw gateway stop
openclaw gateway status    # should show stopped
```

## Use it

Talk to your OpenClaw agent normally — no special syntax:

```bash
openclaw agent --agent main --message "when should I leave for my next meeting?"
openclaw agent --agent main --message "I'm running late"
openclaw agent --agent main --message "what if I leave at 10:30 by taxi?"
openclaw agent --agent main --message "did anyone reply to my late message?"
```

Or in whatever chat surface your OpenClaw is connected to — same skill, same behavior.

The first time it asks to confirm your location, answer it (or run `.venv/bin/python3 src/update_location.py --confirm` directly) — this checks every 2 hours, and also whenever a calendar event currently in progress suggests you're somewhere other than your last confirmed address.

---

## Proactive automations (optional, but this is the point)

Everything above only runs when you ask. To get real proactive behavior — reminders that arrive without being asked, and email questions that get answered automatically — you need the Gateway running **and** two recurring automations set up. Neither is on by default.

First, check what already exists so you don't create duplicates:

```bash
openclaw automations list --all
```

### A note on absolute paths

Every command below uses the **full absolute path** to `.venv/bin/python3` — never a relative one. A recurring automation doesn't execute from this project's directory, so a relative path resolves against whatever Python it happens to find, missing every package this project needs. This was a real bug caught the hard way (`ModuleNotFoundError: No module named 'google'`) — see DEVELOPMENT.md §46.

### Automation 1 — proactive ⏳🎒🚪 reminders

This one is cheap: it runs `schedule_milestones.py` as a plain command, no LLM involved. Python reads your calendar, computes real times, and schedules exact one-shot emails.

```bash
openclaw automations add \
  --every 10m \
  --name gm-schedule-milestones \
  --command "/home/ming/42/openclaw/get_mooving/.venv/bin/python3 /home/ming/42/openclaw/get_mooving/src/schedule_milestones.py" \
  --no-deliver
```

```text
Every 10 min
   ↓
check next Calendar event
   ↓
calculate travel + buffers
   ↓
schedule exact one-shot emails:
⏳ Wrap up · 🎒 Get ready · 🚪 Leave now
```

Safe to re-run this exact command any time — it checks what's already scheduled first and only adds or corrects what's needed (see DEVELOPMENT.md §49), never duplicates.

### Automation 2 — automatic email checking 📧

This one is different: an incoming email might say "when should I leave?" or "I'm running late" — OpenClaw needs to actually read it, understand it, run the right Get Mooving workflow, and potentially reply. That needs a real model-backed agent turn, not a plain command:

```bash
openclaw automations add \
  --every 10m \
  --name gm-email-poll \
  --agent main \
  --session isolated \
  --message "Check my email for new messages and replies using the Get Mooving skill. Run both the new-email and reply checks. If a trusted sender asks a Get Mooving question, answer it using the appropriate workflow and reply by email. If there is nothing new, do nothing." \
  --no-deliver
```

**This one is not free** — every interval, it starts a real conversation with your configured model. See "Model and cost" below before deciding on an interval.

| Interval | When to use |
|---|---|
| `--every 2m` | Testing only — confirms the wiring works quickly |
| `--every 10m` | Normal use |
| `--every 15m` | Low priority / cost-conscious |

### Check both are there

```bash
openclaw automations list
```

You should see both `gm-schedule-milestones` and `gm-email-poll`. These are stored by OpenClaw, so restarting the Gateway doesn't delete them — but they only actually *fire* while the Gateway is running.

### Test immediately, don't wait for the interval

```bash
openclaw automations list                              # find the job ids
openclaw automations run <MILESTONE-JOB-ID> --wait      # run the scheduler now
openclaw automations run <EMAIL-JOB-ID> --wait           # run the email check now
openclaw automations runs <JOB-ID>                       # see what happened on the last run(s)
```

A good first test: set the email poller to `--every 2m`, then send yourself "When should I leave for my next appointment?" and do nothing else — within a couple of minutes it should be detected, answered, and emailed back. Once confirmed, edit the interval back up for normal use (`openclaw automations edit <EMAIL-JOB-ID> --every 10m`).

### Managing the automations

```bash
openclaw automations disable <JOB-ID>   # pause without deleting
openclaw automations enable <JOB-ID>    # resume
openclaw automations rm <JOB-ID>        # delete permanently
```

### Gateway on/off controls both

```text
Gateway OFF  →  ❌ no email checking, ❌ no new proactive scheduling
Gateway ON   →  ✅ both resume automatically
```

So your day-to-day routine, once both automations exist, really is just:

```bash
openclaw gateway start   # start of day — resumes both automations
openclaw gateway stop    # end of day — pauses both, nothing deleted
```

---

## Model and cost

By default this project uses `openrouter/anthropic/claude-sonnet-4.6` — reliable, but not cheap, and every automated email check (if the poller is on) is a real conversation with it.

Check what's currently configured:

```bash
openclaw models status
openclaw agents list          # shows the model for this specific agent
```

List what's available and switch:

```bash
openclaw models list
openclaw models set <model-id>
```

**Before switching to something cheaper, read DEVELOPMENT.md §29.** A cheaper model (`openrouter/qwen/qwen3-30b-a3b-instruct-2507`) was tried first for exactly this reason, and it turned out to *silently* fail at the one thing this whole project depends on — reliably deciding to actually run the deterministic scripts instead of hallucinating an answer or claiming no tools exist. It's not just slower or lower quality; it can quietly break correctness in a way that's easy to miss. If you do switch to save cost, test with a plain "when should I leave" message afterward and confirm it's actually running `run_planner.sh` (real numbers, not a guess) before trusting it for anything scheduled.

`openclaw gateway usage-cost --all-agents` exists but showed `$0.0000` even with heavy real usage in testing here — this project's spend goes through OpenRouter directly, so **check [openrouter.ai's own activity/usage page](https://openrouter.ai/activity)** for real billing, not OpenClaw's local counter.

---

For disconnecting / removing all data, see the table in [README.md](README.md). For the reasoning behind every design decision, see [DEVELOPMENT.md](DEVELOPMENT.md).
