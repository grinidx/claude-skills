<div align="center">

# 🧩 Claude and Codex Skills

**Extend [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and Codex with external service integrations and local tooling.**

[![CI](https://github.com/grinidx/claude-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/grinidx/claude-skills/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude_Code-Skills-blueviolet?logo=anthropic)](https://docs.anthropic.com/en/docs/claude-code)
[![Codex](https://img.shields.io/badge/Codex-Skills-0A66C2)]()
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20WSL-lightgrey)]()

</div>

---

## 📦 Skills

| Skill | Description |
|-------|-------------|
| ⌚ **[Garmin](./garmin/)** | Garmin Connect health & fitness data — Body Battery, HRV, sleep, activities, VO2 max, training load/readiness, daily snapshots & weekly rollups |
| 🎨 **[GPT Image 2](./gpt-image-2/)** | Generate & edit images via OpenAI's GPT Image 2 — 21 style presets, platform sizing, draft→final flow, carousels, photo edits, cost-aware |

> **Moved to their own repositories** under [github.com/dbhq-uk](https://github.com/dbhq-uk), and installable via the DBHQ marketplace (`/plugin marketplace add dbhq-uk/marketplace`):
>
> | Skill | Now lives at | Install |
> |---|---|---|
> | Outlook | [dbhq-uk/outlook-graph-skill](https://github.com/dbhq-uk/outlook-graph-skill) | `/plugin install outlook-graph@dbhq` |
> | PST to Markdown | [dbhq-uk/outlook-graph-skill](https://github.com/dbhq-uk/outlook-graph-skill) (same pack) | `/plugin install outlook-graph@dbhq` |
> | Trello | [dbhq-uk/trello-skill](https://github.com/dbhq-uk/trello-skill) | `/plugin install trello@dbhq` |
> | Deep Research | [dbhq-uk/legwork-skill](https://github.com/dbhq-uk/legwork-skill) (renamed **Legwork**) | `/plugin install legwork@dbhq` |
> | Verve | [dbhq-uk/verve-skill](https://github.com/dbhq-uk/verve-skill) (renamed from **humanize**) | `/plugin install verve@dbhq` |

## 🚀 Installation

```bash
git clone https://github.com/grinidx/claude-skills.git
cd claude-skills

# Install all skills for Claude (symlinks into ~/.claude/skills/)
./install.sh --all

# Install all skills for Codex (into ~/.codex/skills/)
./install-codex.sh --all

# Or pick specific ones
./install.sh garmin gpt-image-2
./install-codex.sh garmin gpt-image-2

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
| ⌚ Garmin | `~/.garmin/` | `garmin/scripts/setup.sh` |
| 🎨 GPT Image 2 | `$OPENAI_API_KEY` env var | `gpt-image-2/setup.sh` |

## ⚙️ Requirements

| Skill | Dependencies |
|-------|-------------|
| ⌚ Garmin | Python 3.12+ · pip (required by `garminconnect` 0.3.x) |
| 🎨 GPT Image 2 | Python 3.9+ · pip · `imagemagick` (optional) |

## 🧪 Development

Every skill has a test suite and a CI job. Nothing in CI touches the network.

```bash
ruff check . && ruff format --check .        # lint
python -m pytest tests/test_repo_hygiene.py  # frontmatter + doc-table sync
bash tests/test_install_codex.sh             # installer parity
python -m pytest <skill>/tests/              # a skill's own suite
```

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the full checklist, and
[SECURITY.md](./SECURITY.md) for how to report a vulnerability.

## 📄 License

[MIT](LICENSE)
