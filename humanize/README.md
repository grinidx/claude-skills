# Humanize

Rewrite AI-generated text to sound natural in **British English** and pass AI detection tools (GPTZero, Turnitin, Originality.ai) while preserving meaning exactly.

## Engines

### Claude Engine (default)

Uses Claude Code's own conversation to rewrite text via a structured workflow. No extra API calls or costs.

**Workflow:**
1. **Triage** — short-circuits if text is already human.
2. **Tone preset** — neutral / casual / professional / academic, applied consistently throughout.
3. **Pattern sweep** — five categorised pattern groups (Content, Language, Style, Communication, Filler) with concrete before/after rewrites.
4. **Soul pass** — adds opinions, rhythm variance and specificity within the tone.
5. **Self-audit dual prompt** — internally asks *"what makes this obviously AI?"* then *"fix it"*.

### Undetectable AI Engine (optional)

Commercial API at ~$10/month. Submit text and receive humanised version.

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
"humanize essay.md and explain what you changed"
"humanize draft.md using undetectable"
"humanize draft.md and save to output.md"
```

## Options

| Option | Values | Default |
|--------|--------|---------|
| Tone | neutral, casual, professional, academic | neutral |
| Aggressiveness | light, moderate, heavy | moderate |
| Explain | on / off | off |
| Engine | claude, undetectable | claude |
| Output | conversation, save to file | conversation |

## Credentials

| Item | Location |
|------|----------|
| Undetectable AI key | `~/.humanize/config.json` |

## Requirements

- Claude Code subscription (for Claude engine)
- python3, requests (for commercial API engine only)
