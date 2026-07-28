## What this changes

<!-- One or two sentences. What is different after this merges? -->

## Why

<!-- The problem, not the solution. If it fixes an issue, link it. -->

## Checklist

<!-- Delete rows that do not apply. CI enforces most of these anyway. -->

- [ ] Tests added or updated, and they are hermetic (no network, no real sleeps)
- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] If a skill was added or renamed: both `install.sh` and `install-codex.sh`
      updated (`AVAILABLE_SKILLS`, `check_deps_*`, `post_install`)
- [ ] If a skill was added or renamed: README tables and CLAUDE.md updated
- [ ] No credentials, tokens, or personal data in the diff

## Notes for the reviewer

<!-- Anything non-obvious: a deliberate trade-off, a known limitation, a
     follow-up you chose not to do here. -->
