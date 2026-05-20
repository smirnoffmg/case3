## Dev (uv + ruff + mypy)

### Setup

```bash
uv sync --dev
uv run python scripts/build_schema_index.py
```

Minimal `.env` for local Ollama (no API key):

```bash
OPENAI_MODEL=qwen2.5:7b
```

Optional overrides:

```bash
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=local   # only if your proxy requires a non-empty header
```

### Tests

```bash
uv run pytest
```

Integration tests mock the LLM in `tests/integration/conftest.py`; they do not call Ollama.

### Lint / format

```bash
uv run ruff check .
uv run ruff format .
```

### Types

```bash
uv run mypy .
```

### All checks

```bash
make check
```

---

## Как это работает внутри

### Схема данных: от DDL до индекса

Всё начинается с файла `data/schema/data_model.sql` — это обычный PostgreSQL DDL-дамп.
Скрипт `scripts/build_schema_index.py` читает его и превращает в `data/derived/schema.json`.

**Что происходит при парсинге** (`schema_index/parser.py`):

1. Регулярными выражениями находятся все `CREATE TABLE` — извлекаются имена таблиц и колонок.
2. Затем собираются `COMMENT ON TABLE` и `COMMENT ON COLUMN` — русскоязычные описания, которые потом помогают LLM и BM25 понять, что лежит в таблице.
3. Парсятся `FOREIGN KEY ... REFERENCES` — строится граф связей между таблицами.

После парсинга происходит обогащение:

- **PII-маркировка** (`schema_index/pii.py`): каждая колонка проверяется по списку паттернов из `data/sensitivity.yaml` (email, phone, inn, snils…). Если имя колонки совпадает — ставится флаг `sensitive = True`. Этот флаг потом использует статический аудитор для детектирования `DIRECT_SENSITIVE`.
- **Дополнение FK-графа** (`schema_index/graph.py`): помимо явных `FOREIGN KEY`, добавляются эвристические рёбра — если колонка называется `org_id`, а таблица `org` существует, то ребро `-> org.id` добавляется автоматически.

Результат — `SchemaIndex`: словарь таблиц с колонками и список FK-рёбер — сериализуется в JSON.

---

### BM25-ретривер: как выбираются таблицы

Когда приходит задача на естественном языке, нужно понять, какие таблицы вообще подходят. Весь контекст схемы (60 таблиц, тысячи колонок) в LLM не влезет — нужен отбор.

**Что делает `SchemaRetriever`** (`schema_index/retriever.py`):

1. При инициализации для каждой таблицы строится **BM25-документ** — строка из имени таблицы и её комментария, повторённых 3 раза:
   ```
   sys_employee sys employee Сотрудник  (x 3)
   ```
   Комментарии предварительно очищаются от шума — вырезается Java-метаданные вида `SysObjTypeEffective{id=..., ident='...'}`, которые остались в дампе от платформы.

2. Документ токенизируется (`_tokenize`):
   - Текст разбивается регуляркой `[а-яёa-z0-9]+` — разделителями служат любые не-буквы (пробелы, слэши, скобки, двоеточия).
   - Русские токены **лемматизируются** через `pymorphy3`: `"сотрудников"` -> `"сотрудник"`, `"кредитные"` -> `"кредитный"`. Без этого шага русские падежи и формы не совпадают с именами таблиц.
   - Предлоги и союзы (`по`, `в`, `из`, `и`…) выкидываются как стоп-слова.
   - Английские токены: срезается финальная `-s` (`employees` -> `employee`).

3. Из всех документов строится **BM25-индекс** (библиотека `rank-bm25`).

4. При запросе токенизируется текст задачи тем же способом и считаются BM25-оценки. Если максимальная оценка ниже порога `0.5` — возвращается fallback (первые K таблиц из индекса). Иначе — топ-K по убыванию оценки.

5. Поверх BM25-результата запускается **FK-расширение**: для каждой найденной таблицы в результат добавляются соседи по FK-графу (не более 3 дополнительных таблиц). Это помогает с запросами вроде "сотрудники с организацией" — BM25 находит `sys_employee`, а FK-расширение автоматически подтягивает связанную таблицу.

> **Почему только имя + комментарий, без колонок?**

С 50+ колонками в таблице длина документа становится огромной. BM25 нормирует оценку по длине, и таблицы с большим числом колонок системно проигрывают компактным таблицам даже при совпадении нужного слова.

---

### Генератор SQL: RAG + LLM

**`PromptRAGGenerator`** (`generator/prompt_rag.py`):

1. BM25-ретривер возвращает список `TableContext` (имя, очищенный комментарий, список колонок с типами и `[PII]`-метками).
2. Из этого строится текстовый контекст схемы и подставляется в промпт.
3. На первой итерации — **начальный промпт** (`build_initial_prompt`): описание задачи + контекст схемы + 2 few-shot примера из `data/examples/few_shot.yaml`.
4. На последующих итерациях — **ремонтный промпт** (`build_repair_prompt`): добавляется история предыдущих SQL, список уязвимостей (отсортированных по риску), накопленные уроки из памяти.

LLM возвращает текст; из него регуляркой вырезается SQL из ` ```sql ` блока.

---

### Гибридный аудитор

Аудит проходит в два слоя (`judge/auditor.py`):

**Статический анализатор** (`judge/static.py`) — быстрые детерминированные проверки:

| Класс              | Что ищет                                          |
| ------------------ | ------------------------------------------------- |
| `SQL_INJ_CLASSIC`  | Конкатенация строк (`\|\|`, `+`) с литералами     |
| `SQL_INJ_UNION`    | Наличие `UNION`                                   |
| `SQL_INJ_TIME`     | `pg_sleep()`, `WAITFOR DELAY`                     |
| `DML_NO_WHERE`     | `UPDATE`/`DELETE` без `WHERE` (через sqlglot AST) |
| `SELECT_STAR`      | `SELECT *`                                        |
| `NO_PAGINATION`    | `SELECT` без `LIMIT` (кроме агрегатов)            |
| `DIRECT_SENSITIVE` | Обращение к PII-колонкам из `sensitivity.yaml`    |
| `PLPGSQL_UNSAFE`   | `EXECUTE format(...)` без `USING`                 |
| `PRIV_ESCALATE`    | Динамический `EXECUTE`                            |

**LLM-судья** (`judge/llm.py`) — семантический слой: получает SQL + описание задачи, находит то, что регулярки не видят (`TASK_SQL_MISMATCH`, намеренные обходы политик и т.д.).

Оба результата объединяются дедупликацией по `(vuln_class, line_hint)`.

**Политика одобрения**: запрос одобряется если `max(risk) <= 4.0` **и** нет ни одной находки с риском `>= 8.0` (hard block). Одна критическая находка блокирует независимо от остальных.

---

### Цикл repair

Если запрос отклонён — `Orchestrator` (`orchestrator/system.py`) запускает новую итерацию:

1. `FeedbackMemory` (`memory/feedback.py`) накапливает уроки из всех находок. Если класс уязвимости появлялся, исчезал, а затем вернулся — урок помечается как `⚠️ THIS IS A REPEAT MISTAKE`.
2. Уроки передаются в `PromptRAGGenerator.set_lessons()` и попадают в ремонтный промпт.
3. Если последние 2 итерации дали **одинаковый набор классов уязвимостей** — цикл останавливается досрочно (`is_stuck()`), чтобы не тратить LLM-вызовы на заведомо неразрешимую задачу.
4. Максимум 5 итераций, таймаут 60 секунд.

---

## Validate locally with Ollama

### Prerequisites

1. [Ollama](https://ollama.com/) running (`ollama serve` or desktop app).
2. Model pulled: `ollama pull qwen2.5:7b`
3. Schema index: `uv run python scripts/build_schema_index.py`

### Smoke test

```bash
uv run case3 run "Список сотрудников с email, лимит 10"
uv run case3 run "Список сотрудников с email, лимит 10" -vv   # agent log on stderr
```

Verbosity (logs go to **stderr**, SQL result stays on **stdout**):

| Flag   | Level   | What you see                                       |
| ------ | ------- | -------------------------------------------------- |
| (none) | WARNING | Final SQL + approved summary only                  |
| `-v`   | INFO    | Iterations, audit summary, LLM endpoint            |
| `-vv`  | DEBUG   | SQL per step, vulnerabilities, full audit markdown |
| `-vvv` | DEBUG   | Full LLM prompts and responses                     |

### Eval (uses live LLM for pipeline tasks)

```bash
uv run case3 eval
# or
make eval
```

Report JSON in `reports/` includes `llm.provider`, `llm.model`, and `llm.base_url`.

### Validate with OpenAI

```bash
LLM_PROVIDER=openai OPENAI_API_KEY=sk-... OPENAI_MODEL=gpt-4o-mini \
  uv run case3 run "Список сотрудников с email, лимит 10"
```

### Validate with Claude (Anthropic)

```bash
LLM_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-ant-... \
  ANTHROPIC_MODEL=claude-sonnet-4-20250514 \
  uv run case3 run "Список сотрудников с email, лимит 10"
```

### Streamlit UI

```bash
uv sync --group ui
uv run streamlit run streamlit_app.py
```

### Troubleshooting

| Symptom                                  | Likely cause                                                             |
| ---------------------------------------- | ------------------------------------------------------------------------ |
| Cloud API 401 / forbidden                | Set real `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` for the chosen provider |
| Both keys set, startup error             | Set explicit `LLM_PROVIDER=openai` or `anthropic`                        |
| `PermissionDeniedError` / api.openai.com | `OPENAI_BASE_URL` missing or wrong (OpenAI path)                         |
| Connection refused                       | Ollama not on port 11434                                                 |
| Model not found                          | `ollama pull <OPENAI_MODEL>`                                             |
| Timeout / exit 1                         | Raise `TIMEOUT_SEC` or use a smaller model                               |
