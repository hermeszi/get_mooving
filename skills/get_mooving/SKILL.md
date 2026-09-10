---
name: get-mooving
description: Help the user prepare and leave on time for their next appointment.
---

# Get Mooving Workflow

When the user asks when they should leave, or about their next meeting or departure plan:

1. Read the next appointment from the available calendar source.
2. Determine:
   - meeting time
   - destination
   - attendee, if available
3. Check the user's current or last-confirmed starting location.
4. If the location is stale, missing, or uncertain, ask the user to confirm it.
5. Get or use the travel duration.
6. You MUST run the project's deterministic planner script:

   /home/ming/42/openclaw/get_mooving/run_planner.sh

7. The script output is the ONLY source of truth for:
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
10. Never calculate or infer these times yourself.
11. Present the exact script output using short ADHD-friendly wording:

    - ⏳ Wrap up
    - 🎒 Get ready
    - 🚪 Leave now
    - 🚇 MRT
    - 🚕 Taxi

12. Prefer concrete actions over abstract time-only language.
13. If the script fails, say that the planner could not be run. Do not guess.
14. If the script reports that the event has no location set, ask the user for the destination. Do not guess or invent one, and do not run the planner again until a destination is available.

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