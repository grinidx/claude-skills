---
name: humanize
description: Rewrite AI-generated text to sound natural and human (British English). Use for humanizing text, making AI writing undetectable, rewriting to pass AI detectors. Trigger on phrases like "humanize", "make this sound human", "rewrite naturally", "humanize text", "sound more natural", "pass AI detection".
---

# Humanize Text

Rewrite AI-generated text to sound natural in **British English** while preserving meaning exactly.

## Prerequisites

- No setup for the Claude engine (default).
- For the commercial API engine: `~/.claude/skills/humanize/scripts/setup.sh`.

## Usage

Provide text inline, from a file, or from the clipboard. Options are expressed in natural language.

### Input methods

- **Inline:** "humanize this: [text]"
- **File:** "humanize the text in draft.md"
- **Clipboard:** "humanize my clipboard"

### Options

- **Tone:** neutral (default), casual, professional, academic
- **Aggressiveness:** light, moderate (default), heavy
- **Explain:** "explain what you changed" — adds a short list of patterns removed
- **Engine:** Claude (default) or "using undetectable" for the commercial API
- **Output:** conversation (default) or "save to [filename]"

### Examples

- "humanize this: The implementation of machine learning algorithms has..."
- "humanize draft.md in a casual tone"
- "humanize draft.md with heavy rewriting"
- "humanize essay.md and explain what you changed"
- "humanize report.md using undetectable"
- "humanize draft.md and save to final.md"

## British English

Default to British spelling and idiom throughout: *organise, recognise, analyse, colour, behaviour, centre, programme, whilst, learnt, amongst*. Use single quotes for inline quotation where natural. Do not change quoted material, proper nouns, code identifiers, or established American spellings inside cited sources.

## Claude Engine: Humanisation Workflow

When humanising with the Claude engine (default), follow this workflow internally and return only the final text (plus the optional explanation list if requested).

### Step 0: Triage

Read the text first. If it already reads as human-written — varied rhythm, opinions, specifics, no stock AI tells — output it unchanged with a one-line note: *"This already reads as human-written; only minor refinements applied."* Do not over-process clean text.

### Step 1: Apply tone preset

Select the tone preset from the user's instruction (default **neutral**) and keep it consistent throughout the rewrite:

- **Neutral** — clean, natural prose. No slang, no stiffness. Mild contractions allowed.
- **Casual** — contractions everywhere, shorter sentences, conversational asides (*honestly, look, the thing is*), occasional sentence fragments. First person fine.
- **Professional** — formal but not robotic. Varied but polished. Occasional first person allowed. No slang. Light hedging fine.
- **Academic** — discipline-appropriate vocabulary, longer sentences allowed but with varied structure. Cite-ready. Minimise first person.

### Step 2: Diagnose and rewrite by category

Scan the text for the patterns in **Pattern Catalogue** below. For each pattern found, rewrite the affected section using the *Before → After* style shown.

Apply aggressiveness:

- **Light** — only fix unmistakable AI tells (banned words, em-dash overuse, chatbot artefacts, curly quotes, sycophancy). Preserve original sentence structure where possible.
- **Moderate** (default) — full pattern sweep plus rhythm and voice work.
- **Heavy** — aggressive restructuring. Reorder paragraphs if it improves flow. Rewrite most sentences from scratch while preserving all meaning. Allow voice shifts, rhetorical asides.

### Step 3: Soul

Avoiding AI patterns is only half the job. Clean but voiceless writing is just as obvious as slop. Within the constraints of the selected tone preset, add:

- **Opinions.** React to facts, don't just report them. *"I'm not sure how to feel about this"* beats neutral pro/con lists.
- **Varied rhythm.** Short punchy sentences. Then longer ones that take their time getting where they're going. Mix it up.
- **Acknowledged complexity.** *"Impressive, but also a bit unsettling"* beats *"impressive"*.
- **First person when honest.** *"I keep coming back to..."* or *"what gets me is..."* signals a real person thinking.
- **A little mess.** Tangents, asides, half-formed thoughts. Perfect structure feels algorithmic.
- **Specific feelings, not abstractions.** Not *"this is concerning"* but *"something about agents churning away at 3am while nobody's watching"*.

### Step 4: Self-audit (dual prompt)

Internally, run two prompts in sequence:

1. *"What makes the below so obviously AI-generated?"* — answer briefly with the remaining tells.
2. *"Now make it not obviously AI-generated."* — revise to fix them.

Then verify hard constraints (next section) before returning.

### Hard constraints (NEVER violate)

1. All facts, numbers, names, dates survive unchanged.
2. Technical terms must not be swapped for synonyms.
3. Do not invent statistics, examples, quotes, or credentials.
4. Logical flow and argument structure must be preserved.
5. Any added illustrative example must be labelled hypothetical.
6. If a change would alter meaning, stop and ask before applying it.

### Output format

**Default:** the final humanised text only.

**If "explain" was requested:** the final text, then a short bullet list under *"Changes made"* naming the pattern categories removed (e.g. *"Removed copula avoidance"*, *"Cut chatbot artefacts"*, *"Broke uniform rhythm"*).

---

## Pattern Catalogue

Five categories. Each pattern has the tell, the problem, and a *Before → After* you should match in spirit.

### A. Content patterns

**A1. Significance inflation.** *stands as, serves as, is a testament to, pivotal, key role, evolving landscape, indelible mark, deeply rooted.* AI puffs ordinary facts into civilisational milestones.

> Before: *was established in 1989, marking a pivotal moment in the evolution of regional statistics*
> After: *was established in 1989 to collect regional statistics independently of Spain's national office*

**A2. Notability name-drops.** *cited in The New York Times, BBC, Financial Times; active social media presence; written by a leading expert.* Dropped in without context.

> Before: *Her views have been cited in the NYT, BBC, FT and The Hindu. She has 500k followers.*
> After: *In a 2024 NYT interview she argued that AI regulation should focus on outcomes, not methods.*

**A3. Superficial *-ing* analyses.** *highlighting, underscoring, emphasising, reflecting, symbolising, contributing to, fostering, showcasing.* AI tacks present participles on for fake depth.

> Before: *...resonates with the region's natural beauty, symbolising the bluebonnets, reflecting the community's deep connection to the land.*
> After: *...uses blue, green and gold; the architect chose them to reference local bluebonnets and the Gulf coast.*

**A4. Promotional / brochure language.** *nestled, vibrant, breathtaking, must-visit, stunning, rich (figurative), boasts a, in the heart of, renowned.*

> Before: *Nestled in the breathtaking region of Gonder, Alamata stands as a vibrant town with rich cultural heritage.*
> After: *Alamata is a town in the Gonder region, known for its weekly market and 18th-century church.*

**A5. Vague attribution / weasel words.** *industry reports, observers have noted, experts argue, several sources.* No actual source.

> Before: *Experts believe it plays a crucial role in the regional ecosystem.*
> After: *It supports several endemic fish species, according to a 2019 survey by the Chinese Academy of Sciences.*

**A6. Formulaic "Challenges and Future Prospects".** *Despite its... faces several challenges... Despite these challenges... continues to thrive.*

> Before: *Despite challenges typical of urban areas, Korattur continues to thrive as part of Chennai's growth.*
> After: *Traffic worsened after 2015 when three IT parks opened; the council began a drainage project in 2022.*

### B. Language and grammar

**B1. AI vocabulary.** *delve, tapestry, leverage, utilise, realm, landscape, pivotal, intricate, elucidate, harness, groundbreaking, cutting-edge, navigate, testament, ever-evolving, treasure trove, shed light, dive deep, skyrocket, revolutionise, disruptive, robust, comprehensive, holistic, paradigm, foster, garner, underscore, vibrant, valuable, key (adj), showcase, interplay.* Replace with plain words.

**B2. Copula avoidance.** AI substitutes elaborate constructions for *is/are/has*.

> Before: *Gallery 825 serves as LAAA's exhibition space. The gallery features four rooms and boasts over 3,000 sq ft.*
> After: *Gallery 825 is LAAA's exhibition space. It has four rooms totalling 3,000 sq ft.*

**B3. Negative parallelism and tailing negation.** *Not only X but Y. It's not just a song — it's a statement. The options come from the selected item, no guessing.*

> Before: *It's not just about the beat; it's part of the aggression.*
> After: *The heavy beat adds to the aggression.*

**B4. Rule of three.** Forced triplets to sound comprehensive.

> Before: *talks, panels and networking opportunities; innovation, inspiration and insight.*
> After: *talks and panels, plus informal networking between sessions.*

**B5. Elegant variation / synonym cycling.** *The protagonist... the main character... the central figure... the hero.* AI's repetition penalty forces synonyms.

> Before: *The protagonist faces challenges. The main character overcomes obstacles. The central figure triumphs. The hero returns home.*
> After: *The protagonist faces challenges but eventually triumphs and returns home.*

**B6. False ranges.** *from X to Y* where X and Y aren't on a real scale.

> Before: *from the Big Bang to the cosmic web, from the birth of stars to the dance of dark matter*
> After: *covers the Big Bang, star formation and current theories about dark matter*

**B7. Passive voice / subjectless fragments.** *No configuration needed. The results are preserved automatically.*

> Before: *No configuration file needed. The results are preserved automatically.*
> After: *You don't need a configuration file. The system preserves results automatically.*

**B8. Persuasive authority tropes.** *the real question is, at its core, fundamentally, what really matters, the heart of the matter.* Used to dress an ordinary point in extra ceremony.

> Before: *The real question is whether teams can adapt. At its core, what matters is organisational readiness.*
> After: *Whether teams can adapt depends mostly on whether the organisation is ready to change its habits.*

**B9. Hyphenated word-pair overuse.** *cross-functional, data-driven, decision-making, client-facing, end-to-end, real-time, long-term, third-party, well-known, high-quality.* AI hyphenates these with perfect consistency; humans don't.

### C. Style patterns

**C1. Em dashes.** AI uses em dashes far more than humans. Replace with commas, full stops, semicolons, or parentheses.

**C2. Boldface emphasis.** Mechanical bolding of key terms inline. Strip unless the original document genuinely uses bold (e.g. UI labels, defined terms).

**C3. Inline-header vertical lists.** Bullets that start `- **Foo:** ...`. Convert to flowing prose unless a real list is needed.

**C4. Title Case Headings.** AI capitalises every main word. Use sentence case: *## Strategic negotiations and global partnerships*.

**C5. Emojis in headings/bullets.** 🚀 💡 ✅ — remove unless the source document genuinely uses them.

**C6. Curly quotes.** Replace `"..."` and `'...'` with straight quotes unless the source document is typeset prose where curly is correct.

### D. Communication artefacts

**D1. Chatbot artefacts.** *I hope this helps! Of course! Certainly! You're absolutely right! Let me know if you'd like... Here's an overview of...* — strip entirely.

**D2. Knowledge-cutoff disclaimers.** *As of my last update, while specific details are limited, based on available information.*

**D3. Sycophantic / servile tone.** *Great question! That's an excellent point!* — delete.

**D4. Signposting.** *Let's dive in, let's explore, let's break this down, here's what you need to know, now let's look at, without further ado.* Just do the thing.

> Before: *Let's dive into how caching works in Next.js. Here's what you need to know.*
> After: *Next.js caches data at several layers: request memoisation, the data cache, and the router cache.*

**D5. Fragmented headers.** Heading followed by a one-line paragraph that just restates it.

> Before: *## Performance\n\nSpeed matters.\n\nWhen users hit a slow page they leave.*
> After: *## Performance\n\nWhen users hit a slow page they leave.*

### E. Filler and hedging

**E1. Filler phrases.**
- *in order to* → *to*
- *due to the fact that* → *because*
- *at this point in time* → *now*
- *in the event that* → *if*
- *has the ability to* → *can*
- *it is important to note that* → (delete)
- *it's worth mentioning that* → (delete)

**E2. Excessive hedging.** *It could potentially possibly be argued that the policy might have some effect.* → *The policy may affect outcomes.*

**E3. Generic positive conclusions.** *The future looks bright. Exciting times lie ahead. A major step in the right direction.* Replace with a concrete next thing, or end on the last real point.

**E4. Banned opener / closer phrases.** *In today's world, in today's digital landscape, in conclusion, in summary, in closing, at the end of the day, on the other hand, having said that, with that being said, needless to say, it goes without saying, as a matter of fact, the fact of the matter is, when it comes to.*

### Structural rhythm (apply throughout)

- Mix short punchy sentences (3-7 words) with longer flowing ones (20-30 words). Aim for high variance.
- Vary paragraph length — some single-sentence, some 4-5 sentences.
- An occasional sentence fragment for emphasis. On purpose.
- Don't start consecutive paragraphs the same way.
- Break list-like prose into flowing sentences unless a list is genuinely needed.

---

## Commercial API Engine

When the user requests *"using undetectable"*, call the API script:

```bash
~/.claude/skills/humanize/.venv/bin/python ~/.claude/skills/humanize/scripts/humanize-api.py --text "THE_TEXT_HERE"
```

For file input:

```bash
~/.claude/skills/humanize/.venv/bin/python ~/.claude/skills/humanize/scripts/humanize-api.py --file path/to/file.txt
```

The script returns humanised text to stdout. Present it to the user.
