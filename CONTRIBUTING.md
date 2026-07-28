# Contributing

Thanks for taking a look. This repo is a collection of skills for Claude Code and
Codex; each skill is a self-contained directory, and the rules below exist mostly
to stop the two installers and the docs drifting apart.

## Repo layout

Every skill follows the same shape:

```
skill-name/
  SKILL.md            # Skill definition — YAML frontmatter + usage instructions
  README.md           # Human-readable docs
  setup.sh            # Automated first-time setup
  scripts/            # Executable scripts called by SKILL.md
  references/         # Setup guides, manual instructions
  tests/              # Test suite, run by CI
```

`SKILL.md` is the file the skill host discovers. It must open with YAML
frontmatter carrying `name` and `description`, and `name` must equal the
directory name. CI enforces this — a malformed frontmatter block makes a skill
silently undiscoverable rather than broken, which is much harder to notice.

## Adding a skill

1. Create the directory with `SKILL.md`, `setup.sh`, `scripts/` and `README.md`.
2. Add the skill name to `AVAILABLE_SKILLS` in **both** `install.sh` and
   `install-codex.sh`.
3. Add a `check_deps_<skill>()` function and a `post_install` case in **both**
   installers.
4. Add the skill to the three README tables (Skills, Credentials, Requirements)
   and to the CLAUDE.md structure tree and credentials table.
5. Add a `tests/` directory and a job in `.github/workflows/ci.yml`.
6. Test with `./install.sh <skill-name>` and `./install-codex.sh <skill-name>`.

Steps 2–4 are all enforced by CI (`tests/test_install_codex.sh` and
`tests/test_repo_hygiene.py`), so forgetting one fails the build rather than
shipping a half-installed skill.

## Running the checks locally

CI runs exactly these. Nothing here touches the network.

```bash
# Lint and format (config in pyproject.toml)
pip install ruff
ruff check .
ruff format --check .

# Repo invariants: frontmatter, README/CLAUDE.md table sync
python -m pytest tests/test_repo_hygiene.py -v

# Installer parity + a real Codex install into a temp HOME
bash tests/test_install_codex.sh

# Shell scripts
shellcheck install.sh install-codex.sh tests/*.sh */setup.sh */scripts/setup.sh

# A skill's own suite
python -m pytest <skill>/tests/ -v
```

## Conventions

- Shell scripts use `set -e` and are `chmod +x`.
- Python scripts run from the skill's own `.venv/bin/python`, never system Python.
- Source `SKILL.md` files use Claude-style absolute paths
  (`~/.claude/skills/<skill>/...`); `install-codex.sh` rewrites them at install
  time for Codex.
- Errors go to stderr; structured output (JSON) goes to stdout.
- Tests must be hermetic. Patch the HTTP client rather than calling out, and
  patch `time.sleep` rather than waiting.

## Python version floors

They differ per skill, and the reason is usually a dependency rather than our own
code. The CI matrix encodes the real floor for each:

| Skill | Floor | Why |
|-------|-------|-----|
| gpt-image-2 | 3.9 | PyYAML only |
| humanize | 3.9 | no annotations; `requests` resolves an older release on 3.9 |
| garmin | 3.12 | `garminconnect` 0.3.x declares `Requires-Python >=3.12` |

## Credentials

No secrets in the repo, ever. Each skill externalises its credentials to a
location outside the tree (`~/.garmin/`, `~/.humanize/`, `$OPENAI_API_KEY`). If a
new skill needs a credential, add it to the README and CLAUDE.md credentials
tables — CI checks that the tables list every skill.

## git blame

The repo was reformatted once with `ruff format`. That commit is listed in
`.git-blame-ignore-revs`, which GitHub honours automatically. To get the same
behaviour locally:

```bash
git config blame.ignoreRevsFile .git-blame-ignore-revs
```
