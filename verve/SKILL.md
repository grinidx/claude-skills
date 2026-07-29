---
name: verve
description: Strip AI tells from prose and put a human voice back (British English). Use for humanising AI-generated text, removing AI writing patterns, making drafts sound like a person wrote them. Trigger on phrases like "verve", "give this verve", "humanise", "humanize", "make this sound human", "rewrite naturally", "remove AI tells", "deslop this", "sound more natural", "pass AI detection".
---

# Verve

Cut the AI tells from a piece of writing, then put a voice back into it, in
**British English**, without changing what it says.

Both halves matter. Text with the tells stripped but no voice left reads as
machine-made too, just blandly rather than floridly.

## Prerequisites

- Nothing to set up for the Claude engine (the default).
- Commercial API engine only: `~/.claude/skills/verve/scripts/setup.sh`.

## Usage

Text comes from the message, a file, or the clipboard. Options are natural
language.

- **Inline:** "verve this: [text]"
- **File:** "verve draft.md"
- **Clipboard:** "verve my clipboard"

| Option | Values | Default |
|---|---|---|
| Tone | neutral, casual, professional, academic | neutral |
| Strength | light, moderate, heavy | moderate |
| Explain | "explain what you changed" | off |
| Engine | claude, "using undetectable" | claude |
| Output | conversation, "save to [file]" | conversation |

Examples: *"verve draft.md in a casual tone"*, *"verve essay.md heavily and
explain what you changed"*, *"verve report.md using undetectable"*.

## Hard constraints (never violate)

These outrank every other instruction in this skill. A rewrite that breaks one
of them has failed, however good it reads.

1. Every fact, number, name, date and citation survives unchanged.
2. Technical terms keep their exact wording. No synonym swaps.
3. Never invent statistics, examples, quotes, sources or credentials.
4. The argument keeps its logical structure and its claims. Cutting filler is
   the job; cutting content is not.
5. Any illustrative example you add is labelled hypothetical.
6. If a change would alter meaning, stop and ask instead of applying it.

Rule 4 is the one that gets broken most often. Aggressive de-slopping tempts you
to compress three real points into one punchy line. That is a rewrite, not a
humanisation.

## Workflow

### 0. Triage

Read it first. If it already reads as human-written (varied rhythm, opinions,
specifics, no stock tells), return it unchanged with one line: *"This already
reads as human-written; only minor refinements applied."* Do not process clean
text for the sake of processing it.

### 1. Set the tone

Pick from the user's instruction, default **neutral**, and hold it throughout.
Presets and what each one permits: `references/voice.md`.

### 2. Sweep for tells

Work through `references/patterns.md` (structural and content tells, with
before/after for each) and `references/wordlist.md` (flat lists you can scan for
directly). Strength dial:

- **Light** — unmistakable tells only: banned words, em dashes, chatbot
  artefacts, curly quotes, sycophancy. Keep sentence structure.
- **Moderate** (default) — full sweep, plus rhythm and voice work.
- **Heavy** — restructure freely, reorder paragraphs, rewrite most sentences
  from scratch. Constraints 1-6 still apply, without exception.

### 3. Put the voice back

Opinions, rhythm variance, specificity, acknowledged complexity, a bit of mess.
Within the tone preset. See `references/voice.md`.

### 4. Quick checks

Run this list against the draft before scoring:

- Adverb doing no work (really, just, literally, genuinely, simply, actually)? Cut.
- Passive voice? Find the actor and put them at the front.
- Inanimate subject with a human verb ("the decision emerges", "the data tells us")? Name who acted.
- "Not X, it's Y" contrast? State Y and drop the negation.
- Throat-clearing ("Here's the thing", "It turns out", "The truth is")? Cut to the point.
- Vague declarative ("The implications are significant")? Name the specific implication.
- A sentence announcing difficulty or importance instead of showing it? Show it or cut it.
- Three consecutive sentences of similar length? Break one.
- Stacked fragments ("X. And Y. And Z." / "That's it. That's the thing.")? Collapse them.
- Every paragraph ending on a punchy one-liner? Vary the endings.
- Em dash anywhere? Replace with a comma, full stop, semicolon or brackets.
- Meta-commentary about the piece's own structure ("In this section we'll…")? Delete.
- Lazy extreme (every, always, never, nobody) standing in for a specific? Replace it.
- Rule of three where two items would do? Cut one.

### 5. Score, then stop or revise

Rate the result 1-10 on each dimension:

| Dimension | Question |
|---|---|
| Fidelity | Does it still say exactly what the original said? |
| Directness | Statements, or announcements of statements? |
| Rhythm | Varied, or metronomic? |
| Voice | Is anyone recognisably behind this? |
| Trust | Does it respect the reader's intelligence? |
| Density | Anything left that could be cut? |

**Fidelity is a veto, not an average.** Below 9, revise regardless of the
total, because the failure is a changed meaning rather than a stylistic one.
Otherwise, below 40/60 revise; at or above, deliver.

## Output

**Default:** the humanised text, nothing else.

**With "explain":** the text, then a short *Changes made* list naming the tells
removed (e.g. *"Cut false agency"*, *"Broke uniform rhythm"*, *"Removed copula
avoidance"*).

## References

| File | Contents |
|---|---|
| `references/patterns.md` | The tell catalogue: content, language, style, artefacts, filler. Before/after for each. |
| `references/wordlist.md` | Flat scannable lists: AI vocabulary, jargon, filler phrases, adverbs, banned openers and closers. |
| `references/voice.md` | Tone presets in full, and how to restore voice without inventing content. |
| `references/examples.md` | Worked passages, before and after. |

## Commercial API engine

When the user asks for *"using undetectable"*:

```bash
~/.claude/skills/verve/.venv/bin/python ~/.claude/skills/verve/scripts/verve-api.py --text "THE_TEXT_HERE"
```

File input uses `--file path/to/file.txt`. The script writes the humanised text
to stdout; present that to the user.
