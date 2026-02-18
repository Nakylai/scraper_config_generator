"""Shared helpers for the config_generator package."""

import json
import logging
import re

logger = logging.getLogger(__name__)


def clean_html(html: str, remove_noscript: bool = False) -> str:
    """Remove script, style tags (and optionally noscript), HTML comments, and collapse whitespace.

    Args:
        html: Raw HTML string.
        remove_noscript: If True, also strip ``<noscript>`` tags.

    Returns:
        Cleaned HTML string.
    """
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    if remove_noscript:
        html = re.sub(r"<noscript[^>]*>.*?</noscript>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    html = re.sub(r"\s+", " ", html).strip()
    return html


def parse_json_response(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown code blocks.

    Args:
        text: Raw LLM response text.

    Returns:
        Parsed dict, or empty dict on failure.
    """
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if json_match:
        text = json_match.group(1)

    text = text.strip()
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start : end + 1]

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JSON from LLM response: %s", e)
        logger.debug("Raw response: %s", text[:500])
        return {}


def ensure_dict(value, default=None):
    """Coerce *value* to a dict, parsing JSON strings if needed.

    Args:
        value: A dict, a JSON string, or something else.
        default: Value returned when *value* cannot be converted.

    Returns:
        A dict (or *default*).
    """
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default if default is not None else {}
    return value if value is not None else (default if default is not None else {})
