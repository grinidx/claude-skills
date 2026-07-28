#!/bin/bash
# Tests for install-codex.sh.
#
# The interesting failure this guards against is drift, not breakage: a skill
# gets added to install.sh and the Codex installer is forgotten, so the skill is
# silently uninstallable for Codex users. gpt-image-2 and deep-research sat in
# exactly that state. Most assertions here are therefore static parity checks
# across the two installers, plus one real install to prove the generated
# SKILL.md actually gets Codex paths.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_HOME="$(mktemp -d)"
trap 'rm -rf "$TMP_HOME"' EXIT

FAILURES=0

fail() {
    echo "  FAIL: $*" >&2
    FAILURES=$((FAILURES + 1))
}

# Read the AVAILABLE_SKILLS array literal out of an installer without sourcing
# it (sourcing would run the whole installer).
skills_of() {
    sed -n 's/^AVAILABLE_SKILLS=(\(.*\))[[:space:]]*$/\1/p' "$1" | tr ' ' '\n' | sort
}

# Print the body of a shell function so we can assert a case arm exists in it.
function_body() {
    awk -v fn="$1" '
        $0 ~ "^" fn "\\(\\) \\{" { inside = 1; next }
        inside && /^\}/          { exit }
        inside                   { print }
    ' "$2"
}

has_case_arm() {
    grep -qE "^[[:space:]]*$1\)" <<<"$2"
}

echo "install-codex.sh: skill parity with install.sh"
claude_skills="$(skills_of "$REPO_DIR/install.sh")"
codex_skills="$(skills_of "$REPO_DIR/install-codex.sh")"

if [ "$claude_skills" != "$codex_skills" ]; then
    fail "AVAILABLE_SKILLS differ between installers"
    diff <(echo "$claude_skills") <(echo "$codex_skills") \
        --label install.sh --label install-codex.sh -u >&2 || true
fi

echo "install-codex.sh: every skill in the repo is offered by both installers"
for skill_md in "$REPO_DIR"/*/SKILL.md; do
    [ -e "$skill_md" ] || continue
    skill="$(basename "$(dirname "$skill_md")")"
    grep -qx "$skill" <<<"$claude_skills" || fail "$skill missing from install.sh AVAILABLE_SKILLS"
    grep -qx "$skill" <<<"$codex_skills"  || fail "$skill missing from install-codex.sh AVAILABLE_SKILLS"
done

echo "install-codex.sh: every offered skill has dependency and post-install handling"
codex_check_deps="$(function_body check_deps "$REPO_DIR/install-codex.sh")"
codex_post_install="$(function_body post_install "$REPO_DIR/install-codex.sh")"

while read -r skill; do
    [ -n "$skill" ] || continue
    has_case_arm "$skill" "$codex_check_deps" \
        || fail "$skill has no check_deps case in install-codex.sh"
    has_case_arm "$skill" "$codex_post_install" \
        || fail "$skill has no post_install case in install-codex.sh"
done <<<"$codex_skills"

echo "install-codex.sh: installs a skill with Codex-local paths"
# deep-research is the cheap end-to-end case: its requirements.txt is empty by
# design (stdlib only), so post_install costs a venv and nothing else.
if ! HOME="$TMP_HOME" "$REPO_DIR/install-codex.sh" deep-research >/dev/null; then
    fail "installer exited non-zero for deep-research"
fi

target="$TMP_HOME/.codex/skills/deep-research"
[ -d "$target" ]           || fail "expected $target to exist"
[ -L "$target/scripts" ]   || fail "expected $target/scripts to be a symlink into the repo"
[ -f "$target/SKILL.md" ]  || fail "expected a generated SKILL.md"

# SKILL.md must be generated (a real file), never a symlink to the Claude-path
# original -- that is the whole point of the Codex install.
[ ! -L "$target/SKILL.md" ] || fail "SKILL.md must be generated, not symlinked"

if grep -q "~/.claude/skills/" "$target/SKILL.md"; then
    fail "generated SKILL.md still contains Claude-specific paths"
fi
grep -q "~/.codex/skills/deep-research" "$target/SKILL.md" \
    || fail "generated SKILL.md has no rewritten Codex path"

echo "install-codex.sh: rejects an unknown skill"
if HOME="$TMP_HOME" "$REPO_DIR/install-codex.sh" definitely-not-a-skill >/dev/null 2>&1; then
    fail "installer accepted an unknown skill"
fi

if [ "$FAILURES" -ne 0 ]; then
    echo "test_install_codex.sh: $FAILURES failure(s)" >&2
    exit 1
fi

echo "test_install_codex.sh: ok"
