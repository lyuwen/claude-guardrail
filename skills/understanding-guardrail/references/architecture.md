# Guardrail Architecture Deep Dive

## Component Overview

```
guardrail/
├── cli.py              # Hook entry point, stdin/stdout protocol
├── config.py           # Config loading and merging
├── engine.py           # Layer 1 rule evaluation
├── matcher.py          # Bash command parsing and pattern matching
├── llm.py              # Layer 2 LLM classification
├── sanitizer.py        # Secret redaction before LLM
├── python_analyzer.py  # Python script safety analysis
├── logger.py           # Decision logging and audit trail
└── defaults.yml        # Default security rules
```

## Hook Protocol

### Input (stdin)

JSON payload from Claude Code:

```json
{
  "hook_event_name": "PreToolUse",
  "tool_name": "Bash",
  "tool_input": {"command": "git status"},
  "permission_mode": "ask",
  "context": "...",
  "user_request": "..."
}
```

### Output (stdout)

JSON response for PreToolUse:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "matched allow rule"
  }
}
```

PostToolUse produces no output (silent).

## Layer 1 Engine

### Rule Evaluation Order

1. Check if tool is guarded (Bash, Write, Edit, WebFetch)
2. Extract target (command, file_path, url)
3. **Deny check** - Block if any deny pattern matches
4. **Allow check** - Approve if any allow pattern matches
5. **Python safety check** - Special handling for python scripts
6. **Ask check** - Prompt if any ask pattern matches
7. **Pass** - No rule matched, defer to Layer 2

### Bash Command Parsing

Commands split on separators: `;`, `&&`, `||`, `|`, `\n`

Each segment evaluated independently. Deny wins if any segment matches deny rule.

### Pattern Matching

- Regex patterns with `re.search()` (contains match)
- Case-sensitive by default
- Supports full Python regex syntax

## Layer 2 LLM Classification

### Configuration Priority

1. Config file (`llm` section in guardrail.yml)
2. Environment variables (ANTHROPIC_AUTH_TOKEN, etc.)
3. Disabled (returns "pass")

### Sanitization

Before sending to LLM:

- **Bash**: Redact secrets (API keys, tokens, base64 strings)
- **Write/Edit**: Send only file path, never content
- **WebFetch**: Redact secret query parameters

### Response Handling

- Parse JSON from LLM response
- Strip markdown code blocks if present
- Skip ThinkingBlock objects
- Validate decision is allow/deny/ask
- Return "pass" on any error

## Python Script Analysis

### Safety Criteria

Script is safe if:
1. All imports are whitelisted modules
2. No dangerous patterns in source code
3. File exists and is readable
4. Syntax is valid Python

### Whitelist

Safe modules: pandas, numpy, matplotlib, json, yaml, csv, collections, itertools, functools, math, statistics, datetime, re, pathlib, typing, dataclasses, enum, abc, contextlib, copy, pprint, textwrap, string, random (without seed manipulation).

### Dangerous Patterns

Regex patterns for:
- File writes: `open(..., 'w')`, `.save()`, `.to_csv()`
- OS operations: `os.remove()`, `os.mkdir()`, `shutil.*`
- Subprocess: `subprocess.*`, `os.system()`
- Network: `requests.*`, `urllib.*`, `socket.*`

## Pending Markers

### Purpose

Track actions that passed Layers 1-2 but need Layer 3 approval.

### Lifecycle

1. **PreToolUse**: Create marker in `.claude/guardrail_pending/`
2. **User approves**: Tool executes
3. **PostToolUse**: Resolve marker, log "allow"

### Marker Format

```json
{
  "tool_name": "Bash",
  "target": "docker run ubuntu",
  "timestamp": 1234567890.123,
  "config": {...}
}
```

Filename: `{timestamp_us}_{random_hex}.json`

## Logging

### Log Format

```
[2026-03-26 10:30:45] PreToolUse:Bash | git status | allow | matched allow rule
[2026-03-26 10:31:12] PreToolUse:Bash | rm -rf / | deny | matched deny rule
[2026-03-26 10:32:05] PreToolUse:Bash | docker run ubuntu | pass | no matching rule
[2026-03-26 10:32:08] PostToolUse:Bash | docker run ubuntu | allow | Layer 2 allowed
```

### Log Location

Default: `.claude/guardrail.log`

Configurable via `log_file` in config.

## Security Guarantees

### What Guardrail Protects Against

1. **Accidental destruction**: Blocks `rm -rf /`, `dd`, `mkfs`
2. **Malicious prompts**: LLM detects suspicious patterns
3. **Indirect execution**: Blocks `eval`, `exec`, base64 piping
4. **PATH manipulation**: Deny rules match `/path/to/rm` patterns

### What Guardrail Does NOT Protect Against

1. **Determined attackers**: Users can disable hooks
2. **Novel attack vectors**: Rules must be updated
3. **Social engineering**: Users can approve dangerous actions
4. **Non-tool attacks**: Only guards tool execution

### Fail-Open Philosophy

Guardrail prioritizes user productivity over security:

- Bugs never block users
- Missing config passes through
- LLM errors pass through
- Unknown commands pass to Layer 3

This is appropriate for a development tool where users have full system access anyway.

## Performance

### Layer 1 Latency

- Config load: ~5ms (cached after first load)
- Rule evaluation: <1ms per action
- Python analysis: ~10-50ms (AST parsing)

### Layer 2 Latency

- LLM API call: 200-1000ms
- Sanitization: <1ms
- JSON parsing: <1ms

### Optimization Strategies

1. Layer 1 filters most actions (no LLM call)
2. Config cached in memory
3. Python analysis only for python commands
4. Pending markers use filesystem (no database)

## Extension Points

### Adding New Tools

1. Add tool name to `guarded_tools` in config
2. Add extraction key to `_TOOL_INPUT_KEY` in cli.py
3. Add sanitization logic to `sanitize_target()` in sanitizer.py
4. Add rule category to defaults.yml

### Custom LLM Providers

Implement `_call_provider()` function in llm.py:

```python
def _call_custom(prompt, api_key, model, base_url):
    # Call custom API
    # Return {"decision": "allow"|"deny"|"ask", "reason": "..."}
```

Add to `evaluate_with_llm()` provider dispatch.

### Custom Rule Types

Add new rule category to engine.py:

```python
# After ask check
custom_patterns = config.get("custom_rules", {}).get(rule_category, [])
if _check_custom(target, custom_patterns):
    return {"decision": "custom", "reason": "..."}
```
