#!/usr/bin/env bash
#
# install.sh - Install the guardrail as a Claude Code PreToolUse hook.
#
# Usage:
#   ./guardrail/install.sh [--scope project|user]
#
# --scope project  (default) Write hook to .claude/settings.json in CWD,
#                  using a relative command path.
# --scope user     Write hook to ~/.claude/settings.json, using an absolute
#                  command path.

set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────────────────────

SCOPE="project"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── Argument parsing ─────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case "$1" in
        --scope)
            if [[ -z "${2:-}" ]]; then
                echo "Error: --scope requires a value (project or user)." >&2
                exit 1
            fi
            SCOPE="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [--scope project|user]"
            echo ""
            echo "  --scope project   (default) Install hook in .claude/settings.json in CWD"
            echo "  --scope user      Install hook in ~/.claude/settings.json"
            exit 0
            ;;
        *)
            echo "Error: Unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

if [[ "$SCOPE" != "project" && "$SCOPE" != "user" ]]; then
    echo "Error: --scope must be 'project' or 'user', got '$SCOPE'." >&2
    exit 1
fi

# ── Prerequisite checks ─────────────────────────────────────────────────────

echo "Checking prerequisites..."

# Find a Python >= 3 that has PyYAML installed.
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        # Must be Python 3+
        if "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3,) else 1)" 2>/dev/null; then
            if "$candidate" -c "import yaml" 2>/dev/null; then
                PYTHON="$candidate"
                break
            fi
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo "Error: No Python 3 interpreter with PyYAML found on PATH." >&2
    echo "       Tried: python3, python" >&2
    echo "       Install PyYAML with: pip install pyyaml" >&2
    exit 1
fi

echo "  Python:  $($PYTHON --version) ($PYTHON)"
echo "  PyYAML:  OK"

# ── Determine paths ─────────────────────────────────────────────────────────

if [[ "$SCOPE" == "user" ]]; then
    SETTINGS_DIR="$HOME/.claude"
    SETTINGS_FILE="$SETTINGS_DIR/settings.json"
    HOOK_COMMAND="$PYTHON -m guardrail.cli"
else
    SETTINGS_DIR=".claude"
    SETTINGS_FILE="$SETTINGS_DIR/settings.json"
    # Use absolute path to Python and add guardrail to PYTHONPATH
    HOOK_COMMAND="PYTHONPATH=$PROJECT_DIR:\$PYTHONPATH $PYTHON -m guardrail.cli"
fi

echo ""
echo "Scope:         $SCOPE"
echo "Settings file: $SETTINGS_FILE"
echo "Hook command:  $HOOK_COMMAND"
echo ""

# ── Create directory ─────────────────────────────────────────────────────────

if [[ ! -d "$SETTINGS_DIR" ]]; then
    echo "Creating directory: $SETTINGS_DIR"
    mkdir -p "$SETTINGS_DIR"
fi

# ── Back up existing settings ────────────────────────────────────────────────

if [[ -f "$SETTINGS_FILE" ]]; then
    BACKUP="${SETTINGS_FILE}.bak.$(date +%Y%m%d%H%M%S)"
    echo "Backing up existing settings to: $BACKUP"
    cp "$SETTINGS_FILE" "$BACKUP"
fi

# ── Merge hook config using Python (portable, no jq dependency) ──────────────

$PYTHON - "$SETTINGS_FILE" "$HOOK_COMMAND" <<'PYEOF'
import json
import sys
import os

settings_file = sys.argv[1]
hook_command = sys.argv[2]

MATCHER = "Bash|Write|Edit|WebFetch"

new_hook_handler = {
    "type": "command",
    "command": hook_command,
    "timeout": 10000,
}

new_hook_group = {
    "matcher": MATCHER,
    "hooks": [new_hook_handler],
}

# Load existing settings — NEVER start fresh if the file exists, to avoid data loss
if os.path.isfile(settings_file):
    with open(settings_file) as f:
        raw = f.read()
    if raw.strip():
        try:
            settings = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"Error: {settings_file} contains invalid JSON: {e}", file=sys.stderr)
            print("Aborting to avoid data loss. Fix the file or restore from backup.", file=sys.stderr)
            sys.exit(1)
        if not isinstance(settings, dict):
            print(f"Error: {settings_file} root is not a JSON object (got {type(settings).__name__}).", file=sys.stderr)
            print("Aborting to avoid data loss.", file=sys.stderr)
            sys.exit(1)
    else:
        # File exists but is empty — safe to initialise
        settings = {}
else:
    settings = {}

# Ensure hooks object exists
hooks = settings.setdefault("hooks", {})
if not isinstance(hooks, dict):
    hooks = {}
    settings["hooks"] = hooks


def _install_hook_type(hook_type):
    """Install or update the guardrail hook group for a given hook type."""
    groups = hooks.setdefault(hook_type, [])
    if not isinstance(groups, list):
        groups = []
        hooks[hook_type] = groups

    # Check if a guardrail hook group already exists (avoid duplicates)
    found = False
    for group in groups:
        if not isinstance(group, dict):
            continue
        for h in group.get("hooks", []):
            if isinstance(h, dict) and "guardrail.cli" in h.get("command", ""):
                h["command"] = hook_command
                h["timeout"] = 10000
                group["matcher"] = MATCHER
                found = True
                print(f"  {hook_type}: updated existing guardrail hook.")
                break
        if found:
            break

    if not found:
        groups.append(new_hook_group)
        print(f"  {hook_type}: appended guardrail hook.")


_install_hook_type("PreToolUse")
_install_hook_type("PostToolUse")

# Write back
with open(settings_file, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")

print(f"\nWrote {settings_file}")
PYEOF

# ── Verify the hook works ────────────────────────────────────────────────────

echo ""
echo "Verifying guardrail loads correctly..."

# Run --check from the project directory so the package imports resolve
if (cd "$PROJECT_DIR" && $PYTHON -m guardrail.cli --check); then
    echo ""
    echo "========================================="
    echo "  Guardrail hook installed successfully!"
    echo "========================================="
    echo ""
    echo "The PreToolUse and PostToolUse hooks are now configured in:"
    echo "  $SETTINGS_FILE"
    echo ""
    if [[ "$SCOPE" == "project" ]]; then
        echo "Note: The hook uses PYTHONPATH to find the guardrail module:"
        echo "  $PROJECT_DIR"
    fi
else
    echo ""
    echo "WARNING: guardrail --check failed." >&2
    echo "The hook was written to $SETTINGS_FILE but may not work correctly." >&2
    echo "Check that guardrail/defaults.yml exists and is valid YAML." >&2
    exit 1
fi
