<div align="center">

# 🧩 Claude and Codex Skills

**Extend [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and Codex with external service integrations and local tooling.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude_Code-Skills-blueviolet?logo=anthropic)](https://docs.anthropic.com/en/docs/claude-code)
[![Codex](https://img.shields.io/badge/Codex-Skills-0A66C2)]()
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20WSL-lightgrey)]()

</div>

---

## 📦 Skills

| Skill | Description |
|-------|-------------|
| 📨 **[PST to Markdown](./pst-to-markdown/)** | Extract Outlook PST archives into organised markdown with YAML frontmatter & integrity verification |
| ⌚ **[Garmin](./garmin/)** | Garmin Connect health & fitness data — Body Battery, HRV, sleep, activities, VO2 max, training load/readiness, daily snapshots & weekly rollups |
| ✍️ **[Humanize](./humanize/)** | Rewrite AI-generated text to sound natural in British English — 29+ AI tells across 5 categories with before/after examples, tone presets (neutral/casual/professional/academic), self-audit dual prompt, optional Undetectable AI API |
| 🎨 **[GPT Image 2](./gpt-image-2/)** | Generate & edit images via OpenAI's GPT Image 2 — 21 style presets, platform sizing, draft→final flow, carousels, photo edits, cost-aware |
| 🔬 **[Deep Research](./deep-research/)** | Multi-source web research with citation tracking and evidence persistence. Built-in WebSearch first (free); Bright Data CLI as a paid fallback for blocked pages, Reddit, and geo SERP. Brief-by-default deliverables, quick/standard/deep/ultradeep modes, mode-scaled cost, user-tunable credibility re-ranking |

> **Moved:** the **Outlook** and **Trello** skills now live in their own repositories under [github.com/dbhq-uk](https://github.com/dbhq-uk) - install them via the DBHQ marketplace (`/plugin marketplace add dbhq-uk/marketplace`) or from [dbhq-uk/outlook](https://github.com/dbhq-uk/outlook) and [dbhq-uk/trello](https://github.com/dbhq-uk/trello).

## 🚀 Installation

```bash
git clone https://github.com/grinidx/claude-skills.git
cd claude-skills

# Install all skills for Claude (symlinks into ~/.claude/skills/)
./install.sh --all

# Install all skills for Codex (into ~/.codex/skills/)
./install-codex.sh --all

# Or pick specific ones
./install.sh garmin humanize
./install-codex.sh garmin humanize

# Or interactive mode
./install.sh
./install-codex.sh
```

> Claude installs are **symlinked** — edits to this repo are immediately live in Claude Code.
> Codex installs generate `SKILL.md` files with Codex-local paths and symlink the rest of each skill directory.

Each skill's `SKILL.md` uses the same YAML-frontmatter skill format. `install.sh` installs for Claude, while `install-codex.sh` adapts the generated `SKILL.md` files for Codex on this machine.

## 🗂️ Skill Structure

All skills follow a consistent layout:

```
skill-name/
  SKILL.md            # Skill definition (YAML frontmatter + usage docs)
  README.md           # Human-readable documentation
  setup.sh            # Automated first-time setup
  scripts/            # Executable scripts
  references/         # Setup guides & manual instructions
```

## 🔐 Credentials

No secrets are stored in this repo. Each skill externalises credentials:

| Skill | Credential Location | Setup |
|-------|---------------------|-------|
| 📨 PST to Markdown | None (local only) | `pst-to-markdown/setup.sh` |
| ⌚ Garmin | `~/.garmin/` | `garmin/scripts/setup.sh` |
| ✍️ Humanize | `~/.humanize/` (optional) | `humanize/scripts/setup.sh` |
| 🎨 GPT Image 2 | `$OPENAI_API_KEY` env var | `gpt-image-2/setup.sh` |
| 🔬 Deep Research | None required. Optional: Bright Data CLI (`brightdata login`) for the fallback provider | `deep-research/setup.sh` |

## ⚙️ Requirements

| Skill | Dependencies |
|-------|-------------|
| 🔍 Repo Search | Python 3 · pip |
| 📨 PST to Markdown | Python 3 · pip · `readpst` (optional fallback) |
| 📧 Email Search | Python 3 · pip |
| 📎 Web Clipper | Python 3 · pip |
| ⌚ Garmin | Python 3 · pip |
| ✍️ Humanize | Python 3 · pip (commercial API only) |
| 🎨 GPT Image 2 | Python 3 · pip · `imagemagick` (optional) |
| 🔬 Deep Research | Python 3.9+ (stdlib only). Optional for fallback scraping: Node.js · Bright Data CLI (`npm install -g @brightdata/cli`) · Bright Data account |

## 📄 License

[MIT](LICENSE)
