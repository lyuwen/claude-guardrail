#!/usr/bin/env bash
set -euo pipefail

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

echo "Testing claude-guardrail hook..."
echo ""

test_command() {
    local name="$1"
    local payload="$2"
    local expected="$3"

    echo "Test: $name"
    result=$(echo "$payload" | python3 -m guardrail.cli 2>/dev/null || true)

    if [[ "$result" == *"$expected"* ]]; then
        echo "  ✓ $expected"
    else
        echo "  ✗ Expected '$expected', got: $result"
    fi
    echo ""
}

cd "$PLUGIN_ROOT"

# Test 1: Deny rule
test_command "Deny destructive command" \
    '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"rm -rf /"}}' \
    '"permissionDecision": "deny"'

# Test 2: Allow rule
test_command "Allow safe command" \
    '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"git status"}}' \
    '"permissionDecision": "allow"'

# Test 3: Ask rule
test_command "Ask for script execution" \
    '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"python3 script.py"}}' \
    '"permissionDecision": "ask"'

# Test 4: Layer 2 (if configured)
echo "Test: Layer 2 LLM classification"
result=$(echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"docker run ubuntu"}}' | python3 -m guardrail.cli 2>/dev/null || true)

if [[ "$result" == *'"permissionDecision"'* ]]; then
    echo "  ✓ Layer 2 active (returned decision)"
elif [[ -z "$result" ]]; then
    echo "  ℹ Layer 2 not configured (passed to Claude Code)"
else
    echo "  ✗ Unexpected result: $result"
fi

echo ""
echo "========================================="
echo "  Test complete"
echo "========================================="
