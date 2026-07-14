# Garmin Skill — Correctness Fixes

**Date:** 2026-07-14
**Status:** Approved, pending implementation

## Problem

The garmin skill cannot fetch any data. Investigation found four defects, one
dependency drift, and no CI to have caught any of them.

### 1. Dependency drift broke the auth API (root cause)

`requirements.txt` pins `garminconnect>=0.2.40,<1.0`. The installed version is
**0.3.3**. The 0.3.x line renamed `Garmin.garth` to `Garmin.client`. Both places
the skill touches that attribute are broken:

- `scripts/garmin_client.py:110` — `garmin.garth.dump(token_path)` raises
  `AttributeError` immediately *after* a successful credential login, so tokens
  are never persisted. Every subsequent run therefore performs a full login,
  which is what drove the account into a rate limit.
- `scripts/garmin_login.py:118` — `garmin.garth.load(token_path)` raises
  `AttributeError` at the verification step, so the recovery script fails too.

### 2. Expired tokens produce a misleading error

The stored refresh token expired 2026-03-25. In garminconnect 0.3.3,
`Garmin.login(tokenstore)` attempts a proactive token refresh *inside* the same
`try` block that loads tokens. When the refresh fails it sets
`tokens_loaded = False` and falls through to credential login. Because
`get_client` constructs `Garmin()` with no arguments for the token path, this
surfaces as `GarminConnectAuthenticationError: Username and password are
required` — which describes neither the cause nor the fix.

### 3. Two competing login paths; the worse one wins

`garmin_client.py:97` swallows the token-login failure (`except Exception:
pass`), then attempts a credential login using garminconnect's default **mobile**
User-Agent, which Cloudflare answers with HTTP 429. Meanwhile `garmin_login.py`
already implements a hardened flow — browser User-Agent plus retry with backoff —
to avoid exactly this. The client reimplements login, worse, and masks the real
error while doing so.

### 4. Silent data loss in periodic imports

`_safe_call` (`garmin_health.py:43`) and the fetchers in `garmin_sleep.py`,
`garmin_activities.py` catch every exception and return `None`/`[]`. They cannot
distinguish "Garmin has no data for this day" from "the request failed".
`garmin_snapshot.py` then writes a markdown file whose sections all read
"No data" and exits 0. On a schedule this silently archives hollow days into the
health history, indistinguishable from days the watch was not worn.

### 5. Stale test, and nothing runs the tests

`tests/test_garmin_activities.py:60` asserts `"5.2 km" in result`. Commit
`f879fda` made imperial the default, so `format_activities` emits `3.2 miles`.
The suite has been red since that commit. There is no CI.

### 6. Undocumented `units` setting

The imperial/metric setting is correctly plumbed through every script but appears
in no documentation — not README, SKILL.md, setup.sh, or references/setup.md.

## Design

### Pin the dependency and fix the API

Pin `garminconnect>=0.3.3,<0.4` to match the API the code will target. Fix both
`.garth` → `.client` call sites.

Add a contract test asserting the auth surface exists (the `Garmin` class exposes
`client`, and `login` accepts a tokenstore). This fails loudly on the next
renaming release instead of silently degrading to a rate-limit spiral.

### One auth path

Extract the browser-UA + backoff SSO flow from `garmin_login.py` into a shared
function. Delete the mobile-UA credential login inside `get_client`.

`get_client` becomes: resume from cached tokens; on failure, classify and raise a
`GarminAuthError` carrying an actionable message. Classification reads token
expiry off disk before making any network call:

| Condition | Message |
|---|---|
| No token files | Not authenticated — run `garmin_login.py` |
| Refresh token expired | Tokens expired on `<date>` — run `garmin_login.py` |
| HTTP 429 | Garmin is rate-limiting this IP — wait, do not retry login |
| Anything else | Underlying error, verbatim, plus the re-login hint |

`get_client` will **not** silently attempt a fresh SSO login. That is what causes
the 429 spiral, and it can require MFA, which cannot be satisfied
non-interactively.

### Fail loudly on fetch errors

Separate "no data" from "request failed". Genuinely-absent data continues to
return `None`; auth, rate-limit, and network errors propagate.

`garmin_snapshot.py` and `garmin_rollup.py` abort on any hard fetch error: they
print the error to stderr, **write no file**, and exit non-zero. A day that is
legitimately empty (watch not worn) still writes normally. Rationale: a missing
file is trivially recoverable by re-running; a hollow file silently corrupts the
archive and cannot be told apart from a real rest day.

### `distance_units`

The `units` setting only ever controlled activity distance, so name it for what
it does: `distance_units: miles | km`, defaulting to `miles`.

Legacy `units` keys still map across (`imperial` → `miles`, `metric` → `km`) so
existing installs keep working.

### Tests and CI

Fix the stale assertion (default output is now `3.2 miles`). Add coverage for:

- token expiry classification (each branch of the table above)
- fetch errors propagating vs absent data returning `None`
- snapshot refusing to write a file when a fetch errors
- `distance_units` mapping, including the legacy `units` fallback
- the garminconnect API contract

Add a GitHub Actions workflow running pytest, structured so other skills can be
added later. All tests are offline and mocked; CI makes no live Garmin calls.

### Documentation

Document `distance_units` in README.md, SKILL.md, and references/setup.md.
Document the re-login and rate-limit recovery procedure.

## Out of scope

- New metrics, commands, or output fields (pace, elevation, weight)
- Any refactor not serving the defects above

## Operational follow-up

The stored refresh token is dead, so a real re-login is required to restore
service. This needs an MFA code from the user and must happen **after** the
`.garth` fix lands — re-logging in beforehand would hit the broken `dump()` path
and fail to persist tokens. Live end-to-end verification follows the re-login.
