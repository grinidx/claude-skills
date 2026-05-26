# Claude Code Skills

A collection of Claude Code skills that extend Claude with external service integrations and local tooling.

## Repository Structure

```
claude-skills/
├── outlook/          # Microsoft 365 email & calendar (bash/Graph API)
├── trello/           # Trello board management (bash/REST API)
├── repo-search/      # Semantic search over markdown files (Python/ChromaDB)
├── pst-to-markdown/  # PST to markdown extraction (Python)
├── email-search/     # PST ingestion + vector search + analytics (Python/ChromaDB)
├── garmin/           # Garmin Connect health & fitness data (Python/garminconnect)
├── humanize/         # Humanize AI-generated text (prompt-driven + optional API)
├── gpt-image-2/      # OpenAI GPT Image 2 generation & editing (Python)
├── install.sh        # Symlink installer for all skills
└── README.md         # User-facing documentation
```

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

- `SKILL.md` is the file Claude Code discovers and loads. It must have YAML frontmatter with `name` and `description`.
- Skills are **symlinked** from this repo into `~/.claude/skills/` via `install.sh`. Edits here are immediately live.

## Working on Skills

### Adding a New Skill

1. Create a directory with `SKILL.md`, `setup.sh`, `scripts/`, and `README.md`
2. Add the skill name to `AVAILABLE_SKILLS` in `install.sh`
3. Add a `check_deps_<skill>()` function and `post_install` case in `install.sh`
4. Add the skill to the README tables (skills list, credentials, requirements)
5. Test with `./install.sh <skill-name>`

### Modifying an Existing Skill

- The `SKILL.md` is what Claude reads at runtime — keep it accurate and complete
- Test changes by invoking the skill in Claude Code after editing
- Python skills use isolated `.venv/` directories (gitignored)

### Credentials

No secrets in the repo. Each skill externalises credentials:

| Skill | Location |
|-------|----------|
| Outlook | `~/.outlook/` |
| Trello | `~/.trello/` |
| Repo Search | None (local) |
| PST to Markdown | None (local) |
| Email Search | None (local) |
| Garmin | `~/.garmin/` |
| Humanize | `~/.humanize/` (optional, for commercial API) |
| GPT Image 2 | `$OPENAI_API_KEY` env var |

### Dependencies

- **Outlook/Trello:** bash, jq, curl (+ azure-cli for Outlook)
- **Python skills:** Each has its own `requirements.txt` and `.venv/`
- `install.sh` handles venv creation and dependency installation automatically

## Conventions

- Shell scripts use `set -e` and are `chmod +x`
- Python scripts use the skill's `.venv/bin/python` (not system Python)
- SKILL.md commands use full absolute paths (`~/.claude/skills/<skill>/...`)
- Error messages go to stderr, structured output (JSON) to stdout
- All skills work offline except Outlook, Trello, Garmin, and Humanize's commercial API engine (which need API access)

## Important Reminders

- **Always update README.md** when adding or modifying skills. The README has three tables that must stay in sync: Skills list, Credentials, and Requirements. CLAUDE.md also has a Repository Structure tree and Credentials table that must be updated.
