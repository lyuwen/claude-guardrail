from guardrail.engine import evaluate_action


_SENTINEL = object()


def _make_config(
    guarded_tools=_SENTINEL,
    deny_bash=_SENTINEL,
    deny_file_path=_SENTINEL,
    deny_hostname=_SENTINEL,
    allow_bash=_SENTINEL,
    allow_file_path=_SENTINEL,
    allow_hostname=_SENTINEL,
    ask_bash=_SENTINEL,
    ask_file_path=_SENTINEL,
    ask_hostname=_SENTINEL,
):
    """Helper to build a minimal config dict for testing."""
    return {
        "guarded_tools": (
            ["Bash", "Write", "Edit", "WebFetch"]
            if guarded_tools is _SENTINEL
            else guarded_tools
        ),
        "deny_rules": {
            "bash": [] if deny_bash is _SENTINEL else deny_bash,
            "file_path": [] if deny_file_path is _SENTINEL else deny_file_path,
            "hostname": [] if deny_hostname is _SENTINEL else deny_hostname,
        },
        "allow_rules": {
            "bash": [] if allow_bash is _SENTINEL else allow_bash,
            "file_path": [] if allow_file_path is _SENTINEL else allow_file_path,
            "hostname": [] if allow_hostname is _SENTINEL else allow_hostname,
        },
        "ask_rules": {
            "bash": [] if ask_bash is _SENTINEL else ask_bash,
            "file_path": [] if ask_file_path is _SENTINEL else ask_file_path,
            "hostname": [] if ask_hostname is _SENTINEL else ask_hostname,
        },
    }


# ---------------------------------------------------------------------------
# 1. Unguarded tool -> allow
# ---------------------------------------------------------------------------
class TestUnguardedTool:
    def test_unguarded_tool_returns_allow(self):
        config = _make_config(guarded_tools=["Bash"])
        result = evaluate_action("Read", {"file_path": "/etc/passwd"}, config)
        assert result["decision"] == "allow"
        assert "unguarded" in result["reason"].lower()

    def test_unguarded_tool_with_empty_guarded_list(self):
        config = _make_config(guarded_tools=[])
        result = evaluate_action("Bash", {"command": "rm -rf /"}, config)
        assert result["decision"] == "allow"
        assert "unguarded" in result["reason"].lower()


# ---------------------------------------------------------------------------
# 2. Simple allowed Bash command
# ---------------------------------------------------------------------------
class TestBashAllow:
    def test_git_status_allowed(self):
        config = _make_config(
            allow_bash=[r"^git\s"],
        )
        result = evaluate_action("Bash", {"command": "git status"}, config)
        assert result["decision"] == "allow"

    def test_npm_install_allowed(self):
        config = _make_config(
            allow_bash=[r"^npm\s"],
        )
        result = evaluate_action("Bash", {"command": "npm install"}, config)
        assert result["decision"] == "allow"


# ---------------------------------------------------------------------------
# 3. Simple denied Bash command
# ---------------------------------------------------------------------------
class TestBashDeny:
    def test_rm_rf_denied(self):
        config = _make_config(
            deny_bash=[r"rm\s+-rf\s+/"],
        )
        result = evaluate_action("Bash", {"command": "rm -rf /"}, config)
        assert result["decision"] == "deny"

    def test_fork_bomb_denied(self):
        config = _make_config(
            deny_bash=[r":\(\)\{.*:\|:&\};"],
        )
        result = evaluate_action("Bash", {"command": ":(){:|:&};"}, config)
        assert result["decision"] == "deny"


# ---------------------------------------------------------------------------
# 4. Compound command with deny segment (deny wins over allow)
# ---------------------------------------------------------------------------
class TestBashDenyWinsOverAllow:
    def test_compound_command_deny_wins(self):
        """git status is allowed, but rm -rf / is denied -- deny must win."""
        config = _make_config(
            deny_bash=[r"rm\s+-rf\s+/"],
            allow_bash=[r"^git\s"],
        )
        result = evaluate_action("Bash", {"command": "git status; rm -rf /"}, config)
        assert result["decision"] == "deny"

    def test_compound_command_and_deny_wins(self):
        config = _make_config(
            deny_bash=[r"rm\s+-rf\s+/"],
            allow_bash=[r"^git\s"],
        )
        result = evaluate_action("Bash", {"command": "git status && rm -rf /"}, config)
        assert result["decision"] == "deny"

    def test_substitution_deny_wins(self):
        """A denied command inside $(...) must still be caught."""
        config = _make_config(
            deny_bash=[r"rm\s+-rf\s+/"],
            allow_bash=[r"^echo\s"],
        )
        result = evaluate_action("Bash", {"command": "echo $(rm -rf /)"}, config)
        assert result["decision"] == "deny"


# ---------------------------------------------------------------------------
# 5. Unknown Bash command (not in allow or deny) -> pass
# ---------------------------------------------------------------------------
class TestBashPass:
    def test_unknown_command_passes(self):
        config = _make_config(
            deny_bash=[r"rm\s+-rf\s+/"],
            allow_bash=[r"^git\s"],
        )
        result = evaluate_action("Bash", {"command": "curl http://example.com"}, config)
        assert result["decision"] == "pass"

    def test_no_rules_at_all_passes(self):
        config = _make_config()
        result = evaluate_action("Bash", {"command": "some_random_command"}, config)
        assert result["decision"] == "pass"


# ---------------------------------------------------------------------------
# 6. Denied file path (.env)
# ---------------------------------------------------------------------------
class TestFilePathDeny:
    def test_env_file_denied(self):
        config = _make_config(
            deny_file_path=[r"(^|/)\.env"],
        )
        result = evaluate_action("Write", {"file_path": "/project/.env"}, config)
        assert result["decision"] == "deny"

    def test_edit_env_file_denied(self):
        config = _make_config(
            deny_file_path=[r"(^|/)\.env"],
        )
        result = evaluate_action("Edit", {"file_path": ".env.local"}, config)
        assert result["decision"] == "deny"

    def test_ssh_key_denied(self):
        config = _make_config(
            deny_file_path=[r"(^|/)id_(rsa|ed25519)"],
        )
        result = evaluate_action("Write", {"file_path": "/home/user/.ssh/id_rsa"}, config)
        assert result["decision"] == "deny"


# ---------------------------------------------------------------------------
# 7. Allowed file path
# ---------------------------------------------------------------------------
class TestFilePathAllow:
    def test_regular_file_allowed(self):
        config = _make_config(
            allow_file_path=[r".*"],
        )
        result = evaluate_action("Write", {"file_path": "/project/src/main.py"}, config)
        assert result["decision"] == "allow"

    def test_edit_regular_file_allowed(self):
        config = _make_config(
            allow_file_path=[r"\.py$"],
        )
        result = evaluate_action("Edit", {"file_path": "/project/engine.py"}, config)
        assert result["decision"] == "allow"


# ---------------------------------------------------------------------------
# 8. WebFetch to denied hostname
# ---------------------------------------------------------------------------
class TestWebFetchDeny:
    def test_denied_hostname(self):
        config = _make_config(
            deny_hostname=[r"evil\.com"],
        )
        result = evaluate_action("WebFetch", {"url": "https://evil.com/page"}, config)
        assert result["decision"] == "deny"

    def test_deny_all_hostnames_by_default(self):
        config = _make_config(
            deny_hostname=[r".*"],
        )
        result = evaluate_action("WebFetch", {"url": "https://anything.com"}, config)
        assert result["decision"] == "deny"


# ---------------------------------------------------------------------------
# 9. WebFetch to allowed hostname (if hostname is in allow list)
# ---------------------------------------------------------------------------
class TestWebFetchAllow:
    def test_allowed_hostname(self):
        config = _make_config(
            deny_hostname=[],
            allow_hostname=[r"docs\.python\.org"],
        )
        result = evaluate_action("WebFetch", {"url": "https://docs.python.org/3/"}, config)
        assert result["decision"] == "allow"

    def test_allowed_hostname_with_port(self):
        config = _make_config(
            deny_hostname=[],
            allow_hostname=[r"localhost"],
        )
        result = evaluate_action("WebFetch", {"url": "http://localhost:8080/api"}, config)
        assert result["decision"] == "allow"


# ---------------------------------------------------------------------------
# 10. Missing tool_input keys -> fail-open (pass)
# ---------------------------------------------------------------------------
class TestMissingToolInputKeys:
    def test_bash_missing_command_key(self):
        config = _make_config(deny_bash=[r"rm\s+-rf"])
        result = evaluate_action("Bash", {}, config)
        assert result["decision"] == "pass"
        assert "missing" in result["reason"].lower()

    def test_write_missing_file_path_key(self):
        config = _make_config(deny_file_path=[r"\.env"])
        result = evaluate_action("Write", {}, config)
        assert result["decision"] == "pass"
        assert "missing" in result["reason"].lower()

    def test_edit_missing_file_path_key(self):
        config = _make_config(deny_file_path=[r"\.env"])
        result = evaluate_action("Edit", {"old_string": "x", "new_string": "y"}, config)
        assert result["decision"] == "pass"
        assert "missing" in result["reason"].lower()

    def test_webfetch_missing_url_key(self):
        config = _make_config(deny_hostname=[r"evil\.com"])
        result = evaluate_action("WebFetch", {}, config)
        assert result["decision"] == "pass"
        assert "missing" in result["reason"].lower()


# ---------------------------------------------------------------------------
# Deny-before-allow ordering
# ---------------------------------------------------------------------------
class TestDenyBeforeAllow:
    def test_deny_overrides_allow_for_file_path(self):
        """If both deny and allow match, deny must win."""
        config = _make_config(
            deny_file_path=[r"\.env"],
            allow_file_path=[r".*"],
        )
        result = evaluate_action("Write", {"file_path": ".env"}, config)
        assert result["decision"] == "deny"

    def test_deny_overrides_allow_for_hostname(self):
        config = _make_config(
            deny_hostname=[r"evil\.com"],
            allow_hostname=[r".*"],
        )
        result = evaluate_action("WebFetch", {"url": "https://evil.com"}, config)
        assert result["decision"] == "deny"


# ---------------------------------------------------------------------------
# WebFetch hostname extraction
# ---------------------------------------------------------------------------
class TestHostnameExtraction:
    def test_extracts_hostname_from_https_url(self):
        config = _make_config(
            deny_hostname=[r"^example\.com$"],
        )
        result = evaluate_action("WebFetch", {"url": "https://example.com/path"}, config)
        assert result["decision"] == "deny"

    def test_extracts_hostname_from_http_url(self):
        config = _make_config(
            deny_hostname=[r"^example\.com$"],
        )
        result = evaluate_action("WebFetch", {"url": "http://example.com:8080/path"}, config)
        assert result["decision"] == "deny"

    def test_malformed_url_fails_open(self):
        """If the URL can't be parsed, fail open (pass)."""
        config = _make_config(
            deny_hostname=[r".*"],
        )
        result = evaluate_action("WebFetch", {"url": "not-a-url"}, config)
        assert result["decision"] == "pass"


# ---------------------------------------------------------------------------
# Return value structure
# ---------------------------------------------------------------------------
class TestReturnValueStructure:
    def test_allow_has_decision_and_reason(self):
        config = _make_config(guarded_tools=[])
        result = evaluate_action("Bash", {"command": "echo hi"}, config)
        assert "decision" in result
        assert "reason" in result
        assert result["decision"] in ("allow", "deny", "ask", "pass")

    def test_deny_has_decision_and_reason(self):
        config = _make_config(deny_bash=[r"rm"])
        result = evaluate_action("Bash", {"command": "rm file"}, config)
        assert "decision" in result
        assert "reason" in result

    def test_pass_has_decision_and_reason(self):
        config = _make_config()
        result = evaluate_action("Bash", {"command": "something"}, config)
        assert "decision" in result
        assert "reason" in result


# ---------------------------------------------------------------------------
# Ask rules
# ---------------------------------------------------------------------------
class TestAskRules:
    def test_bash_ask_rule_matches(self):
        config = _make_config(
            ask_bash=[r"^python[0-9.]*\s"],
        )
        result = evaluate_action("Bash", {"command": "python3 script.py"}, config)
        assert result["decision"] == "ask"

    def test_bash_ask_rule_no_match(self):
        config = _make_config(
            ask_bash=[r"^python[0-9.]*\s"],
        )
        result = evaluate_action("Bash", {"command": "curl http://example.com"}, config)
        assert result["decision"] == "pass"

    def test_deny_wins_over_ask(self):
        """Deny must take priority over ask."""
        config = _make_config(
            deny_bash=[r"rm\s+-rf\s+/"],
            ask_bash=[r"rm"],
        )
        result = evaluate_action("Bash", {"command": "rm -rf /"}, config)
        assert result["decision"] == "deny"

    def test_allow_wins_over_ask(self):
        """Allow must take priority over ask (checked before ask)."""
        config = _make_config(
            allow_bash=[r"^git\s"],
            ask_bash=[r"^git\s"],
        )
        result = evaluate_action("Bash", {"command": "git status"}, config)
        assert result["decision"] == "allow"

    def test_file_path_ask_rule(self):
        config = _make_config(
            ask_file_path=[r"\.secret$"],
        )
        result = evaluate_action("Write", {"file_path": "data.secret"}, config)
        assert result["decision"] == "ask"

    def test_hostname_ask_rule(self):
        config = _make_config(
            deny_hostname=[],
            ask_hostname=[r"api\.example\.com"],
        )
        result = evaluate_action("WebFetch", {"url": "https://api.example.com/v1"}, config)
        assert result["decision"] == "ask"

    def test_ask_compound_bash_command(self):
        """Ask should fire if any segment matches an ask rule and none match allow."""
        config = _make_config(
            ask_bash=[r"^python[0-9.]*\s"],
        )
        result = evaluate_action("Bash", {"command": "curl http://x; python3 run.py"}, config)
        assert result["decision"] == "ask"


# ---------------------------------------------------------------------------
# Hardened deny rules
# ---------------------------------------------------------------------------
class TestHardenedDenyRules:
    def test_path_prefixed_rm_rf_denied(self):
        config = _make_config(deny_bash=[r"(^|.*/)rm\s+-rf\s+/"])
        result = evaluate_action("Bash", {"command": "/usr/bin/rm -rf /"}, config)
        assert result["decision"] == "deny"

    def test_eval_denied(self):
        config = _make_config(deny_bash=[r"\beval\b"])
        result = evaluate_action("Bash", {"command": "eval rm -rf /"}, config)
        assert result["decision"] == "deny"

    def test_exec_denied(self):
        config = _make_config(deny_bash=[r"\bexec\b"])
        result = evaluate_action("Bash", {"command": "exec /bin/sh"}, config)
        assert result["decision"] == "deny"

    def test_base64_pipe_to_bash_denied(self):
        config = _make_config(deny_bash=[r"\bbase64\s.*\|.*\b(bash|sh|zsh)\b"])
        result = evaluate_action("Bash", {"command": "echo payload | base64 -d | bash"}, config)
        assert result["decision"] == "deny"

    def test_xargs_rm_denied(self):
        config = _make_config(deny_bash=[r"\bxargs\s.*(rm|dd|mkfs)"])
        result = evaluate_action("Bash", {"command": "find . | xargs rm"}, config)
        assert result["decision"] == "deny"


# ---------------------------------------------------------------------------
# Integration-style: defaults.yml rules
# ---------------------------------------------------------------------------
class TestDefaultsRulesIntegration:
    """Test with rule patterns matching those in defaults.yml."""

    def _defaults_config(self):
        return _make_config(
            deny_bash=[
                r"(^|.*/)rm\s+-rf\s+/",
                r":\(\)\{.*:\|:&\};",
                r"(^|.*/)dd\s+if=/dev/(zero|random)\s+of=",
                r"(^|.*/)mkfs\.",
                r">(\\s*/dev/sd|/dev/nvme)",
                r"\beval\b",
                r"\bexec\b",
                r"\bbase64\s.*\|.*\b(bash|sh|zsh)\b",
                r"\bxargs\s.*(rm|dd|mkfs)",
            ],
            deny_file_path=[
                r"(^|/)\.env",
                r"(^|/)id_(rsa|ed25519)",
                r"(^|/)\.aws/credentials",
            ],
            deny_hostname=[r".*"],
            allow_bash=[
                r"^(ls|cat|grep|find|echo|pwd|head|tail|wc|sort|diff|file|which|whoami|date|uname|type)\s",
                r"\s--(version|help)$",
                r"^git\s+(status|log|diff|show|branch|remote|tag|stash\s+list)",
                r"^(pip|pip3|cargo|npm|go)\s+(list|show|search|info|outdated|audit|version)",
            ],
            allow_file_path=[r".*"],
            allow_hostname=[],
            ask_bash=[
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
            ask_file_path=[],
            ask_hostname=[],
        )

    def test_git_status_allowed(self):
        result = evaluate_action("Bash", {"command": "git status"}, self._defaults_config())
        assert result["decision"] == "allow"

    def test_rm_rf_denied(self):
        result = evaluate_action("Bash", {"command": "rm -rf /"}, self._defaults_config())
        assert result["decision"] == "deny"

    def test_compound_deny_wins(self):
        result = evaluate_action(
            "Bash",
            {"command": "git status; rm -rf /"},
            self._defaults_config(),
        )
        assert result["decision"] == "deny"

    def test_env_file_denied(self):
        result = evaluate_action(
            "Write",
            {"file_path": "/project/.env"},
            self._defaults_config(),
        )
        assert result["decision"] == "deny"

    def test_regular_file_allowed(self):
        result = evaluate_action(
            "Write",
            {"file_path": "/project/src/main.py"},
            self._defaults_config(),
        )
        assert result["decision"] == "allow"

    def test_webfetch_all_denied_by_default(self):
        result = evaluate_action(
            "WebFetch",
            {"url": "https://example.com"},
            self._defaults_config(),
        )
        assert result["decision"] == "deny"

    def test_python3_script_is_ask(self):
        result = evaluate_action(
            "Bash",
            {"command": "python3 script.py"},
            self._defaults_config(),
        )
        assert result["decision"] == "ask"

    def test_make_build_is_ask(self):
        result = evaluate_action(
            "Bash",
            {"command": "make build"},
            self._defaults_config(),
        )
        assert result["decision"] == "ask"

    def test_git_push_is_ask(self):
        result = evaluate_action(
            "Bash",
            {"command": "git push origin main"},
            self._defaults_config(),
        )
        assert result["decision"] == "ask"

    def test_unknown_bash_command_passes(self):
        result = evaluate_action(
            "Bash",
            {"command": "some_custom_tool --flag"},
            self._defaults_config(),
        )
        assert result["decision"] == "pass"

    def test_path_prefixed_rm_denied(self):
        result = evaluate_action(
            "Bash",
            {"command": "/usr/bin/rm -rf /"},
            self._defaults_config(),
        )
        assert result["decision"] == "deny"

    def test_eval_denied(self):
        result = evaluate_action(
            "Bash",
            {"command": "eval rm -rf /"},
            self._defaults_config(),
        )
        assert result["decision"] == "deny"
