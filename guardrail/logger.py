"""Audit logging for guardrail decisions.

Records all guardrail allow/deny/pass decisions to a JSON-lines log file
and manages pending marker files for deferred (Layer 2) decisions.
"""

import json
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

from guardrail.sanitizer import sanitize_target


def _now_iso() -> str:
    """Return the current UTC time in ISO 8601 format with microseconds."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")


def log_decision(
    tool_name: str,
    target: str,
    decision: str,
    reason: str,
    config: dict,
) -> None:
    """Append a JSON audit-log line for a guardrail decision.

    Parameters
    ----------
    tool_name:
        The Claude Code tool name (``Bash``, ``Write``, etc.).
    target:
        The raw target string (command, file path, URL).  Sanitized before
        being written to the log.
    decision:
        One of ``"allow"``, ``"deny"``, or ``"pass"``.
    reason:
        Human-readable explanation of why the decision was made.
    config:
        Configuration dict.  Uses ``config["log_file"]`` for the log path,
        defaulting to ``.claude/guardrail.log``.
    """
    try:
        log_file = Path(config.get("log_file", ".claude/guardrail.log"))
        log_file.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "timestamp": _now_iso(),
            "tool": tool_name,
            "target": sanitize_target(target, tool_name),
            "decision": decision,
            "reason": reason,
        }

        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        # Fail-open: never crash the guardrail because of a logging error.
        pass


def create_pending_marker(
    tool_name: str,
    target: str,
    config: dict,
) -> str:
    """Create a pending-decision marker file.

    Used by the PreToolUse hook when the Layer 1 decision is ``"pass"``
    (deferred to Layer 2).

    Parameters
    ----------
    tool_name:
        The Claude Code tool name.
    target:
        The raw target string.
    config:
        Configuration dict (unused beyond future extensibility).

    Returns
    -------
    str
        The absolute path to the newly created marker file.
    """
    pending_dir = Path(".claude/guardrail_pending")
    pending_dir.mkdir(parents=True, exist_ok=True)

    timestamp_us = int(time.time() * 1_000_000)
    random_hex = secrets.token_hex(2)  # 4 hex chars
    filename = f"{timestamp_us}_{random_hex}.json"
    marker_path = pending_dir / filename

    marker = {
        "tool_name": tool_name,
        "target": target,
        "created_at": _now_iso(),
    }

    with open(marker_path, "w") as f:
        json.dump(marker, f)

    return str(marker_path)


def resolve_pending_marker(
    marker_path: str,
    decision: str,
    reason: str,
    config: dict,
) -> None:
    """Resolve a pending marker by logging the decision and removing the file.

    Parameters
    ----------
    marker_path:
        Path to the marker file created by :func:`create_pending_marker`.
    decision:
        The final decision (``"allow"``, ``"deny"``, or ``"pass"``).
    reason:
        Human-readable explanation.
    config:
        Configuration dict (forwarded to :func:`log_decision`).
    """
    try:
        with open(marker_path) as f:
            marker = json.load(f)

        log_decision(
            tool_name=marker["tool_name"],
            target=marker["target"],
            decision=decision,
            reason=reason,
            config=config,
        )

        os.remove(marker_path)
    except Exception:
        # Silently handle errors (e.g. marker already deleted).
        pass
