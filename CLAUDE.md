# Claude and Codex Skills

A collection of skills that extend Claude and Codex with external service integrations and local tooling.

## Repository Structure

```
claude-skills/
├── pst-to-markdown/  # PST to markdown extraction (Python)
├── garmin/           # Garmin Connect health & fitness data (Python/garminconnect)
├── humanize/         # Humanize AI-generated text (prompt-driven + optional API)
├── gpt-image-2/      # OpenAI GPT Image 2 generation & editing (Python)
├── deep-research/    # Multi-source web research (built-in WebSearch first, Bright Data fallback)
├── install.sh        # Claude installer (symlinks into ~/.claude/skills)
├── install-codex.sh  # Codex installer (installs into ~/.codex/skills)
├── .github/workflows/ci.yml  # CI: deep-research tests (py3.9-3.13) + e2e smoke
└── README.md         # User-facing documentation
```

> **Moved:** the `outlook` and `trello` skills now live in their own repos under [github.com/dbhq-uk](https://github.com/dbhq-uk) (extracted Jul 2026).

## Skill Anatomy

Every skill follows the same layout:

```
skill-name/
  SKILL.md            # Skill definition — YAML frontmatter + usage instructions
  README.md           # Human-readable docs
  setup.sh            # Automated first-time setup
  scripts/            # Executable scripts called by SKILL.md
  references/         # Setup guides, manual instructions
```

- `SKILL.md` is the file the skill host discovers and loads. It must have YAML frontmatter with `name` and `description`.
- Claude installs are symlinked from this repo into `~/.claude/skills/` via `install.sh`.
- Codex installs go into `~/.codex/skills/` via `install-codex.sh`, with generated `SKILL.md` files that rewrite Claude-style paths for Codex.

## Working on Skills

### Adding a New Skill

1. Create a directory with `SKILL.md`, `setup.sh`, `scripts/`, and `README.md`
2. Add the skill name to `AVAILABLE_SKILLS` in both `install.sh` and `install-codex.sh`
3. Add a `check_deps_<skill>()` function and `post_install` case in both installers
4. Add the skill to the README tables (skills list, credentials, requirements)
5. Test with `./install.sh <skill-name>` and `./install-codex.sh <skill-name>`

### Modifying an Existing Skill

- The source `SKILL.md` is used directly by Claude and transformed for Codex at install time
- Test changes by invoking the skill in Claude Code and reinstalling for Codex after editing instructions
- Python skills use isolated `.venv/` directories (gitignored)

### Credentials

No secrets in the repo. Each skill externalises credentials:

| Skill | Location |
|-------|----------|
| Repo Search | None (local) |
| PST to Markdown | None (local) |
| Email Search | None (local) |
| Garmin | `~/.garmin/` |
| Humanize | `~/.humanize/` (optional, for commercial API) |
| GPT Image 2 | `$OPENAI_API_KEY` env var |
| Deep Research | None required (built-in WebSearch is primary). Optional fallback: Bright Data CLI (`brightdata login`, or `BRIGHTDATA_API_KEY`) |

### Dependencies

- **Python skills:** Each has its own `requirements.txt` and `.venv/`
- Both installers handle venv creation and dependency installation automatically

## Conventions

- Shell scripts use `set -e` and are `chmod +x`
- Python scripts use the skill's `.venv/bin/python` (not system Python)
- Source `SKILL.md` commands use Claude-style absolute paths (`~/.claude/skills/<skill>/...`); `install-codex.sh` rewrites them for Codex installs
- Error messages go to stderr, structured output (JSON) to stdout
- All skills work offline except Garmin, Humanize's commercial API engine, and Deep Research (which needs web access, though no API key of its own)

## Important Reminders

- **Always update README.md** when adding or modifying skills. The README has three tables that must stay in sync: Skills list, Credentials, and Requirements. CLAUDE.md also has a Repository Structure tree and Credentials table that must be updated.
