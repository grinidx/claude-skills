# CI Coverage for Every Skill — Design

**Date:** 2026-07-28
**Status:** Approved

## Problem

CI covers `deep-research`, `garmin`, and the installers. Three skills — `gpt-image-2`,
`humanize`, `pst-to-markdown` — have no tests and no CI job at all. Nothing checks
repo-level invariants either: a `SKILL.md` can lose its frontmatter and become
silently undiscoverable, and the README tables can drift from the skill directories
(they carried `outlook` and `trello` rows for weeks after those skills moved out).

The repo also lacks the baseline hygiene a public repo is expected to have:
no Dependabot, no `permissions:` block on the workflow, no lint config, no
contributor docs.

## Goals

1. Every skill has a CI job proportionate to what it actually does.
2. Repo-level invariants are enforced by a test, not by memory.
3. Dependency and action updates arrive as PRs rather than as silent rot.
4. `main` is protected by passing CI.

## Non-goals

- Testing the libratom PST extraction driver. It needs a real PST fixture; only
  its pure helpers get covered, and that limit is stated in the test module.
- Testing live API calls for any skill. Every suite is hermetic.
- Rewriting the skills themselves. Lint fixes are mechanical only.

## Test suites

Plain `unittest`, run under `pytest`, matching the existing `deep-research` and
`garmin` convention. Each skill's tests live in `<skill>/tests/`.

### gpt-image-2

`urllib.request.urlopen` is patched; nothing reaches the network.

- `compose_prompt` resolves a preset from the real `presets.yaml` and substitutes
  `{subject}`; an unknown preset exits non-zero.
- Every entry in `presets.yaml` has `description` + `prompt`, and every `prompt`
  contains the `{subject}` placeholder. Every entry in `platforms.yaml` has
  `description` + positive integer `width`/`height`. These two files are the
  skill's real configuration surface and nothing else validates them.
- `estimate_cost` / `cost_per_unit` across quality x thinking x n, including the
  unknown-key fallback paths.
- History round-trip against a redirected `HOME`: `save_history` then
  `load_history` (with and without a project filter) and `load_last_run`.
- `_build_multipart` — the one piece of hand-rolled wire protocol in the repo —
  produces a body with correct boundaries, per-field dispositions, and a MIME
  type derived from the filename extension.
- Argparse accepts each subcommand and rejects a bad flag combination.

### humanize

`requests` and `time.sleep` are patched; the suite never waits and never calls out.

- `submit_text` posts to `/submit` with the `apikey` header and `content` body,
  returns the document id, and exits non-zero when the response has no `id`.
- `poll_result` returns the output on `status: done`, exits on `status: error`,
  and gives up after `MAX_POLLS` iterations without real sleeping.
- A missing config file and a config without `api_key` both exit 1 with a message
  on stderr.

### pst-to-markdown

`libratom` is already an optional guarded import, so the suite runs without it.

- `sanitize_filename`: length cap, path separators, the `<>:"/\|?*@[]` class,
  hyphen collapsing, and the empty/all-stripped input that must fall back to
  `"unknown"`.
- `sanitize_email`: extracts the address from `Name <addr>` form.
- `parse_email_address` on display-name, bare-address, quoted, and empty inputs.
- `html_to_markdown` through html2text, plus the `HAS_HTML2TEXT = False`
  regex fallback driven by patching the module flag.
- `compute_sha256` against a known digest and `format_size` across unit boundaries.
- `--append` dedupe: `_load_existing_index` reads an `index.csv` fixture, populates
  `existing_message_ids`, and a malformed CSV clears state rather than half-loading.

## Repo hygiene

`tests/test_repo_hygiene.py`:

- **Frontmatter** — every `*/SKILL.md` parses as YAML frontmatter with non-empty
  `name` and `description`, and `name` equals the directory name.
- **Table sync** — every skill directory appears in the three README tables and in
  the CLAUDE.md structure tree and credentials table; and no table row references a
  directory that no longer exists.

Plus a `shellcheck` step over `install.sh`, `install-codex.sh`, `tests/*.sh` and all
five `setup.sh`. The 13 pre-existing findings are fixed in the same change so the
job lands green: 11 x `read` without `-r`, and 2 x SC2088 in
`tests/test_install_codex.sh` that are deliberate (they assert a literal `~/.claude`
string in generated output) and get a scoped `disable` with a reason.

## Matrix

Floor plus ceiling rather than full sweeps — five versions x three skills would add
15 jobs, and libratom is a heavy install.

| Job | Versions | Floor rationale |
|-----|----------|-----------------|
| gpt-image-2 | 3.9, 3.11, 3.13 | `from __future__ import annotations` makes its `str \| None` hints safe below 3.10; PyYAML needs 3.8+ |
| humanize | 3.9, 3.13 | No annotations at all; on 3.9 pip resolves an older `requests`, which is worth exercising |
| pst-to-markdown | 3.9, 3.13 | Hard 3.9: `parse_email_address` uses a runtime `tuple[str, str]` with no `__future__` import |
| repo-hygiene | 3.12 | Single job |
| lint | 3.12 | Single job |

Existing `deep-research`, `garmin`, `installers` and `smoke` jobs are unchanged.

## Hardening

- Top-level `permissions: contents: read` on the workflow. It currently inherits the
  default token permissions, which are broader than any job here needs.
- Actions pinned to commit SHAs with a version comment, so a compromised or moved
  tag cannot change what runs. Dependabot keeps the pins current.
- `.editorconfig`, and a CI badge in the README.

## Ruff

`pyproject.toml` configures ruff for the whole repo; a `lint` job runs
`ruff check` and `ruff format --check`. Rule selection is deliberately modest
(pycodestyle, pyflakes, isort, pyupgrade, bugbear, comprehensions) with a line
length that fits the existing code, because the point is to stop new rot rather
than to relitigate 1,800 lines of working script. `target-version` is `py39`, the
repo-wide floor. Findings are fixed mechanically in the same change.

## Dependabot

`.github/dependabot.yml` covers `github-actions` plus the five `pip` directories,
weekly, with updates grouped per ecosystem to avoid PR spam.

Known limitation, accepted: the five `requirements.txt` files use open ranges
(`PyYAML>=6.0`, `requests>=2.28`). Dependabot largely leaves `>=` constraints alone,
so the pip entries will be quiet until something is pinned. They cost nothing and
start working the moment a pin appears. `github-actions` is where the value is now.

## Contributor docs

`CONTRIBUTING.md` (mirroring the CLAUDE.md add-a-skill checklist so the two cannot
disagree), `SECURITY.md`, and issue/PR templates.

## Branch protection

Applied to `main` via `gh api`: require the CI checks to pass and require a PR
rather than a direct push, with `enforce_admins: false` so the owner retains a
direct path when needed.
