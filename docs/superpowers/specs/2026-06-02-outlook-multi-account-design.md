# Outlook Skill: Multi-Account Support + Ported Fixes

**Date:** 2026-06-02
**Status:** Approved design, pending implementation plan

## Background

The `outlook/` skill currently supports a single Microsoft 365 account, with config and
credentials stored flat in `~/.outlook/`:

```
~/.outlook/
  config.json        # client_id, client_secret, tenant, redirect_uri, scope
  credentials.json   # access_token, refresh_token, ...
  id_cache.json      # cached message IDs for short-ID resolution
```

The upstream fork [cristiandan/outlook-skill](https://github.com/cristiandan/outlook-skill)
added three improvements on an *older, smaller* base than ours (their `outlook-mail.sh`
is 30 KB vs our 58 KB; they lack our inline token auto-refresh, `id_cache` short-ID
resolution, and ~15 extra mail commands such as `mddraft`/`mdreply`/`followup`/`focused`/
`stats`/`move`/`mkdir`). Rather than adopt their scripts wholesale (which would regress our
feature set), we port their three additions into our scripts:

1. Multi-account support
2. Attachment path-traversal fix
3. System timezone auto-detection

## Goals

- Support multiple Outlook accounts selectable per-invocation.
- Migrate the existing single account seamlessly to a `default` account (zero user action).
- Fix the attachment-download path-traversal vulnerability.
- Auto-detect the system timezone for calendar operations.
- Keep all existing features intact (token auto-refresh, short-IDs, every current command).

## Non-Goals

- Rewriting or replacing our scripts with the fork's.
- Concurrent multi-account operations in a single command (each invocation targets one account).
- A "last-used account" memory feature (rejected — too surprising; explicit is safer).

## Design

### 1. Storage layout & account resolution

Base directory stays `~/.outlook/` (matches root `CLAUDE.md` docs; least disruptive).
Per-account subdirectories hold the same files as before:

```
~/.outlook/
  default/
    config.json
    credentials.json
    id_cache.json
  work/
    config.json
    credentials.json
    id_cache.json
```

A shared header block is added to all four scripts (`outlook-setup.sh`, `outlook-token.sh`,
`outlook-mail.sh`, `outlook-calendar.sh`):

```bash
BASE_DIR="$HOME/.outlook"

# Account resolution: --account/-a flag wins, else OUTLOOK_ACCOUNT env, else "default"
ACCOUNT="${OUTLOOK_ACCOUNT:-default}"
if [ "$1" = "--account" ] || [ "$1" = "-a" ]; then
    ACCOUNT="$2"; shift 2
fi

# One-time migration: legacy flat config -> default/
if [ -f "$BASE_DIR/config.json" ] && [ ! -d "$BASE_DIR/default" ]; then
    mkdir -p "$BASE_DIR/default"
    mv "$BASE_DIR/config.json" "$BASE_DIR/credentials.json" "$BASE_DIR/id_cache.json" \
       "$BASE_DIR/default/" 2>/dev/null || true
fi

CONFIG_DIR="$BASE_DIR/$ACCOUNT"
CONFIG_FILE="$CONFIG_DIR/config.json"
CREDS_FILE="$CONFIG_DIR/credentials.json"
ID_CACHE_FILE="$CONFIG_DIR/id_cache.json"
```

Notes:
- `--account`/`-a` is parsed **before** the command, so `outlook-mail.sh -a work inbox` works.
- `OUTLOOK_ACCOUNT` env var sets the default account for a shell session.
- No flag and no env var → the `default` account.
- Migration is idempotent (guarded by `! -d default`). The user's existing mailbox keeps
  working immediately, now as `default`.
- **Divergence from the fork:** we keep our superior inline `ensure_valid_token()`
  auto-refresh in `outlook-mail.sh`/`outlook-calendar.sh`. Because it already reads
  `$CONFIG_FILE`/`$CREDS_FILE`, it becomes account-aware for free. We do **not** adopt the
  fork's "read token raw" approach.
- `id_cache.json` is per-account so short message IDs never collide across mailboxes.

### 2. `outlook-token.sh`: `list` command + account scoping

- New `list` command, handled **before** the config-exists check (listing must not require a
  configured account):

  ```
  $ outlook-token.sh list
  Configured accounts:
    - default
    - work
  ```
- Existing `refresh` / `get` / `test` / `status` become account-scoped via the shared header.
- "Not configured" errors gain a hint: `Run: outlook-setup.sh --account <name>`.

### 3. `outlook-setup.sh`: per-account, reuse existing app registration

- Config is written to the resolved `$CONFIG_DIR`.
- **Reuse-app path (primary for additional accounts):** if any *other* account already has a
  `config.json` with a `client_id`/`client_secret`, setup offers to reuse those credentials and
  **skips Azure app creation**, jumping straight to the OAuth authorize + token-exchange steps.
  Rationale: the app is registered as `AzureADandPersonalMicrosoftAccount` (multi-tenant +
  personal) against the `common` tenant, so one app authenticates many mailboxes. A second
  mailbox often lacks Azure CLI/admin rights to register its own app, so reuse is the practical
  default.
- **Fresh-app path:** if no existing account config is found (or the user declines reuse), run
  the existing 7-step Azure CLI flow unchanged, with the app display name suffixed by the
  account name for non-default accounts (e.g. `Claude-Outlook-Integration-work`).

### 4. Path-traversal fix (`outlook-mail.sh` `download`)

The current `download` command writes attachments to `$DOWNLOAD_DIR/$att_name` using the
server-supplied name verbatim (`outlook-mail.sh:1287`). A malicious attachment named
`../../foo` escapes `$DOWNLOAD_DIR`. Fix: sanitize before building `dest_path`:

```bash
att_name=$(basename "$att_name" | sed 's/\.\.//g')
if [ -z "$att_name" ] || [ "$att_name" = "." ]; then
    att_name="attachment"
fi
```

This composes with the existing collision handling (`_1`, `_2` suffixing) and the `inbox/`
destination logic, which are unchanged.

### 5. Timezone auto-detection (`outlook-calendar.sh`)

Replace the hardcoded `DEFAULT_TIMEZONE="Europe/London"` (`outlook-calendar.sh:10`) with
detection, **preserving the variable name** so the rest of the script is untouched:

```bash
if [ -n "$OUTLOOK_TZ" ]; then
    DEFAULT_TIMEZONE="$OUTLOOK_TZ"
elif [ -f /etc/timezone ]; then
    DEFAULT_TIMEZONE=$(cat /etc/timezone)
elif command -v timedatectl &>/dev/null; then
    DEFAULT_TIMEZONE=$(timedatectl show -p Timezone --value 2>/dev/null)
elif [ -L /etc/localtime ]; then
    DEFAULT_TIMEZONE=$(readlink /etc/localtime | sed 's|.*/zoneinfo/||')
fi
[ -z "$DEFAULT_TIMEZONE" ] && DEFAULT_TIMEZONE="Europe/London"   # fallback
```

### 6. Documentation

- `outlook/SKILL.md`: document `--account`/`-a`, `OUTLOOK_ACCOUNT`, `outlook-token.sh list`,
  per-account setup, and the `OUTLOOK_TZ` override.
- `outlook/README.md`: note multi-account usage.
- Root `CLAUDE.md` + `outlook/README.md` credentials table: location stays `~/.outlook/`, now
  with per-account subdirectories.

## Error Handling

- Unconfigured account → clear error naming the account and the setup command to run, plus a
  list of available accounts.
- Migration failures (`mv` errors) are non-fatal (`|| true`); scripts still resolve `$CONFIG_DIR`.
- Timezone detection failure falls back to `Europe/London`.
- Sanitized-away attachment names fall back to `attachment`.

## Testing

Live Graph API + interactive OAuth cannot be fully automated. Verification plan:

1. `bash -n` syntax check on all four scripts.
2. Migration dry-run against a temp `$HOME` with a fake flat `~/.outlook/` → assert files land
   in `default/` and are idempotent on a second run.
3. Path-sanitization unit check with adversarial names (`../../etc/foo`, `..`, `.`, empty).
4. `outlook-token.sh list` output with 0, 1, and 2 accounts.
5. Timezone detection on this Linux host returns a sane non-empty value.
6. **Real end-to-end:** run `outlook-setup.sh --account <name>` for the user's second mailbox
   via the reuse-app path, then `outlook-token.sh --account <name> test` and a read-only
   `outlook-mail.sh --account <name> inbox`.

## Files Touched

- `outlook/scripts/outlook-setup.sh`
- `outlook/scripts/outlook-token.sh`
- `outlook/scripts/outlook-mail.sh`
- `outlook/scripts/outlook-calendar.sh`
- `outlook/SKILL.md`
- `outlook/README.md`
- `CLAUDE.md` (root, credentials/structure notes)
