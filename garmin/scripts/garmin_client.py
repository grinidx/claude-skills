#!/usr/bin/env python3
"""
Garmin Connect client with session management.

Handles authentication, token caching, and provides a configured
Garmin client instance for other scripts to use.

Usage as library:
    from garmin_client import get_client, load_config
    config = load_config()
    client = get_client(config)
    stats = client.get_stats("2026-02-22")

Usage as CLI (test auth):
    python garmin_client.py
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from garminconnect import Garmin


DEFAULT_CONFIG_PATH = os.path.expanduser("~/.garmin/config.json")
DEFAULT_TOKEN_DIR = os.path.expanduser("~/.garmin/tokens")


class GarminConfigError(Exception):
    """Raised when Garmin configuration is invalid or missing."""
    pass


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


RELOGIN_COMMAND = (
    "  ~/.claude/skills/garmin/.venv/bin/python "
    "~/.claude/skills/garmin/scripts/garmin_login.py"
)


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
        return (
            "Not authenticated: no usable Garmin tokens found.\n"
            "Log in to authenticate:\n"
            f"{RELOGIN_COMMAND}"
        )

    if expiry < datetime.now():
        return (
            f"Garmin tokens expired on {expiry.date().isoformat()}.\n"
            "Log in again to refresh them:\n"
            f"{RELOGIN_COMMAND}"
        )

    return (
        f"Could not resume Garmin session: {exc}\n"
        "Log in again to refresh your tokens:\n"
        f"{RELOGIN_COMMAND}"
    )


def load_config(config_path: str = DEFAULT_CONFIG_PATH) -> dict:
    """Load Garmin credentials from config file.

    Args:
        config_path: Path to config.json containing email and password.

    Returns:
        Dict with 'email' and 'password' keys.

    Raises:
        GarminConfigError: If file missing or fields invalid.
    """
    path = Path(config_path)
    if not path.exists():
        raise GarminConfigError(
            f"Config file not found: {config_path}\n"
            f"Run setup.sh to configure credentials."
        )

    with open(path) as f:
        config = json.load(f)

    if "email" not in config or not config["email"]:
        raise GarminConfigError(
            f"Missing 'email' in {config_path}. Run setup.sh to reconfigure."
        )
    if "password" not in config or not config["password"]:
        raise GarminConfigError(
            f"Missing 'password' in {config_path}. Run setup.sh to reconfigure."
        )

    # Default preferences
    config.setdefault("units", "imperial")

    return config


def get_client(
    config: dict,
    token_dir: str = DEFAULT_TOKEN_DIR,
) -> Garmin:
    """Create an authenticated Garmin client.

    Tries cached tokens first, falls back to email/password login.
    Saves tokens after successful credential-based login.

    Args:
        config: Dict with 'email' and 'password'.
        token_dir: Directory for garth token storage.

    Returns:
        Authenticated Garmin client instance.
    """
    token_path = Path(token_dir)
    token_path.mkdir(parents=True, exist_ok=True)

    # Try cached tokens first
    if any(token_path.iterdir()):
        try:
            garmin = Garmin()
            garmin.login(str(token_path))
            return garmin
        except Exception:
            pass  # Fall through to credential login

    # Credential-based login (requires MFA if account has it enabled)
    # If MFA is needed and we're non-interactive, raise a clear error
    # directing the user to run garmin_login.py first.
    try:
        garmin = Garmin(
            email=config["email"],
            password=config["password"],
            is_cn=False,
        )
        garmin.login()
        garmin.garth.dump(str(token_path))
        return garmin
    except EOFError:
        raise GarminConfigError(
            "MFA required but running non-interactively.\n"
            "Run this first to authenticate:\n"
            "  ~/.claude/skills/garmin/.venv/bin/python "
            "~/.claude/skills/garmin/scripts/garmin_login.py"
        )
    except Exception:
        raise GarminConfigError(
            "Login failed (rate limit or auth error).\n"
            "Run login to re-authenticate:\n"
            "  ~/.claude/skills/garmin/.venv/bin/python "
            "~/.claude/skills/garmin/scripts/garmin_login.py"
        )


if __name__ == "__main__":
    """Quick auth test - run to verify credentials work."""
    try:
        config = load_config()
        client = get_client(config)
        name = client.get_full_name()
        print(f"Authenticated as: {name}")
    except GarminConfigError as e:
        print(f"Config error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Auth error: {e}", file=sys.stderr)
        sys.exit(1)
