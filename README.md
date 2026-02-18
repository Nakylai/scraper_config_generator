# Scraper Config Generator

Пакет `config_generator` превращает URL в валидную конфигурацию для скрапера. Он загружает страницу, анализирует её с помощью LLM, подтягивает похожие конфиги из векторного хранилища как few-shot примеры и генерирует финальный конфиг.

## Pipeline

```
URL
 │
 ▼
1. Fetch HTML          crawl4ai headless browser → raw HTML
 │
 ▼
2. Extract features    LLM → LLMFeatures (6 полей)
 │
 ▼
3. Find similar        embedding all-MiniLM-L6-v2 → ChromaDB cosine search → SimilarConfig[]
 │
 ▼
3.5 Pagination         9 статических примеров + динамические примеры из ChromaDB
 │
 ▼
4. Generate config     LLM → JSON → parse
 │
 ▼
5. Validate            Pydantic validation → GeneratedConfig
```

## Структура проекта

| Файл | Роль |
|------|------|
| `generator.py` | Оркестратор — 5-шаговый пайплайн (`ConfigGenerator.generate`) |
| `llm_client.py` | Обёртка над OpenAI — все LLM-вызовы через `LLMClient.call()`, логирование и трекинг токенов/стоимости |
| `feature_extractor.py` | Очистка HTML, отправка в LLM, парсинг в `LLMFeatures`. Извлечение пагинационного сниппета |
| `vector_store.py` | ChromaDB — хранение и поиск конфигов по similarity фич и pagination HTML |
| `prompts.py` | Шаблоны промптов: `TRAINING_FEATURE_PROMPT`, `INFERENCE_FEATURE_PROMPT`, `CONFIG_GENERATION_PROMPT` |
| `pagination_examples.py` | 9 статических few-shot примеров пагинации (SSR/CSR) + форматтер для RAG-примеров |
| `schemas.py` | Pydantic-модели: `LLMFeatures`, `GeneratedConfig`, `SimilarConfig` |
| `utils.py` | `clean_html`, `parse_json_response`, `ensure_dict` |

## Использование

```python
from config_generator import ConfigGenerator

gen = ConfigGenerator(
    api_key="sk-...",
    model="gpt-4.1-mini",
    chroma_dir="./chroma_db",
)

config = gen.generate(url="https://example.com/tenders", source_name="Example Portal")

# Статистика использования LLM
print(gen.llm_client.get_usage_summary())
```

## SSR vs CSR

Поле `data_render_type` определяет форму конфига:

| Сигнал в HTML пагинации | Тип рендера | Пагинация использует |
|--------------------------|-------------|----------------------|
| Реальные URL: `href="?page=2"` | SSR | `next_page_link_template`, `increment`, `first_page_number` |
| JS: `href="#"`, `onclick`, `<button>` | CSR | `js_next_button`, `js_selector` |

## Тестирование

```bash
pytest tests/config_generator/ -v
```

| Тест | Покрывает |
|------|-----------|
| `test_llm_client.py` | API, расчёт стоимости, аккумуляция токенов |
| `test_feature_extractor.py` | Очистка HTML, извлечение пагинации, парсинг фич |
| `test_generator.py` | Полный пайплайн, обработка ошибок |
| `test_vector_store.py` | ChromaDB add/search/reset |
| `test_schemas.py` | Валидация Pydantic-моделей |
| `test_pagination_examples.py` | Форматирование примеров |
| `test_utils.py` | `clean_html`, `parse_json_response`, `ensure_dict` |
