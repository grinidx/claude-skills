# Verve

Strip AI tells from prose and put a human voice back, in **British English**,
without changing what the text says.

> Renamed from `humanize` in July 2026. The skill still triggers on
> "humanise this" and "make this sound human"; only the directory, the
> credentials path and the script name changed.

## Why two halves

Removing AI tells gets you clean prose that still reads as machine-made,
because nothing is behind it. So the workflow does both: a pattern sweep that
cuts the tells, then a voice pass that puts opinions, rhythm and specificity
back, inside whatever tone you asked for.

The constraint that governs everything: meaning does not change. No invented
statistics, no dropped claims, no compressing three points into one punchy
line.

## Engines

### Claude engine (default)

Runs in the conversation. No extra API calls, no cost.

1. **Triage** — returns already-human text unchanged rather than mangling it.
2. **Tone** — neutral / casual / professional / academic, held throughout.
3. **Pattern sweep** — five groups of tells (content, language, style,
   assistant artefacts, filler) with before/after for each.
4. **Voice pass** — opinions, rhythm variance, specificity, within the tone.
5. **Quick checks** — a 14-item pre-flight list.
6. **Score** — six dimensions, with Fidelity as a veto rather than an average.

### Undetectable AI engine (optional)

Commercial API, around $10/month. Submit text, get a humanised version back.

## Setup

Nothing to do for the Claude engine.

For the commercial API:

```bash
~/.claude/skills/verve/scripts/setup.sh
```

You'll need a key from [Undetectable AI](https://undetectable.ai/develop). If
you set the skill up under its old name, setup offers to copy your existing key
across, and the script reads the old path either way.

## Usage

```
"verve this: [text]"
"verve draft.md"
"verve my clipboard"
"verve draft.md in a casual tone"
"verve draft.md with heavy rewriting"
"verve essay.md and explain what you changed"
"verve draft.md using undetectable"
"verve draft.md and save to output.md"
```

## Options

| Option | Values | Default |
|--------|--------|---------|
| Tone | neutral, casual, professional, academic | neutral |
| Strength | light, moderate, heavy | moderate |
| Explain | on / off | off |
| Engine | claude, undetectable | claude |
| Output | conversation, save to file | conversation |

## Structure

```
verve/
├── SKILL.md                    # Workflow, constraints, quick checks, scoring
├── references/
│   ├── patterns.md             # The tell catalogue, before/after for each
│   ├── wordlist.md             # Flat scannable word and phrase lists
│   ├── voice.md                # Tone presets and restoring voice
│   └── examples.md             # Worked passages
├── scripts/
│   ├── setup.sh
│   └── verve-api.py            # Optional Undetectable AI engine
└── tests/
```

## Credentials

| Item | Location |
|------|----------|
| Undetectable AI key | `~/.verve/config.json` (falls back to `~/.humanize/config.json`) |

## Requirements

- Claude Code subscription (for the Claude engine)
- python3, requests (commercial API engine only)

## Acknowledgements

Several patterns — false agency, vague declaratives, narrator-from-a-distance,
meta-commentary, emphasis crutches, telling-instead-of-showing — and the idea of
a scored exit gate come from [stop-slop](https://github.com/hardikpandya/stop-slop)
by Hardik Pandya (MIT).
