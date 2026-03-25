# Outlook Skill: Alternate Sender (`--from`) Flag

## Problem

The Outlook skill can only send emails from the authenticated user's primary email address. Users with configured aliases (e.g. `support@company.com`) cannot send from those addresses.

## Solution

Add an optional `--from <email>` flag to all email-sending commands. When omitted, behaviour is unchanged (Graph API defaults to the primary address). When provided, the specified alias is set as the sender in the Graph API payload.

## Affected Commands

| Command | How `--from` is applied |
|---------|------------------------|
| `draft` | Added to the JSON payload in `POST /me/messages` |
| `mddraft` | Added to the JSON payload in `POST /me/messages` |
| `reply` | PATCH applied to the reply draft after `createReply` |
| `mdreply` | Added to the existing PATCH payload after `createReply` |
| `followup` | Added to the existing PATCH payload after `createReply` |

The `send` command is unchanged — it just sends an existing draft with no payload.

## Usage

```bash
# With --from (optional, always first arg after command)
outlook-mail.sh draft --from "support@company.com" "to@example.com" "Subject" "Body"
outlook-mail.sh mddraft --from "support@company.com" "to@example.com" "Subject" "# Markdown"
outlook-mail.sh reply --from "support@company.com" <message-id> "Reply body"
outlook-mail.sh mdreply --from "support@company.com" <message-id> "Reply body"
outlook-mail.sh followup --from "support@company.com" <sent-message-id> "Follow-up body"

# Without --from (unchanged behaviour)
outlook-mail.sh draft "to@example.com" "Subject" "Body"
```

## Implementation Details

### 1. Helper function: `parse_from_flag()`

Added near the top of `outlook-mail.sh`, before the `case` block. Scans the argument list for `--from <address>`, sets a global `FROM_ADDRESS` variable, and shifts the remaining positional args.

```bash
FROM_ADDRESS=""

parse_from_flag() {
    FROM_ADDRESS=""
    local args=()
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --from)
                FROM_ADDRESS="$2"
                shift 2
                ;;
            *)
                args+=("$1")
                shift
                ;;
        esac
    done
    REMAINING_ARGS=("${args[@]}")
}
```

### 2. `draft` command

Call `parse_from_flag` with args after the command name. Build the jq payload conditionally:

- If `FROM_ADDRESS` is set: include `from: {emailAddress: {address: $from}}` in the payload
- If not set: payload is identical to today

### 3. `mddraft` command

Same approach as `draft` — conditional `from` field in the payload.

### 4. `reply` command

After `createReply` returns the reply draft, if `FROM_ADDRESS` is set, PATCH the draft with:

```json
{"from": {"emailAddress": {"address": "support@company.com"}}}
```

### 5. `mdreply` command

Already PATCHes the draft to set the HTML body. Add the `from` field to that same PATCH payload when `FROM_ADDRESS` is set.

### 6. `followup` command

Same as `mdreply` — add `from` to the existing PATCH payload.

### 7. `update` command

Add `from` as a new field option:

```bash
outlook-mail.sh update <draft-id> from "support@company.com"
```

This lets users change the sender on an existing draft.

### 8. Documentation updates

- **SKILL.md**: Add `--from` flag to usage examples for all sending commands
- **README.md**: Mention alternate sender alias support

## Prerequisites

The alias must be configured on the user's Microsoft 365 account by an admin. The Graph API will reject `from` addresses the account is not authorised to send as.

No new OAuth scopes or permissions are required — `Mail.Send` already covers send-as for configured aliases.

## What doesn't change

- `send` command (no payload, just triggers send on an existing draft)
- Token management and OAuth flow
- Config files (`~/.outlook/config.json`, `~/.outlook/credentials.json`)
- All read-only commands (inbox, unread, read, etc.)
- Default behaviour when `--from` is omitted
