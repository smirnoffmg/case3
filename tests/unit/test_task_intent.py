from case3.judge.task_intent import (
    _parse_intent,
    classify_task_intent,
    non_actionable_task_finding,
    refusal_sql_for_non_actionable,
)
from case3.llm.client import LLMClient


class _StubLLM:
    def __init__(self, response: str) -> None:
        self._response = response

    def complete(self, prompt: str) -> str:
        return self._response


def test_parse_intent_not_actionable():
    raw = '{"actionable": false, "reason": "Приветствие"}'
    result = _parse_intent(raw)
    assert result.actionable is False
    assert "Приветствие" in result.reason


def test_parse_intent_actionable():
    raw = '{"actionable": true, "reason": "Список сотрудников"}'
    result = _parse_intent(raw)
    assert result.actionable is True


def test_classify_task_intent_calls_llm():
    llm: LLMClient = _StubLLM('{"actionable": false, "reason": "test"}')
    result = classify_task_intent("Привет!", llm)
    assert not result.actionable


def test_parse_intent_actionable_greeting_plus_query():
    raw = '{"actionable": true, "reason": "Есть запрос к данным"}'
    result = _parse_intent(raw)
    assert result.actionable is True


def test_classify_mixed_greeting_and_query():
    llm: LLMClient = _StubLLM('{"actionable": true, "reason": "Запрос к данным"}')
    result = classify_task_intent("Привет! Список сотрудников, лимит 10", llm)
    assert result.actionable


def test_refusal_sql_contains_reason():
    sql = refusal_sql_for_non_actionable("Нет запроса к данным")
    assert "Отказ" in sql
    assert "Нет запроса к данным" in sql


def test_non_actionable_finding_risk():
    f = non_actionable_task_finding("x")
    assert f.vuln_class == "TASK_NOT_ACTIONABLE"
    assert f.risk_score >= 8.0
