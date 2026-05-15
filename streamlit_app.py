"""Streamlit UI for SQL security pipeline."""

from __future__ import annotations

import streamlit as st

from case3.pipeline import run_sql_security_pipeline

st.set_page_config(page_title="SQL Security System", layout="wide")
st.title("SQL Generation & Security Audit")

task = st.text_area(
    "Опишите задачу на естественном языке",
    placeholder="Например: Список сотрудников с email, лимит 10",
    height=100,
)
use_stub = st.checkbox("Stub LLM (без API)", value=True)
max_iter = st.slider("Макс. итераций", 1, 10, 5)

if st.button("Сгенерировать и проверить", type="primary") and task.strip():
    with st.spinner("Генерация и аудит..."):
        result = run_sql_security_pipeline(
            task.strip(),
            max_iterations=max_iter,
            generator_kwargs={"force_stub": use_stub},
            auditor_kwargs={"force_stub": use_stub, "use_llm": not use_stub},
        )
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
