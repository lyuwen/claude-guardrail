---
name: Configuring Guardrail Rules
description: This skill should be used when the user asks to "add guardrail rule", "configure guardrail", "customize security rules", "block command", "allow command", "modify guardrail rules", or wants to customize guardrail behavior.
version: 0.1.0
---

# Configuring Guardrail Rules

## Overview

Guardrail rules are configured through YAML files that define which actions to deny, allow, or prompt for confirmation. Rules are organized by tool type (bash, file_path, hostname) and merge across multiple config files.

## Configuration Files

### File Locations

Rules load from multiple locations with priority:

1. **Defaults**: `guardrail/defaults.yml` (built-in, always present)
2. **User config**: `~/.claude/guardrail.yml` (global, all projects)
3. **Project config**: `.claude/guardrail.yml` (project-specific)
4. **Environment variables**: Runtime overrides for LLM config

**Merge behavior**: Later configs override earlier ones, except deny rules (always additive).

### Basic Structure

```yaml
guarded_tools:
  - Bash
  - Write
  - Edit
  - WebFetch

deny_rules:
  bash: [...]
  file_path: [...]
  hostname: [...]

allow_rules:
  bash: [...]
  file_path: [...]
  hostname: [...]

ask_rules:
  bash: [...]
  file_path: [...]
  hostname: [...]

log_file: .claude/guardrail.log
```

## Rule Types

### Deny Rules (Block Immediately)

Block dangerous operations without prompting:

```yaml
deny_rules:
  bash:
    - "rm\\s+-rf\\s+/"              # Delete root
    - ":\\(\\)\\{.*:\\|:&\\};"      # Fork bomb
    - "kubectl delete namespace prod"  # Block prod deletion
  file_path:
    - "(^|/)\\.env$"                # Block .env files
    - "config/production\\.yml"     # Block prod config
  hostname:
    - ".*"                          # Block all WebFetch (if desired)
```

**Important**: Deny rules from defaults.yml cannot be removed (security guarantee).

### Allow Rules (Auto-Approve)

Auto-approve safe operations:

```yaml
allow_rules:
  bash:
    - "^git\\s+status"              # Git status
    - "^ls\\s"                      # List files
    - "^\\./scripts/safe-deploy\\.sh"  # Specific safe script
  file_path:
    - ".*"                          # Allow all file operations (default)
  hostname: []                      # No auto-allow for WebFetch
```

**Pattern matching**: Uses `re.search()` (contains match), not `re.match()` (start match).

### Ask Rules (Prompt User)

Prompt for potentially dangerous but legitimate operations:

```yaml
ask_rules:
  bash:
    - "^python[0-9.]*\\s"           # Python scripts
    - "^git\\s+push"                # Git push
    - "^kubectl apply"              # Kubernetes apply
  file_path: []                     # No ask rules for files (default)
  hostname: []                      # No ask rules for WebFetch (default)
```

## Rule Syntax

### Regex Patterns

Rules use Python regex syntax:

| Pattern | Meaning | Example |
|---------|---------|---------|
| `^` | Start of string | `^git` matches "git status" |
| `$` | End of string | `\\.py$` matches "script.py" |
| `\s` | Whitespace | `rm\s+-rf` matches "rm -rf" |
| `\\.` | Literal dot | `script\\.py` matches "script.py" |
| `.*` | Any characters | `.*\\.txt` matches any .txt file |
| `[0-9]` | Digit | `python[0-9]` matches "python3" |
| `(a\|b)` | Alternation | `(rm\|dd)` matches "rm" or "dd" |

**Escaping**: Use `\\` to escape special characters in YAML.

### Tool-Specific Patterns

**Bash commands**: Match against full command string

```yaml
bash:
  - "^docker\\s+run"               # Matches "docker run ubuntu"
  - "npm\\s+install"               # Matches "npm install express"
```

**File paths**: Match against file path

```yaml
file_path:
  - "(^|/)\\.env$"                 # Matches ".env" or "path/.env"
  - "^/etc/"                       # Matches files in /etc/
```

**Hostnames**: Match against URL hostname

```yaml
hostname:
  - "^evil\\.com$"                 # Matches "evil.com"
  - ".*\\.internal$"               # Matches "*.internal"
```

## Creating Custom Rules

### Step 1: Identify the Action

Determine what you want to control:
- Bash command?
- File path?
- WebFetch URL?

### Step 2: Choose Rule Type

- **Deny**: Dangerous, should never execute
- **Allow**: Safe, auto-approve
- **Ask**: Legitimate but needs confirmation

### Step 3: Write the Pattern

Test your regex pattern:

```bash
python3 -c "import re; print(re.search(r'YOUR_PATTERN', 'YOUR_TEST_STRING'))"
```

### Step 4: Add to Config

Create or edit `.claude/guardrail.yml`:

```yaml
deny_rules:
  bash:
    - "YOUR_PATTERN"
```

### Step 5: Test the Rule

```bash
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"YOUR_COMMAND"}}' | python -m guardrail.cli
```

## Common Patterns

### Block Specific Commands

```yaml
deny_rules:
  bash:
    - "^terraform\\s+destroy"       # Block terraform destroy
    - "^kubectl\\s+delete\\s+namespace\\s+prod"  # Block prod deletion
```

### Allow Project Scripts

```yaml
allow_rules:
  bash:
    - "^\\./scripts/test\\.sh"      # Allow test script
    - "^\\./scripts/lint\\.sh"      # Allow lint script
```

### Prompt for Deployments

```yaml
ask_rules:
  bash:
    - "^\\./deploy"                 # Prompt for any deploy script
    - "^ansible-playbook"           # Prompt for Ansible
```

### Protect Sensitive Files

```yaml
deny_rules:
  file_path:
    - "secrets\\.yml$"              # Block secrets.yml
    - "^/etc/passwd$"               # Block /etc/passwd
```

## Advanced Configuration

### PATH-Aware Patterns

Match commands regardless of PATH:

```yaml
deny_rules:
  bash:
    - "(^|.*/)rm\\s+-rf\\s+/"       # Matches "rm" or "/usr/bin/rm"
```

### Compound Command Handling

Each segment evaluated independently:

```yaml
deny_rules:
  bash:
    - "rm\\s+-rf"                   # Blocks "ls && rm -rf /"
```

Deny wins if any segment matches.

### Case-Insensitive Matching

Use `(?i)` flag:

```yaml
deny_rules:
  bash:
    - "(?i)delete.*production"      # Matches "DELETE" or "delete"
```

## Testing Rules

### Manual Testing

```bash
# Test deny rule
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"rm -rf /"}}' | python -m guardrail.cli

# Expected: {"permissionDecision": "deny"}
```

### Automated Testing

Use the test script:

```bash
bash hooks/scripts/test-guardrail.sh
```

### Verify Config Loads

```bash
python -m guardrail.cli --check
```

## Troubleshooting

### Rule Not Matching

1. **Check regex syntax**: Test with Python `re.search()`
2. **Check escaping**: Use `\\` in YAML for `\`
3. **Check tool type**: Bash vs file_path vs hostname
4. **Check priority**: Deny > Allow > Ask > Pass

### Rule Matching Too Much

1. **Add anchors**: Use `^` and `$` for exact matches
2. **Escape dots**: Use `\\.` not `.`
3. **Test thoroughly**: Try edge cases

### Config Not Loading

1. **Check YAML syntax**: Use YAML validator
2. **Check file location**: `.claude/guardrail.yml` or `~/.claude/guardrail.yml`
3. **Check permissions**: File must be readable
4. **Check logs**: `.claude/guardrail.log` for errors

## Additional Resources

### Reference Files

For detailed information:
- **`references/regex-patterns.md`** - Common regex patterns and examples
- **`references/config-schema.md`** - Complete configuration schema

### Example Files

Working examples in `examples/`:
- **`project-config.yml`** - Example project configuration
- **`user-config.yml`** - Example user configuration
