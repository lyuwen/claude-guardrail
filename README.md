# Claude Guardrail Plugin

Security hook with rule-based and LLM-powered action classification for Claude Code.

## Overview

Claude Guardrail is a Claude Code plugin that provides a security layer for AI assistant tool execution. It uses a three-layer defense model to prevent accidental destruction, detect prompt injection attacks, and provide context-aware threat detection.

**Key Features**:
- **Layer 1**: Fast rule-based classification (deny/allow/ask)
- **Layer 2**: Optional LLM-powered detection for novel threats
- **Layer 3**: User confirmation for ambiguous actions
- **Auto-install hooks**: Automatic integration with Claude Code
- **Comprehensive skills**: Built-in documentation and troubleshooting

## Quick Start

### 1. Install Dependencies

```bash
# Python 3.10+ required
python3 --version

# Install PyYAML
pip3 install pyyaml

# Optional: Install Anthropic SDK for Layer 2
pip3 install anthropic
```

### 2. Install Plugin

**Recommended: Install from marketplace**

```bash
# Add marketplace
/plugin marketplace add lyuwen/claude-guardrail

# Install plugin
/plugin install claude-guardrail@claude-guardrail
```

**Alternative: Install from GitHub**

```bash
cc plugin add https://github.com/lyuwen/claude-guardrail.git
```

The plugin will automatically:
- Register PreToolUse and PostToolUse hooks
- Make 4 skills available for help and configuration
- Start intercepting tool use for security checks

### 3. Test Installation

```bash
# Run test suite
bash hooks/scripts/test-guardrail.sh
```

Expected: All tests pass with correct deny/allow/ask decisions.

### 4. Use with Claude Code

The plugin provides 4 skills that automatically activate when you ask relevant questions:

**Understanding Guardrail**:
```
"How does guardrail work?"
"Explain the security model"
```

**Configuring Rules**:
```
"Add a guardrail rule to block kubectl delete"
"How do I allow my deployment script?"
```

**Troubleshooting**:
```
"Guardrail not working"
"Why was this command blocked?"
```

**Layer 2 Setup**:
```
"Configure Layer 2"
"Set up LLM classification"
```

## How It Works

### Three-Layer Security Model

**Layer 1: Rule-Based Classification**
- Fast regex pattern matching (<1ms)
- Deny rules block known dangerous commands
- Allow rules auto-approve safe operations
- Ask rules prompt for potentially risky actions

**Layer 2: LLM Classification (Optional)**
- AI-powered detection for novel threats
- Context-aware analysis
- Sanitizes secrets before sending to API
- 200-1000ms latency, requires API key

**Layer 3: User Confirmation**
- Final decision for ambiguous cases
- Human judgment for context-dependent threats
- Audit trail in logs

### Decision Flow

```
Command → Layer 1 Rules → Layer 2 LLM → User Prompt → Execute/Block
          (deny/allow/ask)   (if pass)     (if ask)
```

## Configuration

### Basic Configuration

Create `.claude/guardrail.yml` for project-specific rules:

```yaml
deny_rules:
  bash:
    - "kubectl delete namespace prod"  # Block prod deletion
  file_path:
    - "config/production\\.yml"        # Block prod config edits

allow_rules:
  bash:
    - "^\\./scripts/safe-deploy\\.sh"  # Allow specific script

ask_rules:
  bash:
    - "^kubectl apply"                 # Prompt for k8s changes
```

### Layer 2 Configuration (Optional)

Create `.claude/guardrail.local.md` for LLM classification:

```markdown
---
llm:
  provider: anthropic
  api_key: ${ANTHROPIC_AUTH_TOKEN}
  model: claude-3-5-sonnet-20241022
---
```

Set environment variable:
```bash
export ANTHROPIC_AUTH_TOKEN=sk-ant-your-key-here
```

## Skills

The plugin includes 4 comprehensive skills:

### 1. Understanding Guardrail
- How guardrail works
- Security model explanation
- Decision flow and architecture

### 2. Configuring Rules
- Adding deny/allow/ask rules
- Regex pattern syntax
- Configuration file structure

### 3. Troubleshooting
- Debugging hook issues
- Reading logs
- Testing rules manually
- Common errors and solutions

### 4. Layer 2 Setup
- Configuring LLM classification
- API key setup
- Performance optimization
- Security considerations

## Examples

### Block Dangerous Commands

```yaml
# .claude/guardrail.yml
deny_rules:
  bash:
    - "rm\\s+-rf\\s+/"              # Delete root
    - ":(\\){.*:\\|:&\\};"          # Fork bomb
    - "kubectl delete namespace prod"  # Prod deletion
```

### Allow Safe Scripts

```yaml
allow_rules:
  bash:
    - "^\\./scripts/test\\.sh"      # Test script
    - "^\\./scripts/lint\\.sh"      # Lint script
```

### Prompt for Deployments

```yaml
ask_rules:
  bash:
    - "^\\./deploy"                 # Any deploy script
    - "^git\\s+push\\s+--force"     # Force push
```

## Testing

See [TESTING.md](TESTING.md) for comprehensive testing guide.

Quick test:
```bash
# Test deny rule
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"rm -rf /"}}' | python -m guardrail.cli

# Expected: {"permissionDecision": "deny"}
```

## Logs

View decisions in `.claude/guardrail.log`:

```bash
tail -n 20 .claude/guardrail.log
```

Log format:
```
[2026-03-26 10:30:45] PreToolUse:Bash | git status | allow | matched allow rule
[2026-03-26 10:31:12] PreToolUse:Bash | rm -rf / | deny | matched deny rule
```

## Troubleshooting

### Hooks Not Firing

```bash
# Check hook registration
grep -A 5 "PreToolUse" .claude/settings.json | grep guardrail

# Reinstall if missing
bash hooks/scripts/install-hooks.sh
```

### Wrong Decisions

```bash
# Test command manually
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"YOUR_COMMAND"}}' | python -m guardrail.cli

# Check logs
grep "YOUR_COMMAND" .claude/guardrail.log
```

For more troubleshooting, ask Claude: "Guardrail not working" to load the troubleshooting skill.

## License

MIT
