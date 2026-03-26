---
name: Layer 2 Setup
description: This skill should be used when the user asks to "configure Layer 2", "set up LLM classification", "enable AI detection", "configure Anthropic API", "add LLM to guardrail", or wants to enable advanced threat detection with AI.
version: 0.1.0
---

# Layer 2 Setup (LLM Classification)

## Overview

Layer 2 adds AI-powered classification to guardrail, using Claude to detect novel attacks and context-dependent threats that Layer 1 rules miss. This is optional but recommended for enhanced security.

**When to use Layer 2**:
- Detect novel attack patterns not in deny rules
- Analyze context-dependent threats
- Classify ambiguous commands
- Reduce false positives from overly broad rules

**Trade-offs**:
- Adds 200-1000ms latency per unmatched command
- Requires Anthropic API key (costs money)
- Sends sanitized commands to API (secrets redacted)
- Can be fooled by adversarial prompts

## Quick Setup

### Step 1: Get API Key

1. Visit https://console.anthropic.com
2. Create account or sign in
3. Navigate to API Keys section
4. Create new API key
5. Copy key (starts with `sk-ant-`)

### Step 2: Configure Layer 2

Create `.claude/guardrail.local.md`:

```markdown
---
llm:
  provider: anthropic
  api_key: ${ANTHROPIC_AUTH_TOKEN}
  model: claude-3-5-sonnet-20241022
---
```

### Step 3: Set Environment Variable

```bash
export ANTHROPIC_AUTH_TOKEN=sk-ant-your-key-here
```

Add to shell profile for persistence:

```bash
echo 'export ANTHROPIC_AUTH_TOKEN=sk-ant-your-key-here' >> ~/.bashrc
source ~/.bashrc
```

### Step 4: Test Layer 2

```bash
# Command with no Layer 1 rule (should pass to Layer 2)
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"docker run ubuntu"}}' | python -m guardrail.cli
```

Expected: Decision from LLM (allow/deny/ask)

Check logs:
```bash
grep "Layer 2" .claude/guardrail.log
```

## Configuration Options

### Provider: Anthropic (Default)

```yaml
llm:
  provider: anthropic
  api_key: ${ANTHROPIC_AUTH_TOKEN}
  model: claude-3-5-sonnet-20241022
  base_url: https://api.anthropic.com  # Optional
```

**Models**:
- `claude-3-5-sonnet-20241022` - Recommended (fast, accurate)
- `claude-3-opus-20240229` - Most capable (slower, expensive)
- `claude-3-haiku-20240307` - Fastest (less accurate)

### Environment Variable Substitution

Use `${VAR_NAME}` for environment variables:

```yaml
llm:
  api_key: ${ANTHROPIC_AUTH_TOKEN}
  model: ${GUARDRAIL_MODEL:-claude-3-5-sonnet-20241022}
```

**Syntax**:
- `${VAR}` - Required variable (error if not set)
- `${VAR:-default}` - Optional with default value

### Configuration Priority

Layer 2 config loads from multiple sources (highest priority first):

1. **Environment variables**: `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_MODEL`, `ANTHROPIC_BASE_URL`
2. **Local config**: `.claude/guardrail.local.md` (YAML frontmatter)
3. **Project config**: `.claude/guardrail.yml` (llm section)
4. **User config**: `~/.claude/guardrail.yml` (llm section)

**Recommendation**: Use `.claude/guardrail.local.md` for API keys (gitignored), project config for model selection.

## Security Considerations

### What Gets Sent to LLM

**Bash commands**: Sanitized (secrets redacted)
```
Original: export API_KEY=sk-1234567890
Sent:     export API_KEY=<REDACTED>
```

**File paths**: Path only, never content
```
Original: Write to /home/user/.env with content "SECRET=xyz"
Sent:     Write to /home/user/.env
```

**URLs**: Sanitized (secret query params redacted)
```
Original: https://api.example.com?token=secret123
Sent:     https://api.example.com?token=<REDACTED>
```

### What Never Gets Sent

- File contents
- Command output
- Environment variables (except in commands, redacted)
- User context or conversation history
- Previous decisions

### API Key Security

**Storage**:
- Store in environment variable (not in config files)
- Use `.claude/guardrail.local.md` with `${ANTHROPIC_AUTH_TOKEN}`
- Add `.claude/*.local.md` to `.gitignore`

**Permissions**:
- API key has full account access
- Rotate keys periodically
- Use separate key for guardrail if possible

**Exposure risks**:
- Never commit API keys to git
- Don't log API keys
- Don't share config files with keys

## Testing Layer 2

### Test 1: Novel Command

```bash
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"docker run --privileged ubuntu"}}' | python -m guardrail.cli
```

Expected: LLM classifies (likely "ask" due to --privileged)

### Test 2: Destructive API Call

```bash
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"curl -X DELETE https://api.example.com/users"}}' | python -m guardrail.cli
```

Expected: LLM detects destructive operation (likely "deny" or "ask")

### Test 3: Safe Container

```bash
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"docker ps"}}' | python -m guardrail.cli
```

Expected: LLM allows (safe read-only operation)

### Test 4: Check Logs

```bash
grep "Layer 2" .claude/guardrail.log
```

Expected: Entries showing LLM decisions

## Troubleshooting

### Error: API key not set

```
Error: ANTHROPIC_AUTH_TOKEN not set
```

**Solution**:
```bash
export ANTHROPIC_AUTH_TOKEN=sk-ant-your-key-here
```

### Error: 401 Unauthorized

```
Error: 401 Unauthorized
```

**Solution**: API key invalid or expired
- Verify key: `echo $ANTHROPIC_AUTH_TOKEN`
- Generate new key at console.anthropic.com
- Update environment variable

### Error: 429 Too Many Requests

```
Error: 429 Too Many Requests
```

**Solution**: Rate limit exceeded
- Wait before retrying
- Add more Layer 1 rules to reduce LLM calls
- Use allow/deny rules for common commands

### Error: Network timeout

```
Error: Connection timeout
```

**Solution**:
- Check network connectivity: `curl https://api.anthropic.com`
- Increase timeout in hooks.json (default 10000ms)
- Check firewall/proxy settings

### Layer 2 not activating

**Symptom**: Commands pass through without LLM classification

**Diagnosis**:
```bash
# Check config
python3 -c "
from guardrail.config import load_config
config = load_config()
print('LLM config:', config.get('llm', {}))
"

# Check environment variable
echo $ANTHROPIC_AUTH_TOKEN
```

**Solution**:
- Verify API key set
- Check config file syntax
- Ensure command doesn't match Layer 1 rules (LLM only for "pass")

## Performance Optimization

### Reduce LLM Calls

Add Layer 1 rules for common commands:

```yaml
# .claude/guardrail.yml
allow_rules:
  bash:
    - "^docker\\s+ps"
    - "^docker\\s+images"
    - "^kubectl\\s+get"

ask_rules:
  bash:
    - "^docker\\s+run"
    - "^kubectl\\s+apply"
```

### Monitor Usage

```bash
# Count Layer 2 calls
grep -c "Layer 2" .claude/guardrail.log

# Show Layer 2 decisions
grep "Layer 2" .claude/guardrail.log | tail -n 20
```

### Cost Estimation

**Pricing** (as of 2024):
- Claude 3.5 Sonnet: ~$3 per million input tokens
- Average command: ~100 tokens
- Cost per command: ~$0.0003

**Example**:
- 1000 commands/day → $0.30/day → $9/month
- Most commands match Layer 1 (free)
- Only novel commands use Layer 2

## Advanced Configuration

### Custom Model

```yaml
llm:
  provider: anthropic
  api_key: ${ANTHROPIC_AUTH_TOKEN}
  model: claude-3-opus-20240229  # More capable
```

### Custom Base URL

For proxy or custom endpoint:

```yaml
llm:
  provider: anthropic
  api_key: ${ANTHROPIC_AUTH_TOKEN}
  base_url: https://proxy.example.com/anthropic
```

### Disable Layer 2

Remove `llm` section from config or unset environment variable:

```bash
unset ANTHROPIC_AUTH_TOKEN
```

## Best Practices

### When to Enable Layer 2

✓ **Enable if**:
- Working with untrusted code/prompts
- Need detection of novel attacks
- Want context-aware classification
- Can afford latency and cost

✗ **Skip if**:
- Only need basic protection
- Latency critical
- No API key available
- Offline environment

### Configuration Strategy

1. **Start with Layer 1 only**: Test basic deny/allow/ask rules
2. **Add Layer 2**: Enable for enhanced detection
3. **Monitor logs**: See what Layer 2 catches
4. **Refine Layer 1**: Add rules for common patterns
5. **Optimize**: Reduce LLM calls with better Layer 1 rules

### Security Hardening

1. **Rotate API keys**: Change keys periodically
2. **Monitor usage**: Check API dashboard for anomalies
3. **Review decisions**: Audit Layer 2 classifications
4. **Test adversarial prompts**: Verify LLM robustness
5. **Keep updated**: Update guardrail for improved prompts

## Additional Resources

### Reference Files

For detailed Layer 2 information:
- **`references/llm-classification.md`** - How LLM classification works
- **`references/sanitization.md`** - What gets redacted before LLM
- **`references/adversarial-resistance.md`** - LLM security considerations

### Example Files

Working Layer 2 configurations in `examples/`:
- **`layer2-basic.yml`** - Minimal Layer 2 setup
- **`layer2-advanced.yml`** - Full configuration options
- **`test-layer2.sh`** - Layer 2 testing commands
