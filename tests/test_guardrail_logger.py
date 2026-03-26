import json
import os

from guardrail.logger import (
    create_pending_marker,
    log_decision,
    resolve_pending_marker,
)


class TestLogDecision:
    """Tests for log_decision audit logging."""

    def test_creates_log_file_and_appends_json_line(self, tmp_path):
        log_file = tmp_path / "guardrail.log"
        config = {"log_file": str(log_file)}

        log_decision("Bash", "git status", "allow", "safe command", config)

        assert log_file.exists()
        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["tool"] == "Bash"
        assert entry["decision"] == "allow"

    def test_creates_directory_if_missing(self, tmp_path):
        log_file = tmp_path / "subdir" / "deep" / "guardrail.log"
        config = {"log_file": str(log_file)}

        log_decision("Bash", "ls", "allow", "safe", config)

        assert log_file.exists()

    def test_handles_write_errors_silently(self, tmp_path):
        # Point to a path that cannot be written (directory as file).
        bad_path = tmp_path / "readonly"
        bad_path.mkdir()
        config = {"log_file": str(bad_path)}  # directory, not a file

        # Should not raise.
        log_decision("Bash", "rm -rf /", "deny", "dangerous", config)

    def test_log_entry_has_correct_json_structure(self, tmp_path):
        log_file = tmp_path / "guardrail.log"
        config = {"log_file": str(log_file)}

        log_decision("Bash", "echo hello", "allow", "benign command", config)

        entry = json.loads(log_file.read_text().strip())
        assert "timestamp" in entry
        assert "tool" in entry
        assert "target" in entry
        assert "decision" in entry
        assert "reason" in entry
        # Timestamp should be ISO 8601 with microseconds.
        assert "T" in entry["timestamp"]
        assert entry["tool"] == "Bash"
        assert entry["decision"] == "allow"
        assert entry["reason"] == "benign command"

    def test_multiple_entries_are_appended(self, tmp_path):
        log_file = tmp_path / "guardrail.log"
        config = {"log_file": str(log_file)}

        log_decision("Bash", "cmd1", "allow", "reason1", config)
        log_decision("Bash", "cmd2", "deny", "reason2", config)
        log_decision("Write", "/tmp/f", "pass", "reason3", config)

        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 3
        entries = [json.loads(line) for line in lines]
        assert entries[0]["decision"] == "allow"
        assert entries[1]["decision"] == "deny"
        assert entries[2]["decision"] == "pass"

    def test_target_is_sanitized(self, tmp_path):
        """Secrets in the target should be redacted in the log."""
        log_file = tmp_path / "guardrail.log"
        config = {"log_file": str(log_file)}

        log_decision(
            "Bash",
            "curl -H 'Authorization: Bearer sk-abcdefghijklmnopqrst' https://api.example.com",
            "allow",
            "ok",
            config,
        )

        entry = json.loads(log_file.read_text().strip())
        assert "sk-abcdefghijklmnopqrst" not in entry["target"]
        assert "[REDACTED]" in entry["target"]

    def test_default_log_file_when_not_in_config(self, tmp_path, monkeypatch):
        """When log_file is not in config, use .claude/guardrail.log relative to cwd."""
        monkeypatch.chdir(tmp_path)
        config = {}

        log_decision("Bash", "ls", "allow", "ok", config)

        default_log = tmp_path / ".claude" / "guardrail.log"
        assert default_log.exists()


class TestCreatePendingMarker:
    """Tests for create_pending_marker."""

    def test_creates_file_with_correct_structure(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config = {}

        path = create_pending_marker("Bash", "rm -rf /", config)

        assert os.path.exists(path)
        with open(path) as f:
            marker = json.load(f)
        assert marker["tool_name"] == "Bash"
        assert marker["target"] == "rm -rf /"
        assert "created_at" in marker

    def test_filenames_are_unique(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config = {}

        paths = set()
        for _ in range(20):
            p = create_pending_marker("Bash", "cmd", config)
            paths.add(p)

        assert len(paths) == 20

    def test_creates_pending_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config = {}

        path = create_pending_marker("Bash", "ls", config)

        pending_dir = tmp_path / ".claude" / "guardrail_pending"
        assert pending_dir.is_dir()
        assert os.path.exists(path)


class TestResolvePendingMarker:
    """Tests for resolve_pending_marker."""

    def test_logs_and_cleans_up(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        log_file = tmp_path / "guardrail.log"
        config = {"log_file": str(log_file)}

        # Create a marker, then resolve it.
        marker_path = create_pending_marker("Bash", "dangerous cmd", config)
        assert os.path.exists(marker_path)

        resolve_pending_marker(marker_path, "deny", "blocked by Layer 2", config)

        # Marker file should be deleted.
        assert not os.path.exists(marker_path)
        # Decision should be logged.
        entry = json.loads(log_file.read_text().strip())
        assert entry["tool"] == "Bash"
        assert entry["decision"] == "deny"
        assert entry["reason"] == "blocked by Layer 2"

    def test_handles_missing_marker_silently(self, tmp_path):
        config = {"log_file": str(tmp_path / "guardrail.log")}
        fake_path = str(tmp_path / "nonexistent_marker.json")

        # Should not raise.
        resolve_pending_marker(fake_path, "allow", "ok", config)
