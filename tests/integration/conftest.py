"""Integration tests: mock LLM so pytest does not call Ollama/OpenAI."""

from __future__ import annotations

import json
import re

import pytest

from case3.judge.task_intent import _INTENT_MARKER

_DATA_INTENT_CUES = (
    "список",
    "лимит",
    "limit",
    "сотрудник",
    "employee",
    "счет",
    "счёт",
    "сколько",
    "количество",
    "найти",
    "покаж",
    "вывед",
    "count",
    "email",
    "организ",
    "таблиц",
)

_GREETING_WORDS = frozenset(
    {
        "привет",
        "hello",
        "hi",
        "hey",
        "добрый",
        "день",
        "утро",
        "вечер",
        "здравствуй",
        "спасибо",
        "thanks",
        "thank",
        "you",
    }
)


class _FakeLLM:
    def complete(self, prompt: str) -> str:
        if _INTENT_MARKER in prompt:
            return _fake_task_intent(prompt)
        if "Natural language task:" in prompt:
            return "[]"
        table = _guess_table(prompt)
        return f"```sql\nSELECT id, name FROM public.{table} WHERE status = 1 LIMIT 10;\n```"


def _extract_task_from_intent_prompt(prompt: str) -> str:
    m = re.search(r"Task:\s*\n(.+?)\n\nReturn JSON", prompt, re.DOTALL)
    return m.group(1).strip() if m else prompt


def _has_data_intent(text: str) -> bool:
    low = text.lower()
    return any(cue in low for cue in _DATA_INTENT_CUES)


def _is_pure_greeting(task: str) -> bool:
    low = task.lower().strip()
    if _has_data_intent(low):
        return False
    words = re.findall(r"\w+", low, flags=re.UNICODE)
    if not words:
        return True
    return all(w in _GREETING_WORDS for w in words)


def _fake_task_intent(prompt: str) -> str:
    task = _extract_task_from_intent_prompt(prompt)
    if _is_pure_greeting(task):
        return json.dumps(
            {"actionable": False, "reason": "Приветствие, нет запроса к данным"},
            ensure_ascii=False,
        )
    return json.dumps({"actionable": True, "reason": "Запрос к данным"}, ensure_ascii=False)


def _guess_table(prompt: str) -> str:
    m = re.search(r"public\.(\w+)", prompt)
    if m:
        return m.group(1)
    m = re.search(r"Table:\s*(\w+)", prompt, re.I)
    if m:
        return m.group(1)
    low = prompt.lower()
    if any(w in low for w in ("сотрудник", "employee", "email", "почт")):
        return "sys_employee"
    if any(w in low for w in ("счет", "счёт", "acc_number", "account")):
        return "acc_number"
    if any(w in low for w in ("организ", "org")):
        return "org"
    if any(w in low for w in ("транзак", "transaction", "trans")):
        return "afhd_ac_trans_link"
    return "sys_employee"


@pytest.fixture(autouse=True)
def _mock_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("case3.llm.client.get_llm_client", lambda *a, **k: _FakeLLM())
