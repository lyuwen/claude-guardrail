import pytest
from guardrail.matcher import (
    split_bash_command,
    check_bash_deny_any_segment,
    matches_deny_rule,
    matches_allow_rule,
    _find_process_substitutions,
)


class TestSplitBashCommand:
    def test_simple_command(self):
        assert split_bash_command("git status") == ["git status"]

    def test_semicolon_split(self):
        result = split_bash_command("git status; rm -rf /")
        assert "git status; rm -rf /" in result
        assert "git status" in result
        assert "rm -rf /" in result

    def test_and_split(self):
        result = split_bash_command("make build && make test")
        assert "make build" in result
        assert "make test" in result

    def test_or_split(self):
        result = split_bash_command("test -f file || echo missing")
        assert "test -f file" in result
        assert "echo missing" in result

    def test_pipe_split(self):
        result = split_bash_command("cat file | grep pattern")
        assert "cat file" in result
        assert "grep pattern" in result

    def test_command_substitution_dollar(self):
        result = split_bash_command("echo $(cat /etc/passwd)")
        assert "echo $(cat /etc/passwd)" in result
        assert "cat /etc/passwd" in result

    def test_command_substitution_backtick(self):
        result = split_bash_command("echo `cat /etc/passwd`")
        assert "echo `cat /etc/passwd`" in result
        assert "cat /etc/passwd" in result

    def test_nested_substitution(self):
        result = split_bash_command("$(echo $(cat file))")
        assert "$(echo $(cat file))" in result
        assert "echo $(cat file)" in result
        assert "cat file" in result

    def test_no_duplicates(self):
        result = split_bash_command("echo hello")
        assert result.count("echo hello") == 1

    def test_mixed_operators_and_substitution(self):
        result = split_bash_command("git status; echo $(whoami)")
        assert "git status" in result
        assert "echo $(whoami)" in result
        assert "whoami" in result

    def test_semicolon_inside_dollar_paren(self):
        """Semicolons inside $(...) must not cause top-level splitting."""
        result = split_bash_command("echo $(rm -rf /; cat file)")
        # The full command should remain intact as one segment
        assert "echo $(rm -rf /; cat file)" in result
        # The inner substitution should be extracted
        assert "rm -rf /; cat file" in result
        # The inner substitution should itself be split on ;
        assert "rm -rf /" in result
        assert "cat file" in result
        # Top-level split should NOT break around the substitution
        # (i.e., "echo $(rm -rf /" should NOT appear as a segment)
        for seg in result:
            assert seg != "echo $(rm -rf /"

    def test_pipe_inside_backticks(self):
        """Pipes inside backticks must not cause top-level splitting."""
        result = split_bash_command("echo `ls | grep foo`")
        assert "echo `ls | grep foo`" in result
        assert "ls | grep foo" in result
        # The inner command should be split on pipe
        assert "ls" in result
        assert "grep foo" in result

    def test_newline_split(self):
        """Newlines should cause top-level splitting."""
        result = split_bash_command("echo hello\nrm -rf /")
        assert "echo hello" in result
        assert "rm -rf /" in result

    def test_newline_deny_segment(self):
        """Deny should catch dangerous commands separated by newlines."""
        result = check_bash_deny_any_segment(
            "echo hello\nrm -rf /", [r"rm\s+-rf\s+/"]
        )
        assert result is True


class TestMatchesDenyRule:
    def test_basic_match(self):
        assert matches_deny_rule("rm -rf /", r"rm\s+-rf\s+/")

    def test_no_match(self):
        assert not matches_deny_rule("git status", r"rm\s+-rf")

    def test_invalid_regex(self):
        assert matches_deny_rule("anything", r"[invalid")


class TestMatchesAllowRule:
    def test_basic_match(self):
        assert matches_allow_rule("git status", r"^git\s")

    def test_no_match(self):
        assert not matches_allow_rule("curl http://evil.com", r"^git\s")

    def test_invalid_regex(self):
        assert not matches_allow_rule("anything", r"[invalid")


class TestCheckBashDenyAnySegment:
    def test_deny_simple(self):
        result = check_bash_deny_any_segment("rm -rf /", [r"rm\s+-rf\s+/"])
        assert result is True

    def test_deny_compound_command(self):
        result = check_bash_deny_any_segment(
            "git status; rm -rf /", [r"rm\s+-rf\s+/"]
        )
        assert result is True

    def test_deny_in_substitution(self):
        result = check_bash_deny_any_segment(
            "echo $(rm -rf /)", [r"rm\s+-rf\s+/"]
        )
        assert result is True

    def test_no_deny(self):
        result = check_bash_deny_any_segment("git status", [r"rm\s+-rf"])
        assert result is False

    def test_returns_bool(self):
        """check_bash_deny_any_segment must return a bool, not a tuple."""
        result = check_bash_deny_any_segment("git status", [r"rm\s+-rf"])
        assert isinstance(result, bool)

    def test_deny_in_substitution_with_semicolon(self):
        """Deny should catch dangerous commands inside $(...) with semicolons."""
        result = check_bash_deny_any_segment(
            "echo $(rm -rf /; cat file)", [r"rm\s+-rf\s+/"]
        )
        assert result is True

    def test_multiple_deny_patterns(self):
        """Should match when any of multiple deny patterns matches."""
        result = check_bash_deny_any_segment(
            "curl http://evil.com", [r"rm\s+-rf", r"curl\s"]
        )
        assert result is True

    def test_multiple_deny_patterns_no_match(self):
        """Should not match when none of multiple deny patterns matches."""
        result = check_bash_deny_any_segment(
            "git status", [r"rm\s+-rf", r"curl\s"]
        )
        assert result is False

    def test_empty_deny_patterns_list(self):
        """Empty deny_patterns list should never deny."""
        result = check_bash_deny_any_segment("rm -rf /", [])
        assert result is False


class TestSplitBashCommandEdgeCases:
    def test_empty_string(self):
        result = split_bash_command("")
        assert result == [""]

    def test_whitespace_only(self):
        result = split_bash_command("   ")
        assert result == ["   "]

    def test_unbalanced_dollar_paren(self):
        """Unbalanced $( should not crash and should return the command as-is."""
        result = split_bash_command("$(echo hello")
        assert "$(echo hello" in result

    def test_unmatched_backtick(self):
        """Unmatched backtick should not crash and should return the command as-is."""
        result = split_bash_command("echo `hello")
        assert "echo `hello" in result

    def test_quoted_string_no_split_on_semicolon(self):
        """Semicolon inside double quotes should NOT cause a split."""
        result = split_bash_command('echo "a; b"')
        # The semicolon is inside quotes, so we should NOT see "a" or "b" as segments
        assert 'echo "a; b"' in result
        for seg in result:
            assert seg != "b"

    def test_single_quoted_string_no_split(self):
        """Semicolon inside single quotes should NOT cause a split."""
        result = split_bash_command("echo 'a; b'")
        assert "echo 'a; b'" in result
        for seg in result:
            assert seg != "b"

    def test_deny_rule_still_matches_quoted_content(self):
        """Regex deny rule sees the full segment including quotes, so it can still match."""
        assert matches_deny_rule('echo "rm -rf /"', r"rm\s+-rf\s+/")


class TestMatchesDenyRuleFailClosed:
    def test_invalid_regex_returns_true(self):
        """Invalid deny regex must fail closed (return True)."""
        assert matches_deny_rule("anything", r"[invalid") is True

    def test_valid_regex_still_works(self):
        assert matches_deny_rule("rm -rf /", r"rm\s+-rf") is True
        assert matches_deny_rule("git status", r"rm\s+-rf") is False


class TestMatchesAllowRuleFailOpen:
    def test_invalid_regex_returns_false(self):
        """Invalid allow regex must fail open (return False)."""
        assert matches_allow_rule("anything", r"[invalid") is False

    def test_valid_regex_still_works(self):
        assert matches_allow_rule("git status", r"^git\s") is True
        assert matches_allow_rule("rm -rf /", r"^git\s") is False


class TestProcessSubstitution:
    def test_find_process_substitutions_input(self):
        result = _find_process_substitutions("echo <(rm -rf /)")
        assert "rm -rf /" in result

    def test_find_process_substitutions_output(self):
        result = _find_process_substitutions("tee >(grep error)")
        assert "grep error" in result

    def test_split_bash_command_process_substitution(self):
        """split_bash_command should extract commands from <(...)."""
        result = split_bash_command("echo <(rm -rf /)")
        assert "rm -rf /" in result

    def test_deny_in_process_substitution(self):
        """Deny should catch dangerous commands inside process substitution."""
        result = check_bash_deny_any_segment(
            "echo <(rm -rf /)", [r"rm\s+-rf\s+/"]
        )
        assert result is True
