#!/bin/bash
# Config validation commands

echo "=== Checking Config Files ==="

echo "1. Check if config files exist:"
ls -la .claude/guardrail.yml ~/.claude/guardrail.yml 2>/dev/null
echo ""

echo "2. Validate YAML syntax (.claude/guardrail.yml):"
if [ -f .claude/guardrail.yml ]; then
    python3 -c "import yaml; yaml.safe_load(open('.claude/guardrail.yml')); print('✓ Valid YAML')" 2>&1
else
    echo "File not found"
fi
echo ""

echo "3. Validate YAML syntax (~/.claude/guardrail.yml):"
if [ -f ~/.claude/guardrail.yml ]; then
    python3 -c "import yaml; yaml.safe_load(open('$HOME/.claude/guardrail.yml')); print('✓ Valid YAML')" 2>&1
else
    echo "File not found"
fi
echo ""

echo "4. Display merged config:"
python3 -c "
from guardrail.config import load_config
import json
config = load_config()
print(json.dumps(config, indent=2))
" 2>&1
echo ""

echo "5. Check deny rules:"
python3 -c "
from guardrail.config import load_config
config = load_config()
deny_bash = config.get('deny_rules', {}).get('bash', [])
print(f'Deny rules (bash): {len(deny_bash)} patterns')
for i, pattern in enumerate(deny_bash[:5], 1):
    print(f'  {i}. {pattern}')
if len(deny_bash) > 5:
    print(f'  ... and {len(deny_bash) - 5} more')
" 2>&1
echo ""

echo "6. Check allow rules:"
python3 -c "
from guardrail.config import load_config
config = load_config()
allow_bash = config.get('allow_rules', {}).get('bash', [])
print(f'Allow rules (bash): {len(allow_bash)} patterns')
for i, pattern in enumerate(allow_bash[:5], 1):
    print(f'  {i}. {pattern}')
if len(allow_bash) > 5:
    print(f'  ... and {len(allow_bash) - 5} more')
" 2>&1
echo ""

echo "7. Check ask rules:"
python3 -c "
from guardrail.config import load_config
config = load_config()
ask_bash = config.get('ask_rules', {}).get('bash', [])
print(f'Ask rules (bash): {len(ask_bash)} patterns')
for i, pattern in enumerate(ask_bash[:5], 1):
    print(f'  {i}. {pattern}')
if len(ask_bash) > 5:
    print(f'  ... and {len(ask_bash) - 5} more')
" 2>&1
echo ""

echo "8. Check log file location:"
python3 -c "
from guardrail.config import load_config
config = load_config()
print(f'Log file: {config.get(\"log_file\", \".claude/guardrail.log\")}')
" 2>&1
echo ""

echo "9. Check Layer 2 configuration:"
python3 -c "
from guardrail.config import load_config
config = load_config()
llm = config.get('llm', {})
if llm:
    print('Layer 2 enabled:')
    print(f'  Provider: {llm.get(\"provider\", \"anthropic\")}')
    print(f'  Model: {llm.get(\"model\", \"claude-3-5-sonnet-20241022\")}')
    print(f'  API key set: {bool(llm.get(\"api_key\"))}')
else:
    print('Layer 2 not configured')
" 2>&1
echo ""

echo "=== Config validation complete ==="
