# Testing

How this project is tested, and why it's split into three levels instead of one. For the reasoning behind individual bug fixes, see [DEVELOPMENT.md](DEVELOPMENT.md); this doc is about the testing *mechanism* itself.

---

## Some vocabulary first

If you're new to testing, these are the terms this doc (and the test file names) use:

| Term | Means | Example here |
|---|---|---|
| **Unit test** | Tests one function in isolation, with everything it calls mocked/faked. Fast, no network. | `calculate_plan()` given fixed inputs, checked against a hand-computed expected output |
| **Mock** | A fake stand-in for something real (an API call, a subprocess, a file) that you control completely in a test | Pretending `requests.get()` returned an expired-token error, without ever contacting OneMap |
| **Regression test** | A test written *because* a specific bug happened once, to make sure it can never silently come back | `test_invalid_timestamp_is_never_fresh` — pins down the exact crash from DEVELOPMENT.md §52 so it can't reappear unnoticed |
| **Smoke test** | A shallow "does it even turn on" check against the *real* system — not exhaustive, just enough to catch a broken wire (a dead API key, a missing scope, a renamed field) before it reaches a demo | Running `./run_planner.sh --json` for real, once, before showing the project to someone |
| **Integration test** | Tests that two or more real systems actually talk to each other correctly, not fakes of them | Calling the real Google Calendar API and confirming the shape of what comes back |
| **End-to-end / user flow test** | Tests the whole product the way a person actually experiences it, wording included | Typing "when should I leave?" into OpenClaw and reading the reply |
| **Coverage** | How much of the code a test suite actually exercises | Not tracked formally in this project yet — the goal right now is "the parts that have already broken once, and the parts a mistake would be expensive," not 100% |

The short version: **unit tests catch logic bugs cheaply and constantly. Smoke tests catch "the outside world changed" problems occasionally and deliberately.** Neither replaces the other — this project was already using smoke tests informally (every "tested deliberately with the real expired token" note in DEVELOPMENT.md is one); what's new here is making the *unit* layer explicit, fast, and automatic.

---

## The three levels

```
LEVEL 1 — UNIT TESTS
pytest · no internet · no Google · no OpenClaw · fast · runs constantly (and in CI)

        ↓

LEVEL 2 — INTEGRATION SMOKE TEST
real Calendar · real OneMap · real Gmail (to yourself) · real OpenClaw
run before a demo / before relying on a change for real

        ↓

LEVEL 3 — USER FLOW
talk to the agent normally, in English, through OpenClaw
check the behavior *and* the wording, since an LLM sits in this layer
```

**Why three, not one.** Level 1 is where almost every bug in this project has actually been caught during development — a wrong buffer calculation, a timestamp that crashes instead of returning `False`, an exception type nobody was catching. None of those need a real Google account to find; they need the pure function, called with the right input, checked against the right output. Making that the *fast, constant, automated* layer means those bugs get caught in seconds, not during a live demo.

Level 2 exists because Level 1 mocks the outside world — and the outside world genuinely changes underneath this project (OneMap tokens expire every ~3 days; Google's API occasionally returns something in a shape nobody anticipated). No amount of mocking catches "the real token is expired right now" — only actually calling OneMap does.

Level 3 exists because this is an agent, not just a script. `SKILL.md` decides wording and judgment calls (e.g. when to ask for approval before sending an email) that a Python test can't evaluate — only reading the actual reply can.

### Running each level

**Level 1** — from the project root, with the venv active:

```bash
pip install -r requirements-dev.txt   # first time only
pytest                                 # everything
pytest tests/test_planner.py -v        # one file, verbose
```

No `.env`, no `data/profile.json`, no Google/OneMap credentials are read — every test either exercises a pure function directly, or mocks the one thing that would otherwise touch the network (`requests.get`, `subprocess.run`, the Google API `service` object). `tests/conftest.py` is what makes `import planner` etc. work without turning `src/` into a package.

**Level 2** — manual, deliberate, run before a demo or before trusting a change that touches Calendar/OneMap/Gmail:

```bash
./run_planner.sh --json
./run_planner.sh --json --destination "SUTD"   # exercises the override path
```

along with whatever specific path just changed (e.g. temporarily swap `ONEMAP_TOKEN` for a bad one and confirm `{"error": "onemap_auth_failed", ...}` comes back clean — this is exactly how the DEVELOPMENT.md §52 fix was verified).

**Level 3** — talk to OpenClaw normally ("when should I leave?", "I'm running late", "who replied?") and read what comes back, the way the person actually using this would.

---

## What's covered so far (`tests/`)

| File | What it tests | How |
|---|---|---|
| `test_planner.py` | `calculate_plan()` — the wrap-up/get-ready/leave/arrival math every other feature depends on | Pure function, hand-computed expected output |
| `test_location_state.py` | Freshness, malformed timestamps, calendar-conflict detection | Pure functions |
| `test_onemap.py` | Postal-code fallback, `_extract_minutes()`, `_same_point()`, and every OneMap failure mode (missing token, HTTP error, expired-token-as-200-body) | `requests.get` mocked — no real OneMap call |
| `test_calendar_google.py` | Skips all-day events, skips an already-started event (§47 regression), finds the currently-in-progress event | Google API `service` object mocked |
| `test_late_recovery.py` | Lateness calculation and result shaping | Pure functions |
| `test_schedule_milestones.py` | Add / don't duplicate / reschedule-if-stale / ignore-past-milestones | `resolve_plan()` and `subprocess.run()` mocked — no real `openclaw` calls |
| `test_gmail_safety.py` | A reply is trusted by its real address, never its display name (a spoofed `"trusted@x.com" <attacker@evil.com>` header must resolve to the attacker's address) | Pure function + a temp file standing in for `trusted_contacts.json` |
| `test_whatsapp_trust.py` | A WhatsApp sender's number classifies correctly as owner/trusted/unknown, survives formatting differences (spaces, dashes), doesn't crash without `owner_whatsapp` configured | Pure function + a temp file standing in for `trusted_contacts.json` |
| `test_whatsapp_send.py` | The real `openclaw message send` failure shape (confirmed live pre-link: `{"ok": false, "error": {...}}`) and a non-JSON/command-not-found case both turn into the standard `{"error", "message"}` shape, never a crash | `subprocess.run` mocked |

This is deliberately not exhaustive — it covers the pure calculation core, every already-discovered real bug (so none of them can silently come back), and the one security-relevant rule (sender trust). Scripts that are almost entirely I/O plumbing around already-tested pieces (`update_location.py`, `route_compare.py`, `place_resolver.py`) don't have dedicated files yet; add one the same way if a bug is ever found in one.

---

## CI (GitHub Actions)

`.github/workflows/tests.yml` runs on every push/PR to `main`:

```
checkout
    ↓
install Python
    ↓
pip install -r requirements-dev.txt
    ↓
python -m compileall src
    ↓
pytest -v
```

**Only Level 1 runs in CI, deliberately.** GitHub Actions has no `.env`, no `calendar_credentials.json`/`calendar_token.json`, no `gmail_credentials.json`/`gmail_token.json` — none of that is committed (see `.gitignore` and the disconnect/privacy table in [README.md](README.md)), and it should stay that way. CI must never be handed personal Google/OneMap credentials just to make a smoke test pass; that's a real account's access sitting in a CI secret for no good reason. Level 2 and 3 stay manual, on a real machine, run by a person who already has those credentials.

The payoff this is aiming for: the next time a change accidentally reintroduces something like the stale-location bug or an uncaught OneMap exception, GitHub says so on the pull request — before it reaches a live demo, not during one.
