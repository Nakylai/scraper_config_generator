TRAINING_FEATURE_PROMPT = """You are an expert web scraping analyst. You are given:
1. Raw HTML from a website listing page
2. A working scraping configuration for this page

Analyze both and extract structured features that describe this page's scraping characteristics.

HTML:
{html}

Working Configuration:
- baseSelector: {base_selector}
- pagination_type: {pagination_type}
- data_render_type: {data_render_type}
- Full config: {config_json}

Extract the following features as JSON:

{{
    "page_structure": "description of how items are laid out (table, card grid, list, etc.)",
    "item_container_pattern": "CSS pattern used for item containers (e.g., div.item, tr, li.result)",
    "pagination_mechanism": "how pagination works: url_parameter, next_button_click, infinite_scroll, none",
    "data_render_type": "exactly one of: SSR, CSR — determined by the COMBINATION of content delivery + pagination method (see rules below)",
    "listing_type": "what type of listings: tenders, jobs, news, products, documents, etc.",
    "has_detail_links": true/false
}}

RULES for determining data_render_type — data_render_type and pagination are INTERCONNECTED:

SSR (Server-Side Rendered):
  - Content is visible in the raw HTML (items/data are in the DOM)
  - Pagination is URL-based: links have REAL href values like href="?page=2" or href="/tenders/page/3"
  - Pagination config uses: next_page_link_template with {{}} placeholder, increment, first_page_number
  - NEVER uses js_next_button or js_selector for pagination
  - Even if the page uses React/Angular with wait_for in crawlai_config, it's still SSR if pagination is URL-based

CSR (Client-Side Rendered):
  - Content may or may not be in initial HTML, but pagination REQUIRES JavaScript interaction
  - Pagination links use href="#", href="#anchor", javascript:void(0), data-link, onclick, or are buttons without real URLs
  - Pagination config uses: js_next_button (JS code to click next), js_selector (CSS selector for items)
  - NEVER uses next_page_link_template
  - js_next_button is typically: document.querySelector("...").click() or window.scrollTo(...) for infinite scroll

Return ONLY the JSON object, no explanations."""

INFERENCE_FEATURE_PROMPT = """You are an expert web scraping analyst. You are given raw HTML from a website listing page.

Analyze the HTML and extract structured features that describe this page's scraping characteristics.

URL: {url}

HTML:
{html}

Extracted pagination HTML snippet (focus on this to determine pagination_mechanism and data_render_type):
{pagination_html}

Extract the following features as JSON:

{{
    "page_structure": "description of how items are laid out (table, card grid, list, etc.)",
    "item_container_pattern": "likely CSS selector pattern for item containers (e.g., div.item, tr, li.result)",
    "pagination_mechanism": "how pagination works: url_parameter, next_button_click, infinite_scroll, none",
    "data_render_type": "exactly one of: SSR, CSR — determined by the COMBINATION of content delivery + pagination method (see rules below)",
    "listing_type": "what type of listings: tenders, jobs, news, products, documents, etc.",
    "has_detail_links": true/false
}}

RULES for determining data_render_type — data_render_type and pagination are INTERCONNECTED:

SSR (Server-Side Rendered):
  - Content is visible in the raw HTML (items/data are present in the DOM)
  - Pagination is URL-based: links have REAL href values like href="?page=2" or href="/tenders/page/3"
  - Even if the page uses React/Angular/Vue frameworks, it's SSR if:
    a) The actual data (tender titles, descriptions, dates) is present in the HTML
    b) Pagination links have real URLs (not href="#" or onclick handlers)
  - Key evidence: <a href="?page=2">, <a href="/path/page/3">, <link rel="next">

CSR (Client-Side Rendered):
  - Pagination REQUIRES JavaScript interaction — this is the primary indicator
  - Look for these signs in pagination elements:
    a) href="#" or href="#someAnchor" with data-link or data-page attributes
    b) onclick="..." handlers on pagination links
    c) href="javascript:void(0)" or href="javascript:;"
    d) Angular/React pagination components (mat-paginator, ng-star-inserted, eui-paginator)
    e) "Load More" buttons, infinite scroll patterns
    f) Pagination links are <button> elements, not <a> tags with real URLs
  - Content might be in HTML or loaded dynamically — the KEY factor is how pagination works

  CONCRETE EXAMPLE — this is CSR, NOT SSR:
    <li class="page-item"><a class="t_page page-link" href="#tenderPagination" data-link="https://www.globaltenders.com/20">2</a></li>
    <li class="page-item"><a class="t_page page-link" href="#tenderPagination" data-link="https://www.globaltenders.com/40">3</a></li>
  Why CSR: href="#tenderPagination" is an anchor (NOT a real page URL). The actual URL is in data-link attribute.
  Clicking these links triggers JavaScript, not browser navigation.

IMPORTANT: When in doubt between SSR and CSR, check the pagination links:
  - Real URLs in href (href="?page=2", href="/path/page/3") → SSR
  - href="#", href="#anchor", onclick, data-link, buttons → CSR

Return ONLY the JSON object, no explanations."""

CONFIG_GENERATION_PROMPT = """You are an expert web scraping configuration generator.

Target URL: {url}
Source Name: {source_name}

Target HTML:
{html}

Pre-analyzed features of this page:
{features}

{pagination_examples}

=== SIMILAR WEBSITE CONFIGS (from production) ===
{similar_configs}

Generate a complete scraping configuration JSON:

{{
    "data_render_type": "SSR or CSR",
    "json_css_schema": {{
        "name": "Commit Extractor",
        "type": "list",
        "fields": [
            {{"name": "html", "type": "html or children"}},
            {{"name": "markdown", "type": "text"}}
        ],
        "baseSelector": "CSS selector for each item container"
    }},
    "crawlai_config": {{
        "text_mode": true,
        "page_timeout": 100000,
        "delay_before_return_html": 5
    }},
    "pagination_config": {{...}},
    "request_config": {{...}}
}}

Key rules:
- fields MUST always be exactly: [{{"name": "html", "type": "html"}}, {{"name": "markdown", "type": "text"}}]. Do NOT generate custom fields like "title", "date", etc. We extract raw HTML and markdown per item, then parse them separately.
- Match pagination_config structure to the most similar pagination example above
- SSR: pagination links have real href URLs → use next_page_link_template with {{}} placeholder, increment, first_page_number. NEVER use js_next_button.
- CSR: pagination uses href="#", onclick, data-link, or buttons → use js_next_button + js_selector. NEVER use next_page_link_template (except in hybrid scroll mode).
- baseSelector must select individual item containers (each tender/item as a separate element)
- For CSR, js_selector is the same concept as baseSelector (CSS for each item)
- Default crawlai_config: {{"text_mode": true, "page_timeout": 100000, "delay_before_return_html": 5}}
- If JS rendering needed, add "wait_for" to crawlai_config
- request_config: empty {{}}
- Cross-check: data_render_type must match pagination_config pattern (SSR↔URL-based, CSR↔JS click)

Return ONLY the JSON configuration object."""
