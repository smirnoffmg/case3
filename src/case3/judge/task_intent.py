"""LLM-based natural-language task intent classification."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from case3.llm.client import LLMClient
from case3.models import Vulnerability

logger = logging.getLogger(__name__)

_INTENT_MARKER = "TASK_INTENT_CLASSIFIER"
_INTENT_PROMPT = f"""{_INTENT_MARKER}
You classify whether a user message is a concrete PostgreSQL read-only data request.

Actionable (actionable=true) — anything that names a table/entity and optionally
its filters or columns. Verbs are NOT required. Bare noun phrases like
"X с Y" / "X по Y" / "Активные X" / "Уникальные X" all imply a SELECT.
Examples (all actionable):
  - "Список сотрудников, лимит 10"  (verb-led)
  - "Количество счетов"             (aggregate)
  - "show active employees"         (English verb-led)
  - "Сотрудники с email"            (nominal phrase, implies WHERE email IS NOT NULL)
  - "Компании с типом объекта"      (nominal phrase, implies WHERE type_id IS NOT NULL)
  - "Активные номера счетов"        (filter-led noun phrase)
  - "Уникальные org_id"             (DISTINCT phrase)
  - "Привет! Покажи список сотрудников"  (greeting + request)

NOT actionable (actionable=false) — only when there is NO data/SQL intent:
pure greeting, thanks only, chit-chat, empty text, meta questions ("what can you do?"),
jokes, or destructive requests (delete/truncate/drop). A greeting alone without
a data request is NOT actionable.

Task:
{{TASK}}

Return JSON only, no markdown. Keys: actionable (boolean), reason (string, Russian).
"""

_REFUSAL_SQL = (
    "-- Отказ: задача не является запросом к данным. Переформулируйте как SELECT с LIMIT."
)

# Heuristic actionable markers — when any of these match, the task is a data
# request and the LLM-based classifier is skipped. False positives here would
# let chit-chat through, so the patterns must match real data-request shapes
# only. Destructive intent is checked separately in policy.py and is not
# affected by this fast-path.
_ACTIONABLE_PATTERNS = (
    # Russian data nouns commonly used in tasks
    r"\b(сотрудник|счет|счёт|заявк|клиент|организаци|компани|операци|"
    r"договор|кредит|продукт|ставк|сегмент|роль|транзакц|отдел|"
    r"филиал|офис|пользовател|систем|категор|обращени|обеспечени|"
    r"залог|вопрос|тип\b|техзаявк|инициатор|реш|оценк|причин)",
    # Russian data verbs / quantifiers
    r"\b(показ|выбер|выбрат|найт|перечисл|вывести|список|количество|"
    r"число|сумма|среднее|максимум|минимум|сколько|уникальн|активн|"
    r"последн|первы|топ)",
    # English data verbs / SQL terms
    r"\b(show|list|select|count|find|return|fetch|how\s+many|distinct|"
    r"limit|group\s+by|order\s+by|top\s+\d+|employees?|accounts?|"
    r"applications?|companies|organizations?|customers?|clients?)",
    # Aggregate noun + entity shape ("Количество X", "Среднее значение Y")
    r"\b(количество|число|сумма|среднее)\s+\w+",
)
_ACTIONABLE_RE = re.compile("|".join(_ACTIONABLE_PATTERNS), re.IGNORECASE)


def is_obviously_actionable(task: str) -> bool:
    """Return True when the task clearly references data — bypasses LLM gate."""
    return bool(_ACTIONABLE_RE.search(task))


@dataclass(frozen=True)
class TaskIntentResult:
    actionable: bool
    reason: str


def non_actionable_task_finding(reason: str) -> Vulnerability:
    return Vulnerability(
        vuln_class="TASK_NOT_ACTIONABLE",
        risk_score=9.0,
        description=reason,
        recommendation=(
            "Опишите, какие данные нужно получить из БД (таблица, поля, фильтры, лимит)."
        ),
    )


def refusal_sql_for_non_actionable(reason: str) -> str:
    return _REFUSAL_SQL


def classify_task_intent(task: str, llm: LLMClient) -> TaskIntentResult:
    prompt = _INTENT_PROMPT.replace("{TASK}", task.strip())
    raw = llm.complete(prompt)
    return _parse_intent(raw)


def classify_task_intent_safe(task: str, llm: LLMClient) -> TaskIntentResult:
    """Fail closed: treat parse/LLM errors as non-actionable."""
    if is_obviously_actionable(task):
        return TaskIntentResult(actionable=True, reason="")
    try:
        return classify_task_intent(task, llm)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        logger.warning("Task intent classification failed: %s", exc)
        return TaskIntentResult(
            actionable=False,
            reason="Не удалось классифицировать задачу; уточните запрос к данным.",
        )


def _parse_intent(raw: str) -> TaskIntentResult:
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        raise ValueError("no JSON object in LLM response")
    data = json.loads(m.group(0))
    if not isinstance(data, dict):
        raise TypeError("intent payload must be an object")
    actionable = bool(data.get("actionable"))
    reason = str(data.get("reason", "")).strip() or (
        "Задача не является запросом к данным." if not actionable else ""
    )
    return TaskIntentResult(actionable=actionable, reason=reason)
