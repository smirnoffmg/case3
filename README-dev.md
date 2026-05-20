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

| Symptom                                  | Likely cause                                                                 |
| ---------------------------------------- | ---------------------------------------------------------------------------- |
| Cloud API 401 / forbidden                | Set real `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` for the chosen provider     |
| Both keys set, startup error             | Set explicit `LLM_PROVIDER=openai` or `anthropic`                            |
| `PermissionDeniedError` / api.openai.com | `OPENAI_BASE_URL` missing or wrong (OpenAI path)                             |
| Connection refused                       | Ollama not on port 11434                                                     |
| Model not found                          | `ollama pull <OPENAI_MODEL>`                                                 |
| Timeout / exit 1                         | Raise `TIMEOUT_SEC` or use a smaller model                                   |
