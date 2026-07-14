#!/bin/bash
# Install Codex skills from this repo.
#
# Usage:
#   ./install-codex.sh              # Install all skills (interactive)
#   ./install-codex.sh --all        # Install all skills (no prompts)
#   ./install-codex.sh garmin       # Install specific skill(s)
#
# Skill directories are installed into ~/.codex/skills/. Each installed
# skill keeps the source directory live via symlinks, while SKILL.md is
# generated with Codex-local paths so the instructions execute correctly.

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="$HOME/.codex/skills"

# Note: outlook and trello moved to their own repos under github.com/dbhq-uk (Jul 2026)
AVAILABLE_SKILLS=(pst-to-markdown garmin humanize)

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${BLUE}==>${NC} $*"; }
ok()    { echo -e "${GREEN}✓${NC} $*"; }
warn()  { echo -e "${YELLOW}!${NC} $*"; }
err()   { echo -e "${RED}✗${NC} $*"; }

check_deps_pst_to_markdown() {
    if ! command -v python3 &>/dev/null; then
        err "Missing dependency for pst-to-markdown: python3"
        return 1
    fi
    if ! command -v readpst &>/dev/null; then
        warn "readpst not found (optional — needed if libratom fails)"
        echo "    Ubuntu/Debian: sudo apt install pst-utils"
        echo "    macOS: brew install libpst"
    fi
    return 0
}

check_deps_garmin() {
    if ! command -v python3 &>/dev/null; then
        err "Missing dependency for garmin: python3"
        return 1
    fi
    return 0
}

check_deps_humanize() {
    if ! command -v python3 &>/dev/null; then
        err "Missing dependency for humanize: python3"
        return 1
    fi
    return 0
}

check_deps() {
    local skill="$1"
    case "$skill" in
        pst-to-markdown) check_deps_pst_to_markdown ;;
        garmin)         check_deps_garmin ;;
        humanize)       check_deps_humanize ;;
        *)              return 0 ;;
    esac
}

sync_skill_entries() {
    local skill="$1"
    local source="$REPO_DIR/$skill"
    local target="$SKILLS_DIR/$skill"
    local entry

    mkdir -p "$target"
    find "$target" -mindepth 1 -maxdepth 1 ! -name 'SKILL.md' -exec rm -rf {} +

    for entry in "$source"/* "$source"/.[!.]* "$source"/..?*; do
        [ -e "$entry" ] || continue
        if [ "$(basename "$entry")" = "SKILL.md" ]; then
            continue
        fi
        ln -s "$entry" "$target/$(basename "$entry")"
    done
}

generate_codex_skill_md() {
    local skill="$1"
    local source="$REPO_DIR/$skill/SKILL.md"
    local target="$SKILLS_DIR/$skill/SKILL.md"

    sed \
        -e 's|~/.claude/skills/|~/.codex/skills/|g' \
        -e 's|Claude Code|Codex|g' \
        -e 's|Claude runs|Codex runs|g' \
        -e 's|Claude reads|Codex reads|g' \
        "$source" > "$target"
}

install_skill() {
    local skill="$1"
    local source="$REPO_DIR/$skill"
    local target="$SKILLS_DIR/$skill"

    echo
    info "Installing ${BOLD}$skill${NC}"

    if [ ! -d "$source" ] || [ ! -f "$source/SKILL.md" ]; then
        err "$skill: not found or missing SKILL.md"
        return 1
    fi

    if ! check_deps "$skill"; then
        warn "Skipping $skill (missing dependencies)"
        return 1
    fi

    if [ -L "$target" ]; then
        rm "$target"
    elif [ -d "$target" ]; then
        warn "Existing directory at $target"
        if [ "$AUTO" = "1" ]; then
            info "Replacing existing install (--all mode)"
        else
            read -p "    Replace it? (y/N): " replace
            if [[ ! "$replace" =~ ^[Yy]$ ]]; then
                warn "Skipped $skill"
                return 0
            fi
        fi
        rm -rf "$target"
    fi

    mkdir -p "$SKILLS_DIR"
    sync_skill_entries "$skill"
    generate_codex_skill_md "$skill"
    ok "$skill installed in $target"

    post_install "$skill"
    sync_skill_entries "$skill"
    generate_codex_skill_md "$skill"
}

post_install() {
    local skill="$1"

    case "$skill" in
        pst-to-markdown)
            chmod +x "$REPO_DIR/pst-to-markdown/setup.sh" 2>/dev/null || true
            chmod +x "$REPO_DIR/pst-to-markdown/scripts/extract_pst.py" 2>/dev/null || true

            if [ ! -d "$REPO_DIR/pst-to-markdown/.venv" ]; then
                info "Setting up Python virtual environment..."
                "$REPO_DIR/pst-to-markdown/setup.sh"
            else
                ok "Python venv already exists"
                "$REPO_DIR/pst-to-markdown/.venv/bin/pip" install -r "$REPO_DIR/pst-to-markdown/requirements.txt" -q 2>/dev/null || true
            fi
            ;;


        garmin)
            chmod +x "$REPO_DIR/garmin/scripts/setup.sh" 2>/dev/null || true

            if [ ! -d "$REPO_DIR/garmin/.venv" ]; then
                info "Setting up Python virtual environment..."
                python3 -m venv "$REPO_DIR/garmin/.venv"
                "$REPO_DIR/garmin/.venv/bin/pip" install --upgrade pip -q
                "$REPO_DIR/garmin/.venv/bin/pip" install -r "$REPO_DIR/garmin/requirements.txt" -q
            else
                ok "Python venv already exists"
                "$REPO_DIR/garmin/.venv/bin/pip" install -r "$REPO_DIR/garmin/requirements.txt" -q 2>/dev/null || true
            fi

            if [ -f "$HOME/.garmin/config.json" ]; then
                ok "Garmin credentials found"
            else
                warn "No Garmin credentials — run: ~/.codex/skills/garmin/scripts/setup.sh"
            fi
            ;;

        humanize)
            chmod +x "$REPO_DIR/humanize/scripts/setup.sh" 2>/dev/null || true
            chmod +x "$REPO_DIR/humanize/scripts/humanize-api.py" 2>/dev/null || true

            if [ ! -d "$REPO_DIR/humanize/.venv" ]; then
                info "Setting up Python virtual environment..."
                python3 -m venv "$REPO_DIR/humanize/.venv"
                "$REPO_DIR/humanize/.venv/bin/pip" install --upgrade pip -q
                "$REPO_DIR/humanize/.venv/bin/pip" install -r "$REPO_DIR/humanize/requirements.txt" -q
            else
                ok "Python venv already exists"
                "$REPO_DIR/humanize/.venv/bin/pip" install -r "$REPO_DIR/humanize/requirements.txt" -q 2>/dev/null || true
            fi

            if [ -f "$HOME/.humanize/config.json" ]; then
                ok "Humanize API config found"
            else
                info "No commercial API configured (optional) -- run: ~/.codex/skills/humanize/scripts/setup.sh"
            fi
            ;;
    esac
}

AUTO=0
REQUESTED_SKILLS=()

for arg in "$@"; do
    case "$arg" in
        --all|-a)
            AUTO=1
            ;;
        --help|-h)
            echo "Usage: $0 [--all] [skill ...]"
            echo
            echo "Available skills: ${AVAILABLE_SKILLS[*]}"
            echo
            echo "Options:"
            echo "  --all, -a    Install all skills without prompts"
            echo "  --help, -h   Show this help"
            echo
            echo "Examples:"
            echo "  $0                    # Interactive — choose which skills to install"
            echo "  $0 --all              # Install everything"
            echo "  $0 garmin humanize        # Install specific skills"
            exit 0
            ;;
        *)
            REQUESTED_SKILLS+=("$arg")
            ;;
    esac
done

echo
echo -e "${BOLD}=== Codex Skills Installer ===${NC}"
echo -e "Repo:   $REPO_DIR"
echo -e "Target: $SKILLS_DIR"

if [ "$AUTO" = "1" ]; then
    REQUESTED_SKILLS=("${AVAILABLE_SKILLS[@]}")
elif [ ${#REQUESTED_SKILLS[@]} -eq 0 ]; then
    echo
    echo "Available skills:"
    for i in "${!AVAILABLE_SKILLS[@]}"; do
        skill="${AVAILABLE_SKILLS[$i]}"
        status=""
        if [ -d "$SKILLS_DIR/$skill" ]; then
            status=" ${GREEN}(installed)${NC}"
        fi
        echo -e "  $((i+1)). $skill$status"
    done
    echo
    read -p "Install all? (Y/n): " install_all
    if [[ "$install_all" =~ ^[Nn]$ ]]; then
        read -p "Which skills? (space-separated, e.g. 'garmin humanize'): " -a REQUESTED_SKILLS
        if [ ${#REQUESTED_SKILLS[@]} -eq 0 ]; then
            echo "Nothing selected. Exiting."
            exit 0
        fi
    else
        REQUESTED_SKILLS=("${AVAILABLE_SKILLS[@]}")
    fi
fi

for skill in "${REQUESTED_SKILLS[@]}"; do
    found=0
    for available in "${AVAILABLE_SKILLS[@]}"; do
        if [ "$skill" = "$available" ]; then
            found=1
            break
        fi
    done
    if [ "$found" = "0" ]; then
        err "Unknown skill: $skill"
        echo "Available: ${AVAILABLE_SKILLS[*]}"
        exit 1
    fi
done

INSTALLED=0
FAILED=0
for skill in "${REQUESTED_SKILLS[@]}"; do
    if install_skill "$skill"; then
        INSTALLED=$((INSTALLED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
done

echo
echo -e "${BOLD}=== Done ===${NC}"
echo -e "  Installed: ${GREEN}$INSTALLED${NC}"
[ "$FAILED" -gt 0 ] && echo -e "  Skipped:   ${YELLOW}$FAILED${NC}"
echo
echo "Skills are installed into ~/.codex/skills."
echo "Re-run this script after pulling updates to refresh generated SKILL.md files."
echo
