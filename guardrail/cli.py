"""CLI entry point for the guardrail hook.

Called by Claude Code hooks via stdin/stdout JSON protocol.

Input (stdin):
    {"hook_type": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git status"}}

Output (stdout):
    {"decision": "allow"}              -- auto-approve
    {"decision": "deny", "reason": "..."} -- block with reason
    (empty)                             -- pass / defer to next hook

All errors are fail-open: if anything goes wrong, exit 0 silently so the
user is never blocked by guardrail bugs.
"""

import json
import sys
from pathlib import Path

from guardrail.config import load_config
from guardrail.engine import evaluate_action
from guardrail.logger import create_pending_marker, resolve_pending_marker, log_decision
from guardrail.llm import evaluate_with_llm
from guardrail.sanitizer import sanitize_target


# Maps tool names to the key used to extract the target from tool_input.
_TOOL_INPUT_KEY = {
    "Bash": "command",
    "Write": "file_path",
    "Edit": "file_path",
    "WebFetch": "url",
}


def _extract_target(tool_name: str, tool_input: dict) -> str:
    """Extract a human-readable target string from tool_input."""
    key = _TOOL_INPUT_KEY.get(tool_name)
    if key and key in tool_input:
        return tool_input[key]
    return json.dumps(tool_input, sort_keys=True)


def _find_pending_marker(tool_name: str) -> str | None:
    """Find the most recent pending marker for a given tool_name.

    Looks in ``.claude/guardrail_pending/`` for JSON marker files whose
    ``tool_name`` field matches *tool_name*.  Returns the path of the most
    recent match (by filename timestamp), or ``None`` if none is found.
    """
    pending_dir = Path(".claude/guardrail_pending")
    if not pending_dir.is_dir():
        return None

    # Marker filenames are "{timestamp_us}_{hex}.json" -- sorting in
    # reverse gives most-recent first.
    marker_files = sorted(pending_dir.glob("*.json"), reverse=True)

    for marker_path in marker_files:
        try:
            with open(marker_path) as f:
                marker = json.load(f)
            if marker.get("tool_name") == tool_name:
                return str(marker_path)
        except Exception:
            continue

    return None


def main() -> None:
    """Entry point for the guardrail CLI hook."""
    try:
        # --check mode: verify config loads successfully
        if "--check" in sys.argv:
            try:
                load_config()
                sys.exit(0)
            except Exception:
                sys.exit(1)

        # Read hook payload from stdin
        try:
            raw = sys.stdin.read()
            if not raw.strip():
                sys.exit(0)
            payload = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            sys.exit(0)

        hook_type = payload.get("hook_event_name", "") or payload.get("hook_type", "")
        tool_name = payload.get("tool_name", "")
        tool_input = payload.get("tool_input", {})

        # Skip hook entirely in bypass-permissions mode
        permission_mode = payload.get("permission_mode", "")
        if permission_mode in ("bypass", "bypassPermissions"):
            sys.exit(0)

        # Auto-allow the guardrail hook command itself
        if tool_name == "Bash":
            command = tool_input.get("command", "")
            if "python -m guardrail.cli" in command or "python3 -m guardrail.cli" in command:
                sys.exit(0)

        if hook_type == "PreToolUse":
            # Load config (fail-open on any error)
            config = load_config()

            # Evaluate the action
            result = evaluate_action(tool_name, tool_input, config)
            decision = result.get("decision", "pass")
            reason = result.get("reason", "")
            target = _extract_target(tool_name, tool_input)

            if decision == "allow":
                log_decision(tool_name, target, "allow", reason, config)
                print(json.dumps({
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "allow",
                        "permissionDecisionReason": reason or "matched guardrail allow rule",
                    }
                }))
            elif decision == "deny":
                reason = reason or "matched deny rule"
                log_decision(tool_name, target, "deny", reason, config)
                print(json.dumps({
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": reason,
                    }
                }))
            elif decision == "ask":
                reason = reason or "matched ask rule"
                log_decision(tool_name, target, "ask", reason, config)
                print(json.dumps({
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "ask",
                        "permissionDecisionReason": reason,
                    }
                }))
            else:
                # "pass" -> try Layer 2 LLM classification
                sanitized = sanitize_target(target, tool_name)
                context = payload.get("context", "")
                user_request = payload.get("user_request", "")

                llm_result = evaluate_with_llm(
                    tool_name, sanitized, context, user_request, config
                )
                llm_decision = llm_result.get("decision", "pass")
                llm_reason = llm_result.get("reason", "")

                if llm_decision == "allow":
                    log_decision(tool_name, target, "allow", llm_reason, config)
                    print(json.dumps({
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "allow",
                            "permissionDecisionReason": llm_reason,
                        }
                    }))
                elif llm_decision == "deny":
                    log_decision(tool_name, target, "deny", llm_reason, config)
                    print(json.dumps({
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "deny",
                            "permissionDecisionReason": llm_reason,
                        }
                    }))
                elif llm_decision == "ask":
                    log_decision(tool_name, target, "ask", llm_reason, config)
                    print(json.dumps({
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "ask",
                            "permissionDecisionReason": llm_reason,
                        }
                    }))
                else:
                    # Layer 2 not configured or passed -> create pending marker
                    log_decision(tool_name, target, "pass", llm_reason, config)
                    create_pending_marker(tool_name, target, config)

        elif hook_type == "PostToolUse":
            # Find and resolve the most recent pending marker for this tool.
            # PostToolUse fires after the tool executed, meaning Layer 2
            # (or the user) allowed it.
            marker_path = _find_pending_marker(tool_name)
            if marker_path:
                config = load_config()
                resolve_pending_marker(
                    marker_path,
                    decision="allow",
                    reason="tool execution completed (Layer 2 allowed)",
                    config=config,
                )
            # PostToolUse produces no output

    except Exception:
        # Fail-open: never block the user due to our own bugs
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
