# Outlook `--from` Flag Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional `--from <email>` flag to all email-sending commands so users can send from configured aliases.

**Architecture:** A shared `parse_from_flag()` helper extracts `--from` from the argument list. Each sending command calls it, then conditionally injects a `from` field into the Graph API payload. For `draft`/`mddraft` this goes in the initial POST; for `reply`/`mdreply`/`followup` it's added via PATCH after `createReply`.

**Tech Stack:** Bash, jq, Microsoft Graph API v1.0

**Spec:** `docs/superpowers/specs/2026-03-25-outlook-from-flag-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `outlook/scripts/outlook-mail.sh` | Modify | Add helper function and update 6 commands |
| `outlook/SKILL.md` | Modify | Document `--from` flag in usage examples and workflows |
| `outlook/README.md` | Modify | Add `--from` to email command examples |

---

### Task 1: Add `parse_from_flag()` helper function

**Files:**
- Modify: `outlook/scripts/outlook-mail.sh` (insert after line 87, after the `api_call` function)

- [ ] **Step 1: Add the helper function**

Insert after the `api_call()` function (line 87) and before `cache_message_ids()` (line 89):

```bash
# Parse optional --from flag from argument list.
# Sets FROM_ADDRESS and REMAINING_ARGS globals.
FROM_ADDRESS=""
REMAINING_ARGS=()

parse_from_flag() {
    FROM_ADDRESS=""
    local args=()
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --from)
                if [[ -z "${2:-}" ]]; then
                    echo "Error: --from requires an email address" >&2
                    exit 1
                fi
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

- [ ] **Step 2: Verify the script still parses correctly**

Run: `bash -n outlook/scripts/outlook-mail.sh`
Expected: No output (no syntax errors)

- [ ] **Step 3: Commit**

```bash
git add outlook/scripts/outlook-mail.sh
git commit -m "feat(outlook): add parse_from_flag helper function"
```

---

### Task 2: Update `draft` command

**Files:**
- Modify: `outlook/scripts/outlook-mail.sh:309-351` (the `draft)` case branch)

- [ ] **Step 1: Replace the `draft` case branch**

Replace lines 309-351 (the entire `draft)` block up to `;;`) with:

```bash
    draft)
        parse_from_flag "${@:2}"
        to="${REMAINING_ARGS[0]}"
        subject="${REMAINING_ARGS[1]}"
        body="${REMAINING_ARGS[2]:-}"
        if [ -z "$to" ] || [ -z "$subject" ]; then
            echo "Usage: outlook-mail.sh draft [--from <email>] <to-email> <subject> <body>"
            exit 1
        fi

        echo "Creating draft..."
        if [[ -n "$FROM_ADDRESS" ]]; then
            payload=$(jq -n \
                --arg to "$to" \
                --arg subject "$subject" \
                --arg body "${body:-}" \
                --arg from "$FROM_ADDRESS" \
                '{
                    subject: $subject,
                    body: {
                        contentType: "Text",
                        content: $body
                    },
                    toRecipients: [
                        {
                            emailAddress: {
                                address: $to
                            }
                        }
                    ],
                    from: {
                        emailAddress: {
                            address: $from
                        }
                    }
                }')
        else
            payload=$(jq -n \
                --arg to "$to" \
                --arg subject "$subject" \
                --arg body "${body:-}" \
                '{
                    subject: $subject,
                    body: {
                        contentType: "Text",
                        content: $body
                    },
                    toRecipients: [
                        {
                            emailAddress: {
                                address: $to
                            }
                        }
                    ]
                }')
        fi

        result=$(api_call POST "/me/messages" "$payload")
        draft_id=$(echo "$result" | jq -r '.id')

        if [ -z "$draft_id" ] || [ "$draft_id" = "null" ]; then
            echo "Error creating draft:"
            echo "$result" | jq -r '.error.message // .'
            exit 1
        fi

        echo "Draft created!"
        echo "Draft ID: ${draft_id: -20}"
        if [[ -n "$FROM_ADDRESS" ]]; then
            echo "From: $FROM_ADDRESS (validated on send)"
        fi
        echo
        echo "$result" | jq -r '"To: \(.toRecipients[0].emailAddress.address)", "Subject: \(.subject)", "Body: \(.body.content)"'
        ;;
```

- [ ] **Step 2: Verify syntax**

Run: `bash -n outlook/scripts/outlook-mail.sh`
Expected: No output (no syntax errors)

- [ ] **Step 3: Commit**

```bash
git add outlook/scripts/outlook-mail.sh
git commit -m "feat(outlook): add --from flag to draft command"
```

---

### Task 3: Update `mddraft` command

**Files:**
- Modify: `outlook/scripts/outlook-mail.sh:353-411` (the `mddraft)` case branch)

- [ ] **Step 1: Replace the `mddraft` case branch**

Replace lines 353-411 (the entire `mddraft)` block up to `;;`) with:

```bash
    mddraft)
        parse_from_flag "${@:2}"
        to="${REMAINING_ARGS[0]}"
        subject="${REMAINING_ARGS[1]}"
        body="${REMAINING_ARGS[2]:-}"
        if [ -z "$to" ] || [ -z "$subject" ]; then
            echo "Usage: outlook-mail.sh mddraft [--from <email>] <to-email> <subject> <markdown-body>"
            exit 1
        fi

        # Check for pandoc
        if ! command -v pandoc &> /dev/null; then
            echo "Error: pandoc is required for markdown conversion"
            echo "Install with: brew install pandoc (macOS) or apt install pandoc (Linux)"
            exit 1
        fi

        echo "Creating markdown draft..."

        # Convert markdown to HTML
        html_body=$(echo "${body:-}" | pandoc -f markdown -t html)

        # Wrap in basic email-friendly HTML structure
        html_body="<html><body style=\"font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 14px; line-height: 1.5; color: #333;\">
${html_body}
</body></html>"

        if [[ -n "$FROM_ADDRESS" ]]; then
            payload=$(jq -n \
                --arg to "$to" \
                --arg subject "$subject" \
                --arg body "$html_body" \
                --arg from "$FROM_ADDRESS" \
                '{
                    subject: $subject,
                    body: {
                        contentType: "HTML",
                        content: $body
                    },
                    toRecipients: [
                        {
                            emailAddress: {
                                address: $to
                            }
                        }
                    ],
                    from: {
                        emailAddress: {
                            address: $from
                        }
                    }
                }')
        else
            payload=$(jq -n \
                --arg to "$to" \
                --arg subject "$subject" \
                --arg body "$html_body" \
                '{
                    subject: $subject,
                    body: {
                        contentType: "HTML",
                        content: $body
                    },
                    toRecipients: [
                        {
                            emailAddress: {
                                address: $to
                            }
                        }
                    ]
                }')
        fi

        result=$(api_call POST "/me/messages" "$payload")
        draft_id=$(echo "$result" | jq -r '.id')

        if [ -z "$draft_id" ] || [ "$draft_id" = "null" ]; then
            echo "Error creating draft:"
            echo "$result" | jq -r '.error.message // .'
            exit 1
        fi

        echo "Draft created (HTML from Markdown)!"
        echo "Draft ID: ${draft_id: -20}"
        if [[ -n "$FROM_ADDRESS" ]]; then
            echo "From: $FROM_ADDRESS (validated on send)"
        fi
        echo
        echo "$result" | jq -r '"To: \(.toRecipients[0].emailAddress.address)", "Subject: \(.subject)"'
        ;;
```

- [ ] **Step 2: Verify syntax**

Run: `bash -n outlook/scripts/outlook-mail.sh`
Expected: No output (no syntax errors)

- [ ] **Step 3: Commit**

```bash
git add outlook/scripts/outlook-mail.sh
git commit -m "feat(outlook): add --from flag to mddraft command"
```

---

### Task 4: Update `reply` command

**Files:**
- Modify: `outlook/scripts/outlook-mail.sh:413-443` (the `reply)` case branch)

- [ ] **Step 1: Replace the `reply` case branch**

Replace lines 413-443 (the entire `reply)` block up to `;;`) with:

```bash
    reply)
        parse_from_flag "${@:2}"
        msg_id="${REMAINING_ARGS[0]}"
        body="${REMAINING_ARGS[1]}"
        if [ -z "$msg_id" ] || [ -z "$body" ]; then
            echo "Usage: outlook-mail.sh reply [--from <email>] <message-id> <body>"
            exit 1
        fi

        # Resolve short ID to full ID
        if ! msg_id=$(resolve_message_id "$msg_id" "messages"); then
            echo "Error: Message not found with ID: ${REMAINING_ARGS[0]}"
            exit 1
        fi

        echo "Creating reply draft..."
        payload=$(jq -n --arg body "$body" '{comment: $body}')

        result=$(api_call POST "/me/messages/$msg_id/createReply" "$payload")
        draft_id=$(echo "$result" | jq -r '.id')

        if [ -z "$draft_id" ] || [ "$draft_id" = "null" ]; then
            echo "Error creating reply:"
            echo "$result" | jq -r '.error.message // .'
            exit 1
        fi

        # Set from address if specified
        if [[ -n "$FROM_ADDRESS" ]]; then
            from_payload=$(jq -n --arg from "$FROM_ADDRESS" '{from: {emailAddress: {address: $from}}}')
            api_call PATCH "/me/messages/$draft_id" "$from_payload" > /dev/null
        fi

        echo "Reply draft created!"
        echo "Draft ID: ${draft_id: -20}"
        if [[ -n "$FROM_ADDRESS" ]]; then
            echo "From: $FROM_ADDRESS (validated on send)"
        fi
        echo
        echo "$result" | jq -r '"To: \(.toRecipients[0].emailAddress.address)", "Subject: \(.subject)"'
        ;;
```

- [ ] **Step 2: Verify syntax**

Run: `bash -n outlook/scripts/outlook-mail.sh`
Expected: No output (no syntax errors)

- [ ] **Step 3: Commit**

```bash
git add outlook/scripts/outlook-mail.sh
git commit -m "feat(outlook): add --from flag to reply command"
```

---

### Task 5: Update `mdreply` command

**Files:**
- Modify: `outlook/scripts/outlook-mail.sh:548-616` (the `mdreply)` case branch)

- [ ] **Step 1: Replace the `mdreply` case branch**

Replace lines 548-616 (the entire `mdreply)` block up to `;;`) with:

```bash
    mdreply)
        parse_from_flag "${@:2}"
        msg_id="${REMAINING_ARGS[0]}"
        body="${REMAINING_ARGS[1]}"
        if [ -z "$msg_id" ] || [ -z "$body" ]; then
            echo "Usage: outlook-mail.sh mdreply [--from <email>] <message-id> <markdown-body>"
            exit 1
        fi

        # Check for pandoc
        if ! command -v pandoc &> /dev/null; then
            echo "Error: pandoc is required for markdown conversion"
            echo "Install with: brew install pandoc (macOS) or apt install pandoc (Linux)"
            exit 1
        fi

        # Resolve short ID to full ID
        if ! msg_id=$(resolve_message_id "$msg_id" "messages"); then
            echo "Error: Message not found with ID: ${REMAINING_ARGS[0]}"
            exit 1
        fi

        echo "Creating reply draft with markdown formatting..."

        # Step 1: Create reply draft (empty comment to get thread headers)
        result=$(api_call POST "/me/messages/$msg_id/createReply" '{}')
        draft_id=$(echo "$result" | jq -r '.id')

        if [ -z "$draft_id" ] || [ "$draft_id" = "null" ]; then
            echo "Error creating reply:"
            echo "$result" | jq -r '.error.message // .'
            exit 1
        fi

        # Step 2: Get the existing body (contains the quoted thread)
        existing_body=$(echo "$result" | jq -r '.body.content // ""')

        # Step 3: Convert markdown to HTML
        html_body=$(echo "$body" | pandoc -f markdown -t html)

        # Wrap reply in styled div and prepend to existing thread
        combined_body="<div style=\"font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 14px; line-height: 1.6; color: #333;\">
${html_body}
</div>
<br/>
${existing_body}"

        # Step 4: PATCH the draft to update body (and from address if specified)
        if [[ -n "$FROM_ADDRESS" ]]; then
            patch_payload=$(jq -n \
                --arg body "$combined_body" \
                --arg from "$FROM_ADDRESS" \
                '{
                    body: {
                        contentType: "HTML",
                        content: $body
                    },
                    from: {
                        emailAddress: {
                            address: $from
                        }
                    }
                }')
        else
            patch_payload=$(jq -n \
                --arg body "$combined_body" \
                '{
                    body: {
                        contentType: "HTML",
                        content: $body
                    }
                }')
        fi

        patch_result=$(api_call PATCH "/me/messages/$draft_id" "$patch_payload")

        if echo "$patch_result" | jq -e '.error' > /dev/null 2>&1; then
            echo "Error updating draft body:"
            echo "$patch_result" | jq -r '.error.message'
            exit 1
        fi

        echo "Reply draft created (HTML from Markdown)!"
        echo "Draft ID: ${draft_id: -20}"
        if [[ -n "$FROM_ADDRESS" ]]; then
            echo "From: $FROM_ADDRESS (validated on send)"
        fi
        echo
        echo "$patch_result" | jq -r '"To: \(.toRecipients[0].emailAddress.address)", "Subject: \(.subject)"'
        ;;
```

- [ ] **Step 2: Verify syntax**

Run: `bash -n outlook/scripts/outlook-mail.sh`
Expected: No output (no syntax errors)

- [ ] **Step 3: Commit**

```bash
git add outlook/scripts/outlook-mail.sh
git commit -m "feat(outlook): add --from flag to mdreply command"
```

---

### Task 6: Update `followup` command

**Files:**
- Modify: `outlook/scripts/outlook-mail.sh:618-699` (the `followup)` case branch)

- [ ] **Step 1: Replace the `followup` case branch**

Replace lines 618-699 (the entire `followup)` block up to `;;`) with:

```bash
    followup)
        parse_from_flag "${@:2}"
        msg_id="${REMAINING_ARGS[0]}"
        body="${REMAINING_ARGS[1]}"
        if [ -z "$msg_id" ]; then
            echo "Usage: outlook-mail.sh followup [--from <email>] <sent-message-id> [markdown-body]"
            echo "       Creates a follow-up reply to your own sent email (chaser)"
            echo "       Body defaults to a standard follow-up message if not provided"
            exit 1
        fi

        # Check for pandoc
        if ! command -v pandoc &> /dev/null; then
            echo "Error: pandoc is required for markdown conversion"
            echo "Install with: brew install pandoc (macOS) or apt install pandoc (Linux)"
            exit 1
        fi

        # Resolve short ID from sent items folder
        if ! msg_id=$(resolve_message_id "$msg_id" "sentitems"); then
            echo "Error: Sent message not found with ID: ${REMAINING_ARGS[0]}"
            exit 1
        fi

        # Default follow-up body if not provided
        if [ -z "$body" ]; then
            body="Hi,

Just following up on my email below.

Please let me know if you have any questions or need any additional information."
        fi

        echo "Creating follow-up draft for sent message..."

        # Step 1: Create reply draft using replyAll to include all original recipients
        result=$(api_call POST "/me/messages/$msg_id/createReply" '{}')
        draft_id=$(echo "$result" | jq -r '.id')

        if [ -z "$draft_id" ] || [ "$draft_id" = "null" ]; then
            echo "Error creating follow-up:"
            echo "$result" | jq -r '.error.message // .'
            exit 1
        fi

        # Step 2: Get the existing body (contains the quoted thread)
        existing_body=$(echo "$result" | jq -r '.body.content // ""')

        # Step 3: Convert markdown to HTML
        html_body=$(echo "$body" | pandoc -f markdown -t html)

        # Wrap reply in styled div and prepend to existing thread
        combined_body="<div style=\"font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 14px; line-height: 1.6; color: #333;\">
${html_body}
</div>
<br/>
${existing_body}"

        # Step 4: PATCH the draft to update body (and from address if specified)
        if [[ -n "$FROM_ADDRESS" ]]; then
            patch_payload=$(jq -n \
                --arg body "$combined_body" \
                --arg from "$FROM_ADDRESS" \
                '{
                    body: {
                        contentType: "HTML",
                        content: $body
                    },
                    from: {
                        emailAddress: {
                            address: $from
                        }
                    }
                }')
        else
            patch_payload=$(jq -n \
                --arg body "$combined_body" \
                '{
                    body: {
                        contentType: "HTML",
                        content: $body
                    }
                }')
        fi

        patch_result=$(api_call PATCH "/me/messages/$draft_id" "$patch_payload")

        if echo "$patch_result" | jq -e '.error' > /dev/null 2>&1; then
            echo "Error updating draft body:"
            echo "$patch_result" | jq -r '.error.message'
            exit 1
        fi

        echo "Follow-up draft created!"
        echo "Draft ID: ${draft_id: -20}"
        if [[ -n "$FROM_ADDRESS" ]]; then
            echo "From: $FROM_ADDRESS (validated on send)"
        fi
        echo
        echo "$patch_result" | jq -r '"To: \(.toRecipients[0].emailAddress.address)", "Subject: \(.subject)"'
        echo
        echo "Use 'outlook-mail.sh send ${draft_id: -20}' to send"
        ;;
```

- [ ] **Step 2: Verify syntax**

Run: `bash -n outlook/scripts/outlook-mail.sh`
Expected: No output (no syntax errors)

- [ ] **Step 3: Commit**

```bash
git add outlook/scripts/outlook-mail.sh
git commit -m "feat(outlook): add --from flag to followup command"
```

---

### Task 7: Add `from` field to `update` command

**Files:**
- Modify: `outlook/scripts/outlook-mail.sh:445-546` (the `update)` case branch)

- [ ] **Step 1: Add `from` case to the update field switch**

In the `update)` case branch, add a new case for `from` after the `bcc)` case (after line 528) and before the `*)` fallback:

```bash
            from)
                if [ -z "$value" ]; then
                    echo "Error: Email address required"
                    exit 1
                fi
                echo "Updating sender address..."
                payload=$(jq -n --arg email "$value" '{from: {emailAddress: {address: $email}}}')
                ;;
```

- [ ] **Step 2: Update the usage help text**

In the `update)` branch, find the help text block (lines 452-458) and add a `from` line. Change:

```bash
            echo "  bcc <email>        Add BCC recipient"
```

to:

```bash
            echo "  bcc <email>        Add BCC recipient"
            echo "  from <email>       Set sender address (alias)"
```

- [ ] **Step 3: Update the error message for unknown fields**

Find the `*)` fallback (line 531) and change:

```bash
                echo "Valid fields: subject, body, mdbody, to, cc, bcc"
```

to:

```bash
                echo "Valid fields: subject, body, mdbody, to, cc, bcc, from"
```

- [ ] **Step 4: Verify syntax**

Run: `bash -n outlook/scripts/outlook-mail.sh`
Expected: No output (no syntax errors)

- [ ] **Step 5: Commit**

```bash
git add outlook/scripts/outlook-mail.sh
git commit -m "feat(outlook): add from field to update command"
```

---

### Task 8: Update SKILL.md documentation

**Files:**
- Modify: `outlook/SKILL.md`

- [ ] **Step 1: Update the "Sending Email" section**

In `outlook/SKILL.md`, find the "Sending Email" code block (lines 56-89). Add `--from` examples after the existing commands. After line 58 (`# Create plain text draft`), add a `--from` variant. Update the section to show:

```bash
# Create plain text draft
~/.claude/skills/outlook/scripts/outlook-mail.sh draft "recipient@example.com" "Subject" "Body text"

# Create draft from an alias address
~/.claude/skills/outlook/scripts/outlook-mail.sh draft --from "alias@example.com" "recipient@example.com" "Subject" "Body text"

# Create markdown-formatted draft (converts to HTML)
~/.claude/skills/outlook/scripts/outlook-mail.sh mddraft "recipient@example.com" "Subject" "**Bold** and _italic_ text"

# Send a draft (use draft ID)
~/.claude/skills/outlook/scripts/outlook-mail.sh send <draft-id>

# Reply to a message (plain text - creates draft)
~/.claude/skills/outlook/scripts/outlook-mail.sh reply <message-id> "Reply body"

# Reply from an alias address
~/.claude/skills/outlook/scripts/outlook-mail.sh reply --from "alias@example.com" <message-id> "Reply body"

# Reply with markdown formatting (converts to HTML - creates draft)
~/.claude/skills/outlook/scripts/outlook-mail.sh mdreply <message-id> "**Bold** reply with _formatting_"

# Send reply draft
~/.claude/skills/outlook/scripts/outlook-mail.sh send <reply-draft-id>

# Follow up on your own sent email (chaser)
~/.claude/skills/outlook/scripts/outlook-mail.sh followup <sent-message-id>
~/.claude/skills/outlook/scripts/outlook-mail.sh followup <sent-message-id> "Custom follow-up body in **markdown**"

# Update an existing draft
~/.claude/skills/outlook/scripts/outlook-mail.sh update <draft-id> subject "New subject line"
~/.claude/skills/outlook/scripts/outlook-mail.sh update <draft-id> body "Plain text body"
~/.claude/skills/outlook/scripts/outlook-mail.sh update <draft-id> mdbody "**Markdown** body"
~/.claude/skills/outlook/scripts/outlook-mail.sh update <draft-id> to "new-recipient@example.com"
~/.claude/skills/outlook/scripts/outlook-mail.sh update <draft-id> cc "cc@example.com"
~/.claude/skills/outlook/scripts/outlook-mail.sh update <draft-id> bcc "bcc@example.com"
~/.claude/skills/outlook/scripts/outlook-mail.sh update <draft-id> from "alias@example.com"

# List drafts
~/.claude/skills/outlook/scripts/outlook-mail.sh drafts
```

- [ ] **Step 2: Add a note about aliases after the pandoc note (line 91)**

After the existing note about `pandoc`, add:

```markdown
**Note:** The `--from` flag sends from an email alias configured on your Microsoft 365 account. The alias is validated when the email is sent, not when the draft is created. If the address is not a valid alias, the send will fail.
```

- [ ] **Step 3: Add `--from` to the "Sending Email" workflow (lines 237-246)**

Update the workflow to mention the `--from` option. Change step 1 from:

```markdown
1. Create draft with `draft` or `mddraft` command
```

to:

```markdown
1. Create draft with `draft` or `mddraft` command (use `--from` flag to send from an alias)
```

- [ ] **Step 4: Commit**

```bash
git add outlook/SKILL.md
git commit -m "docs(outlook): document --from flag in SKILL.md"
```

---

### Task 9: Update README.md documentation

**Files:**
- Modify: `outlook/README.md`

- [ ] **Step 1: Add `--from` to features list**

In `outlook/README.md`, find the Email features list (lines 8-15). Change:

```markdown
- Create drafts in Outlook (plain text or markdown-formatted)
```

to:

```markdown
- Create drafts in Outlook (plain text or markdown-formatted, with optional alias sender)
```

- [ ] **Step 2: Add `--from` examples to Email Commands**

In the "Email Commands" code block (lines 83-123), after line 103 (`# Create markdown-formatted draft`), add:

```bash
# Send from an alias address (works with draft, mddraft, reply, mdreply, followup)
~/.claude/skills/outlook/scripts/outlook-mail.sh draft --from "alias@example.com" "to@example.com" "Subject" "Body"
```

- [ ] **Step 3: Commit**

```bash
git add outlook/README.md
git commit -m "docs(outlook): document --from flag in README.md"
```
