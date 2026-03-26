# Guardrail Configuration Schema

Complete YAML configuration schema for guardrail.

## Root Schema

```yaml
guarded_tools: [string]        # Tools to guard (required)
deny_rules: object             # Block rules (optional)
allow_rules: object            # Auto-approve rules (optional)
ask_rules: object              # Prompt rules (optional)
llm: object                    # Layer 2 config (optional)
llm_prompt: string             # Layer 2 prompt template (optional)
log_file: string               # Log file path (optional)
```

## guarded_tools

List of tools to guard. Only these tools will be evaluated.

```yaml
guarded_tools:
  - Bash
  - Write
  - Edit
  - WebFetch
```

**Type**: Array of strings
**Required**: Yes (in defaults.yml)
**Default**: `["Bash", "Write", "Edit", "WebFetch"]`

## deny_rules

Rules that block actions immediately without prompting.

```yaml
deny_rules:
  bash: [string]               # Bash command patterns
  file_path: [string]          # File path patterns
  hostname: [string]           # URL hostname patterns
```

**Type**: Object with arrays of regex strings
**Required**: No
**Merge behavior**: Additive (default deny rules cannot be removed)

### bash

Regex patterns matching bash commands to block.

```yaml
deny_rules:
  bash:
    - "(^|.*/)rm\\s+-rf\\s+/"
    - ":\\(\\)\\{.*:\\|:&\\};"
```

**Pattern matching**: `re.search()` against full command string

### file_path

Regex patterns matching file paths to block.

```yaml
deny_rules:
  file_path:
    - "(^|/)\\.env$"
    - "(^|/)id_(rsa|ed25519)$"
```

**Pattern matching**: `re.search()` against file path

### hostname

Regex patterns matching URL hostnames to block.

```yaml
deny_rules:
  hostname:
    - "^evil\\.com$"
    - ".*\\.malicious\\.org$"
```

**Pattern matching**: `re.search()` against hostname only (not full URL)

## allow_rules

Rules that auto-approve actions without prompting.

```yaml
allow_rules:
  bash: [string]
  file_path: [string]
  hostname: [string]
```

**Type**: Object with arrays of regex strings
**Required**: No
**Merge behavior**: Override (later configs replace earlier)

**Same structure as deny_rules**, but for auto-approval.

## ask_rules

Rules that prompt user for confirmation.

```yaml
ask_rules:
  bash: [string]
  file_path: [string]
  hostname: [string]
```

**Type**: Object with arrays of regex strings
**Required**: No
**Merge behavior**: Override (later configs replace earlier)

**Same structure as deny_rules**, but for prompting.

## llm

Layer 2 LLM classification configuration.

```yaml
llm:
  provider: string             # "anthropic" or "openai"
  api_key: string              # API key
  model: string                # Model name
  base_url: string             # API base URL (optional)
```

**Type**: Object
**Required**: No (Layer 2 disabled if not configured)

### provider

LLM provider to use.

```yaml
llm:
  provider: anthropic
```

**Type**: String
**Values**: `"anthropic"` or `"openai"`
**Default**: `"anthropic"`

### api_key

API key for the LLM provider.

```yaml
llm:
  api_key: sk-ant-...
```

**Type**: String
**Required**: Yes (if llm section present)
**Security**: Never commit to git

### model

Model to use for classification.

```yaml
llm:
  model: claude-3-5-haiku-20241022
```

**Type**: String
**Default**: `"claude-3-5-haiku-20241022"` (Anthropic), `"gpt-4o-mini"` (OpenAI)

### base_url

Custom API base URL.

```yaml
llm:
  base_url: https://api.anthropic.com
```

**Type**: String
**Required**: No
**Default**: Provider default

## llm_prompt

Prompt template for Layer 2 classification.

```yaml
llm_prompt: |
  You are a security classifier for Claude Code actions.
  
  Context: {context}
  User Request: {user_request}
  Tool: {tool_name}
  Target: {sanitized_target}
  
  Classify this action:
  - "allow": Safe, read-only, or clearly matches user intent
  - "deny": Destructive with no legitimate use case
  - "ask": Potentially destructive but legitimate if user confirms
  
  Respond with JSON: {{"decision": "allow"|"deny"|"ask", "reason": "brief explanation"}}
```

**Type**: String (multiline)
**Required**: No
**Default**: See `guardrail/defaults.yml`

**Template variables**:
- `{context}` - Conversation context
- `{user_request}` - User's request
- `{tool_name}` - Tool being used
- `{sanitized_target}` - Sanitized command/path/URL

## log_file

Path to log file for audit trail.

```yaml
log_file: .claude/guardrail.log
```

**Type**: String
**Required**: No
**Default**: `.claude/guardrail.log`

## Complete Example

```yaml
guarded_tools:
  - Bash
  - Write
  - Edit
  - WebFetch

deny_rules:
  bash:
    - "(^|.*/)rm\\s+-rf\\s+/"
    - "kubectl delete namespace prod"
  file_path:
    - "(^|/)\\.env$"
    - "secrets\\.yml$"
  hostname:
    - "^evil\\.com$"

allow_rules:
  bash:
    - "^git\\s+status"
    - "^ls\\s"
    - "^\\./scripts/safe-deploy\\.sh"
  file_path:
    - ".*"
  hostname: []

ask_rules:
  bash:
    - "^python[0-9.]*\\s"
    - "^git\\s+push"
    - "^kubectl apply"
  file_path: []
  hostname: []

llm:
  provider: anthropic
  api_key: ${ANTHROPIC_AUTH_TOKEN}
  model: claude-3-5-haiku-20241022
  base_url: https://api.anthropic.com

log_file: .claude/guardrail.log
```

## Environment Variable Substitution

Config values can reference environment variables:

```yaml
llm:
  api_key: ${ANTHROPIC_AUTH_TOKEN}
  base_url: ${ANTHROPIC_BASE_URL}
```

**Note**: Only works for LLM config when using environment variable fallback, not in YAML files.

## Validation

Validate config with:

```bash
python -m guardrail.cli --check
```

Returns exit code 0 if valid, 1 if invalid.
