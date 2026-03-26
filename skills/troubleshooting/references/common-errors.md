# Common Guardrail Errors

## Installation Errors

### Error: Python not found

```
bash: python: command not found
```

**Cause**: Python not installed or not in PATH

**Solution**:
```bash
# Check Python installation
which python3
python3 --version

# If missing, install Python 3.10+
# Ubuntu/Debian:
sudo apt install python3

# macOS:
brew install python3
```

### Error: PyYAML not installed

```
ModuleNotFoundError: No module named 'yaml'
```

**Cause**: PyYAML package not installed

**Solution**:
```bash
pip3 install pyyaml
# or
python3 -m pip install pyyaml
```

### Error: Hook installation failed

```
Error: Failed to merge hooks into settings.json
```

**Cause**: Invalid JSON in settings.json or permission issue

**Solution**:
```bash
# Validate settings.json syntax
python3 -c "import json; json.load(open('.claude/settings.json'))"

# Check file permissions
ls -la .claude/settings.json

# Backup and retry
cp .claude/settings.json .claude/settings.json.backup
bash hooks/scripts/install-hooks.sh
```

## Configuration Errors

### Error: YAML syntax error

```
yaml.scanner.ScannerError: mapping values are not allowed here
```

**Cause**: Invalid YAML syntax in guardrail.yml

**Solution**:
```bash
# Validate YAML syntax
python3 -c "import yaml; yaml.safe_load(open('.claude/guardrail.yml'))"

# Common issues:
# - Mixed tabs and spaces (use spaces only)
# - Missing quotes around special characters
# - Incorrect indentation
```

**Example fix**:
```yaml
# Bad (tabs)
deny_rules:
	bash:
		- "pattern"

# Good (spaces)
deny_rules:
  bash:
    - "pattern"
```

### Error: Config file not found

```
FileNotFoundError: [Errno 2] No such file or directory: '.claude/guardrail.yml'
```

**Cause**: Config file missing or wrong location

**Solution**:
```bash
# Check file exists
ls -la .claude/guardrail.yml

# Create if missing
mkdir -p .claude
touch .claude/guardrail.yml

# Or use user config
touch ~/.claude/guardrail.yml
```

### Error: Invalid regex pattern

```
re.error: bad escape \s at position 2
```

**Cause**: Incorrect escaping in YAML

**Solution**:
Use double backslashes in YAML:
```yaml
# Bad (single backslash)
- "git\s+status"

# Good (double backslash)
- "git\\s+status"
```

## Runtime Errors

### Error: Hook timeout

```
Error: Hook execution timed out after 10000ms
```

**Cause**: Hook took too long (Layer 2 LLM call slow)

**Solution**:
Increase timeout in hooks.json:
```json
{
  "PreToolUse": [{
    "matcher": "Bash|Write|Edit|WebFetch",
    "hooks": [{
      "type": "command",
      "command": "python -m guardrail.cli",
      "timeout": 30000
    }]
  }]
}
```

### Error: Module not found

```
ModuleNotFoundError: No module named 'guardrail'
```

**Cause**: PYTHONPATH not set or guardrail not in path

**Solution**:
```bash
# Set PYTHONPATH to project root
export PYTHONPATH=/path/to/claude-guardrail:$PYTHONPATH

# Or run from project root
cd /path/to/claude-guardrail
python -m guardrail.cli
```

### Error: Permission denied

```
PermissionError: [Errno 13] Permission denied: '.claude/guardrail.log'
```

**Cause**: Log file not writable

**Solution**:
```bash
# Fix permissions
chmod 644 .claude/guardrail.log

# Or change log location
# In guardrail.yml:
log_file: /tmp/guardrail.log
```

## Layer 2 Errors

### Error: API key not set

```
Error: ANTHROPIC_AUTH_TOKEN not set
```

**Cause**: Environment variable missing

**Solution**:
```bash
# Set environment variable
export ANTHROPIC_AUTH_TOKEN=sk-ant-...

# Or configure in .claude/guardrail.local.md
```

### Error: API authentication failed

```
Error: 401 Unauthorized
```

**Cause**: Invalid API key

**Solution**:
```bash
# Verify API key
echo $ANTHROPIC_AUTH_TOKEN

# Get new key from console.anthropic.com
# Update environment variable or config
```

### Error: API rate limit

```
Error: 429 Too Many Requests
```

**Cause**: Too many API calls

**Solution**:
- Wait before retrying
- Add more Layer 1 rules to reduce LLM calls
- Use allow/deny rules for common commands

### Error: Network timeout

```
Error: Connection timeout
```

**Cause**: Network issue or API unavailable

**Solution**:
```bash
# Check network connectivity
curl https://api.anthropic.com

# Increase timeout in config
# Or disable Layer 2 temporarily
```

## Decision Logic Errors

### Error: Wrong decision

**Symptom**: Command allowed when should be denied

**Cause**: Rule priority or pattern issue

**Solution**:
```bash
# Test command manually
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"YOUR_COMMAND"}}' | python -m guardrail.cli

# Check which rule matched
grep "YOUR_COMMAND" .claude/guardrail.log

# Verify rule priority: deny > allow > ask > pass
# Add missing deny rule if needed
```

### Error: Pattern not matching

**Symptom**: Rule exists but doesn't match

**Cause**: Regex pattern incorrect

**Solution**:
```bash
# Test pattern with Python
python3 -c "import re; print(re.search(r'YOUR_PATTERN', 'YOUR_COMMAND'))"

# Common issues:
# - Missing anchors (^ or $)
# - Not escaping special characters
# - Single backslash instead of double
# - Case sensitivity
```

### Error: Deny rule not working

**Symptom**: Dangerous command not blocked

**Cause**: Pattern doesn't match or rule overridden

**Solution**:
```bash
# Check deny rules in all configs
grep -r "deny_rules" .claude/ ~/.claude/

# Verify pattern matches
python3 -c "import re; print(re.search(r'DENY_PATTERN', 'DANGEROUS_COMMAND'))"

# Remember: deny rules from defaults.yml cannot be removed
```

## Python Script Analysis Errors

### Error: Script always asks

**Symptom**: All Python scripts trigger "ask"

**Cause**: Non-whitelisted imports or dangerous patterns

**Solution**:
```bash
# Check script imports
grep "^import\|^from" script.py

# Whitelisted modules: pandas, numpy, matplotlib, json, yaml, csv, etc.
# Non-whitelisted: os, subprocess, requests, socket, etc.

# Either:
# 1. Remove non-whitelisted imports
# 2. Add script to allow rules if safe
```

### Error: Script not analyzed

**Symptom**: Python script passes without analysis

**Cause**: Script file not found or not readable

**Solution**:
```bash
# Verify script exists
ls -la script.py

# Check file permissions
chmod 644 script.py

# Test analysis manually
python3 -c "from guardrail.python_analyzer import is_safe_python_script; print(is_safe_python_script('script.py'))"
```

## Hook Integration Errors

### Error: Hook not firing

**Symptom**: Commands execute without guardrail

**Cause**: Hook not registered or matcher wrong

**Solution**:
```bash
# Check hook registration
grep -A 10 "PreToolUse" .claude/settings.json

# Verify matcher includes tool
# Should be: "Bash|Write|Edit|WebFetch"

# Reinstall hooks
bash hooks/scripts/install-hooks.sh
```

### Error: Hook fires twice

**Symptom**: Duplicate log entries

**Cause**: Multiple hooks registered

**Solution**:
```bash
# Check for duplicates
grep -c "guardrail.cli" .claude/settings.json

# Should be 1 for PreToolUse, 1 for PostToolUse
# Remove duplicates manually from settings.json
```

### Error: PostToolUse not logging

**Symptom**: No PostToolUse entries in log

**Cause**: PostToolUse hook not registered

**Solution**:
```bash
# Check PostToolUse hook
grep -A 10 "PostToolUse" .claude/settings.json

# Should have guardrail hook
# Reinstall if missing
bash hooks/scripts/install-hooks.sh
```

## Debugging Commands

### Test specific command

```bash
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"git status"}}' | python -m guardrail.cli
```

### Validate config syntax

```bash
python3 -c "import yaml; yaml.safe_load(open('.claude/guardrail.yml'))"
```

### Check Python imports

```bash
python3 -c "import guardrail.cli; import guardrail.engine; import guardrail.config"
```

### Test regex pattern

```bash
python3 -c "import re; print(re.search(r'YOUR_PATTERN', 'YOUR_STRING'))"
```

### View recent logs

```bash
tail -n 50 .claude/guardrail.log
```

### Check dependencies

```bash
bash hooks/scripts/check-dependencies.sh
```

### Run full test suite

```bash
bash hooks/scripts/test-guardrail.sh
```

## Getting Help

If issue persists after troubleshooting:

1. Check logs: `.claude/guardrail.log`
2. Test manually with echo/pipe
3. Verify installation and dependencies
4. Review config files for syntax errors
5. Test regex patterns in isolation
6. Check Layer 2 configuration if using LLM
7. Consult references/debugging-commands.md for more tools
