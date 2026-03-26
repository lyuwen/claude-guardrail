# Claude Guardrail Plugin - Testing Guide

## Installation Testing

### Step 1: Install Plugin Locally

Test the plugin in your current project:

```bash
# From the claude-guardrail directory
cd /home/lfu/git-projects/wutils/claude-guardrail

# The plugin is already in the correct location
# Claude Code will auto-discover it when you use --plugin-dir
```

Or copy to Claude's plugin directory:

```bash
# Copy to user plugins
mkdir -p ~/.claude/plugins
cp -r /home/lfu/git-projects/wutils/claude-guardrail ~/.claude/plugins/

# Or create symlink
ln -s /home/lfu/git-projects/wutils/claude-guardrail ~/.claude/plugins/claude-guardrail
```

### Step 2: Verify Plugin Structure

```bash
# Check plugin.json exists
cat .claude-plugin/plugin.json

# Check hooks configuration
cat hooks/hooks.json

# List all skills
ls -la skills/
```

Expected output:
- plugin.json with name "claude-guardrail"
- hooks.json with PreToolUse and PostToolUse hooks
- 4 skill directories: understanding-guardrail, configuring-rules, troubleshooting, layer-2-setup

### Step 3: Install Dependencies

```bash
# Check Python version (need 3.10+)
python3 --version

# Install PyYAML
pip3 install pyyaml

# Optional: Install Anthropic SDK for Layer 2
pip3 install anthropic

# Run dependency check
bash hooks/scripts/check-dependencies.sh
```

Expected: All dependencies satisfied, exit code 0

### Step 4: Install Hooks

```bash
# Run installation script
bash hooks/scripts/install-hooks.sh

# Verify hooks installed
grep -A 5 "PreToolUse" .claude/settings.json | grep guardrail
```

Expected: Hooks registered in .claude/settings.json

## Skill Testing

### Test 1: Understanding Guardrail Skill

Start Claude Code and ask questions that should trigger the skill:

```
User: "How does guardrail work?"
User: "Explain the 3-layer security model"
User: "What is Layer 2 classification?"
```

**Expected**: Skill loads and provides comprehensive explanation

**Verify**:
- Skill mentions Layer 1 (rules), Layer 2 (LLM), Layer 3 (user)
- References architecture.md, security-model.md, decision-examples.md
- Explains decision flow: deny → allow → ask → pass

### Test 2: Configuring Rules Skill

Ask questions about configuration:

```
User: "How do I add a guardrail rule?"
User: "Block kubectl delete namespace prod"
User: "Configure guardrail to allow my deployment script"
```

**Expected**: Skill loads and guides rule creation

**Verify**:
- Explains deny/allow/ask rule types
- Shows YAML syntax with regex patterns
- References regex-patterns.md and config-schema.md
- Provides example configurations

### Test 3: Troubleshooting Skill

Ask about debugging:

```
User: "Guardrail not working"
User: "Why was this command blocked?"
User: "Check guardrail logs"
```

**Expected**: Skill loads with troubleshooting steps

**Verify**:
- Provides diagnostic commands
- References log-format.md, common-errors.md, debugging-commands.md
- Includes example scripts for testing

### Test 4: Layer 2 Setup Skill

Ask about LLM configuration:

```
User: "Configure Layer 2"
User: "Set up LLM classification"
User: "Enable AI detection in guardrail"
```

**Expected**: Skill loads with setup instructions

**Verify**:
- Explains API key setup
- Shows configuration format
- References llm-classification.md, sanitization.md, adversarial-resistance.md
- Provides test commands

## Hook Testing

### Test 5: PreToolUse Hook

Test that hooks fire on tool use:

```bash
# Test deny rule
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"rm -rf /"}}' | python -m guardrail.cli
```

**Expected**: `{"permissionDecision": "deny"}`

### Test 6: Allow Rule

```bash
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"git status"}}' | python -m guardrail.cli
```

**Expected**: `{"permissionDecision": "allow"}`

### Test 7: Ask Rule

```bash
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"python3 script.py"}}' | python -m guardrail.cli
```

**Expected**: `{"permissionDecision": "ask"}`

### Test 8: Full Test Suite

```bash
bash hooks/scripts/test-guardrail.sh
```

**Expected**: All tests pass with correct decisions

## Integration Testing

### Test 9: Use in Claude Code

Start Claude Code with the plugin:

```bash
# If plugin is in current directory
cc --plugin-dir /home/lfu/git-projects/wutils/claude-guardrail

# Or if installed in ~/.claude/plugins
cc
```

Ask Claude to run commands:

```
User: "Run git status"
```

**Expected**: Command executes (allow rule matches)

```
User: "Run rm -rf /"
```

**Expected**: Command blocked (deny rule matches)

```
User: "Run python3 analyze.py"
```

**Expected**: Prompt for confirmation (ask rule matches)

### Test 10: Check Logs

```bash
# View recent decisions
tail -n 20 .claude/guardrail.log

# Check for hook execution
grep "PreToolUse" .claude/guardrail.log | tail -5
```

**Expected**: Log entries showing decisions

## Verification Checklist

- [ ] Plugin structure correct (.claude-plugin/plugin.json exists)
- [ ] All 4 skills present with SKILL.md files
- [ ] Hooks configuration valid (hooks/hooks.json)
- [ ] Dependencies installed (Python 3.10+, PyYAML)
- [ ] Hooks registered in .claude/settings.json
- [ ] Understanding skill triggers on "how does guardrail work"
- [ ] Configuring skill triggers on "add guardrail rule"
- [ ] Troubleshooting skill triggers on "guardrail not working"
- [ ] Layer 2 skill triggers on "configure Layer 2"
- [ ] PreToolUse hook blocks dangerous commands
- [ ] PreToolUse hook allows safe commands
- [ ] PreToolUse hook asks for scripts
- [ ] Test suite passes (test-guardrail.sh)
- [ ] Logs show decisions (.claude/guardrail.log)

## Common Issues

### Issue: Skills not loading

**Cause**: Plugin not discovered by Claude Code

**Solution**:
- Verify plugin.json exists in .claude-plugin/
- Check SKILL.md files exist in skills/*/
- Restart Claude Code

### Issue: Hooks not firing

**Cause**: Hooks not registered or wrong matcher

**Solution**:
- Run install-hooks.sh again
- Check .claude/settings.json for guardrail hooks
- Verify matcher: "Bash|Write|Edit|WebFetch"

### Issue: Dependency errors

**Cause**: Python or PyYAML not installed

**Solution**:
- Install Python 3.10+
- Run: pip3 install pyyaml
- Run: bash hooks/scripts/check-dependencies.sh

### Issue: Wrong decisions

**Cause**: Rules not matching as expected

**Solution**:
- Test pattern manually with Python re.search()
- Check config file syntax (YAML)
- Review rule priority: deny > allow > ask > pass
- Check logs for which rule matched

## Success Criteria

Plugin is working correctly if:

1. ✓ All 4 skills load on appropriate triggers
2. ✓ Skills provide helpful, accurate information
3. ✓ References load when needed
4. ✓ Examples are complete and working
5. ✓ Hooks fire on tool use
6. ✓ Deny rules block dangerous commands
7. ✓ Allow rules auto-approve safe commands
8. ✓ Ask rules prompt for confirmation
9. ✓ Logs show decisions
10. ✓ Test suite passes

## Next Steps

After successful testing:

1. **Document usage**: Update README.md with examples
2. **Add to marketplace**: Create marketplace entry (optional)
3. **Iterate**: Improve based on usage feedback
4. **Share**: Publish plugin for others to use
