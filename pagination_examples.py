"""Static few-shot pagination examples covering all data_render_type + pagination patterns.

Each example pairs a realistic HTML pagination snippet with the working config.
These are always included in the config generation prompt so the LLM can pattern-match
instead of following fragile rules.
"""

import json

from mini_scraper.config_generator.utils import ensure_dict

PAGINATION_EXAMPLES: list[dict] = [
    # ── SSR: query parameter (?page=N) ──────────────────────────────
    {
        "label": "SSR — query parameter (?page=N)",
        "pagination_html": (
            '<nav aria-label="pagination">\n'
            '  <ul class="pagination">\n'
            '    <li class="page-item active"><a class="page-link" href="?page=1">1</a></li>\n'
            '    <li class="page-item"><a class="page-link" href="?page=2">2</a></li>\n'
            '    <li class="page-item"><a class="page-link" href="?page=3">3</a></li>\n'
            '    <li class="page-item"><a class="page-link" href="?page=2">Next &raquo;</a></li>\n'
            '  </ul>\n'
            '</nav>'
        ),
        "data_render_type": "SSR",
        "pagination_config": {
            "increment": 1,
            "max_pages": 2,
            "first_page_number": 1,
            "next_page_link_template": "https://www.example.com/tenders?page={}",
        },
    },
    # ── SSR: path segment (/page/N) ─────────────────────────────────
    {
        "label": "SSR — path segment (/page/N)",
        "pagination_html": (
            '<div class="pagination">\n'
            '  <span class="current">1</span>\n'
            '  <a href="/call-for-tenders/page/2">2</a>\n'
            '  <a href="/call-for-tenders/page/3">3</a>\n'
            '  <a class="next" href="/call-for-tenders/page/2">&raquo;</a>\n'
            '</div>'
        ),
        "data_render_type": "SSR",
        "pagination_config": {
            "url": "https://www.example.org/en/call-for-tenders",
            "increment": 1,
            "max_pages": 2,
            "first_page_number": 1,
            "next_page_link_template": "https://www.example.org/en/call-for-tenders/page/{}",
        },
    },
    # ── SSR: offset-based (increment > 1) ───────────────────────────
    {
        "label": "SSR — offset-based pagination (increment=15)",
        "pagination_html": (
            '<ul class="pagination">\n'
            '  <li class="active"><a href="?offset=0&max=15">1</a></li>\n'
            '  <li><a href="?offset=15&max=15">2</a></li>\n'
            '  <li><a href="?offset=30&max=15">3</a></li>\n'
            '  <li class="next"><a href="?offset=15&max=15">&raquo;</a></li>\n'
            '</ul>'
        ),
        "data_render_type": "SSR",
        "pagination_config": {
            "increment": 15,
            "max_pages": 10,
            "first_page_number": 0,
            "next_page_link_template": "https://portal.example.org/list?offset={}&max=15&sort=date&order=desc",
        },
    },
    # ── SSR: no pagination ──────────────────────────────────────────
    {
        "label": "SSR — no pagination (single page)",
        "pagination_html": "<!-- No pagination elements found on the page -->",
        "data_render_type": "SSR",
        "pagination_config": {
            "max_pages": 1,
        },
    },
    # ── CSR: Bootstrap pagination with href="#" / data-link ─────────
    {
        "label": "CSR — href=\"#anchor\" + data-link attribute (JavaScript pagination)",
        "pagination_html": (
            '<ul class="pagination">\n'
            '  <li class="page-item active"><a class="page-link" href="#tenderPagination">1</a></li>\n'
            '  <li class="page-item"><a class="t_page page-link" href="#tenderPagination" '
            'data-link="https://www.example.com/tenders/20">2</a></li>\n'
            '  <li class="page-item"><a class="t_page page-link" href="#tenderPagination" '
            'data-link="https://www.example.com/tenders/40">3</a></li>\n'
            '  <li class="page-item"><a class="t_page page-link" href="#tenderPagination" '
            'data-link="https://www.example.com/tenders/20">Next</a></li>\n'
            '</ul>'
        ),
        "data_render_type": "CSR",
        "pagination_config": {
            "max_pages": 2,
            "js_selector": "table tbody tr",
            "js_next_button": 'document.querySelector("ul.pagination li:nth-last-child(2) a")?.click();',
        },
    },
    # ── CSR: DataTables plugin (a.paginate_button.next) ─────────────
    {
        "label": "CSR — DataTables plugin pagination",
        "pagination_html": (
            '<div class="dataTables_paginate paging_simple_numbers">\n'
            '  <a class="paginate_button previous disabled" id="table_previous">Previous</a>\n'
            '  <span>\n'
            '    <a class="paginate_button current">1</a>\n'
            '    <a class="paginate_button">2</a>\n'
            '    <a class="paginate_button">3</a>\n'
            '  </span>\n'
            '  <a class="paginate_button next" id="table_next">Next</a>\n'
            '</div>'
        ),
        "data_render_type": "CSR",
        "pagination_config": {
            "max_pages": 2,
            "js_selector": "table.dataTable tbody tr",
            "js_next_button": 'document.querySelector("a.paginate_button.next")?.click();',
        },
    },
    # ── CSR: Angular/EUI paginator (button-based) ───────────────────
    {
        "label": "CSR — Angular/EUI paginator (button element)",
        "pagination_html": (
            '<div class="eui-paginator">\n'
            '  <div class="eui-paginator__page-navigation">\n'
            '    <div><button class="eui-button" disabled>Previous</button></div>\n'
            '    <div><span>Page 1 of 5</span></div>\n'
            '    <div><button class="eui-button">Next</button></div>\n'
            '  </div>\n'
            '</div>'
        ),
        "data_render_type": "CSR",
        "pagination_config": {
            "max_pages": 2,
            "js_selector": "div > sedia-result-card-calls-for-tenders",
            "js_next_button": 'document.querySelector("div.eui-paginator__page-navigation div:nth-last-child(2) button")?.click();',
        },
    },
    # ── CSR: Angular Material mat-paginator ─────────────────────────
    {
        "label": "CSR — Angular Material mat-paginator",
        "pagination_html": (
            '<mat-paginator class="mat-paginator">\n'
            '  <div class="mat-paginator-container">\n'
            '    <div class="mat-paginator-range-label">1 – 10 of 200</div>\n'
            '    <button class="mat-paginator-navigation-previous" disabled></button>\n'
            '    <button class="mat-focus-indicator mat-paginator-navigation-next"></button>\n'
            '  </div>\n'
            '</mat-paginator>'
        ),
        "data_render_type": "CSR",
        "pagination_config": {
            "max_pages": 7,
            "js_selector": "table tbody tr",
            "js_next_button": 'document.querySelector("button.mat-focus-indicator.mat-paginator-navigation-next")?.click();',
        },
    },
    # ── CSR: Infinite scroll (hybrid — JS scroll + POST backend) ────
    {
        "label": "CSR — infinite scroll with POST backend (hybrid)",
        "pagination_html": (
            '<div class="notice-list">\n'
            '  <div class="notice-table">...</div>\n'
            '  <div class="notice-table">...</div>\n'
            '  <!-- Page loads more items on scroll, no visible pagination buttons -->\n'
            '</div>'
        ),
        "data_render_type": "CSR",
        "pagination_config": {
            "js_mode": "scroll",
            "page_key": "PageIndex",
            "increment": 1,
            "max_pages": 25,
            "js_selector": "div.notice-table",
            "js_next_button": "window.scrollTo(0, document.body.scrollHeight);",
            "first_page_number": 0,
            "next_page_link_template": "https://www.ungm.org/Public/Notice/Search",
        },
    },
]


def format_static_pagination_examples() -> str:
    """Format all static examples as text for the LLM prompt."""
    parts = ["=== STATIC PAGINATION REFERENCE EXAMPLES ==="]
    parts.append(
        "These examples cover all known pagination patterns. "
        "Study how the HTML maps to data_render_type and pagination_config.\n"
    )

    for ex in PAGINATION_EXAMPLES:
        parts.append(f"--- {ex['label']} ---")
        parts.append(f"Pagination HTML:\n  {ex['pagination_html']}")
        parts.append(f"data_render_type: {ex['data_render_type']}")
        parts.append(f"pagination_config: {json.dumps(ex['pagination_config'], indent=2)}")
        parts.append("")

    return "\n".join(parts)


def format_dynamic_pagination_examples(similar_configs: list) -> str:
    """Format RAG-retrieved pagination examples as text for the LLM prompt.

    Args:
        similar_configs: List of SimilarConfig objects with pagination_html field.
    """
    if not similar_configs:
        return ""

    parts = ["\n=== DYNAMIC PAGINATION EXAMPLES (similar to target page) ==="]
    parts.append(
        "These are from production configs with pagination HTML similar to the target page.\n"
    )

    for i, sc in enumerate(similar_configs, 1):
        config = sc.full_config
        pagination_config = ensure_dict(config.get("pagination_config", {}), default={})

        parts.append(f"--- Dynamic Example {i}: {sc.source_name} (distance: {sc.distance:.3f}) ---")

        if sc.pagination_html:
            parts.append(f"Pagination HTML:\n  {sc.pagination_html[:1000]}")

        parts.append(f"data_render_type: {config.get('data_render_type', 'N/A')}")
        parts.append(f"pagination_config: {json.dumps(pagination_config, indent=2)}")
        parts.append("")

    return "\n".join(parts)
