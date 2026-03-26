---
name: Troubleshooting Guardrail
description: This skill should be used when the user asks "guardrail not working", "debug guardrail", "check guardrail logs", "why was this blocked", "test guardrail rules", "hook not firing", or needs help diagnosing guardrail issues.
version: 0.1.0
---

# Troubleshooting Guardrail

## Overview

Diagnose and resolve issues with guardrail hook installation, rule matching, decision logic, and Layer 2 LLM classification. This skill provides systematic troubleshooting workflows for common problems.

## Quick Diagnostics

### Check Hook Installation

Verify hooks are registered in `.claude/settings.json`:

```bash
grep -A 10 "PreToolUse" .claude/settings.json
```

Expected output shows guardrail hook:
```json
"PreToolUse": [{
  "matcher": "Bash|Write|Edit|WebFetch",
  "hooks": [{"type": "command", "command": "python -m guardrail.cli", "timeout": 10000}]
}]
```

If missing, run installation script:
```bash
bash hooks/scripts/install-hooks.sh
```

### Check Dependencies

Verify Python and PyYAML installed:

```bash
bash hooks/scripts/check-dependencies.sh
```

Expected: Exit code 0, no error messages.

If fails: Install missing dependencies per error message.

### Test Rule Matching

Test specific command against rules:

```bash
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"YOUR_COMMAND"}}' | python -m guardrail.cli
```

Expected output format:
```json
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow|deny|ask|pass", "permissionDecisionReason": "..."}}
```

### Check Logs

Read recent decisions from log file:

```bash
tail -n 20 .claude/guardrail.log
```

Log format:
```
[2026-03-26 10:30:45] PreToolUse:Bash | git status | allow | matched allow rule
[2026-03-26 10:31:12] PreToolUse:Bash | rm -rf / | deny | matched deny rule
```

## Common Issues

### Issue 1: Hook Not Firing

**Symptoms**: Commands execute without guardrail checking

**Diagnosis**:
1. Check hook installation (see Quick Diagnostics)
2. Verify tool name in matcher: `Bash|Write|Edit|WebFetch`
3. Check Claude Code permission mode (bypass mode skips hooks)
4. Look for hook errors in Claude Code output

**Solutions**:
- Reinstall hooks: `bash hooks/scripts/install-hooks.sh`
- Verify settings.json syntax (valid JSON)
- Check file permissions on guardrail scripts
- Restart Claude Code session

### Issue 2: Wrong Decision (Allow/Deny/Ask)

**Symptoms**: Command allowed when should be denied, or vice versa

**Diagnosis**:
1. Test command manually (see Quick Diagnostics)
2. Check which rule matched in log file
3. Verify rule priority: deny > allow > ask > pass
4. Check regex pattern syntax

**Solutions**:
- Review rule patterns in config files
- Test regex with Python: `python3 -c "import re; print(re.search(r'PATTERN', 'COMMAND'))"`
- Check config merge order: defaults → user → project
- Add missing deny/allow/ask rules to `.claude/guardrail.yml`

### Issue 3: Layer 2 Not Working

**Symptoms**: Commands pass through without LLM classification

**Diagnosis**:
1. Check Layer 2 configuration in `.claude/guardrail.local.md`
2. Verify API key environment variable set
3. Check log for Layer 2 attempts
4. Test LLM connectivity manually

**Solutions**:
- Configure Layer 2 (see layer-2-setup skill)
- Set environment variable: `export ANTHROPIC_AUTH_TOKEN=...`
- Check API key validity
- Review sanitization (secrets redacted before LLM)
- Verify network connectivity

### Issue 4: Python Script Always Asks

**Symptoms**: All Python scripts trigger "ask" decision

**Diagnosis**:
1. Check if script uses non-whitelisted imports
2. Look for dangerous patterns in script
3. Verify script file exists and is readable
4. Check Python AST parsing errors

**Solutions**:
- Review script imports (see references/python-safety.md)
- Remove dangerous operations (file writes, subprocess, network)
- Use only whitelisted modules for auto-allow
- Add script to allow rules if safe

### Issue 5: Config Not Loading

**Symptoms**: Custom rules not applied

**Diagnosis**:
1. Check YAML syntax: `python3 -c "import yaml; yaml.safe_load(open('.claude/guardrail.yml'))"`
2. Verify file location: `.claude/guardrail.yml` or `~/.claude/guardrail.yml`
3. Check file permissions (readable)
4. Look for config errors in logs

**Solutions**:
- Fix YAML syntax errors
- Verify indentation (use spaces, not tabs)
- Check file path spelling
- Review merge behavior (deny rules additive, others override)

### Issue 6: Regex Pattern Not Matching

**Symptoms**: Rule exists but doesn't match expected commands

**Diagnosis**:
1. Test pattern with Python re.search()
2. Check escaping (use `\\` in YAML for `\`)
3. Verify anchors (`^` for start, `$` for end)
4. Check for greedy vs non-greedy matching

**Solutions**:
- Add anchors for exact matches: `^command$`
- Escape special characters: `\\.` for literal dot
- Use `\\s` for whitespace (not single `\s`)
- Test pattern variations (see references/regex-testing.md)

## Troubleshooting Workflow

### Step 1: Identify Symptom

Determine what's not working:
- Hook not executing at all
- Wrong decision (allow/deny/ask)
- Layer 2 not activating
- Config not loading
- Pattern not matching

### Step 2: Gather Evidence

Collect diagnostic information:
- Check `.claude/guardrail.log` for recent decisions
- Test command manually with echo/pipe
- Verify hook installation in settings.json
- Check config file syntax
- Review Layer 2 configuration

### Step 3: Isolate Cause

Narrow down the problem:
- Is it installation issue? (hook missing from settings.json)
- Is it config issue? (YAML syntax, file location)
- Is it pattern issue? (regex not matching)
- Is it Layer 2 issue? (API key, network)
- Is it decision logic issue? (rule priority)

### Step 4: Apply Fix

Implement solution based on cause:
- Reinstall hooks if missing
- Fix config syntax if invalid
- Adjust regex patterns if not matching
- Configure Layer 2 if needed
- Add/modify rules if decision wrong

### Step 5: Verify Fix

Confirm issue resolved:
- Test command manually
- Check log shows expected decision
- Verify hook fires in Claude Code
- Test edge cases

## Testing Commands

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

### Test Layer 2 Pass

```bash
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"unknown-command --flag"}}' | python -m guardrail.cli
```

Expected: `"permissionDecision": "pass"` (if Layer 2 disabled) or `"allow"/"deny"/"ask"` (if Layer 2 enabled)

### Run Full Test Suite

```bash
bash hooks/scripts/test-guardrail.sh
```

Expected: All tests pass with correct decisions.

## Additional Resources

### Reference Files

For detailed troubleshooting guides:
- **`references/log-format.md`** - Log file structure and interpretation
- **`references/common-errors.md`** - Error messages and solutions
- **`references/debugging-commands.md`** - Complete command reference
- **`references/regex-testing.md`** - Pattern testing techniques
- **`references/python-safety.md`** - Python script analysis details

### Example Files

Working debugging examples in `examples/`:
- **`test-commands.sh`** - Manual testing commands
- **`debug-config.sh`** - Config validation commands
- **`check-installation.sh`** - Installation verification
