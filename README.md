# Генерация SQL и аудит безопасности (кейс 3)

MVP: задача на естественном языке, затем SQL для PostgreSQL, проверка безопасности и итеративное исправление до одобрения судьей или исчерпания лимита попыток.

## Быстрый старт

```bash
uv sync --dev
uv run python scripts/build_schema_index.py
uv run case3 run "Список сотрудников с email, лимит 10"
```

Требуется настроенная LLM (Ollama или API), см. [настройки](#настройки).

## Команды

| Команда                            | Описание                                |
| ---------------------------------- | --------------------------------------- |
| `case3 build-schema`               | Разбор DDL в `data/derived/schema.json` |
| `case3 run TASK`                   | Полный цикл генерации и аудита          |
| `case3 run TASK -v`                | Лог итераций (stderr)                   |
| `case3 run TASK -vv`               | + SQL, замечания, markdown-отчёт        |
| `case3 run TASK -vvv`              | + полные промпты/ответы LLM             |
| `case3 run TASK --log-file out.md` | Сохранить markdown-отчёт в файл         |
| `case3 eval`                       | Оффлайн-метрики по датасету             |
| `make check`                       | ruff + mypy + pytest                    |

## Интерфейс

```bash
uv sync --group ui
uv run streamlit run streamlit_app.py
```

## Настройки

Параметры задаются через файл `.env` в корне репозитория и переменные окружения.  
Имена переменных соответствуют полям в [`src/case3/config.py`](src/case3/config.py) (регистр не важен).

### LLM и модель

| Переменная        | По умолчанию  | Описание                                                                                                                                     |
| ----------------- | ------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `OPENAI_API_KEY`  | не задан      | Ключ облачного API. **Не нужен для Ollama** — при пустом ключе используется `http://localhost:11434/v1`.                                     |
| `OPENAI_MODEL`    | `gpt-4o-mini` | Идентификатор модели (OpenAI, Ollama, vLLM, API GreenData и т.д.).                                                                           |
| `OPENAI_BASE_URL` | не задан      | Базовый URL **OpenAI-совместимого** API (без `/chat/completions`). Подхватывается LangChain. Пример для Ollama: `http://localhost:11434/v1`. |
| `USE_LLM`         | `true`        | Семантический слой судьи (LLM). Статические проверки sqlglot работают всегда. При `false` судья только rule-based.                           |

**Локальная модель (Ollama):**

```bash
# .env
OPENAI_API_KEY=local
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=qwen2.5:7b
```

```bash
ollama serve
ollama pull qwen2.5:7b
uv run case3 run "Список сотрудников, лимит 10"
```

**Облако (OpenAI):**

```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

**API GreenData:** укажите выданные хост, ключ и имя модели в тех же переменных.

### Пайплайн

| Переменная        | По умолчанию | Описание                                          |
| ----------------- | ------------ | ------------------------------------------------- |
| `MAX_ITERATIONS`  | `5`          | Максимум циклов: генерация, аудит, исправление.   |
| `TIMEOUT_SEC`     | `60.0`       | Жесткий лимит времени на один запуск (секунды).   |
| `RETRIEVER_TOP_K` | `8`          | Сколько таблиц схемы подмешивать в промпт (BM25). |

### Пути к данным

| Переменная           | По умолчанию                  | Описание                                          |
| -------------------- | ----------------------------- | ------------------------------------------------- |
| `SCHEMA_DDL_PATH`    | `data/schema/data_model.sql`  | DDL тестовой БД.                                  |
| `SCHEMA_JSON_PATH`   | `data/derived/schema.json`    | Кэш разобранной схемы (создается `build-schema`). |
| `SENSITIVITY_PATH`   | `data/sensitivity.yaml`       | Паттерны чувствительных полей (ПДн).              |
| `FEW_SHOT_PATH`      | `data/examples/few_shot.yaml` | Few-shot примеры для генератора.                  |
| `DATASET_TASKS_PATH` | `data/dataset/tasks.jsonl`    | Эталоны NL-SQL для `case3 eval`.                  |
| `DATASET_VULNS_PATH` | `data/dataset/vulns.jsonl`    | Размеченные уязвимые SQL для оценки судьи.        |
| `REPORTS_DIR`        | `reports/`                    | Каталог отчетов `case3 eval`.                     |

### Пример `.env`

```bash
# Модель
OPENAI_API_KEY=local
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=qwen2.5:7b
USE_LLM=true

# Пайплайн
MAX_ITERATIONS=5
TIMEOUT_SEC=60
RETRIEVER_TOP_K=8
```

Файл `.env` не коммитится (см. `.gitignore`).

### Поведение судьи

| Условие                       | Генератор            | Судья (статика) | Судья (LLM) |
| ----------------------------- | -------------------- | --------------- | ----------- |
| `USE_LLM=true` (по умолчанию) | LangChain, вызов API | Да              | Да          |
| `USE_LLM=false`               | LangChain, вызов API | Да              | Нет         |

Без ключа и без `OPENAI_BASE_URL` по умолчанию вызывается локальный Ollama. Для OpenAI Cloud задайте `OPENAI_API_KEY`.

Рекомендации по кейсу: модели до ~30B параметров, контекст до 256k токенов; полный DDL в промпт не передается, только выборка схемы через RAG.

---

Разработка и тесты: [README-dev.md](README-dev.md), [TESTING.md](TESTING.md).
