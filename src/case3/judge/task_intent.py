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

Actionable (actionable=true): list, count, filter, report, or fetch rows from the database.
Examples: "Список сотрудников, лимит 10", "Количество счетов", "show active employees".
Also actionable when a greeting or polite phrase appears together with a data request, e.g.:
"Привет! Покажи список сотрудников с email, лимит 10", "Добрый день, сколько счетов в таблице".

NOT actionable (actionable=false): only when there is NO data/SQL intent — pure greeting, thanks only,
chit-chat, empty text, meta questions ("what can you do?"), jokes, or delete/truncate/drop requests.
A greeting alone without a data request is NOT actionable.

Task:
{{TASK}}

Return JSON only, no markdown. Keys: actionable (boolean), reason (string, Russian).
"""

_REFUSAL_SQL_TEMPLATE = (
    "-- Отказ: {reason} Переформулируйте задачу как запрос к данным (SELECT с LIMIT)."
)


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
    text = reason.strip() or "Задача не является запросом к данным."
    return _REFUSAL_SQL_TEMPLATE.format(reason=text)


def classify_task_intent(task: str, llm: LLMClient) -> TaskIntentResult:
    prompt = _INTENT_PROMPT.replace("{TASK}", task.strip())
    raw = llm.complete(prompt)
    return _parse_intent(raw)


def classify_task_intent_safe(task: str, llm: LLMClient) -> TaskIntentResult:
    """Fail closed: treat parse/LLM errors as non-actionable."""
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
