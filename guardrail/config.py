import os
import copy
import yaml
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def load_config() -> Dict[str, Any]:
    defaults_path = os.environ.get('GUARDRAIL_DEFAULTS')
    if not defaults_path:
        defaults_path = Path(__file__).parent / 'defaults.yml'
    else:
        defaults_path = Path(defaults_path)

    if not defaults_path.exists():
        raise FileNotFoundError(f"defaults.yml not found: {defaults_path}")

    try:
        with open(defaults_path) as f:
            config = yaml.safe_load(f)
            if not isinstance(config, dict):
                raise ValueError(f"defaults.yml must contain a dictionary, got {type(config).__name__}")
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in defaults.yml: {e}")

    logger.info(f"Loaded defaults from {defaults_path}")

    user_config_path = Path.home() / '.claude' / 'guardrail.yml'
    if user_config_path.exists():
        try:
            with open(user_config_path) as f:
                user_config = yaml.safe_load(f)
                if not isinstance(user_config, dict):
                    logger.warning(f"Invalid YAML in user config, skipping: expected dict, got {type(user_config).__name__}")
                elif user_config:
                    config = merge_configs(config, user_config)
                    logger.info(f"Loaded user config from {user_config_path}")
        except yaml.YAMLError as e:
            logger.warning(f"Invalid YAML in user config, skipping: {e}")

    project_config_path = Path.cwd() / '.claude' / 'guardrail.yml'
    if project_config_path.exists() and project_config_path != user_config_path:
        try:
            with open(project_config_path) as f:
                project_config = yaml.safe_load(f)
                if not isinstance(project_config, dict):
                    logger.warning(f"Invalid YAML in project config, skipping: expected dict, got {type(project_config).__name__}")
                elif project_config:
                    config = merge_configs(config, project_config)
                    logger.info(f"Loaded project config from {project_config_path}")
        except yaml.YAMLError as e:
            logger.warning(f"Invalid YAML in project config, skipping: {e}")

    # Protect default deny rules: they can never be removed by overrides.
    # Re-merge defaults on top so user/project configs are additive-only.
    try:
        with open(defaults_path) as f:
            defaults = yaml.safe_load(f) or {}
        for category, patterns in defaults.get("deny_rules", {}).items():
            merged_patterns = config.get("deny_rules", {}).get(category, [])
            for p in patterns:
                if p not in merged_patterns:
                    merged_patterns.append(p)
            config.setdefault("deny_rules", {})[category] = merged_patterns
    except Exception:
        pass  # fail-open: if we can't re-read defaults, config already has them

    return config


def merge_configs(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        elif key in result and isinstance(result[key], list) and isinstance(value, list):
            result[key] = result[key] + value
        else:
            result[key] = value
    return result
