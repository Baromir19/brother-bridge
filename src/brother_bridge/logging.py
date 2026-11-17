"""Logging helpers.

Importing :mod:`brother_bridge` never touches the root logger configuration: the
package logger only carries a :class:`logging.NullHandler`, so applications keep
full control over handlers, formatters and levels. Call
:func:`configure_logging` for a ready-made setup in scripts and examples.
"""

from __future__ import annotations

import logging
import sys
from typing import IO

PACKAGE_LOGGER_NAME = "brother_bridge"

DEFAULT_FORMAT = "%(asctime)s %(levelname)-8s %(name)s | %(message)s"


def get_logger(name: str) -> logging.Logger:
    """Return the package logger for ``name``.

    Args:
        name: Usually ``__name__`` of the calling module.

    Returns:
        A child logger of :data:`PACKAGE_LOGGER_NAME`.
    """
    if not name or name == PACKAGE_LOGGER_NAME:
        return logging.getLogger(PACKAGE_LOGGER_NAME)

    if name.startswith(f"{PACKAGE_LOGGER_NAME}."):
        return logging.getLogger(name)

    return logging.getLogger(f"{PACKAGE_LOGGER_NAME}.{name}")


def configure_logging(
    level: int | str = logging.INFO,
    stream: IO[str] | None = None,
    fmt: str = DEFAULT_FORMAT,
) -> logging.Logger:
    """Attach a stream handler to the package logger.

    The handler is installed once; repeated calls only adjust the level.

    Args:
        level: Logging level for ``brother_bridge`` and its children.
        stream: Destination stream. Defaults to :data:`sys.stderr`.
        fmt: ``logging`` format string for the handler.

    Returns:
        The configured package logger.
    """
    logger = logging.getLogger(PACKAGE_LOGGER_NAME)
    logger.setLevel(level)

    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        handler = logging.StreamHandler(stream or sys.stderr)
        handler.setFormatter(logging.Formatter(fmt))
        logger.addHandler(handler)

    return logger


__all__ = [
    "DEFAULT_FORMAT",
    "PACKAGE_LOGGER_NAME",
    "configure_logging",
    "get_logger",
]
