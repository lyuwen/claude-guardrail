import os
import pytest
import tempfile
import yaml
from pathlib import Path
from guardrail.config import load_config


@pytest.fixture
def temp_defaults(tmp_path):
    defaults = tmp_path / "defaults.yml"
    defaults.write_text(yaml.dump({
        'tools': ['Bash', 'Write', 'Edit'],
        'max_tokens': 1000
    }))
    old_env = os.environ.get('GUARDRAIL_DEFAULTS')
    os.environ['GUARDRAIL_DEFAULTS'] = str(defaults)
    try:
        yield defaults
    finally:
        if old_env:
            os.environ['GUARDRAIL_DEFAULTS'] = old_env
        else:
            os.environ.pop('GUARDRAIL_DEFAULTS', None)


def test_load_defaults_only(temp_defaults, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: Path('/nonexistent'))
    monkeypatch.setattr(Path, 'cwd', lambda: Path('/nonexistent'))

    config = load_config()
    assert config['tools'] == ['Bash', 'Write', 'Edit']
    assert config['max_tokens'] == 1000


def test_missing_defaults_env(monkeypatch):
    old_env = os.environ.pop('GUARDRAIL_DEFAULTS', None)
    monkeypatch.setattr(Path, 'home', lambda: Path('/nonexistent'))
    monkeypatch.setattr(Path, 'cwd', lambda: Path('/nonexistent'))
    try:
        config = load_config()
        assert 'guarded_tools' in config
        assert 'Bash' in config['guarded_tools']
    finally:
        if old_env:
            os.environ['GUARDRAIL_DEFAULTS'] = old_env


def test_missing_defaults_file(tmp_path):
    old_env = os.environ.get('GUARDRAIL_DEFAULTS')
    os.environ['GUARDRAIL_DEFAULTS'] = str(tmp_path / "nonexistent.yml")
    try:
        with pytest.raises(FileNotFoundError):
            load_config()
    finally:
        if old_env:
            os.environ['GUARDRAIL_DEFAULTS'] = old_env
        else:
            os.environ.pop('GUARDRAIL_DEFAULTS', None)


def test_invalid_defaults_yaml(tmp_path):
    defaults = tmp_path / "defaults.yml"
    defaults.write_text("invalid: yaml: content:")
    old_env = os.environ.get('GUARDRAIL_DEFAULTS')
    os.environ['GUARDRAIL_DEFAULTS'] = str(defaults)
    try:
        with pytest.raises(ValueError, match="Invalid YAML"):
            load_config()
    finally:
        if old_env:
            os.environ['GUARDRAIL_DEFAULTS'] = old_env
        else:
            os.environ.pop('GUARDRAIL_DEFAULTS', None)


def test_user_config_merge(temp_defaults, monkeypatch, tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    user_config = claude_dir / "guardrail.yml"
    user_config.write_text(yaml.dump({
        'tools': ['Read'],
        'user_setting': 'value'
    }))

    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setattr(Path, 'cwd', lambda: Path('/nonexistent'))

    config = load_config()
    assert config['tools'] == ['Bash', 'Write', 'Edit', 'Read']
    assert config['user_setting'] == 'value'
    assert config['max_tokens'] == 1000


def test_project_config_merge(temp_defaults, monkeypatch, tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir()
    project_config = claude_dir / "guardrail.yml"
    project_config.write_text(yaml.dump({
        'tools': ['Grep'],
        'project_setting': 'value'
    }))

    monkeypatch.setattr(Path, 'home', lambda: Path('/nonexistent'))
    monkeypatch.setattr(Path, 'cwd', lambda: project_dir)

    config = load_config()
    assert config['tools'] == ['Bash', 'Write', 'Edit', 'Grep']
    assert config['project_setting'] == 'value'


def test_all_configs_merge(temp_defaults, monkeypatch, tmp_path):
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    user_claude_dir = home_dir / ".claude"
    user_claude_dir.mkdir()
    user_config = user_claude_dir / "guardrail.yml"
    user_config.write_text(yaml.dump({
        'tools': ['Read'],
        'user_setting': 'user_value'
    }))

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project_claude_dir = project_dir / ".claude"
    project_claude_dir.mkdir()
    project_config = project_claude_dir / "guardrail.yml"
    project_config.write_text(yaml.dump({
        'tools': ['Grep'],
        'project_setting': 'project_value',
        'max_tokens': 2000
    }))

    monkeypatch.setattr(Path, 'home', lambda: home_dir)
    monkeypatch.setattr(Path, 'cwd', lambda: project_dir)

    config = load_config()
    assert config['tools'] == ['Bash', 'Write', 'Edit', 'Read', 'Grep']
    assert config['user_setting'] == 'user_value'
    assert config['project_setting'] == 'project_value'
    assert config['max_tokens'] == 2000


def test_invalid_user_config_skipped(temp_defaults, monkeypatch, tmp_path, caplog):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    user_config = claude_dir / "guardrail.yml"
    user_config.write_text("invalid: yaml: content:")

    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setattr(Path, 'cwd', lambda: Path('/nonexistent'))

    config = load_config()
    assert config['tools'] == ['Bash', 'Write', 'Edit']
    assert 'Invalid YAML in user config' in caplog.text


def test_invalid_project_config_skipped(temp_defaults, monkeypatch, tmp_path, caplog):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir()
    project_config = claude_dir / "guardrail.yml"
    project_config.write_text("invalid: yaml: content:")

    monkeypatch.setattr(Path, 'home', lambda: Path('/nonexistent'))
    monkeypatch.setattr(Path, 'cwd', lambda: project_dir)

    config = load_config()
    assert config['tools'] == ['Bash', 'Write', 'Edit']
    assert 'Invalid YAML in project config' in caplog.text


def test_deny_rules_preserved_after_override(tmp_path, monkeypatch):
    """Default deny rules must never be removed by user/project configs."""
    # Create a defaults.yml with deny rules
    defaults = tmp_path / "defaults.yml"
    defaults.write_text(yaml.dump({
        'guarded_tools': ['Bash'],
        'deny_rules': {
            'bash': [r'rm\s+-rf\s+/', r'\beval\b'],
        },
        'allow_rules': {'bash': []},
    }))
    os.environ['GUARDRAIL_DEFAULTS'] = str(defaults)

    # Project config tries to override deny_rules with a subset
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir()
    project_config = claude_dir / "guardrail.yml"
    project_config.write_text(yaml.dump({
        'deny_rules': {
            'bash': [r'new_pattern'],
        },
    }))

    monkeypatch.setattr(Path, 'home', lambda: Path('/nonexistent'))
    monkeypatch.setattr(Path, 'cwd', lambda: project_dir)

    try:
        config = load_config()
        deny_bash = config['deny_rules']['bash']
        # All default deny rules must still be present
        assert r'rm\s+-rf\s+/' in deny_bash
        assert r'\beval\b' in deny_bash
        # Project's additional rule should also be present
        assert r'new_pattern' in deny_bash
    finally:
        if 'GUARDRAIL_DEFAULTS' in os.environ:
            del os.environ['GUARDRAIL_DEFAULTS']


def test_deny_rules_preserved_user_config_empty_override(tmp_path, monkeypatch):
    """User config with empty deny list should not remove defaults."""
    defaults = tmp_path / "defaults.yml"
    defaults.write_text(yaml.dump({
        'guarded_tools': ['Bash'],
        'deny_rules': {
            'bash': [r'rm\s+-rf\s+/'],
        },
        'allow_rules': {'bash': []},
    }))
    os.environ['GUARDRAIL_DEFAULTS'] = str(defaults)

    home_dir = tmp_path / "home"
    home_dir.mkdir()
    user_claude_dir = home_dir / ".claude"
    user_claude_dir.mkdir()
    user_config = user_claude_dir / "guardrail.yml"
    # User config doesn't mention deny_rules at all
    user_config.write_text(yaml.dump({
        'allow_rules': {'bash': [r'^safe\s']},
    }))

    monkeypatch.setattr(Path, 'home', lambda: home_dir)
    monkeypatch.setattr(Path, 'cwd', lambda: Path('/nonexistent'))

    try:
        config = load_config()
        deny_bash = config['deny_rules']['bash']
        assert r'rm\s+-rf\s+/' in deny_bash
    finally:
        if 'GUARDRAIL_DEFAULTS' in os.environ:
            del os.environ['GUARDRAIL_DEFAULTS']
