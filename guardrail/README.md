# Guardrail -- Security Hook for Claude Code

A PreToolUse hook that checks Claude Code actions against deny/allow rules before execution, optionally deferring ambiguous cases to LLM classification.

## Architecture

Guardrail uses two security layers:

**Layer 1 -- Fast Regex Rules** (command hook, PreToolUse)

Runs deny-before-allow pattern matching against the tool's target (command, file path, or hostname). Deny rules are checked first; a deny match always wins even if an allow rule also matches.

For Bash commands, the input is split on shell operators (`;`, `&&`, `||`, `|`) and substitutions (`$(...)`, backticks, `<(...)`, `>(...)`) are extracted recursively. Each segment is checked independently, so `safe-cmd; rm -rf /` is caught even though the first segment is benign.

**Layer 2 -- LLM Classification** (prompt hook)

When no rule matches, the decision is `pass` and the action is deferred to an LLM classifier. Secrets are redacted before any content is sent to the LLM (see `sanitizer.py`).

## Guarded Tools

| Tool | Target Extracted | Rule Category |
|------|-----------------|---------------|
| Bash | `command` | `bash` |
| Write | `file_path` | `file_path` |
| Edit | `file_path` | `file_path` |
| WebFetch | hostname from `url` | `hostname` |

Unguarded tools are auto-allowed without evaluation.

## Decision Logic

1. Tool not in `guarded_tools` --> **ALLOW**
2. Deny rule matches any segment --> **DENY**
3. Allow rule matches --> **ALLOW**
4. No match --> **PASS** (defer to Layer 2)

## Installation

```bash
# Project scope (recommended for testing)
bash guardrail/install.sh --scope project

# User scope (after thorough testing)
bash guardrail/install.sh --scope user
```

## Configuration

Configs are loaded in order and merged additively (lists append, dicts merge recursively):

1. **Default** -- `guardrail/defaults.yml` (shipped with the project)
2. **User** -- `~/.claude/guardrail.yml` (personal overrides)
3. **Project** -- `.claude/guardrail.yml` (per-repo overrides)

### Example Custom Config

```yaml
# .claude/guardrail.yml -- project-level overrides

deny_rules:
  bash:
    - "curl\\s.*\\|\\s*sh"     # pipe-to-shell
  file_path:
    - "/etc/"                  # block writes outside project

allow_rules:
  bash:
    - "^make\\s"               # allow make commands
  hostname:
    - "^api\\.example\\.com$"  # allow your API domain
```

Lists in custom configs are **appended** to the defaults (not replaced), so your rules add to the built-in set. Scalar values (like `log_file`) are overwritten.

## Audit Log

All decisions are recorded as JSON-lines at `.claude/guardrail.log`:

```json
{"timestamp": "2026-03-26T12:00:00.000000", "tool": "Bash", "target": "git status", "decision": "allow", "reason": "bash command matched allow rule"}
```

Targets are sanitized before logging -- secrets are redacted and file content is never included.

## Fail-Open Design

The guardrail is designed to **never block due to its own bugs**:

- All top-level errors in the CLI are caught and result in a silent `exit 0` (pass-through).
- Config loading errors in user/project overrides are logged as warnings and skipped.
- Logging failures are silently swallowed.
- Invalid deny regex patterns fail closed (match = deny); invalid allow patterns fail open (no match).
