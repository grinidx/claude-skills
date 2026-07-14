"""Tests for garmin_client.py - auth and session management."""

import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from garmin_client import get_client, load_config, GarminConfigError


class TestLoadConfig:
    """Test credential loading from ~/.garmin/config.json."""

    def test_loads_valid_config(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "email": "test@example.com",
            "password": "secret123"
        }))
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
        # Create a dummy file so iterdir() finds something
        (token_dir / "oauth_token").write_text("dummy")

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
        (token_dir / "oauth_token").write_text("dummy")

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
        # Don't create it - get_client should

        mock_garmin = MagicMock()
        mock_garmin.login.return_value = ("", "")
        mock_garmin.garth = MagicMock()
        MockGarmin.return_value = mock_garmin

        config = {"email": "test@example.com", "password": "secret123"}
        get_client(config, token_dir=str(token_dir))

        assert token_dir.exists()


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
    (token_dir / "oauth2_token.json").write_text(
        json.dumps({"refresh_token_expires_at": expires_at})
    )


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
