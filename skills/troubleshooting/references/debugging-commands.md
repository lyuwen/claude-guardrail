# Debugging Commands Reference

Complete reference of commands for diagnosing and testing guardrail.

## Installation Verification

### Check Python Version

```bash
python3 --version
```

Expected: Python 3.10 or higher

### Check PyYAML Installation

```bash
python3 -c "import yaml; print(yaml.__version__)"
```

Expected: Version number (e.g., 6.0)

### Check Anthropic SDK (Optional)

```bash
python3 -c "import anthropic; print(anthropic.__version__)"
```

Expected: Version number or ImportError if not installed

### Verify Guardrail Module

```bash
python3 -c "import guardrail.cli; print('OK')"
```

Expected: "OK"

### Run Dependency Check Script

```bash
bash hooks/scripts/check-dependencies.sh
echo $?
```

Expected: Exit code 0

## Hook Verification

### Check Hook Registration

```bash
grep -A 10 "PreToolUse" .claude/settings.json
```

Expected output:
```json
"PreToolUse": [{
  "matcher": "Bash|Write|Edit|WebFetch",
  "hooks": [{
    "type": "command",
    "command": "python -m guardrail.cli",
    "timeout": 10000
  }]
}]
```

### Check PostToolUse Hook

```bash
grep -A 10 "PostToolUse" .claude/settings.json
```

Expected: Similar structure for PostToolUse

### Count Guardrail Hooks

```bash
grep -c "guardrail.cli" .claude/settings.json
```

Expected: 2 (one PreToolUse, one PostToolUse)

### Validate settings.json Syntax

```bash
python3 -c "import json; json.load(open('.claude/settings.json')); print('Valid JSON')"
```

Expected: "Valid JSON"

## Configuration Testing

### Validate YAML Syntax

```bash
python3 -c "import yaml; yaml.safe_load(open('.claude/guardrail.yml')); print('Valid YAML')"
```

Expected: "Valid YAML"

### Check Config Files Exist

```bash
ls -la .claude/guardrail.yml ~/.claude/guardrail.yml 2>/dev/null
```

Shows which config files exist

### Display Merged Config

```bash
python3 -c "
from guardrail.config import load_config
import json
config = load_config()
print(json.dumps(config, indent=2))
"
```

Shows final merged configuration

### Check Specific Rule Category

```bash
python3 -c "
from guardrail.config import load_config
config = load_config()
print('Deny rules:', config.get('deny_rules', {}).get('bash', []))
"
```

Shows deny rules for bash

### Verify Log File Path

```bash
python3 -c "
from guardrail.config import load_config
config = load_config()
print('Log file:', config.get('log_file', '.claude/guardrail.log'))
"
```

Shows configured log file location

## Rule Testing

### Test Deny Rule

```bash
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"rm -rf /"}}' | python -m guardrail.cli
```

Expected: `"permissionDecision": "deny"`

### Test Allow Rule

```bash
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"git status"}}' | python -m guardrail.cli
```

Expected: `"permissionDecision": "allow"`

### Test Ask Rule

```bash
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"python3 script.py"}}' | python -m guardrail.cli
```

Expected: `"permissionDecision": "ask"`

### Test Pass (No Match)

```bash
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"unknown-command"}}' | python -m guardrail.cli
```

Expected: `"permissionDecision": "pass"`

### Test File Path Rule

```bash
echo '{"hook_event_name":"PreToolUse","tool_name":"Write","tool_input":{"file_path":".env"}}' | python -m guardrail.cli
```

Expected: Depends on rules (likely "deny" for .env)

### Test WebFetch Rule

```bash
echo '{"hook_event_name":"PreToolUse","tool_name":"WebFetch","tool_input":{"url":"https://example.com"}}' | python -m guardrail.cli
```

Expected: Depends on rules

### Test Compound Command

```bash
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"git status && rm -rf /"}}' | python -m guardrail.cli
```

Expected: `"permissionDecision": "deny"` (deny wins)

### Run Full Test Suite

```bash
bash hooks/scripts/test-guardrail.sh
```

Expected: All tests pass

## Regex Pattern Testing

### Test Pattern Match

```bash
python3 -c "import re; print(bool(re.search(r'^git\\s+status', 'git status')))"
```

Expected: True

### Test Pattern No Match

```bash
python3 -c "import re; print(bool(re.search(r'^git\\s+status', 'legit status')))"
```

Expected: False

### Test Escaping

```bash
python3 -c "import re; print(bool(re.search(r'script\\.py', 'script.py')))"
```

Expected: True

### Test Anchors

```bash
python3 -c "import re; print(bool(re.search(r'^rm\\s+-rf\\s+/', 'rm -rf /')))"
```

Expected: True

### Test Case Insensitive

```bash
python3 -c "import re; print(bool(re.search(r'(?i)delete', 'DELETE')))"
```

Expected: True

### Test Multiple Patterns

```bash
python3 -c "
import re
patterns = [r'^git\\s+status', r'^ls\\s']
command = 'git status'
print(any(re.search(p, command) for p in patterns))
"
```

Expected: True

## Python Script Analysis

### Check Script Safety

```bash
python3 -c "
from guardrail.python_analyzer import is_safe_python_script
print(is_safe_python_script('script.py'))
"
```

Expected: True or False with reason

### List Script Imports

```bash
python3 -c "
import ast
with open('script.py') as f:
    tree = ast.parse(f.read())
imports = [node.names[0].name for node in ast.walk(tree) if isinstance(node, ast.Import)]
print('Imports:', imports)
"
```

Shows all imports in script

### Check for Dangerous Patterns

```bash
python3 -c "
from guardrail.python_analyzer import _has_dangerous_patterns
with open('script.py') as f:
    print(_has_dangerous_patterns(f.read()))
"
```

Expected: True if dangerous, False if safe

## Layer 2 Testing

### Check API Key Set

```bash
echo $ANTHROPIC_AUTH_TOKEN | head -c 20
```

Shows first 20 chars of API key (or empty if not set)

### Test API Connectivity

```bash
curl -s -o /dev/null -w "%{http_code}" https://api.anthropic.com
```

Expected: 200 or similar success code

### Check Layer 2 Config

```bash
python3 -c "
from guardrail.config import load_config
config = load_config()
llm = config.get('llm', {})
print('Provider:', llm.get('provider'))
print('Model:', llm.get('model'))
print('API key set:', bool(llm.get('api_key')))
"
```

Shows Layer 2 configuration

### Test LLM Classification

```bash
python3 -c "
from guardrail.llm import evaluate_with_llm
from guardrail.config import load_config
config = load_config()
result = evaluate_with_llm('Bash', 'docker run ubuntu', config)
print(result)
"
```

Expected: Decision from LLM (or error if not configured)

### Test Sanitization

```bash
python3 -c "
from guardrail.sanitizer import sanitize_target
sanitized = sanitize_target('Bash', 'export API_KEY=sk-1234567890')
print(sanitized)
"
```

Expected: API key redacted

## Log Analysis

### View Recent Logs

```bash
tail -n 20 .claude/guardrail.log
```

Shows last 20 log entries

### Count Decisions by Type

```bash
echo "Deny: $(grep -c '| deny |' .claude/guardrail.log)"
echo "Allow: $(grep -c '| allow |' .claude/guardrail.log)"
echo "Ask: $(grep -c '| ask |' .claude/guardrail.log)"
echo "Pass: $(grep -c '| pass |' .claude/guardrail.log)"
```

Shows decision counts

### Find Specific Command

```bash
grep "git push" .claude/guardrail.log
```

Shows all decisions for "git push"

### Show Today's Decisions

```bash
grep "$(date +%Y-%m-%d)" .claude/guardrail.log
```

Shows decisions from today

### Most Blocked Commands

```bash
grep "| deny |" .claude/guardrail.log | awk -F'|' '{print $2}' | sort | uniq -c | sort -rn | head -10
```

Shows top 10 blocked commands

### Layer 2 Usage Count

```bash
grep -c "Layer 2" .claude/guardrail.log
```

Shows how many times LLM was used

### Check Log File Size

```bash
ls -lh .claude/guardrail.log
```

Shows log file size

## Performance Testing

### Measure Layer 1 Latency

```bash
time echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"git status"}}' | python -m guardrail.cli > /dev/null
```

Shows execution time (should be <100ms)

### Measure Layer 2 Latency

```bash
time echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"unknown-command"}}' | python -m guardrail.cli > /dev/null
```

Shows execution time (200-1000ms if Layer 2 enabled)

### Benchmark Rule Matching

```bash
python3 -c "
import time
from guardrail.engine import evaluate_action
from guardrail.config import load_config

config = load_config()
start = time.time()
for _ in range(100):
    evaluate_action('Bash', 'git status', config)
end = time.time()
print(f'100 evaluations: {(end-start)*1000:.2f}ms')
print(f'Per evaluation: {(end-start)*10:.2f}ms')
"
```

Shows rule matching performance

## Cleanup Commands

### Clear Log File

```bash
> .claude/guardrail.log
```

Empties log file

### Rotate Log File

```bash
mv .claude/guardrail.log .claude/guardrail.log.$(date +%Y%m%d)
touch .claude/guardrail.log
```

Archives old log, creates new one

### Remove Pending Markers

```bash
rm -rf .claude/guardrail_pending/*
```

Clears pending action markers

### Reset Configuration

```bash
rm .claude/guardrail.yml
```

Removes project config (falls back to defaults)

## Troubleshooting Workflows

### Full Diagnostic

```bash
echo "=== Python Version ==="
python3 --version

echo "=== Dependencies ==="
bash hooks/scripts/check-dependencies.sh

echo "=== Hook Registration ==="
grep -A 5 "PreToolUse" .claude/settings.json | grep guardrail

echo "=== Config Files ==="
ls -la .claude/guardrail.yml ~/.claude/guardrail.yml 2>/dev/null

echo "=== Recent Logs ==="
tail -n 5 .claude/guardrail.log

echo "=== Test Command ==="
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"git status"}}' | python -m guardrail.cli
```

Runs complete diagnostic check

### Quick Health Check

```bash
bash hooks/scripts/check-dependencies.sh && \
grep -q "guardrail.cli" .claude/settings.json && \
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"git status"}}' | python -m guardrail.cli > /dev/null && \
echo "✓ Guardrail healthy"
```

Quick pass/fail health check

### Reinstall Everything

```bash
bash hooks/scripts/check-dependencies.sh && \
bash hooks/scripts/install-hooks.sh && \
bash hooks/scripts/test-guardrail.sh
```

Complete reinstall and test
