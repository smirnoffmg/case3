import logging
from unittest.mock import MagicMock

from case3.logging_config import (
    LLMExchange,
    begin_llm_exchange_log,
    configure_logging,
    get_llm_exchanges,
    log_llm_exchange,
    verbosity,
)


def test_collector_captures_exchanges() -> None:
    configure_logging(0)
    assert get_llm_exchanges() == []

    with begin_llm_exchange_log() as log:
        log_llm_exchange(logging.getLogger("test"), "prompt-a", "response-a")
        log_llm_exchange(logging.getLogger("test"), "prompt-b", "response-b")
        captured = get_llm_exchanges()

    assert captured == [
        LLMExchange(prompt="prompt-a", response="response-a"),
        LLMExchange(prompt="prompt-b", response="response-b"),
    ]
    assert log == captured
    assert get_llm_exchanges() == []


def test_yielded_log_keeps_exchanges_after_context_exit() -> None:
    with begin_llm_exchange_log() as log:
        log_llm_exchange(logging.getLogger("test"), "p", "r")

    assert len(log) == 1
    assert log[0].prompt == "p"
    assert get_llm_exchanges() == []


def test_collector_inactive_no_capture() -> None:
    configure_logging(0)
    log_llm_exchange(logging.getLogger("test"), "p", "r")
    assert get_llm_exchanges() == []


def test_stderr_logging_respects_verbosity_without_collector() -> None:
    configure_logging(0)
    logger = MagicMock()
    log_llm_exchange(logger, "p", "r")
    logger.debug.assert_not_called()

    configure_logging(2)
    assert verbosity() == 2
    log_llm_exchange(logger, "p", "r")
    logger.debug.assert_called_once()
    assert "chars" in logger.debug.call_args[0][0]

    configure_logging(3)
    log_llm_exchange(logger, "long-p", "long-r")
    assert logger.debug.call_count == 3
    prompt_msg_call = logger.debug.call_args_list[-2]
    assert prompt_msg_call[0][2] == "long-p"
