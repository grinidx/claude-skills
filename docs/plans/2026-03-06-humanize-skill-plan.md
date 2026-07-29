# Humanize Skill Implementation Plan

> **Historical, and already executed.** The skill shipped as `humanize` and was
> renamed to `verve` in July 2026. Paths and names below are as they were on the
> date of writing; the current skill lives in `verve/`.

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a Claude Code skill that rewrites AI-generated text to sound natural and pass AI detectors, using Claude Code's own prompt engine or an optional commercial API.

**Architecture:** SKILL.md contains a multi-pass humanization prompt workflow that Claude Code executes directly in conversation (no API calls). An optional Python script calls Undetectable AI's REST API as an alternative engine. Config at `~/.humanize/config.json` stores the optional API key.

**Tech Stack:** Bash (setup), Python (API backend), requests (HTTP)

**Design doc:** `docs/plans/2026-03-06-humanize-skill-design.md`

---

### Task 1: Create SKILL.md with Humanization Prompt

This is the core of the skill. The SKILL.md contains the full multi-pass prompt that Claude Code follows to rewrite text.

**Files:**
- Create: `humanize/SKILL.md`

**Step 1: Create the SKILL.md file**

```markdown
---
name: humanize
description: Rewrite AI-generated text to sound natural and human. Use for humanizing text, making AI writing undetectable, rewriting to pass AI detectors. Trigger on phrases like "humanize", "make this sound human", "rewrite naturally", "humanize text", "sound more natural", "pass AI detection".
---

# Humanize Text

Rewrite AI-generated text to sound natural and pass AI detection tools while preserving meaning exactly.

## Prerequisites

- No setup required for Claude engine (default)
- For commercial API engine: run setup first

### Optional: Commercial API Setup

```bash
~/.claude/skills/humanize/scripts/setup.sh
```

## Usage

Humanize text by providing it inline, from a file, or from clipboard. Options are expressed in natural language.

### Input Methods

- **Inline:** "humanize this: [text]"
- **File:** "humanize the text in draft.md"
- **Clipboard:** "humanize my clipboard"

### Options

- **Tone:** neutral (default), casual, professional, academic
- **Aggressiveness:** light, moderate (default), heavy
- **Engine:** Claude (default) or "using undetectable" for commercial API
- **Output:** conversation (default) or "save to [filename]"

### Examples

- "humanize this: The implementation of machine learning algorithms has significantly transformed..."
- "humanize draft.md in a casual tone"
- "humanize essay.md with heavy rewriting"
- "humanize report.md using undetectable"
- "humanize draft.md and save to final.md"

## Claude Engine: Humanization Workflow

When humanizing text with the Claude engine (default), follow this exact 4-pass workflow. Execute all passes internally and return only the final result.

### Tone Presets

Apply the selected tone throughout all passes:

- **Neutral** (default): clean, natural prose. No slang, no stiffness.
- **Casual**: contractions everywhere, shorter sentences, conversational asides ("honestly", "look", "the thing is"), occasional sentence fragments.
- **Professional**: formal but not robotic. Varied but polished. Allow occasional first-person.
- **Academic**: discipline-appropriate vocabulary, longer sentences allowed but with varied structure. Cite-ready.

### Aggressiveness Levels

- **Light**: only fix obvious AI patterns (banned words, em dashes, uniform structure). Preserve original sentence structure where possible.
- **Moderate** (default): full 4-pass workflow as described below.
- **Heavy**: aggressive restructuring. Reorder paragraphs if it improves flow. Rewrite most sentences from scratch while preserving all meaning. Change voice, perspective shifts, add rhetorical questions.

### Pass 1: Structural Deconstruction (targets burstiness)

AI detectors measure "burstiness" - how much sentence length and complexity varies. AI text is uniform. Human text is jagged.

Do this:
- Break predictable paragraph patterns. Don't keep the same paragraph count if it hurts flow.
- Start mid-action or with a bold claim. Never open with a generic intro like "In today's world" or "When it comes to".
- Mix very short punchy sentences (3-7 words) with longer flowing clauses (20-30 words). Aim for high variance.
- Vary paragraph lengths. Some paragraphs should be a single sentence. Others 4-5 sentences.
- Occasionally use a sentence fragment for emphasis. On purpose.
- Break up any list-like structure into flowing prose unless the original explicitly needs to be a list.

### Pass 2: Diction & Voice (targets perplexity)

AI detectors measure "perplexity" - how predictable word choices are. AI picks the statistically most likely word. Humans are messier.

Do this:
- Replace generic adjectives ("effective", "significant", "comprehensive", "robust") with precise, domain-specific terms or concrete descriptions.
- Use subjective framing: "I've found that..." or "What works here is..." not "It has been observed that..." or "Research suggests..."
- Use conversational connectors: "Here's the thing", "So what does this actually mean?", "The short version:", "Put differently" instead of "Moreover", "Furthermore", "Additionally", "In addition".
- Use contractions naturally: "it's", "don't", "won't", "that's", "there's".
- Replace broad generalizations with specific examples or concrete scenarios.
- Occasionally address the reader directly: "you", "your", "notice how".
- Vary vocabulary - don't use the same adjective or transition twice in nearby paragraphs.

### Pass 3: Banned Patterns Purge

Scan the rewritten text and remove or replace ALL of the following. These are the most common AI-detection triggers:

**Banned words and phrases:**
delve, tapestry, leverage, utilize, realm, game-changer, unlock, embark, illuminate, unveil, pivotal, intricate, elucidate, hence, furthermore, moreover, however, harness, groundbreaking, cutting-edge, remarkable, navigate, landscape, testament, ever-evolving, shed light, dive deep, treasure trove, craft/crafting, imagine, skyrocket, revolutionize, disruptive, exciting, powerful, inquiries, remains to be seen, glimpse into, stark, certainly, probably, basically, it's important to note, it's worth mentioning, in today's world, in today's digital landscape, in today's era, in conclusion, in summary, in closing, this comprehensive guide, let's explore, not just X but also Y, when it comes to, at the end of the day, on the other hand, having said that, with that being said, needless to say, it goes without saying, as a matter of fact, the fact of the matter is, it should be noted

**Banned formatting patterns:**
- Em dashes (-) - replace with commas, periods, or semicolons
- Perfect parallel structure in consecutive sentences or paragraphs
- Consecutive paragraphs starting the same way
- Every paragraph being the same length
- Bullet points where prose would be more natural

### Pass 4: Self-Audit

Re-read the full output one final time:
- Flag and fix any remaining uniform sentence patterns (3+ consecutive sentences of similar length)
- Verify ALL facts, numbers, names, dates, and technical terms are preserved exactly from the original
- Verify no meaning was lost, added, or distorted
- Verify no statistics, examples, or credentials were invented
- If any illustrative examples were added, they must be clearly marked as hypothetical
- Check that technical terms were NOT swapped for synonyms
- Confirm the logical flow and argument structure matches the original

### Hard Constraints (NEVER violate)

1. All facts, numbers, names, dates survive unchanged
2. Technical terms must not be swapped for synonyms
3. Do not invent statistics, examples, or credentials
4. Logical flow and argument structure must be maintained
5. Any added illustrative examples must be labeled as hypothetical

## Commercial API Engine

When the user requests "using undetectable", call the API script:

```bash
~/.claude/skills/humanize/.venv/bin/python ~/.claude/skills/humanize/scripts/humanize-api.py --text "THE_TEXT_HERE"
```

For file input:
```bash
~/.claude/skills/humanize/.venv/bin/python ~/.claude/skills/humanize/scripts/humanize-api.py --file path/to/file.txt
```

The script returns humanized text to stdout. Present it to the user.
```

**Step 2: Commit**

```bash
git add humanize/SKILL.md
git commit -m "feat(humanize): add SKILL.md with multi-pass humanization prompt"
```

---

### Task 2: Create Setup Script for Commercial API

**Files:**
- Create: `humanize/scripts/setup.sh`

**Step 1: Create the setup script**

```bash
#!/bin/bash
# Set up Humanize skill: optional Undetectable AI API key + Python venv
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$SKILL_DIR/.venv"
CONFIG_DIR="$HOME/.humanize"
CONFIG_FILE="$CONFIG_DIR/config.json"

echo "=== Humanize Skill Setup ==="
echo ""
echo "The Claude engine works without any setup."
echo "This setup configures the optional Undetectable AI commercial API."

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

# --- API Key ---
mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"

if [ -f "$CONFIG_FILE" ]; then
    echo ""
    echo "Existing config found at $CONFIG_FILE"
    read -p "Overwrite? (y/N): " overwrite
    if [[ ! "$overwrite" =~ ^[Yy]$ ]]; then
        echo "Keeping existing config."
        echo ""
        echo "=== Setup Complete ==="
        exit 0
    fi
fi

echo ""
echo "Get your API key from: https://undetectable.ai/develop"
echo ""
read -p "Undetectable AI API key: " api_key

cat > "$CONFIG_FILE" <<CONF_EOF
{
  "api_key": "$api_key",
  "default_engine": "claude"
}
CONF_EOF
chmod 600 "$CONFIG_FILE"
echo "Config saved to $CONFIG_FILE"

echo ""
echo "=== Setup Complete ==="
echo "Virtual environment: $VENV_DIR"
echo "Config: $CONFIG_FILE"
echo ""
echo "Test with: ~/.claude/skills/humanize/.venv/bin/python ~/.claude/skills/humanize/scripts/humanize-api.py --text 'Hello world'"
```

**Step 2: Create requirements.txt**

Create `humanize/requirements.txt`:

```
requests>=2.28
```

**Step 3: Commit**

```bash
git add humanize/scripts/setup.sh humanize/requirements.txt
git commit -m "feat(humanize): add setup script and requirements for commercial API"
```

---

### Task 3: Create Commercial API Script

**Files:**
- Create: `humanize/scripts/humanize-api.py`

**Step 1: Create the API script**

```python
#!/usr/bin/env python3
"""Humanize text via Undetectable AI REST API."""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

CONFIG_FILE = Path.home() / ".humanize" / "config.json"
API_BASE = "https://humanize.undetectable.ai"
POLL_INTERVAL = 5
MAX_POLLS = 60


def load_config():
    if not CONFIG_FILE.exists():
        print("No config found. Run setup first:", file=sys.stderr)
        print("  ~/.claude/skills/humanize/scripts/setup.sh", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_FILE) as f:
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
    parser = argparse.ArgumentParser(description="Humanize text via Undetectable AI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="Text to humanize")
    group.add_argument("--file", help="File containing text to humanize")
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
```

**Step 2: Commit**

```bash
chmod +x humanize/scripts/humanize-api.py
git add humanize/scripts/humanize-api.py
git commit -m "feat(humanize): add Undetectable AI commercial API script"
```

---

### Task 4: Create README

**Files:**
- Create: `humanize/README.md`

**Step 1: Create README**

```markdown
# Humanize

Rewrite AI-generated text to sound natural and pass AI detection tools (GPTZero, Turnitin, Originality.ai) while preserving meaning exactly.

## Engines

### Claude Engine (default)

Uses Claude Code's own conversation to rewrite text via a multi-pass prompt workflow. No extra API calls or costs.

**4-pass process:**
1. **Structural deconstruction** - varies sentence/paragraph length to increase burstiness
2. **Diction & voice** - replaces predictable AI word choices with natural alternatives
3. **Banned patterns purge** - removes 60+ known AI-telltale words and phrases
4. **Self-audit** - verifies meaning preservation and catches remaining patterns

### Undetectable AI Engine (optional)

Commercial API at ~$10/month. Submit text and receive humanized version.

## Setup

No setup required for the Claude engine.

For the commercial API:

```bash
~/.claude/skills/humanize/scripts/setup.sh
```

You'll need an API key from [Undetectable AI](https://undetectable.ai/develop).

## Usage

```
"humanize this: [text]"
"humanize draft.md"
"humanize my clipboard"
"humanize draft.md in a casual tone"
"humanize draft.md with heavy rewriting"
"humanize draft.md using undetectable"
"humanize draft.md and save to output.md"
```

## Options

| Option | Values | Default |
|--------|--------|---------|
| Tone | neutral, casual, professional, academic | neutral |
| Aggressiveness | light, moderate, heavy | moderate |
| Engine | claude, undetectable | claude |
| Output | conversation, save to file | conversation |

## Credentials

| Item | Location |
|------|----------|
| Undetectable AI key | `~/.humanize/config.json` |

## Requirements

- Claude Code subscription (for Claude engine)
- python3, requests (for commercial API engine only)
```

**Step 2: Commit**

```bash
git add humanize/README.md
git commit -m "docs(humanize): add README"
```

---

### Task 5: Register Skill in install.sh

**Files:**
- Modify: `install.sh:19` (AVAILABLE_SKILLS array)
- Modify: `install.sh:112-118` (add check_deps_humanize function)
- Modify: `install.sh:120-133` (add case in check_deps)
- Modify: `install.sh:192-309` (add case in post_install)

**Step 1: Add "humanize" to AVAILABLE_SKILLS array**

In `install.sh` line 19, change:

```bash
AVAILABLE_SKILLS=(outlook trello repo-search pst-to-markdown email-search flaresolverr web-clipper garmin)
```

to:

```bash
AVAILABLE_SKILLS=(outlook trello repo-search pst-to-markdown email-search flaresolverr web-clipper garmin humanize)
```

**Step 2: Add check_deps_humanize function**

After the `check_deps_garmin` function (after line 118), add:

```bash
check_deps_humanize() {
    if ! command -v python3 &>/dev/null; then
        err "Missing dependency for humanize: python3"
        return 1
    fi
    return 0
}
```

**Step 3: Add case in check_deps**

In the `check_deps` case statement (around line 130), add before the `*` case:

```bash
        humanize)       check_deps_humanize ;;
```

**Step 4: Add case in post_install**

In the `post_install` case statement (before the `esac` on line 309), add:

```bash
        humanize)
            chmod +x "$REPO_DIR/humanize/scripts/setup.sh" 2>/dev/null || true
            chmod +x "$REPO_DIR/humanize/scripts/humanize-api.py" 2>/dev/null || true

            # Set up Python venv if needed
            if [ ! -d "$REPO_DIR/humanize/.venv" ]; then
                info "Setting up Python virtual environment..."
                python3 -m venv "$REPO_DIR/humanize/.venv"
                "$REPO_DIR/humanize/.venv/bin/pip" install --upgrade pip -q
                "$REPO_DIR/humanize/.venv/bin/pip" install -r "$REPO_DIR/humanize/requirements.txt" -q
            else
                ok "Python venv already exists"
                "$REPO_DIR/humanize/.venv/bin/pip" install -r "$REPO_DIR/humanize/requirements.txt" -q 2>/dev/null || true
            fi

            if [ -f "$HOME/.humanize/config.json" ]; then
                ok "Humanize API config found"
            else
                info "No commercial API configured (optional) -- run: ~/.claude/skills/humanize/scripts/setup.sh"
            fi
            ;;
```

**Step 5: Commit**

```bash
git add install.sh
git commit -m "feat(humanize): register skill in install.sh"
```

---

### Task 6: Test Installation and Skill Invocation

**Step 1: Run the installer for the humanize skill**

```bash
cd /home/dan/source/claude-skills && ./install.sh humanize
```

Expected: skill is symlinked to `~/.claude/skills/humanize`, venv created, deps installed.

**Step 2: Verify the symlink**

```bash
ls -la ~/.claude/skills/humanize
```

Expected: symlink pointing to `/home/dan/source/claude-skills/humanize`

**Step 3: Verify SKILL.md is readable**

```bash
head -5 ~/.claude/skills/humanize/SKILL.md
```

Expected: YAML frontmatter with `name: humanize`

**Step 4: Test the Claude engine by invoking the skill**

In Claude Code, say: "humanize this: The implementation of advanced machine learning algorithms has significantly transformed the landscape of modern data processing. These groundbreaking technologies leverage sophisticated neural network architectures to deliver remarkable improvements in accuracy and efficiency."

Expected: rewritten text that sounds natural, with no banned words, varied sentence lengths, meaning preserved.

**Step 5: Commit any fixes if needed**

```bash
git add -A
git commit -m "fix(humanize): address issues found during testing"
```

---

### Task 7: Final Commit and Cleanup

**Step 1: Verify all files exist**

```bash
ls -la /home/dan/source/claude-skills/humanize/
ls -la /home/dan/source/claude-skills/humanize/scripts/
```

Expected files:
- `humanize/SKILL.md`
- `humanize/README.md`
- `humanize/requirements.txt`
- `humanize/scripts/setup.sh`
- `humanize/scripts/humanize-api.py`

**Step 2: Run git status to confirm clean state**

```bash
git status
```

Expected: clean working tree or only .venv (gitignored)
