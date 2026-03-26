#!/bin/bash
# Manual testing commands for guardrail

echo "=== Testing Deny Rules ==="

echo "Test 1: rm -rf /"
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"rm -rf /"}}' | python -m guardrail.cli
echo ""

echo "Test 2: Fork bomb"
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":":(){ :|:& };:"}}' | python -m guardrail.cli
echo ""

echo "Test 3: dd wipe disk"
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"dd if=/dev/zero of=/dev/sda"}}' | python -m guardrail.cli
echo ""

echo "Test 4: PATH manipulation"
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"/usr/bin/rm -rf /"}}' | python -m guardrail.cli
echo ""

echo "Test 5: eval wrapper"
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"eval rm -rf /"}}' | python -m guardrail.cli
echo ""

echo "=== Testing Allow Rules ==="

echo "Test 6: git status"
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"git status"}}' | python -m guardrail.cli
echo ""

echo "Test 7: ls"
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"ls -la"}}' | python -m guardrail.cli
echo ""

echo "Test 8: cat"
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"cat file.txt"}}' | python -m guardrail.cli
echo ""

echo "=== Testing Ask Rules ==="

echo "Test 9: python script"
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"python3 script.py"}}' | python -m guardrail.cli
echo ""

echo "Test 10: git push"
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"git push"}}' | python -m guardrail.cli
echo ""

echo "Test 11: npm install"
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"npm install express"}}' | python -m guardrail.cli
echo ""

echo "=== Testing File Operations ==="

echo "Test 12: Write .env (should deny)"
echo '{"hook_event_name":"PreToolUse","tool_name":"Write","tool_input":{"file_path":".env"}}' | python -m guardrail.cli
echo ""

echo "Test 13: Write normal file (should allow)"
echo '{"hook_event_name":"PreToolUse","tool_name":"Write","tool_input":{"file_path":"test.txt"}}' | python -m guardrail.cli
echo ""

echo "=== Testing Compound Commands ==="

echo "Test 14: Safe then dangerous (should deny)"
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"git status && rm -rf /"}}' | python -m guardrail.cli
echo ""

echo "Test 15: Multiple safe commands (should allow)"
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"git status && ls -la"}}' | python -m guardrail.cli
echo ""

echo "=== All tests complete ==="
