"""Decision engine for the guardrail system.

Evaluates tool invocations against deny/allow/ask rules and returns a decision:
  - "allow"  -- auto-allowed by rules, no user prompt needed
  - "deny"   -- blocked by a deny rule
  - "ask"    -- matched an ask rule, prompt user for session approval
  - "pass"   -- no rule matched, defer to Layer 2 (LLM prompt hook)

The evaluation order is **deny-before-allow**: a deny match always wins,
even if an allow rule also matches.
"""

import logging
import re
from typing import Any, Dict, List
from urllib.parse import urlparse

from guardrail.matcher import (
    check_bash_deny_any_segment,
    matches_allow_rule,
    matches_deny_rule,
    split_bash_command,
)
from guardrail.python_analyzer import is_safe_python_script

logger = logging.getLogger(__name__)

# Maps tool names to the key used to extract the target from tool_input.
_TOOL_INPUT_KEY = {
    "Bash": "command",
    "Write": "file_path",
    "Edit": "file_path",
    "WebFetch": "url",
}

# Maps tool names to the rule category used for deny/allow rules.
_TOOL_RULE_CATEGORY = {
    "Bash": "bash",
    "Write": "file_path",
    "Edit": "file_path",
    "WebFetch": "hostname",
}


def _extract_hostname(url: str) -> str | None:
    """Extract the hostname from a URL.  Returns None on failure."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if hostname:
            return hostname
    except Exception:
        pass
    return None


def _check_deny(target: str, deny_patterns: List[str]) -> bool:
    """Return True if target matches any deny pattern."""
    for pattern in deny_patterns:
        if matches_deny_rule(target, pattern):
            return True
    return False


def _check_allow(target: str, allow_patterns: List[str]) -> bool:
    """Return True if target matches any allow pattern."""
    for pattern in allow_patterns:
        if matches_allow_rule(target, pattern):
            return True
    return False


def _check_ask(target: str, ask_patterns: List[str]) -> bool:
    """Return True if target matches any ask pattern."""
    for pattern in ask_patterns:
        if matches_allow_rule(target, pattern):
            return True
    return False


def evaluate_action(
    tool_name: str,
    tool_input: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, str]:
    """Evaluate a tool invocation against the guardrail rules.

    Parameters
    ----------
    tool_name : str
        Name of the tool being invoked (e.g. "Bash", "Write").
    tool_input : dict
        The tool's input parameters (e.g. {"command": "git status"}).
    config : dict
        The merged guardrail configuration containing ``guarded_tools``,
        ``deny_rules``, and ``allow_rules``.

    Returns
    -------
    dict
        ``{"decision": "allow"|"deny"|"ask"|"pass", "reason": str}``
    """
    # ------------------------------------------------------------------
    # Step 1: Tool not in guarded_tools list? --> allow
    # ------------------------------------------------------------------
    guarded_tools: List[str] = config.get("guarded_tools", [])
    if tool_name not in guarded_tools:
        return {"decision": "allow", "reason": "unguarded tool"}

    # ------------------------------------------------------------------
    # Step 2: Extract target from tool_input
    # ------------------------------------------------------------------
    input_key = _TOOL_INPUT_KEY.get(tool_name)
    if input_key is None:
        # Tool is guarded but we don't know how to extract a target --
        # fail open so Layer 2 can handle it.
        return {"decision": "pass", "reason": f"no extraction rule for tool {tool_name}"}

    raw_target = tool_input.get(input_key)
    if raw_target is None:
        return {"decision": "pass", "reason": f"missing '{input_key}' in tool_input"}

    # For WebFetch, we match against the hostname, not the full URL.
    rule_category = _TOOL_RULE_CATEGORY[tool_name]
    if rule_category == "hostname":
        target = _extract_hostname(raw_target)
        if target is None:
            return {"decision": "pass", "reason": "could not parse hostname from URL"}
    else:
        target = raw_target

    # Retrieve rule lists, defaulting to empty.
    deny_rules: Dict[str, List[str]] = config.get("deny_rules", {})
    allow_rules: Dict[str, List[str]] = config.get("allow_rules", {})
    ask_rules: Dict[str, List[str]] = config.get("ask_rules", {})
    deny_patterns: List[str] = deny_rules.get(rule_category, [])
    allow_patterns: List[str] = allow_rules.get(rule_category, [])
    ask_patterns: List[str] = ask_rules.get(rule_category, [])

    # ------------------------------------------------------------------
    # Step 3 & 4: Check deny rules (deny-before-allow)
    # ------------------------------------------------------------------
    if rule_category == "bash":
        # For Bash: use split + check_bash_deny_any_segment
        if check_bash_deny_any_segment(target, deny_patterns):
            return {"decision": "deny", "reason": f"bash command matched deny rule"}
    else:
        # For file_path / hostname: simple deny check
        if _check_deny(target, deny_patterns):
            return {
                "decision": "deny",
                "reason": f"{rule_category} matched deny rule",
            }

    # ------------------------------------------------------------------
    # Step 5: Check allow rules
    # ------------------------------------------------------------------
    if rule_category == "bash":
        # For Bash, check each segment against allow rules.
        # The *full command* and each top-level segment must be considered.
        segments = split_bash_command(target)
        for segment in segments:
            if _check_allow(segment, allow_patterns):
                return {"decision": "allow", "reason": "bash command matched allow rule"}
    else:
        if _check_allow(target, allow_patterns):
            return {
                "decision": "allow",
                "reason": f"{rule_category} matched allow rule",
            }

    # ------------------------------------------------------------------
    # Step 6: Language safety check (before ask rules)
    # ------------------------------------------------------------------
    if rule_category == "bash":
        # Python script execution: check if it's safe read-only
        python_match = re.match(r'^(python[0-9.]*)\s+(.+)$', target.strip())
        if python_match:
            script_path = python_match.group(2).split()[0]

            # Extract working directory from cd commands in the full command
            working_dir: str | None = None
            cd_match = re.search(r'\bcd\s+([^\s;&|]+)', target)
            if cd_match:
                working_dir = cd_match.group(1)

            if is_safe_python_script(script_path, working_dir):
                return {"decision": "allow", "reason": "safe read-only python script"}

    # ------------------------------------------------------------------
    # Step 7: Check ask rules
    # ------------------------------------------------------------------
    if rule_category == "bash":
        segments = split_bash_command(target)
        for segment in segments:
            if _check_ask(segment, ask_patterns):
                return {"decision": "ask", "reason": "bash command matched ask rule"}
    else:
        if _check_ask(target, ask_patterns):
            return {
                "decision": "ask",
                "reason": f"{rule_category} matched ask rule",
            }

    # ------------------------------------------------------------------
    # Step 8: No match --> pass (defer to Layer 2)
    # ------------------------------------------------------------------
    return {"decision": "pass", "reason": "no matching rule, deferred to Layer 2"}
