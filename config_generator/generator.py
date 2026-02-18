import json
import logging

from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig

from config_generator.feature_extractor import (
    LLMFeatureExtractor,
    extract_pagination_html,
)
from config_generator.llm_client import LLMClient
from config_generator.pagination_examples import (
    format_dynamic_pagination_examples,
    format_static_pagination_examples,
)
from config_generator.prompts import CONFIG_GENERATION_PROMPT
from config_generator.schemas import GeneratedConfig
from config_generator.utils import parse_json_response
from config_generator.vector_store import ConfigVectorStore

logger = logging.getLogger(__name__)


class ConfigGenerator:
    """Main pipeline: URL → GeneratedConfig."""

    def __init__(
        self,
        api_key: str,
        model: str,
        chroma_dir: str,
    ):
        self.llm_client = LLMClient(api_key=api_key, model=model)
        self.feature_extractor = LLMFeatureExtractor(llm_client=self.llm_client)
        self.vector_store = ConfigVectorStore(persist_dir=chroma_dir)

    async def generate(
        self,
        url: str,
        source_name: str,
        num_similar: int = 3,
    ) -> GeneratedConfig:
        """Generate a scraping config for a new URL.

        Args:
            url: The target URL to generate config for.
            source_name: Human-readable name for the source.
            num_similar: Number of similar configs to use as few-shot examples.

        Returns:
            Validated GeneratedConfig instance.
        """
        logger.info("Starting config generation for: %s", url)

        # Step 1: Fetch HTML
        logger.info("Step 1: Fetching HTML from %s", url)
        html = await self._fetch_html(url)
        if not html:
            raise RuntimeError(f"Failed to fetch HTML from {url}")
        logger.info("Fetched %d characters of HTML", len(html))

        # Step 2: Extract features (inference mode)
        logger.info("Step 2: Extracting features from HTML")
        features = self.feature_extractor.extract_inference_features(html=html, url=url)
        logger.info("Extracted features: %s", features.to_text())

        # Step 3: Find similar configs
        logger.info("Step 3: Finding %d similar configs", num_similar)
        similar_configs = self.vector_store.find_similar(features, k=num_similar)
        logger.info(
            "Found %d similar configs: %s",
            len(similar_configs),
            [f"{c.source_name} (dist={c.distance:.3f})" for c in similar_configs],
        )

        # Step 3.5: Assemble pagination examples
        logger.info("Step 3.5: Assembling pagination examples")
        pagination_html = extract_pagination_html(html)
        logger.info("Extracted pagination HTML (%d chars):\n%s", len(pagination_html), pagination_html)

        static_examples = format_static_pagination_examples()

        rag_pagination = self.vector_store.find_similar_pagination(pagination_html, k=3)
        logger.info(
            "Found %d similar pagination configs: %s",
            len(rag_pagination),
            [f"{c.source_name} (dist={c.distance:.3f})" for c in rag_pagination],
        )
        dynamic_examples = format_dynamic_pagination_examples(rag_pagination)

        pagination_examples_text = static_examples
        if dynamic_examples:
            pagination_examples_text += "\n" + dynamic_examples

        # Step 4: Generate config using LLM
        logger.info("Step 4: Generating config with LLM")
        similar_configs_text = self._format_similar_configs(similar_configs)
        cleaned_html = self.feature_extractor._prepare_html(html, truncate=False)

        prompt = CONFIG_GENERATION_PROMPT.format(
            url=url,
            source_name=source_name,
            html=cleaned_html,
            features=features.to_text(),
            similar_configs=similar_configs_text,
            pagination_examples=pagination_examples_text,
        )

        llm_response = self.llm_client.call(prompt, step_label="config_generation")

        llm_config = parse_json_response(llm_response)

        if not llm_config:
            raise RuntimeError("LLM returned empty or invalid config")

        # Step 5: Validate config
        logger.info("Step 5: Validating config")
        config = GeneratedConfig(**llm_config)

        logger.info("Config generation complete for: %s", source_name)
        self.last_debug = {
            "pagination_html": pagination_html,
            "features": features.to_text(),
            "prompt": prompt,
        }
        return config

    async def _fetch_html(self, url: str) -> str | None:
        """Fetch HTML from URL using crawl4ai directly."""
        browser_config = BrowserConfig(headless=True, text_mode=True, verbose=False)
        crawler = AsyncWebCrawler(config=browser_config)

        try:
            await crawler.start()
            result = await crawler.arun(
                url=url,
                config=CrawlerRunConfig(
                    page_timeout=100000,
                    delay_before_return_html=5,
                    cache_mode=CacheMode.BYPASS,
                ),
            )

            if result.success and result.html:
                return result.html

            logger.error("Failed to fetch %s: %s", url, result.error_message)
            return None
        finally:
            await crawler.close()

    def _format_similar_configs(self, similar_configs: list) -> str:
        """Format similar configs as text for the LLM prompt."""
        if not similar_configs:
            return "No similar configs found."

        parts = []
        for i, sc in enumerate(similar_configs, 1):
            config = sc.full_config
            parts.append(f"--- Example {i}: {sc.source_name} (similarity distance: {sc.distance:.3f}) ---")
            parts.append(f"URL: {config.get('data_source_url', 'N/A')}")
            parts.append(f"data_render_type: {config.get('data_render_type', 'N/A')}")

            # Show the key config fields
            for field in ["json_css_schema", "crawlai_config", "pagination_config", "request_config"]:
                value = config.get(field, {})
                if isinstance(value, str):
                    parts.append(f"{field}: {value}")
                else:
                    parts.append(f"{field}: {json.dumps(value, indent=2, ensure_ascii=False)}")

            parts.append("")

        return "\n".join(parts)
