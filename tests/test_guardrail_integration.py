"""End-to-end integration tests for the guardrail system.

Tests the full pipeline from CLI stdin to stdout without mocking internal
modules.  Only configuration file paths are controlled via test fixtures.

Run with:
    python -m pytest tests/test_guardrail_integration.py -v
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from guardrail.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _defaults_config() -> dict:
    """Return a config dict that mirrors the real defaults.yml."""
    return {
        "guarded_tools": ["Bash", "Write", "Edit", "WebFetch"],
        "deny_rules": {
            "bash": [
                r"(^|.*/)rm\s+-rf\s+/",
                r":\(\)\{.*:\|:&\};",
                r"(^|.*/)dd\s+if=/dev/(zero|random)\s+of=",
                r"(^|.*/)mkfs\.",
                r">(\s*/dev/sd|/dev/nvme)",
                r"\beval\b",
                r"\bexec\b",
                r"\bbase64\s.*\|.*\b(bash|sh|zsh)\b",
                r"\bxargs\s.*(rm|dd|mkfs)",
            ],
            "file_path": [
                r"(^|/)\.env",
                r"(^|/)id_(rsa|ed25519)",
                r"(^|/)\.aws/credentials",
            ],
            "hostname": [r".*"],
        },
        "allow_rules": {
            "bash": [
                r"^(ls|cat|grep|find|echo|pwd|head|tail|wc|sort|diff|file|which|whoami|date|uname|type)\s",
                r"\s--(version|help)$",
                r"^git\s+(status|log|diff|show|branch|remote|tag|stash\s+list)",
                r"^(pip|pip3|cargo|npm|go)\s+(list|show|search|info|outdated|audit|version)",
            ],
            "file_path": [r".*"],
            "hostname": [],
        },
        "ask_rules": {
            "bash": [
                r"^python[0-9.]*\s",
                r"^node\s",
                r"^(npm|npx)\s",
                r"^(bash|sh|zsh)\s",
                r"^(make|cmake)\s",
                r"^(pytest|jest)\s",
                r"^(go|cargo|pip|pip3)\s+(run|build|install|test)",
                r"^git\s+(push|reset|rebase|merge|checkout|clean|stash\s+drop)",
                r"^\./\S+",
                r"^(ruby|perl|php|java|javac|gcc|g\+\+|rustc)\s",
            ],
            "file_path": [],
            "hostname": [],
        },
        "log_file": ".claude/guardrail.log",
    }


def _write_defaults(tmp_path: Path, config: dict | None = None) -> Path:
    """Write a defaults.yml inside tmp_path and return its path."""
    cfg = config if config is not None else _defaults_config()
    defaults = tmp_path / "defaults.yml"
    defaults.write_text(yaml.dump(cfg, default_flow_style=False))
    return defaults


def _make_payload(
    hook_type: str = "PreToolUse",
    tool_name: str = "Bash",
    tool_input: dict | None = None,
) -> str:
    """Build a JSON hook payload string."""
    return json.dumps({
        "hook_type": hook_type,
        "tool_name": tool_name,
        "tool_input": tool_input or {},
    })


def _run_cli(
    stdin_text: str,
    env_overrides: dict | None = None,
    cwd: Path | None = None,
) -> tuple[str, int]:
    """Run the CLI main() with the given stdin and return (stdout, exit_code).

    Unlike the unit-test helper, this does NOT mock internal modules --
    only stdin/stdout/argv/env are controlled.
    """
    argv = ["guardrail"]

    exit_code = 0
    captured_parts: list[str] = []

    with patch("sys.stdin") as mock_stdin, \
         patch("sys.stdout") as mock_stdout, \
         patch("sys.argv", argv):

        mock_stdin.read.return_value = stdin_text
        mock_stdout.write = lambda s: captured_parts.append(s)
        mock_stdout.flush = lambda: None

        with pytest.raises(SystemExit) as exc_info:
            main()

        exit_code = exc_info.value.code if exc_info.value.code is not None else 0

    return "".join(captured_parts), exit_code


def _get_decision(output: str) -> str:
    """Extract permissionDecision from hookSpecificOutput JSON."""
    result = json.loads(output)
    return result["hookSpecificOutput"]["permissionDecision"]


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Set up an isolated test environment.

    - Writes a defaults.yml to tmp_path
    - Points GUARDRAIL_DEFAULTS at it
    - Changes cwd to tmp_path (so relative log/pending paths land there)
    - Removes user/project config files from the resolution chain
    """
    defaults_path = _write_defaults(tmp_path)
    monkeypatch.setenv("GUARDRAIL_DEFAULTS", str(defaults_path))
    monkeypatch.chdir(tmp_path)
    # Ensure no user-level or project-level overrides interfere.
    # The config loader checks ~/.claude/guardrail.yml and $CWD/.claude/guardrail.yml.
    # Since cwd is tmp_path and we don't create .claude/guardrail.yml, we're clean.
    return tmp_path


# ---------------------------------------------------------------------------
# 1. Deny-before-allow with compound Bash command
# ---------------------------------------------------------------------------
class TestDenyBeforeAllowCompound:
    def test_git_status_semicolon_rm_rf_is_denied(self, env):
        payload = _make_payload(
            tool_name="Bash",
            tool_input={"command": "git status; rm -rf /"},
        )
        output, code = _run_cli(payload)

        assert code == 0
        assert _get_decision(output) == "deny"


# ---------------------------------------------------------------------------
# 2. Deny in command substitution
# ---------------------------------------------------------------------------
class TestDenyInCommandSubstitution:
    def test_dollar_paren_rm_rf(self, env):
        payload = _make_payload(
            tool_name="Bash",
            tool_input={"command": "echo $(rm -rf /)"},
        )
        output, code = _run_cli(payload)

        assert code == 0
        assert _get_decision(output) == "deny"


# ---------------------------------------------------------------------------
# 3. Deny in process substitution
# ---------------------------------------------------------------------------
class TestDenyInProcessSubstitution:
    def test_process_sub_rm_rf(self, env):
        payload = _make_payload(
            tool_name="Bash",
            tool_input={"command": "echo <(rm -rf /)"},
        )
        output, code = _run_cli(payload)

        assert code == 0
        assert _get_decision(output) == "deny"


# ---------------------------------------------------------------------------
# 4. Allow simple Bash command
# ---------------------------------------------------------------------------
class TestAllowSimpleBash:
    def test_git_status_allowed(self, env):
        payload = _make_payload(
            tool_name="Bash",
            tool_input={"command": "git status"},
        )
        output, code = _run_cli(payload)

        assert code == 0
        assert _get_decision(output) == "allow"


# ---------------------------------------------------------------------------
# 5. Pass for unknown command
# ---------------------------------------------------------------------------
class TestPassUnknownCommand:
    def test_curl_is_pass(self, env):
        payload = _make_payload(
            tool_name="Bash",
            tool_input={"command": "curl http://example.com"},
        )
        output, code = _run_cli(payload)

        assert code == 0
        # "pass" means no output on stdout
        assert output.strip() == ""


# ---------------------------------------------------------------------------
# 6. Deny .env file write
# ---------------------------------------------------------------------------
class TestDenyEnvFileWrite:
    def test_write_to_dot_env_denied(self, env):
        payload = _make_payload(
            tool_name="Write",
            tool_input={"file_path": ".env"},
        )
        output, code = _run_cli(payload)

        assert code == 0
        assert _get_decision(output) == "deny"


# ---------------------------------------------------------------------------
# 7. Allow regular file write
# ---------------------------------------------------------------------------
class TestAllowRegularFileWrite:
    def test_write_to_src_main_py_allowed(self, env):
        payload = _make_payload(
            tool_name="Write",
            tool_input={"file_path": "src/main.py"},
        )
        output, code = _run_cli(payload)

        assert code == 0
        assert _get_decision(output) == "allow"


# ---------------------------------------------------------------------------
# 8. Deny all WebFetch by default
# ---------------------------------------------------------------------------
class TestDenyWebFetchDefault:
    def test_webfetch_all_denied(self, env):
        payload = _make_payload(
            tool_name="WebFetch",
            tool_input={"url": "https://example.com"},
        )
        output, code = _run_cli(payload)

        assert code == 0
        assert _get_decision(output) == "deny"


# ---------------------------------------------------------------------------
# 9. Fail-open on malformed JSON
# ---------------------------------------------------------------------------
class TestFailOpenMalformedJSON:
    def test_broken_json_exits_0_empty(self, env):
        output, code = _run_cli("{broken json")

        assert code == 0
        assert output.strip() == ""


# ---------------------------------------------------------------------------
# 10. Fail-open on missing config
# ---------------------------------------------------------------------------
class TestFailOpenMissingConfig:
    def test_missing_defaults_exits_0_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv(
            "GUARDRAIL_DEFAULTS",
            str(tmp_path / "nonexistent" / "defaults.yml"),
        )
        monkeypatch.chdir(tmp_path)

        payload = _make_payload(
            tool_name="Bash",
            tool_input={"command": "git status"},
        )
        output, code = _run_cli(payload)

        assert code == 0
        assert output.strip() == ""


# ---------------------------------------------------------------------------
# 11. Audit log is written on deny
# ---------------------------------------------------------------------------
class TestAuditLogOnDeny:
    def test_deny_is_logged(self, env):
        """After a deny, the log file should contain an entry for that deny.

        The current CLI does not log deny decisions directly; only
        ``log_decision`` produces audit entries.  This test exercises
        ``log_decision`` as part of the full stack (config -> sanitizer ->
        logger) without mocking any internal module.
        """
        from guardrail.config import load_config
        from guardrail.logger import log_decision

        config = load_config()
        log_file = env / ".claude" / "guardrail.log"

        log_decision("Bash", "rm -rf /", "deny", "matched deny rule", config)

        assert log_file.exists()
        entry = json.loads(log_file.read_text().strip())
        assert entry["tool"] == "Bash"
        assert entry["decision"] == "deny"
        assert "rm -rf /" in entry["target"]


# ---------------------------------------------------------------------------
# 12. Audit log is written on allow
# ---------------------------------------------------------------------------
class TestAuditLogOnAllow:
    def test_allow_is_logged(self, env):
        """Same as above but for an allow decision."""
        from guardrail.config import load_config
        from guardrail.logger import log_decision

        config = load_config()
        log_file = env / ".claude" / "guardrail.log"

        log_decision("Bash", "git status", "allow", "matched allow rule", config)

        assert log_file.exists()
        entry = json.loads(log_file.read_text().strip())
        assert entry["tool"] == "Bash"
        assert entry["decision"] == "allow"


# ---------------------------------------------------------------------------
# 13. Pending marker created on pass
# ---------------------------------------------------------------------------
class TestPendingMarkerOnPass:
    def test_pass_creates_marker_file(self, env):
        payload = _make_payload(
            tool_name="Bash",
            tool_input={"command": "curl http://example.com"},
        )
        output, code = _run_cli(payload)

        assert code == 0
        assert output.strip() == ""

        pending_dir = env / ".claude" / "guardrail_pending"
        assert pending_dir.is_dir()
        markers = list(pending_dir.glob("*.json"))
        assert len(markers) >= 1

        marker = json.loads(markers[0].read_text())
        assert marker["tool_name"] == "Bash"
        assert "curl" in marker["target"]


# ---------------------------------------------------------------------------
# 14. Secret sanitization in audit log
# ---------------------------------------------------------------------------
class TestSecretSanitizationInLog:
    def test_aws_key_redacted_in_log(self, env):
        """Send a Bash command containing an AWS key; verify it is redacted."""
        from guardrail.config import load_config
        from guardrail.logger import log_decision

        config = load_config()
        log_file = env / ".claude" / "guardrail.log"

        aws_key = "AKIAIOSFODNN7EXAMPLE"
        command = f"aws s3 ls --access-key {aws_key}"

        log_decision("Bash", command, "allow", "ok", config)

        assert log_file.exists()
        entry = json.loads(log_file.read_text().strip())
        assert aws_key not in entry["target"]
        assert "[REDACTED]" in entry["target"]


# ---------------------------------------------------------------------------
# 15. Ask decision flow
# ---------------------------------------------------------------------------
class TestAskDecisionFlow:
    def test_python3_script_is_ask(self, env):
        payload = _make_payload(
            tool_name="Bash",
            tool_input={"command": "python3 script.py"},
        )
        output, code = _run_cli(payload)

        assert code == 0
        assert _get_decision(output) == "ask"

    def test_make_build_is_ask(self, env):
        payload = _make_payload(
            tool_name="Bash",
            tool_input={"command": "make build"},
        )
        output, code = _run_cli(payload)

        assert code == 0
        assert _get_decision(output) == "ask"

    def test_git_push_is_ask(self, env):
        payload = _make_payload(
            tool_name="Bash",
            tool_input={"command": "git push origin main"},
        )
        output, code = _run_cli(payload)

        assert code == 0
        assert _get_decision(output) == "ask"

    def test_executable_script_is_ask(self, env):
        payload = _make_payload(
            tool_name="Bash",
            tool_input={"command": "./run_tests.sh"},
        )
        output, code = _run_cli(payload)

        assert code == 0
        assert _get_decision(output) == "ask"


# ---------------------------------------------------------------------------
# 16. Bypass-permissions mode
# ---------------------------------------------------------------------------
class TestBypassPermissionsMode:
    def test_bypass_skips_deny(self, env):
        """Dangerous command in bypass mode should produce no output."""
        payload = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"},
            "permission_mode": "bypass",
        })
        output, code = _run_cli(payload)

        assert code == 0
        assert output.strip() == ""

    def test_bypass_permissions_variant(self, env):
        payload = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"},
            "permission_mode": "bypassPermissions",
        })
        output, code = _run_cli(payload)

        assert code == 0
        assert output.strip() == ""


# ---------------------------------------------------------------------------
# 17. Hardened deny patterns
# ---------------------------------------------------------------------------
class TestHardenedDenyPatterns:
    def test_path_prefixed_rm_denied(self, env):
        payload = _make_payload(
            tool_name="Bash",
            tool_input={"command": "/usr/bin/rm -rf /"},
        )
        output, code = _run_cli(payload)

        assert code == 0
        assert _get_decision(output) == "deny"

    def test_eval_denied(self, env):
        payload = _make_payload(
            tool_name="Bash",
            tool_input={"command": "eval rm -rf /"},
        )
        output, code = _run_cli(payload)

        assert code == 0
        assert _get_decision(output) == "deny"

    def test_base64_pipe_bash_denied(self, env):
        payload = _make_payload(
            tool_name="Bash",
            tool_input={"command": "echo payload | base64 -d | bash"},
        )
        output, code = _run_cli(payload)

        assert code == 0
        assert _get_decision(output) == "deny"


# ---------------------------------------------------------------------------
# 18. Safe Python script detection
# ---------------------------------------------------------------------------
class TestSafePythonScripts:
    def test_safe_python_script_auto_allowed(self, env):
        """Safe read-only Python scripts should be auto-allowed."""
        script = env / "safe_script.py"
        script.write_text("import pandas as pd\ndf = pd.read_csv('data.csv')\nprint(df.head())")

        payload = _make_payload(
            tool_name="Bash",
            tool_input={"command": f"python {script}"},
        )
        output, code = _run_cli(payload)

        assert code == 0
        assert _get_decision(output) == "allow"

    def test_unsafe_python_script_asks(self, env):
        """Python scripts with file writes should ask."""
        script = env / "unsafe_script.py"
        script.write_text("with open('out.txt', 'w') as f:\n    f.write('data')")

        payload = _make_payload(
            tool_name="Bash",
            tool_input={"command": f"python3 {script}"},
        )
        output, code = _run_cli(payload)

        assert code == 0
        assert _get_decision(output) == "ask"
