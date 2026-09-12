---
name: get-mooving
description: Use for next meeting, meeting location, when to leave, travel/departure plans, transition timing, or running late.
---

# Get Mooving Workflow

This is not a callable tool. There is no tool named "get-mooving" — do not try to call one. Follow these instructions directly using your normal tools (exec) to run the script below.

When the user asks when they should leave, or about their next meeting or departure plan:

1. Read the next appointment from the available calendar source.
2. Determine:
   - meeting time
   - destination
   - attendee, if available
3. Check the user's current or last-confirmed starting location.
4. If the location is stale, missing, or uncertain, ask the user to confirm it.
5. Get or use the travel duration.
6. You MUST run the project's deterministic planner script in JSON mode:

   /home/ming/42/openclaw/get_mooving/run_planner.sh --json

   This prints one JSON object on success:

   {"event": ..., "destination": ..., "meeting_time": ..., "arrival_target": ..., "wrap_up": ..., "get_ready": ..., "leave_prompt": ..., "physical_departure": ..., "transport": ...}

   or one JSON object with an "error" field on failure:

   {"error": "<reason>", "message": "<human-readable text>", ...}

7. The JSON output is the ONLY source of truth for:
   - event title
   - destination
   - meeting time
   - wrap-up time
   - get-ready time
   - leave-prompt time
   - physical departure time
   - arrival time
8. Never use example values from this file.
9. Never reuse times from an earlier conversation.
10. Never calculate, convert, or infer these times yourself. Reword the field values for tone; never change or recompute them.
11. On success, present the exact field values using short ADHD-friendly wording:

    - ⏳ Wrap up
    - 🎒 Get ready
    - 🚪 Leave now
    - 🚇 MRT
    - 🚕 Taxi

12. Prefer concrete actions over abstract time-only language.
13. If the command produces no valid JSON at all (crash, empty output), say that the planner could not be run. Do not guess.
14. If the JSON output contains an "error" field, relay its "message" value to the user exactly (do not guess or invent a location, destination, or time), and do not run the planner again until the user has resolved the underlying issue (a missing event, a missing destination, or an unconfirmed location).

Example:

⏳  — Finish what you are doing. Do not start another task.  
🎒  — Pack your things and get ready.  
🚪  — Leave now.  
🚇 Expected arrival: about  .

# Late Recovery

When the user says:

late

1. Recheck the next appointment.
2. Confirm the current location if uncertain.
3. Recalculate travel from the current time.
4. Compare available transport options.
5. Recommend the best practical option.
6. If the user will be late, offer to draft a message to the attendee.
7. Never send a message without explicit user approval.

# Rules

- Never invent a location.
- Never invent a travel time.
- Never silently use stale location information.
- Never override planner.py calculations.
- Do not shame or scold the user.
- When plans change, focus on the next useful action.