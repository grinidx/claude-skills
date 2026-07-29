#!/bin/bash
# Set up Verve skill: optional Undetectable AI API key + Python venv
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$SKILL_DIR/.venv"
CONFIG_DIR="$HOME/.verve"
CONFIG_FILE="$CONFIG_DIR/config.json"

echo "=== Verve Skill Setup ==="
echo ""
echo "The Claude engine works without any setup."
echo "This setup configures the optional Undetectable AI commercial API."

# --- Python venv ---
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python version: $PYTHON_VERSION"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
else
    echo "Virtual environment already exists"
fi

echo "Installing dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -r "$SKILL_DIR/requirements.txt" -q

# --- API Key ---
mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"

# The skill was called `humanize` until Jul 2026. verve-api.py still reads the
# old path, so an existing key keeps working without re-entering it here.
LEGACY_CONFIG_FILE="$HOME/.humanize/config.json"
if [ ! -f "$CONFIG_FILE" ] && [ -f "$LEGACY_CONFIG_FILE" ]; then
    echo ""
    echo "Found a config at the old path: $LEGACY_CONFIG_FILE"
    read -r -p "Copy it to $CONFIG_FILE? (Y/n): " migrate
    if [[ ! "$migrate" =~ ^[Nn]$ ]]; then
        cp "$LEGACY_CONFIG_FILE" "$CONFIG_FILE"
        chmod 600 "$CONFIG_FILE"
        echo "Copied. The old file is left in place; delete it when you're happy."
        echo ""
        echo "=== Setup Complete ==="
        exit 0
    fi
fi

if [ -f "$CONFIG_FILE" ]; then
    echo ""
    echo "Existing config found at $CONFIG_FILE"
    read -r -p "Overwrite? (y/N): " overwrite
    if [[ ! "$overwrite" =~ ^[Yy]$ ]]; then
        echo "Keeping existing config."
        echo ""
        echo "=== Setup Complete ==="
        exit 0
    fi
fi

echo ""
echo "Get your API key from: https://undetectable.ai/develop"
echo ""
read -r -p "Undetectable AI API key: " api_key

cat > "$CONFIG_FILE" <<CONF_EOF
{
  "api_key": "$api_key",
  "default_engine": "claude"
}
CONF_EOF
chmod 600 "$CONFIG_FILE"
echo "Config saved to $CONFIG_FILE"

echo ""
echo "=== Setup Complete ==="
echo "Virtual environment: $VENV_DIR"
echo "Config: $CONFIG_FILE"
echo ""
echo "Test with: ~/.claude/skills/verve/.venv/bin/python ~/.claude/skills/verve/scripts/verve-api.py --text 'Hello world'"
