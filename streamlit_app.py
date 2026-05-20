"""Streamlit UI for SQL security pipeline."""

from __future__ import annotations

from typing import Literal

import streamlit as st

from case3.config import DEFAULT_OLLAMA_BASE_URL, LLMProvider, Settings, get_settings
from case3.logging_config import (
    LLMExchange,
    begin_llm_exchange_log,
    configure_logging,
)
from case3.pipeline import run_sql_security_pipeline

DetailLevel = Literal["minimal", "standard", "full"]
ProviderOption = Literal["ollama", "openai", "anthropic"]
_PROVIDER_LABELS: dict[ProviderOption, str] = {
    "ollama": "Ollama (локально)",
    "openai": "OpenAI",
    "anthropic": "Claude (Anthropic)",
}


def _init_session_defaults(settings: Settings) -> None:
    if "ui_provider" not in st.session_state:
        try:
            st.session_state.ui_provider = settings.resolve_llm_provider().value
        except Exception:
            st.session_state.ui_provider = "ollama"
    if "ui_model" not in st.session_state:
        st.session_state.ui_model = settings.openai_model
    if "ui_anthropic_model" not in st.session_state:
        st.session_state.ui_anthropic_model = settings.anthropic_model
    if "ui_base_url" not in st.session_state:
        st.session_state.ui_base_url = settings.openai_base_url or ""
    if "api_key_ui" not in st.session_state:
        st.session_state.api_key_ui = ""
    if "anthropic_api_key_ui" not in st.session_state:
        st.session_state.anthropic_api_key_ui = ""


def _build_effective_settings(settings: Settings) -> Settings:
    provider = str(st.session_state.ui_provider)
    updates: dict[str, object] = {
        "llm_provider": provider,
        "retriever_top_k": int(st.session_state.retriever_top_k),
    }

    if provider == "anthropic":
        updates["anthropic_model"] = (
            str(st.session_state.ui_anthropic_model).strip() or settings.anthropic_model
        )
        anthropic_key_ui = str(st.session_state.anthropic_api_key_ui).strip()
        if anthropic_key_ui:
            updates["anthropic_api_key"] = anthropic_key_ui
    else:
        updates["openai_model"] = str(st.session_state.ui_model).strip() or settings.openai_model
        updates["openai_base_url"] = str(st.session_state.ui_base_url).strip() or None
        api_key_ui = str(st.session_state.api_key_ui).strip()
        if api_key_ui:
            updates["openai_api_key"] = api_key_ui

    return settings.model_copy(update=updates)


def _render_llm_sidebar(settings: Settings) -> None:
    st.sidebar.subheader("LLM")

    st.sidebar.selectbox(
        "Провайдер",
        options=list(_PROVIDER_LABELS.keys()),
        format_func=lambda x: _PROVIDER_LABELS[x],
        key="ui_provider",
        help="LLM_PROVIDER — ollama, openai или anthropic.",
    )

    provider = st.session_state.ui_provider

    if provider == "anthropic":
        st.sidebar.text_input(
            "Claude model",
            key="ui_anthropic_model",
            help="ANTHROPIC_MODEL",
        )
        st.sidebar.text_input(
            "Anthropic API KEY",
            type="password",
            key="anthropic_api_key_ui",
            help="Не сохраняется на диск; пустое — ключ из `.env`.",
        )
    else:
        if provider == "ollama":
            st.sidebar.text_input(
                "LLM URL",
                key="ui_base_url",
                placeholder=DEFAULT_OLLAMA_BASE_URL,
                help="OPENAI_BASE_URL — OpenAI-совместимый API (Ollama).",
            )
        st.sidebar.text_input(
            "LLM MODEL",
            key="ui_model",
            help="OPENAI_MODEL",
        )
        if provider == "openai":
            st.sidebar.text_input(
                "OpenAI API KEY",
                type="password",
                key="api_key_ui",
                help="Не сохраняется на диск; пустое — ключ из `.env`.",
            )
        else:
            st.sidebar.text_input(
                "LLM API KEY (опционально)",
                type="password",
                key="api_key_ui",
                help="Для Ollama обычно не нужен.",
            )


def _render_pipeline_sidebar(settings: Settings) -> tuple[int, float, int, DetailLevel]:
    st.sidebar.subheader("Пайплайн")
    max_iter = st.sidebar.slider(
        "Макс. итераций",
        1,
        10,
        settings.max_iterations,
        key="max_iterations",
    )
    timeout_sec = st.sidebar.slider(
        "Таймаут (с)",
        10,
        120,
        int(settings.timeout_sec),
        key="timeout_sec",
    )
    retriever_top_k = st.sidebar.slider(
        "Таблиц в RAG (top_k)",
        1,
        20,
        settings.retriever_top_k,
        key="retriever_top_k",
    )
    detail_level: DetailLevel = st.sidebar.selectbox(
        "Детализация результата",
        options=["minimal", "standard", "full"],
        format_func=lambda x: {"minimal": "Минимум", "standard": "Стандарт", "full": "Полная"}[x],
        index=1,
        key="detail_level",
    )
    st.sidebar.checkbox(
        "Показать LLM промпты/ответы",
        key="show_llm_log",
        help="Промпты и ответы модели в интерфейсе; только в RAM сессии, на диск не пишется.",
    )
    return max_iter, float(timeout_sec), retriever_top_k, detail_level


def _render_results(
    result: object,
    detail_level: DetailLevel,
    model_label: str,
) -> None:
    from case3.models import SystemResult

    assert isinstance(result, SystemResult)

    st.caption(f"Модель: {result.metadata.get('llm_mode', model_label)}")

    meta = result.metadata
    if meta.get("refusal") == "non_actionable_task":
        reason = str(meta.get("refusal_reason", ""))
        if result.iterations_log:
            reason = reason or result.iterations_log[0].audit_result.summary
        st.error(reason or "Задача не является запросом к данным. Уточните формулировку.")
    badges: list[str] = []
    if meta.get("timeout_reached"):
        badges.append("Таймаут")
    if meta.get("regression_detected"):
        badges.append("Регрессия риска")
    if meta.get("refusal"):
        badges.append(f"Отказ: {meta['refusal']}")
    if badges:
        st.warning(" | ".join(badges))

    st.subheader("Итоговый SQL")
    st.code(result.final_sql, language="sql")
    col1, col2 = st.columns(2)
    col1.metric("Одобрено", "Да" if result.approved else "Нет")
    col2.metric("Итераций", result.iterations_used)

    st.download_button(
        "Скачать лог аудита",
        data=result.audit_log,
        file_name="audit_log.md",
        mime="text/markdown",
    )

    if detail_level == "minimal":
        return

    with st.expander("Лог аудита", expanded=detail_level == "full"):
        st.markdown(result.audit_log)

    if not result.iterations_log:
        return

    st.subheader("Итерации")
    for entry in result.iterations_log:
        with st.expander(
            f"Итерация {entry.iteration}, риск {entry.audit_result.overall_risk_score:.1f}",
            expanded=detail_level == "full",
        ):
            st.code(entry.sql_query, language="sql")
            if entry.audit_result.vulnerabilities:
                for v in entry.audit_result.vulnerabilities:
                    if detail_level == "full":
                        st.warning(
                            f"**{v.vuln_class}** (риск {v.risk_score:.1f}): {v.description}\n\n"
                            f"Рекомендация: {v.recommendation}"
                        )
                    else:
                        st.warning(f"{v.vuln_class}: {v.description}")


def _render_llm_exchanges(exchanges: list[LLMExchange], show: bool) -> None:
    if not show:
        return
    st.subheader("LLM")
    if not exchanges:
        st.caption("Нет записей LLM за этот прогон.")
        return
    for i, ex in enumerate(exchanges, start=1):
        with st.expander(
            f"Вызов {i} — промпт {len(ex.prompt)} симв., ответ {len(ex.response)} симв."
        ):
            st.markdown("**Промпт**")
            st.code(ex.prompt, language="text")
            st.markdown("**Ответ**")
            st.code(ex.response, language="text")


def _render_provider_hint(effective: Settings) -> None:
    try:
        provider = effective.resolve_llm_provider()
    except Exception as exc:
        st.error(str(exc))
        return

    if (
        provider == LLMProvider.OLLAMA
        and not effective.openai_api_key
        and not effective.openai_base_url
    ):
        st.info(
            f"`OPENAI_API_KEY` не задан — используется локальный Ollama "
            f"({DEFAULT_OLLAMA_BASE_URL}). Укажите модель в боковой панели или `.env`."
        )
    elif provider == LLMProvider.ANTHROPIC and not effective.anthropic_api_key:
        st.warning("Задайте `ANTHROPIC_API_KEY` в `.env` или в боковой панели.")
    elif provider == LLMProvider.OPENAI and not effective.openai_api_key:
        st.warning("Задайте `OPENAI_API_KEY` в `.env` или в боковой панели.")


def main() -> None:
    settings = get_settings()
    layout = (
        settings.streamlit_layout if settings.streamlit_layout in ("centered", "wide") else "wide"
    )
    st.set_page_config(page_title=settings.streamlit_page_title, layout=layout)
    st.title("SQL Generation & Security Audit")

    _init_session_defaults(settings)
    _render_llm_sidebar(settings)
    max_iter, timeout_sec, _top_k, detail_level = _render_pipeline_sidebar(settings)
    effective = _build_effective_settings(settings)

    model_label = effective.llm_endpoint_label()
    _render_provider_hint(effective)

    if not settings.schema_json_path.is_file():
        st.warning(
            f"Схема не найдена: `{settings.schema_json_path}`. "
            "Выполните: `uv run case3 build-schema`"
        )

    st.caption(f"Модель: **{model_label}**")

    task = st.text_area(
        "Опишите задачу на естественном языке",
        placeholder="Например: Список сотрудников с email, лимит 10",
        height=100,
        key="task_input",
    )

    if st.button("Сгенерировать и проверить", type="primary") and task.strip():
        show_llm_log = bool(st.session_state.get("show_llm_log"))
        if show_llm_log:
            configure_logging(3)
        with st.spinner("Генерация и аудит..."):
            if show_llm_log:
                with begin_llm_exchange_log() as llm_exchanges:
                    result = run_sql_security_pipeline(
                        task.strip(),
                        max_iterations=max_iter,
                        timeout_sec=timeout_sec,
                        settings_override=effective,
                    )
            else:
                result = run_sql_security_pipeline(
                    task.strip(),
                    max_iterations=max_iter,
                    timeout_sec=timeout_sec,
                    settings_override=effective,
                )
                llm_exchanges = []
        _render_results(result, detail_level, model_label)
        _render_llm_exchanges(llm_exchanges, show_llm_log)


if __name__ == "__main__":
    main()
