# Garmin Import Skill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python-native Claude skill that queries Garmin Connect for health/fitness data and imports it as markdown into the second brain.

**Architecture:** Python scripts using the `garminconnect` library (OAuth via garth) for all API interaction. A shared client module handles auth and session caching. Individual scripts handle health, sleep, activities, snapshot, and rollup commands. All output is either printed (on-demand queries) or written as markdown files (periodic imports).

**Tech Stack:** Python 3, `garminconnect` library, `garth` (transitive dependency for OAuth), `pytest` for testing

**Design doc:** `docs/plans/2026-02-22-garmin-skill-design.md`

---

### Task 1: Project Scaffolding + Setup Script

**Files:**
- Create: `/home/devops/claude-skills/garmin/requirements.txt`
- Create: `/home/devops/claude-skills/garmin/scripts/setup.sh`

**Step 1: Create the directory structure**

```bash
mkdir -p /home/devops/claude-skills/garmin/{scripts,references,tests}
```

**Step 2: Write requirements.txt**

Create `/home/devops/claude-skills/garmin/requirements.txt`:

```
garminconnect>=0.2.20,<1.0
pytest>=7.0
```

**Step 3: Write setup.sh**

Create `/home/devops/claude-skills/garmin/scripts/setup.sh`:

```bash
#!/bin/bash
# Set up Garmin skill: credentials + Python venv
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$SKILL_DIR/.venv"
CONFIG_DIR="$HOME/.garmin"
CONFIG_FILE="$CONFIG_DIR/config.json"

echo "=== Garmin Skill Setup ==="

# --- Python venv ---
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python version: $PYTHON_VERSION"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
else
    echo "Virtual environment already exists"
fi

echo "Installing dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -r "$SKILL_DIR/requirements.txt" -q

# --- Credentials ---
mkdir -p "$CONFIG_DIR"

if [ -f "$CONFIG_FILE" ]; then
    echo ""
    echo "Existing credentials found at $CONFIG_FILE"
    read -p "Overwrite? (y/N): " overwrite
    if [[ ! "$overwrite" =~ ^[Yy]$ ]]; then
        echo "Keeping existing credentials."
        echo ""
        echo "=== Setup Complete ==="
        exit 0
    fi
fi

echo ""
echo "Enter your Garmin Connect credentials:"
read -p "Email: " email
read -s -p "Password: " password
echo ""

cat > "$CONFIG_FILE" <<CRED_EOF
{
  "email": "$email",
  "password": "$password"
}
CRED_EOF
chmod 600 "$CONFIG_FILE"
echo "Credentials saved to $CONFIG_FILE"

# --- Test login ---
echo ""
echo "Testing authentication..."
if "$VENV_DIR/bin/python" -c "
import json, sys
from garminconnect import Garmin

config = json.load(open('$CONFIG_FILE'))
garmin = Garmin(email=config['email'], password=config['password'])
garmin.login()
garmin.garth.dump('$CONFIG_DIR/tokens')
name = garmin.get_full_name()
print(f'Authenticated as: {name}')
"; then
    echo "Authentication successful!"
else
    echo "Authentication failed. Check your credentials and try again."
    echo "If MFA is required, run the test login manually."
    exit 1
fi

echo ""
echo "=== Setup Complete ==="
echo "Virtual environment: $VENV_DIR"
echo "Credentials: $CONFIG_FILE"
echo "Tokens: $CONFIG_DIR/tokens/"
```

**Step 4: Make setup.sh executable**

```bash
chmod +x /home/devops/claude-skills/garmin/scripts/setup.sh
```

**Step 5: Commit**

```bash
cd /home/devops/claude-skills
git add garmin/requirements.txt garmin/scripts/setup.sh
git commit -m "feat(garmin): add project scaffolding and setup script"
```

---

### Task 2: Garmin Client Module (Auth + Session)

**Files:**
- Create: `/home/devops/claude-skills/garmin/scripts/garmin_client.py`
- Create: `/home/devops/claude-skills/garmin/tests/test_garmin_client.py`

**Step 1: Write the failing tests**

Create `/home/devops/claude-skills/garmin/tests/test_garmin_client.py`:

```python
"""Tests for garmin_client.py — auth and session management."""

import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


# Ensure scripts/ is importable
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from garmin_client import get_client, load_config, GarminConfigError


class TestLoadConfig:
    """Test credential loading from ~/.garmin/config.json."""

    def test_loads_valid_config(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"email": "test@example.com", "password": "secret123"}))
        config = load_config(config_path=str(config_file))
        assert config["email"] == "test@example.com"
        assert config["password"] == "secret123"

    def test_raises_on_missing_file(self, tmp_path):
        with pytest.raises(GarminConfigError, match="not found"):
            load_config(config_path=str(tmp_path / "nonexistent.json"))

    def test_raises_on_missing_email(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"password": "secret123"}))
        with pytest.raises(GarminConfigError, match="email"):
            load_config(config_path=str(config_file))

    def test_raises_on_missing_password(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"email": "test@example.com"}))
        with pytest.raises(GarminConfigError, match="password"):
            load_config(config_path=str(config_file))


class TestGetClient:
    """Test Garmin client creation with token caching."""

    @patch("garmin_client.Garmin")
    def test_loads_cached_tokens_first(self, MockGarmin, tmp_path):
        """If tokens exist, should try loading them before using credentials."""
        token_dir = tmp_path / "tokens"
        token_dir.mkdir()

        mock_garmin = MagicMock()
        MockGarmin.return_value = mock_garmin

        config = {"email": "test@example.com", "password": "secret123"}
        client = get_client(config, token_dir=str(token_dir))

        # Should attempt token-based login
        mock_garmin.login.assert_called_once_with(str(token_dir))
        assert client is mock_garmin

    @patch("garmin_client.Garmin")
    def test_falls_back_to_credentials_on_token_failure(self, MockGarmin, tmp_path):
        """If token login fails, should fall back to email/password."""
        token_dir = tmp_path / "tokens"
        token_dir.mkdir()

        # First Garmin() instance: token login fails
        mock_token_garmin = MagicMock()
        mock_token_garmin.login.side_effect = Exception("Token expired")

        # Second Garmin() instance: credential login succeeds
        mock_cred_garmin = MagicMock()
        mock_cred_garmin.login.return_value = ("", "")
        mock_cred_garmin.garth = MagicMock()

        MockGarmin.side_effect = [mock_token_garmin, mock_cred_garmin]

        config = {"email": "test@example.com", "password": "secret123"}
        client = get_client(config, token_dir=str(token_dir))

        assert client is mock_cred_garmin
        # Should have saved tokens after successful credential login
        mock_cred_garmin.garth.dump.assert_called_once_with(str(token_dir))

    @patch("garmin_client.Garmin")
    def test_creates_token_dir_if_missing(self, MockGarmin, tmp_path):
        """Token directory should be created if it doesn't exist."""
        token_dir = tmp_path / "tokens"
        # Don't create it — get_client should

        mock_garmin = MagicMock()
        mock_garmin.login.return_value = ("", "")
        mock_garmin.garth = MagicMock()
        MockGarmin.return_value = mock_garmin

        config = {"email": "test@example.com", "password": "secret123"}
        get_client(config, token_dir=str(token_dir))

        assert token_dir.exists()
```

**Step 2: Run tests to verify they fail**

```bash
cd /home/devops/claude-skills/garmin
.venv/bin/python -m pytest tests/test_garmin_client.py -v
```

Expected: FAIL — `garmin_client` module doesn't exist yet.

**Step 3: Write garmin_client.py**

Create `/home/devops/claude-skills/garmin/scripts/garmin_client.py`:

```python
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
from pathlib import Path

from garminconnect import Garmin


DEFAULT_CONFIG_PATH = os.path.expanduser("~/.garmin/config.json")
DEFAULT_TOKEN_DIR = os.path.expanduser("~/.garmin/tokens")


class GarminConfigError(Exception):
    """Raised when Garmin configuration is invalid or missing."""

    pass


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
        raise GarminConfigError(f"Config file not found: {config_path}\nRun setup.sh to configure credentials.")

    with open(path) as f:
        config = json.load(f)

    if "email" not in config or not config["email"]:
        raise GarminConfigError(f"Missing 'email' in {config_path}. Run setup.sh to reconfigure.")
    if "password" not in config or not config["password"]:
        raise GarminConfigError(f"Missing 'password' in {config_path}. Run setup.sh to reconfigure.")

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

    # Credential-based login
    garmin = Garmin(
        email=config["email"],
        password=config["password"],
        is_cn=False,
    )
    garmin.login()
    garmin.garth.dump(str(token_path))
    return garmin


if __name__ == "__main__":
    """Quick auth test — run to verify credentials work."""
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
```

**Step 4: Run tests to verify they pass**

```bash
cd /home/devops/claude-skills/garmin
.venv/bin/python -m pytest tests/test_garmin_client.py -v
```

Expected: All 6 tests PASS.

**Step 5: Commit**

```bash
cd /home/devops/claude-skills
git add garmin/scripts/garmin_client.py garmin/tests/test_garmin_client.py
git commit -m "feat(garmin): add client module with auth and token caching"
```

---

### Task 3: Health Vitals Query

**Files:**
- Create: `/home/devops/claude-skills/garmin/scripts/garmin_health.py`
- Create: `/home/devops/claude-skills/garmin/tests/test_garmin_health.py`

**Step 1: Write the failing tests**

Create `/home/devops/claude-skills/garmin/tests/test_garmin_health.py`:

```python
"""Tests for garmin_health.py — daily vitals formatting."""

import pytest
from unittest.mock import MagicMock
from datetime import date

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from garmin_health import format_daily_vitals, format_weekly_vitals


# Realistic mock data matching Garmin API response shapes
MOCK_STATS = {
    "totalSteps": 8432,
    "totalKilocalories": 2180,
    "restingHeartRate": 58,
    "minHeartRate": 48,
    "maxHeartRate": 178,
}

MOCK_HRV = {
    "hrvSummary": {
        "weeklyAvg": 42,
        "lastNight": 45,
        "lastNightAvg": 43,
        "status": "BALANCED",
    }
}

MOCK_BODY_BATTERY = [
    {"charged": 75, "drained": 53, "startTimestampGMT": "2026-02-22T00:00:00.0"},
]

MOCK_STRESS = {
    "overallStressLevel": 34,
    "restStressDuration": 28800,
    "activityStressDuration": 14400,
    "highStressDuration": 3600,
}


class TestFormatDailyVitals:
    """Test formatting of daily health data into readable output."""

    def test_formats_complete_data(self):
        result = format_daily_vitals(
            cdate="2026-02-22",
            stats=MOCK_STATS,
            hrv=MOCK_HRV,
            body_battery=MOCK_BODY_BATTERY,
            stress=MOCK_STRESS,
        )
        assert "Resting HR" in result
        assert "58 bpm" in result
        assert "HRV" in result
        assert "Steps" in result
        assert "8,432" in result
        assert "Body Battery" in result
        assert "Stress" in result

    def test_handles_missing_hrv(self):
        result = format_daily_vitals(
            cdate="2026-02-22",
            stats=MOCK_STATS,
            hrv=None,
            body_battery=MOCK_BODY_BATTERY,
            stress=MOCK_STRESS,
        )
        assert "HRV" in result
        assert "No data" in result

    def test_handles_empty_body_battery(self):
        result = format_daily_vitals(
            cdate="2026-02-22",
            stats=MOCK_STATS,
            hrv=MOCK_HRV,
            body_battery=[],
            stress=MOCK_STRESS,
        )
        assert "Body Battery" in result
        assert "No data" in result


class TestFormatWeeklyVitals:
    """Test formatting of 7-day vitals table."""

    def test_formats_seven_days(self):
        days = []
        for i in range(7):
            days.append(
                {
                    "date": f"2026-02-{16 + i:02d}",
                    "resting_hr": 56 + i,
                    "hrv": 40 + i,
                    "body_battery_peak": 70 + i,
                    "steps": 7000 + (i * 500),
                    "stress_avg": 30 + i,
                }
            )
        result = format_weekly_vitals(days)
        assert "Mon" in result or "Tue" in result  # Day headers present
        assert "Avg" in result  # Average column present
        assert "Resting HR" in result

    def test_handles_partial_week(self):
        """If fewer than 7 days, should still format what's available."""
        days = [
            {
                "date": "2026-02-22",
                "resting_hr": 58,
                "hrv": 42,
                "body_battery_peak": 75,
                "steps": 8432,
                "stress_avg": 34,
            }
        ]
        result = format_weekly_vitals(days)
        assert "58" in result
```

**Step 2: Run tests to verify they fail**

```bash
cd /home/devops/claude-skills/garmin
.venv/bin/python -m pytest tests/test_garmin_health.py -v
```

Expected: FAIL — `garmin_health` module doesn't exist.

**Step 3: Write garmin_health.py**

Create `/home/devops/claude-skills/garmin/scripts/garmin_health.py`:

```python
#!/usr/bin/env python3
"""
Garmin health vitals — daily and weekly queries.

Commands:
    python garmin_health.py today          # Today's vitals
    python garmin_health.py 2026-02-22     # Specific date
    python garmin_health.py yesterday      # Yesterday's vitals
    python garmin_health.py week           # Last 7 days summary table
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from garmin_client import get_client, load_config, GarminConfigError


def fetch_day_data(client, cdate: str) -> dict:
    """Fetch all health data for a single day from Garmin API.

    Args:
        client: Authenticated Garmin client.
        cdate: Date string in YYYY-MM-DD format.

    Returns:
        Dict with keys: stats, hrv, body_battery, stress.
    """
    stats = _safe_call(client.get_stats, cdate) or {}
    hrv = _safe_call(client.get_hrv_data, cdate)
    body_battery = _safe_call(client.get_body_battery, cdate) or []
    stress = _safe_call(client.get_stress_data, cdate) or {}
    return {
        "stats": stats,
        "hrv": hrv,
        "body_battery": body_battery,
        "stress": stress,
    }


def _safe_call(fn, *args, **kwargs):
    """Call a Garmin API method, returning None on error."""
    try:
        return fn(*args, **kwargs)
    except Exception:
        return None


def format_daily_vitals(
    cdate: str,
    stats: dict,
    hrv: dict | None,
    body_battery: list,
    stress: dict,
) -> str:
    """Format a day's health vitals as a readable table.

    Args:
        cdate: Date string YYYY-MM-DD.
        stats: Response from get_stats().
        hrv: Response from get_hrv_data() or None.
        body_battery: Response from get_body_battery().
        stress: Response from get_stress_data().

    Returns:
        Formatted string with vitals table.
    """
    rhr = stats.get("restingHeartRate")
    rhr_str = f"{rhr} bpm" if rhr else "No data"

    hrv_val = None
    if hrv and isinstance(hrv, dict):
        summary = hrv.get("hrvSummary", {})
        if summary:
            hrv_val = summary.get("lastNightAvg") or summary.get("weeklyAvg")
    hrv_str = f"{hrv_val} ms" if hrv_val else "No data"

    if body_battery and len(body_battery) > 0:
        bb = body_battery[0] if isinstance(body_battery, list) else body_battery
        charged = bb.get("charged", "?")
        drained = bb.get("drained", "?")
        bb_str = (
            f"{charged} → {charged - drained}"
            if isinstance(charged, (int, float)) and isinstance(drained, (int, float))
            else "No data"
        )
    else:
        bb_str = "No data"

    stress_val = stress.get("overallStressLevel")
    stress_str = f"Avg {stress_val}" if stress_val else "No data"

    steps = stats.get("totalSteps")
    steps_str = f"{steps:,}" if steps else "No data"

    cals = stats.get("totalKilocalories")
    cals_str = f"{cals:,}" if cals else "No data"

    lines = [
        f"## Vitals — {cdate}",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Resting HR | {rhr_str} |",
        f"| HRV | {hrv_str} |",
        f"| Body Battery | {bb_str} |",
        f"| Stress | {stress_str} |",
        f"| Steps | {steps_str} |",
        f"| Calories | {cals_str} |",
    ]
    return "\n".join(lines)


def extract_day_summary(cdate: str, data: dict) -> dict:
    """Extract summary metrics from a day's raw data for weekly aggregation.

    Args:
        cdate: Date string YYYY-MM-DD.
        data: Dict from fetch_day_data().

    Returns:
        Dict with normalised metric values.
    """
    stats = data.get("stats", {})
    hrv = data.get("hrv")
    body_battery = data.get("body_battery", [])
    stress = data.get("stress", {})

    hrv_val = None
    if hrv and isinstance(hrv, dict):
        summary = hrv.get("hrvSummary", {})
        if summary:
            hrv_val = summary.get("lastNightAvg") or summary.get("weeklyAvg")

    bb_peak = None
    if body_battery and len(body_battery) > 0:
        bb = body_battery[0] if isinstance(body_battery, list) else body_battery
        bb_peak = bb.get("charged")

    return {
        "date": cdate,
        "resting_hr": stats.get("restingHeartRate"),
        "hrv": hrv_val,
        "body_battery_peak": bb_peak,
        "steps": stats.get("totalSteps"),
        "stress_avg": stress.get("overallStressLevel"),
    }


def format_weekly_vitals(days: list[dict]) -> str:
    """Format multiple days of vitals as a weekly summary table.

    Args:
        days: List of dicts from extract_day_summary(), one per day.

    Returns:
        Formatted string with weekly trends table.
    """
    if not days:
        return "No data available for this week."

    # Build day labels from dates
    day_names = []
    for d in days:
        try:
            dt = date.fromisoformat(d["date"])
            day_names.append(dt.strftime("%a"))
        except (ValueError, KeyError):
            day_names.append("?")

    metrics = [
        ("Resting HR", "resting_hr", ""),
        ("HRV", "hrv", ""),
        ("Body Battery Peak", "body_battery_peak", ""),
        ("Steps", "steps", "k"),
        ("Stress", "stress_avg", ""),
    ]

    # Header
    header = "| Metric | " + " | ".join(day_names) + " | Avg |"
    separator = "|--------|" + "|".join(["-----"] * len(days)) + "|-----|"

    rows = [header, separator]
    for label, key, fmt in metrics:
        values = [d.get(key) for d in days]
        cells = []
        for v in values:
            if v is None:
                cells.append("-")
            elif fmt == "k":
                cells.append(f"{v / 1000:.1f}k")
            else:
                cells.append(str(v))

        # Average
        numeric = [v for v in values if v is not None]
        if numeric:
            avg = sum(numeric) / len(numeric)
            avg_str = f"{avg / 1000:.1f}k" if fmt == "k" else str(round(avg))
        else:
            avg_str = "-"

        row = f"| {label} | " + " | ".join(cells) + f" | {avg_str} |"
        rows.append(row)

    return "\n".join(rows)


def resolve_date(date_arg: str) -> str:
    """Convert date argument to YYYY-MM-DD string.

    Accepts: 'today', 'yesterday', or YYYY-MM-DD.
    """
    if date_arg == "today":
        return date.today().isoformat()
    elif date_arg == "yesterday":
        return (date.today() - timedelta(days=1)).isoformat()
    else:
        # Validate format
        date.fromisoformat(date_arg)
        return date_arg


def main():
    parser = argparse.ArgumentParser(description="Garmin daily health vitals")
    parser.add_argument(
        "command",
        help="'today', 'yesterday', 'week', or a YYYY-MM-DD date",
    )
    args = parser.parse_args()

    try:
        config = load_config()
        client = get_client(config)
    except GarminConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.command == "week":
        today = date.today()
        days = []
        for i in range(6, -1, -1):
            d = (today - timedelta(days=i)).isoformat()
            data = fetch_day_data(client, d)
            days.append(extract_day_summary(d, data))
        print(format_weekly_vitals(days))
    else:
        cdate = resolve_date(args.command)
        data = fetch_day_data(client, cdate)
        print(
            format_daily_vitals(
                cdate=cdate,
                stats=data["stats"],
                hrv=data["hrv"],
                body_battery=data["body_battery"],
                stress=data["stress"],
            )
        )


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

```bash
cd /home/devops/claude-skills/garmin
.venv/bin/python -m pytest tests/test_garmin_health.py -v
```

Expected: All 5 tests PASS.

**Step 5: Commit**

```bash
cd /home/devops/claude-skills
git add garmin/scripts/garmin_health.py garmin/tests/test_garmin_health.py
git commit -m "feat(garmin): add health vitals query with daily and weekly formatting"
```

---

### Task 4: Sleep Data Query

**Files:**
- Create: `/home/devops/claude-skills/garmin/scripts/garmin_sleep.py`
- Create: `/home/devops/claude-skills/garmin/tests/test_garmin_sleep.py`

**Step 1: Write the failing tests**

Create `/home/devops/claude-skills/garmin/tests/test_garmin_sleep.py`:

```python
"""Tests for garmin_sleep.py — sleep data formatting."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from garmin_sleep import format_sleep_data


MOCK_SLEEP = {
    "dailySleepDTO": {
        "sleepScores": {
            "overall": {"value": 82},
        },
        "sleepTimeSeconds": 26640,  # 7h 24m
        "deepSleepSeconds": 4320,  # 1h 12m
        "lightSleepSeconds": 13680,  # 3h 48m
        "remSleepSeconds": 7560,  # 2h 06m
        "awakeSleepSeconds": 1080,  # 18m
        "sleepStartTimestampGMT": 1740182400000,
        "sleepEndTimestampGMT": 1740209040000,
    }
}


class TestFormatSleepData:
    """Test formatting of sleep data into readable output."""

    def test_formats_complete_sleep_data(self):
        result = format_sleep_data("2026-02-22", MOCK_SLEEP)
        assert "Sleep" in result
        assert "82" in result  # score
        assert "7h 24m" in result  # duration
        assert "1h 12m" in result  # deep
        assert "3h 48m" in result  # light
        assert "2h 06m" in result  # REM
        assert "18m" in result  # awake

    def test_handles_missing_sleep_data(self):
        result = format_sleep_data("2026-02-22", {})
        assert "No sleep data" in result

    def test_handles_none_sleep_data(self):
        result = format_sleep_data("2026-02-22", None)
        assert "No sleep data" in result

    def test_handles_zero_duration(self):
        """Edge case: sleep tracked but 0 seconds."""
        data = {
            "dailySleepDTO": {
                "sleepScores": {"overall": {"value": 0}},
                "sleepTimeSeconds": 0,
                "deepSleepSeconds": 0,
                "lightSleepSeconds": 0,
                "remSleepSeconds": 0,
                "awakeSleepSeconds": 0,
            }
        }
        result = format_sleep_data("2026-02-22", data)
        assert "0" in result
```

**Step 2: Run tests to verify they fail**

```bash
cd /home/devops/claude-skills/garmin
.venv/bin/python -m pytest tests/test_garmin_sleep.py -v
```

Expected: FAIL — `garmin_sleep` module doesn't exist.

**Step 3: Write garmin_sleep.py**

Create `/home/devops/claude-skills/garmin/scripts/garmin_sleep.py`:

```python
#!/usr/bin/env python3
"""
Garmin sleep data query.

Commands:
    python garmin_sleep.py                 # Last night's sleep
    python garmin_sleep.py 2026-02-22      # Sleep for specific date
    python garmin_sleep.py yesterday       # Yesterday's sleep
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from garmin_client import get_client, load_config, GarminConfigError


def _format_duration(seconds: int | None) -> str:
    """Convert seconds to human-readable duration like '7h 24m'."""
    if seconds is None or seconds < 0:
        return "No data"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def format_sleep_data(cdate: str, sleep_data: dict | None) -> str:
    """Format sleep data as a readable table.

    Args:
        cdate: Date string YYYY-MM-DD.
        sleep_data: Response from client.get_sleep_data() or None.

    Returns:
        Formatted string with sleep table.
    """
    if not sleep_data or "dailySleepDTO" not in sleep_data:
        return f"## Sleep — {cdate}\n\nNo sleep data recorded for this date."

    dto = sleep_data["dailySleepDTO"]
    scores = dto.get("sleepScores", {})
    overall_score = scores.get("overall", {}).get("value", "No data")

    total = dto.get("sleepTimeSeconds")
    deep = dto.get("deepSleepSeconds")
    light = dto.get("lightSleepSeconds")
    rem = dto.get("remSleepSeconds")
    awake = dto.get("awakeSleepSeconds")

    lines = [
        f"## Sleep — {cdate}",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Score | {overall_score} |",
        f"| Duration | {_format_duration(total)} |",
        f"| Deep | {_format_duration(deep)} |",
        f"| Light | {_format_duration(light)} |",
        f"| REM | {_format_duration(rem)} |",
        f"| Awake | {_format_duration(awake)} |",
    ]
    return "\n".join(lines)


def fetch_sleep(client, cdate: str) -> dict | None:
    """Fetch sleep data from Garmin API."""
    try:
        return client.get_sleep_data(cdate)
    except Exception:
        return None


def resolve_date(date_arg: str) -> str:
    """Convert date argument to YYYY-MM-DD string."""
    if not date_arg or date_arg == "today":
        return date.today().isoformat()
    elif date_arg == "yesterday":
        return (date.today() - timedelta(days=1)).isoformat()
    else:
        date.fromisoformat(date_arg)
        return date_arg


def main():
    parser = argparse.ArgumentParser(description="Garmin sleep data")
    parser.add_argument(
        "date",
        nargs="?",
        default="today",
        help="'today', 'yesterday', or YYYY-MM-DD (default: today)",
    )
    args = parser.parse_args()

    try:
        config = load_config()
        client = get_client(config)
    except GarminConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    cdate = resolve_date(args.date)
    sleep_data = fetch_sleep(client, cdate)
    print(format_sleep_data(cdate, sleep_data))


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

```bash
cd /home/devops/claude-skills/garmin
.venv/bin/python -m pytest tests/test_garmin_sleep.py -v
```

Expected: All 4 tests PASS.

**Step 5: Commit**

```bash
cd /home/devops/claude-skills
git add garmin/scripts/garmin_sleep.py garmin/tests/test_garmin_sleep.py
git commit -m "feat(garmin): add sleep data query with formatting"
```

---

### Task 5: Activities & Training Query

**Files:**
- Create: `/home/devops/claude-skills/garmin/scripts/garmin_activities.py`
- Create: `/home/devops/claude-skills/garmin/tests/test_garmin_activities.py`

**Step 1: Write the failing tests**

Create `/home/devops/claude-skills/garmin/tests/test_garmin_activities.py`:

```python
"""Tests for garmin_activities.py — activities and training formatting."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from garmin_activities import format_activities, format_training_status


MOCK_ACTIVITIES = [
    {
        "activityName": "HYROX Training",
        "activityType": {"typeKey": "strength_training"},
        "startTimeLocal": "2026-02-22 07:30:00",
        "duration": 3480.0,  # 58 min in seconds
        "distance": None,
        "averageHR": 152.0,
        "maxHR": 178.0,
        "calories": 620.0,
        "aerobicTrainingEffect": 3.8,
        "anaerobicTrainingEffect": 2.1,
    },
    {
        "activityName": "Morning Run",
        "activityType": {"typeKey": "running"},
        "startTimeLocal": "2026-02-21 06:45:00",
        "duration": 2100.0,  # 35 min
        "distance": 5200.0,  # metres
        "averageHR": 145.0,
        "maxHR": 168.0,
        "calories": 380.0,
        "aerobicTrainingEffect": 3.2,
        "anaerobicTrainingEffect": 1.5,
    },
]

MOCK_TRAINING_STATUS = {
    "mostRecentVO2Max": 44.0,
    "mostRecentVO2MaxRunning": 44.0,
    "trainingStatusFeedbackPhrase": "PRODUCTIVE",
    "weeklyTrainingLoad": 412,
}

MOCK_TRAINING_READINESS = {
    "score": 62,
    "level": "MODERATE",
}


class TestFormatActivities:
    """Test formatting of activity list."""

    def test_formats_multiple_activities(self):
        result = format_activities(MOCK_ACTIVITIES)
        assert "HYROX Training" in result
        assert "Morning Run" in result
        assert "58 min" in result
        assert "152 bpm" in result
        assert "5.2 km" in result

    def test_handles_empty_list(self):
        result = format_activities([])
        assert "No activities" in result

    def test_handles_missing_distance(self):
        """Activities without distance (e.g. strength) should not show distance."""
        result = format_activities([MOCK_ACTIVITIES[0]])
        assert "HYROX Training" in result
        # Should not crash on None distance

    def test_formats_training_effect(self):
        result = format_activities(MOCK_ACTIVITIES)
        assert "3.8" in result  # aerobic TE
        assert "2.1" in result  # anaerobic TE


class TestFormatTrainingStatus:
    """Test formatting of training status metrics."""

    def test_formats_complete_training_data(self):
        result = format_training_status(MOCK_TRAINING_STATUS, MOCK_TRAINING_READINESS)
        assert "VO2 Max" in result
        assert "44" in result
        assert "Training Load" in result
        assert "412" in result
        assert "Training Readiness" in result
        assert "62" in result
        assert "Productive" in result or "PRODUCTIVE" in result

    def test_handles_missing_readiness(self):
        result = format_training_status(MOCK_TRAINING_STATUS, None)
        assert "VO2 Max" in result
        assert "Training Readiness" in result
        assert "No data" in result

    def test_handles_missing_training_status(self):
        result = format_training_status(None, MOCK_TRAINING_READINESS)
        assert "No data" in result or "VO2 Max" in result
```

**Step 2: Run tests to verify they fail**

```bash
cd /home/devops/claude-skills/garmin
.venv/bin/python -m pytest tests/test_garmin_activities.py -v
```

Expected: FAIL — `garmin_activities` module doesn't exist.

**Step 3: Write garmin_activities.py**

Create `/home/devops/claude-skills/garmin/scripts/garmin_activities.py`:

```python
#!/usr/bin/env python3
"""
Garmin activities and training status query.

Commands:
    python garmin_activities.py 7           # Activities from last 7 days
    python garmin_activities.py 30          # Activities from last 30 days
    python garmin_activities.py training    # Training status (VO2, load, readiness)
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from garmin_client import get_client, load_config, GarminConfigError


def _format_duration_mins(seconds: float | None) -> str:
    """Convert seconds to 'Xh Ym' or 'Ym' format."""
    if not seconds:
        return "?"
    total_mins = int(seconds / 60)
    hours = total_mins // 60
    mins = total_mins % 60
    if hours > 0:
        return f"{hours}h {mins:02d} min"
    return f"{mins} min"


def _format_distance(metres: float | None) -> str | None:
    """Convert metres to km string, or None if no distance."""
    if metres is None or metres <= 0:
        return None
    km = metres / 1000
    return f"{km:.1f} km"


def format_activities(activities: list[dict]) -> str:
    """Format a list of activities into readable output.

    Args:
        activities: List of activity dicts from Garmin API.

    Returns:
        Formatted string listing activities.
    """
    if not activities:
        return "No activities found for this period."

    lines = ["## Activities", ""]
    for act in activities:
        name = act.get("activityName", "Unknown Activity")
        duration = _format_duration_mins(act.get("duration"))
        distance = _format_distance(act.get("distance"))
        avg_hr = act.get("averageHR")
        max_hr = act.get("maxHR")
        calories = act.get("calories")
        aero_te = act.get("aerobicTrainingEffect")
        anaero_te = act.get("anaerobicTrainingEffect")

        start_time = act.get("startTimeLocal", "")
        date_part = start_time.split(" ")[0] if " " in start_time else start_time

        # Title line
        title_parts = [f"### {name} ({duration})"]
        if distance:
            title_parts[0] += f" — {distance}"
        lines.append(title_parts[0])
        if date_part:
            lines.append(f"*{date_part}*")

        # Detail lines
        details = []
        if avg_hr:
            hr_str = f"Avg HR: {int(avg_hr)} bpm"
            if max_hr:
                hr_str += f" | Max HR: {int(max_hr)} bpm"
            details.append(hr_str)
        if calories:
            details.append(f"Calories: {int(calories)}")
        if aero_te is not None:
            te_str = f"Training Effect: Aerobic {aero_te}"
            if anaero_te is not None:
                te_str += f" / Anaerobic {anaero_te}"
            details.append(te_str)

        for d in details:
            lines.append(f"- {d}")
        lines.append("")

    return "\n".join(lines)


def format_training_status(
    training_status: dict | None,
    training_readiness: dict | None,
) -> str:
    """Format training status metrics as a table.

    Args:
        training_status: Response from get_training_status().
        training_readiness: Response from get_training_readiness().

    Returns:
        Formatted string with training metrics table.
    """
    vo2 = None
    load = None
    status = None
    readiness = None

    if training_status:
        vo2 = training_status.get("mostRecentVO2Max") or training_status.get("mostRecentVO2MaxRunning")
        load = training_status.get("weeklyTrainingLoad")
        status_raw = training_status.get("trainingStatusFeedbackPhrase")
        status = status_raw.replace("_", " ").title() if status_raw else None

    if training_readiness:
        readiness = training_readiness.get("score")

    lines = [
        "## Training Status",
        "| Metric | Value |",
        "|--------|-------|",
        f"| VO2 Max | {vo2 if vo2 else 'No data'} |",
        f"| Training Load | {load if load else 'No data'} |",
        f"| Training Readiness | {readiness if readiness else 'No data'} |",
        f"| Training Status | {status if status else 'No data'} |",
    ]
    return "\n".join(lines)


def fetch_activities(client, days: int = 7) -> list[dict]:
    """Fetch recent activities from Garmin API."""
    try:
        end = date.today().isoformat()
        start = (date.today() - timedelta(days=days)).isoformat()
        return client.get_activities_by_date(start, end) or []
    except Exception:
        return []


def fetch_training(client, cdate: str) -> tuple[dict | None, dict | None]:
    """Fetch training status and readiness from Garmin API."""
    status = None
    readiness = None
    try:
        status = client.get_training_status(cdate)
    except Exception:
        pass
    try:
        readiness = client.get_training_readiness(cdate)
    except Exception:
        pass
    return status, readiness


def main():
    parser = argparse.ArgumentParser(description="Garmin activities and training")
    parser.add_argument(
        "command",
        help="Number of days to look back, or 'training' for training status",
    )
    args = parser.parse_args()

    try:
        config = load_config()
        client = get_client(config)
    except GarminConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.command == "training":
        cdate = date.today().isoformat()
        status, readiness = fetch_training(client, cdate)
        print(format_training_status(status, readiness))
    else:
        try:
            days = int(args.command)
        except ValueError:
            print(f"Error: expected a number of days or 'training', got '{args.command}'", file=sys.stderr)
            sys.exit(1)
        activities = fetch_activities(client, days)
        print(format_activities(activities))


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

```bash
cd /home/devops/claude-skills/garmin
.venv/bin/python -m pytest tests/test_garmin_activities.py -v
```

Expected: All 7 tests PASS.

**Step 5: Commit**

```bash
cd /home/devops/claude-skills
git add garmin/scripts/garmin_activities.py garmin/tests/test_garmin_activities.py
git commit -m "feat(garmin): add activities and training status query"
```

---

### Task 6: Daily Snapshot (Markdown Import)

**Files:**
- Create: `/home/devops/claude-skills/garmin/scripts/garmin_snapshot.py`
- Create: `/home/devops/claude-skills/garmin/tests/test_garmin_snapshot.py`

**Step 1: Write the failing tests**

Create `/home/devops/claude-skills/garmin/tests/test_garmin_snapshot.py`:

```python
"""Tests for garmin_snapshot.py — daily markdown file generation."""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from garmin_snapshot import generate_daily_markdown, write_snapshot


# Reuse mock data structures
MOCK_HEALTH = {
    "stats": {
        "totalSteps": 8432,
        "totalKilocalories": 2180,
        "restingHeartRate": 58,
    },
    "hrv": {
        "hrvSummary": {"lastNightAvg": 42, "weeklyAvg": 42, "status": "BALANCED"},
    },
    "body_battery": [{"charged": 75, "drained": 53}],
    "stress": {"overallStressLevel": 34},
}

MOCK_SLEEP = {
    "dailySleepDTO": {
        "sleepScores": {"overall": {"value": 82}},
        "sleepTimeSeconds": 26640,
        "deepSleepSeconds": 4320,
        "lightSleepSeconds": 13680,
        "remSleepSeconds": 7560,
        "awakeSleepSeconds": 1080,
    }
}

MOCK_ACTIVITIES = [
    {
        "activityName": "HYROX Training",
        "activityType": {"typeKey": "strength_training"},
        "startTimeLocal": "2026-02-22 07:30:00",
        "duration": 3480.0,
        "distance": None,
        "averageHR": 152.0,
        "maxHR": 178.0,
        "calories": 620.0,
        "aerobicTrainingEffect": 3.8,
        "anaerobicTrainingEffect": 2.1,
    },
]

MOCK_TRAINING_STATUS = {
    "mostRecentVO2Max": 44.0,
    "trainingStatusFeedbackPhrase": "PRODUCTIVE",
    "weeklyTrainingLoad": 412,
}

MOCK_TRAINING_READINESS = {"score": 62, "level": "MODERATE"}


class TestGenerateDailyMarkdown:
    """Test full daily markdown generation."""

    def test_contains_all_sections(self):
        md = generate_daily_markdown(
            cdate="2026-02-22",
            health_data=MOCK_HEALTH,
            sleep_data=MOCK_SLEEP,
            activities=MOCK_ACTIVITIES,
            training_status=MOCK_TRAINING_STATUS,
            training_readiness=MOCK_TRAINING_READINESS,
        )
        assert "# Garmin Daily: 2026-02-22" in md
        assert "## Vitals" in md
        assert "## Sleep" in md
        assert "## Activities" in md
        assert "## Training Status" in md

    def test_contains_actual_data(self):
        md = generate_daily_markdown(
            cdate="2026-02-22",
            health_data=MOCK_HEALTH,
            sleep_data=MOCK_SLEEP,
            activities=MOCK_ACTIVITIES,
            training_status=MOCK_TRAINING_STATUS,
            training_readiness=MOCK_TRAINING_READINESS,
        )
        assert "58 bpm" in md  # resting HR
        assert "82" in md  # sleep score
        assert "HYROX" in md  # activity name
        assert "44" in md  # VO2 max

    def test_handles_no_activities(self):
        md = generate_daily_markdown(
            cdate="2026-02-22",
            health_data=MOCK_HEALTH,
            sleep_data=MOCK_SLEEP,
            activities=[],
            training_status=MOCK_TRAINING_STATUS,
            training_readiness=MOCK_TRAINING_READINESS,
        )
        assert "No activities" in md

    def test_handles_no_sleep(self):
        md = generate_daily_markdown(
            cdate="2026-02-22",
            health_data=MOCK_HEALTH,
            sleep_data=None,
            activities=MOCK_ACTIVITIES,
            training_status=MOCK_TRAINING_STATUS,
            training_readiness=MOCK_TRAINING_READINESS,
        )
        assert "No sleep data" in md


class TestWriteSnapshot:
    """Test writing snapshot to file."""

    def test_writes_file_to_correct_path(self, tmp_path):
        md = "# Garmin Daily: 2026-02-22\n\nTest content"
        output_path = write_snapshot("2026-02-22", md, output_dir=str(tmp_path))
        assert Path(output_path).exists()
        assert output_path.endswith("2026-02-22.md")
        assert Path(output_path).read_text() == md

    def test_creates_directory_if_missing(self, tmp_path):
        target = tmp_path / "garmin"
        md = "# Test"
        write_snapshot("2026-02-22", md, output_dir=str(target))
        assert (target / "2026-02-22.md").exists()

    def test_overwrites_existing_file(self, tmp_path):
        existing = tmp_path / "2026-02-22.md"
        existing.write_text("old content")
        write_snapshot("2026-02-22", "new content", output_dir=str(tmp_path))
        assert existing.read_text() == "new content"
```

**Step 2: Run tests to verify they fail**

```bash
cd /home/devops/claude-skills/garmin
.venv/bin/python -m pytest tests/test_garmin_snapshot.py -v
```

Expected: FAIL — `garmin_snapshot` module doesn't exist.

**Step 3: Write garmin_snapshot.py**

Create `/home/devops/claude-skills/garmin/scripts/garmin_snapshot.py`:

```python
#!/usr/bin/env python3
"""
Garmin daily snapshot — pulls all data for a day and writes a markdown file.

Commands:
    python garmin_snapshot.py                 # Snapshot for today
    python garmin_snapshot.py 2026-02-22      # Specific date
    python garmin_snapshot.py yesterday       # Yesterday

Output: areas/health/garmin/YYYY-MM-DD.md in the brain repo.
"""

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from garmin_client import get_client, load_config, GarminConfigError
from garmin_health import fetch_day_data, format_daily_vitals
from garmin_sleep import format_sleep_data, fetch_sleep
from garmin_activities import (
    format_activities,
    format_training_status,
    fetch_activities,
    fetch_training,
)


# Default output directory — resolve from brain repo
DEFAULT_OUTPUT_DIR = os.path.expanduser("~/brain/areas/health/garmin")


def generate_daily_markdown(
    cdate: str,
    health_data: dict,
    sleep_data: dict | None,
    activities: list[dict],
    training_status: dict | None,
    training_readiness: dict | None,
) -> str:
    """Generate a complete daily markdown snapshot.

    Args:
        cdate: Date string YYYY-MM-DD.
        health_data: Dict from fetch_day_data() with stats, hrv, body_battery, stress.
        sleep_data: Response from get_sleep_data() or None.
        activities: List of activity dicts for this date.
        training_status: Response from get_training_status() or None.
        training_readiness: Response from get_training_readiness() or None.

    Returns:
        Complete markdown string for the daily snapshot file.
    """
    sections = [f"# Garmin Daily: {cdate}", ""]

    # Vitals
    vitals = format_daily_vitals(
        cdate=cdate,
        stats=health_data.get("stats", {}),
        hrv=health_data.get("hrv"),
        body_battery=health_data.get("body_battery", []),
        stress=health_data.get("stress", {}),
    )
    sections.append(vitals)
    sections.append("")

    # Sleep
    sleep = format_sleep_data(cdate, sleep_data)
    sections.append(sleep)
    sections.append("")

    # Activities
    acts = format_activities(activities)
    sections.append(acts)
    sections.append("")

    # Training status
    training = format_training_status(training_status, training_readiness)
    sections.append(training)
    sections.append("")

    return "\n".join(sections)


def write_snapshot(cdate: str, markdown: str, output_dir: str = DEFAULT_OUTPUT_DIR) -> str:
    """Write a daily snapshot markdown file.

    Args:
        cdate: Date string YYYY-MM-DD.
        markdown: Complete markdown content.
        output_dir: Directory to write the file to.

    Returns:
        Absolute path of the written file.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    file_path = out_path / f"{cdate}.md"
    file_path.write_text(markdown)
    return str(file_path)


def resolve_date(date_arg: str) -> str:
    """Convert date argument to YYYY-MM-DD string."""
    if not date_arg or date_arg == "today":
        return date.today().isoformat()
    elif date_arg == "yesterday":
        return (date.today() - timedelta(days=1)).isoformat()
    else:
        date.fromisoformat(date_arg)
        return date_arg


def main():
    parser = argparse.ArgumentParser(description="Garmin daily snapshot")
    parser.add_argument(
        "date",
        nargs="?",
        default="today",
        help="'today', 'yesterday', or YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    args = parser.parse_args()

    try:
        config = load_config()
        client = get_client(config)
    except GarminConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    cdate = resolve_date(args.date)
    print(f"Fetching Garmin data for {cdate}...")

    # Fetch all data
    health_data = fetch_day_data(client, cdate)
    sleep_data = fetch_sleep(client, cdate)
    activities_data = fetch_activities(client, days=1)
    # Filter activities to just this date
    activities = [a for a in activities_data if a.get("startTimeLocal", "").startswith(cdate)]
    training_status, training_readiness = fetch_training(client, cdate)

    # Generate and write
    markdown = generate_daily_markdown(
        cdate=cdate,
        health_data=health_data,
        sleep_data=sleep_data,
        activities=activities,
        training_status=training_status,
        training_readiness=training_readiness,
    )

    file_path = write_snapshot(cdate, markdown, output_dir=args.output_dir)
    print(f"Snapshot written to: {file_path}")


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

```bash
cd /home/devops/claude-skills/garmin
.venv/bin/python -m pytest tests/test_garmin_snapshot.py -v
```

Expected: All 7 tests PASS.

**Step 5: Commit**

```bash
cd /home/devops/claude-skills
git add garmin/scripts/garmin_snapshot.py garmin/tests/test_garmin_snapshot.py
git commit -m "feat(garmin): add daily snapshot markdown generation"
```

---

### Task 7: Weekly Rollup

**Files:**
- Create: `/home/devops/claude-skills/garmin/scripts/garmin_rollup.py`
- Create: `/home/devops/claude-skills/garmin/tests/test_garmin_rollup.py`

**Step 1: Write the failing tests**

Create `/home/devops/claude-skills/garmin/tests/test_garmin_rollup.py`:

```python
"""Tests for garmin_rollup.py — weekly rollup markdown generation."""

import pytest
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from garmin_rollup import (
    generate_weekly_markdown,
    get_week_dates,
    find_highlights,
    write_rollup,
)


def _make_day_summary(cdate, rhr=58, hrv=42, bb=75, steps=8000, stress=34):
    return {
        "date": cdate,
        "resting_hr": rhr,
        "hrv": hrv,
        "body_battery_peak": bb,
        "steps": steps,
        "stress_avg": stress,
    }


MOCK_WEEK = [
    _make_day_summary("2026-02-16", rhr=58, hrv=42, bb=75, steps=8432, stress=34),
    _make_day_summary("2026-02-17", rhr=56, hrv=45, bb=80, steps=10100, stress=30),
    _make_day_summary("2026-02-18", rhr=59, hrv=38, bb=68, steps=6200, stress=40),
    _make_day_summary("2026-02-19", rhr=57, hrv=44, bb=78, steps=9300, stress=32),
    _make_day_summary("2026-02-20", rhr=55, hrv=48, bb=82, steps=11000, stress=28),
    _make_day_summary("2026-02-21", rhr=58, hrv=41, bb=71, steps=7800, stress=36),
    _make_day_summary("2026-02-22", rhr=56, hrv=46, bb=84, steps=5100, stress=31),
]

MOCK_ACTIVITIES = [
    {
        "activityName": "HYROX Training",
        "startTimeLocal": "2026-02-16 07:30:00",
        "duration": 3480.0,
        "distance": None,
        "aerobicTrainingEffect": 3.8,
    },
    {
        "activityName": "Running",
        "startTimeLocal": "2026-02-18 06:45:00",
        "duration": 2100.0,
        "distance": 5200.0,
        "aerobicTrainingEffect": 3.2,
    },
]


class TestGetWeekDates:
    """Test ISO week date calculation."""

    def test_returns_seven_dates(self):
        dates = get_week_dates(2026, 8)
        assert len(dates) == 7

    def test_starts_on_monday(self):
        dates = get_week_dates(2026, 8)
        first = date.fromisoformat(dates[0])
        assert first.weekday() == 0  # Monday

    def test_ends_on_sunday(self):
        dates = get_week_dates(2026, 8)
        last = date.fromisoformat(dates[-1])
        assert last.weekday() == 6  # Sunday


class TestFindHighlights:
    """Test highlight extraction from weekly data."""

    def test_finds_best_sleep(self):
        highlights = find_highlights(MOCK_WEEK, MOCK_ACTIVITIES)
        # Best body battery peak is Sunday (84)
        assert any("84" in h for h in highlights)

    def test_finds_highest_hrv(self):
        highlights = find_highlights(MOCK_WEEK, MOCK_ACTIVITIES)
        # Highest HRV is Friday (48)
        assert any("48" in h for h in highlights)

    def test_counts_activities(self):
        highlights = find_highlights(MOCK_WEEK, MOCK_ACTIVITIES)
        assert any("2" in h for h in highlights)  # 2 sessions


class TestGenerateWeeklyMarkdown:
    """Test full weekly markdown generation."""

    def test_contains_all_sections(self):
        md = generate_weekly_markdown(
            year=2026,
            week=8,
            day_summaries=MOCK_WEEK,
            activities=MOCK_ACTIVITIES,
            training_status={"mostRecentVO2Max": 44.0, "weeklyTrainingLoad": 412},
            training_readiness={"score": 62},
        )
        assert "# Garmin Weekly: 2026-W08" in md
        assert "## Trends" in md
        assert "## Activities" in md
        assert "## Highlights" in md
        assert "## Notes" in md

    def test_contains_data_values(self):
        md = generate_weekly_markdown(
            year=2026,
            week=8,
            day_summaries=MOCK_WEEK,
            activities=MOCK_ACTIVITIES,
            training_status={"mostRecentVO2Max": 44.0, "weeklyTrainingLoad": 412},
            training_readiness={"score": 62},
        )
        assert "HYROX" in md
        assert "Running" in md


class TestWriteRollup:
    """Test writing rollup to file."""

    def test_writes_to_correct_path(self, tmp_path):
        md = "# Test rollup"
        path = write_rollup(2026, 8, md, output_dir=str(tmp_path))
        assert Path(path).exists()
        assert "2026-W08.md" in path

    def test_creates_directory(self, tmp_path):
        target = tmp_path / "weekly"
        write_rollup(2026, 8, "# Test", output_dir=str(target))
        assert (target / "2026-W08.md").exists()
```

**Step 2: Run tests to verify they fail**

```bash
cd /home/devops/claude-skills/garmin
.venv/bin/python -m pytest tests/test_garmin_rollup.py -v
```

Expected: FAIL — `garmin_rollup` module doesn't exist.

**Step 3: Write garmin_rollup.py**

Create `/home/devops/claude-skills/garmin/scripts/garmin_rollup.py`:

```python
#!/usr/bin/env python3
"""
Garmin weekly rollup — aggregates daily data into a weekly summary.

Commands:
    python garmin_rollup.py              # Current week
    python garmin_rollup.py 2026-W08     # Specific ISO week
    python garmin_rollup.py last         # Previous week

Output: areas/health/garmin/weekly/YYYY-WXX.md in the brain repo.
"""

import argparse
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from garmin_client import get_client, load_config, GarminConfigError
from garmin_health import fetch_day_data, extract_day_summary, format_weekly_vitals
from garmin_activities import (
    format_activities,
    format_training_status,
    fetch_activities,
    fetch_training,
    _format_duration_mins,
    _format_distance,
)


DEFAULT_OUTPUT_DIR = os.path.expanduser("~/brain/areas/health/garmin/weekly")


def get_week_dates(year: int, week: int) -> list[str]:
    """Get all 7 dates (Mon-Sun) for an ISO week.

    Args:
        year: ISO year.
        week: ISO week number.

    Returns:
        List of 7 date strings in YYYY-MM-DD format.
    """
    # ISO week: Monday is day 1
    monday = date.fromisocalendar(year, week, 1)
    return [(monday + timedelta(days=i)).isoformat() for i in range(7)]


def find_highlights(day_summaries: list[dict], activities: list[dict]) -> list[str]:
    """Extract notable highlights from the week's data.

    Args:
        day_summaries: List of daily summary dicts.
        activities: List of activity dicts for the week.

    Returns:
        List of highlight strings.
    """
    highlights = []

    # Best body battery
    bb_days = [(d["date"], d["body_battery_peak"]) for d in day_summaries if d.get("body_battery_peak")]
    if bb_days:
        best_bb = max(bb_days, key=lambda x: x[1])
        dt = date.fromisoformat(best_bb[0])
        highlights.append(f"**Best Body Battery:** {dt.strftime('%A')} ({best_bb[1]})")

    # Highest HRV
    hrv_days = [(d["date"], d["hrv"]) for d in day_summaries if d.get("hrv")]
    if hrv_days:
        best_hrv = max(hrv_days, key=lambda x: x[1])
        dt = date.fromisoformat(best_hrv[0])
        highlights.append(f"**Highest HRV:** {dt.strftime('%A')} ({best_hrv[1]})")

    # Activity count
    if activities:
        highlights.append(f"**Activities:** {len(activities)} sessions")

    return highlights


def _format_activity_summary(act: dict) -> str:
    """Format a single activity as a one-line summary for the weekly view."""
    name = act.get("activityName", "Unknown")
    duration = _format_duration_mins(act.get("duration"))
    start = act.get("startTimeLocal", "")
    date_part = start.split(" ")[0] if " " in start else start

    day_str = ""
    if date_part:
        try:
            dt = date.fromisoformat(date_part)
            day_str = dt.strftime("%a")
        except ValueError:
            pass

    parts = [f"- {day_str}: {name} — {duration}"]
    distance = _format_distance(act.get("distance"))
    if distance:
        parts[0] += f", {distance}"
    te = act.get("aerobicTrainingEffect")
    if te:
        parts[0] += f", TE {te}"

    return parts[0]


def generate_weekly_markdown(
    year: int,
    week: int,
    day_summaries: list[dict],
    activities: list[dict],
    training_status: dict | None,
    training_readiness: dict | None,
) -> str:
    """Generate a complete weekly rollup markdown file.

    Args:
        year: ISO year.
        week: ISO week number.
        day_summaries: List of daily summary dicts (from extract_day_summary).
        activities: List of activity dicts for the week.
        training_status: Latest training status or None.
        training_readiness: Latest training readiness or None.

    Returns:
        Complete markdown string for the weekly rollup.
    """
    week_str = f"{year}-W{week:02d}"
    sections = [f"# Garmin Weekly: {week_str}", ""]

    # Trends table
    sections.append("## Trends")
    sections.append(format_weekly_vitals(day_summaries))
    sections.append("")

    # Activities summary
    if activities:
        sections.append(f"## Activities ({len(activities)} sessions)")
        for act in activities:
            sections.append(_format_activity_summary(act))
    else:
        sections.append("## Activities")
        sections.append("No activities recorded this week.")
    sections.append("")

    # Highlights
    highlights = find_highlights(day_summaries, activities)

    # Add training metrics to highlights
    if training_status:
        vo2 = training_status.get("mostRecentVO2Max")
        load = training_status.get("weeklyTrainingLoad")
        if load:
            highlights.append(f"**Training load:** {load}")
        if vo2:
            highlights.append(f"**VO2 Max:** {vo2}")

    sections.append("## Highlights")
    for h in highlights:
        sections.append(f"- {h}")
    sections.append("")

    # Notes placeholder
    sections.append("## Notes")
    sections.append("[Auto-generated — edit to add context during weekly review]")
    sections.append("")

    return "\n".join(sections)


def write_rollup(year: int, week: int, markdown: str, output_dir: str = DEFAULT_OUTPUT_DIR) -> str:
    """Write a weekly rollup markdown file.

    Args:
        year: ISO year.
        week: ISO week number.
        markdown: Complete markdown content.
        output_dir: Directory to write the file to.

    Returns:
        Absolute path of the written file.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    filename = f"{year}-W{week:02d}.md"
    file_path = out_path / filename
    file_path.write_text(markdown)
    return str(file_path)


def resolve_week(week_arg: str) -> tuple[int, int]:
    """Resolve a week argument to (year, week) tuple.

    Accepts: 'current', 'last', or 'YYYY-WXX'.
    """
    if not week_arg or week_arg == "current":
        today = date.today()
        iso = today.isocalendar()
        return iso.year, iso.week
    elif week_arg == "last":
        last_week = date.today() - timedelta(weeks=1)
        iso = last_week.isocalendar()
        return iso.year, iso.week
    else:
        match = re.match(r"(\d{4})-W(\d{1,2})", week_arg)
        if not match:
            raise ValueError(f"Invalid week format: {week_arg}. Use YYYY-WXX.")
        return int(match.group(1)), int(match.group(2))


def main():
    parser = argparse.ArgumentParser(description="Garmin weekly rollup")
    parser.add_argument(
        "week",
        nargs="?",
        default="current",
        help="'current', 'last', or YYYY-WXX (default: current)",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    args = parser.parse_args()

    try:
        config = load_config()
        client = get_client(config)
    except GarminConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    year, week = resolve_week(args.week)
    dates = get_week_dates(year, week)
    print(f"Generating rollup for {year}-W{week:02d} ({dates[0]} to {dates[-1]})...")

    # Fetch daily data for each day
    day_summaries = []
    for d in dates:
        data = fetch_day_data(client, d)
        day_summaries.append(extract_day_summary(d, data))

    # Fetch activities for the week
    try:
        activities = client.get_activities_by_date(dates[0], dates[-1]) or []
    except Exception:
        activities = []

    # Training status from most recent day
    training_status, training_readiness = fetch_training(client, dates[-1])

    # Generate and write
    markdown = generate_weekly_markdown(
        year=year,
        week=week,
        day_summaries=day_summaries,
        activities=activities,
        training_status=training_status,
        training_readiness=training_readiness,
    )

    file_path = write_rollup(year, week, markdown, output_dir=args.output_dir)
    print(f"Rollup written to: {file_path}")


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

```bash
cd /home/devops/claude-skills/garmin
.venv/bin/python -m pytest tests/test_garmin_rollup.py -v
```

Expected: All 10 tests PASS.

**Step 5: Commit**

```bash
cd /home/devops/claude-skills
git add garmin/scripts/garmin_rollup.py garmin/tests/test_garmin_rollup.py
git commit -m "feat(garmin): add weekly rollup markdown generation"
```

---

### Task 8: SKILL.md, README, and Integration

**Files:**
- Create: `/home/devops/claude-skills/garmin/SKILL.md`
- Create: `/home/devops/claude-skills/garmin/README.md`
- Create: `/home/devops/claude-skills/garmin/references/setup.md`

**Step 1: Write SKILL.md**

Create `/home/devops/claude-skills/garmin/SKILL.md`:

```markdown
---
name: garmin
description: Use for Garmin health and fitness data - body battery, sleep, VO2 max, training load, heart rate, HRV, stress, activities. Trigger on phrases like "garmin", "body battery", "sleep score", "vo2 max", "training load", "fitness data", "pull garmin", "garmin snapshot".
---

# Garmin Health & Fitness

Query Garmin Connect for health metrics, sleep data, activities, and training status. Supports live queries and periodic markdown imports into the brain.

## Prerequisites

- Python virtual environment set up (run setup.sh if not done)
- Garmin Connect credentials configured

### First-Time Setup

```bash
# Run setup (creates venv, installs deps, configures credentials)
~/.claude/skills/garmin/scripts/setup.sh
```

## On-Demand Queries

### Today's Vitals

```bash
~/.claude/skills/garmin/.venv/bin/python ~/.claude/skills/garmin/scripts/garmin_health.py today
```

Returns: Resting HR, HRV, Body Battery, stress, steps, calories.

### Health for a Specific Date

```bash
~/.claude/skills/garmin/.venv/bin/python ~/.claude/skills/garmin/scripts/garmin_health.py 2026-02-22
~/.claude/skills/garmin/.venv/bin/python ~/.claude/skills/garmin/scripts/garmin_health.py yesterday
```

### Weekly Vitals Summary

```bash
~/.claude/skills/garmin/.venv/bin/python ~/.claude/skills/garmin/scripts/garmin_health.py week
```

Returns: 7-day table of all vitals with averages.

### Sleep Data

```bash
# Last night
~/.claude/skills/garmin/.venv/bin/python ~/.claude/skills/garmin/scripts/garmin_sleep.py

# Specific date
~/.claude/skills/garmin/.venv/bin/python ~/.claude/skills/garmin/scripts/garmin_sleep.py 2026-02-22
```

Returns: Sleep score, duration, deep/light/REM/awake breakdown.

### Recent Activities

```bash
# Last 7 days (default)
~/.claude/skills/garmin/.venv/bin/python ~/.claude/skills/garmin/scripts/garmin_activities.py 7

# Last 30 days
~/.claude/skills/garmin/.venv/bin/python ~/.claude/skills/garmin/scripts/garmin_activities.py 30
```

Returns: Activity list with HR, calories, training effect.

### Training Status

```bash
~/.claude/skills/garmin/.venv/bin/python ~/.claude/skills/garmin/scripts/garmin_activities.py training
```

Returns: VO2 max, training load, training readiness, training status.

## Periodic Imports

### Daily Snapshot

Pulls all data for a day and writes to `areas/health/garmin/YYYY-MM-DD.md`:

```bash
# Today
~/.claude/skills/garmin/.venv/bin/python ~/.claude/skills/garmin/scripts/garmin_snapshot.py

# Specific date
~/.claude/skills/garmin/.venv/bin/python ~/.claude/skills/garmin/scripts/garmin_snapshot.py 2026-02-22

# Yesterday
~/.claude/skills/garmin/.venv/bin/python ~/.claude/skills/garmin/scripts/garmin_snapshot.py yesterday
```

### Weekly Rollup

Aggregates a week of data into `areas/health/garmin/weekly/YYYY-WXX.md`:

```bash
# Current week
~/.claude/skills/garmin/.venv/bin/python ~/.claude/skills/garmin/scripts/garmin_rollup.py

# Last week
~/.claude/skills/garmin/.venv/bin/python ~/.claude/skills/garmin/scripts/garmin_rollup.py last

# Specific week
~/.claude/skills/garmin/.venv/bin/python ~/.claude/skills/garmin/scripts/garmin_rollup.py 2026-W08
```

## Workflows

### During Daily Review

1. Run snapshot to capture today's data
2. Reference key metrics in the daily review file
3. Note any anomalies or patterns

### During Weekly Review

1. Run rollup for the week
2. Compare trends against previous weeks
3. Cross-reference with training programme, TRT, CPAP data
4. Add context notes to the rollup file

### Quick Health Check

Ask: "What's my body battery?", "How did I sleep?", "Show my training status"
→ Runs the relevant on-demand query and returns formatted results.

## Error Handling

- **Auth expired:** Auto-refreshes using stored credentials
- **Wrong credentials:** Clear error message, suggests re-running setup.sh
- **No data for date:** Sections show "No data" rather than failing
- **Garmin service down:** 30s timeout with clear error
- **MFA required:** Interactive prompt (first login only)

## Test Auth

```bash
~/.claude/skills/garmin/.venv/bin/python ~/.claude/skills/garmin/scripts/garmin_client.py
```
```

**Step 2: Write README.md**

Create `/home/devops/claude-skills/garmin/README.md`:

```markdown
# Garmin Health Skill

Pull health, fitness, and training data from Garmin Connect into your second brain.

## Features

- **On-demand queries:** Body Battery, HRV, sleep, activities, training status
- **Daily snapshots:** Full day's data as a markdown file
- **Weekly rollups:** Aggregated trends and highlights

## Quick Start

```bash
# 1. Run setup
~/.claude/skills/garmin/scripts/setup.sh

# 2. Test it works
~/.claude/skills/garmin/.venv/bin/python ~/.claude/skills/garmin/scripts/garmin_client.py

# 3. Try a query
~/.claude/skills/garmin/.venv/bin/python ~/.claude/skills/garmin/scripts/garmin_health.py today
```

## Data

- Daily snapshots: `areas/health/garmin/YYYY-MM-DD.md`
- Weekly rollups: `areas/health/garmin/weekly/YYYY-WXX.md`

See SKILL.md for full command reference.
```

**Step 3: Write references/setup.md**

Create `/home/devops/claude-skills/garmin/references/setup.md`:

```markdown
# Garmin Skill Manual Setup

## Prerequisites

- Python 3.10+
- A Garmin Connect account (same one used in the Garmin Connect app)

## Steps

### 1. Create the virtual environment

```bash
cd ~/.claude/skills/garmin
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

### 2. Configure credentials

```bash
mkdir -p ~/.garmin
chmod 700 ~/.garmin
cat > ~/.garmin/config.json << 'EOF'
{
  "email": "your-garmin-email@example.com",
  "password": "your-garmin-password"
}
EOF
chmod 600 ~/.garmin/config.json
```

### 3. Test authentication

```bash
.venv/bin/python scripts/garmin_client.py
```

This should print your name from Garmin Connect. On first login, you may be prompted for an MFA code.

### 4. Create the symlink (if not already done)

```bash
ln -sf /home/devops/claude-skills/garmin ~/.claude/skills/garmin
```

## Token Storage

After first successful login, OAuth tokens are cached at `~/.garmin/tokens/`. These are valid for approximately one year. If authentication starts failing, delete the tokens directory and re-authenticate:

```bash
rm -rf ~/.garmin/tokens
.venv/bin/python scripts/garmin_client.py
```

## Troubleshooting

### "Config file not found"
Run `scripts/setup.sh` or create `~/.garmin/config.json` manually.

### "Authentication failed"
1. Check your email/password in `~/.garmin/config.json`
2. Try logging into Garmin Connect in a browser to verify credentials
3. Delete `~/.garmin/tokens/` and try again

### MFA prompt
Garmin may require MFA on first login. Enter the code when prompted. Subsequent logins use cached tokens.
```

**Step 4: Create the symlink**

```bash
ln -sf /home/devops/claude-skills/garmin ~/.claude/skills/garmin
```

**Step 5: Run the full test suite**

```bash
cd /home/devops/claude-skills/garmin
.venv/bin/python -m pytest tests/ -v
```

Expected: All tests PASS.

**Step 6: Commit**

```bash
cd /home/devops/claude-skills
git add garmin/SKILL.md garmin/README.md garmin/references/setup.md
git commit -m "feat(garmin): add SKILL.md, README, setup reference, and symlink"
```

---

### Task 9: Create tests/__init__.py and Run Full Suite

**Files:**
- Create: `/home/devops/claude-skills/garmin/tests/__init__.py`

**Step 1: Create empty __init__.py**

```bash
touch /home/devops/claude-skills/garmin/tests/__init__.py
```

**Step 2: Run the complete test suite**

```bash
cd /home/devops/claude-skills/garmin
.venv/bin/python -m pytest tests/ -v --tb=short
```

Expected: All tests across all 4 test files PASS.

**Step 3: Commit**

```bash
cd /home/devops/claude-skills
git add garmin/tests/__init__.py
git commit -m "chore(garmin): add tests init file"
```

---

### Task 10: End-to-End Verification

**Step 1: Run setup.sh (requires real Garmin credentials)**

```bash
~/.claude/skills/garmin/scripts/setup.sh
```

Expected: Prompts for email/password, installs deps, confirms authentication.

**Step 2: Test auth**

```bash
~/.claude/skills/garmin/.venv/bin/python ~/.claude/skills/garmin/scripts/garmin_client.py
```

Expected: Prints "Authenticated as: [name]".

**Step 3: Test on-demand queries**

```bash
# Today's vitals
~/.claude/skills/garmin/.venv/bin/python ~/.claude/skills/garmin/scripts/garmin_health.py today

# Sleep data
~/.claude/skills/garmin/.venv/bin/python ~/.claude/skills/garmin/scripts/garmin_sleep.py

# Activities
~/.claude/skills/garmin/.venv/bin/python ~/.claude/skills/garmin/scripts/garmin_activities.py 7

# Training status
~/.claude/skills/garmin/.venv/bin/python ~/.claude/skills/garmin/scripts/garmin_activities.py training
```

Expected: Each prints formatted data tables.

**Step 4: Test snapshot**

```bash
~/.claude/skills/garmin/.venv/bin/python ~/.claude/skills/garmin/scripts/garmin_snapshot.py
```

Expected: Creates `~/brain/areas/health/garmin/YYYY-MM-DD.md` with full daily data.

**Step 5: Test rollup**

```bash
~/.claude/skills/garmin/.venv/bin/python ~/.claude/skills/garmin/scripts/garmin_rollup.py
```

Expected: Creates `~/brain/areas/health/garmin/weekly/YYYY-WXX.md` with weekly trends.

**Step 6: Verify files exist and look correct**

```bash
ls -la ~/brain/areas/health/garmin/
cat ~/brain/areas/health/garmin/$(date +%Y-%m-%d).md
```

**Step 7: Final commit**

```bash
cd /home/devops/claude-skills
git add -A garmin/
git commit -m "feat(garmin): complete Garmin health skill with queries, snapshots, and rollups"
```
