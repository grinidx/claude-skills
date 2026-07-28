#!/usr/bin/env python3
"""Tests for humanize-api.py — the optional Undetectable AI engine.

No network and no waiting: requests.post and time.sleep are both patched, so the
timeout case exercises all MAX_POLLS iterations in microseconds rather than the
five real minutes it would otherwise take.

The script's filename is hyphenated, so it cannot be imported by name; it gets
loaded from its path instead.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SCRIPT = Path(__file__).parent.parent / "scripts" / "humanize-api.py"

_spec = importlib.util.spec_from_file_location("humanize_api", SCRIPT)
humanize_api = importlib.util.module_from_spec(_spec)
sys.modules["humanize_api"] = humanize_api
_spec.loader.exec_module(humanize_api)


def response(payload: dict, status: int = 200) -> MagicMock:
    """A stand-in for a requests.Response that raise_for_status() accepts."""
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


def failing_response(exc: Exception) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.side_effect = exc
    return resp


class TestLoadConfig(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._saved = humanize_api.CONFIG_FILE
        humanize_api.CONFIG_FILE = Path(self.tmp.name) / "config.json"

    def tearDown(self):
        humanize_api.CONFIG_FILE = self._saved
        self.tmp.cleanup()

    def test_missing_config_exits_one(self):
        with self.assertRaises(SystemExit) as ctx:
            humanize_api.load_config()
        self.assertEqual(ctx.exception.code, 1)

    def test_reads_an_existing_config(self):
        humanize_api.CONFIG_FILE.write_text(json.dumps({"api_key": "secret"}))
        self.assertEqual(humanize_api.load_config(), {"api_key": "secret"})

    def test_config_without_api_key_still_loads(self):
        # load_config only reads; main() is what rejects a keyless config.
        humanize_api.CONFIG_FILE.write_text(json.dumps({"other": "value"}))
        self.assertEqual(humanize_api.load_config(), {"other": "value"})


class TestSubmitText(unittest.TestCase):

    def test_posts_to_submit_with_key_and_content(self):
        with patch.object(humanize_api.requests, "post",
                          return_value=response({"id": "doc-123"})) as post:
            doc_id = humanize_api.submit_text("my-key", "some text")

        self.assertEqual(doc_id, "doc-123")
        args, kwargs = post.call_args
        self.assertEqual(args[0], f"{humanize_api.API_BASE}/submit")
        self.assertEqual(kwargs["headers"]["apikey"], "my-key")
        self.assertEqual(kwargs["json"], {"content": "some text"})

    def test_sends_a_timeout(self):
        # A request without a timeout can hang the skill indefinitely.
        with patch.object(humanize_api.requests, "post",
                          return_value=response({"id": "doc-123"})) as post:
            humanize_api.submit_text("my-key", "text")
        self.assertIn("timeout", post.call_args.kwargs)

    def test_response_without_id_exits_one(self):
        with patch.object(humanize_api.requests, "post",
                          return_value=response({"error": "bad request"})):
            with self.assertRaises(SystemExit) as ctx:
                humanize_api.submit_text("my-key", "text")
        self.assertEqual(ctx.exception.code, 1)

    def test_empty_id_is_treated_as_missing(self):
        with patch.object(humanize_api.requests, "post",
                          return_value=response({"id": ""})):
            with self.assertRaises(SystemExit):
                humanize_api.submit_text("my-key", "text")

    def test_http_error_propagates(self):
        error = RuntimeError("401 Unauthorized")
        with patch.object(humanize_api.requests, "post",
                          return_value=failing_response(error)):
            with self.assertRaises(RuntimeError):
                humanize_api.submit_text("bad-key", "text")


class TestPollResult(unittest.TestCase):

    def test_returns_output_when_done(self):
        with patch.object(humanize_api.requests, "post",
                          return_value=response({"status": "done", "output": "humanised"})), \
             patch.object(humanize_api.time, "sleep") as sleep:
            self.assertEqual(humanize_api.poll_result("k", "doc-1"), "humanised")
        sleep.assert_not_called()

    def test_polls_until_done(self):
        pending = response({"status": "pending"})
        done = response({"status": "done", "output": "final"})
        with patch.object(humanize_api.requests, "post",
                          side_effect=[pending, pending, done]) as post, \
             patch.object(humanize_api.time, "sleep") as sleep:
            self.assertEqual(humanize_api.poll_result("k", "doc-1"), "final")
        self.assertEqual(post.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_posts_the_document_id(self):
        with patch.object(humanize_api.requests, "post",
                          return_value=response({"status": "done", "output": "x"})) as post, \
             patch.object(humanize_api.time, "sleep"):
            humanize_api.poll_result("my-key", "doc-77")
        args, kwargs = post.call_args
        self.assertEqual(args[0], f"{humanize_api.API_BASE}/document")
        self.assertEqual(kwargs["json"], {"id": "doc-77"})
        self.assertEqual(kwargs["headers"]["apikey"], "my-key")

    def test_done_without_output_returns_empty_string(self):
        with patch.object(humanize_api.requests, "post",
                          return_value=response({"status": "done"})), \
             patch.object(humanize_api.time, "sleep"):
            self.assertEqual(humanize_api.poll_result("k", "doc-1"), "")

    def test_error_status_exits_one(self):
        with patch.object(humanize_api.requests, "post",
                          return_value=response({"status": "error", "message": "nope"})), \
             patch.object(humanize_api.time, "sleep"):
            with self.assertRaises(SystemExit) as ctx:
                humanize_api.poll_result("k", "doc-1")
        self.assertEqual(ctx.exception.code, 1)

    def test_gives_up_after_max_polls(self):
        with patch.object(humanize_api.requests, "post",
                          return_value=response({"status": "pending"})) as post, \
             patch.object(humanize_api.time, "sleep"):
            with self.assertRaises(SystemExit) as ctx:
                humanize_api.poll_result("k", "doc-1")
        self.assertEqual(ctx.exception.code, 1)
        self.assertEqual(post.call_count, humanize_api.MAX_POLLS)

    def test_sleeps_the_configured_interval(self):
        pending = response({"status": "pending"})
        done = response({"status": "done", "output": "x"})
        with patch.object(humanize_api.requests, "post", side_effect=[pending, done]), \
             patch.object(humanize_api.time, "sleep") as sleep:
            humanize_api.poll_result("k", "doc-1")
        sleep.assert_called_once_with(humanize_api.POLL_INTERVAL)


class TestMain(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self._saved = humanize_api.CONFIG_FILE
        humanize_api.CONFIG_FILE = self.root / "config.json"

    def tearDown(self):
        humanize_api.CONFIG_FILE = self._saved
        self.tmp.cleanup()

    def write_config(self, payload: dict):
        humanize_api.CONFIG_FILE.write_text(json.dumps(payload))

    def run_main(self, *argv: str):
        with patch.object(sys, "argv", ["humanize-api.py", *argv]):
            humanize_api.main()

    def test_config_without_api_key_exits_one(self):
        self.write_config({"other": "value"})
        with self.assertRaises(SystemExit) as ctx:
            self.run_main("--text", "hello")
        self.assertEqual(ctx.exception.code, 1)

    def test_whitespace_only_text_exits_one(self):
        self.write_config({"api_key": "k"})
        with self.assertRaises(SystemExit) as ctx:
            self.run_main("--text", "   \n  ")
        self.assertEqual(ctx.exception.code, 1)

    def test_text_and_file_are_mutually_exclusive(self):
        self.write_config({"api_key": "k"})
        with self.assertRaises(SystemExit) as ctx:
            self.run_main("--text", "hello", "--file", "x.txt")
        self.assertNotEqual(ctx.exception.code, 0)

    def test_one_of_text_or_file_is_required(self):
        self.write_config({"api_key": "k"})
        with self.assertRaises(SystemExit) as ctx:
            self.run_main()
        self.assertNotEqual(ctx.exception.code, 0)

    def test_file_input_is_read_and_submitted(self):
        self.write_config({"api_key": "k"})
        source = self.root / "input.txt"
        source.write_text("text from a file")

        with patch.object(humanize_api.requests, "post") as post, \
             patch.object(humanize_api.time, "sleep"):
            post.side_effect = [
                response({"id": "doc-9"}),
                response({"status": "done", "output": "humanised"}),
            ]
            self.run_main("--file", str(source))

        submit_kwargs = post.call_args_list[0].kwargs
        self.assertEqual(submit_kwargs["json"], {"content": "text from a file"})


if __name__ == "__main__":
    unittest.main()
