from guardrail.sanitizer import sanitize_target, redact_secrets


class TestRedactSecrets:
    """Tests for the redact_secrets helper that redacts known secret patterns."""

    # --- AWS Access Key IDs ---
    def test_redact_aws_key(self):
        text = "export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"
        result = redact_secrets(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "[REDACTED]" in result

    def test_redact_aws_key_inline(self):
        text = "aws configure set aws_access_key_id AKIAIOSFODNN7EXAMPLE"
        result = redact_secrets(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "[REDACTED]" in result

    # --- OpenAI-style API keys (sk-...) ---
    def test_redact_openai_key(self):
        text = "OPENAI_API_KEY=sk-abc123def456ghi789jkl012mno345"
        result = redact_secrets(text)
        assert "sk-abc123def456ghi789jkl012mno345" not in result
        assert "[REDACTED]" in result

    def test_redact_openai_key_in_curl(self):
        text = 'curl -H "Authorization: Bearer sk-proj-abcdefghijklmnopqrstuv"'
        result = redact_secrets(text)
        assert "sk-proj-abcdefghijklmnopqrstuv" not in result

    # --- GitHub Personal Access Tokens ---
    def test_redact_github_pat(self):
        text = "GITHUB_TOKEN=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"
        result = redact_secrets(text)
        assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij" not in result
        assert "[REDACTED]" in result

    # --- Environment variable patterns: TOKEN=, SECRET=, PASSWORD=, API_KEY= ---
    def test_redact_token_env_var(self):
        text = "MY_TOKEN=some_secret_value_here"
        result = redact_secrets(text)
        assert "some_secret_value_here" not in result
        assert "[REDACTED]" in result

    def test_redact_secret_env_var(self):
        text = "DB_SECRET=super_secret_123"
        result = redact_secrets(text)
        assert "super_secret_123" not in result
        assert "[REDACTED]" in result

    def test_redact_password_env_var(self):
        text = "DATABASE_PASSWORD=p@ssw0rd!123"
        result = redact_secrets(text)
        assert "p@ssw0rd!123" not in result
        assert "[REDACTED]" in result

    def test_redact_api_key_env_var(self):
        text = "STRIPE_API_KEY=sk_test_FAKE1234567890abcdefghij"
        result = redact_secrets(text)
        assert "sk_test_FAKE1234567890abcdefghij" not in result
        assert "[REDACTED]" in result

    def test_redact_env_var_case_insensitive(self):
        """TOKEN/SECRET/PASSWORD/API_KEY matching should be case insensitive."""
        text = "my_token=value123"
        result = redact_secrets(text)
        assert "value123" not in result
        assert "[REDACTED]" in result

    def test_redact_env_var_with_export(self):
        text = "export SECRET_KEY=mysecretvalue123"
        result = redact_secrets(text)
        assert "mysecretvalue123" not in result

    def test_redact_env_var_double_quoted(self):
        text = 'export TOKEN="my_token_value_here"'
        result = redact_secrets(text)
        assert "my_token_value_here" not in result

    def test_redact_env_var_single_quoted(self):
        text = "export PASSWORD='my_password_here'"
        result = redact_secrets(text)
        assert "my_password_here" not in result

    # --- Bearer tokens ---
    def test_redact_bearer_token(self):
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0"
        result = redact_secrets(text)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "[REDACTED]" in result

    def test_redact_bearer_in_curl_header(self):
        text = 'curl -H "Authorization: Bearer abcdef123456.token.value"'
        result = redact_secrets(text)
        assert "abcdef123456.token.value" not in result

    # --- Base64 long strings ---
    def test_redact_long_base64_string(self):
        """Long base64-like strings (40+ chars) that look like secrets."""
        secret = "aGVsbG8gd29ybGQgdGhpcyBpcyBhIHZlcnkgbG9uZyBiYXNlNjQ="
        text = f"SOME_VAR={secret}"
        result = redact_secrets(text)
        assert secret not in result

    def test_no_redact_short_base64(self):
        """Short base64 strings should not be redacted."""
        text = "echo aGVsbG8="
        result = redact_secrets(text)
        assert "aGVsbG8=" in result

    # --- Private keys ---
    def test_redact_private_key_rsa(self):
        text = "-----BEGIN RSA PRIVATE KEY-----"
        result = redact_secrets(text)
        assert "-----BEGIN RSA PRIVATE KEY-----" not in result
        assert "[REDACTED]" in result

    def test_redact_private_key_ec(self):
        text = "-----BEGIN EC PRIVATE KEY-----"
        result = redact_secrets(text)
        assert "-----BEGIN EC PRIVATE KEY-----" not in result

    def test_redact_private_key_generic(self):
        text = "-----BEGIN PRIVATE KEY-----"
        result = redact_secrets(text)
        assert "-----BEGIN PRIVATE KEY-----" not in result

    # --- Edge cases ---
    def test_no_secrets_unchanged(self):
        text = "git status && echo hello"
        result = redact_secrets(text)
        assert result == text

    def test_multiple_secrets(self):
        text = "TOKEN=abc123 PASSWORD=def456"
        result = redact_secrets(text)
        assert "abc123" not in result
        assert "def456" not in result
        assert result.count("[REDACTED]") == 2

    def test_empty_string(self):
        assert redact_secrets("") == ""

    def test_mixed_content_with_secrets(self):
        text = "curl -H 'Authorization: Bearer my_token_value' https://api.example.com"
        result = redact_secrets(text)
        assert "my_token_value" not in result
        assert "https://api.example.com" in result


class TestSanitizeTargetBash:
    """Tests for sanitize_target with Bash tool."""

    def test_simple_command(self):
        result = sanitize_target("git status", "Bash")
        assert result == "git status"

    def test_command_with_secret(self):
        result = sanitize_target(
            "curl -H 'Authorization: Bearer sk-abcdefghijklmnopqrst' https://api.example.com",
            "Bash",
        )
        assert "sk-abcdefghijklmnopqrst" not in result
        assert "https://api.example.com" in result

    def test_command_with_aws_key(self):
        result = sanitize_target(
            "aws s3 cp s3://bucket/key . --access-key AKIAIOSFODNN7EXAMPLE",
            "Bash",
        )
        assert "AKIAIOSFODNN7EXAMPLE" not in result

    def test_export_with_secret(self):
        result = sanitize_target(
            "export DATABASE_PASSWORD=supersecret123", "Bash"
        )
        assert "supersecret123" not in result

    def test_command_with_github_pat(self):
        result = sanitize_target(
            "git clone https://ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij@github.com/repo.git",
            "Bash",
        )
        assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij" not in result


class TestSanitizeTargetWrite:
    """Tests for sanitize_target with Write tool -- only file path, no content."""

    def test_write_returns_path_only(self):
        result = sanitize_target("/home/user/project/main.py", "Write")
        assert result == "[file: /home/user/project/main.py]"

    def test_write_does_not_include_content(self):
        """Even if target includes content, only the path should be returned."""
        target = "/home/user/.env"
        result = sanitize_target(target, "Write")
        assert result == "[file: /home/user/.env]"

    def test_write_path_with_spaces(self):
        result = sanitize_target("/home/user/my project/file.py", "Write")
        assert result == "[file: /home/user/my project/file.py]"


class TestSanitizeTargetEdit:
    """Tests for sanitize_target with Edit tool -- only file path, no content."""

    def test_edit_returns_path_only(self):
        result = sanitize_target("/home/user/project/config.py", "Edit")
        assert result == "[file: /home/user/project/config.py]"


class TestSanitizeTargetWebFetch:
    """Tests for sanitize_target with WebFetch tool -- URL sanitization."""

    def test_url_no_secrets(self):
        result = sanitize_target("https://example.com/api/data", "WebFetch")
        assert result == "https://example.com/api/data"

    def test_url_with_api_key_param(self):
        result = sanitize_target(
            "https://api.example.com/data?api_key=secret123&format=json",
            "WebFetch",
        )
        assert "secret123" not in result
        assert "format=json" in result
        assert "[REDACTED]" in result

    def test_url_with_token_param(self):
        result = sanitize_target(
            "https://example.com/api?token=mysecrettoken&page=1",
            "WebFetch",
        )
        assert "mysecrettoken" not in result
        assert "page=1" in result

    def test_url_with_secret_param(self):
        result = sanitize_target(
            "https://example.com/api?secret=value123",
            "WebFetch",
        )
        assert "value123" not in result

    def test_url_with_password_param(self):
        result = sanitize_target(
            "https://example.com/login?password=mypass&user=admin",
            "WebFetch",
        )
        assert "mypass" not in result
        assert "user=admin" in result

    def test_url_with_auth_param(self):
        result = sanitize_target(
            "https://example.com/api?auth=abc123",
            "WebFetch",
        )
        assert "abc123" not in result

    def test_url_with_access_token_param(self):
        result = sanitize_target(
            "https://example.com/api?access_token=xyz789",
            "WebFetch",
        )
        assert "xyz789" not in result

    def test_url_without_query_params(self):
        result = sanitize_target("https://example.com/path", "WebFetch")
        assert result == "https://example.com/path"

    def test_url_with_fragment(self):
        result = sanitize_target(
            "https://example.com/page#section", "WebFetch"
        )
        assert result == "https://example.com/page#section"

    def test_url_with_mixed_params(self):
        """Multiple params, some secret some not."""
        result = sanitize_target(
            "https://api.example.com/v1/search?q=hello&api_key=secretkey123&limit=10",
            "WebFetch",
        )
        assert "secretkey123" not in result
        assert "q=hello" in result
        assert "limit=10" in result


class TestSanitizeTargetUnknownTool:
    """Tests for sanitize_target with an unknown tool name."""

    def test_unknown_tool_redacts_secrets(self):
        """Unknown tools should still get secret redaction as a safety measure."""
        result = sanitize_target(
            "AKIAIOSFODNN7EXAMPLE", "SomeUnknownTool"
        )
        assert "AKIAIOSFODNN7EXAMPLE" not in result

    def test_unknown_tool_preserves_safe_content(self):
        result = sanitize_target("just a normal string", "SomeUnknownTool")
        assert result == "just a normal string"


class TestRedactSecretsEnvVarEdgeCases:
    """More detailed env var redaction tests."""

    def test_credential_env_var(self):
        text = "AZURE_CREDENTIAL=longvalue1234567890"
        result = redact_secrets(text)
        assert "longvalue1234567890" not in result

    def test_passphrase_env_var(self):
        text = "GPG_PASSPHRASE=my-secret-passphrase"
        result = redact_secrets(text)
        assert "my-secret-passphrase" not in result

    def test_auth_env_var(self):
        text = "AUTH_TOKEN=abc123xyz"
        result = redact_secrets(text)
        assert "abc123xyz" not in result

    def test_no_false_positive_on_path_equals(self):
        """PATH=... should not be redacted since it doesn't match secret patterns."""
        text = "PATH=/usr/local/bin:/usr/bin"
        result = redact_secrets(text)
        assert "/usr/local/bin:/usr/bin" in result

    def test_no_false_positive_on_normal_assignment(self):
        """Normal variable assignments without secret-like names should be kept."""
        text = "DISPLAY=:0"
        result = redact_secrets(text)
        assert ":0" in result
