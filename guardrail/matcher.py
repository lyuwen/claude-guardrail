import logging
import re
from typing import List


def _find_dollar_parens(cmd: str) -> List[str]:
    """Find all $(...) substitutions, handling nesting via paren depth."""
    results = []
    i = 0
    while i < len(cmd) - 1:
        if cmd[i] == '$' and cmd[i + 1] == '(':
            depth = 1
            start = i + 2
            j = start
            while j < len(cmd) and depth > 0:
                if cmd[j] == '(':
                    depth += 1
                elif cmd[j] == ')':
                    depth -= 1
                j += 1
            if depth == 0:
                inner = cmd[start:j - 1]
                results.append(inner)
                results.extend(_find_dollar_parens(inner))
            i = j
        else:
            i += 1
    return results


def _find_backticks(cmd: str) -> List[str]:
    """Find all `...` substitutions (no nesting)."""
    results = []
    for match in re.finditer(r'`([^`]+)`', cmd):
        inner = match.group(1)
        results.append(inner)
        results.extend(_find_dollar_parens(inner))
        results.extend(_find_backticks(inner))
    return results


def _find_process_substitutions(cmd: str) -> List[str]:
    """Find all <(...) and >(...) process substitutions, handling nesting."""
    results = []
    i = 0
    while i < len(cmd) - 1:
        if cmd[i] in ('<', '>') and cmd[i + 1] == '(':
            depth = 1
            start = i + 2
            j = start
            while j < len(cmd) and depth > 0:
                if cmd[j] == '(':
                    depth += 1
                elif cmd[j] == ')':
                    depth -= 1
                j += 1
            if depth == 0:
                inner = cmd[start:j - 1]
                results.append(inner)
                results.extend(_find_dollar_parens(inner))
                results.extend(_find_process_substitutions(inner))
            i = j
        else:
            i += 1
    return results


def _top_level_split(command: str, separators: List[str]) -> List[str]:
    """Split command on separators, but only at the top level.

    Characters inside $(...) or `...` substitutions are not considered
    for splitting.
    """
    # Build a mask of which characters are inside substitutions
    length = len(command)
    inside = [False] * length

    # Mark $(...) regions
    i = 0
    while i < length - 1:
        if command[i] == '$' and command[i + 1] == '(':
            depth = 1
            j = i + 2
            while j < length and depth > 0:
                if command[j] == '(':
                    depth += 1
                elif command[j] == ')':
                    depth -= 1
                j += 1
            if depth == 0:
                # Mark from $( to the closing ) as inside
                for k in range(i, j):
                    inside[k] = True
            i = j
        else:
            i += 1

    # Mark <(...) and >(...) process substitution regions
    i = 0
    while i < length - 1:
        if command[i] in ('<', '>') and command[i + 1] == '(':
            depth = 1
            j = i + 2
            while j < length and depth > 0:
                if command[j] == '(':
                    depth += 1
                elif command[j] == ')':
                    depth -= 1
                j += 1
            if depth == 0:
                for k in range(i, j):
                    inside[k] = True
            i = j
        else:
            i += 1

    # Mark backtick regions
    in_backtick = False
    bt_start = 0
    for i in range(length):
        if command[i] == '`':
            if not in_backtick:
                in_backtick = True
                bt_start = i
            else:
                for k in range(bt_start, i + 1):
                    inside[k] = True
                in_backtick = False

    # Mark single-quoted regions (no escape inside single quotes in bash)
    i = 0
    while i < length:
        if not inside[i] and command[i] == "'":
            j = i + 1
            while j < length and command[j] != "'":
                j += 1
            if j < length:
                # Found closing quote, mark entire region including quotes
                for k in range(i, j + 1):
                    inside[k] = True
                i = j + 1
            else:
                i += 1
        else:
            i += 1

    # Mark double-quoted regions (with backslash-escape for \")
    i = 0
    while i < length:
        if not inside[i] and command[i] == '"':
            j = i + 1
            while j < length:
                if command[j] == '\\' and j + 1 < length:
                    j += 2  # skip escaped character
                elif command[j] == '"':
                    break
                else:
                    j += 1
            if j < length:
                # Found closing quote, mark entire region including quotes
                for k in range(i, j + 1):
                    inside[k] = True
                i = j + 1
            else:
                i += 1
        else:
            i += 1

    # Now split on each separator at positions that are not inside substitutions
    # Process separators from longest to shortest to handle && and || before |
    sorted_seps = sorted(separators, key=len, reverse=True)

    # We'll collect split points as (start_of_sep, len_of_sep)
    split_points = []
    i = 0
    while i < length:
        if inside[i]:
            i += 1
            continue
        matched = False
        for sep in sorted_seps:
            slen = len(sep)
            if i + slen <= length and command[i:i + slen] == sep:
                # Verify none of the separator chars are inside a substitution
                if not any(inside[i + k] for k in range(slen)):
                    split_points.append((i, slen))
                    i += slen
                    matched = True
                    break
        if not matched:
            i += 1

    # Build segments from split points
    segments = []
    prev = 0
    for pos, slen in split_points:
        part = command[prev:pos].strip()
        if part:
            segments.append(part)
        prev = pos + slen
    # Last segment
    part = command[prev:].strip()
    if part:
        segments.append(part)

    return segments


def split_bash_command(command: str) -> List[str]:
    """Split a bash command into segments for rule checking.

    Returns the original command, any command substitution contents
    (recursively), and top-level operator-split parts. Splitting on
    ;, &&, ||, | only happens at the top level -- not inside $(...) or
    backtick substitutions.
    """
    segments = [command]

    # Extract command substitutions recursively (call once and reuse)
    dollar_subs = _find_dollar_parens(command)
    backtick_subs = _find_backticks(command)
    process_subs = _find_process_substitutions(command)
    subs = dollar_subs + backtick_subs + process_subs

    segments.extend(subs)

    # Top-level operator splitting on the original command
    for sep in [';', '&&', '||', '|', '\n']:
        parts = _top_level_split(command, [sep])
        segments.extend(p for p in parts if p)

    # Also do top-level operator splitting on each extracted substitution
    for sub in subs:
        for sep in [';', '&&', '||', '|', '\n']:
            parts = _top_level_split(sub, [sep])
            segments.extend(p for p in parts if p)

    return list(dict.fromkeys(segments))


def matches_deny_rule(target: str, pattern: str) -> bool:
    """Check if target matches a deny pattern using re.search."""
    try:
        return bool(re.search(pattern, target))
    except re.error:
        logging.getLogger(__name__).warning(f"Invalid deny pattern: {pattern}")
        return True  # Fail closed for deny rules


def matches_allow_rule(target: str, pattern: str) -> bool:
    """Check if target matches an allow pattern using re.search."""
    try:
        return bool(re.search(pattern, target))
    except re.error:
        return False


def check_bash_deny_any_segment(command: str, deny_patterns: List[str]) -> bool:
    """Check if any segment of a bash command matches any deny pattern.

    Splits the command into segments (handling substitutions and operators)
    and returns True if any segment matches any deny pattern.
    """
    segments = split_bash_command(command)
    for segment in segments:
        for pattern in deny_patterns:
            if matches_deny_rule(segment, pattern):
                return True
    return False
