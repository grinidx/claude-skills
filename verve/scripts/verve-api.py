#!/usr/bin/env python3
"""Humanise text via Undetectable AI REST API."""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

CONFIG_FILE = Path.home() / ".verve" / "config.json"
# The skill was called `humanize` until Jul 2026. Anyone who ran the old setup
# has a key at the old path, so read it rather than making them re-enter it.
LEGACY_CONFIG_FILE = Path.home() / ".humanize" / "config.json"
API_BASE = "https://humanize.undetectable.ai"
POLL_INTERVAL = 5
MAX_POLLS = 60


def config_path():
    if CONFIG_FILE.exists():
        return CONFIG_FILE
    if LEGACY_CONFIG_FILE.exists():
        return LEGACY_CONFIG_FILE
    return CONFIG_FILE


def load_config():
    path = config_path()
    if not path.exists():
        print("No config found. Run setup first:", file=sys.stderr)
        print("  ~/.claude/skills/verve/scripts/setup.sh", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def submit_text(api_key, text):
    resp = requests.post(
        f"{API_BASE}/submit",
        headers={"apikey": api_key, "Content-Type": "application/json"},
        json={"content": text},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    doc_id = data.get("id")
    if not doc_id:
        print(f"Unexpected response: {data}", file=sys.stderr)
        sys.exit(1)
    return doc_id


def poll_result(api_key, doc_id):
    for _ in range(MAX_POLLS):
        resp = requests.post(
            f"{API_BASE}/document",
            headers={"apikey": api_key, "Content-Type": "application/json"},
            json={"id": doc_id},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        if status == "done":
            return data.get("output", "")
        if status == "error":
            print(f"API error: {data}", file=sys.stderr)
            sys.exit(1)
        time.sleep(POLL_INTERVAL)
    print("Timed out waiting for result", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Humanise text via Undetectable AI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="Text to humanise")
    group.add_argument("--file", help="File containing text to humanise")
    args = parser.parse_args()

    config = load_config()
    api_key = config.get("api_key")
    if not api_key:
        print("No API key in config. Run setup first.", file=sys.stderr)
        sys.exit(1)

    if args.file:
        text = Path(args.file).read_text()
    else:
        text = args.text

    if not text.strip():
        print("No text provided", file=sys.stderr)
        sys.exit(1)

    print("Submitting to Undetectable AI...", file=sys.stderr)
    doc_id = submit_text(api_key, text)
    print(f"Document ID: {doc_id}, polling for result...", file=sys.stderr)
    result = poll_result(api_key, doc_id)
    print(result)


if __name__ == "__main__":
    main()
