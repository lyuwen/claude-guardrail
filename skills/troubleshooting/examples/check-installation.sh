#!/bin/bash
# Installation verification commands

echo "=== Checking Installation ==="

echo "1. Python version:"
python3 --version
echo ""

echo "2. Check PyYAML:"
python3 -c "import yaml; print(f'PyYAML version: {yaml.__version__}')" 2>&1
echo ""

echo "3. Check Anthropic SDK (optional):"
python3 -c "import anthropic; print(f'Anthropic SDK version: {anthropic.__version__}')" 2>&1 || echo "Not installed (optional)"
echo ""

echo "4. Check guardrail module:"
python3 -c "import guardrail.cli; print('✓ Guardrail module found')" 2>&1
echo ""

echo "5. Run dependency check script:"
bash hooks/scripts/check-dependencies.sh
echo "Exit code: $?"
echo ""

echo "6. Check hook registration in settings.json:"
if [ -f .claude/settings.json ]; then
    echo "PreToolUse hook:"
    grep -A 5 '"PreToolUse"' .claude/settings.json | grep -A 3 'guardrail' || echo "Not found"
    echo ""
    echo "PostToolUse hook:"
    grep -A 5 '"PostToolUse"' .claude/settings.json | grep -A 3 'guardrail' || echo "Not found"
else
    echo ".claude/settings.json not found"
fi
echo ""

echo "7. Validate settings.json syntax:"
if [ -f .claude/settings.json ]; then
    python3 -c "import json; json.load(open('.claude/settings.json')); print('✓ Valid JSON')" 2>&1
else
    echo ".claude/settings.json not found"
fi
echo ""

echo "8. Count guardrail hooks:"
if [ -f .claude/settings.json ]; then
    count=$(grep -c 'guardrail.cli' .claude/settings.json)
    echo "Guardrail hooks found: $count (expected: 2)"
else
    echo ".claude/settings.json not found"
fi
echo ""

echo "9. Check log file:"
if [ -f .claude/guardrail.log ]; then
    echo "Log file exists:"
    ls -lh .claude/guardrail.log
    echo "Recent entries:"
    tail -n 3 .claude/guardrail.log
else
    echo "Log file not found (will be created on first use)"
fi
echo ""

echo "10. Test basic command:"
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"git status"}}' | python -m guardrail.cli
echo ""

echo "=== Installation check complete ==="
