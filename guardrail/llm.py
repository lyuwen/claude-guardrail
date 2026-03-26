"""LLM-based classification for Layer 2 (ambiguous actions)."""

import json
import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _get_llm_config(config: Dict[str, Any]) -> Dict[str, Any] | None:
    """Get LLM configuration from config or environment.

    Priority:
    1. Config file (api_key, base_url, model, provider)
    2. Environment variables (ANTHROPIC_AUTH_TOKEN, ANTHROPIC_BASE_URL, ANTHROPIC_MODEL)
    3. None (Layer 2 disabled)
    """
    # Check config file first
    llm_config = config.get("llm", {})
    if llm_config.get("api_key"):
        return {
            "provider": llm_config.get("provider", "anthropic"),
            "api_key": llm_config["api_key"],
            "base_url": llm_config.get("base_url"),
            "model": llm_config.get("model", "claude-3-5-haiku-20241022"),
        }

    # Check environment variables
    api_key = os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if api_key:
        return {
            "provider": "anthropic",
            "api_key": api_key,
            "base_url": os.environ.get("ANTHROPIC_BASE_URL"),
            "model": os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022"),
        }

    return None


def _call_anthropic(
    prompt: str,
    api_key: str,
    model: str,
    base_url: str | None,
) -> Dict[str, str] | None:
    """Call Anthropic API."""
    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic package not installed, Layer 2 disabled")
        return None

    try:
        client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
        response = client.messages.create(
            model=model,
            max_tokens=200,
            system="You are a security classifier. Respond only with valid JSON, no other text.",
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract text from content blocks (skip thinking blocks)
        text_content = ""
        for block in response.content:
            if hasattr(block, "text"):
                text_content += block.text

        text_content = text_content.strip()

        if not text_content:
            logger.warning(f"No text content in response")
            return None

        # Strip markdown code blocks if present
        if text_content.startswith("```"):
            lines = text_content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text_content = "\n".join(lines).strip()

        result = json.loads(text_content)
        return result
    except Exception as e:
        logger.warning(f"Anthropic API call failed: {e}")
        return None


def _call_openai(
    prompt: str,
    api_key: str,
    model: str,
    base_url: str | None,
) -> Dict[str, str] | None:
    """Call OpenAI API."""
    try:
        import openai
    except ImportError:
        logger.warning("openai package not installed, Layer 2 disabled")
        return None

    try:
        client = openai.OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.choices[0].message.content
        result = json.loads(content)
        return result
    except Exception as e:
        logger.warning(f"OpenAI API call failed: {e}")
        return None


def evaluate_with_llm(
    tool_name: str,
    sanitized_target: str,
    context: str,
    user_request: str,
    config: Dict[str, Any],
) -> Dict[str, str]:
    """Evaluate an action using LLM (Layer 2).

    Returns {"decision": "allow"|"deny", "reason": str} or {"decision": "pass"}
    if Layer 2 is not configured.
    """
    llm_config = _get_llm_config(config)
    if not llm_config:
        return {"decision": "pass", "reason": "Layer 2 not configured"}

    # Build prompt from template
    prompt_template = config.get("llm_prompt", "")
    if not prompt_template:
        return {"decision": "pass", "reason": "no llm_prompt in config"}

    prompt = prompt_template.format(
        context=context,
        user_request=user_request,
        tool_name=tool_name,
        sanitized_target=sanitized_target,
    )

    # Call LLM
    provider = llm_config["provider"]
    if provider == "anthropic":
        result = _call_anthropic(
            prompt,
            llm_config["api_key"],
            llm_config["model"],
            llm_config.get("base_url"),
        )
    elif provider == "openai":
        result = _call_openai(
            prompt,
            llm_config["api_key"],
            llm_config["model"],
            llm_config.get("base_url"),
        )
    else:
        logger.warning(f"Unknown LLM provider: {provider}")
        return {"decision": "pass", "reason": "unknown provider"}

    if not result:
        return {"decision": "pass", "reason": "LLM call failed"}

    # Validate response
    decision = result.get("decision", "pass")
    if decision not in ("allow", "deny", "ask"):
        decision = "pass"

    return {
        "decision": decision,
        "reason": result.get("reason", "LLM classification"),
    }
