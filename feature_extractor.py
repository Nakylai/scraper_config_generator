import json
import logging
import re

from bs4 import BeautifulSoup

from mini_scraper.config_generator.llm_client import LLMClient
from mini_scraper.config_generator.prompts import (
    INFERENCE_FEATURE_PROMPT,
    TRAINING_FEATURE_PROMPT,
)
from mini_scraper.config_generator.schemas import LLMFeatures
from mini_scraper.config_generator.utils import clean_html, ensure_dict, parse_json_response

logger = logging.getLogger(__name__)

PAGINATION_SELECTORS = [
    # Semantic nav elements
    "nav[aria-label*='pagination' i]",
    "nav[aria-label*='pager' i]",
    "nav.pagination",
    "nav[class*='pagination']",
    "nav#pagination",
    # Standard class-based
    "ul.pagination",
    "div.pagination",
    "nav.pager",
    "ul.pager",
    "div.pager",
    # Component-based / framework
    "[class*='paginator']",
    "[class*='dataTables_paginate']",
    "mat-paginator",
    # Broader fallback selectors (order matters — more specific first)
    "[class*='pager']",
    "[class*='interfacciaPagine']",
    "div[class*='pagination']",
]


def extract_pagination_html(html: str, max_length: int = 2000) -> str:
    """Extract the pagination HTML snippet from a full page.

    Searches for common pagination selectors using BeautifulSoup.
    Falls back to the last ``max_length`` characters of cleaned HTML
    if no pagination element is found.

    Args:
        html: Full page HTML string.
        max_length: Max length of fallback snippet.

    Returns:
        Outer HTML of the pagination element, or a fallback tail.
    """
    soup = BeautifulSoup(html, "html.parser")
    for selector in PAGINATION_SELECTORS:
        el = soup.select_one(selector)
        if el:
            snippet = str(el)
            if len(snippet) > max_length:
                snippet = snippet[:max_length]
            return snippet

    # Fallback: return the tail of the HTML (pagination is usually at the bottom)
    cleaned = clean_html(html)
    return cleaned[-max_length:] if len(cleaned) > max_length else cleaned


class LLMFeatureExtractor:
    """Extracts structured features from HTML pages using OpenAI."""

    MAX_HTML_LENGTH = 40_000

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def extract_training_features(self, html: str, config: dict) -> LLMFeatures:
        """Extract features from a known HTML + config pair (for indexing)."""
        cleaned_html = self._prepare_html(html)
        base_selector = self._extract_base_selector(config.get("json_css_schema", {}))
        pagination_type = self._get_pagination_type(config.get("pagination_config", {}))
        data_render_type = config.get("data_render_type", "SSR")

        prompt = TRAINING_FEATURE_PROMPT.format(
            html=cleaned_html,
            base_selector=base_selector,
            pagination_type=pagination_type,
            data_render_type=data_render_type,
            config_json=json.dumps(config, indent=2, ensure_ascii=False)[:5000],
        )

        response_text = self.llm_client.call(prompt, step_label="training_feature_extraction")
        features = self._parse_features(response_text)
        return features

    def extract_inference_features(self, html: str, url: str) -> LLMFeatures:
        """Extract features from HTML of a new (unknown) page."""
        cleaned_html = self._prepare_html(html, truncate=False)
        pagination_html = extract_pagination_html(html)

        prompt = INFERENCE_FEATURE_PROMPT.format(
            html=cleaned_html,
            url=url,
            pagination_html=pagination_html,
        )

        response_text = self.llm_client.call(prompt, step_label="inference_feature_extraction")
        return self._parse_features(response_text)

    def _prepare_html(self, html: str, truncate: bool = True) -> str:
        """Clean HTML by removing script/style/noscript tags and comments.

        Args:
            html: Raw HTML string.
            truncate: If True, truncate to MAX_HTML_LENGTH keeping head + tail.
                      If False, return full cleaned HTML (for config generation).
        """
        html = clean_html(html, remove_noscript=True)
        # Truncate: keep beginning + end to preserve pagination at bottom
        if truncate and len(html) > self.MAX_HTML_LENGTH:
            head_size = self.MAX_HTML_LENGTH * 3 // 4
            tail_size = self.MAX_HTML_LENGTH - head_size
            html = html[:head_size] + "\n... [TRUNCATED MIDDLE] ...\n" + html[-tail_size:]
        return html

    def _parse_features(self, text: str) -> LLMFeatures:
        """Parse LLM response text into LLMFeatures."""
        data = parse_json_response(text)
        return LLMFeatures(**data)

    def _extract_base_selector(self, json_css_schema) -> str:
        """Extract baseSelector from json_css_schema config."""
        json_css_schema = ensure_dict(json_css_schema, default={})
        if not isinstance(json_css_schema, dict):
            return "unknown"
        return json_css_schema.get("baseSelector", "unknown")

    def _get_pagination_type(self, pagination_config) -> str:
        """Determine pagination type from config."""
        parsed = ensure_dict(pagination_config, default={})
        if not isinstance(parsed, dict):
            return "none"
        pagination_config = parsed

        if not pagination_config:
            return "none"

        if pagination_config.get("js_next_button"):
            return "csr_click"
        if pagination_config.get("js_selector") and not pagination_config.get("js_next_button"):
            return "csr_scroll"
        if pagination_config.get("next_page_link_template"):
            return "url_template"
        if pagination_config.get("max_pages", 0) <= 1:
            return "none"

        return "unknown"
