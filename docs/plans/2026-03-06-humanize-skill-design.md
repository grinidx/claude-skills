# Humanize Skill Design

> **Historical.** The skill shipped as `humanize` and was renamed to `verve` in
> July 2026. Paths and names below are as they were on the date of writing; the
> skill now lives in its own repo at [dbhq-uk/verve-skill](https://github.com/dbhq-uk/verve-skill).

**Date:** 2026-03-06
**Status:** Approved

## Goal

Create a Claude Code skill that rewrites AI-generated text to sound natural and pass AI detection tools (GPTZero, Turnitin, Originality.ai) while preserving meaning exactly.

## Requirements

- **Primary engine**: Claude Code prompt-driven — uses existing subscription, no extra API calls
- **Optional engine**: Pluggable commercial API (Undetectable AI initially) via Python script
- **Input**: file, inline text, or clipboard; any length (short paragraphs to 5,000+ word articles)
- **Output**: humanized text in conversation or saved to file
- **Hard constraint**: all facts, numbers, names, dates, and technical terms preserved exactly

## Architecture

### Claude Code Engine (Primary)

The SKILL.md contains a multi-pass humanization prompt workflow. When invoked, Claude Code follows the instructions to rewrite text directly in conversation. No scripts or API calls needed.

**4-pass workflow:**

1. **Pass 1 — Structural deconstruction** (targets burstiness):
   - Break predictable paragraph patterns
   - Start mid-action or with a bold statement, not a generic intro
   - Mix very short punchy sentences with longer flowing clauses
   - Vary paragraph lengths — some 1-sentence, some 4-5 sentences
   - Don't preserve original paragraph count if it harms flow

2. **Pass 2 — Diction & voice** (targets perplexity):
   - Replace generic adjectives ("effective", "significant") with precise, domain-specific terms
   - Use subjective voice — "I've found that..." not "It has been observed that..."
   - Use conversational connectors ("Here's the thing", "So what does this mean?") instead of formal transitions
   - Use contractions naturally
   - Replace broad generalizations with specific examples

3. **Pass 3 — Banned patterns purge**:
   - 60+ banned words/phrases: delve, tapestry, leverage, utilize, realm, game-changer, unlock, embark, illuminate, unveil, pivotal, intricate, elucidate, hence, furthermore, moreover, however, harness, groundbreaking, cutting-edge, remarkable, navigate, landscape, testament, ever-evolving, in today's world, it's important to note, in conclusion, shed light, dive deep, treasure trove, not just...but also, craft/crafting, imagine, skyrocket, revolutionize, disruptive, exciting, powerful, inquiries, ever-evolving, remains to be seen, glimpse into, stark, in summary, certainly, probably, basically
   - Ban em dashes (—), excessive markdown formatting, perfect parallel structure
   - Ban common setup language ("In conclusion", "In closing")
   - Ban constructions like "not just X, but also Y"

4. **Pass 4 — Self-audit**:
   - Re-read and flag any remaining uniform sentence patterns
   - Check that all facts/numbers/technical terms are preserved exactly
   - Verify no meaning was lost or invented
   - Any added illustrative examples must be labeled as hypothetical

### Commercial API Engine (Optional)

Python script calls Undetectable AI REST API:
- Submit text → poll for result (~10s processing)
- Print humanized text to stdout
- Requires API key stored in `~/.humanize/config.json`

### Tone Presets

- **Neutral** (default): clean, natural prose
- **Casual**: contractions, shorter sentences, conversational asides
- **Professional**: formal but not stiff, varied but polished
- **Academic**: discipline-appropriate vocabulary, longer sentences allowed but varied

### Aggressiveness Levels

- **Light**: minimal changes, just fix obvious AI patterns
- **Moderate** (default): full 4-pass workflow
- **Heavy**: aggressive restructuring, significant sentence-level rewrites

## Interface

```
# From a file
"humanize the text in draft.md"

# Inline text
"humanize this: [paste text]"

# From clipboard
"humanize my clipboard"

# With options
"humanize draft.md in a casual tone"
"humanize draft.md with heavy rewriting"
"humanize draft.md using undetectable"
"humanize draft.md and save to output.md"
```

Natural language flags:
- **Engine**: defaults to Claude Code prompt; say "using undetectable" for commercial API
- **Tone**: defaults to neutral; request "casual", "professional", or "academic"
- **Aggressiveness**: defaults to moderate; request "light touch" or "heavy rewrite"
- **Output**: prints to conversation by default; say "save to file" to write output

## File Structure

```
humanize/
  SKILL.md              # Skill definition with full humanization prompt
  README.md             # Human-readable docs
  setup.sh              # Configure commercial API key (optional)
  scripts/
    setup.sh            # Interactive setup for Undetectable AI key
    humanize-api.py     # Commercial API backend
  requirements.txt      # requests
  .venv/                # Python venv (gitignored)
```

## Config

`~/.humanize/config.json` (only created if commercial API is set up):

```json
{
  "api_key": "undetectable-ai-api-key",
  "default_engine": "claude"
}
```

## Meaning Preservation Rules (Hard Constraints)

- All facts, numbers, names, dates, technical terms survive unchanged
- Do not invent statistics, examples, or credentials
- Any added illustrative examples must be labeled as hypothetical
- Logical flow and argument structure must be maintained
- Technical terms must not be swapped for synonyms

## Research Sources

- [Best AI Prompt to Humanize AI Writing](https://www.sabrina.dev/p/best-ai-prompt-to-humanize-ai-writing) — 60+ banned word list, style constraints
- [5 Prompts That Make AI Write Like a Human](https://www.eesel.ai/blog/prompts-that-make-ai-write-like-a-human) — role-based, storytelling, emotion techniques
- [How AI Detectors Work (GPTZero)](https://gptzero.me/news/how-ai-detectors-work/) — perplexity, burstiness, scoring
- [Humanize AI Prompt Templates](https://ainaturalwrite.com/blog/humanize-ai-prompt-templates) — structural deconstruction, semantic nuance
- [Undetectable AI Developer API](https://docs.undetectable.ai/) — commercial API docs
