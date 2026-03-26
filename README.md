# Claude Code Guardrail

A security hook for Claude Code that provides rule-based and LLM-powered classification of tool actions before execution.

## Features

- **Three-layer security model:**
  - **Layer 1**: Fast regex-based rules (deny/allow/ask)
  - **Layer 2**: LLM-based classification for ambiguous actions
  - **Layer 3**: User confirmation prompts

- **Python script safety analysis**: AST-based whitelist/blacklist checking for safe read-only scripts

- **Secret sanitization**: Redacts API keys, tokens, and credentials before LLM evaluation

- **Fail-open design**: Never blocks users due to guardrail bugs

## Installation

### Prerequisites

- Python 3.10+
- PyYAML: `pip install pyyaml`
- (Optional) Anthropic SDK for Layer 2: `pip install anthropic`

### Install as Claude Code Hook

```bash
# Clone the repository
git clone https://github.com/yourusername/claude-guardrail.git
cd claude-guardrail

# Install for current project
./guardrail/install.sh

# Or install globally for all projects
./guardrail/install.sh --scope user
```

## Configuration

### Layer 1: Rule-based Classification

Create `.claude/guardrail.yml` in your project or `~/.claude/guardrail.yml` for global config:

```yaml
deny_rules:
  bash:
    - "custom-dangerous-command"
  file_path:
    - "secret-config.yml"

allow_rules:
  bash:
    - "^my-safe-tool\\s"

ask_rules:
  bash:
    - "^deploy\\s"
```

### Layer 2: LLM Classification

Configure LLM credentials in `~/.claude/guardrail.yml`:

```yaml
llm:
  provider: anthropic  # or openai
  api_key: your-api-key
  model: claude-3-5-haiku-20241022
  base_url: https://api.anthropic.com  # optional
```

Or use environment variables:

```bash
export ANTHROPIC_AUTH_TOKEN=your-api-key
export ANTHROPIC_MODEL=claude-3-5-haiku-20241022
export ANTHROPIC_BASE_URL=https://api.anthropic.com  # optional
```

## Decision Flow

```
Tool Action
    ↓
Deny Rules? → DENY (block immediately)
    ↓
Allow Rules? → ALLOW (auto-approve)
    ↓
Ask Rules? → ASK (prompt user)
    ↓
Layer 2 LLM → allow/deny/ask
    ↓
Pass → Claude Code built-in prompting
```

## Examples

```bash
# Test deny rule
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"rm -rf /"}}' | python -m guardrail.cli

# Test allow rule
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"git status"}}' | python -m guardrail.cli

# Test Layer 2 (requires LLM configured)
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"docker run ubuntu"}}' | python -m guardrail.cli
```

## Development

```bash
# Run tests
python -m pytest tests/ -v

# Verify config loads
python -m guardrail.cli --check
```

## License

MIT
