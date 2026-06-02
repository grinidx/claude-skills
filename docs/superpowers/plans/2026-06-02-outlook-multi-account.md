# Outlook Multi-Account Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-account support to the Outlook skill (per-account credential storage selectable via `--account`/`-a`/`OUTLOOK_ACCOUNT`), plus port two fixes from the cristiandan fork: attachment path-traversal sanitization and system timezone auto-detection.

**Architecture:** A shared header block in each of the four bash scripts resolves the active account, migrates any legacy flat config into a `default/` subdirectory, and points the existing `CONFIG_FILE`/`CREDS_FILE`/`ID_CACHE_FILE` variables at `~/.outlook/<account>/`. Because the rest of each script already reads those variables, the bulk of the logic (token auto-refresh, short-ID cache, all commands) is unchanged. Setup gains a reuse-existing-app path so additional mailboxes need no Azure admin rights.

**Tech Stack:** bash, jq, curl, Azure CLI (`az`), Microsoft Graph API.

---

## File Structure

- `outlook/scripts/outlook-token.sh` — account header + `list` command + scoped errors.
- `outlook/scripts/outlook-mail.sh` — account header + attachment path-traversal fix.
- `outlook/scripts/outlook-calendar.sh` — account header + timezone auto-detection.
- `outlook/scripts/outlook-setup.sh` — account header + reuse-existing-app path + account-suffixed app name + per-account config write.
- `outlook/SKILL.md` — document `--account`/`-a`, `OUTLOOK_ACCOUNT`, `OUTLOOK_TZ`, `outlook-token.sh list`.
- `outlook/README.md` — multi-account usage + credentials location note.
- `CLAUDE.md` (root) — credentials table / structure note.

**Shared header (referred to as THE HEADER below; the exact text differs slightly per script because of which path variables each needs):**

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
```

`outlook-mail.sh` additionally sets `ID_CACHE_FILE="$CONFIG_DIR/id_cache.json"`.

---

## Task 1: Account header + `list` in `outlook-token.sh`

**Files:**
- Modify: `outlook/scripts/outlook-token.sh:4-14` (replace the flat path block and config check)

- [ ] **Step 1: Replace the path block and add account resolution + `list`**

Replace lines 4-14 (from `set -e` through the `Config not found` check) with:

```bash
set -e

BASE_DIR="$HOME/.outlook"

# Account resolution: --account/-a flag wins, else OUTLOOK_ACCOUNT env, else "default"
ACCOUNT="${OUTLOOK_ACCOUNT:-default}"
if [ "$1" = "--account" ] || [ "$1" = "-a" ]; then
    ACCOUNT="$2"; shift 2
fi

# `list` must work without a configured account, so handle it before the config check.
if [ "$1" = "list" ]; then
    echo "Configured accounts:"
    found=0
    for dir in "$BASE_DIR"/*/; do
        [ -f "$dir/credentials.json" ] || continue
        echo "  - $(basename "$dir")"
        found=1
    done
    [ "$found" = 0 ] && echo "  (none configured — run outlook-setup.sh)"
    exit 0
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

# Check config exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Account '$ACCOUNT' not configured."
    echo "Run: outlook-setup.sh --account $ACCOUNT"
    exit 1
fi
```

- [ ] **Step 2: Update the usage/help text to mention accounts**

In the `*)` help case at the bottom of the file, add these two lines after the existing `Commands:` block (before the closing `;;`):

```bash
        echo "  list       List configured accounts"
        echo
        echo "Account selection: --account <name> | -a <name> | OUTLOOK_ACCOUNT env (default: default)"
```

- [ ] **Step 3: Syntax check**

Run: `bash -n outlook/scripts/outlook-token.sh`
Expected: no output, exit 0.

- [ ] **Step 4: Migration + list verification against a temp HOME**

Run:
```bash
TMP=$(mktemp -d); mkdir -p "$TMP/.outlook"
echo '{"client_id":"x","client_secret":"y"}' > "$TMP/.outlook/config.json"
echo '{"access_token":"a","refresh_token":"r"}' > "$TMP/.outlook/credentials.json"
HOME="$TMP" bash outlook/scripts/outlook-token.sh list
ls "$TMP/.outlook/default/"
rm -rf "$TMP"
```
Expected: `list` prints `  - default`; the `ls` shows `config.json` and `credentials.json` migrated into `default/`.

- [ ] **Step 5: Commit**

```bash
git add outlook/scripts/outlook-token.sh
git commit -m "feat(outlook): per-account token management + list command"
```

---

## Task 2: Account header in `outlook-mail.sh`

**Files:**
- Modify: `outlook/scripts/outlook-mail.sh:4-16` (replace flat path block + credentials check)

- [ ] **Step 1: Replace the path block with the account header**

Replace lines 4-16 (from `set -e` through the `Credentials not found` check) with:

```bash
set -e

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
GRAPH_URL="https://graph.microsoft.com/v1.0"

# Check credentials
if [ ! -f "$CREDS_FILE" ]; then
    echo "Error: Account '$ACCOUNT' not configured. Run: outlook-setup.sh --account $ACCOUNT"
    exit 1
fi
```

(Note: `GRAPH_URL` was previously on line 10; it is reintroduced here so the rest of the script is unchanged. `ensure_valid_token()`, `api_call()`, and all commands already reference `CONFIG_FILE`/`CREDS_FILE`/`ID_CACHE_FILE` and need no edits.)

- [ ] **Step 2: Syntax check**

Run: `bash -n outlook/scripts/outlook-mail.sh`
Expected: no output, exit 0.

- [ ] **Step 3: Verify flag parsing + unconfigured-account error**

Run:
```bash
TMP=$(mktemp -d)
HOME="$TMP" bash outlook/scripts/outlook-mail.sh -a ghost inbox; echo "exit=$?"
rm -rf "$TMP"
```
Expected: prints `Error: Account 'ghost' not configured. Run: outlook-setup.sh --account ghost` and `exit=1`.

- [ ] **Step 4: Commit**

```bash
git add outlook/scripts/outlook-mail.sh
git commit -m "feat(outlook): per-account credential resolution in mail script"
```

---

## Task 3: Attachment path-traversal fix in `outlook-mail.sh`

**Files:**
- Modify: `outlook/scripts/outlook-mail.sh` — inside the `download)` case, the per-attachment loop (currently around line 1275-1287, after `att_name=$(echo "$att" | jq -r '.name')`).

- [ ] **Step 1: Sanitize the attachment name before it is used in any path**

Immediately after the line `att_size=$(echo "$att" | jq -r '.size')` and before `base_name="${att_name%.*}"`, insert:

```bash
            # Sanitize server-supplied name: prevent path traversal out of $DOWNLOAD_DIR
            att_name=$(basename "$att_name" | sed 's/\.\.//g')
            if [ -z "$att_name" ] || [ "$att_name" = "." ]; then
                att_name="attachment"
            fi
```

- [ ] **Step 2: Syntax check**

Run: `bash -n outlook/scripts/outlook-mail.sh`
Expected: no output, exit 0.

- [ ] **Step 3: Verify sanitization logic in isolation**

Run:
```bash
sanitize() { local n; n=$(basename "$1" | sed 's/\.\.//g'); { [ -z "$n" ] || [ "$n" = "." ]; } && n="attachment"; echo "$n"; }
sanitize "../../etc/passwd"      # expect: etcpasswd  (no slashes, no ..)
sanitize "../../../foo.pdf"      # expect: foo.pdf
sanitize ".."                    # expect: attachment
sanitize "normal report.docx"    # expect: normal report.docx
```
Expected: `etcpasswd`, `foo.pdf`, `attachment`, `normal report.docx` — none contain `/` or `..`.

- [ ] **Step 4: Commit**

```bash
git add outlook/scripts/outlook-mail.sh
git commit -m "fix(outlook): sanitize attachment filenames to prevent path traversal"
```

---

## Task 4: Account header + timezone auto-detection in `outlook-calendar.sh`

**Files:**
- Modify: `outlook/scripts/outlook-calendar.sh:4-16` (replace flat path block, timezone line, and credentials check)

- [ ] **Step 1: Replace the path block, add account header, and auto-detect timezone**

Replace lines 4-16 (from `set -e` through the `Credentials not found` check) with:

```bash
set -e

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
GRAPH_URL="https://graph.microsoft.com/v1.0"

# Timezone: OUTLOOK_TZ override, else system timezone, else Europe/London fallback
if [ -n "$OUTLOOK_TZ" ]; then
    DEFAULT_TIMEZONE="$OUTLOOK_TZ"
elif [ -f /etc/timezone ]; then
    DEFAULT_TIMEZONE=$(cat /etc/timezone)
elif command -v timedatectl &>/dev/null; then
    DEFAULT_TIMEZONE=$(timedatectl show -p Timezone --value 2>/dev/null)
elif [ -L /etc/localtime ]; then
    DEFAULT_TIMEZONE=$(readlink /etc/localtime | sed 's|.*/zoneinfo/||')
fi
[ -z "$DEFAULT_TIMEZONE" ] && DEFAULT_TIMEZONE="Europe/London"

# Check credentials
if [ ! -f "$CREDS_FILE" ]; then
    echo "Error: Account '$ACCOUNT' not configured. Run: outlook-setup.sh --account $ACCOUNT"
    exit 1
fi
```

- [ ] **Step 2: Syntax check**

Run: `bash -n outlook/scripts/outlook-calendar.sh`
Expected: no output, exit 0.

- [ ] **Step 3: Verify timezone detection resolves to a non-empty value**

Run:
```bash
bash -c '
if [ -n "$OUTLOOK_TZ" ]; then TZ="$OUTLOOK_TZ"
elif [ -f /etc/timezone ]; then TZ=$(cat /etc/timezone)
elif command -v timedatectl &>/dev/null; then TZ=$(timedatectl show -p Timezone --value 2>/dev/null)
elif [ -L /etc/localtime ]; then TZ=$(readlink /etc/localtime | sed "s|.*/zoneinfo/||")
fi
[ -z "$TZ" ] && TZ="Europe/London"
echo "Detected: $TZ"'
OUTLOOK_TZ="America/New_York" bash -c '[ -n "$OUTLOOK_TZ" ] && echo "Override: $OUTLOOK_TZ"'
```
Expected: a non-empty `Detected:` value (this host's zone), and `Override: America/New_York`.

- [ ] **Step 4: Commit**

```bash
git add outlook/scripts/outlook-calendar.sh
git commit -m "feat(outlook): per-account calendar + system timezone auto-detection"
```

---

## Task 5: Account header + reuse-app path in `outlook-setup.sh`

**Files:**
- Modify: `outlook/scripts/outlook-setup.sh` — header/path block (lines ~14-17 + the `mkdir -p "$CONFIG_DIR"` area) and the app-registration section (Step 2).

- [ ] **Step 1: Replace the path/APP_NAME definitions with the account header**

Replace the block that defines `CONFIG_DIR`/`CONFIG_FILE`/`CREDS_FILE`/`APP_NAME` (the four lines after the color definitions) with:

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

# App name is suffixed per non-default account when a fresh app is created.
if [ "$ACCOUNT" = "default" ]; then
    APP_NAME="Claude-Outlook-Integration"
else
    APP_NAME="Claude-Outlook-Integration-$ACCOUNT"
fi
```

- [ ] **Step 2: Echo the active account near the top banner**

After the `=== Outlook OAuth Setup ===` banner echo, add:

```bash
echo -e "Account: ${GREEN}$ACCOUNT${NC}"
```

- [ ] **Step 3: Add the reuse-existing-app path at the start of Step 2 (App Registration)**

At the very start of the `Step 2/7: App Registration` section (before the existing `EXISTING_APP=$(az ad app list ...)` lookup), insert:

```bash
# Reuse an existing account's app registration when available. The app is
# multi-tenant + personal-account, so one app can authorize many mailboxes,
# and additional mailboxes then need no Azure admin rights.
REUSE_CONFIG=""
for dir in "$BASE_DIR"/*/; do
    other="$dir/config.json"
    [ "$dir" = "$CONFIG_DIR/" ] && continue
    [ -f "$other" ] || continue
    REUSE_CONFIG="$other"
    break
done

if [ -n "$REUSE_CONFIG" ]; then
    REUSE_NAME=$(basename "$(dirname "$REUSE_CONFIG")")
    echo -e "${YELLOW}Found existing app registration from account '$REUSE_NAME'.${NC}"
    read -p "Reuse it for '$ACCOUNT'? (recommended) (Y/n): " reuse_ans
    if [[ ! "$reuse_ans" =~ ^[Nn]$ ]]; then
        CLIENT_ID=$(jq -r '.client_id' "$REUSE_CONFIG")
        CLIENT_SECRET=$(jq -r '.client_secret' "$REUSE_CONFIG")
        echo -e "${GREEN}Reusing app: $CLIENT_ID${NC}"
        SKIP_APP_CREATE=1
    fi
fi
```

- [ ] **Step 4: Guard the Azure-app creation and secret/permission steps so they are skipped on reuse**

Wrap the existing app-creation lookup+create logic (Step 2 body), the Step 3 client-secret creation, and the Step 4 permission-add calls so they only run when not reusing. At the start of each of those three blocks add:

```bash
if [ -z "$SKIP_APP_CREATE" ]; then
```

and close each with a matching `fi` at the block's end. (The Azure login Step 1 still runs only if needed — leave it; when reusing it is harmless because `az account show` short-circuits. If you prefer, also guard Step 1 with the same `if [ -z "$SKIP_APP_CREATE" ]` so reuse needs no `az` at all — do this: it makes reuse work without Azure CLI.)

- [ ] **Step 5: Ensure the config directory is created before writing config**

Confirm `mkdir -p "$CONFIG_DIR"` and `chmod 700 "$CONFIG_DIR"` run before Step 5 writes `$CONFIG_FILE`. If the original `mkdir -p "$CONFIG_DIR"` line was removed with the old header, re-add it immediately before the `Step 5/7: Saving Configuration` write:

```bash
mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"
```

- [ ] **Step 6: Syntax check**

Run: `bash -n outlook/scripts/outlook-setup.sh`
Expected: no output, exit 0.

- [ ] **Step 7: Verify reuse-detection logic against a temp HOME (no network)**

Run:
```bash
TMP=$(mktemp -d); mkdir -p "$TMP/.outlook/default"
echo '{"client_id":"abc","client_secret":"sec"}' > "$TMP/.outlook/default/config.json"
echo '{"access_token":"a"}' > "$TMP/.outlook/default/credentials.json"
BASE_DIR="$TMP/.outlook"; CONFIG_DIR="$BASE_DIR/work"; REUSE_CONFIG=""
for dir in "$BASE_DIR"/*/; do o="$dir/config.json"; [ "$dir" = "$CONFIG_DIR/" ] && continue; [ -f "$o" ] && { REUSE_CONFIG="$o"; break; }; done
echo "REUSE_CONFIG=$REUSE_CONFIG"
jq -r '.client_id' "$REUSE_CONFIG"
rm -rf "$TMP"
```
Expected: `REUSE_CONFIG` points at `default/config.json`; `client_id` prints `abc`.

- [ ] **Step 8: Commit**

```bash
git add outlook/scripts/outlook-setup.sh
git commit -m "feat(outlook): per-account setup with reusable app registration"
```

---

## Task 6: Documentation updates

**Files:**
- Modify: `outlook/SKILL.md`
- Modify: `outlook/README.md`
- Modify: `CLAUDE.md` (root)

- [ ] **Step 1: Document account selection in `outlook/SKILL.md`**

Add a short "Multiple accounts" subsection near the top of the usage instructions:

```markdown
## Multiple accounts

All scripts accept an account selector. Precedence: `--account`/`-a` flag, then the
`OUTLOOK_ACCOUNT` env var, then `default`.

```bash
outlook-mail.sh inbox                 # default account
outlook-mail.sh -a work inbox         # 'work' account
OUTLOOK_ACCOUNT=work outlook-mail.sh inbox
outlook-token.sh list                 # list configured accounts
outlook-setup.sh --account work       # add a new account (reuses existing app reg)
```

Credentials live under `~/.outlook/<account>/`. An existing single-account install is
migrated automatically to `~/.outlook/default/` on first run.

Calendar timezone is auto-detected from the system; override with `OUTLOOK_TZ`
(e.g. `OUTLOOK_TZ=America/New_York`).
```

- [ ] **Step 2: Add multi-account note to `outlook/README.md`**

Under the existing setup/usage section, add the same account-selector examples and note that credentials are stored per-account under `~/.outlook/<account>/`, with automatic migration of legacy installs to `default/`.

- [ ] **Step 3: Update root `CLAUDE.md` credentials note**

In the Credentials table row for Outlook, change the location to `~/.outlook/<account>/` and (if a one-line description exists) note multi-account support. No structural tree change is needed.

- [ ] **Step 4: Commit**

```bash
git add outlook/SKILL.md outlook/README.md CLAUDE.md
git commit -m "docs(outlook): document multi-account, list, and timezone override"
```

---

## Task 7: Live end-to-end test against a second mailbox

**Files:** none (manual verification).

- [ ] **Step 1: Confirm the existing account still works post-migration**

Run:
```bash
outlook/scripts/outlook-token.sh status
outlook/scripts/outlook-token.sh list
```
Expected: `status` shows Connected for the migrated `default` account; `list` shows `- default`.

- [ ] **Step 2: Configure the user's second mailbox (interactive OAuth)**

Run `outlook/scripts/outlook-setup.sh --account <name>` and walk the user through the
reuse-app prompt (accept reuse) and the browser sign-in / paste-redirect-URL step.

- [ ] **Step 3: Verify the second account end-to-end (read-only)**

Run:
```bash
outlook/scripts/outlook-token.sh --account <name> test
outlook/scripts/outlook-mail.sh --account <name> inbox 5
```
Expected: connection test succeeds; inbox lists messages for the second mailbox.

- [ ] **Step 4: Confirm both accounts coexist**

Run: `outlook/scripts/outlook-token.sh list`
Expected: both `default` and `<name>` listed.

---

## Self-Review Notes

- **Spec coverage:** layout/migration (Tasks 1-5 header), `list` (Task 1), setup reuse-app
  (Task 5), path-traversal (Task 3), timezone (Task 4), docs (Task 6), live test (Task 7) —
  all spec sections covered.
- **Token auto-refresh preserved:** Tasks 2/4 only swap the path block; `ensure_valid_token()`
  is untouched and now reads the per-account `CONFIG_FILE`/`CREDS_FILE`.
- **Consistency:** the migration block and `CONFIG_DIR`/`CONFIG_FILE`/`CREDS_FILE` names are
  identical across all four scripts; `ID_CACHE_FILE` added only where used (mail).
