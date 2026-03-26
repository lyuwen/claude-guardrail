#!/usr/bin/env bash
set -euo pipefail

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

echo "Installing claude-guardrail hooks..."
echo ""

# Check dependencies first
if ! bash "$PLUGIN_ROOT/hooks/scripts/check-dependencies.sh"; then
    echo ""
    echo "❌ Dependency check failed. Install missing dependencies and try again."
    exit 1
fi

echo ""
echo "Adding hooks to .claude/settings.json..."

# Determine settings file location
SETTINGS_DIR=".claude"
SETTINGS_FILE="$SETTINGS_DIR/settings.json"

# Create directory if needed
if [[ ! -d "$SETTINGS_DIR" ]]; then
    mkdir -p "$SETTINGS_DIR"
fi

# Backup existing settings
if [[ -f "$SETTINGS_FILE" ]]; then
    BACKUP="${SETTINGS_FILE}.bak.$(date +%Y%m%d%H%M%S)"
    cp "$SETTINGS_FILE" "$BACKUP"
    echo "✓ Backed up existing settings to: $BACKUP"
fi

# Use Python to merge hooks into settings.json
python3 - "$SETTINGS_FILE" "$PLUGIN_ROOT" <<'PYEOF'
import json
import sys
import os

settings_file = sys.argv[1]
plugin_root = sys.argv[2]

MATCHER = "Bash|Write|Edit|WebFetch"
hook_command = f"PYTHONPATH={plugin_root}:$PYTHONPATH python3 -m guardrail.cli"

new_hook = {
    "type": "command",
    "command": hook_command,
    "timeout": 10000,
}

new_hook_group = {
    "matcher": MATCHER,
    "hooks": [new_hook],
}

# Load existing settings
if os.path.isfile(settings_file):
    with open(settings_file) as f:
        raw = f.read()
    if raw.strip():
        try:
            settings = json.loads(raw)
        except json.JSONDecodeError:
            settings = {}
    else:
        settings = {}
else:
    settings = {}

hooks = settings.setdefault("hooks", {})

def install_hook_type(hook_type):
    groups = hooks.setdefault(hook_type, [])

    # Check if guardrail hook already exists
    for group in groups:
        for h in group.get("hooks", []):
            if "guardrail.cli" in h.get("command", ""):
                h["command"] = hook_command
                h["timeout"] = 10000
                group["matcher"] = MATCHER
                print(f"  {hook_type}: updated existing guardrail hook")
                return

    # Add new hook group
    groups.append(new_hook_group)
    print(f"  {hook_type}: added guardrail hook")

install_hook_type("PreToolUse")
install_hook_type("PostToolUse")

# Write back
with open(settings_file, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")

print(f"\n✓ Wrote {settings_file}")
PYEOF

echo ""
echo "========================================="
echo "  Guardrail hooks installed successfully!"
echo "========================================="
echo ""
echo "Hooks are now active in: $SETTINGS_FILE"
echo ""
echo "Next steps:"
echo "  1. Restart Claude Code to activate hooks"
echo "  2. Test with: bash $PLUGIN_ROOT/hooks/scripts/test-guardrail.sh"
echo "  3. Configure Layer 2: See skills/layer-2-setup/SKILL.md"
