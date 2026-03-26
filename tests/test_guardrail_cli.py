"""Tests for guardrail.cli -- the CLI entry point for Claude Code hooks."""

import json
from unittest.mock import patch

import pytest

from guardrail.cli import main


def _run_cli(stdin_text: str, args: list[str] | None = None) -> tuple[str, int]:
    """Run the CLI main() with given stdin and return (stdout, exit_code)."""
    argv = ["guardrail"]
    if args:
        argv.extend(args)

    exit_code = 0
    captured_output = ""

    with patch("sys.stdin") as mock_stdin, \
         patch("sys.stdout") as mock_stdout, \
         patch("sys.argv", argv):

        mock_stdin.read.return_value = stdin_text

        # Capture print output
        written_parts = []
        mock_stdout.write = lambda s: written_parts.append(s)
        mock_stdout.flush = lambda: None

        # Capture sys.exit calls
        with pytest.raises(SystemExit) as exc_info:
            main()

        exit_code = exc_info.value.code if exc_info.value.code is not None else 0
        captured_output = "".join(written_parts)

    return captured_output, exit_code


def _make_payload(hook_type: str = "PreToolUse", tool_name: str = "Bash",
                  tool_input: dict | None = None) -> str:
    """Build a JSON hook payload string."""
    return json.dumps({
        "hook_type": hook_type,
        "tool_name": tool_name,
        "tool_input": tool_input or {},
    })


# ---------------------------------------------------------------------------
# Helper config for mocking
# ---------------------------------------------------------------------------
_BASIC_CONFIG = {
    "guarded_tools": ["Bash", "Write", "Edit", "WebFetch"],
    "deny_rules": {
        "bash": [r"rm\s+-rf\s+/"],
        "file_path": [r"(^|/)\.env"],
        "hostname": [r".*"],
    },
    "allow_rules": {
        "bash": [r"^git\s"],
        "file_path": [r".*"],
        "hostname": [],
    },
    "ask_rules": {
        "bash": [r"^python[0-9.]*\s"],
        "file_path": [],
        "hostname": [],
    },
}


# ---------------------------------------------------------------------------
# 1. Valid deny input -> outputs deny JSON
# ---------------------------------------------------------------------------
class TestDenyOutput:
    def test_deny_returns_json(self):
        payload = _make_payload(tool_name="Bash",
                                tool_input={"command": "rm -rf /"})
        with patch("guardrail.cli.load_config", return_value=_BASIC_CONFIG):
            output, code = _run_cli(payload)

        assert code == 0
        result = json.loads(output)
        hso = result["hookSpecificOutput"]
        assert hso["permissionDecision"] == "deny"
        assert "permissionDecisionReason" in hso

    def test_deny_file_path(self):
        payload = _make_payload(tool_name="Write",
                                tool_input={"file_path": "/project/.env"})
        with patch("guardrail.cli.load_config", return_value=_BASIC_CONFIG):
            output, code = _run_cli(payload)

        assert code == 0
        result = json.loads(output)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


# ---------------------------------------------------------------------------
# 2. Valid allow input -> outputs allow JSON
# ---------------------------------------------------------------------------
class TestAllowOutput:
    def test_allow_returns_json(self):
        payload = _make_payload(tool_name="Bash",
                                tool_input={"command": "git status"})
        with patch("guardrail.cli.load_config", return_value=_BASIC_CONFIG):
            output, code = _run_cli(payload)

        assert code == 0
        result = json.loads(output)
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_allow_unguarded_tool(self):
        payload = _make_payload(tool_name="Read",
                                tool_input={"file_path": "/etc/passwd"})
        with patch("guardrail.cli.load_config", return_value=_BASIC_CONFIG):
            output, code = _run_cli(payload)

        assert code == 0
        result = json.loads(output)
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"


# ---------------------------------------------------------------------------
# 3. Valid pass input -> outputs nothing (empty stdout)
# ---------------------------------------------------------------------------
class TestPassOutput:
    def test_pass_returns_empty(self):
        # A Bash command that matches neither deny nor allow rules
        payload = _make_payload(tool_name="Bash",
                                tool_input={"command": "some-unknown-cmd foo"})
        with patch("guardrail.cli.load_config", return_value=_BASIC_CONFIG), \
             patch("guardrail.cli.create_pending_marker"):
            output, code = _run_cli(payload)

        assert code == 0
        assert output.strip() == ""


# ---------------------------------------------------------------------------
# 4. Malformed stdin JSON -> exits 0, no output (fail-open)
# ---------------------------------------------------------------------------
class TestMalformedStdin:
    def test_invalid_json(self):
        output, code = _run_cli("{not valid json!!!")
        assert code == 0
        assert output.strip() == ""

    def test_empty_stdin(self):
        output, code = _run_cli("")
        assert code == 0
        assert output.strip() == ""

    def test_whitespace_only_stdin(self):
        output, code = _run_cli("   \n  ")
        assert code == 0
        assert output.strip() == ""


# ---------------------------------------------------------------------------
# 5. Missing config -> exits 0, no output (fail-open)
# ---------------------------------------------------------------------------
class TestMissingConfig:
    def test_config_load_fails(self):
        payload = _make_payload(tool_name="Bash",
                                tool_input={"command": "git status"})
        with patch("guardrail.cli.load_config",
                    side_effect=FileNotFoundError("defaults.yml not found")):
            output, code = _run_cli(payload)

        assert code == 0
        assert output.strip() == ""

    def test_config_load_value_error(self):
        payload = _make_payload(tool_name="Bash",
                                tool_input={"command": "git status"})
        with patch("guardrail.cli.load_config",
                    side_effect=ValueError("Invalid YAML")):
            output, code = _run_cli(payload)

        assert code == 0
        assert output.strip() == ""


# ---------------------------------------------------------------------------
# 6. --check mode with valid config -> exits 0
# ---------------------------------------------------------------------------
class TestCheckModeValid:
    def test_check_valid_config(self):
        with patch("guardrail.cli.load_config", return_value=_BASIC_CONFIG):
            output, code = _run_cli("", args=["--check"])

        assert code == 0

    def test_check_does_not_read_stdin(self):
        """--check should not try to process stdin."""
        with patch("guardrail.cli.load_config", return_value=_BASIC_CONFIG):
            output, code = _run_cli("garbage input", args=["--check"])

        assert code == 0


# ---------------------------------------------------------------------------
# 7. --check mode with invalid config -> exits 1
# ---------------------------------------------------------------------------
class TestCheckModeInvalid:
    def test_check_missing_config(self):
        with patch("guardrail.cli.load_config",
                    side_effect=FileNotFoundError("not found")):
            output, code = _run_cli("", args=["--check"])

        assert code == 1

    def test_check_bad_yaml(self):
        with patch("guardrail.cli.load_config",
                    side_effect=ValueError("bad yaml")):
            output, code = _run_cli("", args=["--check"])

        assert code == 1


# ---------------------------------------------------------------------------
# 8. Non-PreToolUse hook_type -> exits 0, no output
# ---------------------------------------------------------------------------
class TestNonPreToolUseHook:
    def test_notification_ignored(self):
        payload = _make_payload(hook_type="Notification", tool_name="Bash",
                                tool_input={"command": "rm -rf /"})
        output, code = _run_cli(payload)
        assert code == 0
        assert output.strip() == ""

    def test_empty_hook_type(self):
        payload = json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"},
        })
        output, code = _run_cli(payload)
        assert code == 0
        assert output.strip() == ""


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------
class TestEdgeCases:
    def test_evaluate_action_exception_is_failopen(self):
        """If evaluate_action itself throws, we fail open."""
        payload = _make_payload(tool_name="Bash",
                                tool_input={"command": "git status"})
        with patch("guardrail.cli.load_config", return_value=_BASIC_CONFIG), \
             patch("guardrail.cli.evaluate_action",
                   side_effect=RuntimeError("unexpected bug")):
            output, code = _run_cli(payload)

        assert code == 0
        assert output.strip() == ""

    def test_payload_missing_tool_input(self):
        """Payload with no tool_input key should still work (engine handles it)."""
        payload = json.dumps({
            "hook_type": "PreToolUse",
            "tool_name": "Bash",
        })
        with patch("guardrail.cli.load_config", return_value=_BASIC_CONFIG), \
             patch("guardrail.cli.create_pending_marker"):
            output, code = _run_cli(payload)

        # Engine returns "pass" when tool_input is missing the expected key
        assert code == 0


# ---------------------------------------------------------------------------
# 9. PreToolUse "pass" creates a pending marker
# ---------------------------------------------------------------------------
class TestPreToolUseCreatesMarker:
    def test_pass_creates_pending_marker(self):
        """When the engine returns 'pass', the CLI should create a pending marker."""
        payload = _make_payload(tool_name="Bash",
                                tool_input={"command": "some-unknown-cmd foo"})
        with patch("guardrail.cli.load_config", return_value=_BASIC_CONFIG), \
             patch("guardrail.cli.create_pending_marker") as mock_create:
            output, code = _run_cli(payload)

        assert code == 0
        assert output.strip() == ""
        mock_create.assert_called_once_with(
            "Bash", "some-unknown-cmd foo", _BASIC_CONFIG
        )

    def test_pass_creates_marker_with_file_path(self):
        """Pass on a Write tool creates a marker with the file_path target."""
        # Use a config where Write produces "pass" (no matching allow/deny)
        config = {
            "guarded_tools": ["Write"],
            "deny_rules": {"file_path": []},
            "allow_rules": {"file_path": []},
        }
        payload = _make_payload(tool_name="Write",
                                tool_input={"file_path": "/tmp/test.txt"})
        with patch("guardrail.cli.load_config", return_value=config), \
             patch("guardrail.cli.create_pending_marker") as mock_create:
            output, code = _run_cli(payload)

        assert code == 0
        mock_create.assert_called_once_with(
            "Write", "/tmp/test.txt", config
        )

    def test_allow_does_not_create_marker(self):
        """When the engine returns 'allow', no pending marker is created."""
        payload = _make_payload(tool_name="Bash",
                                tool_input={"command": "git status"})
        with patch("guardrail.cli.load_config", return_value=_BASIC_CONFIG), \
             patch("guardrail.cli.create_pending_marker") as mock_create:
            output, code = _run_cli(payload)

        assert code == 0
        mock_create.assert_not_called()

    def test_deny_does_not_create_marker(self):
        """When the engine returns 'deny', no pending marker is created."""
        payload = _make_payload(tool_name="Bash",
                                tool_input={"command": "rm -rf /"})
        with patch("guardrail.cli.load_config", return_value=_BASIC_CONFIG), \
             patch("guardrail.cli.create_pending_marker") as mock_create:
            output, code = _run_cli(payload)

        assert code == 0
        mock_create.assert_not_called()


# ---------------------------------------------------------------------------
# 10. PostToolUse resolves pending markers
# ---------------------------------------------------------------------------
class TestPostToolUseResolvesMarker:
    def test_resolves_pending_marker(self):
        """PostToolUse should find and resolve the pending marker."""
        payload = _make_payload(hook_type="PostToolUse", tool_name="Bash",
                                tool_input={"command": "some-cmd"})
        marker_path = ".claude/guardrail_pending/1234_abcd.json"
        with patch("guardrail.cli._find_pending_marker",
                   return_value=marker_path), \
             patch("guardrail.cli.load_config",
                   return_value=_BASIC_CONFIG), \
             patch("guardrail.cli.resolve_pending_marker") as mock_resolve:
            output, code = _run_cli(payload)

        assert code == 0
        assert output.strip() == ""
        mock_resolve.assert_called_once_with(
            marker_path,
            decision="allow",
            reason="tool execution completed (Layer 2 allowed)",
            config=_BASIC_CONFIG,
        )

    def test_no_pending_marker_does_nothing(self):
        """PostToolUse with no matching marker should do nothing."""
        payload = _make_payload(hook_type="PostToolUse", tool_name="Bash",
                                tool_input={"command": "some-cmd"})
        with patch("guardrail.cli._find_pending_marker",
                   return_value=None), \
             patch("guardrail.cli.resolve_pending_marker") as mock_resolve:
            output, code = _run_cli(payload)

        assert code == 0
        assert output.strip() == ""
        mock_resolve.assert_not_called()

    def test_missing_pending_directory_silent(self):
        """PostToolUse handles missing pending directory silently."""
        payload = _make_payload(hook_type="PostToolUse", tool_name="Bash",
                                tool_input={"command": "some-cmd"})
        # _find_pending_marker returns None when directory doesn't exist
        with patch("guardrail.cli._find_pending_marker",
                   return_value=None), \
             patch("guardrail.cli.resolve_pending_marker") as mock_resolve:
            output, code = _run_cli(payload)

        assert code == 0
        assert output.strip() == ""
        mock_resolve.assert_not_called()

    def test_post_tool_use_produces_no_output(self):
        """PostToolUse should never produce stdout output, even with a marker."""
        payload = _make_payload(hook_type="PostToolUse", tool_name="Write",
                                tool_input={"file_path": "/tmp/test.txt"})
        with patch("guardrail.cli._find_pending_marker",
                   return_value=".claude/guardrail_pending/999_ff.json"), \
             patch("guardrail.cli.load_config",
                   return_value=_BASIC_CONFIG), \
             patch("guardrail.cli.resolve_pending_marker"):
            output, code = _run_cli(payload)

        assert code == 0
        assert output.strip() == ""


# ---------------------------------------------------------------------------
# 11. _find_pending_marker unit tests
# ---------------------------------------------------------------------------
class TestFindPendingMarker:
    def test_finds_most_recent_marker(self, tmp_path, monkeypatch):
        """Should return the most recent marker matching the tool_name."""
        monkeypatch.chdir(tmp_path)
        pending_dir = tmp_path / ".claude" / "guardrail_pending"
        pending_dir.mkdir(parents=True)

        # Older marker
        (pending_dir / "1000000_aaaa.json").write_text(
            json.dumps({"tool_name": "Bash", "target": "old-cmd",
                         "created_at": "2024-01-01T00:00:00"})
        )
        # Newer marker
        (pending_dir / "2000000_bbbb.json").write_text(
            json.dumps({"tool_name": "Bash", "target": "new-cmd",
                         "created_at": "2024-01-02T00:00:00"})
        )

        from guardrail.cli import _find_pending_marker
        result = _find_pending_marker("Bash")
        assert result is not None
        assert "2000000_bbbb.json" in result

    def test_ignores_different_tool(self, tmp_path, monkeypatch):
        """Should not return markers for a different tool_name."""
        monkeypatch.chdir(tmp_path)
        pending_dir = tmp_path / ".claude" / "guardrail_pending"
        pending_dir.mkdir(parents=True)

        (pending_dir / "1000000_aaaa.json").write_text(
            json.dumps({"tool_name": "Write", "target": "/tmp/x.txt",
                         "created_at": "2024-01-01T00:00:00"})
        )

        from guardrail.cli import _find_pending_marker
        result = _find_pending_marker("Bash")
        assert result is None

    def test_missing_directory_returns_none(self, tmp_path, monkeypatch):
        """Should return None when the pending directory doesn't exist."""
        monkeypatch.chdir(tmp_path)

        from guardrail.cli import _find_pending_marker
        result = _find_pending_marker("Bash")
        assert result is None

    def test_corrupt_marker_skipped(self, tmp_path, monkeypatch):
        """Should skip corrupt marker files and continue searching."""
        monkeypatch.chdir(tmp_path)
        pending_dir = tmp_path / ".claude" / "guardrail_pending"
        pending_dir.mkdir(parents=True)

        # Corrupt file (newer timestamp)
        (pending_dir / "3000000_cccc.json").write_text("not valid json!!!")
        # Valid file (older timestamp)
        (pending_dir / "1000000_aaaa.json").write_text(
            json.dumps({"tool_name": "Bash", "target": "cmd",
                         "created_at": "2024-01-01T00:00:00"})
        )

        from guardrail.cli import _find_pending_marker
        result = _find_pending_marker("Bash")
        assert result is not None
        assert "1000000_aaaa.json" in result


# ---------------------------------------------------------------------------
# 12. Ask decision output
# ---------------------------------------------------------------------------
class TestAskOutput:
    def test_ask_returns_json(self):
        payload = _make_payload(tool_name="Bash",
                                tool_input={"command": "python3 script.py"})
        with patch("guardrail.cli.load_config", return_value=_BASIC_CONFIG):
            output, code = _run_cli(payload)

        assert code == 0
        result = json.loads(output)
        hso = result["hookSpecificOutput"]
        assert hso["permissionDecision"] == "ask"
        assert "permissionDecisionReason" in hso

    def test_ask_does_not_create_marker(self):
        """When the engine returns 'ask', no pending marker is created."""
        payload = _make_payload(tool_name="Bash",
                                tool_input={"command": "python3 script.py"})
        with patch("guardrail.cli.load_config", return_value=_BASIC_CONFIG), \
             patch("guardrail.cli.create_pending_marker") as mock_create:
            output, code = _run_cli(payload)

        assert code == 0
        mock_create.assert_not_called()


# ---------------------------------------------------------------------------
# 13. Bypass-permissions mode
# ---------------------------------------------------------------------------
class TestBypassPermissionsMode:
    def test_bypass_mode_exits_silently(self):
        """In bypass mode, no output and no decision."""
        payload = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"},
            "permission_mode": "bypass",
        })
        output, code = _run_cli(payload)

        assert code == 0
        assert output.strip() == ""

    def test_bypass_permissions_mode_exits_silently(self):
        """bypassPermissions variant also skips."""
        payload = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"},
            "permission_mode": "bypassPermissions",
        })
        output, code = _run_cli(payload)

        assert code == 0
        assert output.strip() == ""

    def test_non_bypass_mode_still_evaluates(self):
        """Normal mode should still evaluate rules."""
        payload = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"},
            "permission_mode": "default",
        })
        with patch("guardrail.cli.load_config", return_value=_BASIC_CONFIG):
            output, code = _run_cli(payload)

        assert code == 0
        result = json.loads(output)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


# ---------------------------------------------------------------------------
# 14. Hook-triggered actions
# ---------------------------------------------------------------------------
class TestHookTriggeredActions:
    def test_guardrail_hook_command_exits_silently(self):
        """The guardrail hook command itself should be auto-allowed."""
        payload = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "python -m guardrail.cli"},
        })
        output, code = _run_cli(payload)

        assert code == 0
        assert output.strip() == ""

    def test_guardrail_hook_command_python3_exits_silently(self):
        """The guardrail hook command with python3 should be auto-allowed."""
        payload = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "echo test | python3 -m guardrail.cli"},
        })
        output, code = _run_cli(payload)

        assert code == 0
        assert output.strip() == ""

    def test_other_python_commands_still_evaluated(self):
        """Other python commands should still be evaluated."""
        payload = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "python3 script.py"},
        })
        with patch("guardrail.cli.load_config", return_value=_BASIC_CONFIG):
            output, code = _run_cli(payload)

        assert code == 0
        result = json.loads(output)
        assert result["hookSpecificOutput"]["permissionDecision"] == "ask"
