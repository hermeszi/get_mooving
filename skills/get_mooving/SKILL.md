---
name: get-mooing
description: Help the user prepare and leave on time for their next appointment.
---

# Get Mooing Workflow

When the user asks when they should leave:

1. Read the next appointment from the available calendar source.
2. Determine:
   - meeting time
   - destination
   - attendee, if available
3. Check the user's current or last-confirmed starting location.
4. If the location is stale, missing, or uncertain, ask the user to confirm it.
5. Get or use the travel duration.
6. Run the project's deterministic planner script:

   ./run_planner.sh

7. Use the planner output as the source of truth for calculated times.
8. Do not recalculate times yourself.
9. Present the result using short ADHD-friendly prompts:

   - ⏳ Wrap up
   - 🎒 Get ready
   - 🚪 Leave now
   - 🚇 MRT
   - 🚕 Taxi

10. Prefer concrete actions over abstract time-only language.

Example:

⏳ 1:29 PM — Finish what you are doing. Do not start another task.  
🎒 1:39 PM — Pack your things and get ready.  
🚪 1:54 PM — Leave now.  
🚇 Expected arrival: about 2:50 PM.

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