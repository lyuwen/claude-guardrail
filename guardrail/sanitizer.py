"""Sanitizer for redacting secrets and summarizing content before LLM evaluation.

Ensures that actual secrets, file contents, and sensitive query parameters
are never sent to the LLM classifier.
"""

import re
from urllib.parse import urlparse, parse_qs, urlunparse


# ---------------------------------------------------------------------------
# Secret patterns: each is (compiled regex, replacement description)
# Order matters -- more specific patterns should come before generic ones.
# ---------------------------------------------------------------------------

# AWS Access Key IDs: AKIA followed by 16 uppercase alphanumeric chars
_RE_AWS_KEY = re.compile(r'AKIA[A-Z0-9]{16}')

# OpenAI-style keys: sk- followed by 20+ alphanumeric chars
_RE_SK_KEY = re.compile(r'sk-[a-zA-Z0-9]{20,}')

# GitHub Personal Access Tokens: ghp_ followed by 36 alphanumeric chars
_RE_GHP_KEY = re.compile(r'ghp_[a-zA-Z0-9]{36}')

# Bearer tokens: "Bearer " followed by a token string
_RE_BEARER = re.compile(r'Bearer\s+[a-zA-Z0-9._\-]+')

# Private key headers
_RE_PRIVATE_KEY = re.compile(r'-----BEGIN\s+[\w\s]*PRIVATE\s+KEY-----')

# Environment variable assignments with secret-like names (case insensitive).
# Matches: SOME_TOKEN=value, SECRET_KEY="value", PASSWORD='value', etc.
# The name part must contain one of the sensitive keywords.
_SECRET_ENV_KEYWORDS = (
    r'TOKEN|SECRET|PASSWORD|API_KEY|CREDENTIAL|PASSPHRASE|AUTH'
)
_RE_ENV_SECRET = re.compile(
    r'(?i)([A-Za-z_]*(?:' + _SECRET_ENV_KEYWORDS + r')[A-Za-z_]*)='
    r'(?:"([^"]*)"|\'([^\']*)\'|(\S+))'
)

# Long base64 strings (40+ chars) that look like secrets.
# Must consist of base64 chars and optionally end with = padding.
_RE_BASE64_LONG = re.compile(
    r'(?<![A-Za-z0-9+/])'        # not preceded by base64 content chars
    r'[A-Za-z0-9+/]{40,}={0,3}'  # 40+ base64 chars with optional padding
    r'(?![A-Za-z0-9+/=])'        # not followed by base64 chars
)

# Ordered list of (pattern, replacement_fn_or_string) pairs.
_SECRET_PATTERNS = [
    (_RE_PRIVATE_KEY, '[REDACTED]'),
    (_RE_BEARER, 'Bearer [REDACTED]'),
    (_RE_AWS_KEY, '[REDACTED]'),
    (_RE_GHP_KEY, '[REDACTED]'),
    (_RE_SK_KEY, '[REDACTED]'),
]

# Query parameter names that look like secrets (case insensitive match).
_SECRET_PARAM_NAMES = re.compile(
    r'(?i)^(api_key|token|secret|password|passwd|auth|access_token|'
    r'private_key|client_secret|authorization|bearer|credential)$'
)


def redact_secrets(text: str) -> str:
    """Redact known secret patterns from *text* and return the sanitized version.

    Replaces API keys, tokens, passwords in env-var assignments, Bearer tokens,
    private key markers, and suspiciously long base64 strings with ``[REDACTED]``.
    """
    if not text:
        return text

    result = text

    # 1. Apply fixed-pattern replacements
    for pattern, replacement in _SECRET_PATTERNS:
        result = pattern.sub(replacement, result)

    # 2. Redact env-var assignments with secret-like names.
    #    We replace only the *value* portion, keeping the key name for context.
    def _env_replacer(m: re.Match) -> str:
        key_name = m.group(1)
        return f'{key_name}=[REDACTED]'

    result = _RE_ENV_SECRET.sub(_env_replacer, result)

    # 3. Redact long base64 strings (after other patterns, to avoid double-hits)
    result = _RE_BASE64_LONG.sub('[REDACTED]', result)

    return result


def _sanitize_url(url: str) -> str:
    """Redact secret-looking query parameters from a URL."""
    try:
        parsed = urlparse(url)
    except Exception:
        # If URL parsing fails, fall back to generic secret redaction.
        return redact_secrets(url)

    if not parsed.query:
        # No query string -- nothing to redact in params, but still
        # run generic redaction on the whole URL (e.g., embedded tokens).
        return redact_secrets(url)

    params = parse_qs(parsed.query, keep_blank_values=True)
    sanitized_params: dict[str, list[str]] = {}

    for key, values in params.items():
        if _SECRET_PARAM_NAMES.match(key):
            sanitized_params[key] = ['[REDACTED]']
        else:
            sanitized_params[key] = values

    # Rebuild query string manually to avoid URL-encoding [REDACTED].
    parts = []
    for key, values in sanitized_params.items():
        for val in values:
            parts.append(f'{key}={val}')
    new_query = '&'.join(parts)

    # Redact secrets in the non-query parts of the URL (path, netloc) to
    # catch e.g. AWS keys or tokens embedded in the path.  We must NOT
    # run the generic env-var redactor on the full URL because its \S+
    # pattern would greedily consume &-separated query parameters.
    sanitized_base = redact_secrets(
        urlunparse(parsed._replace(query=''))
    )
    parsed_base = urlparse(sanitized_base)

    sanitized_url = urlunparse(parsed_base._replace(query=new_query))
    return sanitized_url


def sanitize_target(target: str, tool_name: str) -> str:
    """Sanitize *target* for LLM classification based on *tool_name*.

    Parameters
    ----------
    target:
        The raw target string (bash command, file path, URL, etc.).
    tool_name:
        The name of the Claude Code tool (``Bash``, ``Write``, ``Edit``,
        ``WebFetch``, etc.).

    Returns
    -------
    str
        A sanitized version of the target that is safe to send to the LLM.
    """
    tool = tool_name.lower() if tool_name else ""

    if tool == "bash":
        return redact_secrets(target)

    if tool in ("write", "edit"):
        # Only return the path; never include file content.
        return f"[file: {target}]"

    if tool == "webfetch":
        return _sanitize_url(target)

    # Unknown / other tools: still apply generic secret redaction.
    return redact_secrets(target)
