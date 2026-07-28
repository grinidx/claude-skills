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
├── docs/plans/       # Per-skill design & implementation docs (<date>-<skill>-{design,plan}.md)
├── tests/            # Repo-level tests (installer behaviour, repo hygiene)
├── install.sh        # Claude installer (symlinks into ~/.claude/skills)
├── install-codex.sh  # Codex installer (installs into ~/.codex/skills)
├── pyproject.toml    # Repo tooling config (ruff only — this is not a package)
├── CONTRIBUTING.md   # How to add/modify a skill; local equivalents of every CI check
├── SECURITY.md       # Private vulnerability reporting
├── .github/workflows/ci.yml  # CI: every skill + lint + repo hygiene + installers + e2e smoke
├── .github/dependabot.yml    # Weekly github-actions + 5 pip ecosystems
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
4. Add the skill to the README tables (skills list, credentials, requirements) and to this file's structure tree and credentials table
5. Add a `tests/` directory and a job in `.github/workflows/ci.yml` (including `ci-ok`'s `needs:` list)
6. Test with `./install.sh <skill-name>` and `./install-codex.sh <skill-name>`

Steps 2-3 are enforced in CI by `tests/test_install_codex.sh`, which fails if the two installers offer different skills or if a skill is missing a `check_deps`/`post_install` case. Step 4 is enforced by `tests/test_repo_hygiene.py`, which also checks that every `SKILL.md` has valid frontmatter whose `name` matches its directory.

### Modifying an Existing Skill

- The source `SKILL.md` is used directly by Claude and transformed for Codex at install time
- Test changes by invoking the skill in Claude Code and reinstalling for Codex after editing instructions
- Python skills use isolated `.venv/` directories (gitignored)

### Credentials

No secrets in the repo. Each skill externalises credentials:

| Skill | Location |
|-------|----------|
| PST to Markdown | None (local) |
| Garmin | `~/.garmin/` |
| Humanize | `~/.humanize/` (optional, for commercial API) |
| GPT Image 2 | `$OPENAI_API_KEY` env var |
| Deep Research | None required (built-in WebSearch is primary). Optional fallback: Bright Data CLI (`brightdata login`, or `BRIGHTDATA_API_KEY`) |

### Dependencies

- **Python skills:** Each has its own `requirements.txt` and `.venv/`
- Both installers handle venv creation and dependency installation automatically
- **Garmin needs Python 3.12+** — `garminconnect` 0.3.x declares `Requires-Python >=3.12`. Both installers and `garmin/scripts/setup.sh` check this up front, so the failure is a clear message rather than a pip resolver dump
- **PST to Markdown caps at Python 3.11** — `libratom` pins `numpy==1.23.5`, whose newest wheel is cp311, so `pip install -r requirements.txt` fails outright on 3.12+. The two floors point in opposite directions: there is no single Python that runs both garmin and pst-to-markdown

## CI

`.github/workflows/ci.yml` runs a job per skill plus three repo-wide gates. Every
job is hermetic — no network, no credentials, no real sleeps.

| Job | What it guards |
|-----|----------------|
| `lint` | `ruff check` + `ruff format --check` (config in `pyproject.toml`, `target-version = py39`) |
| `repo-hygiene` | SKILL.md frontmatter, README/CLAUDE.md table sync, shellcheck |
| `installers` | `install.sh` / `install-codex.sh` parity, real Codex install |
| per-skill | each skill's `tests/`, on a floor + ceiling Python matrix |
| `pst-to-markdown-install` | asserts the full `requirements.txt` installs on 3.11 |
| `smoke` | deep-research end-to-end lifecycle against shipped fixtures |
| `ci-ok` | aggregates the rest; this is the single required check for branch protection |

Adding a job means adding it to `ci-ok`'s `needs:` list — the branch protection
rule points only at `ci-ok`, so a job missing from that list is a job nobody is
gated on. `tests/test_repo_hygiene.py` is stdlib-only by design so it can run
before any skill's dependencies are installed.

## Conventions

- Shell scripts use `set -e` and are `chmod +x`
- Python scripts use the skill's `.venv/bin/python` (not system Python)
- Source `SKILL.md` commands use Claude-style absolute paths (`~/.claude/skills/<skill>/...`); `install-codex.sh` rewrites them for Codex installs
- Error messages go to stderr, structured output (JSON) to stdout
- All skills work offline except Garmin, Humanize's commercial API engine, and Deep Research (which needs web access, though no API key of its own)

## Important Reminders

- **Always update README.md** when adding or modifying skills. The README has three tables that must stay in sync: Skills list, Credentials, and Requirements. CLAUDE.md also has a Repository Structure tree and Credentials table that must be updated.
