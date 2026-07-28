# Garmin Skill Correctness Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the garmin skill's broken auth path, stop periodic imports from silently archiving empty days, and add CI so neither regresses.

**Architecture:** `garmin_client.py` becomes resume-only: it loads cached tokens and never attempts an SSO login, so it can never trigger a Cloudflare 429 or block on MFA. All SSO login lives in `garmin_login.py`, the one script a human runs interactively. Fetchers stop swallowing exceptions: absent data still returns `None`, but auth/rate-limit/network errors raise `GarminFetchError`, which makes `garmin_snapshot.py` and `garmin_rollup.py` abort without writing a file.

**Tech Stack:** Python 3.12, `garminconnect` 0.3.x, `garth` 0.5.x, pytest, GitHub Actions.

## Global Constraints

- Pin `garminconnect>=0.3.3,<0.4` in `garmin/requirements.txt`. The code targets the 0.3.x API only.
- The 0.3.x API exposes the garth client as `Garmin.client`. The attribute `Garmin.garth` **does not exist** — never write `.garth`.
- `Garmin()` constructed with no email/password **cannot** perform a credential login; `login(tokenstore)` raises `GarminConnectAuthenticationError("Username and password are required")` when tokens fail to load. This plan relies on that as a safety property.
- `GarminAuthError` subclasses `GarminConfigError`, so every existing `except GarminConfigError` handler in the scripts keeps working unchanged.
- All tests are offline. No test may make a live Garmin network call.
- Default `distance_units` is `miles`.
- Run tests with the installed venv: `~/.claude/skills/garmin/.venv/bin/python -m pytest` from the `garmin/` directory.

---

## Deviation from the spec (deliberate, flagged)

The spec said to "extract the browser-UA + backoff SSO flow from `garmin_login.py` into a shared function." Once `get_client` stops doing SSO (Task 3), `garmin_login.py` is the **only** SSO consumer, so a shared module would have exactly one caller. Per YAGNI the flow stays in `garmin_login.py` and no new module is created. The spec's actual goal — one auth path, not two — is still met, by deletion rather than extraction.

---

### Task 1: Pin garminconnect and lock the API contract

The root cause was silent dependency drift: `<1.0` let pip install 0.3.3, which renamed `.garth` to `.client`. This task pins the range and adds a test that fails loudly if the auth surface ever moves again. It is deliberately first — it is the regression guard for everything that follows.

**Files:**
- Modify: `garmin/requirements.txt:1`
- Create: `garmin/tests/test_garmin_api_contract.py`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing consumed by later tasks. This is a standalone guard.

- [ ] **Step 1: Write the failing test**

Create `garmin/tests/test_garmin_api_contract.py`. Unlike every other test file, this one deliberately does **not** mock `Garmin` — mocking is what let the breakage go unnoticed, because `MagicMock` auto-creates any attribute you ask for, including `.garth`.

```python
"""Contract tests against the real garminconnect package.

These tests deliberately do NOT mock Garmin. The .garth -> .client rename in
garminconnect 0.3.x went undetected for months precisely because every other
test mocks the class, and MagicMock auto-creates any attribute accessed --
including a .garth that no longer exists. These tests assert the real auth
surface the skill depends on, so the next renaming release fails CI instead of
silently degrading into a rate-limit spiral.

No network calls: constructing Garmin() and inspecting attributes is offline.
"""

import inspect

import pytest
from garminconnect import Garmin
from garminconnect.exceptions import GarminConnectAuthenticationError


def test_garmin_exposes_client_attribute():
    """The skill persists tokens via Garmin.client (garth client)."""
    g = Garmin()
    assert hasattr(g, "client"), "garminconnect renamed the garth client attribute"


def test_garmin_has_no_garth_attribute():
    """Guard against reintroducing the 0.2.x .garth call sites."""
    g = Garmin()
    assert not hasattr(g, "garth"), "garminconnect exposes .garth again -- reconcile with garmin_client.py"


def test_garth_client_can_dump_and_load_tokens():
    """garmin_login.py depends on client.dump()/client.load()."""
    g = Garmin()
    assert hasattr(g.client, "dump")
    assert hasattr(g.client, "load")


def test_login_accepts_a_tokenstore_path():
    """get_client() resumes sessions via login(tokenstore)."""
    params = inspect.signature(Garmin.login).parameters
    assert "tokenstore" in params


def test_credential_free_login_cannot_reach_sso():
    """Safety property: Garmin() with no credentials cannot start an SSO login.

    get_client() relies on this -- it is why resume-only auth can never trip a
    429 or block on an MFA prompt.
    """
    g = Garmin()
    with pytest.raises(GarminConnectAuthenticationError):
        # Empty tokenstore dir -> tokens fail to load -> must refuse, not log in.
        g.login("/nonexistent/token/dir/for/contract/test")
```

- [ ] **Step 2: Run the test to verify the contract holds on the pinned version**

Run: `cd garmin && ~/.claude/skills/garmin/.venv/bin/python -m pytest tests/test_garmin_api_contract.py -v`
Expected: 5 passed. If `test_garmin_has_no_garth_attribute` fails, the installed version is 0.2.x and the pin in Step 3 is wrong — stop and re-check.

- [ ] **Step 3: Pin the dependency**

Replace line 1 of `garmin/requirements.txt`:

```
garminconnect>=0.3.3,<0.4
garth>=0.5.17,<0.7.0
pytest>=7.0
```

- [ ] **Step 4: Verify the pin resolves to what is installed**

Run: `~/.claude/skills/garmin/.venv/bin/python -m pip show garminconnect | grep ^Version`
Expected: `Version: 0.3.3`

- [ ] **Step 5: Commit**

```bash
git add garmin/requirements.txt garmin/tests/test_garmin_api_contract.py
git commit -m "fix(garmin): pin garminconnect to 0.3.x and lock the auth API contract"
```

---

### Task 2: Classify auth failures from token expiry

`get_client` currently swallows the token-login error (`except Exception: pass`) and reports every failure as "rate limit or auth error". This task adds token inspection so the user is told which of four distinct things went wrong, and — critically — is *not* told to re-login when the real problem is a 429 (re-logging in makes a 429 worse).

**Files:**
- Modify: `garmin/scripts/garmin_client.py` (add exceptions + `read_refresh_expiry` + `describe_auth_failure`)
- Modify: `garmin/tests/test_garmin_client.py` (add `TestAuthFailureClassification`)

**Interfaces:**
- Consumes: nothing.
- Produces, all importable from `garmin_client`:
  - `class GarminAuthError(GarminConfigError)` — raised when a session cannot be resumed.
  - `class GarminFetchError(Exception)` — raised by Task 4's fetchers on a hard API failure. Defined here so all custom exceptions live in one module; **not used** until Task 4.
  - `read_refresh_expiry(token_dir: str) -> datetime | None` — reads `refresh_token_expires_at` from `<token_dir>/oauth2_token.json`; returns `None` if the file is missing, unreadable, or lacks the field.
  - `describe_auth_failure(token_dir: str, exc: Exception) -> str` — builds the actionable error message.

- [ ] **Step 1: Write the failing tests**

Append to `garmin/tests/test_garmin_client.py`:

```python
import json
from datetime import datetime, timedelta

from garmin_client import (
    GarminAuthError,
    describe_auth_failure,
    read_refresh_expiry,
)

RELOGIN_HINT = "garmin_login.py"


def _write_oauth2(token_dir, expires_at):
    token_dir.mkdir(parents=True, exist_ok=True)
    (token_dir / "oauth2_token.json").write_text(json.dumps({"refresh_token_expires_at": expires_at}))


class TestReadRefreshExpiry:
    def test_returns_none_when_token_dir_missing(self, tmp_path):
        assert read_refresh_expiry(str(tmp_path / "nope")) is None

    def test_returns_none_when_field_absent(self, tmp_path):
        token_dir = tmp_path / "tokens"
        token_dir.mkdir()
        (token_dir / "oauth2_token.json").write_text(json.dumps({"scope": "x"}))
        assert read_refresh_expiry(str(token_dir)) is None

    def test_returns_none_on_corrupt_json(self, tmp_path):
        token_dir = tmp_path / "tokens"
        token_dir.mkdir()
        (token_dir / "oauth2_token.json").write_text("{not json")
        assert read_refresh_expiry(str(token_dir)) is None

    def test_reads_expiry_timestamp(self, tmp_path):
        token_dir = tmp_path / "tokens"
        expected = datetime(2026, 3, 25, 10, 25, 14)
        _write_oauth2(token_dir, expected.timestamp())
        assert read_refresh_expiry(str(token_dir)) == expected


class TestAuthFailureClassification:
    def test_no_tokens_says_not_authenticated(self, tmp_path):
        msg = describe_auth_failure(str(tmp_path / "tokens"), Exception("boom"))
        assert "Not authenticated" in msg
        assert RELOGIN_HINT in msg

    def test_expired_tokens_report_the_expiry_date(self, tmp_path):
        token_dir = tmp_path / "tokens"
        expired = datetime.now() - timedelta(days=30)
        _write_oauth2(token_dir, expired.timestamp())

        msg = describe_auth_failure(str(token_dir), Exception("boom"))

        assert "expired" in msg.lower()
        assert expired.date().isoformat() in msg
        assert RELOGIN_HINT in msg

    def test_rate_limit_does_not_advise_relogin(self, tmp_path):
        """A 429 must NOT tell the user to log in again -- that deepens the block."""
        token_dir = tmp_path / "tokens"
        _write_oauth2(token_dir, (datetime.now() + timedelta(days=10)).timestamp())

        msg = describe_auth_failure(str(token_dir), Exception("Error 429: Too Many Requests"))

        assert "rate-limit" in msg.lower() or "rate limit" in msg.lower()
        assert RELOGIN_HINT not in msg

    def test_unknown_error_is_surfaced_verbatim(self, tmp_path):
        token_dir = tmp_path / "tokens"
        _write_oauth2(token_dir, (datetime.now() + timedelta(days=10)).timestamp())

        msg = describe_auth_failure(str(token_dir), Exception("kaboom specifics"))

        assert "kaboom specifics" in msg
        assert RELOGIN_HINT in msg
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd garmin && ~/.claude/skills/garmin/.venv/bin/python -m pytest tests/test_garmin_client.py -v`
Expected: FAIL — `ImportError: cannot import name 'GarminAuthError' from 'garmin_client'`

- [ ] **Step 3: Implement the classification**

In `garmin/scripts/garmin_client.py`, add `from datetime import datetime` to the imports, then add below `GarminConfigError`:

```python
class GarminAuthError(GarminConfigError):
    """Raised when a Garmin session cannot be resumed from cached tokens.

    Subclasses GarminConfigError so existing `except GarminConfigError`
    handlers in the CLI scripts catch it unchanged.
    """

    pass


class GarminFetchError(Exception):
    """Raised when a Garmin API call fails (auth, rate limit, network).

    Distinct from "Garmin has no data for this day", which is a None return.
    Callers that write files must abort on this rather than archive an empty day.
    """

    pass


RELOGIN_COMMAND = "  ~/.claude/skills/garmin/.venv/bin/python ~/.claude/skills/garmin/scripts/garmin_login.py"


def read_refresh_expiry(token_dir: str = DEFAULT_TOKEN_DIR) -> datetime | None:
    """Read the refresh token's expiry from the cached oauth2 token.

    Returns None if the token file is missing, unreadable, or has no expiry --
    all of which mean "we cannot say when this expires", not "it is valid".
    """
    token_file = Path(token_dir) / "oauth2_token.json"
    try:
        with open(token_file) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None

    expires_at = data.get("refresh_token_expires_at")
    if not expires_at:
        return None
    try:
        return datetime.fromtimestamp(expires_at)
    except (OSError, OverflowError, TypeError, ValueError):
        return None


def describe_auth_failure(token_dir: str, exc: Exception) -> str:
    """Build an actionable message explaining why a session could not be resumed.

    Deliberately does NOT suggest re-login on a 429: a fresh SSO login while
    rate-limited extends the block rather than clearing it.
    """
    if "429" in str(exc) or "too many requests" in str(exc).lower():
        return (
            "Garmin is rate-limiting this IP (HTTP 429).\n"
            "Wait before retrying. Do not re-run login -- that extends the block."
        )

    expiry = read_refresh_expiry(token_dir)

    if expiry is None:
        return f"Not authenticated: no usable Garmin tokens found.\nLog in to authenticate:\n{RELOGIN_COMMAND}"

    if expiry < datetime.now():
        return (
            f"Garmin tokens expired on {expiry.date().isoformat()}.\nLog in again to refresh them:\n{RELOGIN_COMMAND}"
        )

    return f"Could not resume Garmin session: {exc}\nLog in again to refresh your tokens:\n{RELOGIN_COMMAND}"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd garmin && ~/.claude/skills/garmin/.venv/bin/python -m pytest tests/test_garmin_client.py -v -k "RefreshExpiry or Classification"`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add garmin/scripts/garmin_client.py garmin/tests/test_garmin_client.py
git commit -m "feat(garmin): classify auth failures from token expiry"
```

---

### Task 3: Make get_client resume-only and fix the .garth call sites

This removes the second, worse login path. `get_client` will resume from tokens or raise — it will never attempt SSO. That closes the 429 spiral at its source: the reason the account got rate-limited is that `garmin.garth.dump()` crashed after every successful login, so tokens were never saved and every run logged in afresh.

**Files:**
- Modify: `garmin/scripts/garmin_client.py:72-125` (rewrite `get_client`) and `:128-140` (the `__main__` block)
- Modify: `garmin/scripts/garmin_login.py:118` (`.garth.load` → `.client.load`)
- Modify: `garmin/tests/test_garmin_client.py:44-105` (replace `TestGetClient` wholesale)

**Interfaces:**
- Consumes: `GarminAuthError`, `describe_auth_failure` (Task 2).
- Produces: `get_client(config: dict, token_dir: str = DEFAULT_TOKEN_DIR) -> Garmin` — returns an authenticated client resumed from cached tokens, or raises `GarminAuthError`. The `config` parameter is retained for signature compatibility with all four calling scripts but is no longer used for login.

- [ ] **Step 1: Replace the TestGetClient class with tests for resume-only behaviour**

The three existing tests in `TestGetClient` (`garmin/tests/test_garmin_client.py:44-105`) all assert the *broken* behaviour — `test_falls_back_to_credentials_on_token_failure` even asserts `mock_cred_garmin.garth.dump` was called, enshrining the attribute that no longer exists. Delete the whole class and replace it:

```python
class TestGetClient:
    """get_client resumes from cached tokens and never performs an SSO login."""

    @patch("garmin_client.Garmin")
    def test_resumes_from_cached_tokens(self, MockGarmin, tmp_path):
        token_dir = tmp_path / "tokens"
        _write_oauth2(token_dir, (datetime.now() + timedelta(days=10)).timestamp())

        mock_garmin = MagicMock()
        MockGarmin.return_value = mock_garmin

        config = {"email": "test@example.com", "password": "secret123"}
        client = get_client(config, token_dir=str(token_dir))

        assert client is mock_garmin
        mock_garmin.login.assert_called_once_with(str(token_dir))
        # Constructed WITHOUT credentials: this is what makes SSO unreachable.
        MockGarmin.assert_called_once_with()

    @patch("garmin_client.Garmin")
    def test_never_attempts_credential_login(self, MockGarmin, tmp_path):
        """The whole point: a failed resume must not fall back to SSO."""
        token_dir = tmp_path / "tokens"
        _write_oauth2(token_dir, (datetime.now() - timedelta(days=30)).timestamp())

        mock_garmin = MagicMock()
        mock_garmin.login.side_effect = Exception("Username and password are required")
        MockGarmin.return_value = mock_garmin

        config = {"email": "test@example.com", "password": "secret123"}
        with pytest.raises(GarminAuthError, match="expired"):
            get_client(config, token_dir=str(token_dir))

        # Exactly one Garmin() -- no second, credential-bearing instance.
        MockGarmin.assert_called_once_with()

    @patch("garmin_client.Garmin")
    def test_raises_not_authenticated_when_no_tokens(self, MockGarmin, tmp_path):
        token_dir = tmp_path / "tokens"

        mock_garmin = MagicMock()
        mock_garmin.login.side_effect = Exception("Username and password are required")
        MockGarmin.return_value = mock_garmin

        with pytest.raises(GarminAuthError, match="Not authenticated"):
            get_client({"email": "a@b.c", "password": "x"}, token_dir=str(token_dir))

    @patch("garmin_client.Garmin")
    def test_rate_limit_does_not_advise_relogin(self, MockGarmin, tmp_path):
        token_dir = tmp_path / "tokens"
        _write_oauth2(token_dir, (datetime.now() + timedelta(days=10)).timestamp())

        mock_garmin = MagicMock()
        mock_garmin.login.side_effect = Exception("Error 429: Too Many Requests")
        MockGarmin.return_value = mock_garmin

        with pytest.raises(GarminAuthError) as excinfo:
            get_client({"email": "a@b.c", "password": "x"}, token_dir=str(token_dir))

        assert "garmin_login.py" not in str(excinfo.value)

    @patch("garmin_client.Garmin")
    def test_persists_tokens_after_resume(self, MockGarmin, tmp_path):
        """A resume may silently refresh the access token; persist it."""
        token_dir = tmp_path / "tokens"
        _write_oauth2(token_dir, (datetime.now() + timedelta(days=10)).timestamp())

        mock_garmin = MagicMock()
        MockGarmin.return_value = mock_garmin

        get_client({"email": "a@b.c", "password": "x"}, token_dir=str(token_dir))

        mock_garmin.client.dump.assert_called_once_with(str(token_dir))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd garmin && ~/.claude/skills/garmin/.venv/bin/python -m pytest tests/test_garmin_client.py::TestGetClient -v`
Expected: FAIL — the current `get_client` constructs `Garmin(email=..., password=...)` on fallback, so `MockGarmin.assert_called_once_with()` fails.

- [ ] **Step 3: Rewrite get_client**

Replace `garmin/scripts/garmin_client.py:72-125` entirely:

```python
def get_client(
    config: dict,
    token_dir: str = DEFAULT_TOKEN_DIR,
) -> Garmin:
    """Create a Garmin client by resuming a cached session.

    Resume-only by design. This never performs an SSO login, because doing so
    non-interactively is what drove the account into a Cloudflare 429: it can
    also demand an MFA code that no cron job can supply. Interactive login is
    garmin_login.py's job.

    Args:
        config: Loaded config. Retained for signature compatibility with the
            calling scripts; credentials are not used to log in here.
        token_dir: Directory holding cached garth tokens.

    Returns:
        Authenticated Garmin client.

    Raises:
        GarminAuthError: If the session cannot be resumed. The message names the
            actual cause (no tokens / expired on <date> / rate limited).
    """
    token_path = Path(token_dir)

    try:
        garmin = Garmin()
        garmin.login(str(token_path))
    except Exception as exc:
        raise GarminAuthError(describe_auth_failure(str(token_path), exc)) from exc

    # login() may have refreshed the access token in memory. Persist it so the
    # next run resumes cleanly instead of drifting towards a full re-login.
    try:
        garmin.client.dump(str(token_path))
    except Exception as exc:
        print(f"Warning: could not persist refreshed tokens: {exc}", file=sys.stderr)

    return garmin
```

- [ ] **Step 4: Update the `__main__` auth-test block**

Replace `garmin/scripts/garmin_client.py:128-140` so the message matches the new behaviour:

```python
if __name__ == "__main__":
    """Quick auth test - run to verify cached tokens work."""
    try:
        config = load_config()
        client = get_client(config)
        name = client.get_full_name()
        print(f"Authenticated as: {name}")
    except GarminConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
```

(`GarminAuthError` subclasses `GarminConfigError`, so this single handler covers both.)

- [ ] **Step 5: Fix the .garth call site in garmin_login.py**

`garmin/scripts/garmin_login.py:118` is the last `.garth` reference. Replace:

```python
# Verify
from garminconnect import Garmin

garmin = Garmin()
garmin.client.load(str(token_path))
name = garmin.get_full_name()
```

- [ ] **Step 6: Verify no .garth references remain**

Run: `grep -rn "\.garth" garmin/scripts/ garmin/tests/`
Expected: no output (exit 1). Any hit is a bug — 0.3.x has no such attribute.

- [ ] **Step 7: Run the full suite**

Run: `cd garmin && ~/.claude/skills/garmin/.venv/bin/python -m pytest tests/ -v`
Expected: all pass except the known-stale `test_formats_multiple_activities` (fixed in Task 6).

- [ ] **Step 8: Commit**

```bash
git add garmin/scripts/garmin_client.py garmin/scripts/garmin_login.py garmin/tests/test_garmin_client.py
git commit -m "fix(garmin): make get_client resume-only and repair .garth call sites"
```

---

### Task 4: Propagate fetch errors instead of swallowing them

Every fetcher catches all exceptions and returns `None`/`[]`, so a rate-limited or offline run looks exactly like a day the watch was not worn. This task teaches them the difference. Absent data still returns `None`; a hard failure raises `GarminFetchError`.

**Files:**
- Create: `garmin/tests/conftest.py` (shared `fake_http_error` fixture)
- Modify: `garmin/scripts/garmin_health.py:43-48` (`_safe_call`)
- Modify: `garmin/scripts/garmin_sleep.py:68-73` (`fetch_sleep`)
- Modify: `garmin/scripts/garmin_activities.py:152-174` (`fetch_activities`, `fetch_training`)
- Modify: `garmin/tests/test_garmin_health.py`, `garmin/tests/test_garmin_sleep.py`, `garmin/tests/test_garmin_activities.py`

**Interfaces:**
- Consumes: `GarminFetchError` (Task 2).
- Produces:
  - `garmin_health._safe_call(fn, *args, **kwargs)` — returns the call's result, or `None` if Garmin reports no data (HTTP 404); raises `GarminFetchError` on any other failure.
  - `garmin_sleep.fetch_sleep(client, cdate) -> dict | None` — same contract.
  - `garmin_activities.fetch_activities(client, days=7) -> list[dict]` — raises `GarminFetchError` on failure; `[]` genuinely means no activities.
  - `garmin_activities.fetch_training(client, cdate) -> tuple[dict | None, dict | None]` — raises `GarminFetchError` on failure.

A 404 from Garmin means "nothing recorded for this date" and is the one error that is *not* a failure. `garth.exc.GarthHTTPError` wraps the underlying `requests` response, so the status code is reachable at `exc.error.response.status_code`.

- [ ] **Step 1: Create the shared test double**

All three test files need the same stand-in for `garth.exc.GarthHTTPError`. Define it **once** in a new `garmin/tests/conftest.py` and expose it as a fixture, so no test file has to import it:

```python
"""Shared test fixtures for the garmin skill."""

from unittest.mock import MagicMock

import pytest


class FakeHTTPError(Exception):
    """Stands in for garth.exc.GarthHTTPError, which wraps a requests response.

    The skill reads the status code at exc.error.response.status_code to tell
    "no data for this date" (404) apart from a real failure (429, 5xx, ...).
    """

    def __init__(self, status_code):
        super().__init__(f"HTTP {status_code}")
        self.error = MagicMock()
        self.error.response.status_code = status_code


@pytest.fixture
def fake_http_error():
    """The FakeHTTPError class itself, so tests can raise it with a status code."""
    return FakeHTTPError
```

- [ ] **Step 2: Write the failing tests**

Append to `garmin/tests/test_garmin_health.py`:

```python
from unittest.mock import MagicMock

import pytest

from garmin_client import GarminFetchError
from garmin_health import _safe_call, fetch_day_data


class TestSafeCall:
    def test_returns_value_on_success(self):
        assert _safe_call(lambda: {"restingHeartRate": 52}) == {"restingHeartRate": 52}

    def test_returns_none_when_garmin_has_no_data(self, fake_http_error):
        """404 means 'nothing recorded that day' -- absence, not failure."""

        def not_found():
            raise fake_http_error(404)

        assert _safe_call(not_found) is None

    def test_raises_on_rate_limit(self, fake_http_error):
        def rate_limited():
            raise fake_http_error(429)

        with pytest.raises(GarminFetchError):
            _safe_call(rate_limited)

    def test_raises_on_network_error(self):
        def offline():
            raise ConnectionError("network unreachable")

        with pytest.raises(GarminFetchError, match="network unreachable"):
            _safe_call(offline)


class TestFetchDayData:
    def test_propagates_failure_rather_than_returning_empty(self, fake_http_error):
        """The silent-data-loss guard: a failed fetch must not look like an empty day."""
        client = MagicMock()
        client.get_stats.side_effect = fake_http_error(429)

        with pytest.raises(GarminFetchError):
            fetch_day_data(client, "2026-07-14")
```

Append to `garmin/tests/test_garmin_sleep.py`:

```python
from unittest.mock import MagicMock

import pytest

from garmin_client import GarminFetchError
from garmin_sleep import fetch_sleep


class TestFetchSleep:
    def test_returns_none_when_no_sleep_recorded(self, fake_http_error):
        client = MagicMock()
        client.get_sleep_data.side_effect = fake_http_error(404)
        assert fetch_sleep(client, "2026-07-14") is None

    def test_raises_on_hard_failure(self, fake_http_error):
        client = MagicMock()
        client.get_sleep_data.side_effect = fake_http_error(429)
        with pytest.raises(GarminFetchError):
            fetch_sleep(client, "2026-07-14")
```

Append to `garmin/tests/test_garmin_activities.py`:

```python
from unittest.mock import MagicMock

from garmin_client import GarminFetchError
from garmin_activities import fetch_activities, fetch_training


class TestFetchActivities:
    def test_returns_empty_list_when_none_recorded(self):
        client = MagicMock()
        client.get_activities_by_date.return_value = []
        assert fetch_activities(client, days=7) == []

    def test_raises_on_hard_failure(self, fake_http_error):
        client = MagicMock()
        client.get_activities_by_date.side_effect = fake_http_error(429)
        with pytest.raises(GarminFetchError):
            fetch_activities(client, days=7)


class TestFetchTraining:
    def test_raises_on_hard_failure(self, fake_http_error):
        client = MagicMock()
        client.get_training_status.side_effect = fake_http_error(500)
        with pytest.raises(GarminFetchError):
            fetch_training(client, "2026-07-14")
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd garmin && ~/.claude/skills/garmin/.venv/bin/python -m pytest tests/test_garmin_health.py tests/test_garmin_sleep.py tests/test_garmin_activities.py -v -k "SafeCall or FetchDayData or FetchSleep or FetchActivities or FetchTraining"`
Expected: FAIL — the fetchers currently swallow everything and return `None`/`[]`, so every `pytest.raises` block fails.

- [ ] **Step 4: Implement the shared error policy in garmin_health.py**

Replace `garmin/scripts/garmin_health.py:43-48`. Also add `from garmin_client import GarminFetchError` to the existing `garmin_client` import on line 18.

```python
def _is_not_found(exc: Exception) -> bool:
    """True if Garmin said 'no data for this date' (HTTP 404).

    A 404 is the one error that means absence rather than failure. Everything
    else -- 401, 429, 5xx, connection errors -- is a real failure and must not
    be quietly rendered as an empty day.
    """
    response = getattr(getattr(exc, "error", None), "response", None)
    return getattr(response, "status_code", None) == 404


def _safe_call(fn, *args, **kwargs):
    """Call a Garmin API method.

    Returns:
        The call's result, or None if Garmin has no data for the date.

    Raises:
        GarminFetchError: On any real failure (auth, rate limit, network, 5xx).
    """
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        if _is_not_found(exc):
            return None
        raise GarminFetchError(f"Garmin API call failed: {exc}") from exc
```

`fetch_day_data` (lines 21-40) needs no change: it calls `_safe_call`, which now raises.

- [ ] **Step 5: Apply the same policy in garmin_sleep.py**

Replace `garmin/scripts/garmin_sleep.py:68-73`, and add the import below line 17:

```python
from garmin_health import _is_not_found
from garmin_client import GarminFetchError


def fetch_sleep(client, cdate: str) -> dict | None:
    """Fetch sleep data from Garmin API.

    Returns None if no sleep was recorded; raises GarminFetchError on failure.
    """
    try:
        return client.get_sleep_data(cdate)
    except Exception as exc:
        if _is_not_found(exc):
            return None
        raise GarminFetchError(f"Could not fetch sleep for {cdate}: {exc}") from exc
```

- [ ] **Step 6: Apply the same policy in garmin_activities.py**

Replace `garmin/scripts/garmin_activities.py:152-174`, and extend the import on line 17 to include `GarminFetchError`, adding `from garmin_health import _is_not_found`:

```python
def fetch_activities(client, days: int = 7) -> list[dict]:
    """Fetch recent activities.

    An empty list means no activities were recorded. Failures raise.
    """
    end = date.today().isoformat()
    start = (date.today() - timedelta(days=days)).isoformat()
    try:
        return client.get_activities_by_date(start, end) or []
    except Exception as exc:
        if _is_not_found(exc):
            return []
        raise GarminFetchError(f"Could not fetch activities: {exc}") from exc


def fetch_training(client, cdate: str) -> tuple[dict | None, dict | None]:
    """Fetch training status and readiness.

    None for either value means Garmin has no such data; failures raise.
    """

    def _call(fn):
        try:
            return fn(cdate)
        except Exception as exc:
            if _is_not_found(exc):
                return None
            raise GarminFetchError(f"Could not fetch training data: {exc}") from exc

    return _call(client.get_training_status), _call(client.get_training_readiness)
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd garmin && ~/.claude/skills/garmin/.venv/bin/python -m pytest tests/ -v`
Expected: all pass except the known-stale `test_formats_multiple_activities` (Task 6).

- [ ] **Step 8: Commit**

```bash
git add garmin/scripts/garmin_health.py garmin/scripts/garmin_sleep.py garmin/scripts/garmin_activities.py garmin/tests/
git commit -m "fix(garmin): raise on API failures instead of returning empty data"
```

---

### Task 5: Abort snapshot and rollup instead of writing hollow files

With Task 4 in place the fetchers raise, but `main()` in both writers would now crash with a traceback. This task turns that into a clean abort: print the error, write nothing, exit 1. A day the watch was not worn still writes a normal file full of "No data" — that is real information. A day we *failed to fetch* writes nothing at all.

**Files:**
- Modify: `garmin/scripts/garmin_snapshot.py:113-166` (`main`)
- Modify: `garmin/scripts/garmin_rollup.py:216-274` (`main`)
- Modify: `garmin/tests/test_garmin_snapshot.py`, `garmin/tests/test_garmin_rollup.py`

**Interfaces:**
- Consumes: `GarminFetchError` (Task 2), the raising fetchers (Task 4), `write_snapshot`/`write_rollup` (unchanged).
- Produces: no new functions. Behavioural contract: on `GarminFetchError`, both scripts exit non-zero having created no file.

- [ ] **Step 1: Write the failing tests**

Append to `garmin/tests/test_garmin_snapshot.py`:

```python
from unittest.mock import MagicMock, patch

import pytest

from garmin_client import GarminFetchError
import garmin_snapshot


class TestSnapshotAbortsOnFetchError:
    @patch("garmin_snapshot.fetch_day_data")
    @patch("garmin_snapshot.get_client")
    @patch("garmin_snapshot.load_config")
    def test_writes_no_file_when_fetch_fails(self, mock_config, mock_client, mock_fetch, tmp_path, monkeypatch, capsys):
        """The core guard: a failed fetch must never archive a hollow day."""
        mock_config.return_value = {"email": "a@b.c", "password": "x"}
        mock_client.return_value = MagicMock()
        mock_fetch.side_effect = GarminFetchError("Garmin is rate-limiting this IP")

        monkeypatch.setattr(
            "sys.argv",
            ["garmin_snapshot.py", "2026-07-14", "--output-dir", str(tmp_path)],
        )

        with pytest.raises(SystemExit) as excinfo:
            garmin_snapshot.main()

        assert excinfo.value.code != 0
        assert list(tmp_path.iterdir()) == [], "aborted run must leave no file behind"
        assert "rate-limiting" in capsys.readouterr().err
```

Append to `garmin/tests/test_garmin_rollup.py`:

```python
from unittest.mock import MagicMock, patch

import pytest

from garmin_client import GarminFetchError
import garmin_rollup


class TestRollupAbortsOnFetchError:
    @patch("garmin_rollup.fetch_day_data")
    @patch("garmin_rollup.get_client")
    @patch("garmin_rollup.load_config")
    def test_writes_no_file_when_a_day_fails(self, mock_config, mock_client, mock_fetch, tmp_path, monkeypatch, capsys):
        mock_config.return_value = {"email": "a@b.c", "password": "x"}
        mock_client.return_value = MagicMock()
        mock_fetch.side_effect = GarminFetchError("Garmin API call failed: 429")

        monkeypatch.setattr(
            "sys.argv",
            ["garmin_rollup.py", "2026-W28", "--output-dir", str(tmp_path)],
        )

        with pytest.raises(SystemExit) as excinfo:
            garmin_rollup.main()

        assert excinfo.value.code != 0
        assert list(tmp_path.iterdir()) == []
        assert "429" in capsys.readouterr().err
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd garmin && ~/.claude/skills/garmin/.venv/bin/python -m pytest tests/test_garmin_snapshot.py tests/test_garmin_rollup.py -v -k "Abort"`
Expected: FAIL — `GarminFetchError` escapes `main()` uncaught, so pytest sees `GarminFetchError`, not `SystemExit`.

- [ ] **Step 3: Guard snapshot's main()**

In `garmin/scripts/garmin_snapshot.py`, extend the import on line 19 to include `GarminFetchError`, then wrap the fetch block (currently lines 139-148):

```python
# Fetch all data. Any hard failure aborts before we write anything: a
# missing file is trivially fixed by re-running, but a file full of
# "No data" is indistinguishable from a genuine rest day forever after.
try:
    health_data = fetch_day_data(client, cdate)
    sleep_data = fetch_sleep(client, cdate)
    activities_data = fetch_activities(client, days=1)
    training_status, training_readiness = fetch_training(client, cdate)
except GarminFetchError as e:
    print(f"Error: {e}", file=sys.stderr)
    print(f"No snapshot written for {cdate}.", file=sys.stderr)
    sys.exit(1)

# Filter activities to just this date
activities = [a for a in activities_data if a.get("startTimeLocal", "").startswith(cdate)]
```

- [ ] **Step 4: Guard rollup's main()**

In `garmin/scripts/garmin_rollup.py`, extend the import on line 20 to include `GarminFetchError`, then replace the fetch block (currently lines 243-256):

```python
    # Any hard failure aborts the whole week rather than writing a rollup with
    # silently missing days.
    try:
        day_summaries = []
        for d in dates:
            data = fetch_day_data(client, d)
            day_summaries.append(extract_day_summary(d, data))

        activities = fetch_activities_for_range(client, dates[0], dates[-1])
        training_status, training_readiness = fetch_training(client, dates[-1])
    except GarminFetchError as e:
        print(f"Error: {e}", file=sys.stderr)
        print(f"No rollup written for {year}-W{week:02d}.", file=sys.stderr)
        sys.exit(1)
```

The old code called `client.get_activities_by_date` inline inside a bare `try/except: activities = []` — the same swallow-everything bug. Add a helper alongside the other fetchers in `garmin/scripts/garmin_activities.py` (below `fetch_activities`) and import it in `garmin_rollup.py`'s existing `from garmin_activities import (...)` block:

```python
def fetch_activities_for_range(client, start: str, end: str) -> list[dict]:
    """Fetch activities between two dates (inclusive).

    An empty list means none were recorded. Failures raise.
    """
    try:
        return client.get_activities_by_date(start, end) or []
    except Exception as exc:
        if _is_not_found(exc):
            return []
        raise GarminFetchError(f"Could not fetch activities for {start}..{end}: {exc}") from exc
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd garmin && ~/.claude/skills/garmin/.venv/bin/python -m pytest tests/ -v`
Expected: all pass except the known-stale `test_formats_multiple_activities` (Task 6).

- [ ] **Step 6: Commit**

```bash
git add garmin/scripts/garmin_snapshot.py garmin/scripts/garmin_rollup.py garmin/scripts/garmin_activities.py garmin/tests/
git commit -m "fix(garmin): abort snapshot and rollup instead of archiving empty days"
```

---

### Task 6: Rename units to distance_units and fix the stale test

The `units` setting only ever controlled activity distance, so name it for what it does. Default is `miles`, preserving current output. Legacy `units: imperial|metric` keys keep working so existing installs do not break.

**Files:**
- Modify: `garmin/scripts/garmin_client.py:66-69` (`load_config` defaulting)
- Modify: `garmin/scripts/garmin_activities.py:32-63, 192, 205` (`_format_distance`, `format_activities`, `main`)
- Modify: `garmin/scripts/garmin_rollup.py:77-137, 238, 266`
- Modify: `garmin/scripts/garmin_snapshot.py:30-80, 135, 158`
- Modify: `garmin/tests/test_garmin_activities.py:60` (the stale assertion)
- Modify: `garmin/tests/test_garmin_client.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `load_config()` sets `config["distance_units"]` to `"miles"` or `"km"`, mapping any legacy `units` key (`imperial` → `miles`, `metric` → `km`). An explicit `distance_units` wins over a legacy `units`.
  - `_format_distance(metres, distance_units="miles")`, `format_activities(activities, distance_units="miles")`, `generate_daily_markdown(..., distance_units="miles")`, `generate_weekly_markdown(..., distance_units="miles")`, `_format_activity_summary(act, distance_units="miles")`.

- [ ] **Step 1: Write the failing tests**

Fix the stale assertion at `garmin/tests/test_garmin_activities.py:60`. It has asserted `"5.2 km"` since commit `f879fda` made imperial the default; the formatter emits `3.2 miles`. Replace the body of `test_formats_multiple_activities`:

```python
def test_formats_multiple_activities(self):
    result = format_activities(MOCK_ACTIVITIES)
    assert "HYROX Training" in result
    assert "Morning Run" in result
    assert "58 min" in result
    assert "152 bpm" in result
    assert "3.2 miles" in result  # 5200 m, default distance_units=miles


def test_formats_distance_in_km_when_requested(self):
    result = format_activities(MOCK_ACTIVITIES, distance_units="km")
    assert "5.2 km" in result
    assert "miles" not in result
```

Append to `garmin/tests/test_garmin_client.py`:

```python
class TestDistanceUnits:
    def test_defaults_to_miles(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"email": "a@b.c", "password": "x"}))
        config = load_config(config_path=str(config_file))
        assert config["distance_units"] == "miles"

    def test_explicit_km_is_respected(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"email": "a@b.c", "password": "x", "distance_units": "km"}))
        config = load_config(config_path=str(config_file))
        assert config["distance_units"] == "km"

    def test_legacy_imperial_maps_to_miles(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"email": "a@b.c", "password": "x", "units": "imperial"}))
        config = load_config(config_path=str(config_file))
        assert config["distance_units"] == "miles"

    def test_legacy_metric_maps_to_km(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"email": "a@b.c", "password": "x", "units": "metric"}))
        config = load_config(config_path=str(config_file))
        assert config["distance_units"] == "km"

    def test_explicit_setting_beats_legacy_key(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps(
                {
                    "email": "a@b.c",
                    "password": "x",
                    "units": "imperial",
                    "distance_units": "km",
                }
            )
        )
        config = load_config(config_path=str(config_file))
        assert config["distance_units"] == "km"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd garmin && ~/.claude/skills/garmin/.venv/bin/python -m pytest tests/test_garmin_client.py::TestDistanceUnits tests/test_garmin_activities.py::TestFormatActivities -v`
Expected: FAIL — `KeyError: 'distance_units'`, and `format_activities()` rejects the `distance_units` keyword.

- [ ] **Step 3: Map the setting in load_config**

Replace `garmin/scripts/garmin_client.py:66-69` (the `config.setdefault("units", "imperial")` line and the `return`):

```python
    # distance_units is the modern key. Map the legacy units key across so
    # existing installs keep working; an explicit distance_units wins.
    if "distance_units" not in config:
        legacy = config.get("units")
        config["distance_units"] = "km" if legacy == "metric" else "miles"

    return config
```

- [ ] **Step 4: Rename the parameter through the formatters**

In `garmin/scripts/garmin_activities.py`, replace `_format_distance` (lines 32-43):

```python
def _format_distance(metres: float | None, distance_units: str = "miles") -> str | None:
    """Convert metres to a distance string.

    Args:
        metres: Distance in metres.
        distance_units: 'miles' or 'km'.
    """
    if metres is None or metres <= 0:
        return None
    if distance_units == "km":
        return f"{metres / 1000:.1f} km"
    return f"{metres / 1609.344:.1f} miles"
```

Then in the same file: change `format_activities`'s signature to `def format_activities(activities: list[dict], distance_units: str = "miles") -> str:`, update its docstring `units:` line to `distance_units: 'miles' or 'km'.`, and change line 63 to `distance = _format_distance(act.get("distance"), distance_units)`. In `main()`, replace line 192 with `distance_units = config["distance_units"]` and line 205 with `print(format_activities(activities, distance_units))`.

In `garmin/scripts/garmin_rollup.py`: rename the `units` parameter to `distance_units` (default `"miles"`) in `_format_activity_summary` (line 77) and `generate_weekly_markdown` (line 110), update the two call sites (lines 93 and 137), replace line 238 with `distance_units = config["distance_units"]`, and line 266 with `distance_units=distance_units,`.

In `garmin/scripts/garmin_snapshot.py`: rename the `units` parameter to `distance_units` (default `"miles"`) in `generate_daily_markdown` (line 37), update the call on line 71 to `format_activities(activities, distance_units)`, replace line 135 with `distance_units = config["distance_units"]`, and line 158 with `distance_units=distance_units,`.

- [ ] **Step 5: Verify no stale `units` references remain**

Run: `grep -rn "\bunits\b" garmin/scripts/ | grep -v distance_units`
Expected: exactly one hit — the legacy-key lookup `config.get("units")` in `garmin_client.py`. Anything else is a missed rename.

- [ ] **Step 6: Run the full suite — it should now be fully green**

Run: `cd garmin && ~/.claude/skills/garmin/.venv/bin/python -m pytest tests/ -v`
Expected: all pass, zero failures. This is the first fully-green run since commit `f879fda`.

- [ ] **Step 7: Commit**

```bash
git add garmin/scripts/ garmin/tests/
git commit -m "refactor(garmin): rename units to distance_units, defaulting to miles"
```

---

### Task 7: Add CI

Tests existed but nothing ran them, which is why a red suite went unnoticed from February to July. The workflow is written so other skills can be added to the matrix later.

**Files:**
- Create: `.github/workflows/tests.yml`

**Interfaces:**
- Consumes: `garmin/requirements.txt` (Task 1).
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/tests.yml`:

```yaml
name: tests

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        skill: [garmin]
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: ${{ matrix.skill }}/requirements.txt

      - name: Install dependencies
        run: pip install -r ${{ matrix.skill }}/requirements.txt

      # Tests are offline and mocked -- no live Garmin calls, no credentials.
      - name: Run tests
        working-directory: ${{ matrix.skill }}
        run: python -m pytest tests/ -v
```

- [ ] **Step 2: Verify the workflow's test command works from a clean checkout**

Reproduce what CI does, in a throwaway venv, to prove the run does not depend on the already-installed skill venv:

```bash
cd /tmp && rm -rf garmin-ci-check && python3 -m venv garmin-ci-check
/tmp/garmin-ci-check/bin/pip install -q -r /home/devops/.paseo/worktrees/123szssq/nifty-pony/garmin/requirements.txt
cd /home/devops/.paseo/worktrees/123szssq/nifty-pony/garmin && /tmp/garmin-ci-check/bin/python -m pytest tests/ -v
```

Expected: all tests pass. Then clean up: `rm -rf /tmp/garmin-ci-check`

- [ ] **Step 3: Validate the YAML parses**

Run: `~/.claude/skills/garmin/.venv/bin/python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/tests.yml')); print('workflow YAML OK')"`
Expected: `workflow YAML OK` (if PyYAML is absent, `pip install pyyaml` into a scratch venv rather than the skill venv).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/tests.yml
git commit -m "ci: run skill test suites on push and pull request"
```

---

### Task 8: Update the documentation

Three docs currently mislead. `references/setup.md` claims tokens last "approximately one year" (the observed refresh token lasted ~30 days) and tells users to recover by deleting tokens and re-running `garmin_client.py` — which after Task 3 cannot log in at all. `distance_units` is documented nowhere.

**Files:**
- Modify: `garmin/references/setup.md` (Token Storage + Troubleshooting)
- Modify: `garmin/SKILL.md` (Error Handling section)
- Modify: `garmin/README.md` (add Configuration section)
- Modify: `CLAUDE.md` (Credentials table)

**Interfaces:**
- Consumes: the behaviour established in Tasks 3-6.
- Produces: nothing.

- [ ] **Step 1: Fix the token lifetime and recovery advice**

In `garmin/references/setup.md`, replace the whole "Token Storage" section:

```markdown
## Token Storage

After a successful login, OAuth tokens are cached in `~/.garmin/tokens/`. The
refresh token is the one that matters: once it expires, cached tokens cannot be
renewed and you must log in again. Observed lifetime is roughly a month, not a
year.

The scripts resume from these tokens and never log in on your behalf — an
automated SSO login can trip Garmin's rate limiting and may demand an MFA code
that a cron job cannot answer. When tokens expire, the scripts tell you the
expiry date and stop. Re-authenticate with:

```bash
.venv/bin/python scripts/garmin_login.py
```
```

Then replace the "Troubleshooting" section:

```markdown
## Troubleshooting

### "Config file not found"
Run `scripts/setup.sh` or create `~/.garmin/config.json` manually.

### "Not authenticated" or "Garmin tokens expired on <date>"
Cached tokens are missing or too old to refresh. Log in again:

```bash
.venv/bin/python scripts/garmin_login.py
```

### "Garmin is rate-limiting this IP (HTTP 429)"
Garmin has temporarily blocked login attempts from your IP. **Wait** — do not
re-run login, which extends the block. Try again later.

### MFA prompt
Garmin may require MFA at login. Enter the code when prompted, or pass it as an
argument: `garmin_login.py 123456`. Cached tokens then work without MFA until
the refresh token expires.
```

- [ ] **Step 2: Document configuration in the README**

In `garmin/README.md`, insert a Configuration section between "Quick Start" and "Data Export":

```markdown
## Configuration

`~/.garmin/config.json` holds your credentials and preferences:

```json
{
  "email": "you@example.com",
  "password": "your-password",
  "distance_units": "miles"
}
```

| Key | Values | Default | Effect |
|-----|--------|---------|--------|
| `distance_units` | `miles`, `km` | `miles` | Units for activity distances in queries, snapshots, and rollups |

The older `units` key (`imperial` / `metric`) still works and maps to
`distance_units` automatically.
```

- [ ] **Step 3: Correct the SKILL.md error-handling claims**

`garmin/SKILL.md:145-151` currently promises "Auth expired: Auto-refreshes using stored credentials" and "No data for date: Sections show 'No data' rather than failing". Both are now wrong. Replace the "Error Handling" section body:

```markdown
- **Tokens expired:** Scripts report the expiry date and stop. Run `garmin_login.py` to re-authenticate.
- **Rate limited (429):** Scripts report it and stop. Wait — re-running login extends the block.
- **No data for a date:** Sections show "No data". The snapshot still writes.
- **Fetch failure:** Snapshots and rollups abort and write no file, rather than archiving a day of empty sections. Re-run once the cause clears.
- **MFA required:** `garmin_login.py` prompts, or accepts the code as an argument.
```

Also add a Configuration note under Prerequisites:

```markdown
Set `"distance_units": "miles"` or `"km"` in `~/.garmin/config.json` to control activity distance units (default: `miles`).
```

- [ ] **Step 4: Update the root CLAUDE.md credentials table**

In `CLAUDE.md`, the Credentials table row for Garmin currently reads `` `~/.garmin/` ``. Replace it:

```markdown
| Garmin | `~/.garmin/config.json` (email, password, `distance_units`); tokens in `~/.garmin/tokens/` |
```

- [ ] **Step 5: Verify the docs match reality**

Run: `grep -rn "one year\|Auto-refreshes\|units.*imperial" garmin/README.md garmin/SKILL.md garmin/references/setup.md`
Expected: no output. Any hit is stale documentation that survived the edit.

- [ ] **Step 6: Commit**

```bash
git add garmin/README.md garmin/SKILL.md garmin/references/setup.md CLAUDE.md
git commit -m "docs(garmin): document distance_units and correct token/error guidance"
```

---

## Post-implementation: restore live service

Not a code task — it needs a human with an MFA code, and must happen **after** Task 3 (re-logging in beforehand hits the broken `dump()` path and fails to persist tokens).

1. Confirm the rate limit has cleared and re-authenticate:
   `~/.claude/skills/garmin/.venv/bin/python garmin/scripts/garmin_login.py`
   Supply the MFA code when prompted. Expect: `Authenticated as: <name>`.
2. Verify the resume path works — this is the assertion that the original bug is dead:
   `~/.claude/skills/garmin/.venv/bin/python garmin/scripts/garmin_client.py`
   Expect: `Authenticated as: <name>`, with no login attempt.
3. Smoke-test a real query: `garmin_health.py today`, `garmin_sleep.py`, `garmin_activities.py 7`.
4. Confirm tokens persisted: `~/.garmin/tokens/oauth2_token.json` should have a fresh `refresh_token_expires_at`.
