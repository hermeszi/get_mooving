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

   Add `--destination "<place>"` only if you already have one from the user this turn (see "Destination Override" below) — never invent one.

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
14. If the JSON output contains an "error" field, relay its "message" value to the user exactly (do not guess or invent a location, destination, or time). See "Destination Override" and "Location Confirmation" below for how `no_destination` and `location_confirmation_required` get resolved. For any other error, do not run the planner again until the user has resolved the underlying issue.

Example:

⏳  — Finish what you are doing. Do not start another task.  
🎒  — Pack your things and get ready.  
🚪  — Leave now.  
🚇 Expected arrival: about  .

# Destination Override

When the planner's JSON output has `"error": "no_destination"`, the calendar event has no location set. Ask the user directly, e.g. "Where is it?" Do not guess or invent a place.

1. Take the user's answer literally and re-run the planner with it:

   /home/ming/42/openclaw/get_mooving/run_planner.sh --json --destination "<what the user said>"

2. If the JSON output now succeeds, present the plan as normal.
3. If it instead returns `"error": "destination_not_found"`, relay the `message` to the user and ask for a more specific place or a postal code. Do not guess coordinates or fall back to a default location yourself.
4. This override is only for that one run — it does not change the calendar event or any stored file. Ask again next time this event comes up without a location.

# Location Confirmation

When the planner's JSON output has `"error": "location_confirmation_required"`, its `message` field is a 📍 prompt with numbered options (Yes / a named place / somewhere else). Present it exactly, then wait for the user's answer. Do not guess an address and do not edit `data/profile.json` yourself — always go through `update_location.py`:

1. If the user confirms they are still at that location (option 1, or "yes"):

   /home/ming/42/openclaw/get_mooving/.venv/bin/python3 /home/ming/42/openclaw/get_mooving/src/update_location.py --confirm

2. If the user gives a different location (option 3, or names a place directly):

   /home/ming/42/openclaw/get_mooving/.venv/bin/python3 /home/ming/42/openclaw/get_mooving/src/update_location.py --address "<address or place the user gave>" --label "<short name for it>"

   This validates the address before saving anything — trust its result, do not pre-validate or invent coordinates yourself.

3. Both forms print one JSON object:

   {"status": "ok", "location": "<label>", "confirmed_at": "<timestamp>"}

   or, if the address could not be found:

   {"error": "location_not_found", "message": "..."}

4. If it returns an "error" field, relay the `message` to the user and ask them to try a more specific address or a postal code. Do not mark the location confirmed yourself.
5. On `"status": "ok"`, re-run the planner:

   /home/ming/42/openclaw/get_mooving/run_planner.sh --json

6. Never edit `data/profile.json` directly, and never invent a `confirmed_at` timestamp — only `update_location.py` sets it.

# Late Recovery

When the user signals they are behind — "late", "just finished shower", "still at the MRT", "meeting just ended", or similar:

1. You MUST run the late-recovery script in JSON mode. This computes travel from right now, not the original planned departure:

   /home/ming/42/openclaw/get_mooving/.venv/bin/python3 /home/ming/42/openclaw/get_mooving/src/late_recovery.py --json

2. It prints one JSON object on success, with one entry per transport mode:

   {"event": ..., "destination": ..., "meeting_time": ..., "options": [{"mode": "public_transport", "expected_arrival": ..., "lateness_minutes": ...}, {"mode": "drive", "expected_arrival": ..., "lateness_minutes": ...}]}

   or an "error" field on failure, using the same reasons as the planner (`no_upcoming_event`, `no_destination`, `location_confirmation_required`, `destination_not_found`, `start_location_not_found`). Handle these exactly as documented above under "Destination Override" and "Location Confirmation", then re-run this script instead of the planner once resolved.
3. Never calculate, convert, or infer any `expected_arrival` or `lateness_minutes` yourself — use the exact JSON values for every option.
4. Present all options plainly, without scolding, for example:

   🚨 Plans changed.
   🚇 Public transport   arrive <expected_arrival> (<lateness_minutes> min late)
   🚕 Drive/taxi         arrive <expected_arrival> (on time)

   Then choose how to communicate the recommendation yourself — this is a wording decision, not a calculation. Recommend whichever option has the lowest (or no) lateness, in your own words, e.g. "Taxi gives you the best chance of being on time." If every option is late, say so plainly and recommend the least-late one rather than picking an arbitrary one.
   If an option's `lateness_minutes` is zero or negative, describe it as on time rather than inventing a late message for it.
5. Offer to draft a short message to the attendee, using the event's attendee list. Never send it without explicit user approval.
6. Support approve / edit / cancel on that draft.

# Hypothetical Departure or Mode

When the user asks a "what if" question about a specific departure time or transport mode — "what if I leave at 10:30?", "is 10:15 by taxi ok?", "best way if I leave at X?" — the planner's numbers from earlier don't answer this; they were computed for a different departure time. Never estimate this yourself, and never speculate about a mode you have not actually checked this turn (e.g. do not say "taxi would give you more flexibility" unless you just ran a check for taxi). Run the comparison script instead:

1. Extract the departure time the user actually said, in 24-hour HH:MM. Never invent one, and never reuse a time from earlier in the conversation.
2. Extract the transport mode if the user named one ("taxi"/"car" → drive, "train"/"MRT"/"bus"/"public transport" → public_transport, "walk"/"on foot" → walk, "cycle"/"bike" → cycle). If no mode was named, check the default set.

   One named mode (always honored exactly as asked, even if it's far or raining — see step 6):

   /home/ming/42/openclaw/get_mooving/.venv/bin/python3 /home/ming/42/openclaw/get_mooving/src/route_compare.py --departure "<HH:MM>" --mode <public_transport|drive|walk|cycle> --json

   No mode named — check public transport and drive, plus walk/cycle if they're realistic for this trip and it isn't raining (the script decides this, not you):

   /home/ming/42/openclaw/get_mooving/.venv/bin/python3 /home/ming/42/openclaw/get_mooving/src/route_compare.py --departure "<HH:MM>" --compare --json

3. It prints one JSON object on success:

   {"departure": ..., "meeting_time": ..., "arrival_target": ..., "distance_km": ..., "weather": {"area": ..., "forecast": ..., "rain": ...} | null, "options": {"<mode>": {"travel_minutes": ..., "arrival": ...}, ...}, "best_option": "<mode>"}

   (`best_option` only appears when more than one mode was checked. `weather` is `null` if the forecast lookup failed — don't treat that as an error, just don't mention weather.) Or an "error" field on failure, using the same reasons as the other scripts — handle exactly as documented above.
4. Never calculate, convert, or infer `travel_minutes`, `arrival`, `distance_km`, or the weather fields yourself — use the exact JSON values.
5. Always describe a `drive` result as a road-time estimate — it does not include how long a taxi takes to get hailed or arrive.
6. `--compare` already excludes `walk`/`cycle` when they're too far or when `weather.rain` is true — you don't need to filter them yourself, and you don't need to re-explain why they're absent. If the user explicitly names walk or cycle with `--mode` despite rain or distance, the script still computes it (that's an explicit request, not a suggestion) — mention the rain or the distance so they can judge for themselves, rather than silently going along with it.
7. This is a one-off check for that specific departure/mode. It does not change the plan from the main workflow, and nothing is saved anywhere.
8. This script can only compute from a real departure time and a mode it has a function for. It cannot check "in an hour from now" without a concrete clock time, and it cannot check a mode with no function behind it. If asked something outside that, say so plainly rather than guessing.

# Rules

- Never invent a location.
- Never invent a travel time.
- Never claim a transport mode is faster, safer, or better unless you actually ran a check for it this turn — a plausible-sounding guess about an unchecked option is still an invented fact.
- Never silently use stale location information.
- Never override planner.py calculations.
- Never edit data/profile.json directly; only update_location.py may change it.
- Do not shame or scold the user.
- When plans change, focus on the next useful action.