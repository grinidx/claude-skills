# Tone presets and restoring voice

Cutting tells is half the job. Text with every tell removed and no voice left
still reads as machine-made, because nobody is behind it. This file covers the
other half.

Everything here is subordinate to the hard constraints in `SKILL.md`. Voice
comes from how existing content is expressed, never from inventing content that
was not in the source.

## Tone presets

| Preset | Contractions | First person | Second person | Fragments | Slang |
|---|---|---|---|---|---|
| Neutral | mild | sparing | fine | rare | no |
| Casual | throughout | fine | encouraged | fine | light |
| Professional | occasional | occasional | fine | rare | no |
| Academic | no | minimise | avoid | no | no |

**Neutral** (default). Clean natural prose. Neither slangy nor stiff.

**Casual.** Contractions everywhere, shorter sentences, conversational asides
(*honestly, look, the thing is*), the occasional fragment. First person is fine.
This is the one preset where discourse-marker adverbs earn their place.

**Professional.** Formal without being robotic. Varied but polished. Occasional
first person. No slang. Light hedging is fine.

**Academic.** Discipline-appropriate vocabulary. Long sentences are fine as long
as their structure varies. Cite-ready. Minimise first person, avoid second
person, and keep the passive where convention expects it.

### Where presets override the pattern rules

Several tells in `patterns.md` are tone-dependent rather than absolute:

- **Second person as the fix for false agency (B5).** Works in casual and
  neutral. In academic register, name the actor by role instead: *the authors*,
  *the review board*, *survey respondents*.
- **Narrator from a distance (B6).** A tell in essays and blog posts, normal in
  academic writing. Leave it alone under the academic preset.
- **Passive voice (B10).** Cut it in casual and neutral. In academic and much
  professional writing it is the expected register; cut only where it hides an
  actor the reader needs.
- **Hedging (E2).** Stacked hedges are always a tell. But a single hedge is
  precision in academic writing, not padding. *May* and *suggests* are load-
  bearing where the evidence is genuinely partial.
- **Fragments (C7).** Never under the academic preset.

## Restoring voice

Within the preset, work these in:

**Opinions.** React to the material, don't just relay it. *I'm not sure how to
feel about this* beats a balanced pro/con list. Only where the source already
implies a stance; do not invent a position the author did not take.

**Varied rhythm.** Short punchy sentences. Then longer ones that take their time
getting where they are going, and earn the space by carrying more than one
idea. Measure variance across the passage, not inside one paragraph.

**Acknowledged complexity.** *Impressive, but a bit unsettling* beats
*impressive*. Two-sidedness reads as someone actually thinking.

**First person where it is honest.** *I keep coming back to…* or *what gets me
is…* signals a person, subject to the preset.

**Some mess.** Tangents, asides, half-finished thoughts. Perfect structure
reads as generated. This is licence to be slightly untidy, not licence to be
unclear.

**Specific feelings over abstractions.** Not *this is concerning* but *something
about agents churning away at 3am while nobody's watching*.

**Concrete over categorical.** *Both teams that tried it hit lock contention at
around 200 writers* beats *this approach doesn't scale*. Where the source has a
specific, use it; where it doesn't, keep the general claim rather than
fabricating a number.

## What voice is not

- Not adding jokes the source did not support.
- Not adding statistics, examples or quotes. Constraint 3 has no exceptions.
- Not compressing three points into one punchy line. Punchiness that costs
  content is a failed rewrite, not a good one.
- Not swapping precise words for casual ones. *Latency* does not become
  *slowness*.
- Not stacking fragments. See `patterns.md` C7.
