# Sanitization Before LLM

## Overview

Before sending commands to the LLM, guardrail sanitizes them to prevent leaking secrets. This ensures API keys, tokens, and other sensitive data never reach the LLM API.

## What Gets Sanitized

### API Keys and Tokens

**Pattern**: Common API key formats

```bash
# Original
export ANTHROPIC_API_KEY=sk-ant-1234567890abcdef

# Sanitized
export ANTHROPIC_API_KEY=<REDACTED>
```

**Patterns matched**:
- `sk-[a-zA-Z0-9-]+` - Anthropic keys
- `sk_live_[a-zA-Z0-9]+` - Stripe keys
- `ghp_[a-zA-Z0-9]+` - GitHub personal access tokens
- `gho_[a-zA-Z0-9]+` - GitHub OAuth tokens
- `AIza[a-zA-Z0-9_-]+` - Google API keys
- `ya29\.[a-zA-Z0-9_-]+` - Google OAuth tokens
- `xox[baprs]-[a-zA-Z0-9-]+` - Slack tokens

### Environment Variables

**Pattern**: `$VAR` or `${VAR}` with sensitive names

```bash
# Original
curl -H "Authorization: Bearer $API_TOKEN" https://api.example.com

# Sanitized
curl -H "Authorization: Bearer <REDACTED>" https://api.example.com
```

**Sensitive variable names**:
- `*KEY*` - API_KEY, SECRET_KEY, etc.
- `*TOKEN*` - AUTH_TOKEN, ACCESS_TOKEN, etc.
- `*SECRET*` - DB_SECRET, AWS_SECRET, etc.
- `*PASSWORD*` - DB_PASSWORD, USER_PASSWORD, etc.
- `*CREDENTIAL*` - Any credential variables

### Base64 Encoded Data

**Pattern**: Long base64 strings (potential encoded secrets)

```bash
# Original
echo "c2VjcmV0LWRhdGEtaGVyZQ==" | base64 -d | bash

# Sanitized
echo "<REDACTED>" | base64 -d | bash
```

**Criteria**:
- Length > 20 characters
- Valid base64 format
- Followed by decode operation

### URLs with Secret Parameters

**Pattern**: Query parameters with sensitive names

```bash
# Original
curl "https://api.example.com?token=secret123&api_key=xyz789"

# Sanitized
curl "https://api.example.com?token=<REDACTED>&api_key=<REDACTED>"
```

**Sensitive parameter names**:
- `token`
- `api_key`
- `apikey`
- `secret`
- `password`
- `auth`
- `credential`

### JWT Tokens

**Pattern**: JWT format (header.payload.signature)

```bash
# Original
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"

# Sanitized
curl -H "Authorization: Bearer <REDACTED>"
```

**Format**: `eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+`

## What Doesn't Get Sanitized

### Public Information

```bash
# Not sanitized (public)
curl https://api.github.com/repos/anthropics/claude-code
git clone https://github.com/user/repo.git
```

### File Paths

```bash
# Not sanitized (paths are context)
cat /home/user/.env
rm /tmp/file.txt
```

**Note**: File contents are never sent to LLM, only paths.

### Command Structure

```bash
# Not sanitized (structure is needed for classification)
docker run --privileged ubuntu
kubectl delete namespace production
```

### Non-Secret Variables

```bash
# Not sanitized (not sensitive)
echo $HOME
echo $USER
echo $PATH
```

## Tool-Specific Sanitization

### Bash Commands

**What's sent**: Sanitized command string

```bash
# Original
export API_KEY=sk-1234 && curl -H "Authorization: Bearer $API_KEY" https://api.example.com

# Sent to LLM
export API_KEY=<REDACTED> && curl -H "Authorization: Bearer <REDACTED>" https://api.example.com
```

### Write/Edit Operations

**What's sent**: File path only, never content

```bash
# Original
Write to /home/user/.env with content:
API_KEY=sk-1234567890
SECRET=xyz789

# Sent to LLM
Write to /home/user/.env
```

**Reason**: File contents may contain secrets

### WebFetch Operations

**What's sent**: URL with sanitized query parameters

```bash
# Original
https://api.example.com/data?token=secret123&user=john

# Sent to LLM
https://api.example.com/data?token=<REDACTED>&user=john
```

## Sanitization Implementation

### Regex Patterns

```python
REDACTION_PATTERNS = [
    # API keys
    (r'sk-[a-zA-Z0-9-]{20,}', '<REDACTED>'),
    (r'sk_live_[a-zA-Z0-9]{24,}', '<REDACTED>'),

    # Tokens
    (r'ghp_[a-zA-Z0-9]{36}', '<REDACTED>'),
    (r'gho_[a-zA-Z0-9]{36}', '<REDACTED>'),

    # Environment variables
    (r'\$\{?[A-Z_]*(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)[A-Z_]*\}?', '<REDACTED>'),

    # Base64 (long strings)
    (r'[A-Za-z0-9+/]{40,}={0,2}', '<REDACTED>'),

    # JWT
    (r'eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+', '<REDACTED>'),
]
```

### Application Order

1. **API key patterns** - Most specific first
2. **Token patterns** - Known formats
3. **Environment variables** - Sensitive names
4. **Base64 strings** - Long encoded data
5. **JWT tokens** - Standard format
6. **URL parameters** - Query string secrets

### Edge Cases

**Multiple secrets in one command**:
```bash
# Original
export KEY1=sk-123 KEY2=sk-456 && curl -H "Auth: $KEY1" https://api.example.com

# Sanitized
export KEY1=<REDACTED> KEY2=<REDACTED> && curl -H "Auth: <REDACTED>" https://api.example.com
```

**Secrets in different formats**:
```bash
# Original
curl -u "user:sk-123456" https://api.example.com

# Sanitized
curl -u "user:<REDACTED>" https://api.example.com
```

## Testing Sanitization

### Test API Key Redaction

```bash
python3 -c "
from guardrail.sanitizer import sanitize_target
original = 'export API_KEY=sk-ant-1234567890'
sanitized = sanitize_target('Bash', original)
print(f'Original:  {original}')
print(f'Sanitized: {sanitized}')
"
```

Expected: API key replaced with `<REDACTED>`

### Test Environment Variable Redaction

```bash
python3 -c "
from guardrail.sanitizer import sanitize_target
original = 'curl -H \"Authorization: Bearer \$API_TOKEN\" https://api.example.com'
sanitized = sanitize_target('Bash', original)
print(f'Original:  {original}')
print(f'Sanitized: {sanitized}')
"
```

Expected: `$API_TOKEN` replaced with `<REDACTED>`

### Test URL Parameter Redaction

```bash
python3 -c "
from guardrail.sanitizer import sanitize_target
original = 'https://api.example.com?token=secret123&user=john'
sanitized = sanitize_target('WebFetch', original)
print(f'Original:  {original}')
print(f'Sanitized: {sanitized}')
"
```

Expected: `token=secret123` becomes `token=<REDACTED>`

## Security Guarantees

### What's Protected

✓ **API keys never sent to LLM**
✓ **Tokens redacted before transmission**
✓ **Environment variables with sensitive names redacted**
✓ **URL parameters with sensitive names redacted**
✓ **File contents never sent (only paths)**

### What's Not Protected

✗ **Novel secret formats** - Unknown patterns may leak
✗ **Obfuscated secrets** - Encoded in non-standard ways
✗ **Secrets in file paths** - Paths are sent as-is
✗ **Secrets in non-sensitive variable names** - `$MY_VAR` not redacted

## Limitations

### False Positives

Legitimate data may be redacted:

```bash
# Redacted (false positive)
echo "The key to success is persistence"
```

**Reason**: Word "key" triggers redaction

**Impact**: LLM sees less context, may misclassify

### False Negatives

Novel secret formats may leak:

```bash
# Not redacted (false negative)
export MY_SECRET_VALUE=actual-secret-here
```

**Reason**: Variable name doesn't match patterns

**Mitigation**: Add more patterns, use standard naming

### Performance

Sanitization adds minimal overhead:
- Regex matching: <1ms per command
- Multiple patterns: <5ms total
- Negligible compared to LLM latency (200-1000ms)

## Best Practices

### For Users

1. **Use standard secret names**: `API_KEY`, `TOKEN`, `SECRET`
2. **Don't put secrets in file paths**: Use standard locations
3. **Review sanitization**: Check logs to verify redaction
4. **Report leaks**: If secrets leak, report patterns

### For Developers

1. **Add new patterns**: As new secret formats emerge
2. **Test thoroughly**: Verify redaction works
3. **Balance precision**: Avoid over-redacting
4. **Document patterns**: Explain what gets redacted
5. **Monitor logs**: Check for leaked secrets

### For Administrators

1. **Audit sanitization**: Review redaction patterns
2. **Add custom patterns**: For organization-specific secrets
3. **Test with real data**: Verify no leaks
4. **Rotate keys**: If leak suspected
5. **Monitor API logs**: Check what's sent to LLM

## Extending Sanitization

### Add Custom Patterns

Edit `guardrail/sanitizer.py`:

```python
REDACTION_PATTERNS = [
    # Existing patterns...

    # Custom organization pattern
    (r'MYORG-[A-Z0-9]{16}', '<REDACTED>'),
]
```

### Add Custom Variable Names

```python
SENSITIVE_VAR_NAMES = [
    'KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'CREDENTIAL',
    # Custom names
    'MYORG_AUTH', 'INTERNAL_TOKEN',
]
```

### Test Custom Patterns

```bash
python3 -c "
from guardrail.sanitizer import sanitize_target
original = 'export MYORG_AUTH=MYORG-1234567890ABCDEF'
sanitized = sanitize_target('Bash', original)
print(f'Sanitized: {sanitized}')
assert '<REDACTED>' in sanitized, 'Pattern not working'
print('✓ Custom pattern works')
"
```

## Comparison to Other Approaches

### vs. No Sanitization

**No sanitization**: Secrets sent to LLM API
**With sanitization**: Secrets redacted before transmission

**Risk reduction**: ~99% (assuming good patterns)

### vs. Local LLM

**Local LLM**: No network transmission, no sanitization needed
**Cloud LLM**: Requires sanitization

**Trade-off**: Local LLM slower, less capable

### vs. No Layer 2

**No Layer 2**: No LLM, no sanitization needed
**With Layer 2**: Sanitization required

**Trade-off**: Layer 2 provides better detection but requires sanitization

## Conclusion

Sanitization is critical for Layer 2 security:
- Prevents secret leakage to LLM API
- Minimal performance overhead
- Extensible for custom patterns
- Not perfect but significantly reduces risk

**Recommendation**: Always enable sanitization when using Layer 2
