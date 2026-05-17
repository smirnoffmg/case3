"""CLI verbosity → logging levels (-v, -vv, -vvv)."""

from __future__ import annotations

import logging
import sys

_PACKAGE = "case3"

# Set by configure_logging(); read via verbosity().
_verbosity: int = 0


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


def log_llm_exchange(logger: logging.Logger, prompt: str, response: str) -> None:
    """Log prompt/response detail according to -v depth."""
    v = _verbosity
    if v < 2:
        return
    if v >= 3:
        logger.debug("LLM prompt (%d chars):\n%s", len(prompt), prompt)
        logger.debug("LLM response (%d chars):\n%s", len(response), response)
    else:
        logger.debug("LLM prompt: %d chars, response: %d chars", len(prompt), len(response))
