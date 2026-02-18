from pydantic import BaseModel, Field


class LLMFeatures(BaseModel):
    """Structured features extracted by LLM from a website page.

    Args:
        page_structure: Layout description (table, card grid, list, etc.).
        item_container_pattern: CSS selector pattern for item containers.
        pagination_mechanism: How pagination works (url_parameter,
            next_button_click, infinite_scroll, none).
        data_render_type: Content delivery type — ``"SSR"`` or ``"CSR"``.
        listing_type: What the page lists (tenders, jobs, news, etc.).
        has_detail_links: Whether items link to detail pages.
    """

    page_structure: str = Field(default="unknown")
    item_container_pattern: str = Field(default="unknown")
    pagination_mechanism: str = Field(default="unknown")
    data_render_type: str = Field(default="SSR")
    listing_type: str = Field(default="unknown")
    has_detail_links: bool = Field(default=True)

    def to_text(self) -> str:
        """Convert features to a text representation for embedding."""
        parts = [
            f"structure:{self.page_structure}",
            f"container:{self.item_container_pattern}",
            f"pagination:{self.pagination_mechanism}",
            f"render_type:{self.data_render_type}",
            f"listing:{self.listing_type}",
            f"detail_links:{self.has_detail_links}",
        ]
        return " | ".join(parts)


class GeneratedConfig(BaseModel):
    """Validated structure of the LLM-generated scraping config.

    Args:
        data_render_type: How the page delivers content — ``"SSR"`` or ``"CSR"``.
        json_css_schema: CSS extraction schema (baseSelector, fields, etc.).
        crawlai_config: Browser/crawl4ai options (timeouts, wait_for, etc.).
        pagination_config: Pagination parameters (template, selectors, max_pages).
        request_config: Extra request options (headers, etc.).
    """

    data_render_type: str = Field(default="SSR")
    json_css_schema: dict = Field(default_factory=dict)
    crawlai_config: dict = Field(default_factory=dict)
    pagination_config: dict = Field(default_factory=dict)
    request_config: dict = Field(default_factory=dict)


class SimilarConfig(BaseModel):
    """A similar config result from vector search.

    Args:
        config_id: Unique identifier of the stored config.
        source_name: Human-readable name of the source.
        distance: Cosine distance from the query (lower = more similar).
        full_config: Complete stored config dict.
        features_text: Feature string used for embedding.
        pagination_html: Stored pagination HTML snippet.
    """

    config_id: str = Field(description="ID of the config")
    source_name: str = Field(default="")
    distance: float = Field(default=0.0)
    full_config: dict = Field(default_factory=dict)
    features_text: str = Field(default="")
    pagination_html: str = Field(default="")
