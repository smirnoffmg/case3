"""Integration tests: mock LLM so pytest does not call Ollama/OpenAI."""

from __future__ import annotations

import re

import pytest


class _FakeLLM:
    def complete(self, prompt: str) -> str:
        table = _guess_table(prompt)
        return f"```sql\nSELECT id, name FROM public.{table} WHERE status = 1 LIMIT 10;\n```"


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
