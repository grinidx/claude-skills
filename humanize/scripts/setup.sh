#!/bin/bash
# Set up Humanize skill: optional Undetectable AI API key + Python venv
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$SKILL_DIR/.venv"
CONFIG_DIR="$HOME/.humanize"
CONFIG_FILE="$CONFIG_DIR/config.json"

echo "=== Humanize Skill Setup ==="
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
echo "Test with: ~/.claude/skills/humanize/.venv/bin/python ~/.claude/skills/humanize/scripts/humanize-api.py --text 'Hello world'"
