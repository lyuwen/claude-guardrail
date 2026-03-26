#!/usr/bin/env bash
#
# test_install.sh - Smoke tests for guardrail/install.sh
#
# Runs the install script in a temporary directory and verifies:
#   1. Project-scope install creates .claude/settings.json with the hook
#   2. User-scope install creates settings.json with an absolute path
#   3. Re-running install does not duplicate the hook
#   4. Existing settings are preserved (non-hook keys survive)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
INSTALL_SCRIPT="$PROJECT_DIR/guardrail/install.sh"

PASS=0
FAIL=0
TESTS=0

# Detect the same Python the install script will use.
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        if "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3,) else 1)" 2>/dev/null; then
            if "$candidate" -c "import yaml" 2>/dev/null; then
                PYTHON="$candidate"
                break
            fi
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo "Error: No Python 3 with PyYAML found. Cannot run tests." >&2
    exit 1
fi

# ── Helpers ──────────────────────────────────────────────────────────────────

pass() {
    PASS=$((PASS + 1))
    TESTS=$((TESTS + 1))
    echo "  PASS: $1"
}

fail() {
    FAIL=$((FAIL + 1))
    TESTS=$((TESTS + 1))
    echo "  FAIL: $1" >&2
}

assert_file_exists() {
    if [[ -f "$1" ]]; then
        pass "$2"
    else
        fail "$2 (file not found: $1)"
    fi
}

assert_json_contains() {
    # $1 = file, $2 = python expression that must be truthy, $3 = description
    if $PYTHON -c "
import json, sys
with open('$1') as f:
    data = json.load(f)
assert $2, 'assertion failed'
" 2>/dev/null; then
        pass "$3"
    else
        fail "$3"
    fi
}

# ── Setup ────────────────────────────────────────────────────────────────────

TMPDIR_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_ROOT"' EXIT

echo "Temp directory: $TMPDIR_ROOT"
echo ""

# ── Test 1: Project-scope install ────────────────────────────────────────────

echo "Test 1: Project-scope install (default)"

WORKDIR="$TMPDIR_ROOT/test1"
mkdir -p "$WORKDIR"

# Copy the guardrail package so imports work
cp -r "$PROJECT_DIR/guardrail" "$WORKDIR/guardrail"

(cd "$WORKDIR" && bash "$INSTALL_SCRIPT") >/dev/null 2>&1

assert_file_exists "$WORKDIR/.claude/settings.json" \
    "settings.json created"

assert_json_contains "$WORKDIR/.claude/settings.json" \
    "'PreToolUse' in data.get('hooks', {})" \
    "hooks.PreToolUse key exists"

assert_json_contains "$WORKDIR/.claude/settings.json" \
    "any('guardrail/cli.py' in h.get('command','') for h in data['hooks']['PreToolUse'])" \
    "hook command references guardrail/cli.py"

assert_json_contains "$WORKDIR/.claude/settings.json" \
    "'guardrail/cli.py' in data['hooks']['PreToolUse'][0].get('command','') and not data['hooks']['PreToolUse'][0].get('command','').split('guardrail/')[0].rstrip().startswith('/')" \
    "project scope uses relative path"

echo ""

# ── Test 2: User-scope install ───────────────────────────────────────────────

echo "Test 2: User-scope install"

WORKDIR="$TMPDIR_ROOT/test2"
FAKEHOME="$TMPDIR_ROOT/fakehome"
mkdir -p "$WORKDIR" "$FAKEHOME"

cp -r "$PROJECT_DIR/guardrail" "$WORKDIR/guardrail"

(cd "$WORKDIR" && HOME="$FAKEHOME" bash "$INSTALL_SCRIPT" --scope user) >/dev/null 2>&1

assert_file_exists "$FAKEHOME/.claude/settings.json" \
    "user settings.json created"

assert_json_contains "$FAKEHOME/.claude/settings.json" \
    "'/guardrail/cli.py' in data['hooks']['PreToolUse'][0].get('command','')" \
    "user scope uses absolute path"

echo ""

# ── Test 3: Idempotency — no duplicate hooks ─────────────────────────────────

echo "Test 3: Idempotency (run twice, no duplicates)"

WORKDIR="$TMPDIR_ROOT/test3"
mkdir -p "$WORKDIR"
cp -r "$PROJECT_DIR/guardrail" "$WORKDIR/guardrail"

(cd "$WORKDIR" && bash "$INSTALL_SCRIPT") >/dev/null 2>&1
(cd "$WORKDIR" && bash "$INSTALL_SCRIPT") >/dev/null 2>&1

assert_json_contains "$WORKDIR/.claude/settings.json" \
    "len(data['hooks']['PreToolUse']) == 1" \
    "only one guardrail hook after two installs"

echo ""

# ── Test 4: Preserves existing settings ──────────────────────────────────────

echo "Test 4: Preserves existing settings"

WORKDIR="$TMPDIR_ROOT/test4"
mkdir -p "$WORKDIR/.claude"
cp -r "$PROJECT_DIR/guardrail" "$WORKDIR/guardrail"

# Write pre-existing settings
cat > "$WORKDIR/.claude/settings.json" <<'JSON'
{
  "permissions": {
    "allow": ["Read"]
  },
  "hooks": {
    "PostToolUse": [
      {
        "type": "command",
        "command": "echo done"
      }
    ]
  }
}
JSON

(cd "$WORKDIR" && bash "$INSTALL_SCRIPT") >/dev/null 2>&1

assert_json_contains "$WORKDIR/.claude/settings.json" \
    "'allow' in data.get('permissions', {})" \
    "existing permissions key preserved"

assert_json_contains "$WORKDIR/.claude/settings.json" \
    "len(data['hooks'].get('PostToolUse', [])) == 1" \
    "existing PostToolUse hook preserved"

assert_json_contains "$WORKDIR/.claude/settings.json" \
    "len(data['hooks'].get('PreToolUse', [])) == 1" \
    "PreToolUse hook added alongside existing hooks"

echo ""

# ── Test 5: Backup is created ────────────────────────────────────────────────

echo "Test 5: Backup created for existing settings"

WORKDIR="$TMPDIR_ROOT/test5"
mkdir -p "$WORKDIR/.claude"
cp -r "$PROJECT_DIR/guardrail" "$WORKDIR/guardrail"

echo '{"existing": true}' > "$WORKDIR/.claude/settings.json"

(cd "$WORKDIR" && bash "$INSTALL_SCRIPT") >/dev/null 2>&1

BACKUP_COUNT=$(ls "$WORKDIR/.claude/settings.json.bak."* 2>/dev/null | wc -l)
if [[ "$BACKUP_COUNT" -ge 1 ]]; then
    pass "backup file created"
else
    fail "no backup file found"
fi

echo ""

# ── Test 6: --help flag ─────────────────────────────────────────────────────

echo "Test 6: --help exits 0"

if bash "$INSTALL_SCRIPT" --help >/dev/null 2>&1; then
    pass "--help exits cleanly"
else
    fail "--help returned non-zero"
fi

echo ""

# ── Test 7: Invalid --scope rejected ─────────────────────────────────────────

echo "Test 7: Invalid --scope rejected"

if bash "$INSTALL_SCRIPT" --scope bogus >/dev/null 2>&1; then
    fail "should have rejected --scope bogus"
else
    pass "--scope bogus rejected with non-zero exit"
fi

echo ""

# ── Summary ──────────────────────────────────────────────────────────────────

echo "========================================="
echo "  Results: $PASS/$TESTS passed, $FAIL failed"
echo "========================================="

if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
exit 0
