## Проверка функциональности (manual QA)

Ниже — пошаговая инструкция проверки, рассчитанная на локальный запуск и **без реальных LLM API** (используется fake LLM по умолчанию).

### 1) Подготовка окружения

```bash
uv sync --dev --group ui
```

### 2) Полная техническая проверка (качество кода)

```bash
make check
```

Ожидается: `ruff`/`mypy`/`pytest` проходят.

### 3) Проверка `schema_index` (парсинг DDL)

```bash
uv run case3 schema parse data/ddl/synthetic.sql
```

Ожидается:

- `tables: 5`
- перечисление `users/products/orders/order_items/payments`
- у `orders` 1 FK, у `order_items` 2 FK, у `payments` 1 FK

### 4) Проверка полного цикла NL→SQL→audit (offline)

```bash
uv run case3 run-task "Get first user id" --ddl data/ddl/synthetic.sql --audit /tmp/case3-audit.jsonl --use-fake-llm
```

Ожидается:

- на stdout выводится JSON `RunResult`
- `final_sql` содержит `SELECT id FROM users LIMIT 1`

### 4b) Проверка полного цикла с реальным LLM (опционально)

1) Задать ключ и модель (через `.env` или env vars):

```bash
export CASE3_OPENAI_API_KEY="..."
export CASE3_OPENAI_MODEL="gpt-4o-mini"
```

2) Запустить без fake LLM:

```bash
uv run case3 run-task "Get first user id" --ddl data/ddl/synthetic.sql --audit /tmp/case3-audit.jsonl --no-use-fake-llm
```

### 5) Проверка отчёта из audit log

```bash
uv run case3 audit show /tmp/case3-audit.jsonl
```

Ожидается:

- несколько строк вида `[timestamp] <event_type> {...}`
- присутствует `approved` или `exhausted`

### 6) Проверка evaluator (метрики итераций/риска)

```bash
uv run python scripts/eval.py
```

Ожидается JSON с ключами:

- `avg_iterations`
- `avg_max_risk`
- `repeated_classes_rate`

### 7) Проверка Streamlit UI (тонкая обёртка)

```bash
uv run streamlit run streamlit_app.py
```

Ожидается:

- в браузере открывается страница `SQL Generation & Security Audit (MVP)`
- по кнопке **Run** выдаётся результат и список итераций (offline fake LLM)

