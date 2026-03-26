---
name: Understanding Guardrail
description: This skill should be used when the user asks "how does guardrail work", "explain guardrail", "what is guardrail decision flow", "what is Layer 2", "guardrail architecture", or wants to understand the security classification system.
version: 0.1.0
---

# Understanding Claude Guardrail

## Overview

Claude Guardrail is a security hook system that classifies tool actions before execution using a three-layer model: fast rule-based filtering, LLM-powered classification for ambiguous cases, and user confirmation prompts.

## Three-Layer Security Model

### Layer 1: Rule-Based Classification

Fast regex pattern matching against configured rules:

| Rule Type | Purpose | Example |
|-----------|---------|---------|
| **Deny** | Block dangerous operations | `rm -rf /`, fork bombs, destructive commands |
| **Allow** | Auto-approve safe operations | `git status`, `ls`, read-only commands |
| **Ask** | Prompt for confirmation | Script execution, git push, package installs |

**Decision priority**: Deny rules always win, even if allow rules also match.

### Layer 2: LLM Classification

When Layer 1 returns "pass" (no rule match), an optional LLM evaluates the action:

- Analyzes sanitized command/target with context
- Returns: allow (safe), deny (malicious), or ask (needs confirmation)
- Falls back to Layer 3 if not configured

**Sanitization**: Secrets, API keys, and file contents are redacted before sending to LLM.

### Layer 3: Claude Code Prompting

If Layers 1 and 2 pass, Claude Code's built-in permission system prompts the user.

## Decision Flow

```
Tool Action
    ↓
Layer 1: Deny Rules? → DENY (block immediately)
    ↓
Layer 1: Allow Rules? → ALLOW (auto-approve)
    ↓
Layer 1: Ask Rules? → ASK (prompt user)
    ↓
Layer 2: LLM Classification → allow/deny/ask
    ↓
Layer 3: Claude Code Prompt → user decides
```

## Python Script Safety

Special handling for `python`/`python3` commands:

1. Extract script path from command
2. Parse script with AST to check imports
3. Scan for dangerous patterns (file writes, subprocess, os operations)
4. If safe (read-only with whitelisted modules) → auto-allow
5. Otherwise → ask for confirmation

**Whitelisted modules**: pandas, numpy, matplotlib, json, collections, itertools, math, etc.

**Dangerous patterns**: `open(..., 'w')`, `os.remove()`, `subprocess.*`, `.to_csv()`, etc.

## Hook Events

Guardrail responds to two Claude Code hook events:

**PreToolUse**: Fires before tool execution
- Evaluates action through Layers 1-2
- Returns decision: allow, deny, or ask
- Creates pending marker if passed to Layer 3

**PostToolUse**: Fires after tool execution
- Resolves pending markers (action was allowed)
- Logs final outcome for audit trail

## Configuration Layering

Config files merge with priority:

1. **Defaults** (`guardrail/defaults.yml`) - Base rules, always present
2. **User config** (`~/.claude/guardrail.yml`) - Global overrides
3. **Project config** (`.claude/guardrail.yml`) - Project-specific rules
4. **Environment variables** - Runtime overrides

**Deny rule protection**: Default deny rules can never be removed by user/project configs (additive only).

## Fail-Open Design

Guardrail never blocks users due to its own bugs:

- All exceptions caught and logged
- Errors result in silent pass-through
- Hook exits with code 0 on any failure
- User workflow continues uninterrupted

## Bypass Mode

When Claude Code runs in bypass-permissions mode, guardrail automatically passes through without evaluation.

## Additional Resources

### Reference Files

For detailed information:
- **`references/architecture.md`** - Deep dive into implementation
- **`references/security-model.md`** - Threat model and security guarantees
- **`references/decision-examples.md`** - Example decisions for common scenarios

### Example Files

Working examples in `examples/`:
- **`example-decisions.txt`** - Sample commands and their classifications
