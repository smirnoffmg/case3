"""Streamlit UI for SQL security pipeline."""

from __future__ import annotations

import streamlit as st

from case3.config import DEFAULT_OLLAMA_BASE_URL, get_settings
from case3.pipeline import run_sql_security_pipeline

st.set_page_config(page_title="SQL Security System", layout="wide")
st.title("SQL Generation & Security Audit")

settings = get_settings()
_, base_url = settings.resolve_llm_credentials()
model_label = settings.llm_endpoint_label()

if not settings.openai_api_key and not settings.openai_base_url:
    st.info(
        f"`OPENAI_API_KEY` не задан — используется локальный Ollama "
        f"({DEFAULT_OLLAMA_BASE_URL}). Укажите `OPENAI_MODEL` в `.env`."
    )

st.caption(f"Модель: **{model_label}**")

task = st.text_area(
    "Опишите задачу на естественном языке",
    placeholder="Например: Список сотрудников с email, лимит 10",
    height=100,
)
max_iter = st.slider("Макс. итераций", 1, 10, 5)

if st.button("Сгенерировать и проверить", type="primary") and task.strip():
    with st.spinner("Генерация и аудит..."):
        result = run_sql_security_pipeline(task.strip(), max_iterations=max_iter)
    st.caption(f"Модель: {result.metadata.get('llm_mode', model_label)}")
    st.subheader("Итоговый SQL")
    st.code(result.final_sql, language="sql")
    st.metric("Одобрено", "Да" if result.approved else "Нет")
    st.metric("Итераций", result.iterations_used)
    with st.expander("Лог аудита"):
        st.markdown(result.audit_log)
    if result.iterations_log:
        st.subheader("Итерации")
        for entry in result.iterations_log:
            with st.expander(
                f"Итерация {entry.iteration}, риск {entry.audit_result.overall_risk_score:.1f}"
            ):
                st.code(entry.sql_query, language="sql")
                if entry.audit_result.vulnerabilities:
                    for v in entry.audit_result.vulnerabilities:
                        st.warning(f"{v.vuln_class}: {v.description}")
