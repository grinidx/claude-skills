#!/bin/bash

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_HOME="$(mktemp -d)"
trap 'rm -rf "$TMP_HOME"' EXIT

run_test() {
    HOME="$TMP_HOME" "$REPO_DIR/install-codex.sh" trello >/dev/null

    local target="$TMP_HOME/.codex/skills/trello"
    test -d "$target"
    test -L "$target/scripts"
    test -f "$target/SKILL.md"

    grep -q "~/.codex/skills/trello/scripts/trello-setup.sh" "$target/SKILL.md"
    if grep -q "~/.claude/skills/trello" "$target/SKILL.md"; then
        echo "expected generated Codex skill file to avoid Claude-specific paths" >&2
        return 1
    fi
}

run_test
echo "test_install_codex.sh: ok"
