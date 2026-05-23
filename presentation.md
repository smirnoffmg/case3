# Презентация: Кейс 3 — Генерация SQL и аудит безопасности (v2)

---

## Слайд 1. Титул

**Кейс 3. Генерация SQL и аудит безопасности**

NL -> SQL для PostgreSQL с гибридным аудитом и итеративным исправлением.

- Команда: <ФИО участников, роли>
- Репозиторий: `<ссылка>`
- Стек: Python 3.12, uv, sqlglot, BM25 (rank_bm25 + pymorphy3), Ollama / OpenAI / Claude, PostgreSQL в Docker

---

## Слайд 2. Архитектура одним взглядом

Пайплайн `src/case3/pipeline.py`:

1. **Task Intent Gate** — rule-based fast-path по доменным ключевым словам, fallback на LLM-классификатор; отсекает приветствия, мета-вопросы, деструктив
2. **Generator** (`generator/prompt_rag.py`) — LLM + BM25-retrieval (лемматизация pymorphy3, FK-расширение)
3. **Hybrid Auditor** (`judge/auditor.py`) — статика (regex + sqlglot) ∪ LLM-судья, дедуп по `(class, line)`
4. **Approval policy** — `max_risk ≤ 4.0` AND нет hard-block (`risk ≥ 8.0`)
5. **Repair loop** — `FeedbackMemory` копит уроки + флаг регрессии, лимит 5 итераций / 60 c, early-exit `is_stuck()`
6. **Audit log** — markdown-отчёт со всеми итерациями и явным обоснованием порога

![pipeline](doc/img/C3_Component_Core.png)

---

## Слайд 3. Что мы знаем о тестовой БД (новый слайд)

`data/schema/data_model.sql` — слепок реальной кредитной системы банка **ПСБ** (~20 700 строк DDL, 60 таблиц).

**Подсистемы по префиксам:**

| Префикс                        | Подсистема                                                                 |
| ------------------------------ | -------------------------------------------------------------------------- |
| `sys_`                         | системные сущности (`sys_employee`, `sys_company`)                         |
| `acc_` / `count_turnover`      | ОСВ (оборотно-сальдовая ведомость)                                         |
| `scp_` (28 таблиц)             | СКП — Система Корпоративного Принятия решений                              |
| `ic_` / `mler_` / `corp_tech_` | параллельные потоки заявок (ИУ / МЮЭР / КТ)                                |
| `yaig_`                        | УАиГ — Управление Активами и Гарантиями                                    |
| `cb_interest_rate`             | ставки ЦБ                                                                  |
| `application_obj`              | родовая «заявка»                                                           |
| `ms_*` (13 таблиц)             | служебные MultiSelect-контейнеры (UUID-имена) — **не несут бизнес-смысла** |

**Известные ловушки:**

- Все таблицы имеют **14 одинаковых базовых полей** (`id, name, name__ru, name__en, status, ...`) — ORM-наследование на уровне приложения (`OWNER = moon_tuning`).
- **287 объявленных FK, только 12 активных** (остальные закомментированы в DDL).
- Имя инициатора заявки **не в `application_obj.name__ru`** — это имя самой заявки. Имя контрагента живёт в `sys_company` -> требуется JOIN через `initiator_id`.
- `*_application` таблицы — **дубли без FK-связей**, легитимная двусмысленность при формулировке «покажи заявки».

**Что починили на основе этого понимания:**

- Парсер схемы извлекает FK и из закомментированных блоков -> граф 6 -> **206 рёбер**.
- Ретривер исключает `ms_*` контейнеры -> 60 -> **47 бизнес-таблиц** в BM25-индексе.
- В промпт добавлены: подсказка «`application_obj` для общих «заявок», `scp_application` / `ic_application` / … только при упоминании подсистемы»; JOIN-пример для фильтра по имени инициатора.

![ddl](doc/img/ddl.png)

---

## Слайд 4. Критерий «Точность генерации SQL» (15 баллов)

**Цель:** Execution Accuracy ≥ 70%.

**Текущий результат (LLM: Ollama qwen2.5:7b):**

| метрика                | ast_normalized (основной) | result_set (Docker, справочно) |
| ---------------------- | ------------------------- | ------------------------------ |
| Execution Accuracy     | **34.2%** (26/76)         | **65.8%** (50/76)              |
| approval rate          | 100%                      | 100%                           |
| mean iterations        | 1.01                      | 1.01                           |
| gold validity          | —                         | 1.000                          |
| судья precision/recall | 1.0 / 1.0                 | 1.0 / 1.0                      |

`ast_normalized` — строгое структурное сравнение нормализованных запросов, не требует Docker.
`result_set` — сравнение по набору строк (PK-матч), требует PostgreSQL в Docker.

**Динамика result_set EA по итеративным фиксам (исторически):**

```
15.8% -> 17.1% -> 28.9% -> 42.1% -> 46.1% -> 59.2% -> 65.8%  [result_set]
23.7% -> 34.2%                                              [ast_normalized]
```

| Шаг                                                                                  | EA (result_set) |
| ------------------------------------------------------------------------------------ | --------------- |
| baseline (strict tuple match)                                                        | 15.8%           |
| + column projection (gold ⊆ pred columns)                                            | 17.1%           |
| + strip LIMIT before comparison                                                      | 28.9%           |
| + PK-set match (когда есть `id`)                                                     | 42.1%           |
| + Intent Gate fast-path + WHERE-rule prompt                                          | 46.1%           |
| + cleaned gold + JOIN few-shot                                                       | 59.2%           |
| + расширенный _DOMAIN_CONTEXT, правила MIN/MAX, «по признаку», TASK_SQL_MISMATCH fix | **65.8%**       |

**Динамика ast_normalized EA:**

| Шаг                                           | EA (ast_normalized) |
| --------------------------------------------- | ------------------- |
| baseline (строгое AST-сравнение)              | 23.7% (18/76)       |
| + исправление правил промпта (MIN/MAX, alias) | **34.2%** (26/76)   |

С Claude Sonnet 4.6 (реальный прогон, 76 задач): ast_normalized EA **31.6%**, approval_rate **94.7%**. Архитектура поддерживает три провайдера через `LLM_PROVIDER=anthropic|openai|ollama`.

---

## Слайд 5. Как считается EA: два режима сравнения

**Execution Accuracy** = доля задач, в которых сгенерированный SQL возвращает тот же результат, что и эталонный.

### Режим `ast_normalized` (основной; без Docker)

Сравнение через sqlglot AST с прагматическими послаблениями (`eval/metrics.py -> _normalize_ast`):

| Послабление                  | Обоснование                                                        |
| ---------------------------- | ------------------------------------------------------------------ |
| **Strip LIMIT**              | LIMIT — редакторский выбор в gold; пагинацию ловит `NO_PAGINATION` |
| **Drop проекционные алиасы** | `COUNT(*) AS cnt` ≡ `COUNT(*)` — одна семантика                    |
| **Drop `OFFSET 0`**          | Нет эффекта на результат                                           |

**Ограничение:** структурное сравнение — если предсказание добавило лишнюю колонку (`create_date`) или лишний `WHERE name IS NOT NULL`, AST их зафиксирует как расхождение, даже если строки в реальной БД совпадут.

Запуск: `uv run case3 eval` (без переменных окружения). **Результат: 34.2%.**

### Режим `result_set` (справочный; требует Docker)

Выполняет оба SQL на живом PostgreSQL и сравнивает наборы строк (`eval/db.py -> result_sets_equal`):

1. **Strip LIMIT** перед `fetch`
2. **PK-set match** — если оба возвращают `id`, сравниваем множества id (устойчиво к лишним колонкам и вариантам `name__ru`)
3. **Single-cell fallback** — для `MIN/MAX/COUNT` (матрица 1×1)
4. **Single-column fallback** — для `SELECT DISTINCT col`

```bash
make db-seed                                              # docker-compose up + seed_db.py
export EVAL_DATABASE_URL=postgresql://case3:case3@localhost:55432/demo_db
uv run case3 eval                                         # EA в режиме result_set
```

**Результат: 65.8%.** PK-матч принимает лишние колонки и `WHERE X IS NOT NULL` при ненулевых данных — это объясняет разрыв с ast_normalized.

**Ключевое различие:**

|                                      | ast_normalized | result_set                     |
| ------------------------------------ | -------------- | ------------------------------ |
| EA                                   | 34.2% (26/76)  | 65.8% (50/76)                  |
| Что проверяет                        | структуру SQL  | одинаковые строки по `id` в БД |
| Нужен Docker                         | нет            | да                             |
| Чувствителен к лишним колонкам       | **да**         | нет (PK-матч)                  |
| Чувствителен к `WHERE X IS NOT NULL` | **да**         | нет (если все строки не-null)  |

---

## Слайд 6. Критерий «Покрытие классов уязвимостей» (25 баллов)

**Реализовано 9 классов, по каждому риск 0–10:**

| Класс              | Слой         | Risk | Пример                                                |
| ------------------ | ------------ | ---- | ----------------------------------------------------- |
| `SQL_INJ_CLASSIC`  | static + LLM | 10.0 | `' \|\|` / `' +` концат.                              |
| `SQL_INJ_UNION`    | static + LLM | 9.0  | `... UNION SELECT password FROM users`                |
| `SQL_INJ_TIME`     | static + LLM | 8.0  | `pg_sleep(...)` / `WAITFOR DELAY`                     |
| `DML_NO_WHERE`     | static       | 9.0  | `DELETE FROM t` без WHERE                             |
| `DIRECT_SENSITIVE` | static + LLM | 6.0  | прямой `SELECT email, credit_amount`                  |
| `SELECT_STAR`      | static       | 5.0  | `SELECT *`                                            |
| `NO_PAGINATION`    | static       | 4.0  | SELECT с FROM без LIMIT                               |
| `PRIV_ESCALATE`    | static       | 8.0  | `GRANT / REVOKE / ALTER ROLE / EXECUTE` без концат.   |
| `PLPGSQL_UNSAFE`   | static       | 9.0  | `EXECUTE format(...)` без `USING` / EXECUTE с конкат. |

Плюс мета-классы судьи: `TASK_NOT_ACTIONABLE`, `TASK_SQL_MISMATCH`, `TASK_DESTRUCTIVE`, `DESTRUCTIVE_DML`, `NOT_VALID_SELECT`.

**Метрики на собственном датасете `vulns.jsonl` (54 строки, ≥ 5 примеров на класс):**
```
precision = 1.000   recall = 1.000   (по всем 9 классам)
```

![vulns](doc/img/vulns.png)

---

## Слайд 7. Критерий «Работа итеративного цикла» (25 баллов)

**Механизм:**

- `FeedbackMemory` (`memory/feedback.py`): описания и рекомендации по найденным классам
- Детектор **регрессий**: исчез -> вернулся -> флаг `THIS IS A REPEAT MISTAKE` идёт в repair-промпт
- `is_stuck(min_iterations=2)`: два прохода подряд с одинаковым набором классов -> early-exit, экономия LLM-вызовов
- Жёсткие лимиты: 5 итераций / 60 секунд

**Демо итеративного исправления** на специально подобранной задаче `"Покажи всё из сотрудников"`:

- Итерация 1: `SELECT * FROM sys_employee` -> `SELECT_STAR` + `NO_PAGINATION`, risk 5.0 -> rejected
- Итерация 2: явные колонки + `LIMIT 100`, risk 0.0 -> approved

На eval-наборе `mean_iterations = 1.00` — почти все задачи проходят с первой попытки благодаря качественному промпту и retrieval.

[СКРИНШОТ: audit log с итерациями, видно как риск падает 5.0 -> 0.0]

---

## Слайд 8. Критерий «Аналитика и отчётность» (15 баллов)

**Что выводит `case3 eval` в `reports/eval_<ts>.json`:**

- Pipeline: `execution_accuracy`, `execution_accuracy_mode`, `approval_rate`, `mean_iterations`, `mean_risk_delta`, `gold_validity_rate`
- Judge: aggregate + **per-class precision/recall** (9 классов)
- Samples: финальный SQL + matched-флаг по каждой из 76 задач

**Анализ ошибок ast_normalized (50 непрошедших из 76, при EA 34.2%):**

| Причина                     | N   | Пример                                                                       |
| --------------------------- | --- | ---------------------------------------------------------------------------- |
| Разный набор колонок        | ~18 | pred: `id, name`; gold: `id, name, ident`                                    |
| Лишний JOIN                 | ~12 | pred добавил JOIN к `sys_company` когда задача не требовала имени инициатора |
| Лишний/пропущенный ORDER BY | ~10 | pred добавил `ORDER BY create_date DESC` без указания в задаче               |
| Лишний `IS NOT NULL`        | ~5  | `WHERE name IS NOT NULL` при gold без WHERE                                  |
| Пропущенный WHERE           | ~3  | pred без фильтра, gold с `WHERE status = 1`                                  |
| Прочее                      | ~2  | extra WHERE без значения                                                     |

**Примечание по result_set (65.8%):** PK-матч по `id` «прощает» лишние колонки и `IS NOT NULL` при ненулевых данных -> 32 задачи дополнительно засчитываются. ast_normalized — строгий критерий без Docker.

---

## Слайд 9. Критерий «Прозрачность для пользователя» (10 баллов)

**Audit log (markdown) теперь содержит:**

- Блок «**Параметры аудита**» в шапке: пороги и формула одобрения
- В каждой итерации — строку «**Решение**»:
  - `одобрено — риск 0.0 ≤ порога 4.0 и нет hard-block (≥ 8.0)`
  - `отклонено — риск 5.0 > порога 4.0`
  - `отклонено — hard-block SQL_INJ_UNION (risk 9.0 ≥ 8.0)`
- Маркер `⛔ HARD-BLOCK` рядом с находками риском ≥ 8.0
- Финальное обоснование в виде выражения: `final_risk = 3.0 ≤ 4.0 AND no hard-block (≥ 8.0) -> APPROVED`

Скачивается из CLI (`--log-file out.md`) и из Streamlit-UI.

[СКРИНШОТ: реальный markdown-отчёт целиком — заголовок + одна-две итерации + явная строка решения]

---

## Слайд 10. Критерий «Воспроизводимость и качество кода» (10 баллов)

```bash
uv sync --dev
uv run python scripts/build_schema_index.py
make check                                  # ruff + mypy + pytest
make db-seed                                # PostgreSQL в docker + синтетика
uv run case3 run "Список сотрудников, лимит 10"
```

- `make check` = ruff + mypy + pytest (unit + integration) — **79/79 unit-тестов зелёные**
- Конфиг через `.env` (шаблон `.env.example`); три LLM-провайдера через единый `get_llm_client()`
- `docker-compose.yml` + `make db-seed` для оффлайн-БД с метриками EA
- README + README-dev.md + ADR 0001–0005 + audit-log внутри отчётов

![check](doc/img/make_check.png)

---

## Слайд 11. Критерий «Обоснованность архитектурных решений» (10 баллов)

**ADR (`doc/adr/`):**

- **ADR 0002** — система не исполняет SQL. *Альтернатива:* sandbox-исполнение — отвергнуто (read-only роль не защищает от утечек ПДн через корректный SELECT).
- **ADR 0003** — гибридный судья (статика + LLM всегда включены). *Альтернатива:* только LLM — отвергнуто (нестабильно на инъекциях с явным паттерном); только статика — не ловит семантику задачи.
- **ADR 0004** — max-risk + hard-block. *Альтернатива:* сумма рисков — отвергнуто (не блокирует одиночные критические находки).
- **ADR 0005** — Prompt + RAG (BM25), без fine-tuning. *Альтернатива:* fine-tuning — нет размеченного корпуса; ломается при изменении схемы.

**Выбор LLM:** Ollama (`qwen2.5:7b`) для локальной разработки; Claude Sonnet 4 для качества; OpenAI-совместимый прокси GreenData для прода — переключается через `LLM_PROVIDER=` без правок кода.

![adr](doc/img/adr.png)

---

## Слайд 12. Live demo

**Сценарий 1. Безопасная задача:**
`uv run case3 run "Список сотрудников с id и именем, лимит 10"`
-> одобрено за 1 итерацию.

**Сценарий 2. Уязвимость -> исправление:**
`uv run case3 run "Покажи всё из сотрудников" -vv`
-> итерация 1: `SELECT_STAR` + `NO_PAGINATION` (risk 5.0) -> rejected
-> итерация 2: явные колонки + LIMIT (risk 0.0) -> approved.

**Сценарий 3. Деструктив:**
`uv run case3 run "Удали всех клиентов старше 2020"`
-> Intent Gate блокирует с риском 9.0 (`TASK_DESTRUCTIVE`).

**Сценарий 4. Воспроизводимая метрика (без Docker):**
```bash
uv run case3 eval
jq .pipeline reports/eval_<latest>.json
```
-> EA = 0.342 (ast_normalized), approval = 1.000, judge P/R = 1.0/1.0.

**Сценарий 5. С Docker (эталонный результат):**
```bash
make db-seed
EVAL_DATABASE_URL=postgresql://case3:case3@localhost:55432/demo_db uv run case3 eval
jq .pipeline reports/eval_<latest>.json
```
-> EA = 0.658 (result_set), approval = 1.000, judge P/R = 1.0/1.0.

**Сценарий 6. Streamlit UI** — те же запросы в браузере, скачивание audit log.

[СКРИНШОТ: терминал с прогоном сценария 2, видно две итерации]

---

## Слайд 13. Дополнительный критерий «Поддержка PL/pgSQL» (+10 баллов)

Класс **`PLPGSQL_UNSAFE`** ловит:
- `EXECUTE format(...)` без `USING`
- `EXECUTE 'literal' || var` — конкатенация строк в динамическом SQL
- Различает от `PRIV_ESCALATE` (статичный `EXECUTE`, `GRANT/REVOKE/ALTER ROLE`)

В `vulns.jsonl` 7 строк с этим классом: precision / recall = **1.0 / 1.0**.

Оговорка: в реальном DDL (`data/schema/data_model.sql`) нет `CREATE FUNCTION/TRIGGER/VIEW/INDEX` — PL/pgSQL не используется в продовой схеме. Покрытие класса синтетическое, на собственном датасете.

[СКРИНШОТ: пример уязвимого `EXECUTE format(...)` + находка судьи с риском 9.0]

---

## Слайд 14. Дополнительный критерий «Авторский размеченный датасет» (+10 баллов)

- `data/dataset/tasks.jsonl`: **87 пар** NL -> ожидаемый SQL (русские задачи, разные подсистемы)
- `data/dataset/vulns.jsonl`: **54 строки**, ≥ 5 примеров на каждый из 9 классов уязвимостей
- Используется для:
  - Execution Accuracy генератора (на seeded DB через Docker)
  - precision / recall судьи по каждому классу (агрегатно и per-class)
- Покрытие требования «не менее 50 пар» по бонусному критерию ✓

DIRECT_SENSITIVE: 8
DML_NO_WHERE: 7
NO_PAGINATION: 26
PLPGSQL_UNSAFE: 7
PRIV_ESCALATE: 6
SELECT_STAR: 7
SQL_INJ_CLASSIC: 10
SQL_INJ_TIME: 6
SQL_INJ_UNION: 6

---

## Слайд 15. Итоги и распределение в команде

**Что реализовано:**
- Все 7 основных критериев закрыты, артефакты в репозитории
- 2 из 2 дополнительных критериев (PL/pgSQL поддержка + датасет ≥ 50 пар)
- Архитектура поддерживает три LLM-провайдера через единый фабричный интерфейс

**Что унесём дальше:**
- Расширение датасета адверсариальными примерами для LLM-судьи (где статика заведомо промахнётся)
- Подключение полной схемы ПСБ (сейчас 60 таблиц-срез из ~225)
- Доисполнение SQL в read-only sandbox как опциональный слой

**Роли:**
Оля Ожерельева - фея, координатор, голос разума
Кирилл Никулин - укротитель датасета, исследователь схемы БД
Максим Смирнов - делал "тык" по кнопкам, чуть-чуть ругался на сроки

---
