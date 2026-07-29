# Security Policy

## Reporting a vulnerability

Please report security issues privately rather than opening a public issue.

Use GitHub's [private vulnerability reporting](https://github.com/grinidx/claude-skills/security/advisories/new)
on this repository. If that is unavailable, open an issue asking for a private
contact channel — without including any detail of the vulnerability itself.

Expect an acknowledgement within a few days.

## Scope

These skills run locally as an extension of a coding agent, with the permissions
of whoever invokes them. The things worth reporting are:

- A skill script reading, writing, or transmitting data outside its documented
  scope.
- Credential handling that writes a secret into the repo, into logs, or into a
  world-readable file.
- Command injection through a skill's arguments — several scripts shell out to
  `readpst`, `magick`, or the Bright Data CLI.
- An installer writing outside `~/.claude/skills/` or `~/.codex/skills/`.

Out of scope: vulnerabilities in the upstream services these skills talk to
(Garmin Connect, OpenAI, Undetectable AI, Bright Data) — report those to the
vendor.

## Credentials

No secrets are stored in this repository. Each skill keeps credentials outside
the tree:

| Skill | Location |
|-------|----------|
| PST to Markdown | none (fully local) |
| Garmin | `~/.garmin/` |
| Verve | `~/.verve/` (optional, commercial API only) |
| GPT Image 2 | `$OPENAI_API_KEY` environment variable |
| Deep Research | none required; optional Bright Data CLI login |

If you find a credential committed to this repo, please report it as above and
treat it as live until confirmed otherwise.

## Supply chain

GitHub Actions are pinned to commit SHAs rather than mutable tags, and Dependabot
keeps both the action pins and the Python dependencies under review. See
`.github/dependabot.yml`.
