#!/bin/bash
# Install Claude Code skills from this repo via symlinks
#
# Usage:
#   ./install.sh              # Install all skills (interactive)
#   ./install.sh --all        # Install all skills (no prompts)
#   ./install.sh garmin       # Install specific skill(s)
#   ./install.sh garmin verve
#
# Skills are symlinked into ~/.claude/skills/ so edits to this repo
# are immediately available to Claude Code — no re-install needed.

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="$HOME/.claude/skills"

# All available Claude Code skills (have SKILL.md)
# Note: outlook and trello moved to their own repos under github.com/dbhq-uk (Jul 2026)
AVAILABLE_SKILLS=(garmin verve gpt-image-2)

# Colours
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

# ─── Dependency checks ───────────────────────────────────────────────

check_deps_garmin() {
    if ! command -v python3 &>/dev/null; then
        err "Missing dependency for garmin: python3"
        return 1
    fi
    # post_install provisions the venv directly rather than via the skill's
    # setup.sh, so the 3.12 floor that garminconnect 0.3.x requires has to be
    # enforced here too — otherwise the only symptom is a pip resolver dump.
    if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"; then
        err "garmin needs Python 3.12+ (garminconnect 0.3.x), found $(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
        return 1
    fi
    return 0
}

check_deps_verve() {
    if ! command -v python3 &>/dev/null; then
        err "Missing dependency for verve: python3"
        return 1
    fi
    return 0
}

check_deps_gpt_image_2() {
    if ! command -v python3 &>/dev/null; then
        err "Missing dependency for gpt-image-2: python3"
        return 1
    fi
    if ! command -v magick &>/dev/null; then
        warn "ImageMagick not found (optional — needed for resizing and contact sheets)"
        echo "    macOS: brew install imagemagick"
        echo "    Linux: sudo apt install imagemagick"
    fi
    return 0
}

check_deps() {
    local skill="$1"
    case "$skill" in
        garmin)         check_deps_garmin ;;
        verve)          check_deps_verve ;;
        gpt-image-2)    check_deps_gpt_image_2 ;;
        *)              return 0 ;;
    esac
}

# ─── Install a single skill ──────────────────────────────────────────

install_skill() {
    local skill="$1"
    local source="$REPO_DIR/$skill"
    local target="$SKILLS_DIR/$skill"

    echo
    info "Installing ${BOLD}$skill${NC}"

    # Check source exists
    if [ ! -d "$source" ] || [ ! -f "$source/SKILL.md" ]; then
        err "$skill: not found or missing SKILL.md"
        return 1
    fi

    # Check dependencies
    if ! check_deps "$skill"; then
        warn "Skipping $skill (missing dependencies)"
        return 1
    fi

    # Handle existing installation
    if [ -L "$target" ]; then
        local current
        current="$(readlink "$target")"
        if [ "$current" = "$source" ]; then
            ok "$skill already linked → $source"
            # Still run post-install for things like .venv
            post_install "$skill"
            return 0
        fi
        info "Updating symlink (was → $current)"
        rm "$target"
    elif [ -d "$target" ]; then
        warn "Existing directory at $target (not a symlink)"
        if [ "$AUTO" = "1" ]; then
            info "Replacing with symlink (--all mode)"
        else
            read -r -p "    Replace with symlink? (y/N): " replace
            if [[ ! "$replace" =~ ^[Yy]$ ]]; then
                warn "Skipped $skill"
                return 0
            fi
        fi
        rm -rf "$target"
    fi

    # Create symlink
    mkdir -p "$SKILLS_DIR"
    ln -s "$source" "$target"
    ok "$skill → $source"

    # Post-install steps
    post_install "$skill"
}

post_install() {
    local skill="$1"

    case "$skill" in

        garmin)
            chmod +x "$REPO_DIR/garmin/scripts/setup.sh" 2>/dev/null || true

            # Set up Python venv if needed
            if [ ! -d "$REPO_DIR/garmin/.venv" ]; then
                info "Setting up Python virtual environment..."
                python3 -m venv "$REPO_DIR/garmin/.venv"
                "$REPO_DIR/garmin/.venv/bin/pip" install --upgrade pip -q
                "$REPO_DIR/garmin/.venv/bin/pip" install -r "$REPO_DIR/garmin/requirements.txt" -q
            else
                ok "Python venv already exists"
                # Update deps quietly
                "$REPO_DIR/garmin/.venv/bin/pip" install -r "$REPO_DIR/garmin/requirements.txt" -q 2>/dev/null || true
            fi

            if [ -f "$HOME/.garmin/config.json" ]; then
                ok "Garmin credentials found"
            else
                warn "No Garmin credentials — run: ~/.claude/skills/garmin/scripts/setup.sh"
            fi
            ;;

        verve)
            chmod +x "$REPO_DIR/verve/scripts/setup.sh" 2>/dev/null || true
            chmod +x "$REPO_DIR/verve/scripts/verve-api.py" 2>/dev/null || true

            # Set up Python venv if needed
            if [ ! -d "$REPO_DIR/verve/.venv" ]; then
                info "Setting up Python virtual environment..."
                python3 -m venv "$REPO_DIR/verve/.venv"
                "$REPO_DIR/verve/.venv/bin/pip" install --upgrade pip -q
                "$REPO_DIR/verve/.venv/bin/pip" install -r "$REPO_DIR/verve/requirements.txt" -q
            else
                ok "Python venv already exists"
                "$REPO_DIR/verve/.venv/bin/pip" install -r "$REPO_DIR/verve/requirements.txt" -q 2>/dev/null || true
            fi

            if [ -f "$HOME/.verve/config.json" ]; then
                ok "Verve API config found"
            else
                info "No commercial API configured (optional) -- run: ~/.claude/skills/verve/scripts/setup.sh"
            fi
            ;;

        gpt-image-2)
            chmod +x "$REPO_DIR/gpt-image-2/setup.sh" 2>/dev/null || true
            chmod +x "$REPO_DIR/gpt-image-2/scripts/gpt_image_2.py" 2>/dev/null || true

            # Set up Python venv if needed
            if [ ! -d "$REPO_DIR/gpt-image-2/.venv" ]; then
                info "Setting up Python virtual environment..."
                python3 -m venv "$REPO_DIR/gpt-image-2/.venv"
                "$REPO_DIR/gpt-image-2/.venv/bin/pip" install --upgrade pip -q
                "$REPO_DIR/gpt-image-2/.venv/bin/pip" install -r "$REPO_DIR/gpt-image-2/requirements.txt" -q
            else
                ok "Python venv already exists"
                "$REPO_DIR/gpt-image-2/.venv/bin/pip" install -r "$REPO_DIR/gpt-image-2/requirements.txt" -q 2>/dev/null || true
            fi

            if [ -n "$OPENAI_API_KEY" ] || [ -n "$OPENROUTER_API_KEY" ]; then
                ok "API key found in environment"
            else
                warn "No OPENAI_API_KEY in environment — set it before generating images"
                echo "    export OPENAI_API_KEY=sk-..."
            fi
            ;;

    esac
}

# ─── Main ─────────────────────────────────────────────────────────────

AUTO=0
REQUESTED_SKILLS=()

# Parse args
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
            echo "  $0 garmin verve        # Install specific skills"
            exit 0
            ;;
        *)
            REQUESTED_SKILLS+=("$arg")
            ;;
    esac
done

echo
echo -e "${BOLD}=== Claude Code Skills Installer ===${NC}"
echo -e "Repo:   $REPO_DIR"
echo -e "Target: $SKILLS_DIR"

# Determine which skills to install
if [ "$AUTO" = "1" ]; then
    REQUESTED_SKILLS=("${AVAILABLE_SKILLS[@]}")
elif [ ${#REQUESTED_SKILLS[@]} -eq 0 ]; then
    # Interactive mode
    echo
    echo "Available skills:"
    for i in "${!AVAILABLE_SKILLS[@]}"; do
        skill="${AVAILABLE_SKILLS[$i]}"
        status=""
        if [ -L "$SKILLS_DIR/$skill" ]; then
            status=" ${GREEN}(linked)${NC}"
        elif [ -d "$SKILLS_DIR/$skill" ]; then
            status=" ${YELLOW}(installed — not linked)${NC}"
        fi
        echo -e "  $((i+1)). $skill$status"
    done
    echo
    read -r -p "Install all? (Y/n): " install_all
    if [[ "$install_all" =~ ^[Nn]$ ]]; then
        read -r -p "Which skills? (space-separated, e.g. 'garmin verve'): " -a REQUESTED_SKILLS
        if [ ${#REQUESTED_SKILLS[@]} -eq 0 ]; then
            echo "Nothing selected. Exiting."
            exit 0
        fi
    else
        REQUESTED_SKILLS=("${AVAILABLE_SKILLS[@]}")
    fi
fi

# Validate requested skills
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

# Install each skill
INSTALLED=0
FAILED=0
for skill in "${REQUESTED_SKILLS[@]}"; do
    if install_skill "$skill"; then
        INSTALLED=$((INSTALLED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
done

# Summary
echo
echo -e "${BOLD}=== Done ===${NC}"
echo -e "  Installed: ${GREEN}$INSTALLED${NC}"
[ "$FAILED" -gt 0 ] && echo -e "  Skipped:   ${YELLOW}$FAILED${NC}"
echo
echo "Skills are symlinked — edits to this repo are live in Claude Code."
echo "No need to re-install after pulling updates."
echo
