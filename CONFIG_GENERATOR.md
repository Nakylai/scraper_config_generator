# config_generator — Developer Guide

The `config_generator` package turns a URL into a validated scraping configuration. It fetches a page, analyzes it with an LLM, pulls similar configs from a vector store as few-shot examples, and asks the LLM to produce a final config.

## Files

| File | Role |
|------|------|
| `generator.py` | Orchestrator — runs the 5-step pipeline (`ConfigGenerator.generate`) |
| `llm_client.py` | Shared OpenAI wrapper — every LLM call goes through `LLMClient.call()`, which handles debug logging and token/cost tracking |
| `feature_extractor.py` | Cleans HTML, sends it to the LLM, parses the response into `LLMFeatures`. Also contains `extract_pagination_html()` for pulling the pagination snippet |
| `vector_store.py` | ChromaDB wrapper — stores and retrieves configs by feature similarity (`find_similar`) and pagination HTML similarity (`find_similar_pagination`) |
| `prompts.py` | Three prompt templates: `TRAINING_FEATURE_PROMPT`, `INFERENCE_FEATURE_PROMPT`, `CONFIG_GENERATION_PROMPT` |
| `pagination_examples.py` | 9 static few-shot pagination examples (SSR/CSR patterns) + formatter for dynamic RAG examples |
| `schemas.py` | Pydantic models: `LLMFeatures`, `GeneratedConfig`, `SimilarConfig` |
| `utils.py` | `clean_html`, `parse_json_response`, `ensure_dict` |

## Pipeline

`ConfigGenerator.generate(url, source_name)` runs these steps:

```
URL
 │
 ▼
1. Fetch HTML          crawl4ai headless browser → raw HTML string
 │
 ▼
2. Extract features    LLMClient.call(INFERENCE_FEATURE_PROMPT) → LLMFeatures (6 fields)
 │
 ▼
3. Find similar        embed features with all-MiniLM-L6-v2 → ChromaDB cosine search → SimilarConfig[]
 │
 ▼
3.5 Pagination         static examples (always 9) + dynamic examples from ChromaDB by pagination HTML
 │
 ▼
4. Generate config     LLMClient.call(CONFIG_GENERATION_PROMPT) → JSON string → parse_json_response
 │
 ▼
5. Validate            GeneratedConfig(**parsed_dict) — Pydantic validation
```

Steps 2 and 4 both go through the same `LLMClient` instance, so token usage and cost accumulate in one place. Call `generator.llm_client.get_usage_summary()` after `generate()` to get totals.

## Key data structures

### LLMFeatures

Extracted by the LLM in step 2. Used for vector similarity search in step 3.

```python
LLMFeatures(
    page_structure="table with rows",        # layout description
    item_container_pattern="table tbody tr",  # CSS selector for items
    pagination_mechanism="url_parameter",     # url_parameter | next_button_click | infinite_scroll | none
    data_render_type="SSR",                   # SSR | CSR
    listing_type="tenders",                   # what the page lists
    has_detail_links=True,                    # items link to detail pages?
)
```

`to_text()` produces a single string for embedding:
```
structure:table with rows | container:table tbody tr | pagination:url_parameter | render_type:SSR | listing:tenders | detail_links:True
```

### GeneratedConfig

The final output of the pipeline (step 5):

```python
GeneratedConfig(
    data_render_type="SSR",           # SSR or CSR
    json_css_schema={...},            # baseSelector + fields
    crawlai_config={...},             # browser options (timeouts, wait_for)
    pagination_config={...},          # how to paginate
    request_config={...},             # extra request options (headers)
)
```

### SimilarConfig

Returned by `ConfigVectorStore.find_similar()` and `find_similar_pagination()`:

```python
SimilarConfig(
    config_id="source_123",
    source_name="Example Portal",
    distance=0.15,                    # cosine distance (lower = more similar)
    full_config={...},                # complete stored config dict
    features_text="structure:...",
    pagination_html="<nav>...</nav>",
)
```

## How LLM calls work

All LLM communication goes through `LLMClient` (`llm_client.py`):

```python
client = LLMClient(api_key="...", model="gpt-4.1-mini")
text = client.call(prompt, step_label="config_generation")
print(client.get_usage_summary())
```

`call()` does:
1. Logs the full prompt to `config_generator.llm_debug` logger (DEBUG level)
2. Sends `messages=[{"role": "user", "content": prompt}]` with `temperature=0.1`
3. Accumulates `prompt_tokens`, `completion_tokens`, and cost
4. Logs the full response
5. Returns `response.choices[0].message.content` as a string

Cost calculation uses `OPENAI_PRICING` dict (per 1K tokens). Unknown models return cost = 0.

## How vector search works

`ConfigVectorStore` wraps ChromaDB with `all-MiniLM-L6-v2` embeddings.

**Two search modes used during generation:**

| Method | Input | Matches by |
|--------|-------|------------|
| `find_similar(features)` | `LLMFeatures` object | Feature text embedding — semantic similarity (e.g. "table of tenders" matches "table of tenders") |
| `find_similar_pagination(html)` | Pagination HTML snippet | Pagination HTML embedding — structural similarity (e.g. DataTables markup matches DataTables markup) |

Both return `list[SimilarConfig]` sorted by cosine distance.

**Indexing** is a separate process, not part of generation. `add_config()` stores:
- Feature text embedding (for step 3 similarity search)
- Pagination HTML as metadata (for step 3.5 similarity search)
- Full config as serialized JSON (returned in search results as few-shot examples)

Without indexed configs, both searches return empty results and the LLM relies on the 9 static pagination examples only.

## How pagination examples work

The LLM prompt in step 4 receives two sets of pagination examples:

**Static** (always present) — 9 hardcoded examples in `pagination_examples.py`:

| Pattern | Example |
|---------|---------|
| SSR query param | `?page=N` |
| SSR path segment | `/page/N` |
| SSR offset | `?offset=0&max=15`, increment > 1 |
| SSR no pagination | `max_pages: 1` |
| CSR href="#" + data-link | `href="#anchor"` with `data-link` attribute |
| CSR DataTables | `a.paginate_button.next` |
| CSR Angular/EUI | `<button>` element paginator |
| CSR mat-paginator | Angular Material component |
| CSR infinite scroll | `js_mode: "scroll"`, hybrid with POST backend |

**Dynamic** (from RAG) — `extract_pagination_html()` finds the pagination element on the target page using a list of CSS selectors (`nav[aria-label*='pagination']`, `ul.pagination`, `.dataTables_paginate`, `mat-paginator`, etc.). That HTML snippet is embedded and searched against ChromaDB. Matching configs are appended to the prompt as additional few-shot examples.

## SSR vs CSR decision

The `data_render_type` field drives the entire config shape. The LLM decides it based on pagination links:

| Signal in pagination HTML | Render type | Pagination config uses |
|---------------------------|-------------|----------------------|
| Real URLs: `href="?page=2"`, `href="/path/page/3"` | SSR | `next_page_link_template`, `increment`, `first_page_number` |
| JS-driven: `href="#"`, `onclick`, `data-link`, `<button>` elements | CSR | `js_next_button`, `js_selector` |

These rules are spelled out in both `INFERENCE_FEATURE_PROMPT` and `CONFIG_GENERATION_PROMPT`.

## Constructor wiring

```python
# generator.py
class ConfigGenerator:
    def __init__(self, api_key, model, chroma_dir):
        self.llm_client = LLMClient(api_key=api_key, model=model)
        self.feature_extractor = LLMFeatureExtractor(llm_client=self.llm_client)
        self.vector_store = ConfigVectorStore(persist_dir=chroma_dir)
```

One `LLMClient` is shared between `feature_extractor` (step 2) and `generator` (step 4), so usage stats cover both calls.

## Two feature extraction modes

| Mode | Method | Input | Used for |
|------|--------|-------|----------|
| Training | `extract_training_features(html, config)` | HTML + known working config | Indexing existing configs into vector store |
| Inference | `extract_inference_features(html, url)` | HTML only | Generating config for a new URL |

Both return the same `LLMFeatures` structure, which ensures embedding compatibility in the vector store: training features and inference features live in the same space.

## Testing

Tests are in `tests/config_generator/`. `LLMClient` and `openai.OpenAI` are always mocked.

| Test file | Covers |
|-----------|--------|
| `test_llm_client.py` | API dispatch, cost calculation, token accumulation |
| `test_feature_extractor.py` | HTML cleaning, pagination extraction, feature parsing, LLM call integration |
| `test_generator.py` | Full pipeline happy path, error handling, config formatting |
| `test_vector_store.py` | ChromaDB add/search/reset |
| `test_schemas.py` | Pydantic model defaults and validation |
| `test_pagination_examples.py` | Static/dynamic example formatting |
| `test_utils.py` | `clean_html`, `parse_json_response`, `ensure_dict` |

```bash
pytest tests/config_generator/ -v
```
