"""CLI verbosity → logging levels (-v, -vv, -vvv) and optional LLM exchange capture."""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

_PACKAGE = "case3"

# Set by configure_logging(); read via verbosity().
_verbosity: int = 0


@dataclass(frozen=True)
class LLMExchange:
    prompt: str
    response: str


_llm_exchange_log: ContextVar[list[LLMExchange] | None] = ContextVar(
    "llm_exchange_log", default=None
)


def verbosity() -> int:
    return _verbosity


def configure_logging(verbosity_count: int = 0) -> int:
    """Map -v count to log levels. Returns the count stored."""
    global _verbosity
    _verbosity = max(0, verbosity_count)

    if _verbosity >= 2:
        level = logging.DEBUG
    elif _verbosity == 1:
        level = logging.INFO
    else:
        level = logging.WARNING

    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=level,
            format="%(levelname)s %(message)s",
            stream=sys.stderr,
        )
    else:
        root.setLevel(level)

    logging.getLogger(_PACKAGE).setLevel(level)
    return _verbosity


def get_llm_exchanges() -> list[LLMExchange]:
    """Return captured LLM I/O while ``begin_llm_exchange_log`` is active."""
    log = _llm_exchange_log.get()
    if log is None:
        return []
    return list(log)


@contextmanager
def begin_llm_exchange_log() -> Iterator[list[LLMExchange]]:
    """Capture full prompt/response pairs; yields the live list (safe to keep after exit)."""
    log: list[LLMExchange] = []
    token = _llm_exchange_log.set(log)
    try:
        yield log
    finally:
        _llm_exchange_log.reset(token)


def log_llm_exchange(logger: logging.Logger, prompt: str, response: str) -> None:
    """Append to the active exchange log and/or log to stderr per -v depth."""
    log = _llm_exchange_log.get()
    if log is not None:
        log.append(LLMExchange(prompt=prompt, response=response))

    v = _verbosity
    if v < 2:
        return
    if v >= 3:
        logger.debug("LLM prompt (%d chars):\n%s", len(prompt), prompt)
        logger.debug("LLM response (%d chars):\n%s", len(response), response)
    else:
        logger.debug("LLM prompt: %d chars, response: %d chars", len(prompt), len(response))
